from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from agents.analyst import analyst_to_str, run_analyst
from agents.citation import build_citation_context
from agents.document_rag import run_document_rag
from agents.researcher import run_researcher
from agents.reviewer import run_reviewer
from agents.writer import astream_writer
from database import get_report, get_reports, save_report
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from memory import get_memory, remember_query
from pydantic import BaseModel, Field
from rag import delete_document, ingest_pdf, list_documents

MAX_RETRIES = 3
MAX_RESEARCH_RETRIES = 1
MAX_REVISIONS = 2

app = FastAPI(title="AI Research Assistant", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


class ResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="English", max_length=50)
    session_id: str = Field(min_length=8, max_length=100)


def session_scope(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", value):
        raise HTTPException(status_code=400, detail="A valid session identifier is required.")
    return value


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_in_thread(function, *args):
    return await asyncio.get_running_loop().run_in_executor(None, function, *args)


def is_transient(error: Exception) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in ("429", "rate limit", "ratelimit", "too many requests", "rate_limit_exceeded", "timeout", "temporarily unavailable"))


def friendly_error(error: Exception) -> str:
    message = str(error)
    if is_transient(error):
        return "A model or search provider is temporarily unavailable. The request was retried; please try again shortly."
    return message


async def stream_pipeline(query: str, language: str, session_id: str):
    yield sse("start", {"query": query, "language": language, "timestamp": datetime.now().isoformat()})
    yield sse("agent_start", {"agent": "researcher", "label": "Researcher", "message": "Searching current sources and uploaded evidence..."})
    research_data = ""
    citation_stats = {}
    for attempt in range(MAX_RETRIES):
        try:
            started = time.time()
            research_data, tracker = await run_in_thread(run_researcher, query)
            citation_stats = tracker.get_stats()
            yield sse("agent_done", {"agent": "researcher", "duration": round(time.time() - started, 1), "chars": len(research_data), "stat": f"{citation_stats.get('total_urls', 0)} web sources"})
            break
        except Exception as error:
            if attempt < MAX_RETRIES - 1 and is_transient(error):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "researcher", "attempt": attempt + 1, "delay": delay, "message": f"Retrying research in {delay}s..."})
                await asyncio.sleep(delay)
                continue
            yield sse("agent_error", {"agent": "researcher", "message": str(error)})
            yield sse("pipeline_error", {"message": friendly_error(error)})
            return

    try:
        rag_context, retrieved_chunks = await run_in_thread(run_document_rag, query, session_id)
        yield sse("retrieved_sources", {"sources": retrieved_chunks})
    except Exception:
        rag_context, retrieved_chunks = "", []
    combined_research = research_data + (f"\n\n{rag_context}" if rag_context else "")
    citation_context = build_citation_context(retrieved_chunks)

    yield sse("agent_start", {"agent": "analyst", "label": "Analyst", "message": "Validating evidence and extracting findings..."})
    analysis_obj = None
    analysis_str = ""
    for attempt in range(MAX_RETRIES):
        try:
            started = time.time()
            analysis_obj = await run_in_thread(run_analyst, combined_research, query)
            analysis_str = analyst_to_str(analysis_obj)
            yield sse("agent_done", {"agent": "analyst", "duration": round(time.time() - started, 1), "chars": len(analysis_str), "stat": f"{len(analysis_obj.key_findings)} findings · confidence {analysis_obj.overall_confidence}/10"})
            break
        except Exception as error:
            if attempt < MAX_RETRIES - 1 and is_transient(error):
                delay = 2 ** attempt
                yield sse("agent_retry", {"agent": "analyst", "attempt": attempt + 1, "delay": delay, "message": f"Retrying analysis in {delay}s..."})
                await asyncio.sleep(delay)
                continue
            yield sse("agent_error", {"agent": "analyst", "message": str(error)})
            yield sse("pipeline_error", {"message": friendly_error(error)})
            return

    if analysis_obj and analysis_obj.overall_confidence < 6:
        gaps = analysis_obj.gaps_and_contradictions
        try:
            yield sse("agent_retry", {"agent": "researcher", "attempt": 1, "message": "Low confidence detected; checking targeted evidence..."})
            additional_research, _ = await run_in_thread(run_researcher, query, "", gaps)
            combined_research += f"\n\n{additional_research}"
            analysis_obj = await run_in_thread(run_analyst, combined_research, query)
            analysis_str = analyst_to_str(analysis_obj)
        except Exception:
            pass

    enriched_analysis = analysis_str + (f"\n\n{rag_context}\n\n{citation_context}" if rag_context else "")
    revision_count = 0
    revision_instructions = ""
    reviewer_output = None
    final_report = ""
    while revision_count <= MAX_REVISIONS:
        if revision_count:
            yield sse("revision_start", {"revision": revision_count, "message": f"Applying quality revision {revision_count}/{MAX_REVISIONS}..."})
        yield sse("agent_start", {"agent": "writer", "label": "Writer", "message": "Writing a grounded report..."})
        report = ""
        try:
            started = time.time()
            async for token in astream_writer(enriched_analysis, query, revision_instructions, language):
                report += token
                yield sse("writer_token", {"token": token})
            yield sse("agent_done", {"agent": "writer", "duration": round(time.time() - started, 1), "chars": len(report), "stat": f"{len(report.split()):,} words"})
        except Exception as error:
            yield sse("agent_error", {"agent": "writer", "message": str(error)})
            yield sse("pipeline_error", {"message": friendly_error(error)})
            return

        yield sse("agent_start", {"agent": "reviewer", "label": "Reviewer", "message": "Checking evidence, citations, and report quality..."})
        for attempt in range(MAX_RETRIES):
            try:
                started = time.time()
                reviewer_output = await run_in_thread(run_reviewer, report, combined_research, query, language)
                yield sse("agent_done", {"agent": "reviewer", "duration": round(time.time() - started, 1), "chars": len(reviewer_output.polished_report), "stat": f"score {reviewer_output.quality_score}/10"})
                break
            except Exception as error:
                if attempt < MAX_RETRIES - 1 and is_transient(error):
                    delay = 2 ** attempt
                    yield sse("agent_retry", {"agent": "reviewer", "attempt": attempt + 1, "delay": delay, "message": f"Retrying review in {delay}s..."})
                    await asyncio.sleep(delay)
                    continue
                yield sse("agent_error", {"agent": "reviewer", "message": str(error)})
                yield sse("pipeline_error", {"message": friendly_error(error)})
                return
        revision_count += 1
        final_report = reviewer_output.polished_report
        if reviewer_output.passed or revision_count > MAX_REVISIONS:
            break
        revision_instructions = reviewer_output.revision_instructions

    report_id = None
    try:
        report_id = await run_in_thread(lambda: save_report(query, final_report, combined_research, analysis_str, reviewer_output.quality_score if reviewer_output else 0, revision_count, "standard", session_id))
        remember_query(session_id, query, report_id)
    except Exception:
        pass
    yield sse("complete", {"report": final_report, "report_id": report_id, "query": query, "quality_score": reviewer_output.quality_score if reviewer_output else 0, "revisions": revision_count, "citation_stats": citation_stats, "retrieved_sources": retrieved_chunks})


