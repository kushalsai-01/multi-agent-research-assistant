# 🔬 AI Multi-Agent Research Assistant

> A **LangGraph + LangChain** powered system where 4 specialized AI agents autonomously collaborate to research any topic, extract insights, write a polished report, and self-review for quality — with a conditional revision loop.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![LangChain](https://img.shields.io/badge/LangChain-0.3-green)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-teal?logo=fastapi)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?logo=react)
![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-orange)
![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E?logo=supabase)

---

## 📐 Architecture Diagrams

### Diagram 1 — System Architecture
> *(Full diagram in `/docs/system-architecture.excalidraw`)*

![System Architecture](docs/system-architecture.png)

---

### Diagram 2 — LangGraph Agent State Machine
> *(Full diagram in `/docs/langgraph-state-machine.excalidraw`)*

![LangGraph State Machine](docs/langgraph-state-machine.png)

---

### Diagram 3 — Deployment Infrastructure
> *(Full diagram in `/docs/deployment.excalidraw`)*

![Deployment Infrastructure](docs/deployment.png)

---

## 🤖 How It Works

A user submits a research topic. LangGraph runs a **stateful 4-node pipeline** where each agent reads from and writes to a shared `ResearchState`. The Reviewer scores the final report — if quality is below 7/10, it loops back to the Writer with feedback for revision (max 2 rounds).

```
User Query → Researcher → Analyst → Writer → Reviewer → Final Report
                                        ↑         |
                                        └── if score < 7 (max 2x)
```

---

## 🧠 The 4 Agents

| # | Agent | Implementation | Role |
|---|-------|---------------|------|
| 1 | 🔍 **Researcher** | LangChain ReAct Agent + DuckDuckGo Tool | Runs 4–6 web searches, compiles raw research |
| 2 | 📊 **Analyst** | LCEL Chain (`prompt \| llm \| parser`) | Extracts key insights, patterns, confidence scores |
| 3 | ✍️ **Writer** | LCEL Chain (`prompt \| llm \| parser`) | Writes structured 1000+ word Markdown report |
| 4 | 🔎 **Reviewer** | LCEL Chain + `JsonOutputParser` | Scores 1–10, returns structured feedback, routes decision |

### LangGraph Pipeline

```python
graph = StateGraph(ResearchState)

graph.add_node("researcher", researcher_node)
graph.add_node("analyst",    analyst_node)
graph.add_node("writer",     writer_node)
graph.add_node("reviewer",   reviewer_node)

graph.set_entry_point("researcher")
graph.add_edge("researcher", "analyst")
graph.add_edge("analyst",    "writer")
graph.add_edge("writer",     "reviewer")

# Conditional edge — self-correcting loop
graph.add_conditional_edges(
    "reviewer",
    should_revise,          # returns "end" or "revise"
    {"end": END, "revise": "writer"}
)
```

### Shared State (the "baton" between agents)

```python
class ResearchState(TypedDict):
    topic:        str           # User's query
    raw_research: str           # Researcher output
    analysis:     str           # Analyst output
    report:       str           # Writer output
    review:       dict          # Reviewer score + feedback
    final_report: str           # Approved report
    iteration:    int           # Revision count (max 2)
```

---

## 🏗️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **LLM** | Groq — LLaMA 3.3 70B | Free tier, 10× faster than OpenAI |
| **Agent Framework** | LangChain 0.3 | Industry standard, LCEL chains |
| **Orchestration** | LangGraph 0.2 | Stateful graph, conditional routing |
| **Web Search** | DuckDuckGo | Free, no API key needed |
| **Backend** | FastAPI + SSE streaming | Live agent progress to frontend |
| **Frontend** | React + Vite | Fast, clean UI |
| **Database** | Supabase (Postgres) | Stores all reports + agent logs |
| **Backend Deploy** | Render | Free tier, easy GitHub deploy |
| **Frontend Deploy** | Vercel | Free, global CDN |

---

## 📁 Project Structure

```
ai-research-assistant/
├── main.py                  # FastAPI app + SSE streaming endpoint
├── orchestrator.py          # LangGraph StateGraph pipeline
├── config.py                # Groq LLM setup, env loading
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── researcher.py        # ReAct Agent + DuckDuckGo tool
│   ├── analyst.py           # LCEL chain
│   ├── writer.py            # LCEL chain
│   └── reviewer.py          # LCEL chain + JsonOutputParser
│
├── tools/
│   ├── web_search.py        # DuckDuckGo wrapper
│   └── text_tools.py        # Text utilities
│
├── frontend/                # React + Vite app (deployed to Vercel)
│   ├── src/
│   │   └── App.jsx
│   └── package.json
│
├── docs/                    # Architecture diagrams (Excalidraw)
│   ├── system-architecture.excalidraw
│   ├── langgraph-state-machine.excalidraw
│   └── deployment.excalidraw
│
└── output/                  # Generated reports (local runs)
```

---

## 🚀 Quick Start (Local)

### 1. Clone & Install

```bash
git clone https://github.com/your-username/ai-research-assistant
cd ai-research-assistant
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your-anon-key
```

Get your free Groq key at [console.groq.com](https://console.groq.com)

### 3. Run Backend

```bash
uvicorn main:app --reload
# API running at http://localhost:8000
```

### 4. Run Frontend

```bash
cd frontend
npm install
npm run dev
# UI running at http://localhost:5173
```

---

## ☁️ Deployment

### Backend → Render (Free)

1. Push to GitHub
2. [render.com](https://render.com) → New Web Service → Connect repo
3. Set environment variables: `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Deploy ✅

### Frontend → Vercel (Free)

1. [vercel.com](https://vercel.com) → Import GitHub repo (`/frontend` folder)
2. Add env variable: `VITE_API_URL=https://your-app.onrender.com`
3. Deploy ✅

### Database → Supabase (Free)

```sql
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic TEXT NOT NULL,
  final_report TEXT,
  review_score FLOAT,
  raw_research TEXT,
  analysis TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID REFERENCES reports(id),
  agent_name TEXT,
  output TEXT,
  duration_ms INT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 💰 Cost

| Service | Cost |
|---------|------|
| Groq API | Free (14,400 req/day) |
| Render | Free tier |
| Vercel | Free tier |
| Supabase | Free (500MB) |
| **Total** | **$0/month** |

---

## 🧪 Example Output

```
📝 Query: "Impact of AI on healthcare in 2025"

🔍 Researcher  — Searched 6 queries, compiled 800 words of raw research
📊 Analyst     — Extracted 5 key findings with confidence scores
✍️ Writer      — Composed 1,200-word structured Markdown report
🔎 Reviewer    — Score: 8.4/10 — Approved ✅

📄 Report saved → Supabase + available to download
```

---

## 📝 License

MIT — free for personal and commercial use.

---

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain) — LLM agent framework
- [LangGraph](https://github.com/langchain-ai/langgraph) — Multi-agent orchestration
- [Groq](https://groq.com) — Ultra-fast LLM inference
- [Supabase](https://supabase.com) — Open source Firebase alternative
