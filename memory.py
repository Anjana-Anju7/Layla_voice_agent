import os
import json
from typing import Any

MEMORY_FILE = os.getenv("MEMORY_FILE_PATH", "memory.json")


def _load() -> dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {"facts": {}, "preferences": {}, "contacts": {}}


def _save(data: dict):
    os.makedirs(os.path.dirname(MEMORY_FILE) if os.path.dirname(MEMORY_FILE) else ".", exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_all_memories() -> dict:
    """Return all stored long-term memories."""
    return _load()


def add_memory(category: str, key: str, value: Any) -> str:
    """
    Store a memory. Category is one of: facts, preferences, contacts.
    Example: add_memory('preferences', 'meeting_time', 'mornings')
    """
    data = _load()
    if category not in data:
        data[category] = {}
    data[category][key] = value
    _save(data)
    return f"Remembered: {key} = {value}"


def forget_memory(category: str, key: str) -> str:
    """Remove a specific memory by category and key."""
    data = _load()
    if category in data and key in data[category]:
        del data[category][key]
        _save(data)
        return f"Forgotten: {key}"
    return f"No memory found for {key} in {category}"


def learn_contact(email: str, name: str):
    """Auto-learn a contact from an email sender."""
    data = _load()
    if email not in data["contacts"]:
        data["contacts"][email] = name
        _save(data)


def build_memory_prompt() -> str:
    """Format all memories as a system prompt block."""
    data = _load()
    lines = []

    if data.get("preferences"):
        lines.append("User preferences:")
        for k, v in data["preferences"].items():
            lines.append(f"  - {k}: {v}")

    if data.get("facts"):
        lines.append("Known facts about the user:")
        for k, v in data["facts"].items():
            lines.append(f"  - {k}: {v}")

    if data.get("contacts"):
        lines.append("Known contacts:")
        for email, name in data["contacts"].items():
            lines.append(f"  - {name} <{email}>")

    return "\n".join(lines) if lines else ""
