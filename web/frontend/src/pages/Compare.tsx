import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import { CHART_COLORS, CHART_DEFAULTS } from '../components/ChartTheme'

const ALL_SPECS = [
  'warrior:protection', 'warrior:fury', 'warrior:arms',
  'paladin:holy', 'paladin:protection', 'paladin:retribution',
  'rogue:combat',
  'hunter:beast mastery', 'hunter:survival',
  'shaman:restoration', 'shaman:elemental', 'shaman:enhancement',
  'druid:feral', 'druid:restoration', 'druid:balance',
  'mage:arcane', 'mage:fire',
  'warlock:affliction', 'warlock:destruction',
  'priest:holy', 'priest:discipline', 'priest:shadow',
]

interface CompareEntry {
  name: string
  class_name: string
  avg_score: number
  avg_parse: number
  avg_utility: number | null
  fight_count: number
}

export default function Compare() {
  const [spec, setSpec] = useState(ALL_SPECS[0])
  const [weeks, setWeeks] = useState(4)

  const { data: players, isLoading } = useQuery({
    queryKey: ['compare', spec, weeks],
    queryFn: () => api.compare(spec, weeks),
  })

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Spec Comparison</h1>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <select
          value={spec}
          onChange={e => setSpec(e.target.value)}
          className="flex-1 px-3 py-2 bg-bg-surface border border-border-default rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent-gold capitalize"
        >
          {ALL_SPECS.map(s => (
            <option key={s} value={s}>{s.replace(':', ' — ')}</option>
          ))}
        </select>
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

      {isLoading ? (
        <div className="text-text-muted text-sm">Loading comparison...</div>
      ) : players && players.length > 0 ? (
        <>
          {/* Bar chart */}
          <div className="bg-bg-surface border border-border-default rounded-xl p-4 mb-4">
            <ResponsiveContainer width="100%" height={Math.max(200, players.length * 40)}>
              <BarChart data={players} layout="vertical">
                <CartesianGrid stroke={CHART_DEFAULTS.gridStroke} strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
                <YAxis type="category" dataKey="name" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} width={100} />
                <Tooltip
                  contentStyle={{ backgroundColor: CHART_COLORS.bg, border: `1px solid ${CHART_COLORS.grid}`, borderRadius: 8 }}
                  labelStyle={{ color: CHART_COLORS.text }}
                />
                <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
                <Bar dataKey="avg_score" name="Score" fill={CHART_COLORS.gold} />
                <Bar dataKey="avg_parse" name="Parse" fill={CHART_COLORS.info} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Table */}
          <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border-default">
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase">Player</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase">Score</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase">Parse</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase hidden sm:table-cell">Utility</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase">Fights</th>
                </tr>
              </thead>
              <tbody>
                {players.map((p: CompareEntry) => (
                  <tr key={p.name} className="border-b border-border-default/50 hover:bg-bg-hover transition-colors">
                    <td className="p-3">
                      <Link to={`/player/${p.name}`} className="no-underline">
                        <ClassIcon className={p.class_name} name={p.name} />
                      </Link>
                    </td>
                    <td className="p-3 text-sm font-semibold text-accent-gold">{p.avg_score}</td>
                    <td className="p-3 text-sm text-text-primary">{p.avg_parse}</td>
                    <td className="p-3 text-sm text-text-secondary hidden sm:table-cell">{p.avg_utility ?? '—'}</td>
                    <td className="p-3 text-sm text-text-secondary">{p.fight_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="text-text-muted text-sm">No players found for this spec in the selected time period.</div>
      )}
    </Layout>
  )
}
