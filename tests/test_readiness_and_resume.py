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
