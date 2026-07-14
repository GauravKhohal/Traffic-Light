export const APPROACHES = ['N', 'E', 'S', 'W']

// congestion colour ramp by total halted vehicles at a signal
export function queueColor(total) {
  if (total <= 8) return '#22c55e'
  if (total <= 20) return '#f59e0b'
  return '#ef4444'
}

// colour for the current phase badge
export function phaseColor(phase) {
  if (phase === 'yellow') return '#f59e0b'
  if (phase === 'allred' || phase === '—') return '#64748b'
  return '#22c55e' // an approach label => that approach has green
}

export function phaseLabel(phase) {
  if (phase === 'yellow') return 'YELLOW'
  if (phase === 'allred') return 'ALL-RED'
  if (phase === '—' || phase == null) return '—'
  return `GREEN ${phase}`
}
