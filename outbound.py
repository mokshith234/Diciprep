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
            target_url = (
                getattr(btn, "url", None)
                or (str(data) if str(data).startswith(("http://", "https://")) else None)
                or ("https://docs.google.com/forms/d/e/1FAIpQLSc8njVZKFo_9iivLLoDIjiOykw5Dql_KDdp3up4fHcstXdC-w/viewform" if data == "cmd:open_feedback" else None)
            )
            if target_url:
                keyboard.append([{"text": str(label)[:64], "url": str(target_url)}])
            else:
                keyboard.append([{"text": str(label)[:64], "callback_data": str(data)[:64]}])
        reply_markup = {"inline_keyboard": keyboard}
    else:
        # Persistent Telegram Reply Keyboard — when pressed, text sends from the user's side
        reply_markup = {
            "keyboard": [
                [{"text": "⚡ Mock Interview"}, {"text": "📄 AI Resume Scanner"}],
                [{"text": "📊 Readiness Score"}, {"text": "🎓 Menu"}],
                [{"text": "💡 Hint"}, {"text": "📜 Solution"}, {"text": "⏭️ Skip"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
        }

    parts = chunk_text(text)
    if not parts and reply_markup:
        parts = [" "]
    for i, part in enumerate(parts):
        payload: dict = {"chat_id": chat_id, "text": part, "parse_mode": "Markdown"}
        if i == len(parts) - 1 and reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            r = httpx.post(url, json=payload, timeout=30, verify=False)
            if r.status_code == 400 and ("parse" in r.text.lower() or "entity" in r.text.lower()):
                # Markdown entity syntax error in LLM output: fallback to plain text
                payload.pop("parse_mode", None)
                r = httpx.post(url, json=payload, timeout=30, verify=False)
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
        httpx.post(url, json={"chat_id": chat_id, "action": "typing"}, timeout=5, verify=False)
    except Exception:
        pass


def answer_telegram_callback(callback_id: str) -> None:
    """Acknowledge Telegram callback query so client button stops spinning."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not callback_id:
        return
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    try:
        httpx.post(url, json={"callback_query_id": str(callback_id)}, timeout=5, verify=False)
    except Exception:
        pass


def post_chunks(thread, text: str, actions=None) -> None:
    parts = chunk_text(text)
    if not parts and actions:
        parts = [" "]
    if hasattr(thread, "post") and callable(thread.post):
        for i, part in enumerate(parts):
            if i == len(parts) - 1 and actions:
                thread.post(part, actions=actions)
            else:
                thread.post(part)
    else:
        # Fallback if thread object has no post method
        tid = str(getattr(thread, "thread_id", ""))
        chat_id = tid.split(":", 1)[-1] if ":" in tid else tid
        send_telegram(chat_id, text, actions=actions)

