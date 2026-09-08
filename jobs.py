"""Morning capsule + evening streak reminders."""

from __future__ import annotations

import logging
import os

import db
from llm import (
    generate_capsule,
    generate_morning_capsule_with_score,
    generate_question,
    generate_weekly_report,
)
from outbound import send_whatsapp

log = logging.getLogger("placementprep.jobs")


def _send_user(phone: str, text: str) -> None:
    if os.environ.get("TELEGRAM_BOT_TOKEN") and not os.environ.get("WHATSAPP_ACCESS_TOKEN"):
        from outbound import send_telegram
        send_telegram(phone, text)
    else:
        send_whatsapp(phone, text)


def morning_blast() -> int:
    sent = 0
    for user in db.list_users():
        phone = user["phone_number"]
        track = user.get("track") or "General SDE"
        try:
            profile = db.get_readiness_profile(phone)
            capsule, target_topic = generate_morning_capsule_with_score(profile)
            question, topic = generate_question(track, topic=target_topic)
            db.set_pending(phone, question, topic, drill_remaining=0)
            _send_user(
                phone,
                f"{capsule}\n\n"
                f"📝 *Targeted Diagnostic Question*\n\n{question}\n\n"
                "_Reply to get graded. Send *score* for full report, or *drill* for 3-Q mock._",
            )
            sent += 1
        except Exception:
            log.exception("Morning send failed for %s", phone)
    log.info("Morning blast sent to %s users", sent)
    return sent


def evening_reminders() -> int:
    sent = 0
    for user in db.users_inactive_today():
        phone = user["phone_number"]
        streak = int(user.get("streak_count") or 0)
        _send_user(
            phone,
            "🌙 *Don't break the chain*\n\n"
            f"You haven't practiced yet today. Streak: *{streak}*.\n"
            "Send *drill* (2 min) or answer your morning question.\n"
            "Campus offers reward consistency — one question still counts.",
        )
        sent += 1
    log.info("Evening reminders sent to %s users", sent)
    return sent


def weekly_report() -> int:
    """Sunday 10 AM — personalized weekly progress report."""
    sent = 0
    for user in db.list_users():
        phone = user["phone_number"]
        track = user.get("track") or "General SDE"
        try:
            drills = db.weekly_drill_summary(phone)
            user_stats = db.stats(phone)
            user_stats["difficulty"] = user.get("difficulty") or "easy"
            report = generate_weekly_report(track, drills, user_stats)
            _send_user(phone, report)
            sent += 1
        except Exception:
            log.exception("Weekly report failed for %s", phone)
    log.info("Weekly reports sent to %s users", sent)
    return sent


def timezone_name() -> str:
    return os.environ.get("TIMEZONE", "Asia/Kolkata")
