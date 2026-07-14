import { APPROACHES, phaseColor, phaseLabel } from '../constants'

// One intersection: current phase + countdown, per-approach queues, and a
// manual override button per approach (plus Auto to release).
export default function SignalCard({ signal, selected, onSelect, onOverride }) {
  const { id, queues = {}, phase, countdown, override } = signal
  const maxQ = Math.max(8, ...APPROACHES.map((a) => queues[a] || 0))

  return (
    <div
      onClick={() => onSelect(id)}
      className={`cursor-pointer rounded-xl bg-slate-900 p-3 ring-1 transition ${
        selected ? 'ring-slate-300' : 'ring-slate-800 hover:ring-slate-700'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-base font-bold">{id}</span>
        <span
          className="rounded px-2 py-0.5 text-xs font-semibold text-slate-950"
          style={{ background: phaseColor(phase) }}
        >
          {phaseLabel(phase)}
        </span>
      </div>

      <div className="mt-1 text-xs text-slate-400">
        {countdown == null ? 'countdown n/a' : `${countdown}s remaining`}
        {override && <span className="ml-2 text-purple-400">override {override}</span>}
      </div>

      <div className="mt-2 space-y-1">
        {APPROACHES.map((a) => {
          const q = queues[a] || 0
          const isGreen = phase === a
          return (
            <div key={a} className="flex items-center gap-2">
              <span className="w-4 text-xs text-slate-400">{a}</span>
              <div className="h-2 flex-1 overflow-hidden rounded bg-slate-800">
                <div
                  className="h-full rounded"
                  style={{ width: `${(q / maxQ) * 100}%`, background: isGreen ? '#22c55e' : '#38bdf8' }}
                />
              </div>
              <span className="w-6 text-right text-xs tabular-nums text-slate-300">{q}</span>
            </div>
          )
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {APPROACHES.map((a) => (
          <button
            key={a}
            onClick={(e) => {
              e.stopPropagation()
              onOverride(id, a)
            }}
            className={`rounded px-2 py-1 text-xs font-medium ${
              override === a ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            }`}
          >
            {a}
          </button>
        ))}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onOverride(id, null)
          }}
          className={`rounded px-2 py-1 text-xs font-medium ${
            override ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-emerald-700 text-white'
          }`}
        >
          Auto
        </button>
      </div>
    </div>
  )
}
