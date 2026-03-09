"""
Orchestrator — builds LangGraph pipelines for Standard, Debate, and HITL modes.

Standard pipeline:  researcher → analyst → writer → reviewer (conditional loop)
Debate pipeline:    researcher → analyst → optimist + skeptic → judge
HITL pipeline:      researcher → (human pause) → analyst → writer → reviewer
"""
from __future__ import annotations

import time
from typing import TypedDict, Optional, List, Any

from langgraph.graph import StateGraph, END

from agents.researcher import run_researcher
from agents.analyst import run_analyst, analyst_to_str
from agents.writer import run_writer, writer_to_markdown
from agents.reviewer import run_reviewer
from agents.debater import run_optimist, run_skeptic
from agents.judge import run_judge
from agents.metadata_extractor import run_metadata_extractor, metadata_to_context
from agents.schemas import AnalysisOutput, WriterOutput, ReviewerOutput
import config

MAX_REVISIONS = 2


# ═══════════════════════════════════════════════════════════════════
#  Standard Pipeline State
# ═══════════════════════════════════════════════════════════════════

class ResearchState(TypedDict):
    query: str
    research_data: str
    analysis: str               # markdown string for downstream
    analysis_obj: Any           # AnalysisOutput object
    metadata: Any               # dict from metadata_extractor
    report: str                 # markdown from writer
    writer_output: Any          # WriterOutput object
    reviewer_output: Any        # ReviewerOutput object
    review: str
    final_report: str
    current_agent: str
    log: list[str]
    error: Optional[str]
    revision_count: int
    quality_score: int
    traced_urls: list[str]
    citation_stats: dict


def _log(state, msg):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    return state.get("log", []) + [entry]


# ── Standard Nodes ────────────────────────────────────────────────

