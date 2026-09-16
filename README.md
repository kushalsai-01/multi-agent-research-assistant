# Multi-Agent Research Assistant

A polished portfolio project that combines multi-agent web research with PDF RAG. Ask a question, upload supporting PDFs when useful, and receive a streamed, cited Markdown report.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-Vite-61DAFB?logo=react)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-7C3AED)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20Search-DC244C)

## Overview

The assistant combines current web research from Tavily (with DuckDuckGo fallback) and evidence retrieved from uploaded PDFs. The React UI streams progress and report text live, displays source chunks, manages uploaded documents, and keeps a lightweight report history.

Read [prep.md](prep.md) for the architecture, RAG rationale, deployment runbook, and technical-interview talking points.

## Architecture

```text
Question
  → Researcher
  → Analyst
  → Writer (streamed)
  → Reviewer
  → Final cited report
```

PDFs are parsed in memory, split into heading-aware, page-aware token chunks, embedded with `BAAI/bge-small-en-v1.5`, and stored durably in Qdrant. Retrieval uses dense candidate recall, lexical reranking, and page diversification; every result retains filename, page, section, and content-hash provenance.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, react-markdown |
| API | FastAPI, Server-Sent Events |
| Agent workflow | LangChain, LangGraph, Groq |
| Web search | Tavily, DuckDuckGo fallback |
| PDF RAG | pypdf, token-aware chunking, Sentence Transformers, Qdrant |
| Persistence | Supabase Postgres |
| Observability | LangSmith |
| Deployment | Vercel, Render, Qdrant Cloud, Supabase |

## Features

- Four-agent research workflow: researcher, analyst, writer, and reviewer.
- Live SSE status and writer-token streaming.
- Multiple PDF upload, document management, page-aware retrieval, and visible retrieved sources.
- Citation-aware reports with PDF references such as `[document.pdf p.3]`.
- Report history and session memory when Supabase is configured.
- Markdown, copy, `.md` download, and print-to-PDF export.

## Screenshots

> Add screenshots here before publishing: the idle research screen, an active workflow, uploaded PDFs/retrieved sources, and a final report.

## Local Installation

Prerequisites: Python 3.11+, Node.js 20+, a Groq API key, and optionally Tavily, Supabase, LangSmith, and Qdrant Cloud credentials.

```bash
git clone <your-repository-url>
cd Project-2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`, then start the backend:

```bash
uvicorn api.main:app --reload --port 8000
```

In another terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The API health check is available at `http://localhost:8000/health`.

## Environment Variables

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Yes | LLM access |
| `GROQ_MODEL` | No | Primary Groq model |
| `GROQ_FALLBACK_MODEL` | No | Retry fallback model |
| `TAVILY_API_KEY` | Recommended | Web research; DuckDuckGo is the fallback |
| `QDRANT_URL` / `QDRANT_API_KEY` | Production | Qdrant Cloud connection; omitted uses local Qdrant |
| `QDRANT_COLLECTION` | No | Defaults to `research_documents` |
| `SUPABASE_URL` / `SUPABASE_KEY` | Optional | Report history and session memory |
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing |
| `CORS_ORIGINS` | Production | Comma-separated frontend origins |
| `VITE_API_URL` | Frontend production | Render API URL, without a trailing slash |

## Deployment

### Backend: Render

1. Create a Render Web Service from this repository; `render.yaml` supplies the build and start commands.
2. Add `GROQ_API_KEY`, `TAVILY_API_KEY`, Supabase variables, and Qdrant Cloud variables.
3. Set `CORS_ORIGINS` to your exact Vercel URL, for example `https://research-agent.vercel.app`.
4. Deploy, then verify `https://<render-service>/health`.

### Frontend: Vercel

1. Import the repository and set **Root Directory** to `frontend`.
2. Set `VITE_API_URL` to the Render backend URL.
3. Build command: `npm run build`; output directory: `dist`.
4. Deploy and add the generated Vercel URL to Render's `CORS_ORIGINS`.

### Qdrant and Supabase

Create a Qdrant Cloud cluster and copy its HTTPS URL/API key into Render. In Supabase, run `docs/supabase_schema.sql`; on an existing database, also apply `docs/supabase_production_migration.sql`. The older `docs/supabase_v2_migration.sql` is optional legacy report-vector support.

## Folder Structure

```text
agents/       Agent prompts and small workflow adapters
api/          FastAPI app and SSE endpoints
frontend/     React/Vite client
tools/        Web search and citation utilities
rag.py        PDF ingestion, embeddings, Qdrant retrieval
database.py   Supabase report persistence
memory.py     Lightweight session memory
docs/         Database schema and architecture assets
```

## Future Improvements

- Add academic-search and richer document parsers.
- Add automated end-to-end tests and a CI workflow.
- Add source-quality scoring and richer citation rendering.

## License

MIT
