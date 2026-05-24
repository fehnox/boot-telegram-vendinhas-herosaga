"""
Monitor de vendinha Herosaga.

Uso:
    python bot.py

Variáveis de ambiente:
- TOKEN: token do bot Telegram
- CHAT_ID: chat id para enviar notificações
- SHOP_URL: url da lojinha
- DISCORD_WEBHOOK: webhook opcional para futuras notificações no Discord
- DISCORD_MESSAGE: texto personalizado opcional para mensagens no Discord
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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT_DIR / "config"
SHOP_URLS_FILE = CONFIG_DIR / "shop_urls.txt"
DATA_DIR = ROOT_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"

load_dotenv(ROOT_DIR / ".env")

DEFAULT_SHOP_URL = "https://herosaga.com.br/?module=vending&action=viewshop&id=30313"
# Prefere as variáveis usadas no .env local, sem perder compatibilidade com o GitHub Actions.
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")
# `CHAT_IDS` prepara o envio para múltiplos usuários sem quebrar o fluxo atual.
CHAT_IDS = [chat.strip() for chat in os.getenv("CHAT_IDS", "").split(",") if chat.strip()]
if not CHAT_IDS and CHAT_ID:
    CHAT_IDS = [CHAT_ID]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_MESSAGE = os.getenv("DISCORD_MESSAGE", "").strip()
SHOP_URL = os.getenv("SHOP_URL", DEFAULT_SHOP_URL)
STORE_TARGETS = []


@dataclass(frozen=True)
class StoreTarget:
    name: str
    url: str


def parse_store_target(line: str, index: int) -> StoreTarget | None:
    raw = line.strip()
    if not raw:
        return None

    if "|" in raw:
        parts = [part.strip() for part in raw.split("|", 1)]
        name = parts[0] or f"loja-{index}"
        url = parts[1]
    else:
        name = f"loja-{index}"
        url = raw

    if not url:
        return None

    return StoreTarget(name=name, url=url)


def load_store_targets() -> list[StoreTarget]:
    env_value = os.getenv("SHOP_URLS", "").strip()
    if env_value:
        targets = []
        raw_items = []
        for line in env_value.splitlines():
            raw_items.extend([part.strip() for part in line.split(",") if part.strip()])

        for raw in raw_items:
            target = parse_store_target(raw, len(targets) + 1)
            if target:
                targets.append(target)

        if targets:
            return targets

    if SHOP_URLS_FILE.exists():
        targets = []
        for line in SHOP_URLS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            target = parse_store_target(line, len(targets) + 1)
            if target:
                targets.append(target)
        if targets:
            return targets

    fallback = (os.getenv("SHOP_URL", DEFAULT_SHOP_URL) or DEFAULT_SHOP_URL).strip()
    return [StoreTarget(name="loja-1", url=fallback)]


STORE_TARGETS = load_store_targets()

COOLDOWN = int(os.getenv("NOTIFY_COOLDOWN", "300"))  # segundos entre notificações por item
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
STATE_VERSION = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("vend-monitor")


def build_message_prefix(target: StoreTarget) -> str:
    return f"Loja: {target.name}\nURL: {target.url}\n"


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_history():
    ensure_data_dir()
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if history.get("version") == STATE_VERSION:
                return history

            if isinstance(history, dict) and ("stores" in history or "quantities" in history or "notified" in history):
                migrated = {"version": STATE_VERSION, "stores": {}, "alerts": {}}

                if isinstance(history.get("stores"), dict):
                    migrated["stores"] = history.get("stores", {})
                elif history.get("quantities") is not None or history.get("notified") is not None:
                    legacy_store_key = STORE_TARGETS[0].url if STORE_TARGETS else SHOP_URL
                    migrated["stores"][legacy_store_key] = {
                        "quantities": history.get("quantities", {}),
                        "last_alerts": history.get("notified", {}),
                    }

                if isinstance(history.get("alerts"), dict):
                    migrated["alerts"] = history.get("alerts", {})

                logger.info("Histórico migrado para o formato atual")
                save_history(migrated)
                return migrated

            return history
        except Exception:
            logger.warning("Histórico corrompido ou inválido; reiniciando estado local")
            return {"version": STATE_VERSION, "stores": {}, "alerts": {}}
    return {"version": STATE_VERSION, "stores": {}, "alerts": {}}


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


def telegram_api_request(method: str, payload: dict | None = None) -> requests.Response:
    if not TOKEN:
        raise RuntimeError("TOKEN ausente")

    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    return requests.post(url, json=payload or {}, timeout=10)


def send_telegram(text: str, chat_ids: list[str] | None = None) -> bool:
    recipients = chat_ids or CHAT_IDS
    if not TOKEN or not recipients:
        logger.warning("Telegram não configurado; pulando envio")
        return False
    sent_any = False
    try:
        for chat_id in recipients:
            payload = {"chat_id": chat_id, "text": text, "disable_notification": True}
            r = telegram_api_request("sendMessage", payload)
            if r.ok:
                logger.info("Alerta enviado")
                sent_any = True
            else:
                logger.error("Erro Telegram: %s", r.text)
        return sent_any
    except Exception as e:
        logger.exception("Erro Telegram: %s", e)
        return False


def build_discord_message(default_text: str) -> str:
    if not DISCORD_MESSAGE:
        return default_text

    message = DISCORD_MESSAGE
    replacements = {
        "{default}": default_text,
        "{text}": default_text,
    }
    for key, value in replacements.items():
        message = message.replace(key, value)
    return message or default_text


def send_discord(text: str) -> bool:
    if not DISCORD_WEBHOOK:
        return False
    try:
        payload_text = build_discord_message(text)
        r = requests.post(DISCORD_WEBHOOK, json={"content": payload_text}, timeout=10)
        if r.ok:
            logger.info("Alerta enviado via Discord")
            return True
        else:
            logger.warning("Falha ao enviar Discord: %s", r.text)
            return False
    except Exception:
        logger.exception("Erro enviando Discord")
        return False


def telegram_smoke_test() -> bool:
    if not TOKEN or not CHAT_IDS:
        logger.error("TOKEN e CHAT_ID são obrigatórios para o teste inicial do Telegram")
        return False

    try:
        response = telegram_api_request("getMe")
        response.raise_for_status()
        test_message = "Teste de conectividade do monitor"
        sent_response = telegram_api_request(
            "sendMessage",
            {"chat_id": CHAT_IDS[0], "text": test_message, "disable_notification": True},
        )
        sent_response.raise_for_status()

        message_id = sent_response.json().get("result", {}).get("message_id")
        if message_id:
            try:
                telegram_api_request("deleteMessage", {"chat_id": CHAT_IDS[0], "message_id": message_id}).raise_for_status()
            except Exception:
                logger.warning("Teste Telegram enviado, mas a remoção da mensagem falhou")

        logger.info("Telegram conectado com sucesso")
        return True
    except Exception:
        logger.exception("Erro Telegram no teste inicial de conectividade")
        return False


def notify_sale(target: StoreTarget, name: str, before: int, after: int) -> bool:
    now = datetime.utcnow().isoformat()
    text = (
        f"VENDA DETECTADA\n"
        f"{build_message_prefix(target)}"
        f"Item: {name}\n"
        f"Antes: {before} -> Agora: {after}\n"
        f"Hora(UTC): {now}"
    )
    telegram_sent = send_telegram(text)
    discord_sent = send_discord(text)
    if telegram_sent or discord_sent:
        logger.info("Alerta enviado para %s", name)
        return True
    return False


def load_store_state(history: dict, target: StoreTarget) -> dict:
    stores = history.setdefault("stores", {})
    return stores.setdefault(target.url, {"quantities": {}, "last_alerts": {}})


def should_alert(last_alerts: dict, key: str, now_ts: int) -> bool:
    last_seen = int(last_alerts.get(key, 0))
    return now_ts - last_seen >= COOLDOWN


def register_alert(last_alerts: dict, key: str, now_ts: int):
    last_alerts[key] = now_ts


def inspect_store(target: StoreTarget, history: dict) -> dict:
    logger.info("Carregando lojas: %s", target.name)
    store_state = load_store_state(history, target)
    quantities = store_state.setdefault("quantities", {})
    last_alerts = store_state.setdefault("last_alerts", {})

    logger.info("Verificando itens: %s", target.url)
    html = fetch_shop(target.url)
    items = parse_shop(html)
    changes = []

    if not items:
        logger.warning("Nenhum item detectado na página — verifique o parser ou a URL.")
        return {"items_found": 0, "changes": changes}

    logger.info("Itens encontrados na loja %s: %d", target.name, len(items))
    now_ts = int(time.time())

    for name, qty in items.items():
        logger.info("Item encontrado: %s | quantidade=%s", name, qty)
        prev = quantities.get(name)
        if prev is None:
            quantities[name] = qty
            continue

        if qty < prev:
            alert_key = f"{target.url}:{name}"
            if should_alert(last_alerts, alert_key, now_ts):
                if notify_sale(target, name, prev, qty):
                    register_alert(last_alerts, alert_key, now_ts)
                    changes.append((name, prev, qty))
            else:
                logger.warning("Mudança repetida em cooldown para %s", name)

        quantities[name] = qty

    missing_items = [name for name in quantities.keys() if name not in items]
    for name in missing_items:
        prev = quantities.get(name, 0)
        if prev > 0:
            alert_key = f"{target.url}:{name}"
            if should_alert(last_alerts, alert_key, now_ts):
                if notify_sale(target, name, prev, 0):
                    register_alert(last_alerts, alert_key, now_ts)
                    changes.append((name, prev, 0))
            else:
                logger.warning("Mudança repetida em cooldown para %s", name)
        quantities[name] = 0

    if not changes:
        logger.info("Nenhuma mudança encontrada em %s", target.name)

    return {"items_found": len(items), "changes": changes}


def check_once(history: dict) -> dict:
    results = []
    total_items = 0
    total_changes = 0

    for target in STORE_TARGETS:
        try:
            result = inspect_store(target, history)
            results.append({"target": target.name, **result})
            total_items += result["items_found"]
            total_changes += len(result["changes"])
        except requests.RequestException:
            logger.exception("Erro de API ao consultar a loja %s", target.name)
        except Exception:
            logger.exception("Erro inesperado ao processar a loja %s", target.name)

    history["version"] = STATE_VERSION
    save_history(history)
    return {"items_found": total_items, "changes": total_changes, "results": results, "saved": True}


def main():
    logger.info("Monitor iniciado | lojas=%d | cooldown=%ss", len(STORE_TARGETS), COOLDOWN)
    if not TOKEN or not CHAT_IDS:
        logger.error("TOKEN e CHAT_ID são obrigatórios para enviar alertas no Telegram")
        raise SystemExit(1)

    if not telegram_smoke_test():
        raise SystemExit(1)

    history = load_history()
    try:
        result = check_once(history)
        logger.info(
            "Verificação concluída: %d item(ns) encontrados, %d mudança(s), histórico salvo=%s",
            result["items_found"],
            result["changes"],
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
