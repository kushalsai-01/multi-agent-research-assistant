const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Generic SSE stream reader.
 * Calls onEvent(event, data) for each SSE event received.
 */
async function readSSEStream(res, onEvent) {
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })

    const parts = buf.split('\n\n')
    buf = parts.pop()

    for (const part of parts) {
      const lines = part.trim().split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) event = line.slice(7)
        if (line.startsWith('data: ')) data = line.slice(6)
      }
      if (data) {
        try {
          onEvent(event, JSON.parse(data))
        } catch {
          onEvent(event, { raw: data })
        }
      }
    }
  }
}

/**
 * Stream a standard research pipeline via SSE.
 */
export async function streamResearch(query, onEvent) {
  const res = await fetch(`${API_BASE}/api/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  await readSSEStream(res, onEvent)
}

/**
 * Stream a debate pipeline via SSE.
 */
export async function streamDebate(query, onEvent) {
  const res = await fetch(`${API_BASE}/api/research/debate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Debate request failed')
  }

  await readSSEStream(res, onEvent)
}

/**
 * Stream a HITL pipeline via SSE (pauses after researcher).
 */
export async function streamHitl(query, onEvent) {
  const res = await fetch(`${API_BASE}/api/research/hitl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'HITL request failed')
  }

  await readSSEStream(res, onEvent)
}

/**
 * Resume a paused HITL pipeline with optional feedback.
 */
export async function streamResume(sessionId, feedback, onEvent) {
  const res = await fetch(`${API_BASE}/api/research/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, feedback }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Resume failed')
  }

  await readSSEStream(res, onEvent)
}

/** Fetch report history from Supabase (via backend). */
export async function fetchHistory() {
  const res = await fetch(`${API_BASE}/api/reports`)
  if (!res.ok) return []
  return res.json()
}

/** Fetch a single full report. */
export async function fetchReport(id) {
  const res = await fetch(`${API_BASE}/api/reports/${id}`)
  if (!res.ok) throw new Error('Report not found')
  return res.json()
}
