export const APPROACHES = ['N', 'E', 'S', 'W']

// congestion colour ramp by total halted vehicles at a signal
export function queueColor(total) {
  if (total <= 8) return '#22c55e'
  if (total <= 20) return '#f59e0b'
  return '#ef4444'
}

// `phase` is a compact code from the backend: a single approach letter for a
// solo green ("N"), two letters for a paired straight-only surge on a high-
// traffic opposing pair ("NS"/"EW" — see feeds.py SURGE_PAIRS), or the
// literal "yellow"/"allred" during a transition. This is true whenever it is
// neither of those transition strings nor the "no data yet" placeholder.
export function isGreenPhase(phase) {
  return phase != null && phase !== 'yellow' && phase !== 'allred' && phase !== '—'
}

// Approaches currently in the signal's spotlight (green now, or transitioning
// through yellow/all-red after being green). Prefers the demo feed's explicit
// `active` array (needed for a 2-approach surge); falls back to the legacy
// single-approach `phase_index` for the MQTT feed, which never surges.
export function activeApproaches(signal) {
  if (Array.isArray(signal.active)) return signal.active
  const idx = signal.phase_index
  return typeof idx === 'number' && idx >= 0 && idx < APPROACHES.length ? [APPROACHES[idx]] : []
}

// colour for the current phase badge
export function phaseColor(phase) {
  if (phase === 'yellow') return '#f59e0b'
  if (phase === 'allred' || phase === '—' || phase == null) return '#64748b'
  return '#22c55e' // an approach code (solo or paired) => green
}

export function phaseLabel(phase) {
  if (phase === 'yellow') return 'YELLOW'
  if (phase === 'allred') return 'ALL-RED'
  if (phase === '—' || phase == null) return '—'
  if (phase.length === 2) return `GREEN ${phase[0]}+${phase[1]} straight`
  return `GREEN ${phase}`
}
