import { APPROACHES } from '../constants'

const YELLOW_S = 4
const ALLRED_S = 2
const MAX_SHOWN = 8 // cars drawn per approach even if the real queue is longer

// Roughly-varied car body colours so the queue reads as real traffic, not a
// single-colour block. Purely cosmetic, cycles by position in the queue.
const CAR_COLORS = ['#f2cc3d', '#4ade80', '#60a5fa', '#f87171', '#c084fc', '#fb923c']

// Estimated seconds until `targetIdx` next gets green, walking the fixed
// N->E->S->W rotation from the currently-active approach (phase_index is
// always the active/transitioning approach, regardless of green/yellow/
// all-red). Returns null only if the feed hasn't sent usable data yet.
function etaSeconds(signal, targetIdx) {
  const { phase_index: active, countdown, greens = {} } = signal
  if (active == null || active < 0 || countdown == null) return null
  const kind = signal.phase
  const isGreenNow = APPROACHES.includes(kind)
  if (isGreenNow && active === targetIdx) return 0

  // seconds remaining until the NEXT approach in rotation starts its green
  let t
  if (isGreenNow) t = countdown + YELLOW_S + ALLRED_S
  else if (kind === 'yellow') t = countdown + ALLRED_S
  else t = countdown // all-red

  let i = (active + 1) % 4
  while (i !== targetIdx) {
    t += (greens[APPROACHES[i]] ?? 30) + YELLOW_S + ALLRED_S
    i = (i + 1) % 4
  }
  return t
}

const DIR = {
  N: { dx: 0, dy: -1 },
  E: { dx: 1, dy: 0 },
  S: { dx: 0, dy: 1 },
  W: { dx: -1, dy: 0 },
}

function Lamp({ cx, cy, color, lit }) {
  return <circle cx={cx} cy={cy} r="5" fill={lit ? color : '#1e293b'} stroke="#0f172a" strokeWidth="1" />
}

