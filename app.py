"""PlacementPrep AI — FastAPI webhook + Caspian WhatsApp + scheduler."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
import ssl

# Fix SSL certificate verification issue on Windows / trycaspianai.com
# The Caspian SDK uses httpx for gateway HTTP requests; forcing verify=False
# prevents [SSL: CERTIFICATE_VERIFY_FAILED] errors in environments without
# proper CA certificate bundles (common on Windows).
_original_client_init = httpx.Client.__init__

def _patched_client_init(self, *args, **kwargs):
    if "verify" not in kwargs:
        kwargs["verify"] = False
    return _original_client_init(self, *args, **kwargs)

httpx.Client.__init__ = _patched_client_init

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from caspian import Caspian

CASPIAN_API_KEY = os.environ.get("CASPIAN_API_KEY", "")

import db
from bot import register
from jobs import evening_reminders, morning_blast, timezone_name, weekly_report

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("placementprep")

scheduler = BackgroundScheduler(timezone=timezone_name())


def _require_whatsapp() -> tuple[str, str, str, str]:
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    app_secret = os.environ.get("WHATSAPP_APP_SECRET", "").strip()
    verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "").strip()
    missing = [
        name
        for name, val in [
            ("WHATSAPP_ACCESS_TOKEN", access_token),
            ("WHATSAPP_PHONE_NUMBER_ID", phone_number_id),
            ("WHATSAPP_APP_SECRET", app_secret),
            ("WHATSAPP_VERIFY_TOKEN", verify_token),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
    return access_token, phone_number_id, app_secret, verify_token


cx = Caspian(api_key=CASPIAN_API_KEY)
_VERIFY_TOKEN = ""
if os.environ.get("WHATSAPP_ACCESS_TOKEN"):
    access_token, phone_number_id, app_secret, _VERIFY_TOKEN = _require_whatsapp()
    cx.channels.add(
        "whatsapp",
        via="hosted",
        access_token=access_token,
        phone_number_id=phone_number_id,
        app_secret=app_secret,
        bot_token="local",
    )
    register(cx)

if os.environ.get("TELEGRAM_BOT_TOKEN"):
    _tg_token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    cx.channels.add("telegram", bot_token=_tg_token)
    if not os.environ.get("WHATSAPP_ACCESS_TOKEN"):
        register(cx)
    log.info("Telegram channel registered")


def normalize_whatsapp_body(body: bytes) -> bytes:
    """Turn interactive button replies into text so Caspian parses them."""
    try:
        payload: dict[str, Any] = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return body
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            for msg in value.get("messages") or []:
                if not isinstance(msg, dict) or msg.get("type") != "interactive":
                    continue
                interactive = msg.get("interactive") or {}
                reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
                payload_id = str(reply.get("id") or reply.get("title") or "")
                if payload_id:
                    msg["type"] = "text"
                    msg["text"] = {"body": payload_id}
    return json.dumps(payload).encode("utf-8")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    os.environ.setdefault("TZ", timezone_name())
    try:
        import time

        time.tzset()
    except (AttributeError, OSError):
        pass
    db.init_db()
    morning_hour = int(os.environ.get("MORNING_HOUR", "8"))
    evening_hour = int(os.environ.get("EVENING_HOUR", "20"))
    scheduler.add_job(morning_blast, CronTrigger(hour=morning_hour, minute=0), id="morning")
    scheduler.add_job(evening_reminders, CronTrigger(hour=evening_hour, minute=0), id="evening")
    scheduler.add_job(weekly_report, CronTrigger(day_of_week="sun", hour=10, minute=0), id="weekly")
    scheduler.start()
    log.info("Scheduler on %s at %02d:00 and %02d:00", timezone_name(), morning_hour, evening_hour)

    import threading

    stop_caspian = threading.Event()

    def _caspian_poller():
        log.info("Starting Caspian hosted message listener")
        from caspian.hosted.inbound import GatewayPoller
        poller = GatewayPoller(cx._gateway_client)
        while not stop_caspian.is_set():
            try:
                fetched = poller.fetch_raw()
                if fetched.is_ok:
                    raw = fetched.value
                    if raw.body:
                        import json
                        try:
                            data = json.loads(raw.body)
                            events = data.get("events") or []
                            if events:
                                threading.Thread(
                                    target=cx.handle,
                                    args=("gateway", raw.body, raw.headers),
                                    daemon=True,
                                ).start()
                        except Exception:
                            threading.Thread(
                                target=cx.handle,
                                args=("gateway", raw.body, raw.headers),
                                daemon=True,
                            ).start()
                import time
                time.sleep(0.5)
            except Exception as exc:
                log.warning("Caspian listener warning: %s", exc)
                import time
                time.sleep(2)

    poller_thread = threading.Thread(target=_caspian_poller, daemon=True)
    poller_thread.start()

    yield

    stop_caspian.set()
    scheduler.shutdown(wait=False)


app = FastAPI(title="PlacementPrep AI", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "placementprep-ai"}


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "PlacementPrep AI",
        "webhook": "/webhook",
        "hint": "Message the WhatsApp business number with hi or send @your_telegram_bot on Telegram",
    }


@app.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    expected = _VERIFY_TOKEN or os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    if mode == "subscribe" and token == expected:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def process_webhook(request: Request) -> dict[str, str]:
    body = normalize_whatsapp_body(await request.body())
    headers = dict(request.headers)
    cx.handle("gateway", body, headers)
    return {"status": "ok"}


@app.post("/telegram")
async def process_telegram(request: Request) -> dict[str, str]:
    body = await request.body()
    headers = dict(request.headers)
    cx.handle("gateway", body, headers)
    return {"status": "ok"}


def _check_cron(secret: str | None) -> None:
    expected = os.environ.get("CRON_SECRET", "").strip()
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.api_route("/jobs/morning", methods=["GET", "POST"])
async def job_morning(secret: str | None = Query(default=None)) -> dict[str, int]:
    _check_cron(secret)
    return {"sent": morning_blast()}


@app.api_route("/jobs/evening", methods=["GET", "POST"])
async def job_evening(secret: str | None = Query(default=None)) -> dict[str, int]:
    _check_cron(secret)
    return {"sent": evening_reminders()}


@app.api_route("/jobs/weekly", methods=["GET", "POST"])
async def job_weekly(secret: str | None = Query(default=None)) -> dict[str, int]:
    _check_cron(secret)
    return {"sent": weekly_report()}
