from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from tools.web_search import get_search_tool, quick_search
from tools.text_tools import get_current_date
from tools.citation_tracker import CitationTracker
from agents.llm_factory import FALLBACK_MODEL
import config

SYSTEM_PROMPT = """You are a Senior Research Specialist. Your job is to 
search the web and collect comprehensive, factual information on a given topic.

INSTRUCTIONS:
1. Break the user's query into 2-3 targeted search queries to get broad coverage.
2. Use the web_search tool for each query.
3. Compile ALL relevant facts, statistics, dates, names, and URLs you find.
4. Present your findings as structured bullet points grouped by sub-topic.
5. Always include the source URL for each piece of information.
6. Note any conflicting information you find between sources.
7. At the end, list 3 key questions that would need deeper investigation.

DO NOT make up any facts. Only report what you actually find from search results.
If a search returns nothing useful, say so honestly.

Current date context: use the get_current_date tool if you need today's date.
"""


def build_researcher_agent(model: str | None = None):
    llm = ChatGroq(
        model=model or config.GROQ_MODEL,
        temperature=config.LLM_TEMPERATURE,
        api_key=config.GROQ_API_KEY,
    )

    tools = [get_search_tool(), quick_search, get_current_date]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
    return agent


def run_researcher(topic: str) -> tuple:
    """
    Run the researcher agent.
    Returns (research_text: str, citation_tracker: CitationTracker).
    Automatically falls back to the smaller model if the primary is rate-limited.
    """
def _is_rate_limit(e: Exception) -> bool:
    s = str(e).lower()
    return "429" in s or "rate limit" in s or "ratelimit" in s or "too many requests" in s


def run_researcher(topic: str) -> tuple:
    """
    Run the researcher agent. Automatically falls back to the smaller model
    if the primary model is rate-limited (TPM or TPD exhausted).
    Returns (research_text: str, citation_tracker: CitationTracker).
    """
    def _run(model: str | None = None):
        agent = build_researcher_agent(model)
        tracker = CitationTracker()
        result = agent.invoke(
            {"messages": [HumanMessage(content=f"Research the following topic thoroughly:\n\n{topic}")]},
            config={"callbacks": [tracker]},
        )
        messages = result.get("messages", [])
        text = messages[-1].content if messages else "No research data collected."
        return text, tracker

    try:
        return _run()
    except Exception as e:
        if _is_rate_limit(e):
            # Primary model quota exhausted — retry with fallback model
            return _run(FALLBACK_MODEL)
        raise
