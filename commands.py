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
    # Quick queries
    "?": "help",
    "what": "help",
    "what?": "help",
    # Readiness scorecard & progress
    "score": "readiness",
    "/score": "readiness",
    "readiness": "readiness",
    "/readiness": "readiness",
    "progress": "readiness",
    "/progress": "readiness",
    "report": "readiness",
    "/report": "readiness",
    "cmd:readiness": "readiness",
    "cmd:score": "readiness",
    # Hackathon Judge telemetry commands
    "judge": "judge",
    "/judge": "judge",
    "metrics": "judge",
    "/metrics": "judge",
    "audit": "judge",
    "/audit": "judge",
    "eval": "judge",
    "/eval": "judge",
    "telemetry": "judge",
    "/telemetry": "judge",
    "cmd:judge": "judge",
    # Reply Keyboard & Natural Language Actions
    "mock interview": "drill",
    "ai resume scanner": "resume",
    "resume scanner": "resume",
    "scan resume": "resume",
    "readiness score": "readiness",
    "scorecard": "readiness",
    # User feedback form
    "feedback": "feedback",
    "/feedback": "feedback",
    "form": "feedback",
    "survey": "feedback",
    "cmd:feedback": "feedback",
    "cmd:open_feedback": "feedback",
}


def normalize(text: str) -> str:
    return (text or "").strip()


def parse_command(text: str) -> str | None:
    norm = normalize(text)
    key = norm.lower()
    if key in COMMAND_ALIASES:
        return COMMAND_ALIASES[key]
    # Strip leading non-alphanumeric symbols/emojis (e.g. "⚡ Mock Interview" -> "mock interview")
    clean = re.sub(r"^[^\w/]+", "", norm).strip().lower()
    if clean in COMMAND_ALIASES:
        return COMMAND_ALIASES[clean]
    first = key.split()[0] if key else ""
    if first.startswith("/") and first in COMMAND_ALIASES:
        return COMMAND_ALIASES[first]
    clean_first = clean.split()[0] if clean else ""
    if clean_first in COMMAND_ALIASES:
        return COMMAND_ALIASES[clean_first]
    return None


def parse_topic_drill(text: str) -> str | None:
    """Matches 'drill os', '/drill dsa', 'drill system design', or bare topic names like 'ml', 'os', 'dsa'."""
    norm = normalize(text).lower()
    m = re.match(r"^/?drill\s+([a-zA-Z0-9_\-\s]+)$", norm, re.I)
    if m:
        topic = m.group(1).strip()
        if topic.lower() not in ("now", "me", "please"):
            return topic

    COMMON_TOPICS = {
        "ml": "machine learning",
        "machine learning": "machine learning",
        "dsa": "dsa",
        "os": "os",
        "dbms": "dbms",
        "cn": "computer networks",
        "computer networks": "computer networks",
        "networks": "computer networks",
        "sql": "sql",
        "pandas": "pandas",
        "numpy": "numpy",
        "python": "python",
        "system design": "system design",
        "oops": "oops",
        "oop": "oops",
        "aptitude": "aptitude",
    }
    if norm in COMMON_TOPICS:
        return COMMON_TOPICS[norm]
    return None


def parse_fix_command(text: str) -> str | None:
    """Matches 'fix:<topic>', 'cmd:fix:<topic>', 'fix <topic>', '/fix <topic>' for weakness repair buttons."""
    norm = normalize(text)
    lower = norm.lower()
    if lower.startswith("cmd:fix:"):
        topic = norm[8:].strip()
        return topic if topic else None
    if lower.startswith("fix:"):
        topic = norm[4:].strip()
        return topic if topic else None
    m = re.match(r"^(?:/?fix|cmd:fix)\s+([a-zA-Z0-9_\-\s&/]+)$", norm, re.I)
    if m:
        return m.group(1).strip()
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
    return is_asking_question_or_clarification(text)


def is_asking_question_or_clarification(text: str) -> bool:
    """Detect if the student is asking a question or seeking clarification instead of submitting an answer."""
    norm = normalize(text).strip()
    if not norm:
        return False
    lower = norm.lower()

    # 1. Ends with a question mark
    if norm.endswith("?"):
        return True

    # 2. Starts with common question words or phrases
    question_starters = (
        "can i", "can we", "could i", "could we", "is it", "is there",
        "how to", "how do", "how does", "how can", "why do", "why does", "why is", "why would",
        "what is", "what are", "what does", "what if", "what about",
        "explain", "clarify", "tell me", "meaning of", "i don't understand",
        "i dont understand", "i am stuck", "im stuck", "what do you mean",
        "difference between", "should i", "should we", "does it", "does this",
        "where does", "where is", "which one", "which algorithm",
        "is this", "are we", "will this",
    )
    if any(lower.startswith(q) for q in question_starters):
        return True

    # 3. Matches existing FOLLOWUP_RE
    if FOLLOWUP_RE.search(norm):
        return True

    return False


def parse_track_payload(text: str) -> str | None:
    from prompts import TRACKS

    key = normalize(text)
    if key in TRACKS:
        return TRACKS[key]
    lowered = key.lower()
    if re.search(r"\bdata\s+science\b", lowered):
        return "Data Science"
    if re.search(r"\bcore\b", lowered):
        return "Core CS"
    if re.search(r"\b(?:sde|software)\b", lowered):
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


TARGET_PROFILES = {
    "tp:faang": {
        "company": "Tier-1 / FAANG",
        "role": "Software Development Engineer",
        "timeline": "1-3 Months",
        "track": "Software Development",
    },
    "tp:amazon": {
        "company": "Amazon",
        "role": "Backend SDE",
        "timeline": "1-3 Months",
        "track": "Software Development",
    },
    "tp:microsoft": {
        "company": "Microsoft",
        "role": "Fullstack SDE",
        "timeline": "1-3 Months",
        "track": "Software Development",
    },
    "tp:tcs": {
        "company": "TCS & Mass Recruiters",
        "role": "Software Engineer",
        "timeline": "This Month",
        "track": "Core CS",
    },
    "tp:ds": {
        "company": "Data & AI Firms",
        "role": "Data Scientist",
        "timeline": "1-3 Months",
        "track": "Data Science",
    },
    "tp:core": {
        "company": "Core Systems",
        "role": "Systems Engineer",
        "timeline": "1-3 Months",
        "track": "Core CS",
    },
    "tp:general": {
        "company": "General Tech",
        "role": "Software Engineer",
        "timeline": "Immediate",
        "track": "Software Development",
    },
}


def parse_target_profile(text: str) -> dict | None:
    """Parse a single combined target selection (button payload or 1-line text).
    
    Returns dict with keys: company, role, timeline, track.
    """
    norm = normalize(text).lower()
    if norm in TARGET_PROFILES:
        return dict(TARGET_PROFILES[norm])

    raw = normalize(text)
    if not raw:
        return None

    # Handle comma-separated custom input e.g. "Google, SDE, 2 months"
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) >= 3:
        company = parts[0]
        role = parts[1]
        timeline = parts[2]
    elif len(parts) == 2:
        company = parts[0]
        role = parts[1]
        timeline = "1-3 Months"
    else:
        company = parts[0]
        role = "Software Engineer"
        timeline = "1-3 Months"

    # Infer track from role/company
    combined = (company + " " + role).lower()
    if any(k in combined for k in ("data", "ml", "ai", "machine learning", "analyst")):
        track = "Data Science"
    elif any(k in combined for k in ("core", "os", "embedded", "network", "system")):
        track = "Core CS"
    else:
        track = "Software Development"

    return {
        "company": company,
        "role": role,
        "timeline": timeline,
        "track": track,
    }


