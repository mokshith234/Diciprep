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


def test_gateway_action_parser_robustness():
    from caspian.hosted.inbound import GatewayEventParser
    from caspian.core.ports import RawInbound
    import json

    parser = GatewayEventParser()

    # Shape 1: telegram-style with callback_data and id
    p1 = {
        "events": [
            {
                "type": "interaction.received",
                "data": {
                    "interaction": {
                        "channel": "telegram",
                        "conversation_id": "999888",
                        "callback_data": "cmd:hint",
                        "sender": "999888",
                        "id": "query_12345",
                    }
                },
            }
        ]
    }
    raw1 = RawInbound(body=json.dumps(p1).encode(), headers={})
    events1 = parser.parse(raw1).value
    assert len(events1) == 1
    assert events1[0].data == "cmd:hint"
    assert events1[0].interaction_id == "query_12345"
    assert events1[0].raw["id"] == "query_12345"

    # Shape 2: standard data field
    p2 = {
        "events": [
            {
                "type": "interaction.received",
                "data": {
                    "interaction": {
                        "channel": "telegram",
                        "conversation_id": "999888",
                        "data": "cmd:drill",
                        "sender": "999888",
                    }
                },
            }
        ]
    }
    raw2 = RawInbound(body=json.dumps(p2).encode(), headers={})
    events2 = parser.parse(raw2).value
    assert len(events2) == 1
    assert events2[0].data == "cmd:drill"


