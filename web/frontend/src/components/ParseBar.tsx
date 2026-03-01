function parseColor(percent: number): string {
  if (percent >= 95) return '#e268a8'
  if (percent >= 75) return '#a335ee'
  if (percent >= 50) return '#0070dd'
  if (percent >= 25) return '#1eff00'
  return '#999'
}

export default function ParseBar({ percent }: { percent: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div style={{ width: 100, height: 12, background: '#222', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(percent, 100)}%`, height: '100%', background: parseColor(percent) }} />
      </div>
      <span style={{ color: parseColor(percent), fontWeight: 'bold', fontSize: 14 }}>
        {percent.toFixed(1)}%
      </span>
    </div>
  )
}
