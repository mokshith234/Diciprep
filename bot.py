"""Caspian event handlers for PlacementPrep AI (WhatsApp + Telegram)."""

from __future__ import annotations

import logging
import traceback

from caspian import Button, Caspian, HandlerContext, Message, Thread

import os
import re as _re

import db
from commands import (
    is_followup,
    is_asking_question_or_clarification,
    looks_like_answer,
    parse_command,
    parse_company_command,
    parse_onboard_company,
    parse_onboard_role,
    parse_onboard_timeline,
    parse_onboarding_payload,
    parse_resume_command,
    parse_role_command,
    parse_switch_command,
    parse_target_profile,
    parse_topic_drill,
    parse_track_payload,
)
from llm import (
    analyze_resume,
    evaluate_answer,
    explain_followup,
    extract_skills_from_resume,
    generate_company_question,
    generate_daily_summary,
    generate_hint,
    generate_prep_plan,
    generate_question,
    parse_score,
    show_solution,
    tutor_reason_and_answer,
)
from outbound import post_chunks

log = logging.getLogger("placementprep.bot")

# ── Onboarding buttons ─────────────────────────────────────────────

ONBOARDING_BUTTONS = (
    Button(label="🎯 Pick My Track", data="onboard:manual"),
    Button(label="🤖 AI Resume Scanner", data="onboard:ai"),
    Button(label="⚡ Instant Mock Drill", data="cmd:drill"),
)

TRACK_BUTTONS = (
    Button(label="SDE Track", data="track:sde"),
    Button(label="Data Science", data="track:ds"),
    Button(label="Core CS", data="track:core"),
)

TARGET_PROFILE_BUTTONS = (
    Button(label="🏢 Tier-1 / FAANG SDE", data="tp:faang"),
    Button(label="📦 Amazon / Backend SDE", data="tp:amazon"),
    Button(label="🪟 Microsoft / Fullstack", data="tp:microsoft"),
    Button(label="💼 TCS / Mass Recruiters", data="tp:tcs"),
    Button(label="📊 Data Science & AI", data="tp:ds"),
    Button(label="⚙️ Core CS & Systems", data="tp:core"),
    Button(label="⚡ General SDE Drill", data="tp:general"),
)

COMPANY_BUTTONS = (
    Button(label="🔍 Google", data="obc:google"),
    Button(label="📦 Amazon", data="obc:amazon"),
    Button(label="🪟 Microsoft", data="obc:microsoft"),
    Button(label="🏢 TCS", data="obc:tcs"),
    Button(label="💼 Infosys", data="obc:infosys"),
    Button(label="🎯 Other / Skip", data="obc:any"),
)

ROLE_BUTTONS = (
    Button(label="💻 SDE / Backend", data="obr:SDE"),
    Button(label="🌐 Frontend / Fullstack", data="obr:Frontend"),
    Button(label="📊 Data Scientist", data="obr:Data Scientist"),
    Button(label="⚙️ DevOps / Cloud", data="obr:DevOps"),
    Button(label="🔐 Security / Core", data="obr:Core Engineer"),
    Button(label="🎯 Other / Skip", data="obr:Software Engineer"),
)

TIMELINE_BUTTONS = (
    Button(label="🔥 This Month", data="obt:This Month"),
    Button(label="📅 1–3 Months", data="obt:1-3 Months"),
    Button(label="📆 3–6 Months", data="obt:3-6 Months"),
    Button(label="🗓️ Next Year", data="obt:Next Year"),
)

DRILL_BUTTONS = (
    Button(label="💡 Hint", data="cmd:hint"),
    Button(label="📖 Solution", data="cmd:solution"),
    Button(label="⏭ Skip", data="cmd:skip"),
    Button(label="🔄 Switch Mood", data="cmd:switch_mood"),
)

STALE_QUESTION_BUTTONS = (
    Button(label="✍️ Answer It", data="cmd:continue_pending"),
    Button(label="🔄 Switch Mood", data="cmd:switch_mood"),
    Button(label="📖 Solution", data="cmd:solution"),
    Button(label="⏭ Skip", data="cmd:skip"),
)

SWITCH_MOOD_BUTTONS = (
    Button(label="💻 DSA Drill", data="drill dsa"),
    Button(label="⚙️ OS Drill", data="drill os"),
    Button(label="🗄️ DBMS Drill", data="drill dbms"),
    Button(label="🌐 CN Drill", data="drill cn"),
    Button(label="🏢 Company Mock", data="cmd:menu"),
)

MENU_BUTTONS = (
    Button(label="🎯 3-Question Mock", data="cmd:drill"),
    Button(label="📊 My Stats", data="cmd:streak"),
    Button(label="📑 Today's Summary", data="cmd:summary"),
    Button(label="🔄 Switch Mood", data="cmd:switch_mood"),
)

