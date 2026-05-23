"""
Monitor de vendinha Herosaga.

Uso:
    python bot.py

Variáveis de ambiente:
- TOKEN: token do bot Telegram
- CHAT_ID: chat id para enviar notificações
- SHOP_URL: url da lojinha
- DISCORD_WEBHOOK: webhook opcional para futuras notificações no Discord
- NOTIFY_COOLDOWN: tempo mínimo entre alertas do mesmo item, em segundos
- REQUEST_TIMEOUT: timeout das requisições HTTP, em segundos

O script faz scraping da página da vendinha, salva histórico em data/history.json,
detecta quedas de quantidade (venda) e notifica via Telegram/Discord.
Ele executa um único ciclo por processo, o que o torna compatível com GitHub Actions.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv()

SHOP_URL = os.getenv("SHOP_URL", "https://herosaga.com.br/?module=vending&action=viewshop&id=30313")
TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

COOLDOWN = int(os.getenv("NOTIFY_COOLDOWN", "300"))  # segundos entre notificações por item
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))

DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "history.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vend-monitor")


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_history():
    ensure_data_dir()
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Histórico corrompido ou inválido; reiniciando estado local")
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
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def send_telegram(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        logger.warning("Telegram não configurado; pulando envio")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.ok:
            logger.info("Alerta enviado")
            return True
        else:
            logger.warning("Falha ao enviar Telegram: %s", r.text)
            return False
    except Exception as e:
        logger.exception("Erro enviando Telegram: %s", e)
        return False


def send_discord(text: str) -> bool:
    if not DISCORD_WEBHOOK:
        return False
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": text}, timeout=10)
        if r.ok:
            logger.info("Alerta enviado via Discord")
            return True
        else:
            logger.warning("Falha ao enviar Discord: %s", r.text)
            return False
    except Exception:
        logger.exception("Erro enviando Discord")
        return False


def notify_sale(name: str, before: int, after: int) -> bool:
    now = datetime.utcnow().isoformat()
    text = f"VENDA DETECTADA: {name}\nAntes: {before} -> Agora: {after}\nLoja: {SHOP_URL}\nHora(UTC): {now}"
    telegram_sent = send_telegram(text)
    discord_sent = send_discord(text)
    if telegram_sent or discord_sent:
        logger.info("Alerta enviado para %s", name)
        return True
    return False


def check_once(history: dict) -> dict:
    quantities = history.get("quantities", {})
    notified = history.get("notified", {})

    logger.info("Verificando mercado")
    html = fetch_shop(SHOP_URL)
    items = parse_shop(html)
    if not items:
        logger.warning("Nenhum item detectado na página — verifique o parser ou a URL.")
    else:
        logger.info("Itens encontrados na loja: %d", len(items))

    now_ts = int(time.time())
    changes = []
    for name, qty in items.items():
        logger.info("Item encontrado: %s | quantidade=%s", name, qty)
        prev = quantities.get(name)
        if prev is None:
            quantities[name] = qty
            continue
        if qty < prev:
            last_notif = int(notified.get(name, 0))
            if now_ts - last_notif >= COOLDOWN:
                if notify_sale(name, prev, qty):
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
    logger.info("Monitor iniciado | loja=%s | cooldown=%ss", SHOP_URL, COOLDOWN)
    if not TOKEN or not CHAT_ID:
        logger.error("TOKEN e CHAT_ID são obrigatórios para enviar alertas no Telegram")
        raise SystemExit(1)

    history = load_history()
    try:
        result = check_once(history)
        logger.info(
            "Verificação concluída: %d item(ns) encontrados, %d mudança(s), histórico salvo=%s",
            result["items_found"],
            len(result["changes"]),
            result["saved"],
        )
        logger.info("Execução finalizada")
    except requests.RequestException:
        logger.exception("Erro da API/HTTP ao consultar o mercado")
        raise SystemExit(1)
    except Exception:
        logger.exception("Erro na execução do monitor")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
