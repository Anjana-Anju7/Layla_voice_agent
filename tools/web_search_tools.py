import os
import requests

_GEMINI_MODEL = "gemini-2.5-flash-lite"
_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent"


def web_search(query: str) -> str:
    """
    Search the web for current information (weather, news, sports, prices, etc.)
    using Gemini's Google Search grounding. Reuses GEMINI_API_KEY directly via the
    REST API, since the deprecated google-generativeai SDK doesn't reliably expose
    the google_search grounding tool alongside custom function-calling tools.
    """
    api_key = os.environ["GEMINI_API_KEY"]
    body = {
        "contents": [{"parts": [{"text": query}]}],
        "tools": [{"google_search": {}}],
    }

    resp = requests.post(
        _ENDPOINT,
        params={"key": api_key},
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        return "No web results found."

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        return "No web results found."

    return text[:2000]
