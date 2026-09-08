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

    SCENARIO_SEEDS = [
        "real-time payment ledger or wallet transaction balance",
        "ride-sharing driver allocation or nearest cab matching",
        "streaming audio/video playlist buffer or sliding window",
        "e-commerce flash sale stock decrement or cart checkout",
        "social media timeline feed ranking or hashtag counter",
        "cloud container scheduler or memory allocator",
        "search auto-complete trie or inverted document index",
        "distributed key-value store with TTL cache eviction",
        "financial fraud detection threshold or anomaly detector",
        "log file error parser or log aggregation pipeline",
    ]
    seed = random.choice(SCENARIO_SEEDS)

    prompt = (
        f"You are an elite Senior Staff Engineer interviewing candidates for '{track}'.\n"
        f"Topic: {topic} | Difficulty: {difficulty.upper()} ({diff_desc})\n"
        f"Engineering Context: {seed}\n\n"
        "Create ONE fresh, practical, and highly engaging placement interview question.\n"
        "CRITICAL RULES:\n"
        "- Do NOT generate cliché LeetCode #1 Two-Sum problems. Ground the problem in the engineering context above!\n"
        "- Solvable in a chat conversation with clear constraints and a concrete worked example.\n"
        "- Do NOT reveal the solution.\n"
        "- Use single asterisks *bold*, never double asterisks **. NO LaTeX math.\n\n"
        "Format cleanly:\n"
        f"📌 *Topic:* {topic}\n"
        f"⚡ *Difficulty:* {difficulty.capitalize()}\n\n"
        "🏢 *Scenario & Problem:*\n(Clear scenario description)\n\n"
        "📋 *Input / Output & Constraints:*\n• Input: ...\n• Output: ...\n• Constraints: ...\n\n"
        "💡 *Worked Example:*\n(Sample input -> expected output with brief explanation)\n\n"
        "🎯 *Your Move:* Reply with your logic, time complexity, or code. (You can also ask questions or discuss trade-offs!)"
    )
    return generate(prompt), topic


def generate_capsule(track: str) -> str:
    prompt = (
        f"Write an inspiring, bite-sized 8:00 AM morning capsule for a {track} campus placement student.\n"
        "Include: 1 punchy industry/tech fact, 1 high-yield CS insight (DBMS/OS/DSA), "
        "and 1 practical interview wisdom tip. Under 120 words. Friendly and energizing."
    )
    return generate(prompt)


def evaluate_answer(question: str, answer: str, track: str) -> str:
    prompt = (
        f"You are an encouraging Senior Staff Engineer interviewing a student for a {track} role.\n\n"
        f"Interview Question:\n{question}\n\n"
        f"Student Answer / Code Attempt:\n{answer}\n\n"
        "Evaluate their response with thorough reasoning and deep diagnostic insight:\n"
        "1. *Verdict:* 🌟 Correct (10/10) / ⚡ Partially Correct (Score/10) / 🔍 Needs Work (Score/10)\n"
        "2. *Score:* <integer 1-10>\n"
        "3. *What Was Good:* praise their positive intuition, approach, or valid code\n"
        "4. *Mistake Analysis & Counterexample:* (CRITICAL)\n"
        "   - If there is ANY bug, logical flaw, or unhandled edge case, pinpoint EXACTLY where it fails!\n"
        "   - Provide the concrete breaking test case (e.g. `arr = [0, -1]`, `k > n`, empty input, duplicates).\n"
        "   - Explain WHY this bug occurs and the mental model needed to avoid it in interviews.\n"
        "5. *How to Fix It:* step-by-step guidance on adjusting their idea.\n"
        "6. *Optimal Production Code:* clean, well-commented, industry-standard implementation.\n"
        "7. *Complexity:* Time O(...) · Space O(...)\n"
        "8. *Interviewer Follow-Up:* 1 quick follow-up question or thought experiment to test their mastery.\n\n"
        "Rules: single asterisks *bold*, NO LaTeX math ($ or \\frac). Encouraging, enjoyable engineering mentor tone."
    )
    return generate(prompt)


