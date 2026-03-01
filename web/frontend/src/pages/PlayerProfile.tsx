import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import ScoreCard from '../components/ScoreCard'
import ParseBar from '../components/ParseBar'
import GearGrid from '../components/GearGrid'
import { SkeletonTable, SkeletonCard } from '../components/Skeleton'

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

  if (isLoading) return <Layout><div className="space-y-4"><SkeletonCard /><SkeletonCard /></div></Layout>
  if (!player) return <Layout><p className="text-text-secondary">Player not found</p></Layout>

  const avgScore = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.overall_score, 0) / player.scores.length
    : null
  const avgParse = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.parse_score, 0) / player.scores.length
    : null

  const TABS: { key: Tab; label: string }[] = [
    { key: 'performance', label: 'Performance' },
    { key: 'gear', label: 'Gear' },
    { key: 'attendance', label: 'Attendance' },
  ]

  const WEEK_OPTIONS = [2, 4, 8]

  return (
    <Layout>
      {/* Hero header */}
      <div className="mb-6">
        <div className="flex items-center gap-4 mb-3">
          <ClassIcon className={player.class_name} name={player.name} size={48} />
        </div>
        <p className="text-sm text-text-secondary capitalize">
          {player.class_name} — {player.server} ({player.region.toUpperCase()})
        </p>
      </div>

      {/* Score cards */}
      <div className="flex gap-4 mb-6">
        <ScoreCard label="Consistency" value={avgScore} />
        <ScoreCard label="Avg Parse" value={avgParse} />
      </div>

      {/* Tabs + week selector */}
      <div className="flex items-center justify-between mb-5 border-b border-border-default">
        <div className="flex">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-3 text-sm font-medium transition-colors cursor-pointer bg-transparent border-none border-b-2 -mb-px ${
                tab === t.key
                  ? 'text-accent-gold border-accent-gold'
                  : 'text-text-secondary hover:text-text-primary border-transparent'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        {(tab === 'performance' || tab === 'attendance') && (
          <div className="flex rounded-lg border border-border-default overflow-hidden mb-1">
            {WEEK_OPTIONS.map(w => (
              <button
                key={w}
                onClick={() => setWeeks(w)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer border-none ${
                  weeks === w
                    ? 'bg-accent-gold text-bg-base'
                    : 'bg-bg-surface text-text-secondary hover:text-text-primary'
                }`}
              >
                {w}w
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Performance tab */}
      {tab === 'performance' && (
        <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-default">
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Boss</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Spec</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Parse</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Report</th>
              </tr>
            </thead>
            <tbody>
              {!rankings ? (
                <SkeletonTable rows={6} cols={4} />
              ) : (
                rankings.map((r, i) => (
                  <tr key={i} className="border-b border-border-default/50 hover:bg-bg-hover transition-colors">
                    <td className="p-3 text-sm text-text-primary">{r.encounter_name}</td>
                    <td className="p-3 text-sm text-text-secondary">{r.spec}</td>
                    <td className="p-3"><ParseBar percent={r.rank_percent} /></td>
                    <td className="p-3 text-xs text-text-muted font-mono hidden sm:table-cell">{r.report_code}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Gear tab */}
      {tab === 'gear' && gear && (
        <div>
          <div className="flex items-center gap-4 mb-4">
            <span className="text-sm text-text-secondary">
              Avg iLvl: <strong className="text-text-primary">{gear.avg_ilvl.toFixed(1)}</strong>
              {gear.ilvl_ok ? ' \u2705' : ' \u26A0\uFE0F'}
            </span>
            {gear.issues.length > 0 && (
              <span className="text-sm text-danger">{gear.issues.length} issue(s)</span>
            )}
          </div>
          <GearGrid gear={gear.gear} issues={gear.issues} />
        </div>
      )}

      {/* Attendance tab */}
      {tab === 'attendance' && attendance && (
        <div className="space-y-3">
          {attendance.map((week, i) => (
            <div key={i} className="bg-bg-surface border border-border-default rounded-xl p-4">
              <div className="font-semibold text-sm text-text-primary mb-2">
                Week {week.week}, {week.year}
              </div>
              <div className="flex flex-wrap gap-3">
                {week.zones?.map((z, j) => (
                  <span
                    key={j}
                    className={`text-sm px-3 py-1 rounded-lg border ${
                      z.met
                        ? 'border-success/30 bg-success/10 text-success'
                        : 'border-danger/30 bg-danger/10 text-danger'
                    }`}
                  >
                    {z.met ? '\u2705' : '\u274C'} {z.zone_label} ({z.clear_count}/{z.required})
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
