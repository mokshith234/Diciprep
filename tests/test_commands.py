from datetime import date

from commands import is_followup, parse_command, parse_track_payload
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
