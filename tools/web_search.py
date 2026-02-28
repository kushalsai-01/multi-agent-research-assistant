from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import tool


def get_search_tool():
    return DuckDuckGoSearchResults(
        name="web_search",
        description="Search the web for current information on any topic.",
        max_results=6,
    )


@tool
def quick_search(query: str) -> str:
    """Search the web and return top results for a query."""
    try:
        ddg = DuckDuckGoSearchResults(max_results=4)
        return ddg.run(query)
    except Exception as e:
        return f"Search failed: {e}"
