"""
FastAPI backend for AI Research Assistant — v2.
Supports Standard, Debate, and HITL modes via SSE streaming.

Run locally:
    uvicorn api.main:app --reload --port 8000

Deploy on Render:
    Start command: uvicorn api.main:app --host 0.0.0.0 --port $PORT
"""

import sys
import os
import json
import time
import asyncio
import uuid
from pathlib import Path
from datetime import datetime

# Make sure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # loads .env and sets LangSmith env vars

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.researcher import run_researcher
from agents.analyst import run_analyst, analyst_to_str
from agents.writer import run_writer, writer_to_markdown, astream_writer
from agents.reviewer import run_reviewer
from memory import remember_query, get_memory
from agents.metadata_extractor import run_metadata_extractor, metadata_to_context
from agents.debater import run_optimist, run_skeptic
from agents.judge import run_judge
from agents.schemas import AnalysisOutput, WriterOutput, ReviewerOutput
from database import save_report, get_reports, get_report
from rag import get_rag_context, store_report_embedding

# HITL session storage (in-memory; resets on restart)
from orchestrator import build_hitl_graph, ResearchState
_hitl_sessions: dict = {}
_hitl_graph = None

MAX_REVISIONS = 2


app = FastAPI(
    title="AI Research Assistant",
    description="Multi-agent research pipeline with LangGraph + LangChain (v2)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str
    language: str = "English"
    session_id: str = ""


class ResumeRequest(BaseModel):
    session_id: str
    feedback: str = ""


# ─── SSE helpers ──────────────────────────────────────────────────────────────

def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_in_thread(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)


def _is_rate_limit(e: Exception) -> bool:
    s = str(e).lower()
    return "rate limit" in s or "429" in s or "ratelimit" in s or "too many requests" in s


def _count_urls(text: str) -> int:
    return text.count("http://") + text.count("https://")


def _word_count(text: str) -> int:
    return len(text.split())


MAX_RETRIES = 3


# ─── Standard Streaming Pipeline ──────────────────────────────────────────────

async def stream_pipeline(query: str, language: str = "English", session_id: str = ""):
    yield sse("start", {"query": query, "language": language, "timestamp": datetime.now().isoformat()})

    # ── RAG check — look for cached similar report ───────────────────────
    try:
        rag_result = await run_in_thread(get_rag_context, query)
        if rag_result:
            yield sse("rag_hit", {
                "topic": rag_result.get("topic", ""),
                "similarity": rag_result.get("similarity", 0),
                "report_id": rag_result.get("id", ""),
                "message": f"Found similar report: \"{rag_result.get('topic', '')}\" — generating fresh analysis anyway.",
            })
    except Exception:
        pass  # RAG is optional

    # ── Researcher ──────────────────────────────────────────────────────────
    yield sse("agent_start", {
        "agent": "researcher",
        "label": "Researcher",
        "message": "Searching the web for sources...",
    })
    research_data = None
    citation_stats = {}
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            research_data, tracker = await run_in_thread(run_researcher, query)
            citation_stats = tracker.get_stats()
            yield sse("agent_done", {
                "agent": "researcher",
                "duration": round(time.time() - t0, 1),
                "chars": len(research_data),
                "stat": f"{citation_stats['total_urls']} sources found",
                "preview": research_data[:600],
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "researcher", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "researcher", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Researcher failed: {e}"})
                return

    # ── Analyst ─────────────────────────────────────────────────────────────
    yield sse("agent_start", {
        "agent": "analyst",
        "label": "Analyst",
        "message": f"Extracting insights from {citation_stats.get('total_urls', 0)} sources...",
    })
    analysis_str = None
    analysis_obj = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            analysis_obj = await run_in_thread(run_analyst, research_data, query)
            analysis_str = analyst_to_str(analysis_obj)
            yield sse("agent_done", {
                "agent": "analyst",
                "duration": round(time.time() - t0, 1),
                "chars": len(analysis_str),
                "stat": f"{len(analysis_obj.key_findings)} findings · confidence {analysis_obj.overall_confidence}/10",
                "preview": analysis_str[:600],
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "analyst", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "analyst", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Analyst failed: {e}"})
                return

    # ── Metadata Extractor (runs after analyst) ─────────────────────────────
    metadata = {}
    try:
        metadata = await run_in_thread(run_metadata_extractor, research_data, query)
    except Exception:
        pass  # Metadata is optional enrichment

    enriched_analysis = analysis_str
    if metadata:
        enriched_analysis += "\n\n" + metadata_to_context(metadata)

    # ── Writer + Reviewer Loop ──────────────────────────────────────────────
    revision_count = 0
    revision_instructions = ""
    final_report = None

    while revision_count <= MAX_REVISIONS:
        # Writer
        if revision_count > 0:
            yield sse("revision_start", {
                "revision": revision_count,
                "message": f"Revision {revision_count}/{MAX_REVISIONS} — writer improving report...",
            })
        yield sse("agent_start", {
            "agent": "writer",
            "label": "Writer",
            "message": "Composing report..." if revision_count == 0 else f"Revising report (round {revision_count})...",
        })

        report_md = ""
        try:
            t0 = time.time()
            async for chunk in astream_writer(enriched_analysis, query, revision_instructions, language):
                report_md += chunk
                yield sse("writer_token", {"token": chunk})
            yield sse("agent_done", {
                "agent": "writer",
                "duration": round(time.time() - t0, 1),
                "chars": len(report_md),
                "stat": f"{len(report_md.split()):,} words" + (f" (rev {revision_count})" if revision_count > 0 else ""),
                "preview": report_md[:600],
            })
        except Exception as e:
            yield sse("agent_error", {"agent": "writer", "message": str(e)})
            yield sse("pipeline_error", {"message": f"Writer failed: {e}"})
            return

        # Reviewer
        yield sse("agent_start", {
            "agent": "reviewer",
            "label": "Reviewer",
            "message": "Running QA — checking quality & accuracy...",
        })

        reviewer_output = None
        for attempt in range(MAX_RETRIES):
            try:
                t0 = time.time()
                reviewer_output = await run_in_thread(run_reviewer, report_md, research_data, query, language)
                yield sse("agent_done", {
                    "agent": "reviewer",
                    "duration": round(time.time() - t0, 1),
                    "chars": len(reviewer_output.polished_report),
                    "stat": f"score {reviewer_output.quality_score}/10 · {'✓ passed' if reviewer_output.passed else '✗ needs revision'}",
                })
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                    delay = 2 ** attempt
                    yield sse("agent_retry", {"agent": "reviewer", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                    await asyncio.sleep(delay)
                else:
                    yield sse("agent_error", {"agent": "reviewer", "message": str(e)})
                    yield sse("pipeline_error", {"message": f"Reviewer failed: {e}"})
                    return

        revision_count += 1

        if reviewer_output.passed or revision_count > MAX_REVISIONS:
            final_report = reviewer_output.polished_report
            break
        else:
            revision_instructions = reviewer_output.revision_instructions

    if not final_report and reviewer_output:
        final_report = reviewer_output.polished_report

    # ── Save to Supabase ─────────────────────────────────────────────────────
    report_id = None
    try:
        report_id = await run_in_thread(
            save_report, query, final_report, research_data, analysis_str
        )
        if report_id:
            try:
                await run_in_thread(store_report_embedding, report_id, query, final_report)
            except Exception:
                pass
    except Exception as e:
        print(f"[DB] Save failed: {e}")

    # ── Final event ──────────────────────────────────────────────────────────
    yield sse("complete", {
        "report": final_report,
        "report_id": report_id,
        "query": query,
        "quality_score": reviewer_output.quality_score if reviewer_output else 0,
        "revisions": revision_count,
        "citation_stats": citation_stats,
    })

    # ── Persist session memory ───────────────────────────────────────────────
    if session_id:
        try:
            remember_query(session_id, query, report_id)
        except Exception:
            pass


# ─── Debate Streaming Pipeline ────────────────────────────────────────────────

async def stream_debate(query: str, language: str = "English", session_id: str = ""):
    yield sse("start", {"query": query, "mode": "debate", "language": language, "timestamp": datetime.now().isoformat()})

    # ── Researcher ──────────────────────────────────────────────────────────
    yield sse("agent_start", {"agent": "researcher", "label": "Researcher", "message": "Searching the web..."})
    research_data = None
    citation_stats = {}
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            research_data, tracker = await run_in_thread(run_researcher, query)
            citation_stats = tracker.get_stats()
            yield sse("agent_done", {
                "agent": "researcher",
                "duration": round(time.time() - t0, 1),
                "chars": len(research_data),
                "stat": f"{citation_stats['total_urls']} sources",
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "researcher", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "researcher", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Researcher failed: {e}"})
                return

    # ── Analyst ─────────────────────────────────────────────────────────────
    yield sse("agent_start", {"agent": "analyst", "label": "Analyst", "message": "Analyzing research data..."})
    analysis_str = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            analysis_obj = await run_in_thread(run_analyst, research_data, query)
            analysis_str = analyst_to_str(analysis_obj)
            yield sse("agent_done", {
                "agent": "analyst",
                "duration": round(time.time() - t0, 1),
                "chars": len(analysis_str),
                "stat": f"{len(analysis_obj.key_findings)} findings",
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "analyst", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "analyst", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Analyst failed: {e}"})
                return

    # ── Optimist ────────────────────────────────────────────────────────────
    yield sse("agent_start", {"agent": "optimist", "label": "Optimist", "message": "Writing optimistic perspective..."})
    optimist_report = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            optimist_report = await run_in_thread(run_optimist, analysis_str, query)
            yield sse("agent_done", {
                "agent": "optimist",
                "duration": round(time.time() - t0, 1),
                "chars": len(optimist_report),
                "stat": f"{_word_count(optimist_report)} words",
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "optimist", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "optimist", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Optimist failed: {e}"})
                return

    # ── Skeptic ─────────────────────────────────────────────────────────────
    yield sse("agent_start", {"agent": "skeptic", "label": "Skeptic", "message": "Writing critical analysis..."})
    skeptic_report = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            skeptic_report = await run_in_thread(run_skeptic, analysis_str, query)
            yield sse("agent_done", {
                "agent": "skeptic",
                "duration": round(time.time() - t0, 1),
                "chars": len(skeptic_report),
                "stat": f"{_word_count(skeptic_report)} words",
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "skeptic", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "skeptic", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Skeptic failed: {e}"})
                return

    # ── Judge ───────────────────────────────────────────────────────────────
    yield sse("agent_start", {"agent": "judge", "label": "Judge", "message": "Synthesizing balanced verdict..."})
    final_report = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            final_report = await run_in_thread(run_judge, optimist_report, skeptic_report, research_data, query)
            yield sse("agent_done", {
                "agent": "judge",
                "duration": round(time.time() - t0, 1),
                "chars": len(final_report),
                "stat": f"{_word_count(final_report)} words balanced",
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "judge", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "judge", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Judge failed: {e}"})
                return

    # ── Save to DB ────────────────────────────────────────────────────────
    report_id = None
    try:
        report_id = await run_in_thread(save_report, query, final_report, research_data, analysis_str)
        if report_id:
            try:
                await run_in_thread(store_report_embedding, report_id, query, final_report)
            except Exception:
                pass
    except Exception:
        pass

    yield sse("complete", {
        "report": final_report,
        "report_id": report_id,
        "query": query,
        "mode": "debate",
        "optimist_report": optimist_report,
        "skeptic_report": skeptic_report,
        "citation_stats": citation_stats,
    })

    if session_id:
        try:
            remember_query(session_id, query, report_id)
        except Exception:
            pass


# ─── HITL Streaming Pipeline ──────────────────────────────────────────────────

async def stream_hitl(query: str):
    """Start a HITL pipeline — runs researcher then pauses for human review."""
    global _hitl_graph
    if _hitl_graph is None:
        _hitl_graph = build_hitl_graph()

    session_id = str(uuid.uuid4())[:8]

    yield sse("start", {"query": query, "mode": "hitl", "session_id": session_id, "timestamp": datetime.now().isoformat()})

    yield sse("agent_start", {"agent": "researcher", "label": "Researcher", "message": "Searching the web..."})

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
        "log": [],
        "error": None,
        "revision_count": 0,
        "quality_score": 0,
        "traced_urls": [],
        "citation_stats": {},
    }

    thread_config = {"configurable": {"thread_id": session_id}}

    try:
        t0 = time.time()
        # This will run researcher then pause (interrupt_after=["researcher"])
        result = await run_in_thread(
            lambda: _hitl_graph.invoke(initial_state, config=thread_config)
        )

        research_data = result.get("research_data", "")
        citation_stats = result.get("citation_stats", {})

        yield sse("agent_done", {
            "agent": "researcher",
            "duration": round(time.time() - t0, 1),
            "chars": len(research_data),
            "stat": f"{citation_stats.get('total_urls', 0)} sources found",
            "preview": research_data[:800],
        })

        # Store session for resume
        _hitl_sessions[session_id] = {
            "thread_config": thread_config,
            "query": query,
            "research_preview": research_data[:2000],
        }

        yield sse("hitl_pause", {
            "session_id": session_id,
            "message": "Research complete. Review the findings above, then click Resume to continue with analysis, writing, and review.",
            "research_preview": research_data[:2000],
        })

    except Exception as e:
        yield sse("agent_error", {"agent": "researcher", "message": str(e)})
        yield sse("pipeline_error", {"message": f"HITL researcher failed: {e}"})


async def stream_resume(session_id: str, feedback: str = ""):
    """Resume a paused HITL pipeline after human review."""
    global _hitl_graph
    session = _hitl_sessions.get(session_id)
    if not session:
        yield sse("pipeline_error", {"message": "Session not found or expired."})
        return

    thread_config = session["thread_config"]
    query = session["query"]

    yield sse("start", {"query": query, "mode": "hitl_resume", "session_id": session_id})

    if feedback:
        yield sse("hitl_feedback", {"feedback": feedback, "message": "Human feedback received — incorporating into analysis."})

    try:
        # Resume the graph — it will continue from analyst onward
        yield sse("agent_start", {"agent": "analyst", "label": "Analyst", "message": "Analyzing research data..."})

        t0 = time.time()
        # Update state with human feedback if provided
        update = None
        if feedback:
            update = {"research_data": session.get("research_preview", "") + f"\n\n## Human Feedback\n{feedback}"}

        result = await run_in_thread(
            lambda: _hitl_graph.invoke(update, config=thread_config)
        )

        final_report = result.get("final_report", "")
        quality_score = result.get("quality_score", 0)

        yield sse("agent_done", {"agent": "analyst", "duration": round(time.time() - t0, 1), "chars": len(final_report), "stat": "Analysis complete"})

        # Save
        report_id = None
        try:
            report_id = await run_in_thread(save_report, query, final_report, result.get("research_data", ""), result.get("analysis", ""))
        except Exception:
            pass

        yield sse("complete", {
            "report": final_report,
            "report_id": report_id,
            "query": query,
            "mode": "hitl",
            "quality_score": quality_score,
        })

        # Cleanup session
        _hitl_sessions.pop(session_id, None)

    except Exception as e:
        yield sse("pipeline_error", {"message": f"Resume failed: {e}"})


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/api/research")
async def research(req: ResearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set on the server")

    return StreamingResponse(
        stream_pipeline(req.query.strip(), req.language, req.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/research/debate")
async def research_debate(req: ResearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set on the server")

    return StreamingResponse(
        stream_debate(req.query.strip(), req.language, req.session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/research/hitl")
async def research_hitl(req: ResearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set on the server")

    return StreamingResponse(
        stream_hitl(req.query.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/research/resume")
async def research_resume(req: ResumeRequest):
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    return StreamingResponse(
        stream_resume(req.session_id, req.feedback),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.get("/api/reports")
async def list_reports_endpoint():
    return get_reports()


@app.get("/api/reports/{report_id}")
async def single_report(report_id: str):
    data = get_report(report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found")
    return data


@app.get("/api/memory/{session_id}")
async def memory_endpoint(session_id: str):
    """Return past queries for a given client session."""
    return {"session_id": session_id, "history": get_memory(session_id)}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "langsmith_tracing": config.LANGCHAIN_TRACING_V2 == "true",
        "supabase_configured": bool(config.SUPABASE_URL and config.SUPABASE_KEY),
        "model": config.GROQ_MODEL,
        "features": ["standard", "debate", "hitl", "rag", "citations", "conditional_review",
                     "streaming_writer", "session_memory", "multi_language", "pdf_export",
                     "langsmith_eval"],
    }
