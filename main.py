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
        session_mgr.append_message(user_id, "user", message)
        session_mgr.append_message(user_id, "assistant", reply)
        return JSONResponse({"reply": reply, "action": "continue", "should_stop": None})

    # Main agent path
    try:
        reply, action = run_agent(user_id, message)
    except Exception as e:
        logger.error("run_agent failed (%s): %s", type(e).__name__, e)
        reply = "Sorry, something went wrong. Please try again."
        action = "continue"

    return JSONResponse({"reply": reply, "action": action, "should_stop": True if action == "stop" else None})


GREETING_MAX_COUNT = 10


async def _greeting_fast_path(user_id: str) -> str:
    """
    Build a greeting without calling the LLM: reports the unread email count
    (capped at GREETING_MAX_COUNT so the spoken number stays digestible, e.g.
    "10+" instead of "247") and today's event count.
    """
    email_count = None
    event_count = None

    try:
        email_count = gmail_tools.count_unread_primary()
    except Exception:
        pass

    try:
        event_count = calendar_tools.count_today_events()
    except Exception:
        pass

    if email_count is None and event_count is None:
        return "Hi! I'm Mike, ready to help. What would you like to do?"

    parts = []
    has_something = False

    if email_count is not None:
        if email_count == 0:
            parts.append("no new emails")
        else:
            display = min(email_count, GREETING_MAX_COUNT)
            suffix = "+" if email_count > GREETING_MAX_COUNT else ""
            plural = "s" if display != 1 else ""
            parts.append(f"{display}{suffix} new email{plural}")
            has_something = True

    if event_count is not None:
        if event_count == 0:
            parts.append("nothing on your calendar today")
        else:
            plural = "s" if event_count != 1 else ""
            parts.append(f"{event_count} event{plural} today")
            has_something = True

    summary = " and ".join(parts)
    question = "Want me to go through them?" if has_something else "What would you like to do?"
    return f"Hi! I'm Mike. You have {summary}. {question}"
