import { queueColor } from '../constants'

// screen-direction unit vectors for each nominal approach (outward from node)
const DIR = {
  N: { dx: 0, dy: -1 },
  E: { dx: 1, dy: 0 },
  S: { dx: 0, dy: 1 },
  W: { dx: -1, dy: 0 },
}
const MAX_SHOWN = 5 // vehicle markers drawn per approach, even if the queue is longer

// Schematic 3x3 map of the intersection grid (self-contained SVG — no external
// tiles). Each node has a short spur per approach with small vehicle markers:
// queued and static while red, animated flowing through while that approach
// has green — the AI visibly "opening" the busy lane.
export default function GridMap({ signals, selected, onSelect }) {
  const GAP = 110
  const M = 55
  const pos = (x, y) => [M + x * GAP, M + (2 - y) * GAP] // row 0 at the bottom

  const cols = [0, 1, 2]
  const rows = [0, 1, 2]

  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <h2 className="mb-2 text-sm font-semibold text-slate-300">Intersection grid</h2>
      <svg viewBox="0 0 330 330" className="w-full">
        {/* roads */}
        {rows.map((r) => {
          const [x1, y1] = pos(0, r)
          const [x2, y2] = pos(2, r)
          return <line key={`h${r}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#1e293b" strokeWidth="10" />
        })}
        {cols.map((c) => {
          const [x1, y1] = pos(c, 0)
          const [x2, y2] = pos(c, 2)
          return <line key={`v${c}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#1e293b" strokeWidth="10" />
        })}
        {/* intersections + per-approach vehicle queues */}
        {signals.map((s) => {
          const [cx, cy] = pos(s.x, s.y)
          const queues = s.queues || {}
          const total = Object.values(queues).reduce((a, b) => a + b, 0)
          const isSel = s.id === selected
          return (
            <g key={s.id}>
              {Object.entries(DIR).map(([approach, { dx, dy }]) => {
                const n = Math.min(MAX_SHOWN, queues[approach] || 0)
                const isFlowing = s.phase === approach
                const vertical = dx === 0
                return Array.from({ length: n }, (_, i) => {
                  const r = 17 + i * 6.5 // 0 = closest to the stop line
                  const vx = cx + dx * r
                  const vy = cy + dy * r
                  const w = vertical ? 6 : 9
                  const h = vertical ? 9 : 6
                  return (
                    <rect
                      key={`${s.id}-${approach}-${i}`}
                      x={vx - w / 2}
                      y={vy - h / 2}
                      width={w}
                      height={h}
                      rx="1.5"
                      fill={isFlowing ? '#4ade80' : '#38bdf8'}
                      className={isFlowing ? 'vehicle-flowing' : ''}
                      style={
                        isFlowing
                          ? { '--fx': -dx, '--fy': -dy, animationDelay: `${i * 140}ms` }
                          : undefined
                      }
                    />
                  )
                })
              })}
              <g onClick={() => onSelect(s.id)} className="cursor-pointer">
                {s.override && <circle cx={cx} cy={cy} r="20" fill="none" stroke="#a855f7" strokeWidth="3" />}
                <circle
                  cx={cx}
                  cy={cy}
                  r="14"
                  fill={queueColor(total)}
                  stroke={isSel ? '#e2e8f0' : '#0f172a'}
                  strokeWidth={isSel ? 3 : 2}
                />
                <text x={cx} y={cy + 4} textAnchor="middle" className="fill-slate-950 text-[11px] font-bold">
                  {s.id}
                </text>
              </g>
            </g>
          )
        })}
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-400">
        <span className="flex items-center gap-1"><Dot c="#22c55e" /> light</span>
        <span className="flex items-center gap-1"><Dot c="#f59e0b" /> moderate</span>
        <span className="flex items-center gap-1"><Dot c="#ef4444" /> heavy</span>
        <span className="flex items-center gap-1"><Dot c="#a855f7" /> override</span>
        <span className="flex items-center gap-1"><Dot c="#38bdf8" /> waiting</span>
        <span className="flex items-center gap-1"><Dot c="#4ade80" /> flowing (green)</span>
      </div>
    </div>
  )
}

function Dot({ c }) {
  return <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: c }} />
}
