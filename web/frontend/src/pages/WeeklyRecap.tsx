import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import { SkeletonTable } from '../components/Skeleton'

const MEDAL = ['', '\u{1F947}', '\u{1F948}', '\u{1F949}']

export default function WeeklyRecap() {
  const [weeksAgo, setWeeksAgo] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ['weekly', weeksAgo],
    queryFn: () => api.weekly(weeksAgo),
  })

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary">Weekly Recap</h1>
        <div className="flex items-center gap-3 mt-2">
          <button
            onClick={() => setWeeksAgo(w => w + 1)}
            disabled={weeksAgo >= 52}
            className="px-3 py-1.5 text-sm bg-bg-surface border border-border-default rounded-lg text-text-secondary hover:bg-bg-hover disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed transition-colors"
          >
            &larr; Previous
          </button>
          <span className="text-sm text-text-secondary tabular-nums">
            {data ? `${data.week_start} \u2014 ${data.week_end}` : '...'}
          </span>
          <button
            onClick={() => setWeeksAgo(w => Math.max(0, w - 1))}
            disabled={weeksAgo === 0}
            className="px-3 py-1.5 text-sm bg-bg-surface border border-border-default rounded-lg text-text-secondary hover:bg-bg-hover disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed transition-colors"
          >
            Next &rarr;
          </button>
          {weeksAgo > 0 && (
            <button
              onClick={() => setWeeksAgo(0)}
              className="px-3 py-1.5 text-sm text-accent-gold hover:underline cursor-pointer bg-transparent border-none"
            >
              Current week
            </button>
          )}
        </div>
      </div>

      {isLoading && (
        <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
          <table className="w-full"><tbody><SkeletonTable rows={5} cols={4} /></tbody></table>
        </div>
      )}

      {!isLoading && data && data.report_count === 0 && (
        <div className="bg-bg-surface border border-border-default rounded-xl p-8 text-center">
          <div className="text-text-muted text-sm">No reports found for this week</div>
        </div>
      )}

      {!isLoading && data && data.report_count > 0 && (
        <div className="space-y-6">
          {/* Report count badge */}
          <div className="text-sm text-text-muted">
            {data.report_count} report{data.report_count !== 1 ? 's' : ''} this week
          </div>

          {/* Top Performers */}
          <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <div className="p-4 border-b border-border-default">
              <h2 className="text-sm font-semibold text-text-primary">Top Performers</h2>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b border-border-default">
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider w-10">#</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Avg Score</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Avg Parse</th>
                  <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Fights</th>
                </tr>
              </thead>
              <tbody>
                {data.top_performers.map((p, i) => (
                  <tr key={p.name} className="border-b border-border-default/50 hover:bg-bg-hover transition-colors">
                    <td className="p-3 text-sm text-text-muted">
                      {MEDAL[i + 1] || (i + 1)}
                    </td>
                    <td className="p-3">
                      <Link to={`/player/${p.name}`} className="no-underline">
                        <ClassIcon className={p.class_name} name={p.name} />
                      </Link>
                    </td>
                    <td className="p-3 text-sm font-semibold text-accent-gold tabular-nums">{p.avg_score}</td>
                    <td className="p-3 text-sm tabular-nums text-text-secondary">{p.avg_parse}</td>
                    <td className="p-3 text-sm tabular-nums text-text-muted hidden sm:table-cell">{p.fight_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Zone Summaries */}
          {data.zone_summaries.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-text-primary mb-3">Zone Summaries</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.zone_summaries.map((zone) => (
                  <div key={zone.zone_name} className="bg-bg-surface border border-border-default rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-text-primary">{zone.zone_name}</h3>
                      <div className="text-xs text-text-muted">
                        {zone.run_count} run{zone.run_count !== 1 ? 's' : ''} &middot; {zone.unique_players} players
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      {zone.top_players.map((p, i) => (
                        <div key={p.name} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-sm">{MEDAL[i + 1] || ''}</span>
                            <ClassIcon className={p.class_name} name={p.name} />
                          </div>
                          <span className="text-sm font-semibold text-accent-gold tabular-nums">{p.avg_score}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Attendance */}
          <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <div className="p-4 border-b border-border-default">
              <h2 className="text-sm font-semibold text-text-primary">Attendance</h2>
            </div>
            <div className="p-4">
              {data.attendance.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-success">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                  All players met attendance requirements
                </div>
              ) : (
                <div className="space-y-2">
                  {data.attendance.map((a, i) => (
                    <div key={i} className="flex items-center justify-between p-2 rounded bg-danger/5 border border-danger/10">
                      <span className="text-sm text-text-primary">{a.player_name}</span>
                      <span className="text-xs text-danger">
                        {a.zone_label}: {a.clear_count}/{a.required}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Gear Issues */}
          <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <div className="p-4 border-b border-border-default">
              <h2 className="text-sm font-semibold text-text-primary">Gear Issues</h2>
            </div>
            <div className="p-4">
              {data.gear_issues.length === 0 ? (
                <div className="flex items-center gap-2 text-sm text-success">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                  All players passed gear check
                </div>
              ) : (
                <div className="space-y-3">
                  {data.gear_issues.map((p) => (
                    <div key={p.name} className="p-3 rounded border border-danger/20 bg-danger/5">
                      <div className="flex items-center justify-between mb-1">
                        <ClassIcon className={p.class_name} name={p.name} />
                        <span className={`text-xs tabular-nums ${p.ilvl_ok ? 'text-text-muted' : 'text-danger'}`}>
                          ilvl {p.avg_ilvl}
                        </span>
                      </div>
                      <div className="space-y-0.5">
                        {p.issues.map((issue, j) => (
                          <div key={j} className="text-xs text-danger">
                            {issue.slot}: {issue.problem}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
