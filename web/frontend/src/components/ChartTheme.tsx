// Shared Recharts theme constants matching CRANK dark theme
export const CHART_COLORS = {
  gold: '#c9a959',
  goldLight: '#d4b96a',
  success: '#22c55e',
  danger: '#ef4444',
  info: '#3b82f6',
  text: '#8b95a5',
  textMuted: '#5a6475',
  grid: '#1e2430',
  bg: '#12161f',
}

export const CHART_DEFAULTS = {
  style: { fontSize: 12 },
  tick: { fill: CHART_COLORS.text },
  axisLine: { stroke: CHART_COLORS.grid },
  gridStroke: CHART_COLORS.grid,
}

// Parse color for a percentile value (matches ParseBar colors)
export function parseColor(pct: number): string {
  if (pct >= 99) return '#e268a8'  // legendary/pink
  if (pct >= 95) return '#ff8000'  // orange
  if (pct >= 75) return '#a335ee'  // epic/purple
  if (pct >= 50) return '#0070dd'  // rare/blue
  if (pct >= 25) return '#1eff00'  // uncommon/green
  return '#9d9d9d'                 // common/gray
}
