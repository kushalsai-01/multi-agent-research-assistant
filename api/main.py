"""
FastAPI backend for AI Research Assistant.
Streams agent progress via Server-Sent Events (SSE).

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
from agents.analyst import run_analyst
from agents.writer import run_writer
from agents.reviewer import run_reviewer
from database import save_report, get_reports, get_report


app = FastAPI(
    title="AI Research Assistant",
    description="Multi-agent research pipeline with LangGraph + LangChain",
    version="1.0.0",
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


# ─── Streaming pipeline ───────────────────────────────────────────────────────

async def stream_pipeline(query: str):
    MAX_RETRIES = 3
    yield sse("start", {"query": query, "timestamp": datetime.now().isoformat()})

    # ── Researcher ──────────────────────────────────────────────────────────
    yield sse("agent_start", {
        "agent": "researcher",
        "label": "Researcher",
        "message": "Searching the web for sources...",
    })
    research_data = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            research_data = await run_in_thread(run_researcher, query)
            urls_found = _count_urls(research_data)
            yield sse("agent_done", {
                "agent": "researcher",
                "duration": round(time.time() - t0, 1),
                "chars": len(research_data),
                "stat": f"{urls_found} sources found",
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
        "message": f"Extracting insights from {_count_urls(research_data)} sources...",
    })
    analysis = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            analysis = await run_in_thread(run_analyst, research_data, query)
            findings = analysis.count("##")
            yield sse("agent_done", {
                "agent": "analyst",
                "duration": round(time.time() - t0, 1),
                "chars": len(analysis),
                "stat": f"{findings} insight sections",
                "preview": analysis[:600],
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

    # ── Writer ──────────────────────────────────────────────────────────────
    yield sse("agent_start", {
        "agent": "writer",
        "label": "Writer",
        "message": "Composing full report...",
    })
    report = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            report = await run_in_thread(run_writer, analysis, query)
            wc = _word_count(report)
            yield sse("agent_done", {
                "agent": "writer",
                "duration": round(time.time() - t0, 1),
                "chars": len(report),
                "stat": f"{wc:,} words written",
                "preview": report[:600],
            })
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and _is_rate_limit(e):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "writer", "attempt": attempt + 1, "delay": delay, "message": f"Rate limited — retrying in {delay}s..."})
                await asyncio.sleep(delay)
            else:
                yield sse("agent_error", {"agent": "writer", "message": str(e)})
                yield sse("pipeline_error", {"message": f"Writer failed: {e}"})
                return

    # ── Reviewer ────────────────────────────────────────────────────────────
    yield sse("agent_start", {
        "agent": "reviewer",
        "label": "Reviewer",
        "message": "Running QA — checking quality & accuracy...",
    })
    final_report = None
    for attempt in range(MAX_RETRIES):
        try:
            t0 = time.time()
            final_report = await run_in_thread(run_reviewer, report, research_data, query)
            yield sse("agent_done", {
                "agent": "reviewer",
                "duration": round(time.time() - t0, 1),
                "chars": len(final_report),
                "stat": f"{_word_count(final_report):,} words final",
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

    # ── Save to Supabase ─────────────────────────────────────────────────────
    report_id = None
    try:
        report_id = await run_in_thread(
            save_report, query, final_report, research_data, analysis
        )
    except Exception as e:
        print(f"[DB] Save failed: {e}")

    # ── Final event ──────────────────────────────────────────────────────────
    yield sse("complete", {
        "report": final_report,
        "report_id": report_id,
        "query": query,
    })


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.post("/api/research")
async def research(req: ResearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set on the server")

    return StreamingResponse(
        stream_pipeline(req.query.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/reports")
async def list_reports():
    return get_reports()


@app.get("/api/reports/{report_id}")
async def single_report(report_id: str):
    data = get_report(report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found")
    return data


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "langsmith_tracing": config.LANGCHAIN_TRACING_V2 == "true",
        "supabase_configured": bool(config.SUPABASE_URL and config.SUPABASE_KEY),
        "model": config.GROQ_MODEL,
    }
