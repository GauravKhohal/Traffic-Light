// REST + WebSocket helpers. Same-origin by default (backend serves the
// build, Vite proxies in dev). Set VITE_API_BASE (e.g. in Vercel) to point
// at a backend hosted on a different origin, such as a Railway deployment.
const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

export async function postOverride(signalId, approach) {
  const res = await fetch(`${API_BASE}/api/signals/${signalId}/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approach }),
  })
  return res.json()
}

// mode: "fixed" (plain round-robin, ignores demand) or "ai" (adaptive)
export async function postMode(mode) {
  const res = await fetch(`${API_BASE}/api/mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
  return res.json()
}

// Connect to the live state WebSocket, auto-reconnecting on drop.
export function connectState(onMessage) {
  let ws
  let closed = false
  const wsBase = API_BASE
    ? API_BASE.replace(/^http/, 'ws')
    : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`
  const connect = () => {
    ws = new WebSocket(`${wsBase}/ws`)
    ws.onmessage = (e) => onMessage(JSON.parse(e.data))
    ws.onclose = () => {
      if (!closed) setTimeout(connect, 1000)
    }
  }
  connect()
  return () => {
    closed = true
    if (ws) ws.close()
  }
}