def build_welcome_message(name: str = "") -> str:
    """Build a rich, vibrant, and immersive startup welcome card."""
    clean_name = f" {name.strip()}" if name and name.strip() else ""
    return (
        "╔══════════════════════════════╗\n"
        "   🚀  *PLACEMENT PREP AI*  ⚡\n"
        "   _The 24/7 Elite Tech Career Studio_\n"
        "╚══════════════════════════════╝\n\n"
        f"👋 *Hey{clean_name}! Welcome to your placement command center.*\n\n"
        "Ready to crack *Google, Amazon, Microsoft, or top-tier tech firms*? "
        "I'm your personal AI placement mentor — here to drill your algorithms, review your code, "
        "analyze your resume, and elevate your interview confidence.\n\n"
        "🌟 *WHAT WE'LL DO TOGETHER:*\n"
        "╭───────────────────────────────\n"
        "│ 🎯 *Adaptive Mock Drills*\n"
        "│    └ Live interview questions with instant grading & hints\n"
        "│ 📄 *Resume & Skill Intelligence*\n"
        "│    └ Deep scan of your projects, gaps & role alignment\n"
        "│ 🏢 *Company-Targeted Modules*\n"
        "│    └ Curated questions modeled after top tech recruiters\n"
        "│ 🔥 *Streak & Daily Capsules*\n"
        "│    └ Daily 8:00 AM micro-challenges to stay sharp\n"
        "╰───────────────────────────────\n\n"
        "✨ *CHOOSE YOUR LAUNCHPAD:*\n\n"
        "1️⃣ 🎯 *Pick My Track* — Choose your domain (SDE / Data Science / Core CS)\n"
        "2️⃣ 🤖 *AI Resume Scanner* — Paste resume text to build a tailored plan\n"
        "3️⃣ ⚡ *Instant Drill* — Jump straight into a 3-question live mock!\n\n"
        "👇 _Tap an option below to begin:_"
    )


WELCOME = build_welcome_message()


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

