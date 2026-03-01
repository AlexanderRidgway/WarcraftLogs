const CLASS_COLORS: Record<string, string> = {
  warrior: '#C79C6E',
  paladin: '#F58CBA',
  hunter: '#ABD473',
  rogue: '#FFF569',
  priest: '#FFFFFF',
  shaman: '#0070DE',
  mage: '#69CCF0',
  warlock: '#9482C9',
  druid: '#FF7D0A',
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
  const color = CLASS_COLORS[cls] || '#999'
  const icon = CLASS_ICONS[cls]

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      {icon && (
        <img
          src={`https://wow.zamimg.com/images/wow/icons/medium/${icon}.jpg`}
          alt={className}
          width={size}
          height={size}
          style={{ borderRadius: 3, verticalAlign: 'middle' }}
        />
      )}
      <span style={{ color, fontWeight: 'bold' }}>{name}</span>
    </span>
  )
}