def researcher_node(state: ResearchState) -> ResearchState:
    try:
        text, tracker = run_researcher(state["query"])
        stats = tracker.get_stats()
        return {
            **state,
            "research_data": text,
            "traced_urls": stats.get("urls", []),
            "citation_stats": stats,
            "current_agent": config.RESEARCHER,
            "log": _log(state, f"✅ Researcher finished — {len(text)} chars, {stats['total_urls']} URLs"),
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
        analysis_str = analyst_to_str(result)
        return {
            **state,
            "analysis": analysis_str,
            "analysis_obj": result,
            "current_agent": config.ANALYST,
            "log": _log(state, f"✅ Analyst finished — {len(result.key_findings)} findings, confidence {result.overall_confidence}/10"),
        }
    except Exception as e:
        return {
            **state,
            "error": f"Analyst failed: {e}",
            "log": _log(state, f"❌ Analyst error: {e}"),
        }


def metadata_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state
    try:
        meta = run_metadata_extractor(state["research_data"], state["query"])
        return {
            **state,
            "metadata": meta,
            "log": _log(state, "✅ Metadata extracted"),
        }
    except Exception as e:
        return {
            **state,
            "metadata": {},
            "log": _log(state, f"⚠ Metadata extraction skipped: {e}"),
        }


def writer_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state
    try:
        # Build enriched analysis with metadata context
        enriched = state["analysis"]
        if state.get("metadata"):
            enriched += "\n\n" + metadata_to_context(state["metadata"])

        # Check if this is a revision pass
        revision_instructions = ""
        if state.get("reviewer_output") and not state["reviewer_output"].passed:
            revision_instructions = state["reviewer_output"].revision_instructions

        result = run_writer(enriched, state["query"], revision_instructions)
        report_md = writer_to_markdown(result)
        return {
            **state,
            "report": report_md,
            "writer_output": result,
            "current_agent": config.WRITER,
            "log": _log(state, f"✅ Writer finished — {result.word_count} words"),
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
        rev_count = state.get("revision_count", 0) + 1
        return {
            **state,
            "reviewer_output": result,
            "quality_score": result.quality_score,
            "review": result.polished_report,
            "final_report": result.polished_report,
            "revision_count": rev_count,
            "current_agent": config.REVIEWER,
            "log": _log(state, f"✅ Reviewer — score {result.quality_score}/10, passed={result.passed} (revision {rev_count})"),
        }
    except Exception as e:
        return {
            **state,
            "error": f"Reviewer failed: {e}",
            "log": _log(state, f"❌ Reviewer error: {e}"),
        }


def should_revise(state: ResearchState) -> str:
    """Conditional edge: send back to writer if score < 7 and within revision limit."""
    if state.get("error"):
        return "end"
    rev = state.get("reviewer_output")
    if rev and not rev.passed and state.get("revision_count", 0) < MAX_REVISIONS:
        return "revise"
    return "end"


def build_graph():
    """Build the standard pipeline with conditional reviewer loop."""
    graph = StateGraph(ResearchState)

    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("metadata", metadata_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "metadata")
    graph.add_edge("metadata", "writer")
    graph.add_edge("writer", "reviewer")

    # Conditional: reviewer → writer (revise) or → END
    graph.add_conditional_edges("reviewer", should_revise, {
        "revise": "writer",
        "end": END,
    })

    return graph.compile()


# ═══════════════════════════════════════════════════════════════════
#  Debate Pipeline
# ═══════════════════════════════════════════════════════════════════

class DebateState(TypedDict):
    query: str
    research_data: str
    analysis: str
    analysis_obj: Any
    citation_stats: dict
    traced_urls: list[str]
    optimist_report: str
    skeptic_report: str
    judge_report: str
    final_report: str
    current_agent: str
    log: list[str]
    error: Optional[str]


def debate_researcher_node(state: DebateState) -> DebateState:
    try:
        text, tracker = run_researcher(state["query"])
        stats = tracker.get_stats()
        return {
            **state,
            "research_data": text,
            "traced_urls": stats.get("urls", []),
            "citation_stats": stats,
            "current_agent": "researcher",
            "log": _log(state, f"✅ Researcher — {len(text)} chars"),
        }
    except Exception as e:
        return {**state, "error": str(e), "log": _log(state, f"❌ Researcher error: {e}")}


def debate_analyst_node(state: DebateState) -> DebateState:
    if state.get("error"):
        return state
    try:
        result = run_analyst(state["research_data"], state["query"])
        return {
            **state,
            "analysis": analyst_to_str(result),
            "analysis_obj": result,
            "current_agent": "analyst",
            "log": _log(state, f"✅ Analyst — {len(result.key_findings)} findings"),
        }
    except Exception as e:
        return {**state, "error": str(e), "log": _log(state, f"❌ Analyst error: {e}")}


def optimist_node(state: DebateState) -> DebateState:
    if state.get("error"):
        return state
    try:
        result = run_optimist(state["analysis"], state["query"])
        return {
            **state,
            "optimist_report": result,
            "current_agent": "optimist",
            "log": _log(state, f"✅ Optimist — {len(result)} chars"),
        }
    except Exception as e:
        return {**state, "error": str(e), "log": _log(state, f"❌ Optimist error: {e}")}


def skeptic_node(state: DebateState) -> DebateState:
    if state.get("error"):
        return state
    try:
        result = run_skeptic(state["analysis"], state["query"])
        return {
            **state,
            "skeptic_report": result,
            "current_agent": "skeptic",
            "log": _log(state, f"✅ Skeptic — {len(result)} chars"),
        }
    except Exception as e:
        return {**state, "error": str(e), "log": _log(state, f"❌ Skeptic error: {e}")}


def judge_node(state: DebateState) -> DebateState:
    if state.get("error"):
        return state
    try:
        result = run_judge(
            state["optimist_report"],
            state["skeptic_report"],
            state["research_data"],
            state["query"],
        )
        return {
            **state,
            "judge_report": result,
            "final_report": result,
            "current_agent": "judge",
            "log": _log(state, "✅ Judge — balanced synthesis complete"),
        }
    except Exception as e:
        return {**state, "error": str(e), "log": _log(state, f"❌ Judge error: {e}")}


def build_debate_graph():
    """Build debate pipeline: researcher → analyst → optimist → skeptic → judge."""
    graph = StateGraph(DebateState)

    graph.add_node("researcher", debate_researcher_node)
    graph.add_node("analyst", debate_analyst_node)
    graph.add_node("optimist", optimist_node)
    graph.add_node("skeptic", skeptic_node)
    graph.add_node("judge", judge_node)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "optimist")
    graph.add_edge("optimist", "skeptic")
    graph.add_edge("skeptic", "judge")
    graph.add_edge("judge", END)

    return graph.compile()


# ═══════════════════════════════════════════════════════════════════
#  HITL Pipeline (Human-in-the-Loop)
# ═══════════════════════════════════════════════════════════════════

def build_hitl_graph():
    """
    Build HITL pipeline with interrupt_after researcher.
    Uses MemorySaver for checkpoint persistence.
    """
    from langgraph.checkpoint.memory import MemorySaver

    graph = StateGraph(ResearchState)

    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("metadata", metadata_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "metadata")
    graph.add_edge("metadata", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_conditional_edges("reviewer", should_revise, {
        "revise": "writer",
        "end": END,
    })

    memory = MemorySaver()
    return graph.compile(checkpointer=memory, interrupt_after=["researcher"])


# ═══════════════════════════════════════════════════════════════════
#  Convenience runner (backward compatible)
# ═══════════════════════════════════════════════════════════════════

def run_pipeline(query: str):
    """Run the standard pipeline synchronously."""
    graph = build_graph()

    initial_state: ResearchState = {
        "query": query,
        "research_data": "",
        "analysis": "",
        "analysis_obj": None,
        "metadata": None,
        "report": "",
        "writer_output": None,
        "reviewer_output": None,
        "review": "",
        "final_report": "",
        "current_agent": "",
        "log": [f"[{time.strftime('%H:%M:%S')}] 🚀 Pipeline started for: {query[:80]}..."],
        "error": None,
        "revision_count": 0,
        "quality_score": 0,
        "traced_urls": [],
        "citation_stats": {},
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
        print(f"\n📊 Quality score: {state.get('quality_score', '?')}/10")
        print(f"🔄 Revisions: {state.get('revision_count', 0)}")

    print("\n📋 Pipeline Log:")
    for entry in state.get("log", []):
        print(f"  {entry}")
