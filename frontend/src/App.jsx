import { useState, useCallback, useRef, useEffect } from "react"
import { streamResearch, fetchHistory, fetchReport, fetchMemory, fetchDocuments, uploadDocument, deleteDocument } from "./api"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

const STANDARD_AGENTS = [
  { id: "researcher", label: "Researcher", idle: "Web search" },
  { id: "analyst", label: "Analyst", idle: "Evidence analysis" },
  { id: "writer",    label: "Writer",     idle: "Report"    },
  { id: "reviewer",  label: "Reviewer",   idle: "QA"        },
]

const WORKFLOW_STEPS = [
  { id: "researcher", label: "Web Search", icon: "⌕" },
  { id: "analyst", label: "Analyse", icon: "◇" },
  { id: "writer", label: "Writer", icon: "✦" },
  { id: "reviewer", label: "Reviewer", icon: "✓" },
  { id: "completed", label: "Completed", icon: "✓" },
]

const AGENT_ICONS = {}


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
    <div className={`agent ${cardClass}`} aria-live={status === "running" ? "polite" : undefined}>
      <div className="agent-head">
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

function HistoryDrawer({ open, onClose, onLoad, sessionId }) {
  const [items,   setItems]   = useState([])
  const [loading, setLoading] = useState(false)
  const [fetched, setFetched] = useState(false)

  useEffect(() => {
    if (open && !fetched) {
      setFetched(true)
      setLoading(true)
      fetchHistory(sessionId)
        .then(d => setItems(Array.isArray(d) ? d : []))
        .catch(() => setItems([]))
        .finally(() => setLoading(false))
    }
    if (!open) setFetched(false)
  }, [open, fetched])

  const handleLoad = async (id) => {
    const r = await fetchReport(id, sessionId).catch(() => null)
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
  { num: "01", title: "Sub-60s Reports",  desc: "Full report in under a minute"       },
  { num: "02", title: "Live Web Search",  desc: "DuckDuckGo · cited sources"          },
  { num: "03", title: "4 AI Agents",      desc: "Research → Analyse → Write → QA"   },
  { num: "04", title: "15 Languages",     desc: "Native language output"              },
]

function FeatureRow() {
  return (
    <div className="features">
      {FEATURE_LIST.map(f => (
        <div key={f.title} className="feature-card">
          <div className="feature-num">{f.num}</div>
          <div className="feature-title">{f.title}</div>
          <div className="feature-desc">{f.desc}</div>
        </div>
      ))}
    </div>
  )
}

function WorkflowSteps({ agents, completed, failed }) {
  const getStatus = (step) => {
    if (step.id === "completed") return completed ? "done" : "idle"
    if (failed && agents[step.id]?.status === "error") return "error"
    return agents[step.id]?.status || "idle"
  }

  return (
    <div className="workflow" aria-label="Research workflow progress">
      {WORKFLOW_STEPS.map((step, index) => {
        const status = getStatus(step)
        return <div className={`workflow-step workflow-${status}`} key={step.id}>
          <div className="workflow-marker" aria-hidden="true">
            {status === "done" ? "✓" : status === "error" ? "!" : step.icon}
          </div>
          <span>{step.label}</span>
          {index < WORKFLOW_STEPS.length - 1 && <i className="workflow-line" aria-hidden="true" />}
        </div>
      })}
    </div>
  )
}

function DocumentsPanel({ documents, uploading, onUpload, onDelete }) {
  const inputRef = useRef(null)
  return (
    <section className="documents-panel">
      <div className="documents-head">
        <div><div className="documents-title">Uploaded Documents</div><div className="documents-subtitle">PDFs are searched alongside web research</div></div>
        <input ref={inputRef} type="file" accept="application/pdf" hidden onChange={e => e.target.files?.[0] && onUpload(e.target.files[0])} />
        <button className="btn btn-ghost btn-sm" onClick={() => inputRef.current?.click()} disabled={uploading}>
          {uploading ? "Uploading…" : "Upload PDF"}
        </button>
      </div>
      {uploading && <div className="upload-progress"><span /></div>}
      {documents.length === 0 ? <div className="documents-empty">No PDFs uploaded yet.</div> : documents.map(doc => (
        <div className="document-row" key={doc.id}>
          <div><strong>{doc.filename}</strong><span>{doc.chunks} chunks</span></div>
          <button className="document-delete" onClick={() => onDelete(doc.id)}>Delete</button>
        </div>
      ))}
    </section>
  )
}

function RetrievedSources({ sources }) {
  if (!sources.length) return null
  return <section className="sources-panel"><div className="documents-title">Retrieved PDF Sources</div>
    {sources.map((source, index) => <div className="source-row" key={`${source.chunk_id}-${index}`}>
      <strong>[{source.metadata?.filename || "Document"} p.{source.page_number}]</strong><span>score {source.score}</span><p>{source.chunk_text}</p>
    </div>)}
  </section>
}

export default function App() {
  const [query,       setQuery]       = useState("")
  const [running,     setRunning]     = useState(false)
  const [agents,      setAgents]      = useState({})
  const [report,      setReport]      = useState(null)
  const [error,       setError]       = useState(null)
  const [showHistory, setShowHistory] = useState(false)
  const [ragHit,      setRagHit]      = useState(null)
  const [language,    setLanguage]    = useState("English")
  const [sessionId]                   = useState(getOrCreateSessionId)
  const [streamingText, setStreamingText] = useState("")
  const [pastSearches,  setPastSearches] = useState([])
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [retrievedSources, setRetrievedSources] = useState([])

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
    if (event === "retrieved_sources") setRetrievedSources(data.sources || [])
    if (event === "writer_token")  setStreamingText(t => t + data.token)
    if (event === "revision_start") {
      // Flash the writer back to running state for revisions
      setAgent("writer", { status: "idle", detail: `Revision ${data.revision} starting...` })
      setAgent("reviewer", { status: "idle" })
    }
    if (event === "complete") {
      setReport(data)
      setStreamingText("")
      setRunning(false)
      // Refresh past searches after completion
      fetchMemory(sessionId).then(h => setPastSearches(h)).catch(() => {})
      setTimeout(() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100)
    }
    if (event === "pipeline_error") { setError(data.message); setRunning(false); setStreamingText("") }
  }, [setAgent])

  const run = async () => {
    if (!query.trim() || running) return
    setRunning(true); setReport(null); setError(null); setAgents({}); setRagHit(null)
    setRetrievedSources([])
    setStreamingText("")

    const opts = { language, sessionId }
    try {
      await streamResearch(query.trim(), handleEvent, opts)
    } catch (e) { setError(e.message); setRunning(false) }
  }

  const reset = () => {
    setQuery(""); setReport(null); setError(null); setAgents({}); setRunning(false)
    setRagHit(null)
    setStreamingText("")
    txRef.current?.focus()
  }

  // Load past searches when going idle
  useEffect(() => {
    if (!running && !report) {
      fetchMemory(sessionId).then(h => setPastSearches(h)).catch(() => {})
    }
  }, [running, report, sessionId])

  useEffect(() => { fetchDocuments(sessionId).then(d => setDocuments(Array.isArray(d) ? d : [])).catch(() => {}) }, [sessionId])

  const handleUpload = async (file) => {
    setUploading(true); setError(null)
    try { await uploadDocument(file, sessionId); setDocuments(await fetchDocuments(sessionId)) }
    catch (e) { setError(e.message) }
    finally { setUploading(false) }
  }

  const handleDeleteDocument = async (id) => {
    try { await deleteDocument(id, sessionId); setDocuments(d => d.filter(doc => doc.id !== id)) }
    catch (e) { setError(e.message) }
  }

  const loadHistoryReport = (r) => {
    setReport({ report: r.final_report, query: r.topic, report_id: r.id })
    setAgents({}); setError(null); setRagHit(null)
    setTimeout(() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100)
  }

  const pipelineVisible = running || Object.keys(agents).length > 0
  const currentAgents = STANDARD_AGENTS

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
        sessionId={sessionId}
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
            <span className="input-hint">⌘ Enter to run · four-agent research</span>
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
              {running ? "Researching..." : "Run Research →"}
            </button>
          </div>
        </div>

        <DocumentsPanel documents={documents} uploading={uploading} onUpload={handleUpload} onDelete={handleDeleteDocument} />

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
        {error && <div className="err" role="alert" style={{ marginTop: 20 }}><span>!</span><div><strong>Research interrupted</strong><br />{error}</div></div>}

        {/* Pipeline */}
        {pipelineVisible && (
          <div className="pipeline" style={{ marginTop: 32 }}>
            <div className="pipeline-label">
              Agent Pipeline
            </div>
            <WorkflowSteps agents={agents} completed={Boolean(report)} failed={Boolean(error)} />
            <div className="agents">
              {currentAgents.map(a => (
                <AgentCard key={a.id} a={a} s={agents[a.id]} />
              ))}
            </div>
          </div>
        )}

        {/* Streaming Writer Text */}
        {streamingText && (
          <div className="writer-stream" aria-live="polite">
            <div className="writer-stream-label"><span className="stream-dot" />Writing report<span className="stream-ellipsis">…</span></div>
            <pre className="writer-stream-text">{streamingText}</pre>
          </div>
        )}

        <RetrievedSources sources={retrievedSources} />
        {report && (
          <div className="report" ref={reportRef}>
            <div className="report-head">
              <span className="report-title">
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
