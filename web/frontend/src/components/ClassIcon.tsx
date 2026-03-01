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

const SPEC_ICONS: Record<string, string> = {
  'warrior:arms': 'ability_warrior_savageblow',
  'warrior:fury': 'ability_warrior_innerrage',
  'warrior:protection': 'ability_warrior_defensivestance',
  'warrior:gladiator': 'ability_warrior_defensivestance',
  'paladin:holy': 'spell_holy_holybolt',
  'paladin:protection': 'spell_holy_devotionaura',
  'paladin:justicar': 'spell_holy_devotionaura',
  'paladin:retribution': 'spell_holy_auraoflight',
  'hunter:beastmastery': 'ability_hunter_beasttaming',
  'hunter:beast mastery': 'ability_hunter_beasttaming',
  'hunter:marksmanship': 'ability_marksmanship',
  'hunter:survival': 'ability_hunter_swiftstrike',
  'rogue:assassination': 'ability_rogue_eviscerate',
  'rogue:combat': 'ability_backstab',
  'rogue:subtlety': 'ability_stealth',
  'priest:discipline': 'spell_holy_wordfortitude',
  'priest:holy': 'spell_holy_guardianspirit',
  'priest:shadow': 'spell_shadow_shadowwordpain',
  'shaman:elemental': 'spell_nature_lightning',
  'shaman:enhancement': 'spell_nature_lightningshield',
  'shaman:restoration': 'spell_nature_magicimmunity',
  'mage:arcane': 'spell_holy_magicalsentry',
  'mage:fire': 'spell_fire_firebolt02',
  'mage:frost': 'spell_frost_frostbolt02',
  'warlock:affliction': 'spell_shadow_deathcoil',
  'warlock:demonology': 'spell_shadow_metamorphosis',
  'warlock:destruction': 'spell_shadow_rainoffire',
  'druid:balance': 'spell_nature_starfall',
  'druid:feral': 'ability_racial_bearform',
  'druid:guardian': 'ability_racial_bearform',
  'druid:restoration': 'spell_nature_healingtouch',
}

export function getSpecIcon(spec?: string): string | undefined {
  if (!spec) return undefined
  return SPEC_ICONS[spec]
}

export function getSpecLabel(spec?: string): string {
  if (!spec) return ''
  const parts = spec.split(':')
  if (parts.length < 2) return spec
  return parts[1].charAt(0).toUpperCase() + parts[1].slice(1)
}

export default function ClassIcon({ className, name, spec, size = 20 }: { className: string; name: string; spec?: string; size?: number }) {
  const cls = className.toLowerCase()
  const colorClass = CLASS_COLORS[cls] || 'text-text-secondary'
  const specIcon = spec ? SPEC_ICONS[spec] : undefined
  const icon = specIcon || CLASS_ICONS[cls]

  return (
    <span className="inline-flex items-center gap-1.5">
      {icon && (
        <img
          src={`https://wow.zamimg.com/images/wow/icons/medium/${icon}.jpg`}
          alt={spec || className}
          width={size}
          height={size}
          className="rounded-sm align-middle"
        />
      )}
      <span className={`font-bold ${colorClass}`}>{name}</span>
    </span>
  )
}
