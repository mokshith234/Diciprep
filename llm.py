"""LLM generation helpers: Groq (ultra-fast primary) + Google Gemini (reliable fallback)."""

from __future__ import annotations

import logging
import os
import random
import re

from google import genai
from google.genai import types

from prompts import DIFFICULTY_DESCRIPTORS, SYSTEM_PROMPT, TRACK_TOPICS

log = logging.getLogger("placementprep.llm")

# Groq models (Primary: openai/gpt-oss-120b is the top free 120B model on Groq)
_GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
_GROQ_CANDIDATE_MODELS = [_GROQ_MODEL, "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

# Gemini models (Fallback)
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
_GEMINI_CANDIDATE_MODELS = [_GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-flash-latest"]

_client: genai.Client | None = None
_groq_client = None


def client() -> genai.Client:
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=key)
    return _client


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            return None
        from groq import Groq
        _groq_client = Groq(api_key=key)
    return _groq_client


def generate_groq(user_prompt: str, system: str = SYSTEM_PROMPT) -> str | None:
    groq_c = get_groq_client()
    if groq_c is None:
        return None
    models_to_try = list(dict.fromkeys(_GROQ_CANDIDATE_MODELS))
    for m in models_to_try:
        try:
            resp = groq_c.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as exc:
            log.warning("Groq model %s error: %s", m, exc)
            continue
    return None


def generate_gemini(user_prompt: str, system: str = SYSTEM_PROMPT) -> str:
    models_to_try = list(dict.fromkeys(_GEMINI_CANDIDATE_MODELS))
    last_err: Exception | None = None
    for model_name in models_to_try:
        try:
            response = client().models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            text = (getattr(response, "text", None) or "").strip()
            if text:
                return text
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return "I blanked for a second — send that again?"


def clean_chat_markdown(text: str) -> str:
    """Sanitize LLM output for mobile messaging platforms (Telegram/WhatsApp)."""
    if not text:
        return text
    # 1. Unpack \text{...}
    while r"\text{" in text:
        text = re.sub(r"\\text\{([^}]+)\}", r"\1", text)
    # 2. Convert LaTeX fractions: \frac{A}{B} -> (A) / (B)
    while r"\frac" in text:
        new_text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1) / (\2)", text)
        if new_text == text:
            break
        text = new_text
    # 3. Clean common math symbols
    text = (
        text.replace(r"\times", "*")
        .replace(r"\div", "/")
        .replace(r"\le", "<=")
        .replace(r"\ge", ">=")
        .replace(r"\neq", "!=")
        .replace(r"\approx", "~=")
    )
    # 4. Remove math dollar signs $...$
    text = re.sub(r"\$([^\$]+)\$", r"\1", text)
    # 5. Convert markdown **bold** to single *bold* (Telegram/WhatsApp compatible)
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
    return text.strip()


def generate(user_prompt: str, system: str = SYSTEM_PROMPT) -> str:
    # 1. Try Groq first for blazing speed if GROQ_API_KEY is provided
    result = ""
    if os.environ.get("GROQ_API_KEY", "").strip():
        groq_result = generate_groq(user_prompt, system)
        if groq_result:
            result = groq_result

    # 2. Fall back to Gemini
    if not result:
        result = generate_gemini(user_prompt, system)

    return clean_chat_markdown(result)


def pick_topic(track: str) -> str:
    topics = TRACK_TOPICS.get(track) or TRACK_TOPICS["General SDE"]
    return random.choice(topics)