// One realistic-ish top-down intersection: roads, queued car icons per
// approach, a real red/yellow/green signal head, and the live countdown /
// estimated-wait numbers — so a viewer watches the AI grant a long green to
// whichever approach is busiest and its queue visibly flow through.
export default function IntersectionView({ signal }) {
  if (!signal) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center rounded-xl bg-slate-900 text-sm text-slate-500 ring-1 ring-slate-800">
        Select an intersection below to view it live
      </div>
    )
  }

  const { id, queues = {}, greens = {}, phase, phase_index: activeIdx, countdown } = signal
  const isGreenNow = APPROACHES.includes(phase)
  const size = 420
  const c = size / 2
  const roadHalf = 40 // half-width of each road surface

  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300">Intersection {id} — live</h2>
        <span className="text-xs text-slate-500">road · signal · queue · AI green plan</span>
      </div>
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full">
        {/* road surfaces */}
        <rect x={c - roadHalf} y="0" width={roadHalf * 2} height={size} fill="#111827" />
        <rect x="0" y={c - roadHalf} width={size} height={roadHalf * 2} fill="#111827" />
        {/* lane dividers (dashed centre lines) */}
        <line x1={c} y1="0" x2={c} y2={c - roadHalf} stroke="#facc15" strokeWidth="1.5" strokeDasharray="8 8" opacity="0.5" />
        <line x1={c} y1={c + roadHalf} x2={c} y2={size} stroke="#facc15" strokeWidth="1.5" strokeDasharray="8 8" opacity="0.5" />
        <line x1="0" y1={c} x2={c - roadHalf} y2={c} stroke="#facc15" strokeWidth="1.5" strokeDasharray="8 8" opacity="0.5" />
        <line x1={c + roadHalf} y1={c} x2={size} y2={c} stroke="#facc15" strokeWidth="1.5" strokeDasharray="8 8" opacity="0.5" />
        {/* intersection surface */}
        <rect x={c - roadHalf} y={c - roadHalf} width={roadHalf * 2} height={roadHalf * 2} fill="#1e293b" />

        {Object.entries(DIR).map(([approach, { dx, dy }]) => {
          const vertical = dx === 0
          const approachIdx = APPROACHES.indexOf(approach)
          const isActive = approachIdx === activeIdx
          const isGreen = isActive && isGreenNow
          const isYellow = isActive && phase === 'yellow'
          const q = queues[approach] || 0
          const shown = Math.min(MAX_SHOWN, q)
          const stopLineR = roadHalf + 4

          // queued / flowing cars, nose pointed at the stop line
          const cars = Array.from({ length: shown }, (_, i) => {
            const r = stopLineR + 14 + i * 20
            const vx = c + dx * r
            const vy = c + dy * r
            const w = vertical ? 20 : 30
            const h = vertical ? 30 : 20
            const color = CAR_COLORS[i % CAR_COLORS.length]
            return (
              <g
                key={i}
                className={isGreen ? 'vehicle-flowing' : ''}
                style={isGreen ? { '--fx': -dx, '--fy': -dy, animationDelay: `${i * 160}ms` } : undefined}
              >
                <rect x={vx - w / 2} y={vy - h / 2} width={w} height={h} rx="5" fill={color} stroke="#0f172a" strokeWidth="1" />
                {/* windshield, offset toward the direction of travel (nose) */}
                <rect
                  x={vx - (vertical ? w * 0.32 : h * 0.32) - (dx ? dx * w * 0.12 : 0)}
                  y={vy - (vertical ? h * 0.32 : w * 0.32) - (dy ? dy * h * 0.12 : 0)}
                  width={vertical ? w * 0.64 : h * 0.64}
                  height={vertical ? h * 0.3 : w * 0.3}
                  rx="2"
                  fill="#0f172a"
                  opacity="0.55"
                />
              </g>
            )
          })

          // signal head just outside the stop line
          const sx = c + dx * (stopLineR - 2) + (vertical ? 18 : 0)
          const sy = c + dy * (stopLineR - 2) + (vertical ? 0 : 18)
          // all-red (or any non-active approach) shows red; only the active
          // approach ever shows yellow or green
          const redLit = !isGreen && !isYellow

          const eta = etaSeconds(signal, approachIdx)

          return (
            <g key={approach}>
              {cars}
              {/* signal head box */}
              <rect x={sx - 8} y={sy - 20} width="16" height="40" rx="3" fill="#0b1220" stroke="#334155" />
              <Lamp cx={sx} cy={sy - 12} color="#ef4444" lit={redLit} />
              <Lamp cx={sx} cy={sy} color="#f59e0b" lit={isYellow} />
              <Lamp cx={sx} cy={sy + 12} color="#22c55e" lit={isGreen} />
              {/* label: approach + queue count */}
              <text x={sx} y={sy - 30} textAnchor="middle" className="fill-slate-300 text-[11px] font-semibold">
                {approach} · {q}
              </text>
              {/* countdown / wait estimate */}
              <text
                x={sx}
                y={sy + 34}
                textAnchor="middle"
                className={
                  isGreen
                    ? 'fill-emerald-400 text-[12px] font-bold'
                    : isYellow
                      ? 'fill-amber-400 text-[11px] font-semibold'
                      : 'fill-slate-500 text-[10px]'
                }
              >
                {isGreen ? `GREEN ${countdown}s` : isYellow ? `YELLOW ${countdown}s` : eta != null ? `wait ~${eta}s` : 'waiting'}
              </text>
            </g>
          )
        })}
      </svg>

      <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
        {APPROACHES.map((a) => (
          <div key={a} className="rounded-lg bg-slate-800/60 p-2">
            <div className="text-slate-400">{a} plan</div>
            <div className={`font-semibold tabular-nums ${greens[a] >= 38 ? 'text-emerald-400' : 'text-slate-300'}`}>
              {greens[a] ?? 30}s
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
