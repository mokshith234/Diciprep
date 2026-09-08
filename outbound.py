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


def send_telegram(chat_id: str, text: str, actions=None) -> None:
    """Send a text message with optional buttons via Telegram Bot API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not chat_id:
        log.warning("Skipping Telegram send; bot token or chat_id missing")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    reply_markup = None
    if actions:
        keyboard = []
        for btn in actions:
            label = getattr(btn, "label", str(btn))
            data = getattr(btn, "data", label)
            keyboard.append([{"text": str(label)[:64], "callback_data": str(data)[:64]}])
        reply_markup = {"inline_keyboard": keyboard}

    parts = chunk_text(text)
    for i, part in enumerate(parts):
        payload: dict = {"chat_id": chat_id, "text": part, "parse_mode": "Markdown"}
        if i == len(parts) - 1 and reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            r = httpx.post(url, json=payload, timeout=30)
            if r.status_code == 400 and "can't parse entities" in r.text:
                # Markdown entity syntax error in LLM output: fallback to plain text
                payload.pop("parse_mode", None)
                r = httpx.post(url, json=payload, timeout=30)
            if r.status_code >= 400:
                log.error("Telegram send failed %s %s", r.status_code, r.text)
        except httpx.HTTPError:
            log.exception("Telegram send failed to %s", chat_id)


def send_telegram_typing(chat_id: str) -> None:
    """Send typing status to Telegram user."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendChatAction"
    try:
        httpx.post(url, json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except Exception:
        pass


def answer_telegram_callback(callback_id: str) -> None:
    """Acknowledge Telegram callback query so client button stops spinning."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not callback_id:
        return
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    try:
        httpx.post(url, json={"callback_query_id": str(callback_id)}, timeout=5)
    except Exception:
        pass


def post_chunks(thread, text: str, actions=None) -> None:
    tid = str(getattr(thread, "thread_id", ""))
    if tid.startswith("telegram:") and actions:
        chat_id = tid.split(":", 1)[-1]
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if token and chat_id:
            try:
                send_telegram(chat_id, text, actions=actions)
                return
            except Exception:
                pass

    parts = chunk_text(text)
    for i, part in enumerate(parts):
        if i == len(parts) - 1 and actions:
            thread.post(part, actions=actions)
        else:
            thread.post(part)
