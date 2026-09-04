"""Command helpers (pure, testable)."""

from __future__ import annotations

import re

FOLLOWUP_RE = re.compile(
    r"^(explain|why\b|what about|line\s+\d+|complexity|edge case|time complexity|space complexity|/explain)",
    re.I,
)

COMMAND_ALIASES = {
    "hi": "start",
    "hello": "start",
    "hey": "start",
    "/start": "start",
    "start": "start",
    "drill": "drill",
    "/drill": "drill",
    "streak": "streak",
    "/streak": "streak",
    "stats": "streak",
    "/stats": "streak",
    "solution": "solution",
    "/solution": "solution",
    "skip": "solution",
    "/skip": "solution",
    "help": "help",
    "/help": "help",
    "hint": "hint",
    "/hint": "hint",
    "topics": "topics",
    "/topics": "topics",
    "level": "level",
    "/level": "level",
    "leaderboard": "leaderboard",
    "/leaderboard": "leaderboard",
    "lb": "leaderboard",
}


def normalize(text: str) -> str:
    return (text or "").strip()


def parse_command(text: str) -> str | None:
    key = normalize(text).lower()
    if key in COMMAND_ALIASES:
        return COMMAND_ALIASES[key]
    if key.startswith("/") and key.split()[0] in COMMAND_ALIASES:
        return COMMAND_ALIASES[key.split()[0]]
    return None


def is_followup(text: str) -> bool:
    return bool(FOLLOWUP_RE.search(normalize(text)))


def parse_track_payload(text: str) -> str | None:
    from prompts import TRACKS

    key = normalize(text)
    if key in TRACKS:
        return TRACKS[key]
    lowered = key.lower()
    if "data science" in lowered:
        return "Data Science"
    if "core" in lowered:
        return "Core CS"
    if "sde" in lowered or "software" in lowered:
        return "Software Development"
    return None
