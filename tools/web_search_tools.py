import logging
from duckduckgo_search import DDGS

logger = logging.getLogger("layla.websearch")


def web_search(query: str) -> str:
    """
    Search the web using DuckDuckGo (free, no API key required).
    Returns formatted results for the main Gemini model to synthesize.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=4))
        logger.info("DDG search '%s': %d results", query, len(results))
    except Exception as e:
        logger.error("DDG search failed (%s): %s", type(e).__name__, e)
        return f"Web search failed: {type(e).__name__}: {str(e)}"

    if not results:
        logger.warning("DDG search '%s': no results returned", query)
        return "No results found for that search."

    formatted = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        if title or body:
            formatted.append(f"{title}: {body}")

    return "\n\n".join(formatted)[:2000]
