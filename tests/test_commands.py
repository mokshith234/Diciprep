from datetime import date

from commands import (
    is_followup,
    parse_command,
    parse_company_command,
    parse_resume_command,
    parse_role_command,
    parse_topic_drill,
    parse_track_payload,
)
from db import next_streak


def test_commands():
    assert parse_command("hi") == "start"
    assert parse_command("/drill") == "drill"
    assert parse_command("streak") == "streak"
    assert parse_command("/solution") == "solution"
    assert parse_command("random code") is None


def test_followup():
    assert is_followup("explain line 4")
    assert is_followup("time complexity?")
    assert not is_followup("def two_sum(a):")


def test_track_payload():
    assert parse_track_payload("track:ds") == "Data Science"
    assert parse_track_payload("track:sde") == "Software Development"
    assert parse_track_payload("track:core") == "Core CS"


def test_streak_math():
    today = date(2026, 9, 3)
    yesterday = date(2026, 9, 2)
    assert next_streak(None, 0, today) == 1
    assert next_streak(yesterday, 4, today) == 5
    assert next_streak(today, 5, today) == 5
    assert next_streak(date(2026, 8, 1), 9, today) == 1


def test_new_commands():
    assert parse_command("hint") == "hint"
    assert parse_command("/hint") == "hint"
    assert parse_command("topics") == "topics"
    assert parse_command("/topics") == "topics"
    assert parse_command("level") == "level"
    assert parse_command("/level") == "level"
    assert parse_command("leaderboard") == "leaderboard"
    assert parse_command("/leaderboard") == "leaderboard"
    assert parse_command("lb") == "leaderboard"

    # Action buttons
    assert parse_command("cmd:hint") == "hint"
    assert parse_command("cmd:solution") == "solution"
    assert parse_command("cmd:skip") == "solution"

    # Summary
    assert parse_command("summary") == "summary"
    assert parse_command("/summary") == "summary"
    assert parse_command("revision") == "summary"


def test_parameterized_features():
    # Topic drill
    assert parse_topic_drill("drill os") == "os"
    assert parse_topic_drill("/drill dsa") == "dsa"
    assert parse_topic_drill("drill dbms") == "dbms"
    assert parse_topic_drill("drill") is None

    # Company
    assert parse_company_command("company amazon") == "amazon"
    assert parse_company_command("/company google") == "google"
    assert parse_company_command("target company tcs") == "tcs"

    # Role & Resume
    assert parse_role_command("role SDE 1") == "SDE 1"
    assert parse_role_command("/role Backend (Python)") == "Backend (Python)"
    is_res, text = parse_resume_command("resume: Built fullstack React app, skilled in Java")
    assert is_res is True
    assert "React" in text
    assert parse_resume_command("/resume")[0] is True
