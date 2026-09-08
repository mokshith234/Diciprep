"""User + drill persistence. SQLite locally, Postgres when DATABASE_URL is set."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator

log = logging.getLogger("placementprep.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("SQLITE_PATH", "placementprep.db")


def _is_postgres() -> bool:
    return DATABASE_URL.startswith("postgres")


@contextmanager
def get_conn() -> Iterator[Any]:
    if _is_postgres():
        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _q(sql: str) -> str:
    """Use %s placeholders on Postgres, ? on SQLite."""
    if _is_postgres():
        return sql.replace("?", "%s")
    return sql


def init_db() -> None:
    users_sql = """
    CREATE TABLE IF NOT EXISTS users (
        phone_number VARCHAR(128) PRIMARY KEY,
        name VARCHAR(128),
        track VARCHAR(64) DEFAULT 'General SDE',
        streak_count INT DEFAULT 0,
        last_active_date DATE,
        questions_solved INT DEFAULT 0,
        correct_count INT DEFAULT 0,
        pending_question TEXT,
        pending_topic VARCHAR(64),
        drill_remaining INT DEFAULT 0,
        difficulty VARCHAR(16) DEFAULT 'easy',
        hint_count INT DEFAULT 0,
        consecutive_good INT DEFAULT 0,
        consecutive_bad INT DEFAULT 0,
        target_company VARCHAR(64) DEFAULT '',
        target_role VARCHAR(128) DEFAULT '',
        resume_summary TEXT DEFAULT '',
        pending_at TIMESTAMP,
        onboarding_step VARCHAR(32),
        resume_score INT DEFAULT 65,
        readiness_score INT DEFAULT 65,
        active_focus_area VARCHAR(128) DEFAULT '',
        skills_summary TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    drills_sql = """
    CREATE TABLE IF NOT EXISTS drills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number VARCHAR(128) REFERENCES users(phone_number),
        topic VARCHAR(64),
        question_text TEXT,
        user_response TEXT,
        model_feedback TEXT,
        score INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    if _is_postgres():
        drills_sql = """
        CREATE TABLE IF NOT EXISTS drills (
            id SERIAL PRIMARY KEY,
            phone_number VARCHAR(128) REFERENCES users(phone_number),
            topic VARCHAR(64),
            question_text TEXT,
            user_response TEXT,
            model_feedback TEXT,
            score INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    with get_conn() as conn:
        conn.execute(users_sql)
        conn.execute(drills_sql)

        # -- migrate: add new columns if missing on existing databases
        cols_to_add = [
            ("difficulty", "VARCHAR(16) DEFAULT 'easy'"),
            ("hint_count", "INT DEFAULT 0"),
            ("consecutive_good", "INT DEFAULT 0"),
            ("consecutive_bad", "INT DEFAULT 0"),
            ("target_company", "VARCHAR(64) DEFAULT ''"),
            ("target_role", "VARCHAR(128) DEFAULT ''"),
            ("resume_summary", "TEXT DEFAULT ''"),
            ("pending_at", "TIMESTAMP"),
            ("onboarding_step", "VARCHAR(32)"),
            ("resume_score", "INT DEFAULT 65"),
            ("readiness_score", "INT DEFAULT 65"),
            ("active_focus_area", "VARCHAR(128) DEFAULT ''"),
            ("skills_summary", "TEXT DEFAULT ''"),
        ]
        if _is_postgres():
            for col, col_def in cols_to_add:
                conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_def}")
        else:
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
            for col, col_def in cols_to_add:
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")


def upsert_user(phone: str, name: str | None = None, track: str | None = None) -> dict[str, Any]:
    existing = get_user(phone)
    if existing is None:
        with get_conn() as conn:
            conn.execute(
                _q(
                    "INSERT INTO users (phone_number, name, track) VALUES (?, ?, ?)"
                ),
                (phone, name or "", track or "General SDE"),
            )
        return get_user(phone)  # type: ignore[return-value]
    if name or track:
        with get_conn() as conn:
            conn.execute(
                _q("UPDATE users SET name = COALESCE(NULLIF(?, ''), name), track = COALESCE(?, track) WHERE phone_number = ?"),
                (name or "", track, phone),
            )
    return get_user(phone)  # type: ignore[return-value]


def get_user(phone: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(_q("SELECT * FROM users WHERE phone_number = ?"), (phone,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM users")
        return [dict(r) for r in cur.fetchall()]


def set_pending(phone: str, question: str | None, topic: str | None, drill_remaining: int | None = None) -> None:
    with get_conn() as conn:
        if question:
            now_iso = datetime.now(timezone.utc).isoformat()
            if drill_remaining is None:
                conn.execute(
                    _q(
                        "UPDATE users SET pending_question = ?, pending_topic = ?, pending_at = ? WHERE phone_number = ?"
                    ),
                    (question, topic, now_iso, phone),
                )
            else:
                conn.execute(
                    _q(
                        "UPDATE users SET pending_question = ?, pending_topic = ?, drill_remaining = ?, pending_at = ? WHERE phone_number = ?"
                    ),
                    (question, topic, drill_remaining, now_iso, phone),
                )
        else:
            conn.execute(
                _q(
                    "UPDATE users SET pending_question = NULL, pending_topic = NULL, drill_remaining = 0, hint_count = 0, pending_at = NULL WHERE phone_number = ?"
                ),
                (phone,),
            )


def clear_pending(phone: str) -> None:
    set_pending(phone, None, None, drill_remaining=0)


def force_clear_all_state(phone: str) -> None:
    """Nuclear reset: wipe ALL session state for a user.

    Use when a user is stuck due to corrupted DB state.
    Preserves: name, track, stats, drills history.
    Clears: pending question, hints, drill counter, pending_at, onboarding.
    """
    with get_conn() as conn:
        conn.execute(
            _q(
                "UPDATE users SET "
                "pending_question = NULL, "
                "pending_topic = NULL, "
                "drill_remaining = 0, "
                "hint_count = 0, "
                "pending_at = NULL, "
                "onboarding_step = NULL "
                "WHERE phone_number = ?"
            ),
            (phone,),
        )
    log.info("Force-cleared all session state for phone=%s", phone)


def set_onboarding_step(phone: str, step: str | None) -> None:
    """Set the onboarding step for multi-step AI-guided onboarding."""
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE users SET onboarding_step = ? WHERE phone_number = ?"),
            (step, phone),
        )


def get_onboarding_step(phone: str) -> str | None:
    """Get the current onboarding step for a user."""
    user = get_user(phone)
    if not user:
        return None
    return user.get("onboarding_step")


def complete_onboarding(phone: str) -> None:
    """Mark onboarding as complete — clear step, user is in normal mode."""
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE users SET onboarding_step = NULL WHERE phone_number = ?"),
            (phone,),
        )


def get_pending_age_seconds(user: dict[str, Any] | None) -> float | None:
    """Returns elapsed seconds since pending_question was set, or None if no pending question."""
    if not user or not user.get("pending_question"):
        return None
    val = user.get("pending_at")
    if not val:
        return None
    try:
        now_utc = datetime.now(timezone.utc)
        if isinstance(val, str):
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (now_utc - dt).total_seconds()
        elif isinstance(val, datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            return (now_utc - val).total_seconds()
    except Exception:
        return None
    return None


def update_profile(
    phone: str,
    target_company: str | None = None,
    target_role: str | None = None,
    resume_summary: str | None = None,
) -> dict[str, Any] | None:
    updates = []
    vals = []
    if target_company is not None:
        updates.append("target_company = ?")
        vals.append(target_company)
    if target_role is not None:
        updates.append("target_role = ?")
        vals.append(target_role)
    if resume_summary is not None:
        updates.append("resume_summary = ?")
        vals.append(resume_summary)
    if updates:
        vals.append(phone)
        sql = f"UPDATE users SET {', '.join(updates)} WHERE phone_number = ?"
        with get_conn() as conn:
            conn.execute(_q(sql), tuple(vals))
    return get_user(phone)


def get_today_drills(phone: str) -> list[dict[str, Any]]:
    today_str = date.today().isoformat()
    with get_conn() as conn:
        if _is_postgres():
            cur = conn.execute(
                _q("SELECT * FROM drills WHERE phone_number = ? AND created_at::date = CURRENT_DATE ORDER BY id ASC"),
                (phone,),
            )
        else:
            cur = conn.execute(
                _q("SELECT * FROM drills WHERE phone_number = ? AND DATE(created_at) = DATE(?) ORDER BY id ASC"),
                (phone, today_str),
            )
        return [dict(r) for r in cur.fetchall()]


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    return None


def next_streak(last_active: date | None, streak: int, today: date) -> int:
    streak = int(streak or 0)
    if last_active == today:
        return streak if streak else 1
    yesterday = date.fromordinal(today.toordinal() - 1)
    if last_active == yesterday:
        return streak + 1
    return 1


def bump_streak(phone: str) -> int:
    """Calendar-day streak (set process TZ via TIMEZONE)."""
    today = date.today()
    user = upsert_user(phone)
    last = _as_date(user.get("last_active_date"))
    streak = int(user.get("streak_count") or 0)
    new_streak = next_streak(last, streak, today)
    if last != today or streak != new_streak:
        _write_streak(phone, new_streak, today)
    return new_streak


def _write_streak(phone: str, streak: int, today: date) -> None:
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE users SET streak_count = ?, last_active_date = ? WHERE phone_number = ?"),
            (streak, today.isoformat(), phone),
        )


def record_attempt(
    phone: str,
    topic: str,
    question: str,
    response: str,
    feedback: str,
    score: int | None,
) -> None:
    correct_inc = 1 if score is not None and score >= 7 else 0
    with get_conn() as conn:
        conn.execute(
            _q(
                """INSERT INTO drills (phone_number, topic, question_text, user_response, model_feedback, score)
                   VALUES (?, ?, ?, ?, ?, ?)"""
            ),
            (phone, topic, question, response, feedback, score),
        )
        conn.execute(
            _q(
                """UPDATE users
                   SET questions_solved = COALESCE(questions_solved, 0) + 1,
                       correct_count = COALESCE(correct_count, 0) + ?
                   WHERE phone_number = ?"""
            ),
            (correct_inc, phone),
        )


def stats(phone: str) -> dict[str, Any]:
    user = upsert_user(phone)
    solved = int(user.get("questions_solved") or 0)
    correct = int(user.get("correct_count") or 0)
    accuracy = round((correct / solved) * 100) if solved else 0
    return {
        "streak": int(user.get("streak_count") or 0),
        "solved": solved,
        "correct": correct,
        "accuracy": accuracy,
        "track": user.get("track") or "General SDE",
        "pending": user.get("pending_question"),
        "drill_remaining": int(user.get("drill_remaining") or 0),
        "name": user.get("name") or "",
    }


def users_inactive_today() -> list[dict[str, Any]]:
    today = date.today().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            _q("SELECT * FROM users WHERE last_active_date IS NULL OR last_active_date < ?"),
            (today,),
        )
        return [dict(r) for r in cur.fetchall()]


def reset_hints(phone: str) -> None:
    """Reset hint counter (called when a new question is set)."""
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE users SET hint_count = 0 WHERE phone_number = ?"),
            (phone,),
        )


