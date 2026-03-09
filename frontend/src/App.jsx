import { useState, useCallback, useRef, useEffect } from "react"
import { streamResearch, streamDebate, streamHitl, streamResume, fetchHistory, fetchReport, fetchMemory } from "./api"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

const STANDARD_AGENTS = [
  { id: "researcher", label: "Researcher", idle: "Web search" },
  { id: "analyst",   label: "Analyst",    idle: "Insights"  },
  { id: "writer",    label: "Writer",     idle: "Report"    },
  { id: "reviewer",  label: "Reviewer",   idle: "QA"        },
]

const DEBATE_AGENTS = [
  { id: "researcher", label: "Researcher", idle: "Web search" },
  { id: "analyst",   label: "Analyst",    idle: "Insights"  },
  { id: "optimist",  label: "Optimist",   idle: "Positive"  },
  { id: "skeptic",   label: "Skeptic",    idle: "Critical"  },
  { id: "judge",     label: "Judge",      idle: "Synthesis"  },
]

const AGENT_ICONS = {
  researcher: "⚡",
  analyst:    "◈",
  writer:     "✦",
  reviewer:   "◉",
  optimist:   "◆",
  skeptic:    "◐",
  judge:      "⊜",
}

const MODES = [
  { id: "standard", label: "Standard",  desc: "4-agent pipeline · researcher → analyst → writer → reviewer" },
  { id: "debate",   label: "Debate",    desc: "Optimist vs Skeptic · Judge synthesises a final verdict" },
  { id: "hitl",     label: "HITL",      desc: "You review raw research before the pipeline continues" },
]

const EXAMPLES = [
  "Latest breakthroughs in quantum computing 2025",
  "How is AI transforming healthcare?",
  "Future of electric vehicles and battery tech",
  "Cybersecurity threats and trends 2025",
  "Impact of AI on global job markets",
]

const LANGUAGES = [
  "English", "Spanish", "French", "German", "Chinese",
  "Japanese", "Hindi", "Arabic", "Portuguese", "Italian",
  "Korean", "Dutch", "Russian", "Swedish", "Turkish",
]

function getOrCreateSessionId() {
  let id = localStorage.getItem("rsid")
  if (!id) {
    id = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36)
    localStorage.setItem("rsid", id)
  }
  return id
}

function Dot({ status }) {
  let cls = "dot"
  if (status === "running") cls += " pulse"
  else if (status === "done")  cls += " done"
  else if (status === "error") cls += " error"
  return <span className={cls} />
}

function AgentCard({ a, s }) {
  const status = s?.status || "idle"
  let detail = a.idle
  if (status === "running")  detail = s.detail || a.idle
  if (status === "retrying") detail = s.detail || "Retrying..."
  if (status === "done")     detail = s.stat || `${(s.chars || 0).toLocaleString()} chars`
  if (status === "error")    detail = "failed"
  const dotStatus = status === "retrying" ? "running" : status
  const cardClass = status === "retrying" ? "running" : (status !== "idle" ? status : "")

  return (
    <div className={`agent ${cardClass}`}>
      <div className="agent-head">
        <span className="agent-icon">{AGENT_ICONS[a.id] || "◈"}</span>
        <span className="agent-name">{a.label}</span>
        <Dot status={dotStatus} />
      </div>
      <div className={`agent-detail${status === "retrying" ? " agent-retry-text" : ""}`}>
        {detail}
      </div>
      {status === "retrying" && s?.retryCount && (
        <div className="agent-time">attempt {s.retryCount}/3</div>
      )}
      {status === "done" && s?.duration && (
        <div className="agent-time">{s.duration}s</div>
      )}
    </div>
  )
}

function HistoryDrawer({ open, onClose, onLoad }) {
  const [items,   setItems]   = useState([])
  const [loading, setLoading] = useState(false)
  const [fetched, setFetched] = useState(false)

  useEffect(() => {
    if (open && !fetched) {
      setFetched(true)
      setLoading(true)
      fetchHistory()
        .then(d => setItems(Array.isArray(d) ? d : []))
        .catch(() => setItems([]))
        .finally(() => setLoading(false))
    }
    if (!open) setFetched(false)
  }, [open, fetched])

  const handleLoad = async (id) => {
    const r = await fetchReport(id).catch(() => null)
    if (r) { onLoad(r); onClose() }
  }

  const fmt = (iso) => {
    try {
      return new Date(iso).toLocaleDateString("en-US", {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
      })
    } catch { return iso }
  }

  const wc = (text) => text ? text.split(/\s+/).length.toLocaleString() : "—"

  return (
    <>
      {open && <div className="drawer-overlay" onClick={onClose} />}
      <aside className={`drawer ${open ? "drawer-open" : ""}`}>
        <div className="drawer-head">
          <span className="drawer-title">Report History</span>
          <button className="drawer-close" onClick={onClose}>✕</button>
        </div>
        {loading && <div className="drawer-empty">Loading...</div>}
        {!loading && items.length === 0 && (
          <div className="drawer-empty">No reports yet. Run a research to get started.</div>
        )}
        {!loading && items.map(r => (
          <button key={r.id} className="history-row" onClick={() => handleLoad(r.id)}>
            <div className="history-topic">{r.topic}</div>
            <div className="history-meta">
              <span>{fmt(r.created_at)}</span>
              <span>{wc(r.final_report)} words</span>
            </div>
          </button>
        ))}
      </aside>
    </>
  )
}

