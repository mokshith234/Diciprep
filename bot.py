"""Caspian event handlers for PlacementPrep AI (WhatsApp + Telegram)."""

from __future__ import annotations

import logging
import traceback

from caspian import Button, Caspian, HandlerContext, Message, Thread

import json
import os
import re as _re

import db
from commands import (
    is_followup,
    is_asking_question_or_clarification,
    looks_like_answer,
    parse_command,
    parse_company_command,
    parse_fix_command,
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
    generate_readiness_report,
    parse_score,
    render_readiness_bar,
    score_and_analyze_resume,
    show_solution,
    tutor_reason_and_answer,
)
from outbound import post_chunks

log = logging.getLogger("placementprep.bot")

# ── Button Constructor (WhatsApp 20-char safety) ───────────────────

def make_button(label: str, data: str) -> Button:
    """Create Button strictly respecting WhatsApp's 20-character title limit."""
    clean = str(label or "").strip()
    if len(clean) > 20:
        clean = clean[:20].strip()
    return Button(label=clean, data=str(data))


# ── Onboarding buttons ─────────────────────────────────────────────

ONBOARDING_BUTTONS = (
    make_button("📄 AI Resume Score", "onboard:ai"),
    make_button("📈 Prep Scorecard", "cmd:readiness"),
    make_button("⚡ Instant Mock Drill", "cmd:drill"),
)

TRACK_BUTTONS = (
    make_button("💻 SDE Track", "track:sde"),
    make_button("📊 Data Science", "track:ds"),
    make_button("⚙️ Core CS", "track:core"),
)

TARGET_PROFILE_BUTTONS = (
    make_button("🏢 Tier-1 FAANG SDE", "tp:faang"),
    make_button("📦 Amazon Backend", "tp:amazon"),
    make_button("🪟 Microsoft Full", "tp:microsoft"),
    make_button("💼 TCS Mass Tech", "tp:tcs"),
    make_button("📊 Data Science & AI", "tp:ds"),
    make_button("⚙️ Core CS Systems", "tp:core"),
    make_button("⚡ General SDE Drill", "tp:general"),
)

COMPANY_BUTTONS = (
    make_button("🔍 Google", "obc:google"),
    make_button("📦 Amazon", "obc:amazon"),
    make_button("🪟 Microsoft", "obc:microsoft"),
    make_button("🏢 TCS", "obc:tcs"),
    make_button("💼 Infosys", "obc:infosys"),
    make_button("🎯 Other / Skip", "obc:any"),
)

ROLE_BUTTONS = (
    make_button("💻 SDE / Backend", "obr:SDE"),
    make_button("🌐 Fullstack / Web", "obr:Frontend"),
    make_button("📊 Data Scientist", "obr:Data Scientist"),
    make_button("⚙️ DevOps / Cloud", "obr:DevOps"),
    make_button("🔐 Security / Core", "obr:Core Engineer"),
    make_button("🎯 Other / Skip", "obr:Software Engineer"),
)

TIMELINE_BUTTONS = (
    make_button("🔥 This Month", "obt:This Month"),
    make_button("📅 1–3 Months", "obt:1-3 Months"),
    make_button("📆 3–6 Months", "obt:3-6 Months"),
    make_button("🗓️ Next Year", "obt:Next Year"),
)

DRILL_BUTTONS = (
    make_button("💡 Hint", "cmd:hint"),
    make_button("📖 Solution", "cmd:solution"),
    make_button("⏭ Skip", "cmd:skip"),
    make_button("🔄 Switch Mood", "cmd:switch_mood"),
)

STALE_QUESTION_BUTTONS = (
    make_button("✍️ Answer It", "cmd:continue_pending"),
    make_button("🔄 Switch Mood", "cmd:switch_mood"),
    make_button("📖 Solution", "cmd:solution"),
    make_button("⏭ Skip", "cmd:skip"),
)

SWITCH_MOOD_BUTTONS = (
    make_button("💻 DSA Drill", "drill dsa"),
    make_button("⚙️ OS Drill", "drill os"),
    make_button("🗄️ DBMS Drill", "drill dbms"),
    make_button("🌐 CN Drill", "drill cn"),
    make_button("🏢 Company Mock", "cmd:menu"),
)

