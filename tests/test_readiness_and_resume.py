"""Tests for Flagship Resume Scoring, Vulnerability Analysis, and Readiness Scorecard."""

import pytest
import db
from commands import parse_command, parse_fix_command
from llm import render_readiness_bar, generate_readiness_report


def test_render_readiness_bar():
    assert "■" in render_readiness_bar(75)
    assert "75%" in render_readiness_bar(75)
    assert "100%" in render_readiness_bar(105)
    assert "0%" in render_readiness_bar(-10)


def test_db_readiness_and_focus_flow():
    test_phone = "+18888888888"
    db.upsert_user(test_phone, name="Test Dev", track="Software Development")
    db.set_resume_analysis(
        test_phone,
        resume_score=72,
        skills_summary='{"strengths": ["Python"], "grill_list": ["OS"], "fix_options": ["Operating Systems"]}',
        resume_summary="Fullstack dev with React and Python",
    )
    db.set_focus_area(test_phone, "Operating Systems")

    profile = db.get_readiness_profile(test_phone)
    assert profile["resume_score"] == 72
    assert profile["readiness_score"] == 72
    assert profile["active_focus_area"] == "Operating Systems"

    # Score update
    new_score = db.update_readiness_score(test_phone, delta=4)
    assert new_score == 76
    updated_profile = db.get_readiness_profile(test_phone)
    assert updated_profile["readiness_score"] == 76


def test_parse_fix_command():
    assert parse_fix_command("fix:Operating Systems") == "Operating Systems"
    assert parse_fix_command("fix: System Design") == "System Design"
    assert parse_fix_command("fix dsa") == "dsa"
    assert parse_fix_command("/fix dbms") == "dbms"
    assert parse_fix_command("cmd:fix:sql") == "sql"
    assert parse_fix_command("hello world") is None


def test_parse_readiness_commands():
    assert parse_command("score") == "readiness"
    assert parse_command("/score") == "readiness"
    assert parse_command("readiness") == "readiness"
    assert parse_command("/readiness") == "readiness"
    assert parse_command("progress") == "readiness"
    assert parse_command("cmd:readiness") == "readiness"


def test_generate_readiness_report():
    mock_profile = {
        "name": "Sarah",
        "phone_number": "+1234567890",
        "readiness_score": 84,
        "resume_score": 75,
        "streak_count": 7,
        "track": "Software Development",
        "difficulty": "medium",
        "active_focus_area": "System Design",
        "solved": 18,
        "accuracy": 88,
    }
    report = generate_readiness_report(mock_profile)
    assert "Sarah" in report
    assert "84%" in report
    assert "System Design" in report
    assert "SDE-1 / Product Company Ready" in report


def test_resume_onboarding_breakout_and_sample_evaluation():
    import bot
    from caspian import Thread

    class MockThread:
        def __init__(self):
            self.thread_id = "telegram:test_res_user"
            self.chat_id = "test_res_user"
            self.messages = []

        def post(self, text, actions=()):
            self.messages.append((text, actions))

        def send(self, text, actions=()):
            self.messages.append((text, actions))

    class MockMsg:
        def __init__(self, text):
            self.sender = "test_res_user"
            self.thread_id = "telegram:test_res_user"
            self.text = text
            self.raw = {}

    phone = "test_res_user"
    db.upsert_user(phone, name="Test Candidate")

    # Step 1: User enters resume onboarding
    t1 = MockThread()
    bot.handle_text(t1, MockMsg("onboard:ai"), "onboard:ai")
    assert db.get_user(phone)["onboarding_step"] == "awaiting_resume"
    assert any("RESUME INTELLIGENCE" in m[0] for m in t1.messages)

    # Step 2: User taps action button while awaiting_resume -> MUST break out cleanly, never say "too short"
    t2 = MockThread()
    bot.handle_text(t2, MockMsg("cmd:readiness"), "cmd:readiness")
    assert db.get_user(phone)["onboarding_step"] is None
    assert all("too short" not in m[0].lower() for m in t2.messages)
    assert any("Readiness" in m[0] or "Diagnostic" in m[0] or "Score" in m[0] for m in t2.messages)

    # Step 3: User taps 1-click sample profile evaluation
    t3 = MockThread()
    orig_score = bot.score_and_analyze_resume
    bot.score_and_analyze_resume = lambda text, target_role=None: {
        "score": 88,
        "recommended_track": "Software Development",
        "fix_options": ["Redis", "DSA Graphs"],
        "message": "Sample Audit Passed! Score: 88/100",
    }
    try:
        bot.handle_text(t3, MockMsg("sample_resume:sde"), "sample_resume:sde")
        assert any("Sample" in m[0] for m in t3.messages)
        assert any("Score: 88/100" in m[0] for m in t3.messages)
    finally:
        bot.score_and_analyze_resume = orig_score


def test_reply_keyboard_phrases():
    # Verify all phrases sent from user's side when pressing Telegram Reply Keyboard
    assert parse_command("⚡ Mock Interview") == "drill"
    assert parse_command("📄 AI Resume Scanner") == "resume"
    assert parse_command("📊 Readiness Score") == "readiness"
    assert parse_command("🎓 Menu") == "menu"
    assert parse_command("💡 Hint") == "hint"
    assert parse_command("📜 Solution") == "solution"
    assert parse_command("⏭️ Skip") == "skip"

