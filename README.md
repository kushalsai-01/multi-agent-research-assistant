# 🔬 AI Multi-Agent Research Assistant

> A **LangChain + LangGraph** multi-agent system where 4 specialized AI agents collaborate to research any topic, analyze findings, write a polished report, and review it for quality — all autonomously.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![LangChain](https://img.shields.io/badge/LangChain-0.3-green?logo=chainlink)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-red?logo=streamlit)

---

## 🏗️ Architecture

```
User Query
    │
    ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  🔍 Researcher  │────▶│  📊 Analyst     │────▶│  ✍️ Writer      │────▶│  🔎 Reviewer    │
│                 │     │                 │     │                 │     │                 │
│ Web search via  │     │ Extracts key    │     │ Composes a      │     │ Scores quality  │
│ DuckDuckGo      │     │ insights &      │     │ structured      │     │ (1-10) & fixes  │
│ (free, no key)  │     │ patterns        │     │ Markdown report │     │ any issues      │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                                                                              │
                                                                              ▼
                                                                     📄 Final Report
                                                                     (saved to output/)
```

**Built with:**
- **LangChain** — Agent framework, prompt templates, tool calling
- **LangGraph** — Multi-agent orchestration as a stateful graph
- **Streamlit** — Interactive web UI with real-time agent progress
- **DuckDuckGo Search** — Free web search (no API key needed)
- **OpenAI GPT** — LLM backbone (gpt-4o-mini by default, very cheap)

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd "project 4"

pip install -r requirements.txt
```

### 2. Set Your API Key

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your OpenAI API key
# Get one at: https://platform.openai.com/api-keys
```

### 3. Run the App

**Option A — Streamlit Web UI (recommended):**
```bash
streamlit run app.py
```

**Option B — Command Line:**
```bash
python main.py "Impact of AI on healthcare in 2025"
```

**Option C — Python API:**
```python
from orchestrator import run_pipeline

result = run_pipeline("Latest trends in quantum computing")
print(result["final_report"])
```

---

## 📁 Project Structure

```
project 4/
├── app.py                  # 🌐 Streamlit web UI
├── main.py                 # 💻 CLI entry point
├── orchestrator.py         # 🔗 LangGraph multi-agent pipeline
├── config.py               # ⚙️ Configuration & env loading
├── requirements.txt        # 📦 Dependencies
├── .env.example            # 🔑 API key template
│
├── agents/                 # 🤖 The 4 AI agents
│   ├── researcher.py       #    🔍 Web research agent
│   ├── analyst.py          #    📊 Data analysis agent
│   ├── writer.py           #    ✍️ Report writing agent
│   └── reviewer.py         #    🔎 Quality review agent
│
├── tools/                  # 🛠️ Agent tools
│   ├── web_search.py       #    DuckDuckGo search
│   └── text_tools.py       #    Text utilities
│
└── output/                 # 📄 Generated reports saved here
```

---

## 🤖 The 4 Agents

| # | Agent | Role | Tech |
|---|-------|------|------|
| 1 | **🔍 Researcher** | Searches the web for information using multiple queries | LangChain Agent + DuckDuckGo Tool |
| 2 | **📊 Analyst** | Extracts key insights, identifies patterns, assesses source reliability | LangChain Chain (LCEL) |
| 3 | **✍️ Writer** | Composes a structured, publication-ready Markdown report | LangChain Chain (LCEL) |
| 4 | **🔎 Reviewer** | Scores report quality (accuracy, completeness, clarity) and fixes issues | LangChain Chain (LCEL) |

### Agent Pipeline (LangGraph)

The agents are orchestrated using **LangGraph**, which manages a shared state object that flows through each node:

```python
# Simplified pipeline
graph = StateGraph(ResearchState)
graph.add_node("researcher", researcher_node)
graph.add_node("analyst", analyst_node)
graph.add_node("writer", writer_node)
graph.add_node("reviewer", reviewer_node)

graph.set_entry_point("researcher")
graph.add_edge("researcher", "analyst")
graph.add_edge("analyst", "writer")
graph.add_edge("writer", "reviewer")
graph.add_edge("reviewer", END)
```

---

## 🖥️ Streamlit UI Features

- **Real-time progress** — Watch each agent work with live status indicators
- **Tabbed results** — View Final Report, Review, Analysis, and Raw Research separately
- **Download button** — Export report as Markdown
- **Configurable** — Change model, temperature, and API key from the sidebar
- **Example topics** — One-click example queries to try

---

## ⚡ Key Technologies

| Technology | Purpose | Why |
|-----------|---------|-----|
| **LangChain** | Agent framework | Industry standard for LLM apps |
| **LangGraph** | Multi-agent orchestration | Stateful graph — more control than simple chains |
| **Streamlit** | Web UI | Fast prototyping, great for demos |
| **DuckDuckGo** | Web search | Free, no API key needed |
| **OpenAI GPT-4o-mini** | LLM | Fast, cheap (~$0.01 per research run) |

---

## 💰 Cost

Using **gpt-4o-mini** (default), each full research pipeline costs approximately **$0.01-0.03** — extremely cheap. You can run hundreds of queries for under $1.

---

## 🧪 Example Output

```
📝 Query: "Impact of AI on healthcare in 2025"

🔍 Researcher: Searched 6 queries, found 18 sources
📊 Analyst: Identified 5 key findings with confidence scores
✍️ Writer: Composed 1,200-word Markdown report
🔎 Reviewer: Score 8.4/10 — Approved with minor fixes

📄 Final report saved to: output/report_20260228_143022.md
```

---

## 📝 License

MIT License — free for personal and commercial use.

---

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain) — LLM framework
- [LangGraph](https://github.com/langchain-ai/langgraph) — Multi-agent orchestration
- [Streamlit](https://streamlit.io/) — Web UI framework
- [OpenAI](https://openai.com/) — GPT models
