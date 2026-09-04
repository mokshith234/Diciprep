# 🔑 Complete API Key Setup Guide — PlacementPrep AI

You need **3 services** and **6 credentials** total. Follow each section step-by-step.

---

## 1️⃣ Google Gemini API Key (~2 minutes)

This powers all the AI — question generation, grading, hints, reports.

### Steps:

1. Go to → https://aistudio.google.com/apikey
2. Sign in with your **Google account**
3. Click **"Create API Key"**
4. Select **"Create API key in new project"** (or an existing project)
5. Copy the key — it looks like: `AIzaSy...` (39 characters)

### Paste in your `.env`:
```
GEMINI_API_KEY=AIzaSy_your_key_here
```

> 💡 The free tier gives you **15 requests/minute** and **1,500 requests/day** on Gemini 2.5 Flash — more than enough for a hackathon demo.

---

## 2️⃣ WhatsApp Cloud API (~15 minutes)

This gives you 4 credentials: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, and `WHATSAPP_VERIFY_TOKEN`.

### Step A — Create a Meta Developer Account

1. Go to → https://developers.facebook.com
2. Click **"Get Started"** (top right)
3. Log in with your **Facebook account** (or create one)
4. Accept the developer agreement
5. Verify your account (phone or email)

### Step B — Create an App

1. Go to → https://developers.facebook.com/apps/create/
2. Select app type: **"Business"**
3. Fill in:
   - **App name**: `PlacementPrep AI` (or anything you want)
   - **App contact email**: your email
   - **Business portfolio**: "I don't want to connect..." (skip for now)
4. Click **"Create App"**

### Step C — Add WhatsApp Product

1. On your app dashboard, scroll to **"Add products to your app"**
2. Find **"WhatsApp"** and click **"Set up"**
3. You'll land on the **WhatsApp > API Setup** page

### Step D — Get Your 4 Credentials

#### 🔹 Credential 1: `WHATSAPP_ACCESS_TOKEN`

1. On the **API Setup** page, you'll see a section called **"Temporary access token"**
2. Click **"Generate"** (valid for 24 hours — fine for hackathon)
3. Copy the token — it's a long string starting with `EAA...`

```
WHATSAPP_ACCESS_TOKEN=EAAGn...your_long_token
```

> ℹ️ For production, create a **System User** token (Settings → Business Settings → System Users → Generate Token). But for hackathon, the temporary token works perfectly.

#### 🔹 Credential 2: `WHATSAPP_PHONE_NUMBER_ID`

1. On the same **API Setup** page, look under **"From"**
2. You'll see a **test phone number** provided by Meta
3. Below it, there's a **Phone number ID** — a number like `101234567890123`
4. Copy it

```
WHATSAPP_PHONE_NUMBER_ID=101234567890123
```

#### 🔹 Credential 3: `WHATSAPP_APP_SECRET`

1. In the left sidebar, click **Settings → Basic**
2. Find **"App Secret"**
3. Click **"Show"** (enter your Facebook password)
4. Copy the secret — looks like: `abc123def456...`

```
WHATSAPP_APP_SECRET=abc123def456your_secret
```

#### 🔹 Credential 4: `WHATSAPP_VERIFY_TOKEN`

This is NOT from Meta — **you make it up yourself**. It's a shared secret between your server and Meta's webhook system.

Pick any random string:
```
WHATSAPP_VERIFY_TOKEN=my-placementprep-verify-2026
```

### Step E — Configure the Webhook

1. In left sidebar, click **WhatsApp → Configuration**
2. Under **Webhook**, click **"Edit"**
3. Fill in:
   - **Callback URL**: `https://<your-ngrok-or-render-url>/webhook`
   - **Verify token**: the same string you put in `WHATSAPP_VERIFY_TOKEN`
4. Click **"Verify and Save"**

> ⚠️ Your server MUST be running when you click "Verify and Save" — Meta sends a GET request to verify the webhook.

5. After saving, click **"Manage"** next to Webhook fields
6. Find **"messages"** and click **"Subscribe"** ✅

### Step F — Add Test Recipients

1. On the **API Setup** page, scroll to **"To"**
2. Click **"Manage phone number list"**
3. Add your own phone number (or any number you want to test with)
4. You'll receive a verification code via WhatsApp — enter it
5. You can add up to **5 test numbers** for free

---

## 3️⃣ Telegram Bot Token (~3 minutes)

### Steps:

1. Open **Telegram** on your phone or desktop
2. Search for **@BotFather** (official Telegram bot manager — has a blue checkmark ✅)
3. Start a chat and send: `/newbot`
4. BotFather asks: **"What name for your bot?"**
   - Type: `PlacementPrep AI` (display name, can have spaces)
5. BotFather asks: **"Choose a username"**
   - Type: `placementprep_ai_bot` (must end in `bot`, no spaces)
6. BotFather replies with your **token** — looks like:
   ```
   7123456789:AAF_your-token-string-here
   ```
7. Copy it

### Paste in your `.env`:
```
TELEGRAM_BOT_TOKEN=7123456789:AAF_your-token-string-here
```

### Set the Webhook (after your server is running):

```bash
curl -X POST "https://api.telegram.org/bot7123456789:AAF_your-token-string-here/setWebhook?url=https://<your-host>/telegram"
```

You should get back: `{"ok":true,"result":true,"description":"Webhook was set"}`

> 💡 Optional: Send `/setdescription` to @BotFather to set a bio, and `/setuserpic` to add a profile photo for your bot.

---

## 📋 Final `.env` File

After getting all credentials, your `.env` should look like this:

```env
# Google Gemini
GEMINI_API_KEY=AIzaSy_your_gemini_key

# Meta WhatsApp Cloud API
WHATSAPP_ACCESS_TOKEN=EAAGn_your_long_token
WHATSAPP_PHONE_NUMBER_ID=101234567890123
WHATSAPP_APP_SECRET=abc123def456_your_secret
WHATSAPP_VERIFY_TOKEN=my-placementprep-verify-2026

# Telegram Bot API
TELEGRAM_BOT_TOKEN=7123456789:AAF_your-token-here

# Optional: Postgres in production (SQLite used if unset)
# DATABASE_URL=postgresql://user:pass@host:5432/placementprep

# Cron job protection
CRON_SECRET=change-me-to-random-string
TIMEZONE=Asia/Kolkata
MORNING_HOUR=8
EVENING_HOUR=20

# Optional
PORT=8080
LOG_LEVEL=INFO
```

---

## 🚀 Launch Checklist

After filling in all keys:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start ngrok (separate terminal)
ngrok http 8080

# 3. Copy the ngrok HTTPS URL (e.g., https://abc123.ngrok-free.app)

# 4. Set WhatsApp webhook in Meta dashboard:
#    Callback URL = https://abc123.ngrok-free.app/webhook

# 5. Set Telegram webhook:
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://abc123.ngrok-free.app/telegram"

# 6. Start the server
uvicorn app:app --host 0.0.0.0 --port 8080

# 7. Test — send "hi" on WhatsApp or Telegram!
```

---

## 💰 Cost Summary

| Service | Free Tier |
|---------|-----------|
| **Gemini 2.5 Flash** | 15 RPM / 1,500 RPD — totally free |
| **WhatsApp Cloud API** | 1,000 free conversations/month |
| **Telegram Bot API** | Completely free, no limits |
| **Render (hosting)** | Free tier available (sleeps after inactivity) |
| **ngrok (local dev)** | Free tier — 1 tunnel |

> **Total cost for hackathon: ₹0** — everything runs on free tiers.