def increment_hints(phone: str) -> int:
    """Increment and return the new hint count."""
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE users SET hint_count = COALESCE(hint_count, 0) + 1 WHERE phone_number = ?"),
            (phone,),
        )
    user = get_user(phone)
    return int((user or {}).get("hint_count") or 0)


def update_difficulty(phone: str, score: int | None) -> str:
    """Adaptive difficulty: promote after 3 good scores, demote after 3 bad."""
    user = get_user(phone)
    if not user:
        return "easy"
    difficulty = user.get("difficulty") or "easy"
    good = int(user.get("consecutive_good") or 0)
    bad = int(user.get("consecutive_bad") or 0)

    if score is not None and score >= 7:
        good += 1
        bad = 0
    elif score is not None and score < 4:
        bad += 1
        good = 0
    else:
        good = 0
        bad = 0

    levels = ["easy", "medium", "hard"]
    idx = levels.index(difficulty) if difficulty in levels else 0

    if good >= 3 and idx < 2:
        idx += 1
        good = 0
    elif bad >= 3 and idx > 0:
        idx -= 1
        bad = 0

    new_diff = levels[idx]
    with get_conn() as conn:
        conn.execute(
            _q(
                "UPDATE users SET difficulty = ?, consecutive_good = ?, consecutive_bad = ? "
                "WHERE phone_number = ?"
            ),
            (new_diff, good, bad, phone),
        )
    return new_diff


