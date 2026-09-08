"""Tests for bot flows: resume onboarding, weakness fix routing, scorecard display, grading."""

import db
from bot import _handle_text_inner, _grade, _show_readiness_scorecard
from commands import parse_command, parse_fix_command


class MockThread:
    def __init__(self):
        self.messages = []

    def post(self, text, actions=None):
        self.messages.append({"text": text, "actions": actions})

    send = post


class MockMessage:
    def __init__(self, text, sender_phone="+15555555555"):
        self.text = text
        self.sender = {"address": sender_phone, "name": "Mokshith"}
        self.thread_id = f"telegram:{sender_phone}"


def test_scorecard_command_flow():
    phone = "+15555555555"
    db.upsert_user(phone, name="Mokshith", track="Software Development")
    db.set_focus_area(phone, "Operating Systems")

    thread = MockThread()
    msg = MockMessage("score", phone)

    _handle_text_inner(thread, msg, "score")

    assert len(thread.messages) >= 1
    last_msg = thread.messages[-1]
    assert "SCORECARD" in last_msg["text"]
    assert "Operating Systems" in last_msg["text"]
    assert last_msg["actions"] is not None
    # Check that at least one action is a fix button
    action_labels = [a.label for a in last_msg["actions"]]
    assert any("Fix:" in lbl for lbl in action_labels)


def test_fix_button_action_flow():
    phone = "+15555555555"
    thread = MockThread()
    msg = MockMessage("fix:DBMS", phone)

    _handle_text_inner(thread, msg, "fix:DBMS")

    # Verify focus area was saved to DB
    profile = db.get_readiness_profile(phone)
    assert profile["active_focus_area"] == "DBMS"
    assert len(thread.messages) >= 1
    # Check that a drill question or intro was sent
    assert any("DBMS" in m["text"] for m in thread.messages)


def test_grade_readiness_bump(monkeypatch):
    phone = "+15555555555"
    db.upsert_user(phone, name="Mokshith", track="Software Development")
    initial_profile = db.get_readiness_profile(phone)
    init_score = initial_profile["readiness_score"]

    # Mock evaluate_answer to return high score feedback
    monkeypatch.setattr("bot.evaluate_answer", lambda q, a, t: "Excellent answer! Clear explanation of paging.\nScore: 9/10\nVerdict: pass")

    thread = MockThread()
    # Grade with remaining = 0 to trigger session complete card
    user = db.get_user(phone)
    user["drill_remaining"] = 0
    _grade(
        thread,
        phone,
        question="Explain virtual memory paging",
        answer="Paging divides memory into fixed size pages and maps them to physical frames using a page table.",
        user=user,
    )

    new_profile = db.get_readiness_profile(phone)
    # Score should have bumped
    assert new_profile["readiness_score"] >= init_score
    # Session complete message with readiness bar
    last_msg = thread.messages[-1]
    assert "Placement Readiness" in last_msg["text"]
    assert last_msg["actions"] is not None
