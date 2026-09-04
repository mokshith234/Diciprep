"""Caspian event handlers for PlacementPrep AI (WhatsApp + Telegram)."""

from __future__ import annotations

import logging

from caspian import Button, Caspian, HandlerContext, Message, Thread

import db
from commands import is_followup, parse_command, parse_track_payload
from llm import (
    evaluate_answer,
    explain_followup,
    generate_hint,
    generate_question,
    parse_score,
    show_solution,
)
from outbound import post_chunks

log = logging.getLogger("placementprep.bot")

TRACK_BUTTONS = (
    Button(label="SDE Track", data="track:sde"),
    Button(label="Data Science", data="track:ds"),
    Button(label="Core CS", data="track:core"),
)

WELCOME = (
    "\U0001f680 *Welcome to PlacementPrep AI*\n\n"
    "Daily capsules, adaptive mocks, and instant code reviews \u2014 "
    "right here on WhatsApp & Telegram.\n\n"
    "Pick your target track:"
)

HELP = (
    "*Commands*\n"
    "\u2022 *drill* \u2014 3-question mock\n"
    "\u2022 *streak* \u2014 streak, solved, accuracy\n"
    "\u2022 *solution* \u2014 skip and see the optimal answer\n"
    "\u2022 *hint* \u2014 get a nudge without the answer\n"
    "\u2022 *topics* \u2014 per-topic performance breakdown\n"
    "\u2022 *level* \u2014 check your difficulty level\n"
    "\u2022 *leaderboard* \u2014 top students\n"
    "\u2022 *hi* \u2014 reset welcome / change track\n\n"
    'Reply with code or an approach to get graded. Ask \u201cexplain line 4\u201d anytime.'
)

MAX_HINTS = 2


def register(cx: Caspian) -> None:
    """Register channel-agnostic handlers so both WhatsApp and Telegram work."""

    @cx.on_action()
    def on_action(thread: Thread, msg: Message, ctx: HandlerContext) -> None:
        data = getattr(ctx, "data", None) or getattr(msg, "text", "") or ""
        handle_text(thread, msg, str(data))

    @cx.on_message({"overlap": "queue"})
    def on_message(thread: Thread, msg: Message, ctx: HandlerContext) -> None:
        text = (msg.text or "").strip()
        if not text:
            return
        handle_text(thread, msg, text)


def handle_text(thread: Thread, msg: Message, text: str) -> None:
    """Central dispatcher for all incoming messages."""
    phone = _phone(msg)
    name = _name(msg)
    db.upsert_user(phone, name=name)
    db.bump_streak(phone)

    # --- Track selection ---
    track_choice = parse_track_payload(text)
    if track_choice:
        db.upsert_user(phone, name=name, track=track_choice)
        thread.post(
            f"\u2705 Track set to *{track_choice}*.\n\n"
            "Send *drill* for a 3-question mock, or just answer anything CS \u2014 I'll coach you.",
        )
        return

    # --- Explicit commands ---
    cmd = parse_command(text)
    if cmd == "start":
        thread.post(WELCOME, actions=TRACK_BUTTONS)
        return
    if cmd == "help":
        thread.post(HELP)
        return
    if cmd == "streak":
        thread.post(_streak_card(phone))
        return
    if cmd == "drill":
        _start_drill(thread, phone)
        return
    if cmd == "solution":
        _give_solution(thread, phone)
        return
    if cmd == "hint":
        _give_hint(thread, phone)
        return
    if cmd == "topics":
        _show_topics(thread, phone)
        return
    if cmd == "level":
        _show_level(thread, phone)
        return
    if cmd == "leaderboard":
        _show_leaderboard(thread, phone)
        return

    # --- Contextual handling ---
    user = db.get_user(phone) or db.upsert_user(phone)
    pending = user.get("pending_question") if user else None
    if pending and is_followup(text):
        post_chunks(thread, explain_followup(pending, "", text))
        return
    if pending:
        _grade(thread, phone, pending, text, user)
        return

    # --- Open tutoring (no pending question) ---
    from llm import generate

    track = (user or {}).get("track") or "General SDE"
    reply = generate(
        f"The student (track {track}) sent this with no open mock question. "
        f"Coach them briefly and offer to start a drill.\n\n{text}"
    )
    post_chunks(thread, reply)