def topic_stats(phone: str) -> list[dict[str, Any]]:
    """Per-topic average score and attempt count."""
    with get_conn() as conn:
        cur = conn.execute(
            _q(
                "SELECT topic, COUNT(*) as attempts, "
                "ROUND(AVG(CAST(score AS FLOAT)), 1) as avg_score "
                "FROM drills WHERE phone_number = ? AND score IS NOT NULL "
                "GROUP BY topic ORDER BY avg_score DESC"
            ),
            (phone,),
        )
        return [dict(r) for r in cur.fetchall()]


def leaderboard(limit: int = 10) -> list[dict[str, Any]]:
    """Top students by accuracy and questions solved."""
    with get_conn() as conn:
        cur = conn.execute(
            _q(
                "SELECT phone_number, name, questions_solved, correct_count, "
                "CASE WHEN questions_solved > 0 "
                "THEN ROUND(CAST(correct_count AS FLOAT) / questions_solved * 100, 1) "
                "ELSE 0 END as accuracy, "
                "streak_count, difficulty "
                "FROM users WHERE questions_solved > 0 "
                "ORDER BY accuracy DESC, questions_solved DESC "
                "LIMIT ?"
            ),
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def weekly_drill_summary(phone: str) -> list[dict[str, Any]]:
    """Drill attempts from the last 7 days for weekly reporting."""
    with get_conn() as conn:
        cur = conn.execute(
            _q(
                "SELECT topic, score, created_at FROM drills "
                "WHERE phone_number = ? "
                "AND created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days' "
                "ORDER BY created_at DESC"
            ) if _is_postgres() else _q(
                "SELECT topic, score, created_at FROM drills "
                "WHERE phone_number = ? "
                "AND created_at >= datetime('now', '-7 days') "
                "ORDER BY created_at DESC"
            ),
            (phone,),
        )
        return [dict(r) for r in cur.fetchall()]


def set_resume_analysis(
    phone: str,
    resume_score: int,
    skills_summary: str,
    resume_summary: str = "",
) -> None:
    """Save parsed resume score and skill diagnostics, setting initial readiness baseline."""
    score = max(10, min(100, int(resume_score or 65)))
    with get_conn() as conn:
        conn.execute(
            _q(
                "UPDATE users SET resume_score = ?, readiness_score = ?, "
                "skills_summary = ?, resume_summary = COALESCE(NULLIF(?, ''), resume_summary) "
                "WHERE phone_number = ?"
            ),
            (score, score, str(skills_summary or ""), str(resume_summary or ""), phone),
        )


def set_focus_area(phone: str, focus_area: str) -> None:
    """Set the active technical gap the user is currently working to fix."""
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE users SET active_focus_area = ? WHERE phone_number = ?"),
            (str(focus_area or "").strip(), phone),
        )