FALLBACK_MSG = (
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


class TelegramDirectThread:
    """Proxies thread.post calls directly to Telegram Bot API when chatting with Telegram users.

    This completely bypasses Caspian's 24-hour conversation reply cap (loop prevention)
    and ensures ultra-fast, 100% reliable delivery of text, markdown, and interactive buttons.
    """

    def __init__(self, original_thread: Thread, chat_id: str):
        self._thread = original_thread
        self.chat_id = chat_id
        self.thread_id = getattr(original_thread, "thread_id", "")
        self._commands = getattr(original_thread, "_commands", [])

    def post(self, text: str, *, actions: tuple[Any, ...] = ()) -> None:
        from outbound import send_telegram
        send_telegram(self.chat_id, text, actions=actions)


def handle_text(thread: Thread, msg: Message, text: str) -> None:
    """Central dispatcher for all incoming messages.

    CRITICAL: This is wrapped in a top-level try/except so that
    no message is ever silently lost.  Any unhandled exception will
    send a friendly error reply instead of leaving the user staring
    at a clock symbol.
    """
    phone = _phone(msg)
    is_telegram = (
        str(getattr(msg, "thread_id", "")).startswith("telegram:")
        or str(getattr(thread, "thread_id", "")).startswith("telegram:")
        or bool(os.environ.get("TELEGRAM_BOT_TOKEN") and not os.environ.get("WHATSAPP_ACCESS_TOKEN"))
    )
    if is_telegram and phone:
        import threading
        from outbound import send_telegram_typing
        threading.Thread(target=send_telegram_typing, args=(phone,), daemon=True).start()
        thread = TelegramDirectThread(thread, phone)

    try:
        _handle_text_inner(thread, msg, text)
    except Exception:
        log.exception("Unhandled error in handle_text for text=%r", text[:100])
        try:
            thread.post(
                "⚠️ Something went wrong on my end. Please try again!\n\n"
                "Send *drill* to start a mock, or *hi* to reset."
            )
        except Exception:
            log.exception("Failed to send error fallback message")


def _handle_text_inner(thread: Thread, msg: Message, text: str) -> None:
    """The real message dispatcher — called inside a safety net."""
    phone = _phone(msg)
    name = _name(msg)

    if not phone:
        log.warning("Could not extract phone/ID from message: %r", msg)
        thread.post("Sorry, I couldn't identify your account. Please try again.")
        return

    # Ensure user exists and bump streak — single safe block
    try:
        db.upsert_user(phone, name=name)
        db.bump_streak(phone)
    except Exception:
        log.exception("DB upsert/streak failed for phone=%s", phone)
        # Continue anyway — user might exist already

    user = _safe_get_user(phone)

    # ── Onboarding path selection (button payloads) ──
    onboard_choice = parse_onboarding_payload(text)
    if onboard_choice == "manual":
        db.set_onboarding_step(phone, None)
        thread.post(
            "🎯 *CUSTOM PREP SETUP*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Pick your target domain below to calibrate your questions, "
            "difficulty scaling, and daily capsules:\n\n"
            "💻 *SDE Track* — DSA, System Design, OOP & Algorithms\n"
            "📊 *Data Science* — Python, Machine Learning, Stats & SQL\n"
            "⚙️ *Core CS* — Operating Systems, DBMS, Networks & Architecture\n\n"
            "👇 _Select your track below:_",
            actions=TRACK_BUTTONS,
        )
        return
    if onboard_choice == "ai":
        db.set_onboarding_step(phone, "awaiting_resume")
        thread.post(
            "🤖 *AI RESUME INTELLIGENCE ENGINE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Drop your resume text, LinkedIn summary, or skill profile right here! 📄✨\n\n"
            "🔍 *What I'll do:*\n"
            "✦ Identify your core technical strengths & stacks\n"
            "✦ Spot critical interview gaps for your target roles\n"
            "✦ Formulate a custom step-by-step prep roadmap\n\n"
            "💡 _Quick Example to copy/paste:_\n"
            "`3rd year CSE. Strong in Java, C++, Python, DSA, DBMS.\n"
            "Built a Fullstack MERN e-commerce app and a Redis caching layer.\n"
            "Targeting SDE-1 backend roles at Tier-1 companies.`\n\n"
            "📋 *Simply paste your resume or summary below to get started!* 👇"
        )
        return

    # ── Quick target profile pack selection (anytime button tap) ──
    if text.strip().lower().startswith("tp:"):
        _onboard_target_profile(thread, phone, text, user)
        return

    # ── Onboarding state machine (multi-step AI flow) ──
    onboarding_step = (user or {}).get("onboarding_step")
    if onboarding_step:
        _handle_onboarding(thread, phone, text, user, onboarding_step)
        return

    # --- Track selection ---
    track_choice = parse_track_payload(text)
    if track_choice:
        try:
            db.upsert_user(phone, name=name, track=track_choice)
        except Exception:
            log.exception("Failed to set track for %s", phone)
        thread.post(
            f"🎉 *Track Confirmed: {track_choice}!* 🚀\n\n"
            "Your placement training environment is now configured.\n"
            "I will adapt every drill and daily capsule to this domain.\n\n"
            "⚡ *Quick Launch:*\n"
            "• Tap *3-Question Mock* below to start your first drill\n"
            "• Or send `company amazon` / `company google` to target specific firms!\n\n"
            "👇 _Ready when you are:_",
            actions=MENU_BUTTONS,
        )
        return

    # --- Switch prep mood / cancel active drill ---
    switch_target = parse_switch_command(text)
    if switch_target:
        db.clear_pending(phone)
        if isinstance(switch_target, str):
            _start_drill(thread, phone, topic=switch_target)
            return
        thread.post(
            "🔄 *Prep Mood Switched!*\n\n"
            "Your previous question is cleared. What would you like to prepare now?\n\n"
            "• *Topic Drill* — `drill os`, `drill dsa`, `drill dbms`, `drill cn`\n"
            "• *Company Mock* — `company amazon`, `company google`\n"
            "• *Resume Tailoring* — `resume: <skills/projects>`\n"
            "• *Random Mock* — `drill`\n\n"
            "Tap an option below to jump straight in:",
            actions=SWITCH_MOOD_BUTTONS,
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

    # Stale question check (> 15 minutes unanswered)
    pending = (user or {}).get("pending_question")
    age_seconds = db.get_pending_age_seconds(user)
    is_stale = bool(pending and age_seconds is not None and age_seconds > 900)

    # --- Explicit commands ---
    cmd = parse_command(text)
    if cmd == "start":
        if is_stale and text.lower().strip() in ("hi", "hello", "hey", "hola"):
            _prompt_stale_question(thread, user, pending, age_seconds)
            return
        db.clear_pending(phone)
        display_name = name or (user or {}).get("name") or ""
        thread.post(build_welcome_message(display_name), actions=ONBOARDING_BUTTONS)
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
    if cmd == "skip":
        _skip_question(thread, phone)
        return
    if cmd == "continue_pending":
        _continue_pending(thread, phone, user)
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
        _show_summary(thread, phone, user)
        return
    # "resume" command without content — show instructions
    if cmd == "resume":
        thread.post(
            "📄 *Resume Analyzer & Prep Tailoring*\n\n"
            "Send your resume text, skills, or projects like this:\n"
            "`resume: 3rd year CSE, built fullstack app with React/Node/Redis, skilled in Java, DSA, OS, DBMS.`\n\n"
            "I will analyze your vulnerabilities, provide a 7-day roadmap, and tailor future drills to your stack!"
        )
        return
    # "switch" command — already handled above by parse_switch_command,
    # but if someone types just "switch" and parse_switch_command returned True
    # but we somehow reached here, catch it:
    if cmd == "switch":
        db.clear_pending(phone)
        thread.post(
            "🔄 *Prep Mood Switched!*\n\n"
            "Your previous question is cleared. Pick what to prep next:",
            actions=SWITCH_MOOD_BUTTONS,
        )
        return
    if cmd == "clear":
        db.force_clear_all_state(phone)
        thread.post(
            "🧹 *Session cleared!* All pending questions and state wiped.\n\n"
            "You're starting fresh. Send *drill* for a new mock, or *hi* to pick a track!",
            actions=MENU_BUTTONS,
        )
        return

    # --- Contextual handling ---
    if pending:
        if is_stale and not looks_like_answer(text) and not is_asking_question_or_clarification(text):
            _prompt_stale_question(thread, user, pending, age_seconds)
            return

        if is_asking_question_or_clarification(text):
            try:
                track = (user or {}).get("track") or "General SDE"
                ans = tutor_reason_and_answer(text, active_question=pending, track=track)
                post_chunks(thread, ans)
                thread.post(
                    "💡 _Your mock drill question is still active above! "
                    "Whenever you're ready, reply with your code or step-by-step logic._",
                    actions=DRILL_BUTTONS,
                )
            except Exception:
                log.exception("Clarification/question tutor failed")
                thread.post("Couldn't process that question right now. Try asking again!")
            return

        _grade(thread, phone, pending, text, user)
        return

    # --- Open tutoring (no pending question) ---
    _open_tutoring(thread, phone, text, user)


# ── Helpers extracted for clarity & safety ──────────────────────────

def _safe_get_user(phone: str) -> dict | None:
    """Get user from DB with error protection."""
    try:
        return db.get_user(phone)
    except Exception:
        log.exception("Failed to get_user for phone=%s", phone)
        return None


# ── Onboarding state machine ──────────────────────────────────────

def _handle_onboarding(thread: Thread, phone: str, text: str, user: dict | None, step: str) -> None:
    """Multi-step AI-guided onboarding flow.

    Steps: awaiting_resume → awaiting_company → awaiting_role → awaiting_timeline → done
    """
    # Allow explicit commands to break out of onboarding
    cmd = parse_command(text)
    if cmd in ("start", "clear", "switch", "help", "drill"):
        db.set_onboarding_step(phone, None)
        user_name = (user or {}).get("name") or ""
        if cmd == "start":
            thread.post(build_welcome_message(user_name), actions=ONBOARDING_BUTTONS)
        elif cmd == "clear":
            db.force_clear_all_state(phone)
            thread.post(
                "🧹 *Session cleared!* Starting fresh.",
                actions=ONBOARDING_BUTTONS,
            )
        elif cmd == "help":
            thread.post(HELP)
        elif cmd == "drill":
            _start_drill(thread, phone)
        elif cmd == "switch":
            thread.post(
                "🔄 *Switched!* Pick what to prep:",
                actions=SWITCH_MOOD_BUTTONS,
            )
        return

    if step == "awaiting_resume":
        _onboard_resume(thread, phone, text)
    elif step == "awaiting_target_profile":
        _onboard_target_profile(thread, phone, text, user)
    elif step == "awaiting_company":
        _onboard_company(thread, phone, text, user)
    elif step == "awaiting_role":
        _onboard_role(thread, phone, text, user)
    elif step == "awaiting_timeline":
        _onboard_timeline(thread, phone, text, user)
    else:
        # Unknown step — reset
        db.set_onboarding_step(phone, None)
        user_name = (user or {}).get("name") or ""
        thread.post(build_welcome_message(user_name), actions=ONBOARDING_BUTTONS)


def _onboard_resume(thread: Thread, phone: str, text: str) -> None:
    """Step 1: User pasted resume text → AI extracts skills → ask combined target."""
    # Ignore very short messages (probably accidental)
    if len(text.strip()) < 15:
        thread.post(
            "📝 That seems too short! Please paste your full resume, skills list, "
            "or project descriptions so I can analyze them properly."
        )
        return

    thread.post("🔍 *Analyzing your profile...*")

    try:
        # Extract skills and save resume
        analysis = extract_skills_from_resume(text)
        db.update_profile(phone, resume_summary=text[:500])

        # Detect track from AI response and set it
        analysis_lower = analysis.lower()
        if "data science" in analysis_lower:
            db.upsert_user(phone, track="Data Science")
        elif "core cs" in analysis_lower:
            db.upsert_user(phone, track="Core CS")
        else:
            db.upsert_user(phone, track="Software Development")

        post_chunks(thread, analysis)

        # Move to combined single-step target selection (saves turns and tokens!)
        db.set_onboarding_step(phone, "awaiting_target_profile")
        thread.post(
            "🎯 *LOCK YOUR TARGET CAREER GOAL*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Choose a target pack below to configure your company questions, role focus, "
            "and timeline together in *1 click*:\n\n"
            "• *Tier-1 / FAANG* — Google, Amazon, Meta (SDE • 1–3 mos)\n"
            "• *Amazon / Backend* — Distributed systems & DSA (1–3 mos)\n"
            "• *Microsoft / Fullstack* — Web systems & Algorithms (1–3 mos)\n"
            "• *TCS / Mass Recruiters* — Aptitude, Core CS & Coding (This Month)\n"
            "• *Data Science & AI* — Python, ML, SQL (1–3 mos)\n"
            "• *Core CS* — Operating Systems, DBMS & Networks (1–3 mos)\n"
            "• *General SDE* — Universal coding drills (Immediate)\n\n"
            "💬 _Or send your custom target in one line:_\n"
            "`Company, Role, Timeline` (e.g. `Google, SDE, 2 months`)",
            actions=TARGET_PROFILE_BUTTONS,
        )
    except Exception:
        log.exception("Resume skill extraction failed for %s", phone)
        thread.post(
            "⚠️ Couldn't analyze that right now. Please try pasting your resume again!"
        )


def _onboard_target_profile(thread: Thread, phone: str, text: str, user: dict | None) -> None:
    """Consolidated Step: User picks a target pack or sends custom 1-line target.

    Extracts company, role, timeline, and track in ONE SINGLE SHOT!
    Generates prep plan and immediately starts the first drill!
    """
    profile = parse_target_profile(text)
    if not profile:
        profile = {
            "company": text.strip() or "General Tech",
            "role": "Software Engineer",
            "timeline": "1-3 Months",
            "track": "Software Development",
        }

    company = profile["company"]
    role = profile["role"]
    timeline = profile["timeline"]
    track = profile["track"]

    try:
        db.update_profile(phone, target_company=company, target_role=role)
        db.upsert_user(phone, track=track)
    except Exception:
        log.exception("Failed to save target profile for %s", phone)

    user = _safe_get_user(phone) or {}
    resume = user.get("resume_summary") or "General engineering student"

    thread.post("⚡ *Building your personalized roadmap...*")

    try:
        plan = generate_prep_plan(resume, company, role, timeline)
        first_topic = _extract_first_drill_topic(plan)
        clean_plan = _re.sub(r'\n?FIRST_DRILL_TOPIC:.*$', '', plan, flags=_re.MULTILINE).strip()

        post_chunks(thread, clean_plan)
        db.complete_onboarding(phone)

        if "month" in timeline.lower():
            db.update_difficulty(phone, 7)  # Push to medium

        thread.post(
            f"🎉 *Target Locked:* {role} @ {company}!\n\n"
            f"🎯 Launching your kickoff mock drill on *{first_topic.upper()}*...\n\n"
            "_Reply with your code or step-by-step logic to get graded._",
        )

        _start_drill(thread, phone, topic=first_topic)
    except Exception:
        log.exception("Prep plan generation failed for %s", phone)
        db.complete_onboarding(phone)
        thread.post(
            f"✅ *Target Locked:* {role} @ {company}!\n\n"
            "Starting your mock interview now:",
        )
        _start_drill(thread, phone)


def _onboard_company(thread: Thread, phone: str, text: str, user: dict | None) -> None:
    """Step 2: User selected company → save → ask role."""
    # Check button payload first
    company = parse_onboard_company(text)
    if not company:
        # User typed free text — use it as company name
        company = text.strip()

    if company.lower() == "any":
        company = "General (No Specific Company)"

    try:
        db.update_profile(phone, target_company=company)
    except Exception:
        log.exception("Failed to save target company for %s", phone)

    db.set_onboarding_step(phone, "awaiting_role")
    thread.post(
        f"✅ *Target company:* {company.capitalize()}\n\n"
        "💼 *What role are you targeting?*\n\n"
        "Tap a button or type your target role:",
        actions=ROLE_BUTTONS,
    )


def _onboard_role(thread: Thread, phone: str, text: str, user: dict | None) -> None:
    """Step 3: User selected role → save → ask timeline."""
    # Check button payload first
    role = parse_onboard_role(text)
    if not role:
        role = text.strip()

    try:
        db.update_profile(phone, target_role=role)
    except Exception:
        log.exception("Failed to save target role for %s", phone)

    db.set_onboarding_step(phone, "awaiting_timeline")
    thread.post(
        f"✅ *Target role:* {role}\n\n"
        "📅 *When is your placement season?*\n\n"
        "This helps me calibrate the intensity of your prep plan:",
        actions=TIMELINE_BUTTONS,
    )


def _onboard_timeline(thread: Thread, phone: str, text: str, user: dict | None) -> None:
    """Step 4: User selected timeline → generate full prep plan → start first drill."""
    # Check button payload first
    timeline = parse_onboard_timeline(text)
    if not timeline:
        timeline = text.strip()

    user = _safe_get_user(phone) or {}
    resume = user.get("resume_summary") or "General engineering student"
    company = user.get("target_company") or "General"
    role = user.get("target_role") or "Software Engineer"

    thread.post("⚡ *Generating your personalized prep plan...*")

    try:
        plan = generate_prep_plan(resume, company, role, timeline)

        # Extract the recommended first drill topic from the plan
        first_topic = _extract_first_drill_topic(plan)

        # Clean the FIRST_DRILL_TOPIC line from the displayed plan
        clean_plan = _re.sub(r'\n?FIRST_DRILL_TOPIC:.*$', '', plan, flags=_re.MULTILINE).strip()

        post_chunks(thread, clean_plan)

        # Complete onboarding
        db.complete_onboarding(phone)

        # Auto-set difficulty based on timeline
        if "this month" in timeline.lower():
            db.update_difficulty(phone, 7)  # Push to medium
        elif "next year" in timeline.lower():
            pass  # Keep easy

        thread.post(
            "✅ *Setup complete!* Your prep is fully personalized.\n\n"
            f"🎯 Starting your first drill on *{first_topic}* based on your weakest area...\n\n"
            "_You can always send *switch* to change topics, or *hi* to restart setup._",
        )

        # Auto-start first drill on the identified weak topic
        _start_drill(thread, phone, topic=first_topic)

    except Exception:
        log.exception("Prep plan generation failed for %s", phone)
        db.complete_onboarding(phone)
        thread.post(
            "⚠️ Couldn't generate the full plan right now, but your profile is saved!\n\n"
            "Send *drill* to start practicing — your drills will be personalized!",
            actions=MENU_BUTTONS,
        )


def _extract_first_drill_topic(plan_text: str) -> str:
    """Extract FIRST_DRILL_TOPIC from the AI-generated plan text."""
    match = _re.search(r'FIRST_DRILL_TOPIC:\s*(\S+)', plan_text, _re.IGNORECASE)
    if match:
        topic = match.group(1).strip().upper()
        valid_topics = {"DSA", "DBMS", "OS", "CN", "OOP", "SQL", "APTITUDE"}
        if topic in valid_topics:
            return topic.lower()
    return "dsa"  # Safe default


def _prompt_stale_question(thread: Thread, user: dict | None, pending_q: str, age_sec: float | None) -> None:
    """Show the stale question prompt with full error safety."""
    try:
        topic = ((user or {}).get("pending_topic") or "General").upper()
        minutes_ago = int((age_sec or 0) // 60)
        time_desc = f"{minutes_ago}m ago" if minutes_ago < 60 else f"{minutes_ago // 60}h ago"
        q_snippet = (pending_q or "").strip()
        if len(q_snippet) > 220:
            q_snippet = q_snippet[:220] + "..."
        thread.post(
            f"⏳ *You have an unanswered question from earlier ({time_desc})!*\n\n"
            f"📌 *Topic:* {topic}\n"
            f"{q_snippet}\n\n"
            f"Do you want to continue answering this, or switch your mood to prep something else?",
            actions=STALE_QUESTION_BUTTONS,
        )
    except Exception:
        log.exception("Failed to show stale question prompt")
        thread.post(
            "You have an unanswered question from earlier.\n"
            "Send *skip* to clear it, or *drill* for a new question!"
        )


def _continue_pending(thread: Thread, phone: str, user: dict | None) -> None:
    """Resume a pending question."""
    pending = (user or {}).get("pending_question")
    topic = ((user or {}).get("pending_topic") or "General").upper()
    if not pending:
        thread.post("You don't have an active question. Send *drill* to start one!")
        return
    # Refresh pending timestamp to now so they get a fresh active window
    try:
        db.set_pending(phone, pending, topic, drill_remaining=(user or {}).get("drill_remaining"))
    except Exception:
        log.exception("Failed to refresh pending_at for %s", phone)
    post_chunks(
        thread,
        f"✍️ *Resumed!*\n\n"
        f"📌 *Topic:* {topic}\n\n"
        f"{pending}\n\n"
        f"_Reply with your code, calculation, or step-by-step approach whenever you're ready!_",
        actions=DRILL_BUTTONS,
    )


def _show_summary(thread: Thread, phone: str, user: dict | None) -> None:
    """Generate and send daily summary."""
    try:
        drills_today = db.get_today_drills(phone)
        summary = generate_daily_summary(drills_today, user or {})
        post_chunks(thread, summary)
    except Exception:
        log.exception("Daily summary failed")
        thread.post("Couldn't generate your revision summary right now. Try again shortly.")


def _open_tutoring(thread: Thread, phone: str, text: str, user: dict | None) -> None:
    """Handle open-ended messages when no command or pending question applies."""
    track = (user or {}).get("track") or "General SDE"
    try:
        reply = tutor_reason_and_answer(text, active_question="", track=track)
        post_chunks(thread, reply)
        thread.post(
            "🚀 *Ready to practice?*\n"
            "Send *drill* for a 3-question live mock, or tap below to pick a topic:",
            actions=SWITCH_MOOD_BUTTONS,
        )
    except Exception:
        log.exception("Open tutoring generation failed")
        thread.post(FALLBACK_MSG)


# ── Drill lifecycle ────────────────────────────────────────────────

def _start_drill(thread: Thread, phone: str, topic: str | None = None) -> None:
    user = _safe_get_user(phone) or db.upsert_user(phone)
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
    try:
        db.set_pending(phone, question, chosen_topic, drill_remaining=2)
        db.reset_hints(phone)
    except Exception:
        log.exception("Failed to save pending question for %s", phone)

    tag = f" [🏢 {target_company.capitalize()}]" if target_company else ""
    post_chunks(
        thread,
        f"📝 *Drill started* ({track} • {difficulty.capitalize()}){tag} — 3 questions.\n\n"
        f"{question}\n\n"
        "_Reply with your code or approach. Or use the buttons below:_",
        actions=DRILL_BUTTONS,
    )


def _grade(thread: Thread, phone: str, question: str, answer: str, user: dict | None) -> None:
    user = user or {}
    track = user.get("track") or "General SDE"
    topic = user.get("pending_topic") or "general"
    try:
        feedback = evaluate_answer(question, answer, track)
    except Exception:
        log.exception("Gemini grade failed")
        thread.post("Couldn't reach the interviewer model. Try again in a few seconds.")
        return

    score = parse_score(feedback)

    try:
        db.record_attempt(phone, topic, question, answer, feedback, score)
    except Exception:
        log.exception("Failed to record attempt for %s", phone)

    remaining = int(user.get("drill_remaining") or 0)
    post_chunks(thread, feedback)

    # Adaptive difficulty
    try:
        new_diff = db.update_difficulty(phone, score)
        old_diff = user.get("difficulty") or "easy"
        if new_diff != old_diff:
            thread.post(f"💡 Difficulty updated: *{old_diff.capitalize()}* → *{new_diff.capitalize()}*")
    except Exception:
        log.exception("Difficulty update failed for %s", phone)
        new_diff = user.get("difficulty") or "easy"

    if remaining > 0:
        difficulty = new_diff
        target_company = user.get("target_company") or ""
        resume_summary = user.get("resume_summary") or ""
        try:
            if target_company:
                nxt, chosen_topic = generate_company_question(
                    target_company, track, difficulty=difficulty, resume_context=resume_summary
                )
            else:
                nxt, chosen_topic = generate_question(track, difficulty=difficulty)
            db.set_pending(phone, nxt, chosen_topic, drill_remaining=remaining - 1)
            db.reset_hints(phone)
            post_chunks(thread, f"➡️ *Question {4 - remaining}/3*\n\n{nxt}", actions=DRILL_BUTTONS)
        except Exception:
            log.exception("Next drill question generation failed")
            db.clear_pending(phone)
            thread.post(
                "Couldn't generate the next question. Your progress is saved.\n"
                "Send *drill* to start a new round!"
            )
        return

    try:
        db.set_pending(phone, None, None, drill_remaining=0)
    except Exception:
        log.exception("Failed to clear pending after drill completion")
    thread.post(
        "🔥 Session complete! Send *drill* for another round, "
        "*summary* for today's cheat sheet, or *streak* for stats."
    )


def _give_solution(thread: Thread, phone: str) -> None:
    user = _safe_get_user(phone)
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
        try:
            if target_company:
                nxt, chosen_topic = generate_company_question(
                    target_company, track, difficulty=difficulty, resume_context=resume_summary
                )
            else:
                nxt, chosen_topic = generate_question(track, difficulty=difficulty)
            db.set_pending(phone, nxt, chosen_topic, drill_remaining=remaining - 1)
            db.reset_hints(phone)
            post_chunks(thread, f"➡️ Next drill question:\n\n{nxt}", actions=DRILL_BUTTONS)
        except Exception:
            log.exception("Next question after solution failed")
            db.clear_pending(phone)
            thread.post("Couldn't generate the next question. Send *drill* to try again!")
        return
    try:
        db.set_pending(phone, None, None, drill_remaining=0)
    except Exception:
        log.exception("Failed to clear pending after solution")
    thread.post("Send *drill* when you want the next mock.")


def _skip_question(thread: Thread, phone: str) -> None:
    user = _safe_get_user(phone)
    if not user or not user.get("pending_question"):
        thread.post("No active question to skip. Send *drill* to start one!")
        return
    db.clear_pending(phone)
    thread.post(
        "⏭ *Question skipped!* No score deduction.\n\n"
        "Send *drill* for a fresh question, or tap below to switch mood:",
        actions=SWITCH_MOOD_BUTTONS,
    )


# ── Hint system ────────────────────────────────────────────────────

def _give_hint(thread: Thread, phone: str) -> None:
    user = _safe_get_user(phone)
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
    try:
        new_count = db.increment_hints(phone)
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
    try:
        topics = db.topic_stats(phone)
    except Exception:
        log.exception("Topic stats query failed")
        thread.post("Couldn't load topic stats. Try again!")
        return
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
    user = _safe_get_user(phone) or db.upsert_user(phone)
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
    try:
        rows = db.leaderboard()
    except Exception:
        log.exception("Leaderboard query failed")
        thread.post("Couldn't load the leaderboard. Try again!")
        return
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
        try:
            s = db.stats(phone)
            lines.append(f"\n\u2014\n\U0001f464 *You:* {s['accuracy']}% acc \u2022 {s['solved']} Qs")
        except Exception:
            pass
    thread.post("\n".join(lines))


def _streak_card(phone: str) -> str:
    try:
        s = db.stats(phone)
        user = _safe_get_user(phone) or {}
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
    except Exception:
        log.exception("Streak card generation failed")
        return "Couldn't load your stats right now. Try *streak* again!"


# ── Sender extraction (robust, crash-proof) ────────────────────────

def _parse_sender(msg: Message) -> tuple[str, str]:
    """Extract (phone/address, display_name) from a Caspian message.

    Handles both dict-style and string-style sender payloads.
    Guaranteed to never raise — returns ("", "") in worst case.
    """
    try:
        sender = getattr(msg, "sender", None)
        addr, name = "", ""

        if isinstance(sender, dict):
            addr = str(sender.get("address") or "")
            name = str(sender.get("name") or "")
        elif sender:
            s = str(sender).strip()
            if s.startswith("{") and "address" in s:
                # Try ast.literal_eval for dict-like string
                try:
                    import ast
                    d = ast.literal_eval(s)
                    if isinstance(d, dict):
                        addr = str(d.get("address") or "")
                        name = str(d.get("name") or "")
                except Exception:
                    pass
                # Fallback: regex extraction
                if not addr:
                    import re
                    m_addr = re.search(r"['\"]address['\"]\s*:\s*['\"]([^'\"]+)['\"]", s)
                    m_name = re.search(r"['\"]name['\"]\s*:\s*['\"]([^'\"]+)['\"]", s)
                    addr = m_addr.group(1) if m_addr else ""
                    name = m_name.group(1) if m_name else ""
            else:
                addr = s

        # Fallback: use thread_id
        if not addr:
            tid = str(getattr(msg, "thread_id", "") or "")
            if tid:
                addr = tid.split(":", 1)[-1]

        # Try to extract name from raw contacts (WhatsApp)
        if not name:
            try:
                raw = getattr(msg, "raw", None)
                if isinstance(raw, dict):
                    contacts = raw.get("contacts") or []
                    if contacts and isinstance(contacts[0], dict):
                        profile = contacts[0].get("profile") or {}
                        name = str(profile.get("name") or "")
            except Exception:
                pass

        return addr.strip(), name.strip()
    except Exception:
        log.exception("_parse_sender crashed")
        # Last resort: try thread_id
        try:
            tid = str(getattr(msg, "thread_id", "") or "")
            return tid.split(":", 1)[-1], ""
        except Exception:
            return "", ""


def _phone(msg: Message) -> str:
    addr, _ = _parse_sender(msg)
    return addr


def _name(msg: Message) -> str:
    _, name = _parse_sender(msg)
    return name
