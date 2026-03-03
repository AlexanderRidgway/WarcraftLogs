import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'
import Layout from '../components/Layout'
import { CHART_COLORS } from '../components/ChartTheme'
import { useScoreAccess } from '../hooks/useScoreAccess'

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

export default function Roster() {
  const [weeks, setWeeks] = useState(4)

  const { data, isLoading } = useQuery({
    queryKey: ['roster-health', weeks],
    queryFn: () => api.roster(weeks),
  })

  const { canViewScores } = useScoreAccess()

  if (isLoading) return <Layout><div className="text-text-muted text-sm">Loading roster data...</div></Layout>

  const distribution = data?.distribution || []
  const atRiskSpecs = data?.at_risk_specs || []
  const atRisk = data?.at_risk || []
  const attendanceGrid = data?.attendance_grid || []

  // Aggregate by class for pie chart
  const classCounts: Record<string, number> = {}
  for (const d of distribution) {
    classCounts[d.class_name] = (classCounts[d.class_name] || 0) + d.count
  }
  const pieData = Object.entries(classCounts).map(([name, value]) => ({ name, value }))

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">Roster Health</h1>
        <div className="flex rounded-lg border border-border-default overflow-hidden">
          {[2, 4, 8].map(w => (
            <button
              key={w}
              onClick={() => setWeeks(w)}
              className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer border-none ${
                weeks === w ? 'bg-accent-gold text-bg-base' : 'bg-bg-surface text-text-secondary hover:text-text-primary'
              }`}
            >
              {w}w
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Class Distribution */}
        <div className="bg-bg-surface border border-border-default rounded-xl p-4">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Class Distribution</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name} (${value})`}>
                  {pieData.map(entry => (
                    <Cell key={entry.name} fill={CLASS_COLORS[entry.name] || CHART_COLORS.textMuted} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: CHART_COLORS.bg, border: `1px solid ${CHART_COLORS.grid}`, borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-text-muted text-sm">No data</div>
          )}
        </div>

        {/* At Risk */}
        {canViewScores && (
        <div className="bg-bg-surface border border-border-default rounded-xl p-4">
          <h2 className="text-sm font-semibold text-text-primary mb-3">At Risk</h2>
          {atRiskSpecs.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-text-muted mb-1">Single-player specs:</div>
              <div className="flex flex-wrap gap-1">
                {atRiskSpecs.map((s: any) => (
                  <span key={s.spec} className="px-2 py-0.5 text-xs rounded bg-danger/10 text-danger border border-danger/20 capitalize">
                    {s.spec.replace(':', ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}
          {atRisk.length > 0 ? (
            <div className="space-y-2">
              <div className="text-xs text-text-muted">Declining performance:</div>
              {atRisk.map((p: any) => (
                <div key={p.name} className="flex items-center justify-between p-2 rounded bg-danger/5 border border-danger/10">
                  <Link to={`/player/${p.name}`} className="text-sm text-text-primary no-underline hover:text-accent-gold capitalize">{p.name}</Link>
                  <span className="text-xs text-danger">{p.reason}</span>
                </div>
              ))}
            </div>
          ) : atRiskSpecs.length === 0 ? (
            <div className="text-text-muted text-sm">No at-risk players or specs detected</div>
          ) : null}
        </div>
        )}
      </div>

      {/* Attendance Heatmap */}
      <div className="bg-bg-surface border border-border-default rounded-xl p-4">
        <h2 className="text-sm font-semibold text-text-primary mb-3">Attendance Overview</h2>
        {attendanceGrid.length > 0 ? (
          <div className="overflow-x-auto">
            <div className="space-y-1">
              {attendanceGrid.map((player: any) => (
                <div key={player.name} className="flex items-center gap-2">
                  <Link to={`/player/${player.name}`} className="w-24 text-xs text-text-secondary truncate no-underline hover:text-accent-gold">{player.name}</Link>
                  <div className="flex gap-0.5">
                    {player.weeks.map((w: any, i: number) => (
                      <div
                        key={i}
                        className={`w-4 h-4 rounded-sm ${w.met ? 'bg-success/60' : 'bg-danger/60'}`}
                        title={`Week ${w.week}, ${w.year}: ${w.met ? 'Met' : 'Missed'}`}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-text-muted text-sm">No attendance data available</div>
        )}
      </div>
    </Layout>
  )
}