def update_readiness_score(phone: str, delta: int = 0) -> int:
    """Recompute or bump the user's composite placement readiness score (0-100)."""
    user = get_user(phone)
    if not user:
        return 65

    base = int(user.get("resume_score") or 65)
    solved = int(user.get("questions_solved") or 0)
    correct = int(user.get("correct_count") or 0)
    streak = int(user.get("streak_count") or 0)
    curr = int(user.get("readiness_score") or base)

    # Progressive composite formula:
    # Blend resume baseline with practice accuracy, volume, and consistency
    if solved > 0:
        accuracy = (correct / solved) * 100.0
        practice_weight = min(0.50, (solved / 20.0) * 0.50)
        resume_weight = 1.0 - practice_weight

        streak_bonus = min(5, streak)
        volume_bonus = min(10, int((solved / 30.0) * 10))

        computed = int((resume_weight * base) + (practice_weight * accuracy) + streak_bonus + volume_bonus)
    else:
        computed = base

    # Apply manual delta nudge from latest drill attempt (+2 for high score, etc.)
    new_score = max(20, min(99, computed + delta))

    with get_conn() as conn:
        conn.execute(
            _q("UPDATE users SET readiness_score = ? WHERE phone_number = ?"),
            (new_score, phone),
        )
    return new_score


def get_readiness_profile(phone: str) -> dict[str, Any]:
    """Fetch complete stats, readiness score, active focus, and target profile."""
    user = get_user(phone) or {}
    st = stats(phone)
    return {
        "name": user.get("name") or "Candidate",
        "track": user.get("track") or "General SDE",
        "resume_score": int(user.get("resume_score") or 65),
        "readiness_score": int(user.get("readiness_score") or 65),
        "active_focus_area": user.get("active_focus_area") or "",
        "target_company": user.get("target_company") or "",
        "target_role": user.get("target_role") or "",
        "streak": st.get("streak", 0),
        "solved": st.get("solved", 0),
        "correct": st.get("correct", 0),
        "accuracy": st.get("accuracy", 0.0),
        "difficulty": user.get("difficulty") or "easy",
    }
