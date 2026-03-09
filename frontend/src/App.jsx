import { useState, useCallback, useEffect } from 'react'
import { streamResearch, fetchHistory, fetchReport } from './api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ─── Agent metadata ──────────────────────────────────────────────────────────

const AGENTS = [
  { id: 'researcher', label: 'Researcher', icon: '⬡', desc: 'Web search' },
  { id: 'analyst',   label: 'Analyst',    icon: '⬡', desc: 'Insights' },
  { id: 'writer',    label: 'Writer',     icon: '⬡', desc: 'Report' },
  { id: 'reviewer',  label: 'Reviewer',   icon: '⬡', desc: 'Quality' },
]

const EXAMPLES = [
  'Latest breakthroughs in quantum computing 2025',
  'How is AI transforming healthcare?',
  'Future of electric vehicles and battery tech',
  'Cybersecurity threats and trends in 2025',
  'Impact of climate change on global food supply',
]

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusDot({ status }) {
  let cls = 'status-dot'
  if (status === 'running') cls += ' pulse'
  else if (status === 'done') cls += ' done'
  else if (status === 'error') cls += ' error'
  return <span className={cls} />
}

// ─── Agent card ───────────────────────────────────────────────────────────────

function AgentCard({ agent, agentState }) {
  const s = agentState[agent.id] || {}
  const status = s.status || 'idle'

  return (
    <div className={`agent-card ${status !== 'idle' ? status : ''}`}>
      <div className="agent-icon">{agent.icon}</div>
      <div className="agent-name">{agent.label}</div>
      <div className="agent-msg">
        {status === 'running' ? s.message
          : status === 'done'    ? `${s.chars?.toLocaleString()} chars`
          : status === 'error'   ? 'failed'
          : agent.desc}
      </div>
      <div className="agent-status">
        <StatusDot status={status} />
        <span>
          {status === 'idle'    ? 'waiting'
            : status === 'running' ? 'running'
            : status === 'done'    ? 'done'
            : 'error'}
        </span>
        {s.duration && (
          <span className="agent-duration">{s.duration}s</span>
        )}
      </div>
    </div>
  )
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────

function Sidebar({ history, activeId, onSelect, onNewSession }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-mark">
            <svg viewBox="0 0 16 16">
              <path d="M8 1L15 5v6L8 15 1 11V5L8 1z" />
            </svg>
          </div>
          Research
        </div>
      </div>

      <div style={{ padding: '12px 8px 4px' }}>
        <button
          className="btn btn-ghost"
          style={{ width: '100%', justifyContent: 'center', fontSize: 12 }}
          onClick={onNewSession}
        >
          + New Research
        </button>
      </div>

      <div className="sidebar-label">History</div>

      <div className="sidebar-body">
        {history.length === 0 ? (
          <div className="empty-history">No reports yet</div>
        ) : (
          history.map((h) => (
            <button
              key={h.id}
              className={`history-item ${h.id === activeId ? 'active' : ''}`}
              onClick={() => onSelect(h.id)}
              title={h.topic}
            >
              {h.topic}
              <div className="history-date">
                {new Date(h.created_at).toLocaleDateString()}
              </div>
            </button>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        LangChain · LangGraph · LangSmith
      </div>
    </aside>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [query, setQuery]           = useState('')
  const [running, setRunning]       = useState(false)
  const [agentState, setAgentState] = useState({})
  const [report, setReport]         = useState(null)
  const [error, setError]           = useState(null)
  const [history, setHistory]       = useState([])
  const [activeId, setActiveId]     = useState(null)

  // Load history on mount
  useEffect(() => {
    fetchHistory().then(setHistory).catch(() => {})
  }, [])

  // Update a single agent's state
  const setAgent = useCallback((id, patch) => {
    setAgentState((prev) => ({ ...prev, [id]: { ...(prev[id] || {}), ...patch } }))
  }, [])

  // Handle SSE events from backend
  const handleEvent = useCallback((event, data) => {
    switch (event) {
      case 'agent_start':
        setAgent(data.agent, { status: 'running', message: data.message })
        break
      case 'agent_done':
        setAgent(data.agent, { status: 'done', duration: data.duration, chars: data.chars })
        break
      case 'agent_error':
        setAgent(data.agent, { status: 'error', message: data.message })
        break
      case 'complete':
        setReport(data)
        setRunning(false)
        fetchHistory().then(setHistory).catch(() => {})
        break
      case 'pipeline_error':
        setError(data.message)
        setRunning(false)
        break
      default:
        break
    }
  }, [setAgent])

  const handleRun = async () => {
    if (!query.trim() || running) return
    setRunning(true)
    setReport(null)
    setError(null)
    setAgentState({})
    setActiveId(null)

    try {
      await streamResearch(query.trim(), handleEvent)
    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  const handleSelectHistory = async (id) => {
    setActiveId(id)
    setReport(null)
    setError(null)
    setRunning(false)
    setAgentState({})
    try {
      const r = await fetchReport(id)
      setReport({ report: r.final_report, query: r.topic, report_id: r.id })
      setQuery(r.topic)
    } catch (e) {
      setError('Could not load report.')
    }
  }

  const handleNewSession = () => {
    setQuery('')
    setReport(null)
    setError(null)
    setAgentState({})
    setActiveId(null)
    setRunning(false)
  }

  const pipelineActive = running || Object.keys(agentState).length > 0

  return (
    <div className="layout">
      <Sidebar
        history={history}
        activeId={activeId}
        onSelect={handleSelectHistory}
        onNewSession={handleNewSession}
      />

      <div className="main">
        {/* Topbar */}
        <div className="topbar">
          <span className="topbar-title">AI Research Assistant</span>
          <span className="topbar-pill">4-agent pipeline</span>
          {running && <span className="topbar-pill" style={{ color: '#fff', borderColor: '#444' }}>● running</span>}
        </div>

        {/* Content */}
        <div className="content">

          {/* Query input */}
          <div className="query-section">
            <h1 className="query-heading">What should we research?</h1>
            <p className="query-sub">
              4 AI agents will search, analyze, write, and review a report on any topic.
            </p>

            <div className="query-box">
              <textarea
                className="query-textarea"
                placeholder="e.g. Impact of AI on healthcare in 2025..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleRun()
                }}
                disabled={running}
                rows={3}
              />
              <div className="query-footer">
                <span className="query-hint">⌘ + Enter to run</span>
                <button
                  className="btn btn-primary"
                  onClick={handleRun}
                  disabled={running || !query.trim()}
                >
                  {running ? 'Running...' : 'Run Research →'}
                </button>
              </div>
            </div>

            {/* Example chips */}
            {!running && !pipelineActive && (
              <div className="examples">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    className="example-chip"
                    onClick={() => setQuery(ex)}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Error */}
          {error && <div className="error-box">⚠ {error}</div>}

          {/* Agent progress */}
          {pipelineActive && (
            <div className="pipeline-section">
              <div className="section-label">Agent Pipeline</div>
              <div className="agent-grid">
                {AGENTS.map((a) => (
                  <AgentCard key={a.id} agent={a} agentState={agentState} />
                ))}
              </div>
            </div>
          )}

          {/* Report */}
          {report?.report ? (
            <div className="report-section">
              <div className="report-header">
                <div className="section-label">Final Report</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    className="btn btn-ghost"
                    onClick={() => {
                      const blob = new Blob([report.report], { type: 'text/markdown' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `research-${Date.now()}.md`
                      a.click()
                      URL.revokeObjectURL(url)
                    }}
                  >
                    ↓ Download .md
                  </button>
                  <button
                    className="btn btn-ghost"
                    onClick={() => navigator.clipboard.writeText(report.report)}
                  >
                    Copy
                  </button>
                </div>
              </div>

              <div className="report-box">
                <div className="md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {report.report}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          ) : !pipelineActive && !error ? (
            <div className="idle-state">
              <h2>Ready to research</h2>
              <p>Enter a topic above and hit Run Research.</p>
            </div>
          ) : null}

        </div>
      </div>
    </div>
  )
}
