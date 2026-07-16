// Big, obvious "General timing" vs "AI Adaptive" switch for a live before/
// after demo, plus two numbers that quantify the difference as it happens:
// average queue right now, and vehicles cleared since the mode was switched
// (the counter resets on switch so it's a fair side-by-side).
export default function ModeToggle({ mode, avgQueue, served, onChange }) {
  const isAi = mode === 'ai'

  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex overflow-hidden rounded-lg ring-1 ring-slate-700">
          <button
            onClick={() => onChange('fixed')}
            className={`px-4 py-2 text-sm font-semibold transition ${
              !isAi ? 'bg-slate-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            General timing
          </button>
          <button
            onClick={() => onChange('ai')}
            className={`px-4 py-2 text-sm font-semibold transition ${
              isAi ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400 hover:text-slate-200'
            }`}
          >
            AI Adaptive
          </button>
        </div>

        <div className="flex gap-6 text-right text-sm">
          <div>
            <div className="text-xs text-slate-400">avg queue / approach</div>
            <div className="text-lg font-semibold tabular-nums">{avgQueue.toFixed(1)}</div>
          </div>
          <div>
            <div className="text-xs text-slate-400">cleared since switch</div>
            <div className="text-lg font-semibold tabular-nums text-emerald-400">{served}</div>
          </div>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {isAi
          ? 'AI is reallocating green time by demand and skipping empty approaches.'
          : 'Fixed 30s per approach, round robin, regardless of traffic — the way most signals run today.'}{' '}
        Switch modes and watch the average queue react.
      </p>
    </div>
  )
}