MENU_BUTTONS = (
    make_button("🎯 3-Question Mock", "cmd:drill"),
    make_button("📈 Prep Scorecard", "cmd:readiness"),
    make_button("📄 Scan Resume", "onboard:ai"),
    make_button("📝 Feedback Form", "cmd:open_feedback"),
    make_button("🔄 Switch Mood", "cmd:switch_mood"),
)

READINESS_BUTTONS = (
    make_button("⚡ 3-Question Mock", "cmd:drill"),
    make_button("📄 Scan Resume", "onboard:ai"),
    make_button("📑 Daily Revision", "cmd:summary"),
    make_button("🔄 Switch Topic", "cmd:switch_mood"),
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
    "• *score* — Real-time placement readiness score & gap analysis\n"
    "• *fix <topic>* — Drill your chosen weakness gap (e.g. `fix os`, `fix dsa`)\n"
    "• *drill* — Start a 3-question adaptive mock interview\n"
    "• *drill <topic>* — Practice a specific topic (e.g. `drill os`, `drill dsa`, `drill dbms`)\n"
    "• *company <name>* — Target a company (e.g. `company amazon`, `company google`)\n"
    "• *role <name>* — Target your dream role (e.g. `role SDE 1`, `role Backend`)\n"
    "• *resume: <text>* — Score resume, find vulnerabilities, and get fix options\n"
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
    "• *score* — View your placement readiness score & diagnostic\n"
    "• *drill* — Start a 3-question adaptive mock interview\n"
    "• *drill <topic>* — Practice a specific topic (e.g. `drill os`, `drill dsa`)\n"
    "• *company <name>* — Target a company (e.g. `company amazon`)\n"
    "• *resume: <text>* — Score resume and get 1-click weakness fixes\n"
    "• *summary* — Daily revision cheat sheet\n"
    "• *streak* — View your active daily streak and stats\n\n"
    "Send *drill* to start practicing!"
)

MAX_HINTS = 2


# Patch GatewayEventParser._normalise and _action to safely parse Telegram and WhatsApp callback query data,
# preserve interaction_id for instant ack, and retain raw payload.
# CRITICAL CASPIAN FIX: Caspian gateway sends interaction.received events with
# payload directly in `data` (with fields `value`, `conversation_id`, `sender`), NOT nested under `data.interaction`.
# Standard Caspian SDK drops these events because `data.get("interaction")` is None.
try:
    from caspian.hosted.inbound import GatewayEventParser
    from caspian.core.types import Action

    _orig_gateway_normalise = GatewayEventParser._normalise
    _orig_gateway_action = GatewayEventParser._action

    def _robust_gateway_normalise(self, obj: dict) -> dict:
        raw_type = str(obj.get("type", ""))
        data = obj.get("data")
        if raw_type == "interaction.received" and isinstance(data, dict):
            inner = dict(data.get("interaction") or data.get("message") or data)
            if "value" in inner and "data" not in inner:
                inner["data"] = inner["value"]
            channel = str(inner.get("channel") or data.get("channel") or "telegram")
            conv_id = str(inner.get("conversation_id") or data.get("conversation_id") or "")
            inner["channel"] = channel
            inner["conversation_id"] = conv_id
            return {
                "type": "action",
                "channel": channel,
                "conversation_id": conv_id,
                "action": inner,
            }
        return _orig_gateway_normalise(self, obj)

    def _robust_gateway_action(self, thread_id, a):
        if not isinstance(a, dict):
            return _orig_gateway_action(self, thread_id, a)
        data = str(
            a.get("data")
            or a.get("callback_data")
            or a.get("payload")
            or a.get("value")
            or a.get("text")
            or ""
        )
        interaction_id = str(
            a.get("id")
            or a.get("interaction_id")
            or a.get("callback_query_id")
            or ""
        )
        raw_sender = a.get("sender")
        raw_from = a.get("from") or {}
        from_id = raw_from.get("id") if isinstance(raw_from, dict) else raw_from
        if isinstance(raw_sender, dict):
            sender = str(raw_sender.get("address") or from_id or json.dumps(raw_sender))
        elif raw_sender:
            sender = str(raw_sender)
        elif from_id:
            sender = str(from_id)
        else:
            sender = ""
        message_id = str(a.get("message_id") or "")
        return [
            Action(
                thread_id=thread_id,
                data=data,
                sender=sender,
                message_id=message_id,
                interaction_id=interaction_id,
                raw=a,
            )
        ]

    GatewayEventParser._normalise = _robust_gateway_normalise
    GatewayEventParser._action = _robust_gateway_action
