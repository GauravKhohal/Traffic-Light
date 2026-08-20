import { APPROACHES, activeApproaches, isGreenPhase } from '../constants'

const YELLOW_S = 4
const ALLRED_S = 2
const MAX_SHOWN = 11 // cars drawn per approach even if the real queue is longer

// Roughly-varied car body colours so the queue reads as real traffic, not a
// single-colour block. Purely cosmetic, cycles by position in the queue.
const CAR_COLORS = ['#f2cc3d', '#4ade80', '#60a5fa', '#f87171', '#c084fc', '#fb923c']

// Keep-left road geometry: each approach's own lanes sit offset toward its
// own kerb (in its own leftPerp direction - see below), not centred on the
// road's centreline. Opposing approaches share a road but use opposite
// leftPerp directions, so their lanes land on opposite sides and never
// overlap - e.g. S's northbound through traffic passes to the west of the
// centreline while N's own (southbound) queue sits to the east of it.
const THROUGH_LANE_OFFSET_PX = 14 // this approach's through+right lane, offset off the centreline
const LEFT_LANE_GAP_PX = 18 // extra offset beyond that for the dedicated left lane, out toward the kerb
const MAX_PER_TURN_LANE = 4 // left lane shown at most this many, through+right lane fills the rest

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

// Only two of the four lefts are actually clear of an active approach A's
// own path: A's own left, and PREV(A)'s (handled above - A's right yields to
// it instead of holding it). The other two merge nose-to-nose with A's own
// straight/right and have to hold for as long as A is active - mirrors
// feeds.py's _held_lefts:
//  - NEXT(A)'s left merges into the same exit lane as A's straight.
//  - OPP(A)'s left merges into the same exit lane as A's right.
// During a straight-only surge (two approaches active) each one's own left
// stays free, and this naturally holds both remaining approaches' lefts.
function heldLeftApproaches(active) {
  const idxs = active.map((a) => APPROACHES.indexOf(a))
  const held = new Set()
  for (const i of idxs) {
    held.add((i + 1) % 4)
    held.add((i + 2) % 4)
  }
  for (const i of idxs) held.delete(i)
  return new Set([...held].map((i) => APPROACHES[i]))
}

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
  // held only while something is actually active (green/surge); clear during
  // yellow/all-red, when nothing has protected right-of-way - matches feeds.py
  const heldLefts = isGreenNow ? heldLeftApproaches(active) : new Set()
  const size = 520
  const c = size / 2
  const roadHalf = 46 // half-width of each road surface (both directions)
  const sidewalkW = 9 // width of the curb/sidewalk strip along each road edge
  const outerHalf = roadHalf + sidewalkW // half-width including sidewalks - marks where the city blocks start

  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300">Intersection {id} — live</h2>
        <span className="text-xs text-slate-500">road · signal · queue · AI green plan</span>
      </div>
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full" style={{ overflow: 'hidden' }}>
        <defs>
          <pattern id={`hatch-${id}`} width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#94a3b8" strokeWidth="1" opacity="0.15" />
          </pattern>
        </defs>

        {/* city blocks: the four corners outside the road+sidewalk, lightly
            textured so the road reads against a real backdrop, not empty space */}
        {[
          [0, 0],
          [c + outerHalf, 0],
          [0, c + outerHalf],
          [c + outerHalf, c + outerHalf],
        ].map(([bx, by], i) => (
          <g key={i}>
            <rect x={bx} y={by} width={c - outerHalf} height={c - outerHalf} fill="#1e293b" />
            <rect x={bx} y={by} width={c - outerHalf} height={c - outerHalf} fill={`url(#hatch-${id})`} />
          </g>
        ))}

        {/* sidewalks (curb strips flanking each road) */}
        <rect x={c - outerHalf} y="0" width={sidewalkW} height={size} fill="#475569" />
        <rect x={c + roadHalf} y="0" width={sidewalkW} height={size} fill="#475569" />
        <rect x="0" y={c - outerHalf} width={size} height={sidewalkW} fill="#475569" />
        <rect x="0" y={c + roadHalf} width={size} height={sidewalkW} fill="#475569" />

        {/* asphalt road surfaces */}
        <rect x={c - roadHalf} y="0" width={roadHalf * 2} height={size} fill="#334155" />
        <rect x="0" y={c - roadHalf} width={size} height={roadHalf * 2} fill="#334155" />
        {/* intersection surface, a touch lighter so its boundary reads clearly */}
        <rect x={c - roadHalf} y={c - roadHalf} width={roadHalf * 2} height={roadHalf * 2} fill="#3f4a5e" />

        {/* double-yellow centre line, each arm - real no-passing road marking,
            stops short of the intersection surface on both ends */}
        {[
          [c, 0, c, c - roadHalf],
          [c, c + roadHalf, c, size],
          [0, c, c - roadHalf, c],
          [c + roadHalf, c, size, c],
        ].map(([x1, y1, x2, y2], i) => {
          const vert = x1 === x2
          const off = vert ? { x: 1.6, y: 0 } : { x: 0, y: 1.6 }
          return (
            <g key={i}>
              <line x1={x1 - off.x} y1={y1 - off.y} x2={x2 - off.x} y2={y2 - off.y} stroke="#facc15" strokeWidth="1.6" />
              <line x1={x1 + off.x} y1={y1 + off.y} x2={x2 + off.x} y2={y2 + off.y} stroke="#facc15" strokeWidth="1.6" />
            </g>
          )
        })}

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
          const leftHeld = heldLefts.has(approach)
          const mv = movements[approach] || { L: 0, S: 0, R: 0 }
          const q = queues[approach] || 0
          const stopLineR = roadHalf + 4

          // Two physical lanes, like a real approach road: a dedicated left
          // lane (left is its own free-flowing movement, a slip lane in
          // effect - held or not per heldLeftApproaches above) and a shared
          // through+right lane, since straight and right traffic wait at the
          // same stop line and only diverge once they actually move. Right
          // only flows on this approach's own solo green (never during a
          // surge) - see feeds.py. Each car keeps its own flow direction for
          // when it's actually moving: straight continues through the
          // intersection, left/right blend the through direction with a
          // sideways component so a turning car visibly peels off instead of
          // driving straight through.
          const travel = { x: -dx, y: -dy }
          const leftPerp = { x: travel.y, y: -travel.x }
          const rightPerp = { x: -travel.y, y: travel.x }
          // both lane positions offset toward this approach's own kerb
          // (leftPerp direction) so opposing traffic on the same road never
          // shares a lane - see THROUGH_LANE_OFFSET_PX/LEFT_LANE_GAP_PX above
          const throughPerp = { x: leftPerp.x * THROUGH_LANE_OFFSET_PX, y: leftPerp.y * THROUGH_LANE_OFFSET_PX }
          const leftLanePerp = {
            x: leftPerp.x * (THROUGH_LANE_OFFSET_PX + LEFT_LANE_GAP_PX),
            y: leftPerp.y * (THROUGH_LANE_OFFSET_PX + LEFT_LANE_GAP_PX),
          }
          const lanes = {
            L: { count: mv.L, flowing: !leftHeld, flow: avg(travel, leftPerp), ring: leftHeld ? '#ef4444' : '#22c55e' },
            S: { count: mv.S, flowing: isGreen, flow: travel, ring: null },
            R: { count: mv.R, flowing: rightGreen, flow: avg(travel, rightPerp), ring: '#ef4444' },
          }
          const shownL = Math.min(MAX_PER_TURN_LANE, lanes.L.count)
          const throughBudget = Math.max(0, MAX_SHOWN - shownL)
          const shownS = Math.min(lanes.S.count, throughBudget)
          const shownR = Math.min(lanes.R.count, Math.max(0, throughBudget - shownS))

          const w = vertical ? 20 : 30
          const h = vertical ? 30 : 20

          // left lane cars sit out toward the kerb, in their own lane;
          // through+right cars share one file closer to the centreline but
          // still offset onto this approach's own side (throughPerp), one
          // behind another in arrival order
          const leftSpecs = Array.from({ length: shownL }, () => ({ ...lanes.L, perp: leftLanePerp }))
          const throughSpecs = [
            ...Array.from({ length: shownS }, () => ({ ...lanes.S, perp: throughPerp })),
            ...Array.from({ length: shownR }, () => ({ ...lanes.R, perp: throughPerp })),
          ]

          // queued / flowing cars, nose pointed at the stop line, one group
          // per lane so a viewer can see left cars peel off in their own
          // lane while the through+right lane sits still (held) or flows
          // wheel nubs: two pairs (front/rear) poking slightly past the
          // body's long edges, like a simple top-down car icon - along-axis
          // offset toward front/rear, cross-axis offset just past the body
          const crossHalf = vertical ? w / 2 : h / 2
          const alongOffset = (vertical ? h : w) * 0.3
          const wheelLong = 6
          const wheelThick = 2
          let colorCursor = 0
          const renderLane = (specs, keyPrefix) =>
            specs.map((spec, i) => {
              const r = stopLineR + 12 + i * 18
              const vx = c + dx * r + spec.perp.x
              const vy = c + dy * r + spec.perp.y
              const flowing = spec.flowing
              const color = CAR_COLORS[colorCursor % CAR_COLORS.length]
              colorCursor += 1
              const wheels = [-1, 1].flatMap((side) =>
                [-1, 1].map((end) => {
                  const cross = side * (crossHalf + 0.5)
                  const along = end * alongOffset
                  const rw = vertical ? wheelThick : wheelLong
                  const rh = vertical ? wheelLong : wheelThick
                  return {
                    x: (vertical ? vx + cross : vx + along) - rw / 2,
                    y: (vertical ? vy + along : vy + cross) - rh / 2,
                    rw,
                    rh,
                  }
                })
              )
              return (
                <g
                  key={`${keyPrefix}-${i}`}
                  className={flowing ? 'vehicle-flowing' : ''}
                  style={
                    flowing
                      ? {
                          '--fx': spec.flow.x,
                          '--fy': spec.flow.y,
                          '--fdist': '340px',
                          '--fdur': '2.4s',
                          animationDelay: `${i * 200}ms`,
                        }
                      : undefined
                  }
                >
                  {wheels.map((wl, wi) => (
                    <rect key={wi} x={wl.x} y={wl.y} width={wl.rw} height={wl.rh} rx="1" fill="#0b1220" opacity="0.85" />
                  ))}
                  <rect
                    x={vx - w / 2}
                    y={vy - h / 2}
                    width={w}
                    height={h}
                    rx="5"
                    fill={color}
                    stroke={spec.ring ?? '#0f172a'}
                    strokeWidth={spec.ring ? 2 : 1}
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
          const cars = [...renderLane(leftSpecs, 'L'), ...renderLane(throughSpecs, 'T')]

          // white dashed lane-boundary between the left lane and the
          // through+right lane, running the length of this arm
          const boundaryOff = THROUGH_LANE_OFFSET_PX + LEFT_LANE_GAP_PX / 2
          const laneBoundary = {
            x1: c + dx * stopLineR + leftPerp.x * boundaryOff,
            y1: c + dy * stopLineR + leftPerp.y * boundaryOff,
            x2: c + dx * c + leftPerp.x * boundaryOff,
            y2: c + dy * c + leftPerp.y * boundaryOff,
          }

          // zebra crosswalk right at the stop line, spanning the full road
          // width (both directions, even though only this side has cars)
          const stripeCount = 7
          const stripeGap = (roadHalf * 2 - 8) / (stripeCount - 1)
          const crosswalk = Array.from({ length: stripeCount }, (_, i) => {
            const t = -roadHalf + 4 + i * stripeGap
            return {
              x: c + dx * stopLineR + leftPerp.x * t,
              y: c + dy * stopLineR + leftPerp.y * t,
            }
          })
          const stripeW = vertical ? 4 : 10
          const stripeH = vertical ? 10 : 4

          // signal head just outside the stop line
          const sx = c + dx * (stopLineR - 2) + (vertical ? 18 : 0)
          const sy = c + dy * (stopLineR - 2) + (vertical ? 0 : 18)
          const eta = etaSeconds(signal, approachIdx)

          // One arrow per movement, each independently coloured red/amber/
          // green for what it's actually doing right now - not a plain ball.
          // Left is green unless heldLeftApproaches holds it for this active
          // approach (leftHeld above). Straight is green on a solo green or
          // a paired surge, amber while its own green is ending. Right is
          // only ever green on a solo green (never during a surge, where
          // it's held), and only ambers if it was actually running before
          // this yellow, not if it was already held - which now includes
          // being held by a crossing left (rightGreen above already folds
          // conflictLeftActive in, so this stays red).
          const soloActive = isActive && active.length === 1
          const leftColor = leftHeld ? '#ef4444' : '#22c55e'
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
              <line
                x1={laneBoundary.x1}
                y1={laneBoundary.y1}
                x2={laneBoundary.x2}
                y2={laneBoundary.y2}
                stroke="#e2e8f0"
                strokeWidth="1.2"
                strokeDasharray="6 6"
                opacity="0.4"
              />
              {crosswalk.map((s, i) => (
                <rect
                  key={i}
                  x={s.x - stripeW / 2}
                  y={s.y - stripeH / 2}
                  width={stripeW}
                  height={stripeH}
                  fill="#e2e8f0"
                  opacity="0.7"
                />
              ))}
              {cars}
              {/* signal head housing */}
              <rect x={sx - 15} y={sy - 15} width="30" height="30" rx="6" fill="#0b1220" stroke="#334155" />
              <Arrow cx={leftAnchor.x} cy={leftAnchor.y} ux={leftPerp.x} uy={leftPerp.y} color={leftColor} />
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

      <StatusList signal={signal} active={active} isGreenNow={isGreenNow} phase={phase} countdown={countdown} heldLefts={heldLefts} />
    </div>
  )
}

// Unambiguous, plain-text readout — one row per approach, in the order it
// will actually be served, so there's no small overlapping SVG text to
// misread. This is the same eta/skip logic as the diagram, just spelled out.
function StatusList({ signal, active, isGreenNow, phase, countdown, heldLefts }) {
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
      leftHeld: heldLefts.has(a),
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
            {r.leftHeld && (
              <span className="text-[10px] font-semibold text-red-400">left held</span>
            )}
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
        Only two lefts run free at a time — the active approach's own, and the one
        whose crossing corner it yields its right into. The other two would merge
        straight into the active approach's own path, so they hold until it stops.
      </div>
    </div>
  )
}
