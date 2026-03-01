function getParseColor(percent: number): string {
  if (percent >= 95) return 'bg-parse-legendary'
  if (percent >= 75) return 'bg-parse-epic'
  if (percent >= 50) return 'bg-parse-rare'
  if (percent >= 25) return 'bg-parse-uncommon'
  return 'bg-parse-common'
}

function getParseTextColor(percent: number): string {
  if (percent >= 95) return 'text-parse-legendary'
  if (percent >= 75) return 'text-parse-epic'
  if (percent >= 50) return 'text-parse-rare'
  if (percent >= 25) return 'text-parse-uncommon'
  return 'text-parse-common'
}

export default function ParseBar({ percent }: { percent: number }) {
  const rounded = Math.round(percent * 10) / 10

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-2.5 bg-bg-base rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getParseColor(percent)}`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      <span className={`text-sm font-semibold tabular-nums ${getParseTextColor(percent)}`}>
        {rounded}
      </span>
    </div>
  )
}
