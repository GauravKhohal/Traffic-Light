import { APPROACHES, activeApproaches, isGreenPhase } from '../constants'

const YELLOW_S = 4
const ALLRED_S = 2
const MAX_SHOWN = 11 // cars drawn per approach even if the real queue is longer

// Roughly-varied car body colours so the queue reads as real traffic, not a
// single-colour block. Purely cosmetic, cycles by position in the queue.
const CAR_COLORS = ['#f2cc3d', '#4ade80', '#60a5fa', '#f87171', '#c084fc', '#fb923c']

const LANE_OFFSET_PX = 9 // lateral gap between the left/straight/right sub-lanes
const MAX_PER_TURN_LANE = 4 // left/right lanes shown at most this many, straight fills the rest

function avg(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
}

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

// A right turn off an approach shares its corner with the free-flowing left
// turn one step counter-clockwise: W's right (W -> S) crosses S's left
// (S -> W) at the south-west corner, and so on around the intersection
// (N<-W, E<-N, S<-E, W<-S). Since that left is never held, the right turn
// has to yield to it instead - mirrors feeds.py's CONFLICTING_LEFT.
const CONFLICTING_LEFT_APPROACH = { N: 'W', E: 'N', S: 'E', W: 'S' }

// A real signal head shows one lit arrow per movement currently allowed, not
// a plain ball - a driver sees exactly which ways they may go. `ux,uy` is the
// direction the arrow points; each movement's arrow is coloured independently
// (e.g. a green straight arrow next to a red right arrow during a surge).
function Arrow({ cx, cy, ux, uy, color, len = 7, halfW = 3 }) {
  const tipX = cx + ux * len
  const tipY = cy + uy * len
  const baseX = cx - ux * len * 0.5
  const baseY = cy - uy * len * 0.5
  const px = -uy
  const py = ux
  const points = [
    `${tipX},${tipY}`,
    `${baseX + px * halfW},${baseY + py * halfW}`,
    `${baseX - px * halfW},${baseY - py * halfW}`,
  ].join(' ')
  return <polygon points={points} fill={color} stroke="#0f172a" strokeWidth="1" strokeLinejoin="round" />
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
  const size = 520
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
          const conflictLeftActive = (movements[CONFLICTING_LEFT_APPROACH[approach]]?.L || 0) > 0
          const rightGreen = isGreen && phase.length === 1 && !conflictLeftActive
          const mv = movements[approach] || { L: 0, S: 0, R: 0 }
          const q = queues[approach] || 0
          const stopLineR = roadHalf + 4

          // Left is always free-flowing; straight flows on a solo green or a
          // paired surge; right only flows on this approach's own solo green
          // (never during a surge) - see feeds.py. Each movement gets its own
          // sub-lane (a lateral offset) and its own flow direction: straight
          // continues through the intersection, left/right blend the through
          // direction with a sideways component so a turning car visibly
          // peels off instead of driving straight through.
          const travel = { x: -dx, y: -dy }
          const leftPerp = { x: travel.y, y: -travel.x }
          const rightPerp = { x: -travel.y, y: travel.x }
          const lanes = {
            L: { count: mv.L, flowing: true, perp: leftPerp, flow: avg(travel, leftPerp), ring: '#22c55e' },
            S: { count: mv.S, flowing: isGreen, perp: { x: 0, y: 0 }, flow: travel, ring: null },
            R: { count: mv.R, flowing: rightGreen, perp: rightPerp, flow: avg(travel, rightPerp), ring: '#ef4444' },
          }
          const shownL = Math.min(MAX_PER_TURN_LANE, lanes.L.count)
          const shownR = Math.min(MAX_PER_TURN_LANE, lanes.R.count)
          const shownS = Math.min(Math.max(0, MAX_SHOWN - shownL - shownR), lanes.S.count)
          const shownByLane = { L: shownL, S: shownS, R: shownR }

          const w = vertical ? 20 : 30
          const h = vertical ? 30 : 20

          // queued / flowing cars, nose pointed at the stop line, one small
          // group per movement so a viewer can see left cars peeling off
          // while right cars sit still (held) and straight cars come through
          let colorCursor = 0
          const cars = ['L', 'S', 'R'].flatMap((key) => {
            const lane = lanes[key]
            const shown = shownByLane[key]
            const group = Array.from({ length: shown }, (_, i) => {
              const r = stopLineR + 12 + i * 18
              const vx = c + dx * r + lane.perp.x * LANE_OFFSET_PX
              const vy = c + dy * r + lane.perp.y * LANE_OFFSET_PX
              const flowing = lane.flowing
              const color = CAR_COLORS[colorCursor % CAR_COLORS.length]
              colorCursor += 1
              return (
                <g
                  key={`${key}-${i}`}
                  className={flowing ? 'vehicle-flowing' : ''}
                  style={flowing ? { '--fx': lane.flow.x, '--fy': lane.flow.y, animationDelay: `${i * 160}ms` } : undefined}
                >
                  <rect
                    x={vx - w / 2}
                    y={vy - h / 2}
                    width={w}
                    height={h}
                    rx="5"
                    fill={color}
                    stroke={lane.ring ?? '#0f172a'}
                    strokeWidth={lane.ring ? 2 : 1}
                  />
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
            return group
          })

          // signal head just outside the stop line
          const sx = c + dx * (stopLineR - 2) + (vertical ? 18 : 0)
          const sy = c + dy * (stopLineR - 2) + (vertical ? 0 : 18)
          const eta = etaSeconds(signal, approachIdx)

          // One arrow per movement, each independently coloured red/amber/
          // green for what it's actually doing right now - not a plain ball.
          // Left is always green (free-flowing, every phase). Straight is
          // green on a solo green or a paired surge, amber while its own
          // green is ending. Right is only ever green on a solo green (never
          // during a surge, where it's held), and only ambers if it was
          // actually running before this yellow, not if it was already held
          // - which now includes being held by a crossing left (rightGreen
          // above already folds conflictLeftActive in, so this stays red).
          const soloActive = isActive && active.length === 1
          const straightColor = isGreen ? '#22c55e' : isYellow ? '#f59e0b' : '#ef4444'
          const rightColor = rightGreen ? '#22c55e' : isYellow && soloActive ? '#f59e0b' : '#ef4444'
          const CLUSTER_GAP = 6
          const straightAnchor = { x: sx + travel.x * 2, y: sy + travel.y * 2 }
          const leftAnchor = { x: sx + leftPerp.x * CLUSTER_GAP, y: sy + leftPerp.y * CLUSTER_GAP }
          const rightAnchor = { x: sx + rightPerp.x * CLUSTER_GAP, y: sy + rightPerp.y * CLUSTER_GAP }

          // Label + countdown sit off to the side of the signal head, not
          // further out along the travel axis - that's where this approach's
          // own queued cars are (they were overlapping the timer). Each
          // approach gets its own quadrant (N->NW, E->NE, S->SE, W->SW) so no
          // two approaches' text ever land near each other, and "side" is
          // always the road's own perpendicular axis, clear of its car lanes.
          const QUADRANT = { N: { x: -1, y: 0 }, E: { x: 0, y: -1 }, S: { x: 1, y: 0 }, W: { x: 0, y: 1 } }
          const side = QUADRANT[approach]
          const textX = sx + side.x * 32
          const textY = sy + side.y * 32

          return (
            <g key={approach}>
              {cars}
              {/* signal head housing */}
              <rect x={sx - 15} y={sy - 15} width="30" height="30" rx="6" fill="#0b1220" stroke="#334155" />
              <Arrow cx={leftAnchor.x} cy={leftAnchor.y} ux={leftPerp.x} uy={leftPerp.y} color="#22c55e" />
              <Arrow cx={straightAnchor.x} cy={straightAnchor.y} ux={travel.x} uy={travel.y} color={straightColor} />
              <Arrow cx={rightAnchor.x} cy={rightAnchor.y} ux={rightPerp.x} uy={rightPerp.y} color={rightColor} />

              {/* label: approach + queue count (L/S/R breakdown is in the status list below - no room for it here) */}
              <text x={textX} y={textY - 8} textAnchor="middle" className="fill-slate-300 text-[11px] font-semibold">
                {approach} · {q}
              </text>
              {/* countdown / wait estimate */}
              <text
                x={textX}
                y={textY + 8}
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
                    ? `STRAIGHT ${countdown}s`
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
    const conflictLeftActive = (movements[CONFLICTING_LEFT_APPROACH[a]]?.L || 0) > 0
    return {
      approach: a,
      queue: q,
      mv: movements[a],
      isActive,
      isGreen: isActive && isGreenNow,
      isYellow: isActive && phase === 'yellow',
      rightHeldSurge: isActive && isGreenNow && isSurge,
      rightHeldConflict: isActive && isGreenNow && !isSurge && conflictLeftActive,
      conflictApproach: CONFLICTING_LEFT_APPROACH[a],
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
              ? r.rightHeldSurge
                ? `STRAIGHT, ${countdown}s left (right held)`
                : r.rightHeldConflict
                  ? `GREEN, ${countdown}s left (right holds — crossing ${r.conflictApproach} left)`
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
        Left turns flow continuously on every approach — never held by the signal. A
        right turn holds whenever the crossing approach's left is active, since both
        cross the same corner.
      </div>
    </div>
  )
}