except Exception as _patch_err:
    log.warning("Failed to patch GatewayEventParser: %s", _patch_err)



def register(cx: Caspian) -> None:
    """Register channel-agnostic handlers so both WhatsApp and Telegram work."""

    @cx.on_action({"overlap": "parallel"})
    def on_action(thread: Thread, msg: Any, ctx: HandlerContext) -> None:
        # Instantly acknowledge Telegram callback query to clear button loading spinner
        raw = getattr(msg, "raw", None)
        cb_id = (
            getattr(msg, "interaction_id", None)
            or (raw.get("id") if isinstance(raw, dict) else None)
            or (raw.get("callback_query_id") if isinstance(raw, dict) else None)
        )
        if cb_id:
            import threading
            from outbound import answer_telegram_callback
            threading.Thread(target=answer_telegram_callback, args=(str(cb_id),), daemon=True).start()

        # Capture phone / Telegram chat ID
        phone = _phone(msg)
        if not phone and isinstance(raw, dict):
            raw_from = raw.get("from") or {}
            phone = str(raw_from.get("id") or raw.get("sender") or raw.get("chat_id") or "")
        if not phone:
            phone = db.get_latest_telegram_user() or ""

        # Attach real recipient chat ID to thread object for outbound replies
        thread.chat_id = phone

        # Capture Caspian conversation ID if present in event payload
        conv_id = (
            (raw.get("conversation_id") if isinstance(raw, dict) else None)
            or getattr(msg, "conversation_id", None)
            or (str(getattr(thread, "thread_id", "")).split(":", 1)[-1] if str(getattr(thread, "thread_id", "")).startswith("conv_") else None)
        )
        if conv_id and phone:
            db.save_caspian_conv_id(phone, str(conv_id))

        data = (
            getattr(msg, "data", None)
            or getattr(ctx, "data", None)
            or getattr(msg, "text", None)
            or ""
        )
        if not data and hasattr(msg, "raw") and isinstance(msg.raw, dict):
            data = str(
                msg.raw.get("data")
                or msg.raw.get("callback_data")
                or msg.raw.get("payload")
                or msg.raw.get("value")
                or msg.raw.get("text")
                or ""
            )
        data = str(data).strip()
        channel = "telegram" if str(getattr(msg, "thread_id", "")).startswith("telegram:") or not os.environ.get("WHATSAPP_ACCESS_TOKEN") else "whatsapp"
        log.info("Action button tapped: data=%r from %s on %s", data, phone, channel)
        if not data:
            return

        # Log inbound button click for hackathon telemetry
        db.log_message(channel, "inbound", phone, data, msg_type="button_click")
        handle_text(thread, msg, data)

    @cx.on_message({"overlap": "parallel"})
    def on_message(thread: Thread, msg: Message, ctx: HandlerContext) -> None:
        text = (msg.text or "").strip()
        if not text:
            return
        phone = _phone(msg)
        if not phone:
            raw = getattr(msg, "raw", None)
            if isinstance(raw, dict):
                phone = str(raw.get("from", {}).get("id") or raw.get("sender") or "")
        if not phone:
            phone = db.get_latest_telegram_user() or ""

        # Attach real recipient chat ID to thread object for outbound replies
        thread.chat_id = phone
        channel = "telegram" if str(getattr(msg, "thread_id", "")).startswith("telegram:") or not os.environ.get("WHATSAPP_ACCESS_TOKEN") else "whatsapp"

        # Capture Caspian conversation ID if present
        raw = getattr(msg, "raw", None)
        conv_id = (
            (raw.get("conversation_id") if isinstance(raw, dict) else None)
            or getattr(msg, "conversation_id", None)
            or (str(getattr(thread, "thread_id", "")).split(":", 1)[-1] if str(getattr(thread, "thread_id", "")).startswith("conv_") else None)
        )
        if conv_id and phone:
            db.save_caspian_conv_id(phone, str(conv_id))

        # Log inbound user message for hackathon telemetry
        db.log_message(channel, "inbound", phone, text, msg_type="text")
        handle_text(thread, msg, text)


