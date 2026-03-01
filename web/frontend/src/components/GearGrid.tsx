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
              <div className="text-xs text-parse-uncommon mt-1">Enchanted</div>
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
