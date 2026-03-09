# AI Multi-Agent Research Assistant

A multi-agent research system built with LangGraph and LangChain. You give it a topic, and 4 specialized agents — Researcher, Analyst, Writer, and Reviewer — work through a stateful pipeline to produce a polished, self-reviewed report.

The frontend is React + Vite with a black/white design. The backend is FastAPI streaming real-time agent progress via SSE. LangSmith handles full trace monitoring. Supabase stores every report.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![LangChain](https://img.shields.io/badge/LangChain-0.3-green)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-teal?logo=fastapi)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?logo=react)
![OpenAI](https://img.shields.io/badge/OpenAI-gpt--4o--mini-black)
![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E?logo=supabase)

---

## Architecture

### System Overview

![System Architecture](docs/system-architecture.png)

---

### LangGraph Agent State Machine

![LangGraph State Machine](docs/langgraph-state-machine.png)

---

## How It Works

Each agent reads from and writes to a shared `ResearchState`. The pipeline is linear — no conditional loops in this version.

```
User Query → Researcher → Analyst → Writer → Reviewer → Final Report
```

Agent progress streams live to the frontend via Server-Sent Events (SSE). When complete, the report is saved to Supabase.

---

## The 4 Agents

| Agent | Built with | Does |
|-------|-----------|------|
| **Researcher** | LangChain ReAct Agent + DuckDuckGo | Runs 4–6 web searches, compiles raw findings |
| **Analyst** | LCEL chain (prompt → llm → parser) | Extracts key insights and confidence scores |
| **Writer** | LCEL chain | Writes a 1000+ word structured Markdown report |
| **Reviewer** | LCEL chain | Scores the report and delivers a final edited version |

---

## Stack

| Layer | Tech | Why |
|-------|------|-----|
| LLM | OpenAI gpt-4o-mini | Cheap, fast, high quality |
| Agent Framework | LangChain 0.3 | LCEL chains, ReAct agents |
| Orchestration | LangGraph 0.2 | Stateful pipeline |
| Monitoring | LangSmith | Full trace visibility per run |
| Web Search | DuckDuckGo | Free, no API key |
| Backend | FastAPI + SSE | Real-time streaming |
| Frontend | React + Vite | Clean, fast |
| Database | Supabase (Postgres) | Stores all reports |
| Backend Deploy | Render | Free tier |
| Frontend Deploy | Vercel | Free tier |

---

## Project Structure

```
ai-research-assistant/
├── api/
│   └── main.py              # FastAPI app with SSE streaming
│
├── agents/
│   ├── researcher.py        # ReAct Agent + DuckDuckGo
│   ├── analyst.py           # LCEL chain
│   ├── writer.py            # LCEL chain
│   └── reviewer.py          # LCEL chain
│
├── tools/
│   ├── web_search.py        # DuckDuckGo wrapper
│   └── text_tools.py
│
├── frontend/                # React + Vite app
│   ├── src/
│   │   ├── App.jsx          # Main app (query, agents, report)
│   │   ├── api.js           # SSE fetch + history API
│   │   └── index.css        # Black/white design system
│   ├── package.json
│   ├── vite.config.js
│   └── vercel.json
│
├── docs/
│   ├── system-architecture.png
│   ├── langgraph-state-machine.png
│   └── supabase_schema.sql  # Run this in Supabase SQL editor
│
├── config.py                # Env vars + LangSmith setup
├── database.py              # Supabase client
├── orchestrator.py          # LangGraph pipeline (for CLI use)
├── main.py                  # CLI runner
├── render.yaml              # Render deployment config
├── requirements.txt
└── .env.example
```

---

## Running Locally

### 1. Clone and install

```bash
git clone https://github.com/kushalsai-01/research-agent
cd research-agent
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Then edit .env and fill in your keys
```

You need at minimum:
- `OPENAI_API_KEY` — from [platform.openai.com](https://platform.openai.com/api-keys)

Optional but recommended:
- `SUPABASE_URL` + `SUPABASE_KEY` — from [supabase.com](https://supabase.com) (free)
- `LANGCHAIN_API_KEY` — from [smith.langchain.com](https://smith.langchain.com) (free)

### 3. Start the backend

```bash
uvicorn api.main:app --reload --port 8000
# http://localhost:8000
# http://localhost:8000/health  ← check config status
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

---

## Supabase Setup

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the contents of `docs/supabase_schema.sql`
3. Copy your project URL and anon key into `.env`

```sql
CREATE TABLE IF NOT EXISTS reports (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic        TEXT NOT NULL,
  final_report TEXT,
  raw_research TEXT,
  analysis     TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

The app works without Supabase — reports just won't be saved to history.

---

## LangSmith Setup

1. Create a free account at [smith.langchain.com](https://smith.langchain.com)
2. Create a project called `ai-research-assistant`
3. Copy your API key into `.env`:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your-key-here
LANGCHAIN_PROJECT=ai-research-assistant
```

Every agent run will now appear in LangSmith with full input/output traces, latency, and token usage across all 4 agents.

---

## Deployment

### Backend → Render

1. Push this repo to GitHub
2. [render.com](https://render.com) → New Web Service → connect the repo
3. Render will auto-detect `render.yaml` — just add your env vars:
   - `OPENAI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `LANGCHAIN_API_KEY`
4. It'll deploy automatically on every push to main

### Frontend → Vercel

1. [vercel.com](https://vercel.com) → Add New Project → import this repo
2. Set **Root Directory** to `frontend`
3. Add environment variable:
   - `VITE_API_URL` = your Render backend URL (e.g. `https://your-app.onrender.com`)
4. Deploy — Vercel handles the rest

### Verify deployment

```
GET https://your-app.onrender.com/health
```

Returns:
```json
{
  "status": "ok",
  "langsmith_tracing": true,
  "supabase_configured": true,
  "model": "gpt-4o-mini"
}
```

---

## Cost

Everything runs on free tiers.

| Service | Cost |
|---------|------|
| OpenAI gpt-4o-mini | ~$0.01–0.05 per report |
| Render | Free |
| Vercel | Free |
| Supabase | Free (500MB) |
| LangSmith | Free (5K traces/month) |

---

## License

MIT

---

## Credits

- [LangChain](https://github.com/langchain-ai/langchain)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [LangSmith](https://smith.langchain.com)
- [Supabase](https://supabase.com)
- [OpenAI](https://openai.com)
