import os
import json
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
import google.api_core.exceptions

import session as session_mgr
import memory
from tools import gmail_tools, calendar_tools

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# ---------------------------------------------------------------------------
# Tool registry — maps function name -> callable
# ---------------------------------------------------------------------------
TOOL_HANDLERS = {
    # Gmail
    "read_emails": lambda args: gmail_tools.read_emails(**args),
    "search_emails": lambda args: gmail_tools.search_emails(**args),
    "get_full_email": lambda args: gmail_tools.get_full_email(**args),
    "send_email": lambda args: gmail_tools.send_email(**args),
    "reply_email": lambda args: gmail_tools.reply_email(**args),
    "archive_email": lambda args: gmail_tools.archive_email(**args),
    # Calendar
    "read_calendar": lambda args: calendar_tools.read_calendar(**args),
    "list_calendars": lambda args: calendar_tools.list_calendars(**args),
    "create_event": lambda args: calendar_tools.create_event(**args),
    "modify_event": lambda args: calendar_tools.modify_event(**args),
    "delete_event": lambda args: calendar_tools.delete_event(**args),
    # Memory
    "add_memory": lambda args: memory.add_memory(**args),
    "forget_memory": lambda args: memory.forget_memory(**args),
}

# ---------------------------------------------------------------------------
# Gemini tool declarations (schema for function calling)
# ---------------------------------------------------------------------------
GEMINI_TOOLS = Tool(function_declarations=[
    FunctionDeclaration(
        name="read_emails",
        description="Read the latest emails from the Primary inbox.",
        parameters={"type": "object", "properties": {
            "max_results": {"type": "integer", "description": "Number of emails to fetch (default 5)"},
        }},
    ),
    FunctionDeclaration(
        name="search_emails",
        description="Search emails using Gmail search syntax, e.g. 'from:sarah', 'subject:invoice', 'is:unread'.",
        parameters={"type": "object", "properties": {
            "query": {"type": "string", "description": "Gmail search query"},
            "max_results": {"type": "integer", "description": "Max results (default 5)"},
        }, "required": ["query"]},
    ),
    FunctionDeclaration(
        name="get_full_email",
        description="Read the full body text of a specific email by its ID.",
        parameters={"type": "object", "properties": {
            "email_id": {"type": "string", "description": "The email message ID"},
        }, "required": ["email_id"]},
    ),
    FunctionDeclaration(
        name="send_email",
        description="Send a new email.",
        parameters={"type": "object", "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body text"},
        }, "required": ["to", "subject", "body"]},
    ),
    FunctionDeclaration(
        name="reply_email",
        description="Reply to an existing email by its ID.",
        parameters={"type": "object", "properties": {
            "email_id": {"type": "string", "description": "The original email ID to reply to"},
            "body": {"type": "string", "description": "The reply text"},
        }, "required": ["email_id", "body"]},
    ),
    FunctionDeclaration(
        name="archive_email",
        description="Archive an email by removing it from the inbox.",
        parameters={"type": "object", "properties": {
            "email_id": {"type": "string", "description": "The email ID to archive"},
        }, "required": ["email_id"]},
    ),
    FunctionDeclaration(
        name="read_calendar",
        description="Read upcoming calendar events.",
        parameters={"type": "object", "properties": {
            "days_ahead": {"type": "integer", "description": "Days ahead to look (1 = today, 7 = this week)"},
        }},
    ),
    FunctionDeclaration(
        name="list_calendars",
        description="List all available calendars for the user.",
        parameters={"type": "object", "properties": {}},
    ),
    FunctionDeclaration(
        name="create_event",
        description="Create a new calendar event.",
        parameters={"type": "object", "properties": {
            "title": {"type": "string"},
            "start": {"type": "string", "description": "ISO datetime, e.g. 2026-06-10T14:00:00"},
            "end": {"type": "string", "description": "ISO datetime, e.g. 2026-06-10T15:00:00"},
            "description": {"type": "string"},
            "calendar_id": {"type": "string", "description": "Calendar ID (default: primary)"},
        }, "required": ["title", "start", "end"]},
    ),
    FunctionDeclaration(
        name="modify_event",
        description="Modify an existing calendar event. Only provided fields are changed. Preserves duration if only new_start is given.",
        parameters={"type": "object", "properties": {
            "event_id": {"type": "string"},
            "title": {"type": "string"},
            "new_start": {"type": "string", "description": "New start ISO datetime"},
            "new_end": {"type": "string", "description": "New end ISO datetime"},
            "description": {"type": "string"},
            "calendar_id": {"type": "string"},
        }, "required": ["event_id"]},
    ),
    FunctionDeclaration(
        name="delete_event",
        description="Delete a calendar event by its ID.",
        parameters={"type": "object", "properties": {
            "event_id": {"type": "string"},
            "calendar_id": {"type": "string"},
        }, "required": ["event_id"]},
    ),
    FunctionDeclaration(
        name="add_memory",
        description="Store a long-term memory about the user. Category must be one of: facts, preferences, contacts.",
        parameters={"type": "object", "properties": {
            "category": {"type": "string", "description": "One of: facts, preferences, contacts"},
            "key": {"type": "string", "description": "Memory key, e.g. 'meeting_preference'"},
            "value": {"type": "string", "description": "Memory value, e.g. 'mornings'"},
        }, "required": ["category", "key", "value"]},
    ),
    FunctionDeclaration(
        name="forget_memory",
        description="Remove a specific long-term memory by category and key.",
        parameters={"type": "object", "properties": {
            "category": {"type": "string"},
            "key": {"type": "string"},
        }, "required": ["category", "key"]},
    ),
])

# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------
_main_model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    tools=[GEMINI_TOOLS],
)

_compact_model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")


# Tools that change real data — require spoken confirmation before executing
DESTRUCTIVE_TOOLS = {"send_email", "reply_email", "delete_event"}

CONFIRM_WORDS = {"yes", "yeah", "yep", "go ahead", "do it", "send it", "send",
                 "confirm", "ok", "okay", "sure", "please", "correct", "that's right"}
CANCEL_WORDS = {"no", "nope", "cancel", "stop", "don't", "abort",
                "never mind", "nevermind", "wait", "hold on"}


def _is_confirmation(message: str) -> bool:
    lowered = message.lower().strip().rstrip(".,!")
    if any(w in lowered for w in CANCEL_WORDS):
        return False
    return any(w in lowered for w in CONFIRM_WORDS)


def _is_cancellation(message: str) -> bool:
    lowered = message.lower().strip().rstrip(".,!")
    return any(w in lowered for w in CANCEL_WORDS)


def _build_confirmation_prompt(tool: str, args: dict) -> str:
    if tool == "send_email":
        return f"I'll send an email to {args.get('to', 'that address')} with subject \"{args.get('subject', '')}\". Shall I go ahead?"
    if tool == "reply_email":
        return "I'll send that reply. Shall I go ahead?"
    if tool == "delete_event":
        return "I'll permanently delete that calendar event. Shall I go ahead?"
    return "Shall I go ahead?"


def _build_system_prompt(user_id: str) -> str:
    mem_block = memory.build_memory_prompt()
    return f"""You are Layla, a voice AI personal assistant. You are helpful, concise, and action-oriented.
You DO things — you send real emails, create real calendar events, search the web — not just tell the user how to do them.
Keep responses short and natural for voice (1-3 sentences unless reading email content).
Never say "I cannot" if you have a tool for it — just use it.
When the user says goodbye (e.g. "goodbye", "bye", "that's all", "stop"), end your reply with the exact string: [ACTION:STOP]

Today's date and time: {datetime.now().strftime("%A, %d %B %Y, %H:%M")}. Use this to interpret relative dates like "tomorrow", "Friday", "next week".

{f"Long-term memory about this user:{chr(10)}{mem_block}" if mem_block else ""}
""".strip()


