import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import ScoreCard from '../components/ScoreCard'
import ParseBar from '../components/ParseBar'
import GearGrid from '../components/GearGrid'

type Tab = 'performance' | 'gear' | 'attendance'

export default function PlayerProfile() {
  const { name } = useParams<{ name: string }>()
  const [tab, setTab] = useState<Tab>('performance')
  const [weeks, setWeeks] = useState(4)

  const { data: player, isLoading } = useQuery({
    queryKey: ['player', name],
    queryFn: () => api.players.get(name!),
    enabled: !!name,
  })

  const { data: rankings } = useQuery({
    queryKey: ['rankings', name, weeks],
    queryFn: () => api.players.rankings(name!, weeks),
    enabled: !!name && tab === 'performance',
  })

  const { data: gear } = useQuery({
    queryKey: ['gear', name],
    queryFn: () => api.players.gear(name!),
    enabled: !!name && tab === 'gear',
  })

  const { data: attendance } = useQuery({
    queryKey: ['player-attendance', name, weeks],
    queryFn: () => api.players.attendance(name!, weeks),
    enabled: !!name && tab === 'attendance',
  })

  if (isLoading) return <Layout><p>Loading...</p></Layout>
  if (!player) return <Layout><p>Player not found</p></Layout>

  const avgScore = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.overall_score, 0) / player.scores.length
    : null

  const avgParse = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.parse_score, 0) / player.scores.length
    : null

  return (
    <Layout>
      <h1><ClassIcon className={player.class_name} name={player.name} size={36} /></h1>
      <p style={{ color: '#8b949e', textTransform: 'capitalize' }}>{player.class_name} — {player.server} ({player.region.toUpperCase()})</p>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <ScoreCard label="Consistency" value={avgScore} />
        <ScoreCard label="Avg Parse" value={avgParse} />
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {(['performance', 'gear', 'attendance'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '0.5rem 1rem',
              background: tab === t ? '#1f6feb' : '#21262d',
              border: '1px solid #30363d',
              borderRadius: 4,
              color: '#e0e0e0',
              cursor: 'pointer',
              textTransform: 'capitalize',
            }}
          >
            {t}
          </button>
        ))}
        {tab === 'performance' && (
          <select value={weeks} onChange={e => setWeeks(Number(e.target.value))} style={{ marginLeft: 'auto', padding: '0.5rem', background: '#161b22', border: '1px solid #30363d', borderRadius: 4, color: '#e0e0e0' }}>
            <option value={2}>2 weeks</option>
            <option value={4}>4 weeks</option>
            <option value={8}>8 weeks</option>
          </select>
        )}
      </div>

      {tab === 'performance' && rankings && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left' }}>
              <th style={{ padding: '0.5rem' }}>Boss</th>
              <th style={{ padding: '0.5rem' }}>Spec</th>
              <th style={{ padding: '0.5rem' }}>Parse</th>
              <th style={{ padding: '0.5rem' }}>Report</th>
            </tr>
          </thead>
          <tbody>
            {rankings.map((r, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #21262d' }}>
                <td style={{ padding: '0.5rem' }}>{r.encounter_name}</td>
                <td style={{ padding: '0.5rem' }}>{r.spec}</td>
                <td style={{ padding: '0.5rem' }}><ParseBar percent={r.rank_percent} /></td>
                <td style={{ padding: '0.5rem', color: '#8b949e', fontSize: 12 }}>{r.report_code}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'gear' && gear && (
        <div>
          <p style={{ marginBottom: '0.5rem' }}>
            Avg iLvl: <strong>{gear.avg_ilvl.toFixed(1)}</strong> {gear.ilvl_ok ? '✅' : '⚠️'}
            {gear.issues.length > 0 && <span style={{ color: '#ff6b6b', marginLeft: '1rem' }}>{gear.issues.length} issue(s)</span>}
          </p>
          <GearGrid gear={gear.gear} issues={gear.issues} />
        </div>
      )}

      {tab === 'attendance' && attendance && (
        <div>
          {attendance.map((week, i) => (
            <div key={i} style={{ marginBottom: '0.75rem', padding: '0.5rem', background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
              <strong>Week {week.week}, {week.year}</strong>
              <div style={{ marginTop: '0.25rem' }}>
                {week.zones?.map((z, j) => (
                  <span key={j} style={{ marginRight: '1rem', fontSize: 14 }}>
                    {z.met ? '✅' : '❌'} {z.zone_label} ({z.clear_count}/{z.required})
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