@app.post("/api/research")
async def research(request: ResearchRequest):
    if not config.GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="The research service is not configured.")
    return StreamingResponse(stream_pipeline(request.query.strip(), request.language, session_scope(request.session_id)), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), x_session_id: str = Header(default="")):
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    try:
        return await run_in_thread(ingest_pdf, file, session_scope(x_session_id), {"content_type": file.content_type})
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"PDF ingestion failed: {error}")


@app.get("/api/documents")
async def documents(x_session_id: str = Header(default="")):
    return await run_in_thread(list_documents, session_scope(x_session_id))


@app.delete("/api/documents/{document_id}")
async def remove_document(document_id: str, x_session_id: str = Header(default="")):
    if not await run_in_thread(delete_document, document_id, session_scope(x_session_id)):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": document_id}


@app.get("/api/reports")
async def reports(x_session_id: str = Header(default="")):
    return get_reports(session_scope(x_session_id))


@app.get("/api/reports/{report_id}")
async def report(report_id: str, x_session_id: str = Header(default="")):
    data = get_report(report_id, session_scope(x_session_id))
    if not data:
        raise HTTPException(status_code=404, detail="Report not found")
    return data


@app.get("/api/memory/{session_id}")
async def memory(session_id: str):
    session_id = session_scope(session_id)
    return {"session_id": session_id, "history": get_memory(session_id)}


@app.get("/health")
async def health():
    issues = config.deployment_issues() if config.DEPLOYMENT_ENV == "production" else []
    return {"status": "ok" if not issues else "degraded", "version": "3.0.0", "deployment_issues": issues, "features": ["four_agents", "rag", "citations", "streaming", "quality_review", "session_history"]}


@app.get("/ready")
async def ready():
    issues = config.deployment_issues()
    if issues:
        return JSONResponse(status_code=503, content={"status": "not_ready", "missing": issues})
    return {"status": "ready"}
