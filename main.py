import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import session as session_mgr
from agent import run_agent
from tools import gmail_tools, calendar_tools

app = FastAPI(title="Layla Voice Agent")

GREETING_TRIGGERS = {"hi layla", "hey layla", "hello layla", "hi", "hello", "hey"}

# Set LAYLA_API_KEY in your .env and Render environment variables
_API_KEY = os.getenv("LAYLA_API_KEY", "")


def _check_api_key(x_api_key: str = Header(default="")):
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(req: ChatRequest, x_api_key: str = Header(default="")):
    _check_api_key(x_api_key)
    message = req.message.strip()
    user_id = req.user_id

    # Fast greeting path — bypass LLM entirely
    if message.lower().rstrip(".,!") in GREETING_TRIGGERS:
        reply = await _greeting_fast_path(user_id)
        return JSONResponse({"reply": reply, "action": "continue", "should_stop": None})

    # Main agent path
    try:
        reply, action = run_agent(user_id, message)
    except Exception:
        reply = "Sorry, something went wrong. Please try again."
        action = "continue"

    return JSONResponse({"reply": reply, "action": action, "should_stop": True if action == "stop" else None})


async def _greeting_fast_path(user_id: str) -> str:
    """
    Build a greeting without calling the LLM.
    Fetches new email count and today's event count directly from APIs.
    """
    prev_end = session_mgr.get_prev_session_end(user_id)

    # Fetch email and calendar data in parallel via separate API calls
    email_summary = ""
    calendar_summary = ""

    try:
        # New emails since last session (or last 24h if first session)
        since_label = "since your last session" if prev_end else "in the last 24 hours"
        emails_text = gmail_tools.read_emails(max_results=5)
        email_lines = [l for l in emails_text.split("\n\n") if l.strip()]
        email_count = len(email_lines)
        email_summary = f"You have {email_count} recent email{'s' if email_count != 1 else ''}."
    except Exception:
        email_summary = ""

    try:
        events_text = calendar_tools.read_calendar(days_ahead=1)
        if "No events" in events_text:
            calendar_summary = "Nothing on your calendar today."
        else:
            event_count = len([l for l in events_text.split("\n") if l.strip().startswith("-")])
            calendar_summary = f"You have {event_count} event{'s' if event_count != 1 else ''} today."
    except Exception:
        calendar_summary = ""

    parts = ["Hi! I'm Layla, ready to help."]
    if email_summary:
        parts.append(email_summary)
    if calendar_summary:
        parts.append(calendar_summary)
    parts.append("What would you like to do?")

    return " ".join(parts)
