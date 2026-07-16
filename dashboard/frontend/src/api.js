// REST + WebSocket helpers. Same-origin in production (backend serves the
// build); Vite proxies these to the backend in dev.

export async function postOverride(signalId, approach) {
  const res = await fetch(`/api/signals/${signalId}/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approach }),
  })
  return res.json()
}

// mode: "fixed" (plain round-robin, ignores demand) or "ai" (adaptive)
export async function postMode(mode) {
  const res = await fetch('/api/mode', {
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
  const connect = () => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/ws`)
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