def generate_question(track: str, topic: str | None = None, difficulty: str = "easy") -> tuple[str, str]:
    topic = topic or pick_topic(track)
    diff_desc = DIFFICULTY_DESCRIPTORS.get(difficulty, DIFFICULTY_DESCRIPTORS["easy"])
    prompt = (
        f"Create ONE campus-placement interview question for the '{track}' track on topic: {topic}.\n"
        f"Difficulty: {difficulty.upper()} — {diff_desc}\n"
        "Make it solvable in a messaging chat (concise problem statement, clear input/output or scenario).\n"
        "Do not reveal the solution.\n"
        "CRITICAL: Do NOT use LaTeX math ($ or \\frac). Use standard text formulas like WT = Start - Arrival.\n"
        "Use single asterisks *bold*, never double asterisks **.\n"
        "Format cleanly:\n"
        f"*Topic:* {topic}\n"
        f"*Difficulty:* {difficulty.capitalize()}\n\n"
        "*Question:*\n...\n\n"
        "*Constraints / Examples:*\n...\n\n"
        "*Your move:* Reply with your step-by-step approach or code."
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


def generate_company_question(
    company: str,
    track: str,
    topic: str | None = None,
    difficulty: str = "medium",
    resume_context: str = "",
) -> tuple[str, str]:
    topic = topic or pick_topic(track)
    diff_desc = DIFFICULTY_DESCRIPTORS.get(difficulty, DIFFICULTY_DESCRIPTORS["medium"])
    resume_clause = f"\nCandidate Profile & Resume Highlights: {resume_context}" if resume_context else ""
    prompt = (
        f"Create ONE realistic technical interview question for {company.upper()} campus/off-campus placements.\n"
        f"Track: {track} · Topic: {topic} · Difficulty: {difficulty.upper()} ({diff_desc}){resume_clause}\n"
        f"Reflect the actual interview pattern of {company} (e.g., algorithmic depth, system edge cases, or core CS fundamentals).\n"
        "Make it solvable in a messaging chat.\n"
        "Do not reveal the solution.\n"
        "CRITICAL: Do NOT use LaTeX math ($ or \\frac). Use standard text notation.\n"
        "Use single asterisks *bold*, never double asterisks **.\n"
        "Format cleanly:\n"
        f"*Company:* {company.capitalize()} Mock\n"
        f"*Topic:* {topic} ({difficulty.capitalize()})\n\n"
        "*Question:*\n...\n\n"
        "*Constraints / Examples:*\n...\n\n"
        "*Your move:* Reply with your step-by-step approach or code."
    )
    return generate(prompt), topic


def analyze_resume(resume_text: str, target_role: str = "") -> str:
    role_clause = f" for the target role: *{target_role}*" if target_role else ""
    prompt = (
        f"You are a Principal Tech Recruiter and Senior Engineering Interviewer evaluating a student's resume{role_clause}.\n\n"
        f"Resume Content:\n{resume_text}\n\n"
        "Analyze this resume with direct, brutally honest, and high-value feedback:\n"
        "1. *Candidate Match & Key Stack:* (Core strengths, tech stack summary)\n"
        "2. *Interview Vulnerabilities (The Grill List):* 3 specific topics, algorithms, or project claims on this resume where interviewers will grill them hardest (e.g. if they mention Redis, ask about cache invalidation)\n"
        "3. *Missing High-Yield Skills:* 2-3 critical concepts missing for this role\n"
        "4. *7-Day Targeted Action Plan:* Day-by-day prep plan to be interview-ready\n\n"
        "Rules:\n"
        "- Messaging-friendly markdown (single asterisks *bold*, clean bullet points, NO LaTeX math).\n"
        "- Actionable and specific to Indian campus/fresher hiring.\n"
        "- Under 350 words total."
    )
    return generate(prompt)


def generate_daily_summary(drills: list[dict], user_profile: dict) -> str:
    if not drills:
        return (
            "📝 *Daily Revision Summary*\n\n"
            "You haven't practiced any questions today yet!\n"
            "Send *drill* or *drill os* to start practicing now."
        )
    lines = []
    for i, d in enumerate(drills[:15], 1):
        q_snippet = (d.get("question_text") or "").split("\n")[0][:60]
        lines.append(
            f"{i}. [{d.get('topic', 'General')}] Score: {d.get('score', '?')}/10\n"
            f"   Q: {q_snippet}...\n"
            f"   Feedback takeaway: {(d.get('model_feedback') or '')[:120]}..."
        )
    drill_blob = "\n".join(lines)
    prompt = (
        "Generate a high-yield Daily Revision Cheat Sheet for this student based on what they solved today.\n\n"
        f"Today's Attempts:\n{drill_blob}\n\n"
        "Structure:\n"
        "📑 *Daily Revision Cheat Sheet*\n"
        f"• *Solved Today:* {len(drills)} question(s)\n"
        "• *Key Concepts & Formulas to Remember:* (3-4 bullet points)\n"
        "• *Edge Cases / Mistakes to Avoid:* (What went wrong in their attempts today)\n"
        "• *Tomorrow's Recommended Drill:* (1 specific topic recommendation)\n\n"
        "Keep it concise, high-yield, and formatted in clean WhatsApp/Telegram markdown (single asterisks *bold*, NO LaTeX math)."
    )
    return generate(prompt)


def extract_skills_from_resume(resume_text: str) -> str:
    """Extract skills, strengths, and gaps from pasted resume text.

    Returns a conversational analysis to show the user what AI detected,
    formatted for messaging apps.
    """
    prompt = (
        "You are an expert campus placement coach analyzing a student's resume/skills.\n\n"
        f"Resume / Skills / Projects:\n{resume_text}\n\n"
        "Respond with EXACTLY this structure (messaging-friendly markdown, single asterisks *bold*):\n\n"
        "🔍 *Here's what I found in your profile:*\n\n"
        "💪 *Your Strengths:*\n"
        "• (list 3-4 key skills/technologies detected)\n\n"
        "⚠️ *Potential Weak Areas:*\n"
        "• (list 2-3 gaps or areas that need prep based on what's missing)\n\n"
        "🎯 *Recommended Track:* (pick: Software Development / Data Science / Core CS)\n\n"
        "📊 *Difficulty:* (easy / medium / hard based on experience level)\n\n"
        "Keep it under 150 words. Be specific about detected tech stack. "
        "Do NOT use LaTeX math. Use single asterisks for bold."
    )
    return generate(prompt)


def generate_prep_plan(
    resume_text: str,
    company: str,
    role: str,
    timeline: str,
) -> str:
    """Generate a personalized, actionable prep plan from gathered onboarding info.

    Returns the plan + a recommended first drill topic.
    """
    prompt = (
        "You are an elite campus placement strategist creating a hyper-personalized prep plan.\n\n"
        f"*Student Profile:*\n"
        f"• Resume/Skills: {resume_text[:600]}\n"
        f"• Target Company: {company}\n"
        f"• Target Role: {role}\n"
        f"• Timeline: {timeline}\n\n"
        "Create a sharp, actionable placement prep plan in this EXACT structure:\n\n"
        "🚀 *Your Personalized Prep Plan*\n\n"
        f"🏢 *Target:* {role} at {company}\n"
        f"⏰ *Timeline:* {timeline}\n\n"
        "📋 *Week-by-Week Roadmap:*\n"
        "• Week 1: (focus area + specific actions)\n"
        "• Week 2: (focus area + specific actions)\n"
        "• Week 3: (focus area + specific actions)\n"
        "• Week 4: (focus area + specific actions)\n\n"
        "🎯 *Daily Prep Routine:*\n"
        "• Morning: (what to do)\n"
        "• Evening: (what to do)\n\n"
        "⚡ *Start Now:*\n"
        "Your weakest area based on resume analysis is: (topic). "
        "I'll start your first drill on this right away!\n\n"
        "CRITICAL: On the VERY LAST LINE of your response, write EXACTLY:\n"
        "FIRST_DRILL_TOPIC: <topic>\n"
        "where <topic> is one of: DSA, DBMS, OS, CN, OOP, SQL, aptitude\n\n"
        "Rules: messaging-friendly markdown, single asterisks *bold*, NO LaTeX. Under 300 words."
    )
    return generate(prompt)
