import time
from typing import Optional
import google.generativeai as genai

SESSION_TTL = 2 * 60 * 60  # 2 hours in seconds
COMPACT_THRESHOLD = 20      # compact when history exceeds this many messages
COMPACT_KEEP = 10           # keep this many recent messages after compaction

# In-memory session store: user_id -> session dict
_sessions: dict[str, dict] = {}


def get_or_create_session(user_id: str) -> dict:
    """Return existing session or create a new one. Expires after SESSION_TTL."""
    now = time.time()
    session = _sessions.get(user_id)

    if session and (now - session["last_active"]) < SESSION_TTL:
        session["last_active"] = now
        return session

    # New session (or expired)
    last_end = session["session_end"] if session else None
    _sessions[user_id] = {
        "history": [],
        "started_at": now,
        "last_active": now,
        "session_end": None,
        "prev_session_end": last_end,
        "pending_action": None,
    }
    return _sessions[user_id]


def append_message(user_id: str, role: str, content: str):
    """Append a message to session history."""
    session = get_or_create_session(user_id)
    session["history"].append({"role": role, "content": content})


def get_history(user_id: str) -> list[dict]:
    session = get_or_create_session(user_id)
    return session["history"]


def end_session(user_id: str):
    """Mark the session as ended (called on goodbye)."""
    if user_id in _sessions:
        _sessions[user_id]["session_end"] = time.time()


def get_pending_action(user_id: str) -> Optional[dict]:
    session = _sessions.get(user_id)
    return session["pending_action"] if session else None


def set_pending_action(user_id: str, tool: str, args: dict, summary: str):
    session = get_or_create_session(user_id)
    session["pending_action"] = {"tool": tool, "args": args, "summary": summary}


def clear_pending_action(user_id: str):
    session = _sessions.get(user_id)
    if session:
        session["pending_action"] = None


def get_prev_session_end(user_id: str) -> Optional[float]:
    """Return the timestamp when the previous session ended, or None."""
    session = _sessions.get(user_id)
    return session["prev_session_end"] if session else None


def maybe_compact(user_id: str, model: genai.GenerativeModel) -> bool:
    """
    If history exceeds COMPACT_THRESHOLD, summarize the oldest messages
    into a single context block and replace them. Returns True if compacted.
    """
    session = get_or_create_session(user_id)
    history = session["history"]

    if len(history) <= COMPACT_THRESHOLD:
        return False

    to_summarize = history[:-COMPACT_KEEP]
    to_keep = history[-COMPACT_KEEP:]

    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in to_summarize
    )
    prompt = (
        "Summarize this conversation excerpt concisely, preserving all important "
        "details like names, email IDs, event IDs, decisions, and actions taken:\n\n"
        + conversation_text
    )

    response = model.generate_content(prompt)
    summary = response.text.strip()

    session["history"] = [
        {"role": "system", "content": f"[Earlier conversation summary]\n{summary}"}
    ] + to_keep

    return True