# ── Drill lifecycle ────────────────────────────────────────────────

def _start_drill(thread: Thread, phone: str) -> None:
    user = db.upsert_user(phone)
    track = user.get("track") or "General SDE"
    difficulty = user.get("difficulty") or "easy"
    question, topic = generate_question(track, difficulty=difficulty)
    db.set_pending(phone, question, topic, drill_remaining=2)
    db.reset_hints(phone)
    post_chunks(
        thread,
        f"\U0001f4dd *Drill started* ({track} \u2022 {difficulty.capitalize()}) \u2014 3 questions.\n\n"
        f"{question}\n\n"
        "_Reply with your code or approach. Send *hint* for a nudge or *solution* to skip._",
    )


def _grade(thread: Thread, phone: str, question: str, answer: str, user: dict) -> None:
    track = user.get("track") or "General SDE"
    topic = user.get("pending_topic") or "general"
    try:
        feedback = evaluate_answer(question, answer, track)
    except Exception:
        log.exception("Gemini grade failed")
        thread.post("Couldn't reach the interviewer model. Try again in a few seconds.")
        return
    score = parse_score(feedback)
    db.record_attempt(phone, topic, question, answer, feedback, score)
    remaining = int(user.get("drill_remaining") or 0)
    post_chunks(thread, feedback)

    # Adaptive difficulty
    new_diff = db.update_difficulty(phone, score)
    old_diff = user.get("difficulty") or "easy"
    if new_diff != old_diff:
        thread.post(f"\U0001f4a1 Difficulty updated: *{old_diff.capitalize()}* \u2192 *{new_diff.capitalize()}*")

    if remaining > 0:
        difficulty = new_diff
        nxt, topic = generate_question(track, difficulty=difficulty)
        db.set_pending(phone, nxt, topic, drill_remaining=remaining - 1)
        db.reset_hints(phone)
        post_chunks(thread, f"\u27a1\ufe0f *Question {4 - remaining}/3*\n\n{nxt}")
        return

    db.set_pending(phone, None, None, drill_remaining=0)
    thread.post(
        "\U0001f525 Session complete! Send *drill* for another round, "
        "*streak* for stats, or *topics* for your performance breakdown."
    )


def _give_solution(thread: Thread, phone: str) -> None:
    user = db.get_user(phone)
    pending = (user or {}).get("pending_question")
    if not pending:
        thread.post("No open question. Send *drill* to start one.")
        return
    track = (user or {}).get("track") or "General SDE"
    try:
        body = show_solution(pending, track)
    except Exception:
        log.exception("Gemini solution failed")
        thread.post("Couldn't fetch the solution. Try *solution* again.")
        return
    remaining = int((user or {}).get("drill_remaining") or 0)
    post_chunks(thread, body)
    if remaining > 0:
        difficulty = (user or {}).get("difficulty") or "easy"
        nxt, topic = generate_question(track, difficulty=difficulty)
        db.set_pending(phone, nxt, topic, drill_remaining=remaining - 1)
        db.reset_hints(phone)
        post_chunks(thread, f"\u27a1\ufe0f Next drill question:\n\n{nxt}")
        return
    db.set_pending(phone, None, None, drill_remaining=0)
    thread.post("Send *drill* when you want the next mock.")


# ── Hint system ────────────────────────────────────────────────────

def _give_hint(thread: Thread, phone: str) -> None:
    user = db.get_user(phone)
    pending = (user or {}).get("pending_question")
    if not pending:
        thread.post("No open question. Send *drill* to start one.")
        return
    current_hints = int((user or {}).get("hint_count") or 0)
    if current_hints >= MAX_HINTS:
        thread.post(
            f"You've used all {MAX_HINTS} hints for this question.\n"
            "Send your best attempt or *solution* to see the answer."
        )
        return
    new_count = db.increment_hints(phone)
    try:
        hint = generate_hint(pending, new_count)
    except Exception:
        log.exception("Gemini hint failed")
        thread.post("Couldn't generate a hint right now. Try again.")
        return
    remaining_hints = MAX_HINTS - new_count
    post_chunks(
        thread,
        f"\U0001f4a1 *Hint {new_count}/{MAX_HINTS}*\n\n{hint}\n\n"
        f"_{'1 hint remaining' if remaining_hints == 1 else 'No more hints'} \u2014 "
        f"reply with your approach or send *solution*._",
    )