def tutor_reason_and_answer(
    user_query: str,
    active_question: str = "",
    track: str = "Software Development",
) -> str:
    """Think, reason, and answer any technical, algorithmic, or conceptual question.

    Acts as an empathetic, brilliant tech mentor who explains things with
    clarity, intuitive analogies, concrete examples, and practical interview relevance.
    """
    context_clause = f"\nActive Interview Drill Question:\n{active_question}\n" if active_question else ""
    prompt = (
        "You are an inspiring Senior Tech Mentor & Placement Coach.\n"
        f"Student Track: {track}{context_clause}\n\n"
        f"Student asked / said:\n\"{user_query}\"\n\n"
        "THINK AND REASON THROUGH THIS STEP-BY-STEP:\n"
        "- If the student is asking a question or doubt about the active drill:\n"
        "  Directly clarify the constraint, validate their thought process, or nudge them in the right direction without giving away the full code.\n"
        "- If the student is asking a conceptual, technical, or interview question:\n"
        "  1. 💡 *Core Intuition / The 'Aha!' Concept*: explain the core idea with an intuitive real-world analogy or mental model.\n"
        "  2. ⚙️ *How it Works (Step-by-Step)*: clear walkthrough or small illustrative code/table.\n"
        "  3. ⚠️ *Common Placement Pitfalls & Edge Cases*: what interviewers watch out for and common mistakes students make.\n"
        "  4. 🎯 *Takeaway & Next Step*: a punchy 1-line recap.\n\n"
        "Tone: Engaging, empowering, clear, conversational. Single asterisks for *bold*, NO LaTeX math."
    )
    return generate(prompt)


def explain_followup(question: str, answer: str, followup: str) -> str:
    return tutor_reason_and_answer(followup, active_question=question)


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
        match = re.search(r"(\d{1,2})\s*/\s*10", feedback, re.I)
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

    Token-optimized for fast, low-latency mobile messaging.
    """
    prompt = (
        "You are an expert campus placement coach analyzing a student's profile.\n\n"
        f"Resume/Text:\n{resume_text[:1200]}\n\n"
        "Respond with EXACTLY this structure:\n\n"
        "🔍 *Profile Highlights:*\n"
        "💪 *Strengths:* (comma-separated top 3-4 skills/tech)\n"
        "⚠️ *Weak Areas:* (comma-separated 2-3 interview gap topics)\n"
        "🎯 *Recommended Track:* (Software Development / Data Science / Core CS)\n\n"
        "Rules: strictly under 60 words. Be ultra-concise to save tokens. Single asterisks *bold*, no LaTeX."
    )
    return generate(prompt)


def generate_prep_plan(
    resume_text: str,
    company: str,
    role: str,
    timeline: str,
) -> str:
    """Generate a personalized, actionable prep plan from gathered onboarding info."""
    prompt = (
        "You are an elite campus placement strategist.\n"
        f"Target: {role} @ {company} | Timeline: {timeline}\n"
        f"Background: {resume_text[:400]}\n\n"
        "Create a hyper-concise placement action plan:\n\n"
        "🚀 *Personalized Placement Roadmap*\n"
        f"🎯 *Goal:* {role} @ {company} ({timeline})\n\n"
        "📋 *Focus Plan:*\n"
        "• Phase 1: (key technical focus)\n"
        "• Phase 2: (mock drills & interview focus)\n"
        "• Daily Habit: (1-line morning & evening routine)\n\n"
        "⚡ *Kickoff Drill:*\n"
        "Weakest area identified: (topic). Starting live questions now!\n\n"
        "CRITICAL: On the VERY LAST LINE of your response, write EXACTLY:\n"
        "FIRST_DRILL_TOPIC: <topic>\n"
        "where <topic> is one of: DSA, DBMS, OS, CN, OOP, SQL, aptitude\n\n"
        "Rules: strictly under 110 words. Single asterisks for bold. No LaTeX."
    )
    return generate(prompt)

