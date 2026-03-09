"""
Citation tracker callback handler.
Intercepts LangChain tool outputs and extracts all URLs the researcher actually visited.
"""
import re
from typing import List, Any, Dict
from langchain_core.callbacks import BaseCallbackHandler

URL_PATTERN = re.compile(r'https?://[^\s\)\]\'"<>]+')


class CitationTracker(BaseCallbackHandler):
    """
    Intercepts LangChain tool outputs and extracts all URLs.
    Attach as a callback to the researcher agent.
    """

    def __init__(self):
        self.cited_urls: List[str] = []
        self.tool_calls: List[Dict] = []

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called after every tool (web_search) returns."""
        urls = URL_PATTERN.findall(str(output))
        for url in urls:
            # Clean trailing punctuation
            url = url.rstrip(".,;:!?)")
            if url not in self.cited_urls:
                self.cited_urls.append(url)
        self.tool_calls.append({
            "tool_name": kwargs.get("name", "unknown"),
            "url_count": len(urls),
        })

    def get_sources_markdown(self) -> str:
        """Returns a formatted Sources section."""
        if not self.cited_urls:
            return ""
        lines = ["## Sources\n"]
        for i, url in enumerate(self.cited_urls, 1):
            lines.append(f"{i}. {url}")
        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {
            "total_urls": len(self.cited_urls),
            "tool_calls": len(self.tool_calls),
            "urls": self.cited_urls[:20],  # cap for SSE JSON size
        }
