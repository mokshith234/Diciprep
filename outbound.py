"""Outbound WhatsApp Cloud API sends (scheduler / cron)."""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("placementprep.wa")
GRAPH_BASE = "https://graph.facebook.com/v21.0"
WA_LIMIT = 4000


def chunk_text(text: str, limit: int = WA_LIMIT) -> list[str]:
    text = (text or "").strip()
    if len(text) <= limit:
        return [text] if text else []
    parts: list[str] = []
    rest = text
    while rest:
        if len(rest) <= limit:
            parts.append(rest)
            break
        cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(rest[:cut])
        rest = rest[cut:].lstrip()
    return parts


def send_whatsapp(to: str, text: str) -> None:
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    if not token or not phone_id:
        log.warning("Skipping send; WhatsApp credentials missing")
        return
    url = f"{GRAPH_BASE}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    for part in chunk_text(text):
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": part, "preview_url": False},
        }
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=30)
            if r.status_code >= 400:
                log.error("WhatsApp send failed %s %s", r.status_code, r.text)
        except httpx.HTTPError:
            log.exception("WhatsApp send failed to %s", to)


def send_telegram(chat_id: str, text: str) -> None:
    """Send a text message via Telegram Bot API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        log.warning("Skipping Telegram send; bot token missing")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for part in chunk_text(text):
        try:
            r = httpx.post(url, json={"chat_id": chat_id, "text": part, "parse_mode": "Markdown"}, timeout=30)
            if r.status_code >= 400:
                log.error("Telegram send failed %s %s", r.status_code, r.text)
        except httpx.HTTPError:
            log.exception("Telegram send failed to %s", chat_id)


def post_chunks(thread, text: str) -> None:
    for part in chunk_text(text):
        thread.post(part)
