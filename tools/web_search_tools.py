from duckduckgo_search import DDGS


def web_search(query: str) -> str:
    """
    Search the web using DuckDuckGo (free, no API key required).
    Returns formatted results for the main Gemini model to synthesize.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
    except Exception as e:
        return f"Web search failed: {str(e)}"

    if not results:
        return "No results found for that search."

    formatted = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        if title or body:
            formatted.append(f"{title}: {body}")

    return "\n\n".join(formatted)[:2000]