def test_unified_thread_post_telegram_direct_routing(monkeypatch):
    import bot
    from caspian import Button

    sent_calls = []
    monkeypatch.setattr(
        "outbound.send_telegram",
        lambda chat_id, text, actions=None: sent_calls.append({"chat_id": chat_id, "text": text, "actions": actions}),
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_token_123")

    class FakeCaspianThread:
        def __init__(self, tid):
            self.thread_id = tid
            self._commands = []

    # 1. Message with buttons
    t1 = FakeCaspianThread("telegram:777666")
    btn = Button(label="Click", data="cmd:click")
    bot._unified_thread_post(t1, "Here are buttons", actions=(btn,))
    assert len(sent_calls) == 1
    assert sent_calls[0]["chat_id"] == "777666"
    assert sent_calls[0]["text"] == "Here are buttons"
    assert len(sent_calls[0]["actions"]) == 1

    # 2. Text-only message (NO BUTTONS - critical fix!)
    bot._unified_thread_post(t1, "This is plain text feedback without buttons")
    assert len(sent_calls) == 2
    assert sent_calls[1]["chat_id"] == "777666"
    assert sent_calls[1]["text"] == "This is plain text feedback without buttons"
    assert sent_calls[1]["actions"] == ()


def test_hint_and_solution_button_actions(monkeypatch):
    phone = "+15551234567"
    db.upsert_user(phone, name="Student", track="Software Development")
    db.set_pending(phone, "Write binary search", "DSA", drill_remaining=2)

    thread = MockThread()
    msg = MockMessage("cmd:hint", phone)

    monkeypatch.setattr("bot.generate_hint", lambda q, c: "Think about dividing the range in half.")
    _handle_text_inner(thread, msg, "cmd:hint")

    assert len(thread.messages) >= 1
    hint_msg = thread.messages[-1]
    assert "Hint" in hint_msg["text"]
    assert "dividing the range" in hint_msg["text"]

    # Test solution button
    thread2 = MockThread()
    msg2 = MockMessage("cmd:solution", phone)
    monkeypatch.setattr("bot.show_solution", lambda q, t: "Solution: low=0, high=len-1...")
    monkeypatch.setattr("bot.generate_question", lambda tr, topic=None, difficulty='easy': ("Next question?", "DSA"))
    _handle_text_inner(thread2, msg2, "cmd:solution")

    assert len(thread2.messages) >= 1
    sol_msg = thread2.messages[0]
    assert "Solution:" in sol_msg["text"]


def test_send_telegram_resilience(monkeypatch):
    import httpx
    from caspian import Button
    from outbound import send_telegram

    sent_requests = []

    def mock_post(url, **kwargs):
        json_body = dict(kwargs.get("json", {}))
        sent_requests.append(json_body)
        # First request simulates markdown entity failure if parse_mode is set
        if json_body.get("parse_mode") == "Markdown" and "bad_entity" in json_body.get("text", ""):
            return httpx.Response(400, text='{"description": "Bad Request: can\'t parse entities: unclosed token"}')
        return httpx.Response(200, text='{"ok": true}')

    monkeypatch.setattr("httpx.post", mock_post)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_bot_token")

    # 1. Test markdown error recovery
    send_telegram("12345", "Here is a *bold* with bad_entity [broken link")
    # Should have attempted once with Markdown, failed, and retried without parse_mode
    assert len(sent_requests) == 2
    assert sent_requests[0]["parse_mode"] == "Markdown"
    assert "parse_mode" not in sent_requests[1]
    assert sent_requests[1]["text"] == "Here is a *bold* with bad_entity [broken link"

    # 2. Test empty text with buttons
    sent_requests.clear()
    btn = Button(label="Click me", data="cmd:click")
    send_telegram("12345", "", actions=(btn,))
    assert len(sent_requests) == 1
    assert "reply_markup" in sent_requests[0]
    assert sent_requests[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "cmd:click"


def test_judge_command_flow():
    thread = MockThread()
    msg = MockMessage("/judge", "+19998887777")
    _handle_text_inner(thread, msg, "/judge")

    assert len(thread.messages) == 1
    report = thread.messages[0]["text"]
    assert "CASPIAN HACKATHON" in report
    assert "Message Volume" in report
    assert "/api/stats" in report
    assert "/api/messages/count" in report


def test_judge_fastapi_endpoints():
    from fastapi.testclient import TestClient
    from app import app

    client = TestClient(app, raise_server_exceptions=False)

    # 1. /health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    d_health = r_health.json()
    assert d_health["status"] == "ok"
    assert "messages_tracked" in d_health
    assert "inbound" in d_health
    assert "outbound" in d_health

    # 2. /api/stats
    r_stats = client.get("/api/stats")
    assert r_stats.status_code == 200
    d_stats = r_stats.json()
    assert d_stats["status"] == "ok"
    assert "metrics" in d_stats
    assert "total_messages" in d_stats["metrics"]
    assert "caspian_telemetry" in d_stats

    # 3. /api/messages/count
    r_count = client.get("/api/messages/count")
    assert r_count.status_code == 200
    d_count = r_count.json()
    assert d_count["status"] == "ok"
    assert "total_messages" in d_count
    assert "inbound" in d_count
    assert "outbound" in d_count

    # 4. /api/messages
    r_msgs = client.get("/api/messages?limit=10")
    assert r_msgs.status_code == 200
    d_msgs = r_msgs.json()
    assert d_msgs["status"] == "ok"
    assert "messages" in d_msgs
    assert isinstance(d_msgs["messages"], list)


def test_message_logging_and_stats_aggregation():
    initial_stats = db.get_message_stats()
    initial_total = initial_stats["total_messages"]

    db.log_message("telegram", "inbound", "test_user_42", "Hello bot!", msg_type="text")
    db.log_message("telegram", "outbound", "test_user_42", "Welcome candidate!", msg_type="text")
    db.log_message("telegram", "inbound", "test_user_42", "cmd:drill", msg_type="button_click")

    updated = db.get_message_stats()
    assert updated["total_messages"] == initial_total + 3
    assert updated["button_clicks"] >= initial_stats["button_clicks"] + 1

    recent = db.get_recent_messages(limit=5)
    assert any(m["text"] == "Hello bot!" for m in recent)
    assert any(m["text"] == "Welcome candidate!" for m in recent)


def test_button_click_event_to_outbound_delivery(monkeypatch):
    import json
    import bot
    from caspian.hosted.inbound import GatewayEventParser
    from caspian.core.ports import RawInbound
    from caspian import HandlerContext

    sent_messages = []
    ack_calls = []
    monkeypatch.setattr(
        "outbound.send_telegram",
        lambda chat_id, text, actions=None: sent_messages.append({"chat_id": chat_id, "text": text, "actions": actions}),
    )
    monkeypatch.setattr(
        "outbound.answer_telegram_callback",
        lambda cb_id: ack_calls.append(cb_id),
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_telegram_bot_token")

    # Simulate Caspian hosted gateway callback query event
    payload = {
        "events": [
            {
                "type": "interaction.received",
                "data": {
                    "interaction": {
                        "id": "query_btn_777",
                        "conversation_id": "conv_999aaa",
                        "channel": "telegram",
                        "callback_data": "track:sde",
                        "sender": {"address": "1162882541", "name": "Mokshith"},
                    }
                },
            }
        ]
    }

    parser = GatewayEventParser()
    events = parser.parse(RawInbound(body=json.dumps(payload).encode(), headers={})).value
    assert len(events) == 1
    action_event = events[0]
    assert action_event.data == "track:sde"
    assert action_event.interaction_id == "query_btn_777"

    class FakeThread:
        def __init__(self, tid):
            self.thread_id = tid
        def post(self, text, actions=()):
            bot._unified_thread_post(self, text, actions=actions)

    thread = FakeThread("telegram:conv_999aaa")

    # Set up dummy Caspian context to invoke the on_action logic
    class FakeCaspian:
        def __init__(self):
            self.action_handler = None
        def on_action(self, *args, **kwargs):
            def decorator(fn):
                self.action_handler = fn
                return fn
            return decorator
        def on_message(self, *args, **kwargs):
            return lambda fn: fn

    fake_cx = FakeCaspian()
    bot.register(fake_cx)

    # 1. Execute on_action for track:sde
    fake_cx.action_handler(thread, action_event, HandlerContext())

    # Verify Telegram callback query is acknowledged
    import time
    time.sleep(0.1)
    assert "query_btn_777" in ack_calls

    # Verify the reply is sent directly to the user's real Telegram chat_id (NOT conv_999aaa!)
    assert len(sent_messages) >= 1
    assert sent_messages[0]["chat_id"] == "1162882541"
    assert "Track Confirmed: Software Development" in sent_messages[0]["text"]
    assert len(sent_messages[0]["actions"]) > 0

    # 2. Test button click on cmd:hint
    sent_messages.clear()
    hint_payload = {
        "events": [
            {
                "type": "interaction.received",
                "data": {
                    "interaction": {
                        "id": "query_btn_888",
                        "conversation_id": "conv_999aaa",
                        "channel": "telegram",
                        "callback_data": "cmd:hint",
                        "sender": {"address": "1162882541", "name": "Mokshith"},
                    }
                },
            }
        ]
    }
    hint_events = parser.parse(RawInbound(body=json.dumps(hint_payload).encode(), headers={})).value
    monkeypatch.setattr("bot.generate_hint", lambda q, c: "💡 Hint 1: Use two pointers to swap elements.")
    db.set_pending("1162882541", "Reverse a linked list", "DSA", drill_remaining=2)
    db.reset_hints("1162882541")
    fake_cx.action_handler(thread, hint_events[0], HandlerContext())

    assert len(sent_messages) >= 1
    assert sent_messages[-1]["chat_id"] == "1162882541"
    assert "Hint" in sent_messages[-1]["text"]


def test_drill_db_persistence_lifecycle(monkeypatch):
    """Verify drill lifecycle: log_drill_started -> record_solution_revealed / record_attempt."""
    test_phone = "+19998887777"
    db.upsert_user(test_phone, name="Tester", track="Data Science")

    # 1. Start drill: question is logged to drills table
    q1 = "Explain bias-variance tradeoff in machine learning."
    drill_id = db.log_drill_started(test_phone, "ML", q1)
    assert drill_id > 0

    today_drills = db.get_today_drills(test_phone)
    assert any(d["question_text"] == q1 for d in today_drills)
    pending_drill = [d for d in today_drills if d["question_text"] == q1][0]
    assert pending_drill["user_response"] == "[In Progress]"
    assert pending_drill["score"] is None

    # 2. View solution: drill record is updated with solution
    sol = "Bias is underfitting, variance is overfitting. Regularization balances both."
    db.record_solution_revealed(test_phone, q1, sol, "ML")
    drills_after_sol = db.get_today_drills(test_phone)
    sol_drill = [d for d in drills_after_sol if d["question_text"] == q1][0]
    assert sol_drill["user_response"] == "[Solution Revealed]"
    assert sol_drill["model_feedback"] == sol
    assert sol_drill["score"] == 0

    # 3. Next question started and answered with grading
    q2 = "What is L1 vs L2 regularization?"
    db.log_drill_started(test_phone, "ML", q2)
    ans2 = "L1 produces sparse weights (Lasso), L2 penalizes large weights (Ridge)."
    feedback2 = "Verdict: Optimal! *Score:* 9/10"
    db.record_attempt(test_phone, "ML", q2, ans2, feedback2, 9)

    drills_final = db.get_today_drills(test_phone)
    graded_drill = [d for d in drills_final if d["question_text"] == q2][0]
    assert graded_drill["user_response"] == ans2
    assert graded_drill["score"] == 9

    # 4. Skip another question
    q3 = "Explain dropout in deep learning."
    db.log_drill_started(test_phone, "Deep Learning", q3)
    db.record_drill_skipped(test_phone, q3)
    drills_after_skip = db.get_today_drills(test_phone)
    skip_drill = [d for d in drills_after_skip if d["question_text"] == q3][0]
    assert skip_drill["user_response"] == "[Skipped]"

    # Check stats reflect drills
    st = db.get_message_stats()
    assert st["drills_count"] >= 3


def test_scalar_helper():
    """Verify _scalar handles tuple, dict, and Row structures without KeyError."""
    assert db._scalar((42,)) == 42
    assert db._scalar({"count": 88}) == 88
    assert db._scalar(None, default=0) == 0
    assert db._scalar([]) == 0




