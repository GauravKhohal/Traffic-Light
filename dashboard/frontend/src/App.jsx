import { useEffect, useState } from 'react'
import { connectState, postOverride } from './api'
import GridMap from './components/GridMap'
import IntersectionView from './components/IntersectionView'
import SignalCard from './components/SignalCard'

export default function App() {
  const [signals, setSignals] = useState([])
  const [selected, setSelected] = useState(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const disconnect = connectState((msg) => {
      setConnected(true)
      setSignals(msg.signals || [])
    })
    return disconnect
  }, [])

  // default the close-up view to the first signal once data arrives
  useEffect(() => {
    if (!selected && signals.length) setSelected(signals[0].id)
  }, [signals, selected])

  const onOverride = async (id, approach) => {
    await postOverride(id, approach)
  }

  const selectedSignal = signals.find((s) => s.id === selected)

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">Adaptive Traffic Signal Control</h1>
          <p className="text-sm text-slate-400">Live 3×3 intersection grid</p>
        </div>
        <span
          className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
            connected ? 'bg-emerald-900/60 text-emerald-300' : 'bg-slate-800 text-slate-400'
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-slate-500'}`} />
          {connected ? 'live' : 'connecting…'}
        </span>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <IntersectionView signal={selectedSignal} />
        </div>
        <div>
          <GridMap signals={signals} selected={selected} onSelect={setSelected} />
        </div>
      </div>

      <div className="mb-2 mt-6 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-slate-300">Signals</h2>
        <p className="text-xs text-slate-500">
          <span className="text-emerald-400">green</span> column = AI-planned green time per direction
          (base 30s, up to 60s for busy approaches) · click a card or a map node to zoom in above
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {signals.map((s) => (
          <SignalCard
            key={s.id}
            signal={s}
            selected={s.id === selected}
            onSelect={setSelected}
            onOverride={onOverride}
          />
        ))}
        {signals.length === 0 && (
          <div className="col-span-full rounded-xl bg-slate-900 p-6 text-center text-slate-400 ring-1 ring-slate-800">
            Waiting for signal data…
          </div>
        )}
      </div>

      <footer className="mt-8 text-center text-xs text-slate-500">
        FastAPI + WebSocket · feed: demo or Phase 4 MQTT · overrides publish to the controller
      </footer>
    </div>
  )
}
