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
    "skip": "skip",
    "/skip": "skip",
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
    "cmd:skip": "skip",
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
    # Switch mood / cancel / resume
    "switch": "switch",
    "/switch": "switch",
    "change": "switch",
    "/change": "switch",
    "cancel": "switch",
    "/cancel": "switch",
    "cmd:switch": "switch",
    "cmd:switch_mood": "switch",
    "cmd:continue_pending": "continue_pending",
    "answer": "continue_pending",
    "continue": "continue_pending",
    # Self-recovery: clear stuck session
    "clear": "clear",
    "/clear": "clear",
    "reset": "clear",
    "/reset": "clear",
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


def parse_switch_command(text: str) -> str | bool | None:
    """
    Returns:
      - topic string if user types 'switch <topic>' (e.g. 'switch os' -> 'os', 'switch dsa' -> 'dsa')
      - True if bare 'switch', '/switch', 'change', 'cancel', 'cmd:switch_mood', 'quit'
      - None otherwise
    """
    norm = normalize(text)
    m = re.match(r"^/?(?:switch|change)\s+([a-zA-Z0-9_\-\s]+)$", norm, re.I)
    if m:
        target = m.group(1).strip().lower()
        if target not in ("now", "mood", "please", "to"):
            if target.startswith("to "):
                target = target[3:].strip()
            return target
        return True
    if norm.lower() in (
        "switch",
        "/switch",
        "change",
        "/change",
        "cancel",
        "/cancel",
        "stop",
        "quit",
        "cmd:switch_mood",
        "cmd:switch",
    ):
        return True
    return None


def looks_like_answer(text: str) -> bool:
    """
    Detects if incoming text looks like a deliberate code solution,
    calculation, or technical explanation rather than a casual greeting or intent change.
    """
    norm = normalize(text)
    if not norm:
        return False
    lower = norm.lower()

    # Short conversational greetings, confirmations, or questions
    greetings = {
        "hi", "hello", "hey", "hola", "yo", "sup", "ready", "start",
        "prep", "test", "ok", "okay", "yes", "no", "help", "menu", "what",
    }
    if lower in greetings or len(lower) <= 3:
        return False

    # Conversational intent questions (e.g. "can we do...", "how to...", "what is...")
    if re.match(r"^(can we|could you|how to|what is|tell me|explain)\b", lower):
        return False

    # Code syntax or mathematical indicators
    code_indicators = [
        "def ", "class ", "int ", "float ", "return ", "select ", "from ",
        "{", "}", "public ", "for ", "while ", "->", "=", "ms", "o(1)", "o(n)",
        "arr[", "nums[", "vector<", "cout", "print(", "fn ", "const ", "let "
    ]
    if any(ind in lower for ind in code_indicators):
        return True

    # Multi-line or substantial answer (more than 10 words or >= 50 characters)
    words = norm.split()
    if len(words) >= 10 or (len(norm) >= 50 and "\n" in norm):
        return True

    return False


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


# ── Onboarding payload parsers ─────────────────────────────────────

def parse_onboarding_payload(text: str) -> str | None:
    """Parse onboarding button payloads like 'onboard:manual', 'onboard:ai'."""
    norm = normalize(text).lower()
    if norm == "onboard:manual":
        return "manual"
    if norm == "onboard:ai":
        return "ai"
    return None


def parse_onboard_company(text: str) -> str | None:
    """Parse company selection during onboarding: 'obc:<name>' or free text."""
    norm = normalize(text)
    if norm.lower().startswith("obc:"):
        return norm[4:].strip()
    return None


def parse_onboard_role(text: str) -> str | None:
    """Parse role selection during onboarding: 'obr:<name>' or free text."""
    norm = normalize(text)
    if norm.lower().startswith("obr:"):
        return norm[4:].strip()
    return None


def parse_onboard_timeline(text: str) -> str | None:
    """Parse timeline selection during onboarding: 'obt:<value>'."""
    norm = normalize(text)
    if norm.lower().startswith("obt:"):
        return norm[4:].strip()
    return None

