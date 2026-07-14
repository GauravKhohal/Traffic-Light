import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// Historical network-wide average waiting time (the primary evaluation metric).
export default function WaitChart({ history }) {
  const data = (history || []).slice(-180).map((h, i) => ({
    i,
    avg_wait: h.avg_wait,
    total_queue: h.total_queue,
  }))

  return (
    <div className="rounded-xl bg-slate-900 p-4 ring-1 ring-slate-800">
      <h2 className="mb-2 text-sm font-semibold text-slate-300">
        Network average wait (s) — last {data.length}s
      </h2>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
          <XAxis dataKey="i" tick={{ fill: '#64748b', fontSize: 11 }} stroke="#334155" />
          <YAxis tick={{ fill: '#64748b', fontSize: 11 }} stroke="#334155" />
          <Tooltip
            contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, color: '#e2e8f0' }}
            labelStyle={{ color: '#94a3b8' }}
          />
          <Line type="monotone" dataKey="avg_wait" stroke="#38bdf8" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
