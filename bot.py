"""Caspian event handlers for PlacementPrep AI (WhatsApp + Telegram)."""

from __future__ import annotations

import logging

from caspian import Button, Caspian, HandlerContext, Message, Thread

import db
from commands import (
    is_followup,
    parse_command,
    parse_company_command,
    parse_resume_command,
    parse_role_command,
    parse_topic_drill,
    parse_track_payload,
)
from llm import (
    analyze_resume,
    evaluate_answer,
    explain_followup,
    generate_company_question,
    generate_daily_summary,
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

DRILL_BUTTONS = (
    Button(label="💡 Hint", data="cmd:hint"),
    Button(label="📖 Solution", data="cmd:solution"),
    Button(label="⏭ Skip", data="cmd:skip"),
)

MENU_BUTTONS = (
    Button(label="🎯 3-Question Mock", data="cmd:drill"),
    Button(label="📊 My Stats", data="cmd:streak"),
    Button(label="📑 Today's Summary", data="cmd:summary"),
)

WELCOME = (
    "🚀 *Welcome to PlacementPrep AI*\n\n"
    "Daily capsules, adaptive mocks, instant code reviews, and resume analysis — "
    "right here on WhatsApp & Telegram.\n\n"
    "Pick your target track:"
)

HELP = (
    "*PlacementPrep AI Commands*\n"
    "• *menu* — Open the on-demand practice dashboard\n"
    "• *drill* — Start a 3-question adaptive mock interview\n"
    "• *drill <topic>* — Practice a specific topic (e.g. `drill os`, `drill dsa`, `drill dbms`)\n"
    "• *company <name>* — Target a company (e.g. `company amazon`, `company google`)\n"
    "• *role <name>* — Target your dream role (e.g. `role SDE 1`, `role Backend`)\n"
    "• *resume: <text>* — Review resume, find vulnerabilities, and get a 7-day roadmap\n"
    "• *summary* — Daily revision cheat sheet of today's solved questions\n"
    "• *streak* — Daily streak, solved count, and accuracy\n"
    "• *topics* — Per-topic performance breakdown\n"
    "• *level* — Current difficulty level\n"
    "• *leaderboard* — Top student rankings\n"
    "• *hint* / *solution* — Get help during a mock drill\n"
    "• *hi* — Reset track selection\n\n"
    "Reply with your code or step-by-step logic anytime to get graded."
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
    user = db.get_user(phone) or db.upsert_user(phone)

    # --- Track selection ---
    track_choice = parse_track_payload(text)
    if track_choice:
        db.upsert_user(phone, name=name, track=track_choice)
        thread.post(
            f"✅ Track set to *{track_choice}*.\n\n"
            "Send *drill* for a 3-question mock, or *company <name>* to target a specific firm!",
        )
        return

    # --- Topic-specific drill (e.g. 'drill os', 'drill dsa') ---
    topic_drill = parse_topic_drill(text)
    if topic_drill:
        _start_drill(thread, phone, topic=topic_drill)
        return

    # --- Company targeting (e.g. 'company amazon', 'company google') ---
    company = parse_company_command(text)
    if company:
        db.update_profile(phone, target_company=company)
        thread.post(
            f"🏢 Target company set to *{company.capitalize()}*!\n\n"
            f"Your mock rounds will now reflect {company.capitalize()}'s hiring bar and question patterns.\n\n"
            "Send *drill* to start a company mock round, or *role <name>* to set your target position!"
        )
        return

    # --- Role targeting (e.g. 'role SDE 1', 'role Backend Python') ---
    role = parse_role_command(text)
    if role:
        db.update_profile(phone, target_role=role)
        thread.post(
            f"🎯 Target role set to *{role}*!\n\n"
            "Now send your resume text or projects to personalize your drills:\n"
            "`resume: <paste your skills / projects / experience>`"
        )
        return

    # --- Resume review & tailored prep ---
    is_res, res_content = parse_resume_command(text)
    if is_res:
        if not res_content:
            thread.post(
                "📄 *Resume Analyzer & Prep Tailoring*\n\n"
                "Send your resume text, skills, or projects like this:\n"
                "`resume: 3rd year CSE, built fullstack app with React/Node/Redis, skilled in Java, DSA, OS, DBMS.`\n\n"
                "I will analyze your vulnerabilities, provide a 7-day roadmap, and tailor future drills to your stack!"
            )
            return
        thread.post("🔍 *Analyzing your resume and tailoring interview drills...*")
        try:
            target_role = (user or {}).get("target_role") or "Software Development Engineer"
            analysis = analyze_resume(res_content, target_role=target_role)
            db.update_profile(phone, resume_summary=res_content[:500])
            post_chunks(thread, analysis)
            thread.post(
                "✅ *Profile saved!* Your mock interview questions will now challenge you on your resume claims.\n\n"
                "Send *drill* whenever you are ready to test your knowledge!"
            )
        except Exception:
            log.exception("Resume analysis failed")
            thread.post("Couldn't analyze your resume right now. Please try sending it again.")
        return

    # --- Explicit commands ---
    cmd = parse_command(text)
    if cmd == "start":
        thread.post(WELCOME, actions=TRACK_BUTTONS)
        return
    if cmd == "menu":
        thread.post(
            "🎓 *PlacementPrep On-Demand Practice*\n\n"
            "Prepare whenever you want, 24/7:\n\n"
            "• *Mock Interview* — 3 adaptive questions\n"
            "• *Topic Practice* — `drill os`, `drill dsa`, `drill dbms`\n"
            "• *Company Mock* — `company amazon`, `company google`\n"
            "• *Resume Roadmap* — `resume: <skills/projects>`\n"
            "• *Daily Revision* — `summary` for today's cheat sheet\n\n"
            "Tap a quick button to start:",
            actions=MENU_BUTTONS,
        )
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
    if cmd == "summary":
        drills_today = db.get_today_drills(phone)
        try:
            summary = generate_daily_summary(drills_today, user or {})
            post_chunks(thread, summary)
        except Exception:
            log.exception("Daily summary failed")
            thread.post("Couldn't generate your revision summary right now. Try again shortly.")
        return

    # --- Contextual handling ---
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
    try:
        reply = generate(
            f"The student (track {track}) sent this with no open mock question. "
            f"Coach them briefly and offer to start a drill.\n\n{text}"
        )
        post_chunks(thread, reply)
    except Exception:
        log.exception("Open tutoring generation failed")
        thread.post(
            "I'm your PlacementPrep AI coach! 🎓\n\n"
            "Here is what you can do:\n"
            "• *drill* — Start a 3-question adaptive mock interview\n"
            "• *drill <topic>* — Practice a specific topic (e.g. `drill os`, `drill dsa`)\n"
            "• *company <name>* — Target a company (e.g. `company amazon`)\n"
            "• *resume: <text>* — Review resume and tailor your questions\n"
            "• *summary* — Daily revision cheat sheet\n"
            "• *streak* — View your active daily streak and stats\n\n"
            "Send *drill* to start practicing!"
        )


# ── Drill lifecycle ────────────────────────────────────────────────

def _start_drill(thread: Thread, phone: str, topic: str | None = None) -> None:
    user = db.upsert_user(phone)
    track = user.get("track") or "General SDE"
    difficulty = user.get("difficulty") or "easy"
    target_company = user.get("target_company") or ""
    resume_summary = user.get("resume_summary") or ""
    try:
        if target_company:
            question, chosen_topic = generate_company_question(
                target_company, track, topic=topic, difficulty=difficulty, resume_context=resume_summary
            )
        else:
            question, chosen_topic = generate_question(track, topic=topic, difficulty=difficulty)
    except Exception:
        log.exception("Drill question generation failed")
        thread.post("Couldn't generate a question right now. Send *drill* again in a moment.")
        return
    db.set_pending(phone, question, chosen_topic, drill_remaining=2)
    db.reset_hints(phone)

    tag = f" [🏢 {target_company.capitalize()}]" if target_company else ""
    post_chunks(
        thread,
        f"📝 *Drill started* ({track} • {difficulty.capitalize()}){tag} — 3 questions.\n\n"
        f"{question}\n\n"
        "_Reply with your code or approach. Or use the buttons below:_",
        actions=DRILL_BUTTONS,
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
        thread.post(f"💡 Difficulty updated: *{old_diff.capitalize()}* → *{new_diff.capitalize()}*")

    if remaining > 0:
        difficulty = new_diff
        target_company = user.get("target_company") or ""
        resume_summary = user.get("resume_summary") or ""
        if target_company:
            nxt, chosen_topic = generate_company_question(
                target_company, track, difficulty=difficulty, resume_context=resume_summary
            )
        else:
            nxt, chosen_topic = generate_question(track, difficulty=difficulty)
        db.set_pending(phone, nxt, chosen_topic, drill_remaining=remaining - 1)
        db.reset_hints(phone)
        post_chunks(thread, f"➡️ *Question {4 - remaining}/3*\n\n{nxt}", actions=DRILL_BUTTONS)
        return

    db.set_pending(phone, None, None, drill_remaining=0)
    thread.post(
        "🔥 Session complete! Send *drill* for another round, "
        "*summary* for today's cheat sheet, or *streak* for stats."
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
        target_company = (user or {}).get("target_company") or ""
        resume_summary = (user or {}).get("resume_summary") or ""
        if target_company:
            nxt, chosen_topic = generate_company_question(
                target_company, track, difficulty=difficulty, resume_context=resume_summary
            )
        else:
            nxt, chosen_topic = generate_question(track, difficulty=difficulty)
        db.set_pending(phone, nxt, chosen_topic, drill_remaining=remaining - 1)
        db.reset_hints(phone)
        post_chunks(thread, f"➡️ Next drill question:\n\n{nxt}", actions=DRILL_BUTTONS)
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
