from __future__ import annotations

import time
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from agents.researcher import run_researcher
from agents.analyst import run_analyst
from agents.writer import run_writer
from agents.reviewer import run_reviewer
import config


class ResearchState(TypedDict):
    query: str
    research_data: str
    analysis: str
    report: str
    review: str
    final_report: str
    current_agent: str
    log: list[str]
    error: Optional[str]


def _log(state, msg):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    return state.get("log", []) + [entry]


def researcher_node(state):
    try:
        result = run_researcher(state["query"])
        return {
            **state,
            "research_data": result,
            "current_agent": config.RESEARCHER,
            "log": _log(state, f"✅ Researcher finished — {len(result)} chars collected"),
        }
    except Exception as e:
        return {
            **state,
            "error": f"Researcher failed: {e}",
            "log": _log(state, f"❌ Researcher error: {e}"),
        }


def analyst_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state
    try:
        result = run_analyst(state["research_data"], state["query"])
        return {
            **state,
            "analysis": result,
            "current_agent": config.ANALYST,
            "log": _log(state, f"✅ Analyst finished — {len(result)} chars of analysis"),
        }
    except Exception as e:
        return {
            **state,
            "error": f"Analyst failed: {e}",
            "log": _log(state, f"❌ Analyst error: {e}"),
        }


def writer_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state
    try:
        result = run_writer(state["analysis"], state["query"])
        return {
            **state,
            "report": result,
            "current_agent": config.WRITER,
            "log": _log(state, f"✅ Writer finished — {len(result)} chars report"),
        }
    except Exception as e:
        return {
            **state,
            "error": f"Writer failed: {e}",
            "log": _log(state, f"❌ Writer error: {e}"),
        }


def reviewer_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state
    try:
        result = run_reviewer(state["report"], state["research_data"], state["query"])
        return {
            **state,
            "review": result,
            "final_report": result,  # reviewer outputs the final version
            "current_agent": config.REVIEWER,
            "log": _log(state, "✅ Reviewer finished — report finalized"),
        }
    except Exception as e:
        return {
            **state,
            "error": f"Reviewer failed: {e}",
            "log": _log(state, f"❌ Reviewer error: {e}"),
        }


def build_graph():
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    # Define edges (linear pipeline)
    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_edge("reviewer", END)

    return graph.compile()


def run_pipeline(query: str):

    graph = build_graph()

    initial_state: ResearchState = {
        "query": query,
        "research_data": "",
        "analysis": "",
        "report": "",
        "review": "",
        "final_report": "",
        "current_agent": "",
        "log": [f"[{time.strftime('%H:%M:%S')}] 🚀 Pipeline started for: {query[:80]}..."],
        "error": None,
    }

    final_state = graph.invoke(initial_state)
    final_state["log"] = final_state.get("log", []) + [
        f"[{time.strftime('%H:%M:%S')}] 🏁 Pipeline complete!"
    ]
    return final_state



if __name__ == "__main__":
    import sys

    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Latest trends in artificial intelligence 2025"
    print(f"\n🔍 Researching: {topic}\n{'='*60}\n")

    state = run_pipeline(topic)

    if state.get("error"):
        print(f"\n❌ Error: {state['error']}")
    else:
        print("\n" + "="*60)
        print("📄 FINAL REPORT")
        print("="*60)
        print(state["final_report"])

    print("\n📋 Pipeline Log:")
    for entry in state.get("log", []):
        print(f"  {entry}")