function ModeToggle({ mode, setMode, disabled }) {
  const current = MODES.find(m => m.id === mode)
  return (
    <div className="mode-wrap">
      <div className="mode-toggle">
        {MODES.map(m => (
          <button
            key={m.id}
            className={`mode-btn ${mode === m.id ? "mode-active" : ""}`}
            onClick={() => setMode(m.id)}
            disabled={disabled}
            title={m.desc}
          >
            {m.label}
          </button>
        ))}
      </div>
      {current && <div className="mode-desc">{current.desc}</div>}
    </div>
  )
}

function HITLPanel({ sessionId, preview, onResume, resuming }) {
  const [feedback, setFeedback] = useState("")

  return (
    <div className="hitl-panel">
      <div className="hitl-head">
        <span className="hitl-badge">HUMAN REVIEW</span>
        <span className="hitl-session">Session: {sessionId}</span>
      </div>
      <div className="hitl-body">
        <p className="hitl-msg">Research is complete. Review the findings above, optionally add feedback, then click Resume.</p>
        {preview && (
          <details className="hitl-preview">
            <summary>Research preview</summary>
            <pre>{preview}</pre>
          </details>
        )}
        <textarea
          className="hitl-feedback"
          placeholder="Optional: Add feedback or additional instructions for the analyst..."
          value={feedback}
          onChange={e => setFeedback(e.target.value)}
          rows={3}
          disabled={resuming}
        />
        <button
          className="btn btn-run hitl-resume-btn"
          onClick={() => onResume(feedback)}
          disabled={resuming}
        >
          {resuming ? "Resuming..." : "Resume Pipeline →"}
        </button>
      </div>
    </div>
  )
}

function RagBanner({ data }) {
  if (!data) return null
  return (
    <div className="rag-banner">
      <span className="rag-icon">⚡</span>
      <span>Similar report found: "<strong>{data.topic}</strong>" — generating fresh analysis anyway.</span>
    </div>
  )
}

const FEATURE_LIST = [
  { icon: "⚡", title: "Sub-60s Reports",    desc: "Full report in under a minute" },
  { icon: "🔍", title: "Live Web Search",    desc: "DuckDuckGo · cited sources" },
  { icon: "🤖", title: "4 AI Agents",        desc: "Research → Analyse → Write → QA" },
  { icon: "🌍", title: "15 Languages",       desc: "Native language output" },
]

