// Local development works without a frontend .env file; deployed builds still
// use VITE_API_URL (for example, the Render backend URL).
const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

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
export async function streamResearch(query, onEvent, { language = 'English', sessionId = '' } = {}) {
  const res = await fetch(`${API_BASE}/api/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, language, session_id: sessionId }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  await readSSEStream(res, onEvent)
}

/** Fetch report history from Supabase (via backend). */
const sessionHeaders = (sessionId) => ({ 'X-Session-Id': sessionId })

export async function fetchHistory(sessionId) {
  const res = await fetch(`${API_BASE}/api/reports`, { headers: sessionHeaders(sessionId) })
  if (!res.ok) return []
  return res.json()
}

/** Fetch a single full report. */
export async function fetchReport(id, sessionId) {
  const res = await fetch(`${API_BASE}/api/reports/${id}`, { headers: sessionHeaders(sessionId) })
  if (!res.ok) throw new Error('Report not found')
  return res.json()
}

/** Fetch session memory (past queries) for a given session ID. */
export async function fetchMemory(sessionId) {
  if (!sessionId) return []
  const res = await fetch(`${API_BASE}/api/memory/${sessionId}`)
  if (!res.ok) return []
  const d = await res.json()
  return Array.isArray(d.history) ? d.history : []
}

export async function fetchDocuments(sessionId) {
  const res = await fetch(`${API_BASE}/api/documents`, { headers: sessionHeaders(sessionId) })
  if (!res.ok) return []
  return res.json()
}

export async function uploadDocument(file, sessionId) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/documents`, { method: 'POST', headers: sessionHeaders(sessionId), body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(err.detail || 'Upload failed')
  }
  return res.json()
}

export async function deleteDocument(id, sessionId) {
  const res = await fetch(`${API_BASE}/api/documents/${id}`, { method: 'DELETE', headers: sessionHeaders(sessionId) })
  if (!res.ok) throw new Error('Could not delete document')
}
