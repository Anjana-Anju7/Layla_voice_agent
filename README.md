# Layla — Voice AI Personal Assistant

Layla is a voice-driven AI assistant built for blind and visually impaired users. Say **"Hi Layla"** and have a natural spoken conversation — she reads your emails, manages your calendar, searches the web, and remembers things about you. No screen interaction required at any point.


---

## Demo

```
"Hi Layla"              → She greets you and reports new emails and today's events
"Read my latest emails" → She reads them aloud
"Reply to the first one saying I'll be there by Friday"
                        → "I'll send a reply to Sarah. Shall I go ahead?"
"Yes"                   → Reply sent
"What's the weather in London?"
                        → Real-time answer 
"Add a team meeting tomorrow at 2pm"
                        → Event created in Google Calendar
"Goodbye"               → Session ends
```

---

## Features

### Email (Gmail)
- Read latest emails from your inbox
- Search by sender, subject, or keyword
- Send new emails with spoken confirmation before sending
- Reply to emails in-thread
- Archive emails
- Read full email body on request

### Calendar (Google Calendar)
- View today's or this week's events
- Create new events
- Modify events — reschedules preserve original duration automatically
- Delete events with spoken confirmation before deleting
- Supports multiple calendars
- Timezone-aware — all times are read/written in a configurable local timezone (`USER_TIMEZONE`, default `Europe/London`)


### Web Search
- Real-time answers via DuckDuckGo search
- Weather, news, directions, general knowledge

### Memory
- **Long-term memory** — remembers your contacts, preferences, and facts across sessions forever
  - *"Remember I prefer morning meetings"* → recalled in every future session
  - *"Forget my coffee preference"* → removed
  - Email contacts auto-learned from your inbox
- **Session memory** — retains conversation context for 2 hours with smart compaction after 20 messages

### Accessibility
- Fully voice-driven — no screen interaction at any step
- Speaks confirmation before any destructive action (send, delete)
- Clean spoken error messages — no raw API errors read aloud
- Built specifically for blind and visually impaired users

---

## Architecture

```
iPhone (iOS Shortcut)              Server (Python / Render)
┌─────────────────────┐            ┌──────────────────────────────────┐
│                     │   HTTPS    │  FastAPI  /api/chat               │
│  "Hi Layla"         │ ────────>  │    │                              │
│  (Vocal Shortcut)   │            │    ├── Greeting? → Fast path      │
│                     │            │    │   (zero LLM, <1s)            │
│  iOS Shortcut loop: │            │    │                              │
│  1. Dictate Text    │            │    └── Agent path →               │
│  2. Speak "On it"   │            │        Gemini 3.5 Flash Lite      │
│  3. POST to server  │ <────────  │          ├── Gmail tools (6)      │
│  4. Speak reply     │   JSON     │          ├── Calendar tools (5)   │
│  5. Repeat          │            │          ├── Web Search            │
│                     │            │          └── Memory tools (2)     │
└─────────────────────┘            └──────────────────────────────────┘
```

---

## Stack

| Layer | Technology |
|---|---|
| LLM | Gemini 3.5 Flash Lite |
| Web Search | DuckDuckGo (ddgs) |
| Backend | FastAPI + Uvicorn |
| Email | Gmail API |
| Calendar | Google Calendar API |
| Auth | OAuth2 (google-auth-oauthlib) |
| Memory | JSON file on persistent disk |
| Voice (STT + TTS) | iOS Shortcuts (on-device) |
| Deployment | Render |

---

## Project Structure