# Map Thread.post and Thread.send across Caspian SDK:
# 1. Telegram outbound messages route directly to Telegram Bot API with verified chat_id
#    for 100% reliable, zero-latency user experience with working native buttons.
# 2. Concurrently logs every message to the database for hackathon judges & telemetry API.
# 3. No testing or duplicate messages are ever dispatched to live users.
_caspian_thread_send = Thread.send

def _unified_thread_post(self: Thread, text: str, *, actions: tuple[Any, ...] = ()) -> None:
    tid = str(getattr(self, "thread_id", ""))
    is_tg = (
        tid.startswith("telegram:")
        or bool(os.environ.get("TELEGRAM_BOT_TOKEN") and not os.environ.get("WHATSAPP_ACCESS_TOKEN"))
    )
    channel = "telegram" if is_tg else "whatsapp"

    # Robust recipient chat ID extraction:
    # 1. thread.chat_id (explicitly set on incoming event)
    # 2. thread.recipient
    # 3. Reverse lookup from conv_id in caspian_conversations
    # 4. Fallback to latest registered telegram user
    # 5. Extract from thread_id string
    chat_id = getattr(self, "chat_id", None) or getattr(self, "recipient", None)
    if not chat_id:
        chat_id = tid.split(":", 1)[-1] if ":" in tid else tid
    if str(chat_id).startswith("conv_"):
        mapped = db.get_sender_for_conv(str(chat_id))
        if mapped:
            chat_id = mapped
        else:
            latest = db.get_latest_telegram_user()
            if latest:
                chat_id = latest

    msg_type = "button_response" if actions else "text"

    # 1. Log outbound message to database for hackathon judges & telemetry API
    db.log_message(channel, "outbound", str(chat_id), text, msg_type=msg_type)

    # 2. Direct Telegram send for 100% reliable delivery and native buttons
    if is_tg:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if token and chat_id and not str(chat_id).startswith("conv_"):
            try:
                from outbound import send_telegram
                send_telegram(str(chat_id), text, actions=actions)
                return
            except Exception:
                log.exception("send_telegram failed for %s", chat_id)
    _caspian_thread_send(self, text, actions=actions)

Thread.post = _unified_thread_post
Thread.send = _unified_thread_post


