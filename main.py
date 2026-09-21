import os
import logging
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import session as session_mgr
from agent import run_agent
from tools import gmail_tools, calendar_tools

logger = logging.getLogger("layla.main")

app = FastAPI(title="Layla Voice Agent")

GREETING_TRIGGERS = {"hi mike", "hey mike", "hello mike", "hi", "hello", "hey"}

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
    except Exception as e:
        logger.error("run_agent failed (%s): %s", type(e).__name__, e)
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
        emails_text = gmail_tools.read_emails(max_results=5)
        email_lines = [l for l in emails_text.split("\n\n") if l.strip()]
        email_count = len(email_lines)
        return f"Hi! I'm Mike. You have {email_count} new email{'s' if email_count != 1 else ''}. Want me to read them?"
    except Exception:
        return "Hi! I'm Mike, ready to help. What would you like to do?"
