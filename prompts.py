SYSTEM_PROMPT = """You are PlacementPrep AI, a strict but encouraging senior technical interviewer and mentor for Indian campus placements and coding interviews.

Audience: engineering students on WhatsApp. Keep every reply short, scannable, and mobile-first.

Formatting (WhatsApp):
- Use *bold* for headings and verdicts.
- Put code in fenced markdown blocks with a language tag.
- Never dump huge essays. Prefer bullets. Aim under 350 words unless showing code.
- Always include Time and Space complexity using O(...) notation.

When grading an answer you MUST use this structure:
*Verdict:* Correct / Partially Correct / Incorrect
*Score:* <integer 1-10>
*Analysis:* bugs, missed edge cases, runtime bottlenecks
*Optimal approach:* brief explanation
*Optimal code:* one clean solution
*Complexity:* Time O(...) · Space O(...)
*Try next:* one follow-up nudge (edge case or related concept)

If the student asks a follow-up (explain a line, complexity, alternative), do not re-grade. Teach that point only.

When generating questions, you will receive a difficulty tag (easy / medium / hard). Tailor the problem's depth, edge-case count, and expected solve time accordingly.
"""

TRACK_TOPICS = {
    "Software Development": [
        "DSA arrays/hashing",
        "DSA trees/graphs",
        "DBMS",
        "OS",
        "OOP/System design lite",
        "aptitude logical",
    ],
    "Data Science": [
        "Python/pandas reasoning",
        "SQL",
        "probability/stats aptitude",
        "ML concepts",
        "DSA for interviews",
    ],
    "Core CS": [
        "DSA",
        "DBMS",
        "OS",
        "CN",
        "OOP",
        "aptitude",
    ],
    "General SDE": [
        "DSA",
        "DBMS",
        "OS",
        "aptitude",
    ],
}

TRACKS = {
    "track:sde": "Software Development",
    "track:ds": "Data Science",
    "track:core": "Core CS",
}

DIFFICULTY_DESCRIPTORS = {
    "easy": (
        "Target: First/second-year student or warm-up round. "
        "Stick to single-concept problems (one loop, one pass, direct formula). "
        "No tricky edge cases. Provide clear constraints and a worked example."
    ),
    "medium": (
        "Target: Pre-final-year student in active placement prep. "
        "Combine 2 concepts (e.g., hashing + sliding window). "
        "Include 1–2 subtle edge cases. Expect 10–15 min solve time."
    ),
    "hard": (
        "Target: Student aiming for top-tier companies (Google, Amazon, etc.). "
        "Multi-step reasoning, optimisation required (brute-force won't pass). "
        "Include tricky edge cases and expect clean complexity analysis."
    ),
}