def run_agent(user_id: str, message: str) -> tuple[str, str]:
    """
    Run the Gemini agent for a given user message.
    Returns (reply_text, action) where action is "stop" or "continue".
    """
    # Handle pending confirmation from previous turn
    pending = session_mgr.get_pending_action(user_id)
    if pending:
        if _is_cancellation(message):
            session_mgr.clear_pending_action(user_id)
            reply = "No problem, I've cancelled that."
            session_mgr.append_message(user_id, "user", message)
            session_mgr.append_message(user_id, "assistant", reply)
            return reply, "continue"

        if _is_confirmation(message):
            session_mgr.clear_pending_action(user_id)
            session_mgr.append_message(user_id, "user", message)
            try:
                handler = TOOL_HANDLERS[pending["tool"]]
                result = handler(pending["args"])
                reply = f"Done. {result}"
            except Exception as e:
                reply = f"Sorry, that didn't work. {str(e)}"
            session_mgr.append_message(user_id, "assistant", reply)
            return reply, "continue"

        # Ambiguous response — ask again
        session_mgr.append_message(user_id, "user", message)
        reply = f"Just to confirm — {pending['summary']} Shall I go ahead? Say yes or no."
        session_mgr.append_message(user_id, "assistant", reply)
        return reply, "continue"

    # Compact history if needed
    session_mgr.maybe_compact(user_id, _compact_model)

    # Append user message to history
    session_mgr.append_message(user_id, "user", message)
    history = session_mgr.get_history(user_id)

    # Build contents list for Gemini
    system_prompt = _build_system_prompt(user_id)
    contents = [{"role": "user", "parts": [{"text": system_prompt + "\n\nUser: " + history[0]["content"]}]}]

    for msg in history[1:]:
        role = "user" if msg["role"] in ("user", "system") else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    # Agentic loop
    max_iterations = 10
    for _ in range(max_iterations):
        try:
            response = _main_model.generate_content(contents)
        except google.api_core.exceptions.ResourceExhausted:
            return "I'm a bit busy right now. Please try again in a moment.", "continue"
        except google.api_core.exceptions.GoogleAPIError as e:
            return "I ran into a problem reaching my brain. Please try again.", "continue"

        candidate = response.candidates[0]
        content = candidate.content

        # Check for function calls
        function_calls = [p for p in content.parts if hasattr(p, "function_call") and p.function_call.name]

        if not function_calls:
            # Final text response
            text = "".join(p.text for p in content.parts if hasattr(p, "text") and p.text).strip()
            if not text:
                try:
                    text = response.text.strip()
                except Exception:
                    text = "I processed that but had trouble forming a reply. Please try again."
            if not text:
                text = "I processed that but had trouble forming a reply. Please try again."
            session_mgr.append_message(user_id, "assistant", text)

            action = "continue"
            if "[ACTION:STOP]" in text:
                text = text.replace("[ACTION:STOP]", "").strip()
                action = "stop"
                session_mgr.end_session(user_id)

            return text, action

        # Check for destructive tools before executing — ask confirmation first
        for part in function_calls:
            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args) if part.function_call.args else {}
            if fn_name in DESTRUCTIVE_TOOLS:
                prompt = _build_confirmation_prompt(fn_name, fn_args)
                session_mgr.set_pending_action(user_id, fn_name, fn_args, prompt)
                session_mgr.append_message(user_id, "assistant", prompt)
                return prompt, "continue"

        # Execute all non-destructive tool calls
        contents.append(content)
        tool_results = []

        for part in function_calls:
            fn = part.function_call
            fn_name = fn.name
            fn_args = dict(fn.args) if fn.args else {}

            try:
                handler = TOOL_HANDLERS.get(fn_name)
                if handler:
                    result = handler(fn_args)
                else:
                    result = f"Unknown tool: {fn_name}"
            except Exception as e:
                result = f"Error running {fn_name}: {str(e)}"

            tool_results.append({
                "function_response": {
                    "name": fn_name,
                    "response": {"result": result},
                }
            })

        contents.append({"role": "user", "parts": tool_results})

    return "I'm sorry, I got stuck trying to complete that. Please try again.", "continue"
