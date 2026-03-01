import { useEffect } from 'react'
import type { GearItem } from '../api/types'

const SLOT_NAMES: Record<number, string> = {
  0: 'Head', 1: 'Neck', 2: 'Shoulder', 4: 'Chest', 5: 'Waist',
  6: 'Legs', 7: 'Feet', 8: 'Wrist', 9: 'Hands', 10: 'Ring 1',
  11: 'Ring 2', 12: 'Trinket 1', 13: 'Trinket 2', 14: 'Cloak',
  15: 'Main Hand', 16: 'Off Hand', 17: 'Ranged',
}

const QUALITY_COLORS: Record<number, string> = {
  0: '#9d9d9d', 1: '#fff', 2: '#1eff00', 3: '#0070dd', 4: '#a335ee', 5: '#ff8000',
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
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.25rem' }}>
      {gear.map(item => {
        const slotName = SLOT_NAMES[item.slot] || `Slot ${item.slot}`
        const issue = issueMap.get(slotName)
        const activeGems = item.gems?.filter(g => g.id > 0) || []
        const dataWh = buildDataWowhead(item)
        return (
          <div
            key={item.slot}
            style={{
              padding: '0.5rem',
              background: issue ? '#2a1515' : '#161b22',
              borderRadius: 4,
              borderLeft: `3px solid ${QUALITY_COLORS[item.quality] || '#999'}`,
            }}
          >
            <div style={{ fontSize: 11, color: '#8b949e' }}>{slotName}</div>
            <div style={{ fontSize: 14 }}>
              <a
                href={`https://tbc.wowhead.com/item=${item.item_id}`}
                target="_blank"
                rel="noopener noreferrer"
                {...(dataWh ? { 'data-wowhead': dataWh } : {})}
              >
                {slotName}
              </a>
              <span style={{ color: '#8b949e', fontSize: 12, marginLeft: 6 }}>
                ilvl {item.item_level}
              </span>
            </div>
            {item.permanent_enchant && (
              <div style={{ fontSize: 11, color: '#1eff00', marginTop: 2 }}>
                Enchanted
              </div>
            )}
            {activeGems.length > 0 && (
              <div style={{ fontSize: 11, marginTop: 2, display: 'flex', flexWrap: 'wrap', gap: '0 6px' }}>
                {activeGems.map((gem, idx) => (
                  <a
                    key={idx}
                    href={`https://tbc.wowhead.com/item=${gem.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 11 }}
                  >
                    [Gem]
                  </a>
                ))}
              </div>
            )}
            {issue && <div style={{ fontSize: 11, color: '#ff6b6b', marginTop: 2 }}>{issue}</div>}
          </div>
        )
      })}
    </div>
  )
}
