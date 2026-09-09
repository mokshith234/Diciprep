# PlacementPrep AI

An **autonomous, multi-channel AI placement coach** that lives on WhatsApp & Telegram. Students get daily capsules, adaptive difficulty drills, instant Gemini-powered grading, progressive hints, topic analytics, and a competitive leaderboard — all inside their messaging app.

Built with the **Caspian SDK** (multi-channel agent framework) + **FastAPI** + **Google Gemini 2.5 Flash**.

## Features

- **Multi-channel** — same agent on WhatsApp *and* Telegram (Caspian SDK)
- **Adaptive difficulty** — auto-promotes (easy → medium → hard) after 3 good scores, auto-demotes after 3 bad
- **3-question mock drills** with instant structured grading (verdict, score 1–10, optimal code, complexity)
- **Progressive hint system** — 2 hints per question (gentle nudge → stronger approach outline)
- **Topic-wise analytics** — per-topic average score and attempt breakdown
- **Leaderboard** — top 10 by accuracy with medals
- **Follow-up tutoring** — ask "explain line 4", "why O(n)?", "edge cases?" without re-grading
- **Morning capsule (8 AM)** — industry fact + CS concept + interview tip + question
- **Evening streak reminder (8 PM)** — nudge inactive students
- **Weekly progress report (Sunday 10 AM)** — AI-generated strengths, weak areas, goals
- **Gamification** — calendar-day streaks, accuracy tracking, difficulty levels

## Commands

| Message | Action |
|---|---|
| `hi` / `/start` | Onboard + pick track (SDE / Data Science / Core CS) |
| `drill` | 3-question adaptive mock |
| `hint` | Get a nudge without the answer (max 2 per question) |
| `solution` / `skip` | Show optimal solution + edge cases |
| `streak` / `stats` | Streak, questions solved, accuracy, level |
| `score` / `readiness` | Real-time placement readiness score & gap diagnostic |
| `fix <topic>` | 1-click drill to repair chosen technical weakness |
| `resume: <text>` | AI resume scoring (0-100), gap audit, and tailored drill |
| `judge` / `/judge` / `/metrics` | **Hackathon Judge Telemetry Report** (live message counts & API links) |
| `topics` | Per-topic performance breakdown |
| `level` | Current difficulty + progress to next level |
| `leaderboard` / `lb` | Top 10 students by accuracy |
| `help` | Command reference |
| anything else | Grade if a question is open; otherwise mentor-mode Q&A |

## ⚖️ Hackathon Judge Verification & Message Tracking

For judges evaluating the agent, PlacementPrep AI provides multiple redundant ways to track and audit message volume, system responsiveness, and Caspian Gateway synchronization:

### 1. Programmatic REST API Endpoints

Judges can query these endpoints at any time to verify real-time message volume and candidate activity:

| Endpoint | Method | Description | Sample Output Field |
|---|---|---|---|
| `/api/stats` | `GET` | **Complete telemetry** (total messages, inbound, outbound, buttons, drills, Caspian sync status) | `{"metrics": {"total_messages": 142, "inbound_messages": 68, "outbound_messages": 74, ...}}` |
| `/api/messages/count` | `GET` | **Lightweight counter** for automated grading & evaluation scripts | `{"total_messages": 142, "inbound": 68, "outbound": 74, "buttons": 38}` |
| `/api/messages` | `GET` | **Audit log stream** with timestamps, channels, sender IDs, and message snippets (`?limit=50`) | `{"messages": [{"id": 1, "channel": "telegram", "direction": "inbound", ...}]}` |
| `/api/caspian/stats` | `GET` | **Direct Caspian Gateway telemetry** fetched live from `api.trycaspianai.com/v1/conversations` | `{"total_conversations": 1, "total_messages_on_caspian_api": 86}` |
| `/health` | `GET` | Health check endpoint including `messages_tracked`, `inbound`, `outbound`, `buttons` | `{"status": "ok", "messages_tracked": 142}` |
| `/docs` | `GET` | **Interactive Swagger UI** to test and inspect all API endpoints directly in the browser | — |

### 2. In-Chat Verification (Telegram & WhatsApp)

