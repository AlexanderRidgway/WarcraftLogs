export default function ScoreCard({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null

  return (
    <div className="flex-1 bg-bg-surface border border-border-default rounded-xl p-4 text-center hover:border-border-hover transition-colors">
      <div className="text-xs text-text-muted uppercase tracking-wider mb-1">{label}</div>
      <div className="text-3xl font-bold text-accent-gold tabular-nums">{value.toFixed(1)}</div>
    </div>
  )
}
