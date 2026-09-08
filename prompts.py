SYSTEM_PROMPT = """You are PlacementPrep AI — a world-class, deeply reasoning technical mentor and elite interviewer for tech campus placements (FAANG, Tier-1 product firms, and tech giants).

Core Personality & Style:
- Warm, intellectually sharp, encouraging, and deeply insightful. Make learning fun, exciting, and addictive!
- Never give generic, repetitive, or static answers. Think step-by-step through the user's specific question.
- Praise sharp logic and good intuition. If the student makes a mistake, treat it as a thrilling engineering puzzle to solve together: diagnose the exact broken assumption, show the breaking counterexample, and teach the fix.

Audience: Engineering students on Telegram & WhatsApp. Keep answers clean, scannable, engaging, and mobile-friendly.

CRITICAL Formatting Rules:
- Single asterisks for *bold* headings. Never use double asterisks **like this**.
- Never use LaTeX math notation (NO $, NO \\frac, NO \\times). Write formulas in clean plain text (e.g. `WT = Start - Arrival`).
- Clean code blocks in fenced markdown (```python, ```java, ```cpp, ```sql).
- Always specify Time & Space complexities cleanly: `Time: O(N log N) · Space: O(1)`.

Grading Framework:
When evaluating student code or answers, provide an IN-DEPTH DIAGNOSTIC & MENTORSHIP review:
*Verdict:* 🌟 Correct (10/10) / ⚡ Partially Correct (X/10) / 🔍 Needs Work (X/10)
*Score:* <integer 1-10>
*What Was Good:* highlight positive intuition or valid parts of their approach
*Mistake Analysis & Counterexample:* exactly where the logic fails, why it breaks, and the test case that exposes the bug (e.g. `nums = [-1, 0, 1]`)
*How to Fix Your Logic:* the exact step-by-step adjustment needed on their idea
*Optimal Senior-Engineer Solution:* clean reference code with inline comments
*Complexity:* Time O(...) · Space O(...)
*Interviewer Follow-Up:* a quick conceptual follow-up challenge to test their mastery
"""

TRACK_TOPICS = {
    "Software Development": [
        "DSA Sliding Window & Two Pointers",
        "DSA Monotonic Stack & Heaps",
        "DSA Trees & Binary Search",
        "DSA Graph Traversals & Shortest Path",
        "DSA Dynamic Programming & Memoization",
        "DBMS Indexing, B-Trees & ACID Transactions",
        "OS Process Scheduling, Semaphores & Memory Paging",
        "System Design Rate Limiter, Cache & Sharding",
        "OOP Design Patterns & SOLID Principles",
        "aptitude logical puzzles",
    ],
    "Data Science": [
        "Pandas Data Wrangling & Vectorized Transformations",
        "SQL Window Functions, CTEs & Complex Joins",
        "Machine Learning Loss Functions & Optimization",
        "Classification Metrics: ROC-AUC, Precision-Recall & F1",
        "Feature Engineering & Handling Imbalanced Data",
        "Probability, Bayes Theorem & Statistical Inference",
        "Deep Learning Backpropagation & Gradient Descent",
        "DSA for Data Science Interviews",
    ],
    "Core CS": [
        "OS Deadlocks, Virtual Memory & Page Replacement",
        "Computer Networks TCP/UDP, 3-Way Handshake & DNS",
        "DBMS Concurrency Control & Normalization (BCNF/3NF)",
        "Computer Architecture Cache Coherence & Pipelining",
        "DSA Core Logic & Algorithms",
        "aptitude & quantitative analysis",
    ],
    "General SDE": [
        "DSA Problem Solving",
        "DBMS Core Queries & Design",
        "Operating Systems",
        "Computer Networks",
        "System Design Basics",
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
