import { useEffect } from 'react'
import type { GearItem } from '../api/types'

const SLOT_NAMES: Record<number, string> = {
  0: 'Head', 1: 'Neck', 2: 'Shoulder', 4: 'Chest', 5: 'Waist',
  6: 'Legs', 7: 'Feet', 8: 'Wrist', 9: 'Hands', 10: 'Ring 1',
  11: 'Ring 2', 12: 'Trinket 1', 13: 'Trinket 2', 14: 'Cloak',
  15: 'Main Hand', 16: 'Off Hand', 17: 'Ranged',
}

const QUALITY_BORDERS: Record<number, string> = {
  0: 'border-l-quality-poor', 1: 'border-l-quality-common', 2: 'border-l-quality-uncommon',
  3: 'border-l-quality-rare', 4: 'border-l-quality-epic', 5: 'border-l-quality-legendary',
}

// TBC enchant effect ID → display name
const ENCHANT_NAMES: Record<number, string> = {
  // Head
  3003: 'Glyph of Ferocity', 3002: 'Glyph of Power', 2999: 'Glyph of the Defender',
  3004: 'Glyph of Renewal', 3001: 'Glyph of the Outcast',
  // Shoulder — Aldor
  2982: 'Greater Inscription of Discipline', 2986: 'Greater Inscription of Faith',
  2990: 'Greater Inscription of Vengeance', 2978: 'Greater Inscription of Warding',
  2980: 'Inscription of Discipline', 2984: 'Inscription of Faith',
  2988: 'Inscription of Vengeance', 2976: 'Inscription of Warding',
  // Shoulder — Scryer
  2995: 'Greater Inscription of the Blade', 2996: 'Greater Inscription of the Knight',
  2997: 'Greater Inscription of the Oracle', 2998: 'Greater Inscription of the Orb',
  2993: 'Inscription of the Blade', 2994: 'Inscription of the Knight',
  // Chest
  2661: 'Exceptional Stats', 2933: 'Major Resilience', 1144: 'Major Spirit',
  3150: 'Exceptional Health', 3233: 'Restore Mana Prime',
  // Cloak
  2622: 'Greater Agility', 2664: 'Major Armor', 368: 'Greater Defense',
  2938: 'Spell Penetration', 2621: 'Subtlety', 2648: 'Steelweave',
  // Wrist
  2647: 'Brawn', 2649: 'Fortitude', 2617: 'Superior Healing',
  1593: 'Assault', 2650: 'Spellpower', 2679: 'Stats',
  // Hands
  2613: 'Threat', 2564: 'Assault', 2322: 'Superior Agility',
  684: 'Major Strength', 2937: 'Major Spellpower', 2935: 'Major Healing',
  // Legs
  3010: 'Nethercobra Leg Armor', 3011: 'Nethercleft Leg Armor',
  3012: 'Runic Spellthread', 3013: 'Mystic Spellthread',
  2744: 'Cobrahide Leg Armor', 2745: 'Clefthide Leg Armor',
  // Feet
  2657: 'Dexterity', 2656: 'Vitality', 2940: "Boar's Speed",
  2939: "Cat's Swiftness", 2658: 'Surefooted',
  // Weapon
  2669: 'Mongoose', 2671: 'Sunfire', 2672: 'Soulfrost',
  2673: 'Spellsurge', 963: 'Major Striking', 3222: 'Greater Agility',
  2667: 'Savagery', 2670: 'Major Spellpower', 3225: 'Executioner',
  2666: 'Major Intellect', 3273: 'Battlemaster', 1900: 'Crusader',
  // Shield
  2655: 'Shield Block', 2654: 'Intellect', 1071: 'Major Stamina',
  // Ring (Enchanting only)
  2928: 'Spellpower', 2929: 'Healing Power', 2931: 'Stats',
  2930: 'Striking', 2927: 'Assault',
}

function getEnchantName(id: number): string {
  return ENCHANT_NAMES[id] || `Enchant #${id}`
}

declare global {
  interface Window {
    $WowheadPower?: { refreshLinks: () => void }
  }
}

function buildDataWowhead(item: GearItem): string | undefined {
  const parts: string[] = []
  if (item.permanent_enchant) parts.push(`ench=${item.permanent_enchant}`)
  const gemIds = item.gems?.filter(g => g.id > 0).map(g => g.id) || []
  if (gemIds.length > 0) parts.push(`gems=${gemIds.join(':')}`)
  return parts.length > 0 ? parts.join('&') : undefined
}

export default function GearGrid({ gear, issues }: { gear: GearItem[]; issues: { slot: string; problem: string }[] }) {
  const issueMap = new Map(issues.map(i => [i.slot, i.problem]))

  useEffect(() => {
    const timer = setTimeout(() => {
      window.$WowheadPower?.refreshLinks()
    }, 100)
    return () => clearTimeout(timer)
  }, [gear])

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {gear.map(item => {
        const slotName = SLOT_NAMES[item.slot] || `Slot ${item.slot}`
        const issue = issueMap.get(slotName)
        const activeGems = item.gems?.filter(g => g.id > 0) || []
        const dataWh = buildDataWowhead(item)
        const borderClass = QUALITY_BORDERS[item.quality] || 'border-l-text-muted'
        return (
          <div
            key={item.slot}
            className={`p-3 rounded-lg border-l-3 transition-all duration-200 hover:scale-[1.02] hover:shadow-lg hover:shadow-black/20 ${borderClass} ${
              issue ? 'bg-danger/10 border border-danger/20' : 'bg-bg-surface border border-border-default hover:border-border-hover'
            }`}
          >
            <div className="text-xs text-text-muted">{slotName}</div>
            <div className="text-sm mt-0.5">
              <a
                href={`https://tbc.wowhead.com/item=${item.item_id}`}
                target="_blank"
                rel="noopener noreferrer"
                {...(dataWh ? { 'data-wowhead': dataWh } : {})}
              >
                {slotName}
              </a>
              <span className="text-text-muted text-xs ml-1.5">ilvl {item.item_level}</span>
            </div>
            {item.permanent_enchant && (
              <div className="text-xs text-parse-uncommon mt-1">{getEnchantName(item.permanent_enchant)}</div>
            )}
            {activeGems.length > 0 && (
              <div className="text-xs mt-1 flex flex-wrap gap-1">
                {activeGems.map((gem, idx) => (
                  <a
                    key={idx}
                    href={`https://tbc.wowhead.com/item=${gem.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs"
                  >
                    [Gem]
                  </a>
                ))}
              </div>
            )}
            {issue && <div className="text-xs text-danger mt-1">{issue}</div>}
          </div>
        )
      })}
    </div>
  )
}
