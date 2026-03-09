"""
MCP Server for the AI Research Assistant.

Exposes 4 tools via the Model Context Protocol:
1. run_research(topic) - runs full pipeline, returns final report
2. get_report_by_id(report_id) - fetches a past report from Supabase
3. search_reports(query, top_k) - RAG semantic search over past reports
4. list_reports(limit) - lists recent reports

Run locally:
    python mcp_server/server.py

For Claude Desktop, add to claude_desktop_config.json:
{
  "mcpServers": {
    "research-assistant": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_server/server.py"],
      "env": {
        "GROQ_API_KEY": "your-key",
        "SUPABASE_URL": "your-url",
        "SUPABASE_KEY": "your-key"
      }
    }
  }
}
"""
import sys
import os

# Make sure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
import config
from agents.researcher import run_researcher
from agents.analyst import run_analyst, analyst_to_str
from agents.writer import run_writer, writer_to_markdown
from agents.reviewer import run_reviewer
from database import get_reports as db_get_reports, get_report as db_get_report
from rag import search_similar_reports

mcp = FastMCP(
    name="research-assistant",
    instructions=(
        "Multi-agent AI research assistant powered by Groq LLaMA 3.3 70B.\n\n"
        "Use run_research to generate a full research report on any topic.\n"
        "Use search_reports to find past reports on similar topics (RAG).\n"
        "Use list_reports to see what topics have been researched.\n"
        "Use get_report_by_id to retrieve a specific past report by ID."
    ),
)


@mcp.tool()
def run_research(topic: str) -> str:
    """
    Run the full 4-agent research pipeline on a topic.

    Agents: Researcher (web search) -> Analyst (insights) -> Writer (report) -> Reviewer (QA)

    Args:
        topic: The research topic or question to investigate

    Returns:
        A comprehensive research report in Markdown format
    """
    try:
        research_data, _tracker = run_researcher(topic)
        analysis_obj = run_analyst(research_data, topic)
        analysis_str = analyst_to_str(analysis_obj)
        writer_obj = run_writer(analysis_str, topic)
        report_md = writer_to_markdown(writer_obj)
        reviewer_out = run_reviewer(report_md, research_data, topic)
        return reviewer_out.polished_report
    except Exception as e:
        return f"Research failed: {e}"


@mcp.tool()
def get_report_by_id(report_id: str) -> str:
    """
    Retrieve a specific past research report by its ID.

    Args:
        report_id: The UUID of the report (from list_reports or search_reports)

    Returns:
        The full report in Markdown, or an error message if not found
    """
    data = db_get_report(report_id)
    if not data:
        return f"Report {report_id} not found."
    return f"# {data['topic']}\n\n*Researched: {data['created_at']}*\n\n{data['final_report']}"


@mcp.tool()
def search_reports(query: str, top_k: int = 3) -> str:
    """
    Semantic search over past research reports using RAG (pgvector).

    Args:
        query: Topic or question to search for
        top_k: Number of results to return (default 3, max 10)

    Returns:
        Matching reports with similarity scores in Markdown
    """
    top_k = min(top_k, 10)
    matches = search_similar_reports(query, threshold=0.6, top_k=top_k)
    if not matches:
        return "No similar reports found. Try run_research to generate one."
    lines = [f"## Found {len(matches)} similar report(s)\n"]
    for i, m in enumerate(matches, 1):
        lines.append(f"### {i}. {m['topic']}")
        lines.append(f"- **Similarity:** {round(m['similarity'] * 100)}%")
        lines.append(f"- **ID:** `{m['id']}`")
        lines.append(f"- **Date:** {m['created_at'][:10]}")
        lines.append(f"\n{m['final_report'][:500]}...\n")
    return "\n".join(lines)


@mcp.tool()
def list_reports(limit: int = 10) -> str:
    """
    List recent research reports.

    Args:
        limit: Maximum number of reports to list (default 10, max 50)

    Returns:
        Table of recent reports with IDs, topics, and dates
    """
    limit = min(limit, 50)
    reports = db_get_reports(limit=limit)
    if not reports:
        return "No reports found. Use run_research to generate one."
    lines = [
        f"## Recent Research Reports ({len(reports)} found)\n",
        "| # | Topic | Date | ID |",
        "|---|-------|------|----|",
    ]
    for i, r in enumerate(reports, 1):
        date = r["created_at"][:10] if r.get("created_at") else "unknown"
        lines.append(f"| {i} | {r['topic'][:60]} | {date} | `{r['id'][:8]}...` |")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