# ── Analytics & info commands ──────────────────────────────────────

def _show_topics(thread: Thread, phone: str) -> None:
    topics = db.topic_stats(phone)
    if not topics:
        thread.post("No topic data yet. Complete a *drill* first!")
        return
    lines = ["\U0001f4ca *Topic-wise Performance*\n"]
    for t in topics:
        avg = t.get("avg_score") or 0
        attempts = t.get("attempts") or 0
        bar = "\u2588" * int(float(avg)) + "\u2591" * (10 - int(float(avg)))
        lines.append(f"{bar} *{t['topic']}* — avg {avg}/10 ({attempts} Qs)")
    thread.post("\n".join(lines))


def _show_level(thread: Thread, phone: str) -> None:
    user = db.get_user(phone) or db.upsert_user(phone)
    difficulty = (user.get("difficulty") or "easy").capitalize()
    good = int(user.get("consecutive_good") or 0)
    bad = int(user.get("consecutive_bad") or 0)
    icons = {"Easy": "\U0001f7e2", "Medium": "\U0001f7e1", "Hard": "\U0001f534"}
    icon = icons.get(difficulty, "\u26aa")
    msg = f"{icon} *Current Level: {difficulty}*\n\n"
    if difficulty != "Hard":
        needed = 3 - good
        msg += f"Score \u2265 7 on *{needed}* more question(s) to level up.\n"
    if difficulty != "Easy":
        danger = 3 - bad
        msg += f"Score < 4 on *{danger}* more question(s) and you'll level down.\n"
    msg += "\nSend *drill* to keep climbing!"
    thread.post(msg)


def _show_leaderboard(thread: Thread, phone: str) -> None:
    rows = db.leaderboard()
    if not rows:
        thread.post("Leaderboard is empty. Be the first \u2014 send *drill*!")
        return
    lines = ["\U0001f3c6 *Leaderboard — Top 10*\n"]
    medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        display_name = r.get("name") or r["phone_number"][-4:]
        acc = r.get("accuracy") or 0
        solved = r.get("questions_solved") or 0
        diff = (r.get("difficulty") or "easy").capitalize()
        lines.append(f"{medal} *{display_name}* — {acc}% acc \u2022 {solved} Qs \u2022 {diff}")
    # Show requester's position if not in top 10
    phones_in_lb = [r["phone_number"] for r in rows]
    if phone not in phones_in_lb:
        s = db.stats(phone)
        lines.append(f"\n\u2014\n\U0001f464 *You:* {s['accuracy']}% acc \u2022 {s['solved']} Qs")
    thread.post("\n".join(lines))


def _streak_card(phone: str) -> str:
    s = db.stats(phone)
    user = db.get_user(phone) or {}
    difficulty = (user.get("difficulty") or "easy").capitalize()
    return (
        "\U0001f4ca *Your PlacementPrep stats*\n\n"
        f"\U0001f525 Streak: *{s['streak']}* day(s)\n"
        f"\u2705 Questions solved: *{s['solved']}*\n"
        f"\U0001f3af Accuracy (score \u2265 7): *{s['accuracy']}%*\n"
        f"\U0001f3af Track: *{s['track']}*\n"
        f"\U0001f4aa Level: *{difficulty}*\n\n"
        "Keep the chain alive \u2014 morning capsule drops at 8:00 AM."
    )


# ── Helpers ────────────────────────────────────────────────────────

def _phone(msg: Message) -> str:
    sender = getattr(msg, "sender", "") or ""
    if sender:
        return str(sender)
    tid = str(getattr(msg, "thread_id", "") or "")
    return tid.split(":", 1)[-1]


def _name(msg: Message) -> str:
    raw = getattr(msg, "raw", None)
    if isinstance(raw, dict):
        contacts = raw.get("contacts") or []
        if contacts and isinstance(contacts[0], dict):
            profile = contacts[0].get("profile") or {}
            return str(profile.get("name") or "")
    return ""
