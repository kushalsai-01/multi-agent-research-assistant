const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Stream a research pipeline via SSE.
 * Calls onEvent(event, data) for each SSE event received.
 * Returns a Promise that resolves when the stream closes.
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

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })

    // Parse SSE chunks
    const parts = buf.split('\n\n')
    buf = parts.pop() // keep incomplete chunk

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