```
├── main.py               # FastAPI server — /api/chat endpoint, fast greeting path
├── agent.py              # Gemini agent — 13 tools, confirmation flow, agentic loop
├── session.py            # Session manager — 2hr TTL, history compaction, pending actions
├── memory.py             # Long-term memory — contacts, facts, preferences
├── auth.py               # Google OAuth2 — credential loading and caching
├── generate_token.py     # One-time OAuth token generator
├── tools/
│   ├── gmail_tools.py       # read, search, send, reply, archive, get_full_email
│   ├── calendar_tools.py    # read, create, modify, delete, list_calendars (timezone-aware)
│   └── web_search_tools.py  # DuckDuckGo web search (ddgs)
├── render.yaml           # Render deployment config with persistent disk
├── requirements.txt
└── .env.example          # Environment variable template
```

---

## Setup

### Prerequisites
- Python 3.11+
- A Google account
- A Google Cloud project with Gmail API and Google Calendar API enabled
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
- An iPhone (for the voice interface)

### 1 — Clone and install

```bash
git clone https://github.com/Anjana-Anju7/Layla_voice_agent.git
cd Layla_voice_agent
pip install -r requirements.txt
```

### 2 — Google Cloud setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → enable **Gmail API** and **Google Calendar API**
3. Configure **OAuth consent screen** → External → add your email as a test user → add scopes:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/calendar`
4. Create **OAuth 2.0 credentials** → Desktop app → download as `credentials.json`
5. Place `credentials.json` in the project root

### 3 — Generate your Google token

```bash
python generate_token.py
```

Opens a browser → sign in → grant permissions → creates `token.json`.

### 4 — Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_CREDENTIALS_JSON=<full contents of credentials.json>
GOOGLE_TOKEN_JSON=<full contents of token.json>
LAYLA_API_KEY=your-secret-key-here
MEMORY_FILE_PATH=memory.json
USER_TIMEZONE=Europe/London
```

### 5 — Run locally

```bash
uvicorn main:app --reload --port 8000
```

Test:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-key-here" \
  -d '{"message": "hi layla", "user_id": "your-name"}'
```

---

## Deploying to Render

1. Push your code to GitHub (without `.env` — it is gitignored)
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo
3. Render detects `render.yaml` automatically → click **Apply**
4. In the **Environment** tab add 4 secrets:

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `GOOGLE_CREDENTIALS_JSON` | Full contents of `credentials.json` |
| `GOOGLE_TOKEN_JSON` | Full contents of `token.json` |
| `LAYLA_API_KEY` | Your chosen secret key |

5. Click **Save Changes** → Render deploys automatically

---

## iOS Shortcut Setup

Create a shortcut named **Layla** with these actions inside a **Repeat** loop:

| Step | Action | Setting |
|---|---|---|
| 1 | **Dictate Text** | Stop: After pause |
| 2 | **Speak Text** | Text: `On it` · Wait until finished: ON |
| 3 | **URL** | `https://your-render-url.onrender.com/api/chat` |
| 4 | **Get Contents of URL** | POST · Headers: `Content-Type: application/json`, `x-api-key: your-secret-key` · Body: JSON `message` = Dictated Text, `user_id` = your name |
| 5 | **Get Dictionary Value** | Key: `reply` from Contents of URL |
| 6 | **Speak Text** | Dictionary Value · Wait until finished: ON |
| 7 | **Get Dictionary Value** | Key: `should_stop` from Contents of URL |
| 8 | **If** value = `true` | Exit Shortcut |

**Hands-free activation:** Settings → Accessibility → Vocal Shortcuts → Add → *"Hi Layla"*

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Gemini API key from Google AI Studio |
| `GOOGLE_CREDENTIALS_JSON` | Yes | Full JSON from Google Cloud OAuth credentials download |
| `GOOGLE_TOKEN_JSON` | Yes | Full JSON from `token.json` after running `generate_token.py` |
| `LAYLA_API_KEY` | Yes | Secret key to protect the `/api/chat` endpoint |
| `MEMORY_FILE_PATH` | No | Path for memory file. Default: `memory.json`. On Render: `/data/memory.json` |
| `USER_TIMEZONE` | No | IANA timezone for interpreting relative dates and calendar events. Default: `Europe/London` |

---



