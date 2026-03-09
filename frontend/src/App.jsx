import { useState, useCallback, useRef, useEffect } from "react"
import { streamResearch } from "./api"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

const AGENTS = [
  { id: "researcher", label: "Researcher", detail: "Web search" },
  { id: "analyst",   label: "Analyst",    detail: "Insights"   },
  { id: "writer",    label: "Writer",     detail: "Report"     },
  { id: "reviewer",  label: "Reviewer",   detail: "QA"         },
]

const EXAMPLES = [
  "Latest breakthroughs in quantum computing 2025",
  "How is AI transforming healthcare?",
  "Future of electric vehicles and battery tech",
  "Cybersecurity threats and trends 2025",
  "Impact of AI on global job markets",
]

function Dot({ status }) {
  let cls = "dot"
  if (status === "running") cls += " pulse"
  else if (status === "done")  cls += " done"
  else if (status === "error") cls += " error"
  return <span className={cls} />
}

export default function App() {
  const [query,   setQuery]   = useState("")
  const [running, setRunning] = useState(false)
  const [agents,  setAgents]  = useState({})
  const [report,  setReport]  = useState(null)
  const [error,   setError]   = useState(null)
  const reportRef             = useRef(null)
  const txRef                 = useRef(null)

  const setAgent = useCallback((id, patch) =>
    setAgents(prev => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } })), [])

  const handleEvent = useCallback((event, data) => {
    if (event === "agent_start") setAgent(data.agent, { status: "running", detail: data.message })
    if (event === "agent_done")  setAgent(data.agent, { status: "done",    duration: data.duration, chars: data.chars })
    if (event === "agent_error") setAgent(data.agent, { status: "error",   detail: data.message })
    if (event === "complete") {
      setReport(data)
      setRunning(false)
      setTimeout(() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100)
    }
    if (event === "pipeline_error") { setError(data.message); setRunning(false) }
  }, [setAgent])

  const run = async () => {
    if (!query.trim() || running) return
    setRunning(true); setReport(null); setError(null); setAgents({})
    try { await streamResearch(query.trim(), handleEvent) }
    catch (e) { setError(e.message); setRunning(false) }
  }

  const reset = () => {
    setQuery(""); setReport(null); setError(null); setAgents({}); setRunning(false)
    txRef.current?.focus()
  }

  const pipelineVisible = running || Object.keys(agents).length > 0

  return (
    <div className="shell">
      {/* Nav */}
      <nav className="nav">
        <div className="nav-brand">
          <span className="nav-dot" />
          Research Agent
        </div>
        <div className="nav-spacer" />
        <span className="nav-badge">Groq · LangGraph · LangSmith</span>
        {running && <span className="nav-badge live">● running</span>}
        {report && !running && (
          <button className="btn btn-ghost btn-sm" onClick={reset}>New Research</button>
        )}
      </nav>

      {/* Page */}
      <main className="page">
        {/* Hero — shown when idle */}
        {!pipelineVisible && !report && (
          <div className="hero">
            <h1>Research anything.<br /><span>In seconds.</span></h1>
            <p>4 AI agents search the web, extract insights, write and review a full report — automatically.</p>
          </div>
        )}

        {/* Input */}
        <div className="input-card">
          <textarea
            ref={txRef}
            className="input-textarea"
            placeholder="What do you want to research?"
            value={query}
            rows={3}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run() }}
            disabled={running}
          />
          <div className="input-bar">
            <span className="input-hint">⌘ Enter to run</span>
            <button className="btn btn-run" onClick={run} disabled={running || !query.trim()}>
              {running ? "Researching..." : "Run →"}
            </button>
          </div>
        </div>

        {/* Examples — only when idle */}
        {!pipelineVisible && !report && (
          <div className="examples">
            {EXAMPLES.map(ex => (
              <button key={ex} className="chip" onClick={() => { setQuery(ex); txRef.current?.focus() }}>
                {ex}
              </button>
            ))}
          </div>
        )}

        {/* Error */}
        {error && <div className="err" style={{ marginTop: 20 }}>⚠ {error}</div>}

        {/* Pipeline */}
        {pipelineVisible && (
          <div className="pipeline" style={{ marginTop: 32 }}>
            <div className="pipeline-label">Agent Pipeline</div>
            <div className="agents">
              {AGENTS.map(a => {
                const s = agents[a.id] || {}
                const status = s.status || "idle"
                return (
                  <div key={a.id} className={`agent ${status !== "idle" ? status : ""}`}>
                    <div className="agent-head">
                      <span className="agent-name">{a.label}</span>
                      <Dot status={status} />
                    </div>
                    <div className="agent-detail">
                      {status === "running" ? s.detail
                        : status === "done"  ? `${(s.chars || 0).toLocaleString()} chars`
                        : status === "error" ? "failed"
                        : a.detail}
                    </div>
                    {s.duration && (
                      <div className="agent-time">{s.duration}s</div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Report */}
        {report?.report && (
          <div className="report-wrap" ref={reportRef} style={{ marginTop: pipelineVisible ? 24 : 32 }}>
            <div className="report-top">
              <span className="report-top-label">Final Report</span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => navigator.clipboard.writeText(report.report)}
              >
                Copy
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  const a = document.createElement("a")
                  a.href = URL.createObjectURL(new Blob([report.report], { type: "text/markdown" }))
                  a.download = `research-${Date.now()}.md`
                  a.click()
                }}
              >
                ↓ .md
              </button>
            </div>
            <div className="report-box">
              <div className="md">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.report}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Idle placeholder */}
        {!pipelineVisible && !report && !error && (
          <div className="idle" style={{ marginTop: 48 }}>
            Groq LLaMA 3.3 70B &nbsp;·&nbsp; LangChain &nbsp;·&nbsp; LangGraph &nbsp;·&nbsp; LangSmith
          </div>
        )}
      </main>
    </div>
  )
}
