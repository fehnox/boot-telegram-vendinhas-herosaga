"""
Monitor de vendinha Herosaga

Uso: python bot.py

Configurar `.env` com as variáveis:
- BOT_TOKEN: token do bot Telegram
- TELEGRAM_CHAT_ID: chat id para enviar notificações
- SHOP_URL: (opcional) url da lojinha — padrão já configurado
- DISCORD_WEBHOOK: (opcional) webhook para enviar notificações ao Discord

O script faz scraping da página da vendinha, salva histórico em `data/history.json`,
detecta quedas de quantidade (venda) e notifica via Telegram/Discord.
"""

import os
import time
import json
import re
import logging
import argparse
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv()

SHOP_URL = os.getenv("SHOP_URL", "https://herosaga.com.br/?module=vending&action=viewshop&id=30313")
BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # segundos
COOLDOWN = int(os.getenv("NOTIFY_COOLDOWN", "300"))  # segundos entre notificações por item

DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "history.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vend-monitor")


def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)


def load_history():
    ensure_data_dir()
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"quantities": {}, "notified": {}}
    return {"quantities": {}, "notified": {}}


def save_history(history: dict):
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_shop(html: str) -> dict:
    """Tenta extrair pares nome->quantidade da página da vendinha.
    Usa heurísticas: varre <tr>, linhas com números, e busca por padrões comuns.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = {}

    # Heurística 1: procurar linhas de tabela
    for tr in soup.find_all("tr"):
        texts = [t.strip() for t in tr.stripped_strings]
        if not texts:
            continue
        # coletar tokens que contenham números
        num_tokens = [s for s in texts if re.search(r"\d+", s)]
        if not num_tokens:
            continue
        # quantity: usar último número encontrado na linha
        qty_match = re.search(r"(\d+)(?!.*\d)", " ".join(texts))
        if not qty_match:
            continue
        qty = int(qty_match.group(1))
        # name: juntar tokens sem o número encontrado
        joined = " ".join(texts)
        name = re.sub(r"\b" + re.escape(qty_match.group(1)) + r"\b", "", joined)
        name = re.sub(r"\s{2,}", " ", name).strip()
        if name and len(name) < 200:
            items[name] = qty

    # Heurística 2: procurar blocos com classes que contenham 'item' ou 'vending'
    if not items:
        for div in soup.find_all(class_=re.compile(r"item|vending|produto|shop", re.I)):
            texts = [t.strip() for t in div.stripped_strings]
            if not texts:
                continue
            qty_match = None
            for s in texts:
                m = re.search(r"\b(\d+)\b", s)
                if m:
                    qty_match = m
            if qty_match:
                qty = int(qty_match.group(1))
                name = " ".join([t for t in texts if qty_match.group(1) not in t])
                name = re.sub(r"\s{2,}", " ", name).strip()
                if name:
                    items[name] = qty

    # Heurística final: tentar mapear por linhas de texto (fallback)
    if not items:
        text = soup.get_text("\n")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.search(r"(.+?)\b(\d+)\b$", line)
            if m:
                name = m.group(1).strip()
                qty = int(m.group(2))
                items[name] = qty

    return items


def fetch_shop(url: str) -> str:
    headers = {"User-Agent": "vend-monitor/1.0 (+https://github.com)"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text


def send_telegram(text: str):
    if not BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram não configurado; pulando envio")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            logger.warning("Falha ao enviar Telegram: %s", r.text)
    except Exception as e:
        logger.exception("Erro enviando Telegram: %s", e)


def send_discord(text: str):
    if not DISCORD_WEBHOOK:
        return
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": text}, timeout=10)
        if not r.ok:
            logger.warning("Falha ao enviar Discord: %s", r.text)
    except Exception:
        logger.exception("Erro enviando Discord")


def notify_sale(name: str, before: int, after: int):
    now = datetime.utcnow().isoformat()
    text = f"🛒 VENDA DETECTADA: {name}\nAntes: {before} → Agora: {after}\nLoja: {SHOP_URL}\nHora(UTC): {now}"
    logger.info(text)
    send_telegram(text)
    send_discord(text)


def check_once(history: dict) -> bool:
    quantities = history.get("quantities", {})
    notified = history.get("notified", {})

    html = fetch_shop(SHOP_URL)
    items = parse_shop(html)
    if not items:
        logger.warning("Nenhum item detectado na página — verifique o parser ou a URL.")

    now_ts = int(time.time())
    changes = []
    for name, qty in items.items():
        prev = quantities.get(name)
        if prev is None:
            quantities[name] = qty
            continue
        if qty < prev:
            last_notif = int(notified.get(name, 0))
            if now_ts - last_notif >= COOLDOWN:
                notify_sale(name, prev, qty)
                notified[name] = now_ts
                changes.append((name, prev, qty))
            else:
                logger.debug("Venda detectada mas em cooldown para %s", name)
        quantities[name] = qty

    if changes:
        logger.info("Notificadas %d venda(s)", len(changes))

    history["quantities"] = quantities
    history["notified"] = notified
    save_history(history)
    return {
        "items_found": len(items),
        "changes": changes,
        "saved": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Monitor de vendinha Herosaga")
    parser.add_argument("--once", action="store_true", help="Executa uma checagem e encerra")
    args = parser.parse_args()

    logger.info("Monitor iniciando para %s", SHOP_URL)
    history = load_history()
    if args.once:
        try:
            result = check_once(history)
            logger.info(
                "Verificação única concluída: %d item(ns) encontrados, %d venda(s) detectada(s), histórico salvo=%s",
                result["items_found"],
                len(result["changes"]),
                result["saved"],
            )
        except Exception:
            logger.exception("Erro na verificação única")
        return

    while True:
        try:
            check_once(history)
        except Exception:
            logger.exception("Erro no loop de verificação")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
