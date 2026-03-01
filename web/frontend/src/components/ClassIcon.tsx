const CLASS_COLORS: Record<string, string> = {
  warrior: 'text-class-warrior',
  paladin: 'text-class-paladin',
  hunter: 'text-class-hunter',
  rogue: 'text-class-rogue',
  priest: 'text-class-priest',
  shaman: 'text-class-shaman',
  mage: 'text-class-mage',
  warlock: 'text-class-warlock',
  druid: 'text-class-druid',
}

const CLASS_ICONS: Record<string, string> = {
  warrior: 'classicon_warrior',
  paladin: 'classicon_paladin',
  hunter: 'classicon_hunter',
  rogue: 'classicon_rogue',
  priest: 'classicon_priest',
  shaman: 'classicon_shaman',
  mage: 'classicon_mage',
  warlock: 'classicon_warlock',
  druid: 'classicon_druid',
}

export default function ClassIcon({ className, name, size = 20 }: { className: string; name: string; size?: number }) {
  const cls = className.toLowerCase()
  const colorClass = CLASS_COLORS[cls] || 'text-text-secondary'
  const icon = CLASS_ICONS[cls]

  return (
    <span className="inline-flex items-center gap-1.5">
      {icon && (
        <img
          src={`https://wow.zamimg.com/images/wow/icons/medium/${icon}.jpg`}
          alt={className}
          width={size}
          height={size}
          className="rounded-sm align-middle"
        />
      )}
      <span className={`font-bold ${colorClass}`}>{name}</span>
    </span>
  )
}
