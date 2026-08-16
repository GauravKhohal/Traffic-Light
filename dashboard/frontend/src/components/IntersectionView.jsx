import { APPROACHES, activeApproaches, isGreenPhase } from '../constants'

const YELLOW_S = 4
const ALLRED_S = 2
const MAX_SHOWN = 8 // cars drawn per approach even if the real queue is longer

// Roughly-varied car body colours so the queue reads as real traffic, not a
// single-colour block. Purely cosmetic, cycles by position in the queue.
const CAR_COLORS = ['#f2cc3d', '#4ade80', '#60a5fa', '#f87171', '#c084fc', '#fb923c']

// Estimated seconds until `targetIdx` next gets green, walking the fixed
// N->E->S->W rotation from the currently-active approach (phase_index is
// always the first active/transitioning approach, regardless of green/
// yellow/all-red). Mirrors the backend's skip-empty-approach behaviour: an
// approach with zero queued vehicles right now is assumed to be skipped
// entirely (no time added), so a busy approach's estimate reflects that it's
// promoted ahead of empty ones rather than waiting through them. Does not
// account for a high-traffic surge that might get inserted along the way
// (that depends on future queue levels), so this is an approximation during
// AI mode. Returns null only if the feed hasn't sent usable data yet.
function etaSeconds(signal, targetIdx) {
  const { phase_index: active, countdown, greens = {}, queues = {} } = signal
  if (active == null || active < 0 || countdown == null) return null
  const kind = signal.phase
  const isGreenNow = isGreenPhase(kind)
  if (isGreenNow && activeApproaches(signal).includes(APPROACHES[targetIdx])) return 0

  // seconds remaining until the NEXT approach in rotation starts its green
  let t
  if (isGreenNow) t = countdown + YELLOW_S + ALLRED_S
  else if (kind === 'yellow') t = countdown + ALLRED_S
  else t = countdown // all-red

  let i = (active + 1) % 4
  while (i !== targetIdx) {
    if ((queues[APPROACHES[i]] || 0) > 0) {
      t += (greens[APPROACHES[i]] ?? 30) + YELLOW_S + ALLRED_S
    }
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

  const { id, queues = {}, movements = {}, greens = {}, phase, countdown } = signal
  const active = activeApproaches(signal)
  const isGreenNow = isGreenPhase(phase)
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
          const isActive = active.includes(approach)
          const isGreen = isActive && isGreenNow
          const isYellow = isActive && phase === 'yellow'
          // a surge (2-letter phase code) opens straight for both paired
          // approaches but holds right; a solo green (1-letter code) opens both
          const isSurge = isGreen && phase.length === 2
          const rightGreen = isGreen && phase.length === 1
          const mv = movements[approach]
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
          // approach ever shows yellow or green — this is the STRAIGHT signal
          const redLit = !isGreen && !isYellow
          // left and right sit either side of the main head (vertical
          // approaches) or above/below it (horizontal approaches)
          const lOffset = vertical ? { x: -16, y: 0 } : { x: 0, y: -16 }
          const rOffset = vertical ? { x: 16, y: 0 } : { x: 0, y: 16 }

          const eta = etaSeconds(signal, approachIdx)

          return (
            <g key={approach}>
              {cars}
              {/* signal head box (straight movement) */}
              <rect x={sx - 8} y={sy - 20} width="16" height="40" rx="3" fill="#0b1220" stroke="#334155" />
              <Lamp cx={sx} cy={sy - 12} color="#ef4444" lit={redLit} />
              <Lamp cx={sx} cy={sy} color="#f59e0b" lit={isYellow} />
              <Lamp cx={sx} cy={sy + 12} color="#22c55e" lit={isGreen} />

              {/* left: always free-flowing, every approach, every phase */}
              <Lamp cx={sx + lOffset.x} cy={sy + lOffset.y} color="#22c55e" lit />
              <text
                x={sx + lOffset.x}
                y={sy + lOffset.y + 13}
                textAnchor="middle"
                className="fill-emerald-500 text-[8px] font-bold"
              >
                L
              </text>

              {/* right: held during a paired straight-only surge */}
              <Lamp cx={sx + rOffset.x} cy={sy + rOffset.y} color={rightGreen ? '#22c55e' : '#ef4444'} lit />
              <text
                x={sx + rOffset.x}
                y={sy + rOffset.y + 13}
                textAnchor="middle"
                className={rightGreen ? 'fill-emerald-500 text-[8px] font-bold' : 'fill-red-500 text-[8px] font-bold'}
              >
                R
              </text>

              {/* label: approach + queue count (+ L/S/R breakdown when known) */}
              <text x={sx} y={sy - 30} textAnchor="middle" className="fill-slate-300 text-[11px] font-semibold">
                {approach} · {q}
                {mv ? ` (L${mv.L}·S${mv.S}·R${mv.R})` : ''}
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
                {isGreen
                  ? isSurge
                    ? `STRAIGHT ${countdown}s (R held)`
                    : `GREEN ${countdown}s`
                  : isYellow
                    ? `YELLOW ${countdown}s`
                    : eta != null
                      ? `wait ~${eta}s`
                      : 'waiting'}
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

      <StatusList signal={signal} active={active} isGreenNow={isGreenNow} phase={phase} countdown={countdown} />
    </div>
  )
}

// Unambiguous, plain-text readout — one row per approach, in the order it
// will actually be served, so there's no small overlapping SVG text to
// misread. This is the same eta/skip logic as the diagram, just spelled out.
function StatusList({ signal, active, isGreenNow, phase, countdown }) {
  const { queues = {}, movements = {} } = signal
  const isSurge = isGreenNow && phase.length === 2
  const rows = APPROACHES.map((a, i) => {
    const q = queues[a] || 0
    const isActive = active.includes(a)
    return {
      approach: a,
      queue: q,
      mv: movements[a],
      isActive,
      isGreen: isActive && isGreenNow,
      isYellow: isActive && phase === 'yellow',
      rightHeld: isActive && isGreenNow && isSurge,
      eta: isActive ? 0 : etaSeconds(signal, i),
    }
  })
  rows.sort((a, b) => (b.isActive - a.isActive) || (a.eta ?? 1e9) - (b.eta ?? 1e9))

  return (
    <div className="mt-3 divide-y divide-slate-800 rounded-lg bg-slate-800/40 text-sm">
      {isSurge && (
        <div className="px-3 py-1.5 text-xs font-semibold text-emerald-400">
          High traffic on {phase[0]} + {phase[1]}: both run straight together, right turns held
        </div>
      )}
      {rows.map((r) => (
        <div key={r.approach} className="flex items-center justify-between px-3 py-1.5">
          <span className="flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                r.isGreen ? 'bg-emerald-400' : r.isYellow ? 'bg-amber-400' : 'bg-slate-600'
              }`}
            />
            <span className="font-semibold">{r.approach}</span>
            <span className="text-slate-400">
              · {r.queue} car{r.queue === 1 ? '' : 's'}
              {r.mv ? ` (L${r.mv.L} · S${r.mv.S} · R${r.mv.R})` : ''}
            </span>
          </span>
          <span className={r.isGreen ? 'font-semibold text-emerald-400' : r.isYellow ? 'text-amber-400' : 'text-slate-400'}>
            {r.isGreen
              ? r.rightHeld
                ? `STRAIGHT, ${countdown}s left (right held)`
                : `GREEN, ${countdown}s left`
              : r.isYellow
                ? `yellow, ${countdown}s`
                : r.queue === 0
                  ? 'empty — will be skipped'
                  : `next in ~${r.eta}s`}
          </span>
        </div>
      ))}
      <div className="px-3 py-1.5 text-xs text-slate-500">
        Left turns flow continuously on every approach — never held by the signal.
      </div>
    </div>
  )
}
