import { APPROACHES, activeApproaches, isGreenPhase, phaseColor, phaseLabel } from '../constants'

// Green time (s) coloured relative to the 30s base: boosted = emerald, trimmed = dim.
function greenStyle(g) {
  if (g == null) return 'text-slate-500'
  if (g >= 38) return 'text-emerald-400 font-semibold'
  if (g <= 22) return 'text-slate-500'
  return 'text-slate-300'
}

// One intersection: current phase + countdown, and per approach the queue plus
// the AI-planned green time (which grows for busier directions). Manual
// override button per approach, Auto to release.
export default function SignalCard({ signal, selected, onSelect, onOverride }) {
  const { id, queues = {}, greens = {}, phase, countdown, override } = signal
  const maxQ = Math.max(8, ...APPROACHES.map((a) => queues[a] || 0))
  const hasGreens = Object.keys(greens).length > 0
  const active = activeApproaches(signal)
  const isSurge = isGreenPhase(phase) && phase.length === 2

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

      {isSurge && (
        <div className="mt-2 rounded bg-emerald-950/60 px-2 py-1 text-[11px] font-medium text-emerald-400">
          High traffic: {phase[0]}+{phase[1]} run straight together, right turns held
        </div>
      )}

      <div className="mt-2 grid grid-cols-[0.9rem_1fr_1.3rem_2.4rem] items-center gap-x-2 text-[11px] text-slate-500">
        <span></span>
        <span>queue</span>
        <span className="text-right">cars</span>
        <span className="text-right">green</span>
      </div>
      <div className="mt-1 space-y-1">
        {APPROACHES.map((a) => {
          const q = queues[a] || 0
          const g = hasGreens ? greens[a] : null
          const isGreen = active.includes(a) && isGreenPhase(phase)
          return (
            <div key={a} className="grid grid-cols-[0.9rem_1fr_1.3rem_2.4rem] items-center gap-x-2">
              <span className="text-xs text-slate-400">{a}</span>
              <div className="h-2 overflow-hidden rounded bg-slate-800">
                <div
                  className="h-full rounded"
                  style={{ width: `${(q / maxQ) * 100}%`, background: isGreen ? '#22c55e' : '#38bdf8' }}
                />
              </div>
              <span className="text-right text-xs tabular-nums text-slate-300">{q}</span>
              <span className={`text-right text-xs tabular-nums ${greenStyle(g)}`}>
                {g == null ? '—' : `${g}s`}
              </span>
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
