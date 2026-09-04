"""Gemini 2.5 Flash generation helpers."""

from __future__ import annotations

import os
import random
import re

from google import genai
from google.genai import types

from prompts import DIFFICULTY_DESCRIPTORS, SYSTEM_PROMPT, TRACK_TOPICS

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=key)
    return _client


def generate(user_prompt: str, system: str = SYSTEM_PROMPT) -> str:
    response = client().models.generate_content(
        model=_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )
    text = (getattr(response, "text", None) or "").strip()
    if not text:
        return "I blanked for a second — send that again?"
    return text


def pick_topic(track: str) -> str:
    topics = TRACK_TOPICS.get(track) or TRACK_TOPICS["General SDE"]
    return random.choice(topics)


def generate_question(track: str, topic: str | None = None, difficulty: str = "easy") -> tuple[str, str]:
    topic = topic or pick_topic(track)
    diff_desc = DIFFICULTY_DESCRIPTORS.get(difficulty, DIFFICULTY_DESCRIPTORS["easy"])
    prompt = (
        f"Create ONE campus-placement interview question for the '{track}' track "
        f"on topic: {topic}.\n"
        f"Difficulty: {difficulty.upper()} — {diff_desc}\n"
        "Make it solvable in WhatsApp (code snippet or 4-8 line reasoning).\n"
        "Do not reveal the solution.\n"
        "Format:\n"
        f"*Topic:* {topic}\n"
        f"*Difficulty:* {difficulty.capitalize()}\n"
        "*Question:* ...\n"
        "*Constraints / examples:* ...\n"
        "*Your move:* Reply with code or a step-by-step approach."
    )
    return generate(prompt), topic


def generate_capsule(track: str) -> str:
    prompt = (
        f"Write a 8:00 AM WhatsApp morning capsule for a {track} campus placement student.\n"
        "Include: 1 punchy industry/tech fact, 1 must-know CS concept (DBMS/OS/DSA), "
        "and 1 one-line interview tip. Under 120 words. No question yet."
    )
    return generate(prompt)


def evaluate_answer(question: str, answer: str, track: str) -> str:
    prompt = (
        f"Track: {track}\n\nQuestion given to the student:\n{question}\n\n"
        f"Student answer:\n{answer}\n\nGrade it using the required structure."
    )
    return generate(prompt)


def explain_followup(question: str, answer: str, followup: str) -> str:
    prompt = (
        f"The open question was:\n{question}\n\n"
        f"Student previously said:\n{answer or '(none yet)'}\n\n"
        f"Follow-up: {followup}\n\nTeach this point only. Stay WhatsApp-short."
    )
    return generate(prompt)


def show_solution(question: str, track: str) -> str:
    prompt = (
        f"Track: {track}\nStudent asked to skip and see the solution.\n"
        f"Question:\n{question}\n\n"
        "Show the optimal solution with complexity and 2 missed edge cases. "
        "Do not invent a new question."
    )
    return generate(prompt)


def parse_score(feedback: str) -> int | None:
    match = re.search(r"\*Score:\*\s*(\d{1,2})", feedback, re.I)
    if not match:
        match = re.search(r"Score:\s*(\d{1,2})", feedback, re.I)
    if not match:
        return None
    score = int(match.group(1))
    return max(1, min(10, score))


def generate_hint(question: str, hint_number: int) -> str:
    """Generate a progressive hint without revealing the full answer."""
    prompt = (
        f"The student is stuck on this question:\n{question}\n\n"
        f"This is hint #{hint_number} of 2.\n"
    )
    if hint_number == 1:
        prompt += (
            "Give a GENTLE nudge: name the data structure or algorithm category "
            "(e.g., 'Think about using a hash map'). Do NOT reveal the approach or code. "
            "Keep it under 40 words."
        )
    else:
        prompt += (
            "Give a STRONGER hint: outline the high-level approach in 2-3 bullet points "
            "(e.g., 'Sort the array first, then use two pointers'). "
            "Do NOT write code. Keep it under 80 words."
        )
    return generate(prompt)


def generate_weekly_report(track: str, drills: list[dict], stats: dict) -> str:
    """Generate a personalized weekly progress report via Gemini."""
    if not drills:
        return (
            "📊 *Weekly Report*\n\n"
            "No practice sessions this week. Start a *drill* to get back on track!"
        )
    summary_lines = []
    for d in drills[:20]:  # cap to avoid token overflow
        summary_lines.append(f"- {d.get('topic', '?')}: score {d.get('score', '?')}")
    drill_text = "\n".join(summary_lines)
    prompt = (
        f"Generate a WhatsApp-friendly weekly progress report for a {track} student.\n\n"
        f"Stats: streak={stats.get('streak', 0)}, solved={stats.get('solved', 0)}, "
        f"accuracy={stats.get('accuracy', 0)}%, level={stats.get('difficulty', 'easy')}\n\n"
        f"This week's drills:\n{drill_text}\n\n"
        "Structure:\n"
        "📊 *Weekly Progress Report*\n"
        "• Summary (2 lines)\n"
        "• 💪 Strengths (top 2 topics)\n"
        "• 🎯 Focus Areas (weakest 2 topics)\n"
        "• 📈 Next Week Goal (1 actionable line)\n\n"
        "Keep it under 200 words. Be encouraging but data-driven."
    )
    return generate(prompt)