Judges testing the live bot directly in Telegram ([@Diciprepbot](https://t.me/Diciprepbot)) or WhatsApp can send:
- `/judge` or `/metrics` or `/audit`

The bot immediately generates an interactive **Hackathon Judge Telemetry Card** displaying live message counts, button interactions, Caspian Gateway sync status, and API links.

### 3. Dual-Dispatch Architecture

To guarantee both 100% real-time reliability and full Caspian Hackathon compliance:
1. **Direct Telegram Bot API Send**: Delivers immediate responses with native inline keyboard buttons, eliminating latency and avoiding 24-hour reply window locks.
2. **Asynchronous Caspian Gateway Sync**: Simultaneously syncs every outbound response to Caspian Gateway API (`POST /v1/conversations/{conv_id}/messages`), ensuring Caspian's platform and dashboard register all message traffic for hackathon scoring.
3. **Persistent Message Ledger**: Every inbound message, outbound response, and button click is recorded in SQLite/PostgreSQL for complete auditability.


## Quick Start

### 1. Prerequisites

You will need the following API keys / tokens:

| Credential | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `WHATSAPP_ACCESS_TOKEN` | [Meta Developer Portal](https://developers.facebook.com) → Your App → WhatsApp → API Setup |
| `WHATSAPP_PHONE_NUMBER_ID` | Same page as above (Phone Number ID) |
| `WHATSAPP_APP_SECRET` | Meta Developer Portal → Your App → Settings → Basic → App Secret |
| `WHATSAPP_VERIFY_TOKEN` | Any random string you choose (used for webhook verification) |
| `TELEGRAM_BOT_TOKEN` | Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` |

### 2. Local Setup

```bash
# Clone and install
copy .env.example .env
# Fill in your API keys in .env
pip install -r requirements.txt

# Expose HTTPS (use ngrok or similar)
ngrok http 8080

# Start the API
uvicorn app:app --host 0.0.0.0 --port 8080
```

### 3. Configure Webhooks

**WhatsApp:**
1. In Meta Developer Portal, set webhook callback URL to `https://<your-host>/webhook`
2. Set verify token to your `WHATSAPP_VERIFY_TOKEN`
3. Subscribe to `messages`

**Telegram:**
1. Set the Telegram webhook:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<your-host>/telegram"
```

### 4. Test It

Message the WhatsApp business number or your Telegram bot with `hi`.

SQLite (`placementprep.db`) is used when `DATABASE_URL` is unset.

## Render Deployment

`render.yaml` defines a Python web service bound to `0.0.0.0:$PORT` and a Postgres database. Set all secrets in the Render dashboard.

- Health check: `GET /health`
- WhatsApp webhook: `https://<service>.onrender.com/webhook`
- Telegram webhook: `https://<service>.onrender.com/telegram`

Free web services sleep after inactivity, which pauses APScheduler. Use a Render cron (or any ping) against:

```
POST /jobs/morning?secret=CRON_SECRET
POST /jobs/evening?secret=CRON_SECRET
POST /jobs/weekly?secret=CRON_SECRET
```

WhatsApp only allows free-form outbound messages inside the 24-hour customer-care window. Morning capsules work for students who messaged recently; older threads need a pre-approved template.

## Architecture

```
  Meta WhatsApp Cloud API          Telegram Bot API
         │                              │
  (POST /webhook)                (POST /telegram)
         ▼                              ▼
  ┌──────────────── app.py (FastAPI) ──────────────┐
  │      cx.channels.add("whatsapp")               │
  │      cx.channels.add("telegram")               │
  └──────────────────┬─────────────────────────────┘
                     ▼
          cx.handle(channel, body, headers)
                     │
              ┌──────┴──────┐
              │   bot.py    │  Channel-agnostic handlers
              ├─────────────┤
              │ commands.py │  Command parsing & aliases
              │ db.py       │  SQLite / Postgres persistence
              │ llm.py      │  Gemini 2.5 Flash integration
              │ prompts.py  │  System prompts & difficulty descriptors
              │ outbound.py │  Chunked outbound sends
              │ jobs.py     │  Scheduled proactive engagement
              └─────────────┘
```

## Tests

```bash
pip install pytest
pytest -q
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12 |
| Agent Framework | Caspian SDK (`caspian-sdk`) |
| LLM | Google Gemini 2.5 Flash (`google-genai`) |
| Web Framework | FastAPI + Uvicorn |
| Scheduler | APScheduler |
| Database | SQLite (dev) / PostgreSQL (prod) |
| HTTP Client | httpx |
| Deployment | Render |
