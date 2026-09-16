from langchain_core.tools import tool
import config


def _ddg_search(query: str, max_results: int = 6) -> str:
    """
    Internal DuckDuckGo search with automatic fallback.
    Tries `ddgs` (v9+) first, then `duckduckgo_search` (v8).
    Returns a formatted string with Title / Link / Snippet for each result,
    so CitationTracker's URL regex can extract links reliably.
    """
    # --- primary: Tavily, optimized for LLM research ---
    if config.TAVILY_API_KEY:
        try:
            from tavily import TavilyClient
            results = TavilyClient(api_key=config.TAVILY_API_KEY).search(
                query=query, max_results=max_results, search_depth="basic"
            ).get("results", [])
            if results:
                return "\n\n".join(
                    f"Title: {r.get('title', '')}\nLink: {r.get('url', '')}\nSnippet: {r.get('content', '')}"
                    for r in results
                )
        except Exception:
            pass

    # --- fallback: ddgs package (v9+, better TLS fingerprinting) ---
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            parts = []
            for r in results:
                link = r.get("href") or r.get("url", "")
                parts.append(
                    f"Title: {r.get('title', '')}\n"
                    f"Link: {link}\n"
                    f"Snippet: {r.get('body', '')}"
                )
            return "\n\n".join(parts)
    except Exception:
        pass

    # --- fallback: duckduckgo_search package (v8) ---
    try:
        from duckduckgo_search import DDGS as DDGS2
        with DDGS2() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            parts = []
            for r in results:
                link = r.get("href") or r.get("url", "")
                parts.append(
                    f"Title: {r.get('title', '')}\n"
                    f"Link: {link}\n"
                    f"Snippet: {r.get('body', '')}"
                )
            return "\n\n".join(parts)
    except Exception as e:
        return f"Search failed: {e}"

    return "No results found."


@tool
def web_search(query: str) -> str:
    """Search the web for current information on any topic."""
    return _ddg_search(query, max_results=6)


def get_search_tool():
    return web_search


@tool
def quick_search(query: str) -> str:
    """Search the web and return top results for a query."""
    return _ddg_search(query, max_results=4)
