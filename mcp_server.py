"""
MCP (Model Context Protocol) Server for AI Research Assistant v2.

Exposes research pipeline tools over the MCP protocol so AI assistants
(Claude Desktop, Cursor, etc.) can call them directly.

Usage:
    python mcp_server.py

Configure in Claude Desktop / Cursor:
    {
      "mcpServers": {
        "research-assistant": {
          "command": "python",
          "args": ["/path/to/mcp_server.py"]
        }
      }
    }
"""

import sys
import os
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent))

import config  # loads .env

try:
    from fastmcp import FastMCP
except ImportError:
    raise RuntimeError("fastmcp is required: pip install fastmcp>=0.4.0")

from agents.researcher import run_researcher
from agents.analyst import run_analyst, analyst_to_str
from agents.writer import run_writer, writer_to_markdown
from agents.reviewer import run_reviewer
from database import get_reports, get_report

mcp = FastMCP(
    name="AI Research Assistant",
    description="Multi-agent research pipeline — search, analyse, write and review reports automatically.",
)


@mcp.tool()
def research_topic(topic: str) -> str:
    """
    Run the full 4-agent research pipeline on a topic and return a polished report.

    Args:
        topic: The research question or subject to investigate.

    Returns:
        A complete Markdown research report with sources.
    """
    research_data, _ = run_researcher(topic)
    analysis_obj = run_analyst(research_data, topic)
    analysis_str = analyst_to_str(analysis_obj)
    writer_output = run_writer(analysis_str, topic)
    report_md = writer_to_markdown(writer_output)
    reviewer_output = run_reviewer(report_md, research_data, topic)
    return reviewer_output.polished_report


@mcp.tool()
def search_and_analyse(topic: str) -> str:
    """
    Run only the Researcher + Analyst agents and return structured analysis.
    Faster and cheaper than the full pipeline — useful for quick fact-checks.

    Args:
        topic: The topic to research and analyse.

    Returns:
        Structured Markdown analysis with key findings, statistics, and source reliability.
    """
    research_data, tracker = run_researcher(topic)
    analysis_obj = run_analyst(research_data, topic)
    stats = tracker.get_stats()
    result = analyst_to_str(analysis_obj)
    result += f"\n\n---\n*Sources found: {stats.get('total_urls', 0)} URLs*"
    return result


@mcp.tool()
def list_past_reports(limit: int = 10) -> str:
    """
    List previously generated research reports stored in the database.

    Args:
        limit: Maximum number of reports to return (default 10).

    Returns:
        Formatted list of report titles and IDs.
    """
    try:
        reports = get_reports()
        if not reports:
            return "No reports found in the database."
        lines = [f"Found {len(reports)} reports:\n"]
        for r in reports[:limit]:
            lines.append(f"- **{r.get('topic', 'Untitled')}**  (ID: `{r.get('id', '?')}`)")
        return "\n".join(lines)
    except Exception as e:
        return f"Could not fetch reports: {e}"


@mcp.tool()
def get_report_by_id(report_id: str) -> str:
    """
    Retrieve a specific past research report by its ID.

    Args:
        report_id: The UUID of the report to retrieve.

    Returns:
        The full Markdown report content.
    """
    try:
        r = get_report(report_id)
        if not r:
            return f"No report found with ID: {report_id}"
        return r.get("final_report", "Report content not available.")
    except Exception as e:
        return f"Could not fetch report {report_id}: {e}"


if __name__ == "__main__":
    print(f"Starting MCP server — model: {config.GROQ_MODEL}")
    mcp.run()
