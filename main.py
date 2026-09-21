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


async def _greeting_fast_path(user_id: str) -> str:
    """
    Build a greeting without calling the LLM.
    Reports the actual unread count in the Primary inbox.
    """
    try:
        count = gmail_tools.count_unread_primary()
        if count == 0:
            return "Hi! I'm Mike. No new emails right now. What would you like to do?"
        plural = "s" if count != 1 else ""
        return f"Hi! I'm Mike. You have {count} new email{plural}. Want me to read them?"
    except Exception:
        return "Hi! I'm Mike, ready to help. What would you like to do?"
