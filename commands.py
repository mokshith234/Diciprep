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
    # Interactive action button payloads
    "cmd:hint": "hint",
    "cmd:solution": "solution",
    "cmd:skip": "solution",
    # New features
    "menu": "menu",
    "/menu": "menu",
    "cmd:menu": "menu",
    "cmd:drill": "drill",
    "cmd:topics": "topics",
    "cmd:streak": "streak",
    "cmd:summary": "summary",
    "cmd:resume": "resume",
    "summary": "summary",
    "/summary": "summary",
    "revision": "summary",
    "/revision": "summary",
    "resume": "resume",
    "/resume": "resume",
    "company": "company",
    "/company": "company",
    "role": "role",
    "/role": "role",
}


def normalize(text: str) -> str:
    return (text or "").strip()


def parse_command(text: str) -> str | None:
    norm = normalize(text)
    key = norm.lower()
    if key in COMMAND_ALIASES:
        return COMMAND_ALIASES[key]
    first = key.split()[0] if key else ""
    if first.startswith("/") and first in COMMAND_ALIASES:
        return COMMAND_ALIASES[first]
    return None


def parse_topic_drill(text: str) -> str | None:
    """Matches 'drill os', '/drill dsa', 'drill system design', etc."""
    norm = normalize(text)
    m = re.match(r"^/?drill\s+([a-zA-Z0-9_\-\s]+)$", norm, re.I)
    if m:
        topic = m.group(1).strip()
        if topic.lower() not in ("now", "me", "please"):
            return topic
    return None


def parse_company_command(text: str) -> str | None:
    """Matches 'company amazon', '/company google', 'target company tcs', etc."""
    norm = normalize(text)
    m = re.match(r"^(?:/?company|target\s+company)\s+([a-zA-Z0-9_\-\s]+)$", norm, re.I)
    if m:
        return m.group(1).strip()
    return None


def parse_role_command(text: str) -> str | None:
    """Matches 'role SDE 1', '/role Backend Python', etc."""
    norm = normalize(text)
    m = re.match(r"^(?:/?role|target\s+role)\s+([a-zA-Z0-9_\-\s/()]+)$", norm, re.I)
    if m:
        return m.group(1).strip()
    return None


def parse_resume_command(text: str) -> tuple[bool, str]:
    """Matches 'resume: <text>' or '/resume <text>' or standalone '/resume'."""
    norm = normalize(text)
    if norm.lower() in ("resume", "/resume"):
        return True, ""
    m = re.match(r"^(?:/?resume\s*[:\-]?\s*)(.+)$", norm, re.I | re.DOTALL)
    if m:
        return True, m.group(1).strip()
    return False, ""


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