def handle_text(thread: Thread, msg: Message, text: str) -> None:
    """Central dispatcher for all incoming messages.

    CRITICAL: This is wrapped in a top-level try/except so that
    no message is ever silently lost.  Any unhandled exception will
    send a friendly error reply instead of leaving the user staring
    at a clock symbol.
    """
    phone = _phone(msg)
    if phone and (
        str(getattr(msg, "thread_id", "")).startswith("telegram:")
        or str(getattr(thread, "thread_id", "")).startswith("telegram:")
    ):
        import threading
        from outbound import send_telegram_typing
        threading.Thread(target=send_telegram_typing, args=(phone,), daemon=True).start()

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
            "👇 *Or tap a button below to instantly analyze a sample profile:*",
            actions=(
                make_button("📋 Analyze Sample SDE", "sample_resume:sde"),
                make_button("📊 Analyze Sample DS", "sample_resume:ds"),
                make_button("⚙️ Analyze Sample Core CS", "sample_resume:core"),
                make_button("❌ Cancel / Menu", "cmd:menu"),
            ),
        )
        return

    # ── 1-Click Sample Resume Evaluation ──
    if text.strip().lower().startswith("sample_resume:"):
        db.set_onboarding_step(phone, None)
        profile_type = text.split(":", 1)[-1].strip().lower()
        if profile_type == "ds":
            sample_text = (
                "Final year Data Science student. Proficient in Python, SQL, Pandas, NumPy, Scikit-Learn, "
                "and exploratory data analysis. Built machine learning models for customer churn prediction "
                "and sentiment analysis using NLP. Familiar with statistical hypothesis testing, regression, and PowerBI. "
                "Targeting Data Analyst / Junior ML Engineer roles."
            )
            role = "Data Scientist"
        elif profile_type == "core":
            sample_text = (
                "Computer Science undergraduate. Strong in C, C++, Operating Systems (Processes, Threads, Deadlocks, Virtual Memory), "
                "DBMS (SQL, Indexing, Transactions, Normalization), and Computer Networks (TCP/IP, OSI, Routing, Sockets). "
                "Built a multi-threaded web server in C++. Targeting Core Systems & Infrastructure roles."
            )
            role = "Systems Engineer"
        else:
            sample_text = (
                "Pre-final year B.Tech CSE. Strong in Java, C++, Python, Data Structures & Algorithms, "
                "Object-Oriented Programming, and DBMS. Built a Fullstack MERN e-commerce application "
                "with Redis caching and JWT authentication. Experienced with Git, Docker, and REST APIs. "
                "Targeting SDE-1 backend roles at top product companies."
            )
            role = "Software Development Engineer"

        thread.post(f"📋 *Analyzing Sample {profile_type.upper()} Profile:*\n_{sample_text}_\n")
        _onboard_resume(thread, phone, sample_text, target_role=role)
        return

    # ── Quick target profile pack selection (anytime button tap) ──
    if text.strip().lower().startswith("tp:"):
        db.set_onboarding_step(phone, None)
        _onboard_target_profile(thread, phone, text, user)
        return

    # ── Immediate Weakness Fix Action (1-click from resume audit or scorecard) ──
    fix_topic = parse_fix_command(text)
    if fix_topic:
        db.set_onboarding_step(phone, None)
        _handle_fix_topic(thread, phone, fix_topic, user)
        return

    # ── Cancel onboarding if user sends any explicit command or action button ──
    cmd_check = parse_command(text)
    if cmd_check or text.startswith(("cmd:", "track:", "onboard:", "tp:", "fix:", "sample_resume:", "/")):
        if (user or {}).get("onboarding_step"):
            db.set_onboarding_step(phone, None)
            if user:
                user["onboarding_step"] = None

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
                "📄 *AI Resume Scoring & Skill Gap Diagnostic*\n\n"
                "Send your resume text, skills, or projects like this:\n"
                "`resume: 3rd year CSE, built fullstack app with React/Node/Redis, skilled in Java, DSA, OS, DBMS.`\n\n"
                "I will evaluate your absolute score (0-100), spot interview vulnerabilities ('The Grill List'), "
                "and provide 1-click weakness repair buttons!"
            )
            return
        thread.post("🔍 *Running deep resume scoring and interview vulnerability scan...* ⏳")
        try:
            target_role = (user or {}).get("target_role") or "Software Development Engineer"
            analysis = score_and_analyze_resume(res_content, target_role=target_role)
            score = analysis.get("score", 65)
            recommended_track = analysis.get("recommended_track") or "Software Development"
            fix_options = analysis.get("fix_options") or ["DSA", "System Design", "Core CS"]
            primary_fix = fix_options[0] if fix_options else "DSA"

            db.set_resume_analysis(
                phone,
                resume_score=score,
                skills_summary=json.dumps(analysis),
                resume_summary=res_content[:1000],
            )
            db.set_focus_area(phone, primary_fix)
            db.upsert_user(phone, track=recommended_track)

            fix_buttons = []
            for opt in fix_options[:3]:
                fix_buttons.append(make_button(f"🛠️ Fix: {opt[:11]}", f"fix:{opt}"))
            fix_buttons.append(make_button("⚡ 3-Question Mock", "cmd:drill"))

            post_chunks(thread, analysis["message"], actions=tuple(fix_buttons))
            thread.post(
                "✅ *Profile & Diagnostics Saved!*\n\n"
                "Tap any *[🛠️ Fix: Topic]* button above to target your weakest technical area, "
                "or send *drill* to start a full mock round."
            )
        except Exception:
            log.exception("Resume deep scoring failed")
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
    if cmd == "readiness":
        _show_readiness_scorecard(thread, phone)
        return
    if cmd == "judge":
        _show_judge_report(thread, phone)
        return
    if cmd == "summary":
        _show_summary(thread, phone, user)
        return
    if cmd == "feedback":
        thread.post(
            "📝 *We Value Your Feedback!* 🎓\n\n"
            "Help us make PlacementPrep AI smoother and more effective for your placements.\n"
            "It takes less than 2 minutes to fill out:\n\n"
            "👉 [Tap here to open Feedback Form](https://docs.google.com/forms/d/e/1FAIpQLSc8njVZKFo_9iivLLoDIjiOykw5Dql_KDdp3up4fHcstXdC-w/viewform)\n\n"
            "Thank you for supporting our project! 🙏✨",
            actions=(
                make_button("📝 Open Feedback Form", "cmd:open_feedback"),
                make_button("🎓 Main Menu", "cmd:menu"),
            ),
        )
        return
    # "resume" command without content — show instructions & sample buttons
    if cmd == "resume":
        db.set_onboarding_step(phone, "awaiting_resume")
        thread.post(
            "📄 *AI Resume Scoring & Skill Gap Diagnostic*\n\n"
            "Drop your resume text, skills, or projects like this:\n"
            "`resume: 3rd year CSE, built fullstack app with React/Node/Redis, skilled in Java, DSA, OS, DBMS.`\n\n"
            "I will evaluate your absolute score (0-100), spot interview vulnerabilities ('The Grill List'), "
            "and provide 1-click weakness repair buttons!\n\n"
            "👇 *Or tap a button below to instantly analyze a sample profile:*",
            actions=(
                make_button("📋 Analyze Sample SDE", "sample_resume:sde"),
                make_button("📊 Analyze Sample DS", "sample_resume:ds"),
                make_button("⚙️ Analyze Sample Core CS", "sample_resume:core"),
                make_button("❌ Cancel / Menu", "cmd:menu"),
            ),
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


def _make_mock_msg(phone: str, thread: Thread, text_val: str) -> Any:
    from types import SimpleNamespace
    return SimpleNamespace(
        sender=phone,
        thread_id=getattr(thread, "thread_id", f"telegram:{phone}"),
        text=text_val,
        raw={},
    )


# ── Onboarding state machine ──────────────────────────────────────

def _handle_onboarding(thread: Thread, phone: str, text: str, user: dict | None, step: str) -> None:
    """Multi-step AI-guided onboarding flow.

    Steps: awaiting_resume → awaiting_company → awaiting_role → awaiting_timeline → done
    """
    # Allow ANY explicit command or button payload to break out of onboarding
    cmd = parse_command(text)
    if cmd or text.startswith(("cmd:", "track:", "onboard:", "tp:", "fix:", "sample_resume:", "/")):
        db.set_onboarding_step(phone, None)
        _handle_text_inner(thread, _make_mock_msg(phone, thread, text), text)
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


def _onboard_resume(thread: Thread, phone: str, text: str, target_role: str | None = None) -> None:
    """Flagship Feature: Deep Resume Diagnostic, Absolute Scoring, Skill Gap Analysis & 1-Click Fix Options."""
    clean = text.strip()
    cmd = parse_command(clean)
    if cmd or clean.startswith(("cmd:", "track:", "onboard:", "tp:", "fix:", "sample_resume:", "/")):
        db.set_onboarding_step(phone, None)
        _handle_text_inner(thread, _make_mock_msg(phone, thread, clean), clean)
        return

    if len(clean) < 10:
        thread.post(
            "📝 *AI Resume & Skill Gap Scanner*\n\n"
            "Drop your resume text, skills list, or project summary right here! 📄✨\n\n"
            "👇 *Or tap a button below to instantly test a sample candidate profile:*",
            actions=(
                make_button("📋 Analyze Sample SDE", "sample_resume:sde"),
                make_button("📊 Analyze Sample DS", "sample_resume:ds"),
                make_button("⚙️ Analyze Sample Core CS", "sample_resume:core"),
                make_button("❌ Cancel / Menu", "cmd:menu"),
            ),
        )
        return

    db.set_onboarding_step(phone, None)
    thread.post("🔍 *Running deep resume scoring and interview vulnerability scan...* ⏳")

    try:
        user = _safe_get_user(phone) or {}
        role = target_role or user.get("target_role") or "Software Engineer"
        analysis = score_and_analyze_resume(text, target_role=role)

        # Persist score and summary
        score = analysis.get("score", 65)
        recommended_track = analysis.get("recommended_track") or "Software Development"
        fix_options = analysis.get("fix_options") or ["DSA", "System Design", "Core CS"]
        primary_fix = fix_options[0] if fix_options else "DSA"

        db.set_resume_analysis(
            phone,
            resume_score=score,
            skills_summary=json.dumps(analysis),
            resume_summary=text[:1000],
        )
        db.set_focus_area(phone, primary_fix)
        db.upsert_user(phone, track=recommended_track)

        # Format 1-click fix buttons directly from the AI's diagnostic!
        fix_buttons = []
        for opt in fix_options[:3]:
            fix_buttons.append(make_button(f"🛠️ Fix: {opt[:11]}", f"fix:{opt}"))
        fix_buttons.append(make_button("🎯 Set Target Pack", "tp:general"))

        # Deliver the flagship audit card with the fix buttons
        post_chunks(thread, analysis["message"], actions=tuple(fix_buttons))

        # Clear onboarding step so user is never locked in
        db.set_onboarding_step(phone, None)
        thread.post(
            "🎯 *NEXT STEP: PICK WHICH WEAKNESS TO REPAIR FIRST*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Tap any *[🛠️ Fix: Topic]* button above to immediately begin targeted interview drills on that weakness.\n\n"
            "Or pick a target company pack below to calibrate your mock bar:",
            actions=TARGET_PROFILE_BUTTONS,
        )
    except Exception:
        log.exception("Resume deep scoring failed for %s", phone)
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

def _handle_fix_topic(thread: Thread, phone: str, topic: str, user: dict | None) -> None:
    """1-Click Weakness Fix: Locks focus area, updates profile, launches adaptive drill."""
    clean_topic = topic.strip()
    if clean_topic.lower() == "active":
        user = user or db.get_user(phone) or {}
        clean_topic = user.get("active_focus_area") or "DSA"

    try:
        db.set_focus_area(phone, clean_topic)
        db.clear_pending(phone)
        db.set_onboarding_step(phone, None)
    except Exception:
        log.exception("Failed to set focus area for %s", phone)

    thread.post(
        f"🛠️ *Priority Weakness Targeted: {clean_topic.upper()}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "I've calibrated your placement profile to target this specific vulnerability.\n"
        "Launching an adaptive diagnostic question to test your depth...\n\n"
        "_Reply with your technical explanation, architecture, or code._"
    )
    _start_drill(thread, phone, topic=clean_topic)


def _show_readiness_scorecard(thread: Thread, phone: str) -> None:
    """Display real-time placement readiness score, ASCII gauge, and action options."""
    profile = db.get_readiness_profile(phone)
    report = generate_readiness_report(profile)

    actions = []
    active_focus = profile.get("active_focus_area")
    if active_focus:
        actions.append(make_button(f"🛠️ Fix: {active_focus[:11]}", f"fix:{active_focus}"))
    actions.extend([
        make_button("⚡ 3-Question Mock", "cmd:drill"),
        make_button("📄 Scan Resume", "onboard:ai"),
        make_button("📑 Daily Revision", "cmd:summary"),
    ])

    post_chunks(thread, report, actions=tuple(actions[:4]))


def _show_judge_report(thread: Thread, phone: str) -> None:
    """Display comprehensive hackathon message telemetry and API endpoints for judges."""
    st = db.get_message_stats()
    caspian_conv_count = 0
    caspian_msg_count = 0
    caspian_status = "Connected 🟢"
    try:
        from app import cx
        from caspian.hosted.client import GatewayRequest

        if hasattr(cx, "_gateway_client") and cx._gateway_client:
            r = cx._gateway_client.send(GatewayRequest(method="GET", path="/v1/conversations"))
            if r.is_ok and r.value.json_list:
                caspian_conv_count = len(r.value.json_list)
                for c in r.value.json_list:
                    cid = c.get("id")
                    if cid:
                        mr = cx._gateway_client.send(
                            GatewayRequest(method="GET", path=f"/v1/conversations/{cid}/messages")
                        )
                        if mr.is_ok and mr.value.json_list:
                            caspian_msg_count += len(mr.value.json_list)
    except Exception:
        caspian_status = "Syncing 🟡"

    report = (
        "⚖️ *CASPIAN HACKATHON — MESSAGE AUDIT & TELEMETRY*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 *Message Volume:*\n"
        f"• Total Tracked Messages: *{st['total_messages']}*\n"
        f"• Inbound User Inputs: *{st['inbound_messages']}*\n"
        f"• Outbound Agent Responses: *{st['outbound_messages']}*\n"
        f"• Button Clicks / Interactions: *{st['button_clicks']}*\n"
        f"• Total Mock Drills Conducted: *{st['drills_count']}*\n"
        f"• Active Candidates Prepared: *{st['users_count']}*\n\n"
        "⚡ *Caspian Gateway Synchronization:*\n"
        f"• Status: *{caspian_status}*\n"
        f"• Active Caspian Conversations: *{caspian_conv_count}*\n"
        f"• Messages on Caspian Gateway API: *{caspian_msg_count}*\n\n"
        "🌐 *Judge REST API Endpoints:*\n"
        "• `GET /api/stats` — Full JSON metrics\n"
        "• `GET /api/messages/count` — Fast count for scripts\n"
        "• `GET /api/messages?limit=50` — Full message stream\n"
        "• `GET /api/caspian/stats` — Direct Caspian Gateway API count\n"
        "• `GET /health` — Service health check\n\n"
        "✅ _Dual dispatch active: Native Telegram delivery + Caspian Gateway API sync._"
    )
    thread.post(report)


def _start_drill(thread: Thread, phone: str, topic: str | None = None) -> None:
    user = _safe_get_user(phone) or db.upsert_user(phone)
    track = user.get("track") or "General SDE"
    difficulty = user.get("difficulty") or "easy"
    target_company = user.get("target_company") or ""
    resume_summary = user.get("resume_summary") or ""
    if not topic and user.get("active_focus_area"):
        topic = user.get("active_focus_area")
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
        db.log_drill_started(phone, chosen_topic, question)
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

    # Dynamic placement readiness score bump
    try:
        delta = 2 if score >= 8 else (1 if score >= 5 else 0)
        new_readiness = db.update_readiness_score(phone, delta)
    except Exception:
        log.exception("Readiness score bump failed for %s", phone)
        new_readiness = int((user or {}).get("readiness_score") or 65)

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
            db.log_drill_started(phone, chosen_topic, nxt)
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

    readiness_bar = render_readiness_bar(new_readiness)
    active_focus = (user or {}).get("active_focus_area") or topic
    thread.post(
        f"🔥 *Mock Session Complete!*\n\n"
        f"📈 *Placement Readiness:* {readiness_bar}\n"
        f"• Last Question Score: *{score}/10*\n"
        f"• Active Focus Area: *{active_focus}*\n\n"
        "Tap *Placement Scorecard* for your full diagnostic, or *3-Question Mock* to keep climbing!",
        actions=(
            make_button("📈 Prep Scorecard", "cmd:readiness"),
            make_button(f"🛠️ Fix: {active_focus[:11]}", f"fix:{active_focus}"),
            make_button("⚡ 3-Question Mock", "cmd:drill"),
            make_button("📑 Daily Revision", "cmd:summary"),
        ),
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
    try:
        db.record_solution_revealed(phone, pending, body, (user or {}).get("pending_topic") or track)
    except Exception:
        log.exception("Failed to record solution revealed for %s", phone)

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
            db.log_drill_started(phone, chosen_topic, nxt)
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
    pending = user.get("pending_question")
    try:
        db.record_drill_skipped(phone, pending)
    except Exception:
        log.exception("Failed to record drill skipped for %s", phone)
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
        readiness = int(user.get("readiness_score") or 65)
        bar = render_readiness_bar(readiness)
        focus = user.get("active_focus_area") or "DSA"
        return (
            "📊 *Your PlacementPrep Performance Profile*\n\n"
            f"📈 Placement Readiness: *{bar}*\n"
            f"🎯 Active Focus Area: *{focus}*\n"
            f"🔥 Streak: *{s['streak']}* day(s)\n"
            f"✅ Questions solved: *{s['solved']}*\n"
            f"🎯 Accuracy (score ≥ 7): *{s['accuracy']}%*\n"
            f"📚 Track: *{s['track']}*\n"
            f"💪 Level: *{difficulty}*\n\n"
            "Keep the chain alive — morning capsule drops at 8:00 AM."
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
