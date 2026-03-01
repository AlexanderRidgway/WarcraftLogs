export default function ScoreCard({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null
  return (
    <div style={{ padding: '0.75rem 1.25rem', background: '#161b22', borderRadius: 8, textAlign: 'center', border: '1px solid #30363d' }}>
      <div style={{ fontSize: 12, color: '#8b949e', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 'bold', color: '#e0e0e0' }}>{value.toFixed(1)}</div>
    </div>
  )
}
