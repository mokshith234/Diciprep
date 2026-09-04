"""Morning capsule + evening streak reminders."""

from __future__ import annotations

import logging
import os

import db
from llm import generate_capsule, generate_question, generate_weekly_report
from outbound import send_whatsapp

log = logging.getLogger("placementprep.jobs")


def morning_blast() -> int:
    sent = 0
    for user in db.list_users():
        phone = user["phone_number"]
        track = user.get("track") or "General SDE"
        try:
            capsule = generate_capsule(track)
            question, topic = generate_question(track)
            db.set_pending(phone, question, topic, drill_remaining=0)
            send_whatsapp(
                phone,
                f"☀️ *Morning Placement Capsule*\n\n{capsule}\n\n"
                f"📝 *Question #1*\n\n{question}\n\n"
                "_Reply to get graded. *drill* for a 3-Q mock. *streak* for stats._",
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
        send_whatsapp(
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
            send_whatsapp(phone, report)
            sent += 1
        except Exception:
            log.exception("Weekly report failed for %s", phone)
    log.info("Weekly reports sent to %s users", sent)
    return sent


def timezone_name() -> str:
    return os.environ.get("TIMEZONE", "Asia/Kolkata")
