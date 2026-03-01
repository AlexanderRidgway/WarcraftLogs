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

export default function ClassIcon({ className, name }: { className: string; name: string }) {
  const color = CLASS_COLORS[className.toLowerCase()] || '#999'
  return <span style={{ color, fontWeight: 'bold' }}>{name}</span>
}