function FeatureRow() {
  return (
    <div className="features">
      {FEATURE_LIST.map(f => (
        <div key={f.title} className="feature-card">
          <span className="feature-icon">{f.icon}</span>
          <div>
            <div className="feature-title">{f.title}</div>
            <div className="feature-desc">{f.desc}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function DebateCards({ optimist, skeptic }) {
  if (!optimist && !skeptic) return null
  return (
    <div className="debate-cards">
      {optimist && (
        <div className="debate-card debate-optimist">
          <div className="debate-card-head">Optimist Perspective</div>
          <div className="md debate-card-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{optimist}</ReactMarkdown>
          </div>
        </div>
      )}
      {skeptic && (
        <div className="debate-card debate-skeptic">
          <div className="debate-card-head">Skeptic Analysis</div>
          <div className="md debate-card-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{skeptic}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [query,       setQuery]       = useState("")
  const [mode,        setMode]        = useState("standard")
  const [running,     setRunning]     = useState(false)
  const [agents,      setAgents]      = useState({})
  const [report,      setReport]      = useState(null)
  const [error,       setError]       = useState(null)
  const [showHistory, setShowHistory] = useState(false)
  const [ragHit,      setRagHit]      = useState(null)
  const [debateData,  setDebateData]  = useState({ optimist: null, skeptic: null })
  const [language,    setLanguage]    = useState("English")
  const [sessionId]                   = useState(getOrCreateSessionId)
  const [streamingText, setStreamingText] = useState("")
  const [pastSearches,  setPastSearches] = useState([])

  // HITL state
  const [hitlPaused,    setHitlPaused]    = useState(false)
  const [hitlSessionId, setHitlSessionId] = useState(null)
  const [hitlPreview,   setHitlPreview]   = useState("")
  const [resuming,      setResuming]      = useState(false)

  const reportRef = useRef(null)
  const txRef     = useRef(null)

  const setAgent = useCallback((id, patch) =>
    setAgents(prev => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } })), [])

  const handleEvent = useCallback((event, data) => {
    if (event === "start")         setStreamingText("")
    if (event === "agent_start")   setAgent(data.agent, { status: "running",  detail: data.message })
    if (event === "agent_retry")   setAgent(data.agent, { status: "retrying", detail: data.message, retryCount: data.attempt })
    if (event === "agent_done")    setAgent(data.agent, { status: "done",     duration: data.duration, chars: data.chars, stat: data.stat || null })
    if (event === "agent_error")   setAgent(data.agent, { status: "error",    detail: data.message })
    if (event === "rag_hit")       setRagHit(data)
    if (event === "writer_token")  setStreamingText(t => t + data.token)
    if (event === "revision_start") {
      // Flash the writer back to running state for revisions
      setAgent("writer", { status: "idle", detail: `Revision ${data.revision} starting...` })
      setAgent("reviewer", { status: "idle" })
    }
    if (event === "hitl_pause") {
      setHitlPaused(true)
      setHitlSessionId(data.session_id)
      setHitlPreview(data.research_preview || "")
    }
    if (event === "complete") {
      setReport(data)
      setStreamingText("")
      if (data.optimist_report) setDebateData({ optimist: data.optimist_report, skeptic: data.skeptic_report })
      setRunning(false)
      setResuming(false)
      setHitlPaused(false)
      // Refresh past searches after completion
      fetchMemory(sessionId).then(h => setPastSearches(h)).catch(() => {})
      setTimeout(() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100)
    }
    if (event === "pipeline_error") { setError(data.message); setRunning(false); setResuming(false); setStreamingText("") }
  }, [setAgent])

  const run = async () => {
    if (!query.trim() || running) return
    setRunning(true); setReport(null); setError(null); setAgents({}); setRagHit(null)
    setDebateData({ optimist: null, skeptic: null }); setHitlPaused(false); setHitlSessionId(null)
    setStreamingText("")

    const opts = { language, sessionId }
    try {
      if (mode === "debate") {
        await streamDebate(query.trim(), handleEvent, opts)
      } else if (mode === "hitl") {
        await streamHitl(query.trim(), handleEvent, opts)
      } else {
        await streamResearch(query.trim(), handleEvent, opts)
      }
    } catch (e) { setError(e.message); setRunning(false) }
  }

  const handleResume = async (feedback) => {
    if (!hitlSessionId) return
    setResuming(true); setHitlPaused(false)
    try {
      await streamResume(hitlSessionId, feedback, handleEvent)
    } catch (e) { setError(e.message); setResuming(false); setRunning(false) }
  }

  const reset = () => {
    setQuery(""); setReport(null); setError(null); setAgents({}); setRunning(false)
    setRagHit(null); setDebateData({ optimist: null, skeptic: null })
    setHitlPaused(false); setHitlSessionId(null); setResuming(false); setStreamingText("")
    txRef.current?.focus()
  }

  // Load past searches when going idle
  useEffect(() => {
    if (!running && !report) {
      fetchMemory(sessionId).then(h => setPastSearches(h)).catch(() => {})
    }
  }, [running, report, sessionId])

  const loadHistoryReport = (r) => {
    setReport({ report: r.final_report, query: r.topic, report_id: r.id })
    setAgents({}); setError(null); setRagHit(null); setDebateData({ optimist: null, skeptic: null })
    setTimeout(() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100)
  }

  const pipelineVisible = running || resuming || Object.keys(agents).length > 0
  const currentAgents = mode === "debate" ? DEBATE_AGENTS : STANDARD_AGENTS

  return (
    <div className="shell">
      {/* Nav — dot turns green while running */}
      <nav className="nav">
        <div className="nav-brand">
          <span className={`nav-dot${running ? " nav-dot-live" : ""}`} />
          Research Agent
        </div>
        <div className="nav-spacer" />
        <span className="nav-badge">Groq · LangGraph · LangSmith</span>
        {running && <span className="nav-badge live">● running</span>}
        <button className="btn btn-ghost btn-sm" onClick={() => setShowHistory(h => !h)}>
          History
        </button>
        {report && !running && (
          <button className="btn btn-ghost btn-sm" onClick={reset}>New Research</button>
        )}
      </nav>

      {/* History Drawer */}
      <HistoryDrawer
        open={showHistory}
        onClose={() => setShowHistory(false)}
        onLoad={loadHistoryReport}
      />

      {/* Page */}
      <main className="page">
        {/* Hero — shown when idle */}
        {!pipelineVisible && !report && (
          <div className="hero">
            <div className="hero-eyebrow">
              <span className="hero-live-dot" />
              Groq LLaMA 3.3 70B &nbsp;·&nbsp; LangGraph &nbsp;·&nbsp; LangSmith
            </div>
            <h1>Research anything.<br /><span>In seconds.</span></h1>
            <p>AI agents search the web, extract insights, write and review a full report — automatically.</p>
          </div>
        )}

        {/* Mode Toggle */}
        {!pipelineVisible && !report && (
          <ModeToggle mode={mode} setMode={setMode} disabled={running} />
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
            <span className="input-hint">⌘ Enter to run · {mode} mode</span>
            <select
              className="lang-select"
              value={language}
              onChange={e => setLanguage(e.target.value)}
              disabled={running}
              title="Output language"
            >
              {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <button className="btn btn-run" onClick={run} disabled={running || !query.trim()}>
              {running ? "Researching..." : `Run ${mode === "debate" ? "Debate" : mode === "hitl" ? "HITL" : ""} →`}
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

        {/* Feature row */}
        {!pipelineVisible && !report && <FeatureRow />}

        {/* Past Searches Memory Panel */}
        {!pipelineVisible && !report && pastSearches.length > 0 && (
          <div className="memory-panel">
            <div className="memory-title">Recent Searches</div>
            {pastSearches.slice(-5).reverse().map((s, i) => (
              <button key={i} className="memory-item" onClick={() => { setQuery(s.query); txRef.current?.focus() }}>
                {s.query}
              </button>
            ))}
          </div>
        )}

        {/* RAG Banner */}
        <RagBanner data={ragHit} />

        {/* Error */}
        {error && <div className="err" style={{ marginTop: 20 }}>⚠ {error}</div>}

        {/* Pipeline */}
        {pipelineVisible && (
          <div className="pipeline" style={{ marginTop: 32 }}>
            <div className="pipeline-label">
              Agent Pipeline {mode !== "standard" && <span className="pipeline-mode">· {mode.toUpperCase()}</span>}
            </div>
            <div className={`agents ${currentAgents.length === 5 ? "agents-5" : ""}`}>
              {currentAgents.map(a => (
                <AgentCard key={a.id} a={a} s={agents[a.id]} />
              ))}
            </div>
          </div>
        )}

        {/* Streaming Writer Text */}
        {streamingText && (
          <div className="writer-stream">
            <div className="writer-stream-label">Writing report…</div>
            <pre className="writer-stream-text">{streamingText}</pre>
          </div>
        )}

        {/* HITL Panel */}
        {hitlPaused && (
          <HITLPanel
            sessionId={hitlSessionId}
            preview={hitlPreview}
            onResume={handleResume}
            resuming={resuming}
          />
        )}

        {/* Debate Side-by-Side Cards */}
        {report && mode === "debate" && (
          <DebateCards optimist={debateData.optimist} skeptic={debateData.skeptic} />
        )}

        {/* Report */}
        {report?.report && (
          <div className="report-wrap" ref={reportRef} style={{ marginTop: pipelineVisible ? 24 : 32 }}>
            <div className="report-top">
              <span className="report-top-label">
                Final Report
                {report.quality_score ? ` · Score ${report.quality_score}/10` : ""}
                {report.revisions > 1 ? ` · ${report.revisions} revisions` : ""}
              </span>
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
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => window.print()}
                title="Export as PDF"
              >
                📄 PDF
              </button>
            </div>
            <div className="report-box">
              <div className="md">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.report}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Idle footer */}
        {!pipelineVisible && !report && !error && (
          <div className="idle" style={{ marginTop: 48 }}>
            <span>Groq LLaMA 3.3 70B</span>
            <span className="idle-sep">·</span>
            <span>LangChain</span>
            <span className="idle-sep">·</span>
            <span>LangGraph</span>
            <span className="idle-sep">·</span>
            <span>LangSmith</span>
          </div>
        )}
      </main>
    </div>
  )
}
