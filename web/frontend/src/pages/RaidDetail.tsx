import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'
import { CHART_COLORS, CHART_DEFAULTS } from '../components/ChartTheme'
import Layout from '../components/Layout'
import ClassIcon, { getSpecLabel } from '../components/ClassIcon'
import ParseBar from '../components/ParseBar'
import { SkeletonTable } from '../components/Skeleton'

export default function RaidDetail() {
  const { code } = useParams<{ code: string }>()
  const { data: report, isLoading } = useQuery({
    queryKey: ['report', code],
    queryFn: () => api.reports.get(code!),
    enabled: !!code,
  })

  const { data: deathData } = useQuery({
    queryKey: ['deaths', code],
    queryFn: () => api.reports.deaths(code!),
    enabled: !!code,
  })

  const { data: wipeData } = useQuery({
    queryKey: ['wipes', code],
    queryFn: () => api.reports.wipes(code!),
    enabled: !!code,
  })

  const { data: utilityData } = useQuery({
    queryKey: ['utility', code],
    queryFn: () => api.reports.utility(code!),
    enabled: !!code,
  })

  const { data: gearData } = useQuery({
    queryKey: ['report-gear', code],
    queryFn: () => api.reports.gear(code!),
    enabled: !!code,
  })

  const [expandedFight, setExpandedFight] = useState<number | null>(null)

  const { data: fights } = useQuery({
    queryKey: ['fights', code],
    queryFn: () => api.reports.fights(code!),
    enabled: !!code,
  })

  const { data: fightDetail } = useQuery({
    queryKey: ['fight-detail', code, expandedFight],
    queryFn: () => api.reports.fightDetail(code!, expandedFight!),
    enabled: !!code && expandedFight !== null,
  })

  if (isLoading) return <Layout><div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden"><table className="w-full"><tbody><SkeletonTable rows={8} cols={5} /></tbody></table></div></Layout>
  if (!report) return <Layout><p className="text-text-secondary">Report not found</p></Layout>

  const consumables = report.consumables?.filter(c => c.actual_value > 0) || []

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary">{report.zone_name}</h1>
        <div className="flex items-center gap-3 mt-1 text-sm text-text-secondary">
          <span>{new Date(report.start_time).toLocaleDateString()}</span>
          <span className="text-text-muted">|</span>
          <span>{report.player_count} players</span>
          <span className="text-text-muted">|</span>
          <span className="font-mono text-text-muted">{report.code}</span>
        </div>
      </div>

      {/* Scores */}
      <div className="bg-bg-surface border border-border-default rounded-xl overflow-hidden mb-6">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-default">
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Spec</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Score</th>
              <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Parse</th>
            </tr>
          </thead>
          <tbody>
            {report.scores.map((s, i) => (
              <tr key={i} className="border-b border-border-default/50 hover:bg-bg-hover transition-colors">
                <td className="p-3">
                  <Link to={`/player/${s.player_name}`} className="no-underline">
                    <ClassIcon className={s.class_name} name={s.player_name} />
                  </Link>
                </td>
                <td className="p-3 text-sm text-text-secondary capitalize hidden sm:table-cell">{getSpecLabel(s.spec)}</td>
                <td className="p-3 text-sm font-semibold text-accent-gold tabular-nums">{s.overall_score.toFixed(1)}</td>
                <td className="p-3"><ParseBar percent={s.parse_score} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Consumables */}
      {consumables.length > 0 && (() => {
        const flags = report.consumable_flags || []
        const flaggedPlayers = flags.filter(f => !f.passed)
        const passedCount = flags.filter(f => f.passed).length
        return (
        <details className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
          <summary className="p-4 cursor-pointer text-sm font-semibold text-text-primary hover:bg-bg-hover transition-colors select-none">
            Consumables — <span className="text-success">{passedCount} passed</span>
            {flaggedPlayers.length > 0 && <>, <span className="text-danger">{flaggedPlayers.length} flagged</span></>}
          </summary>
          {flaggedPlayers.length > 0 && (
            <div className="px-4 pb-3 pt-1">
              <div className="flex flex-wrap gap-2">
                {flaggedPlayers.map(f => (
                  <span key={f.player_name} className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-danger/10 border border-danger/20 text-danger">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                    </svg>
                    {f.player_name}: {f.reasons.join(', ')}
                  </span>
                ))}
              </div>
            </div>
          )}
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-default">
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Metric</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Value</th>
                <th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Target</th>
              </tr>
            </thead>
            <tbody>
              {consumables.map((c, i) => (
                <tr key={i} className="border-b border-border-default/50">
                  <td className="p-3 text-sm text-text-primary">{c.player_name}</td>
                  <td className="p-3 text-sm text-text-secondary">
                    {c.label}
                    {c.optional && <span className="ml-1.5 text-xs text-text-muted">(optional)</span>}
                  </td>
                  <td className="p-3 text-sm tabular-nums text-text-primary">{c.actual_value}</td>
                  <td className="p-3 text-sm tabular-nums text-text-muted">{c.target_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
        )
      })()}

      {/* Utility Breakdown */}
      {utilityData && utilityData.length > 0 && (
        <details className="bg-bg-surface border border-border-default rounded-xl overflow-hidden mt-6">
          <summary className="p-4 cursor-pointer text-sm font-semibold text-text-primary hover:bg-bg-hover transition-colors select-none">
            Utility Breakdown ({utilityData.length} players)
          </summary>
          <div className="p-4 pt-0 space-y-4">
            {utilityData.map((player) => (
              <div key={player.player_name}>
                <div className="flex items-center gap-2 mb-2">
                  <ClassIcon className={player.class_name} name={player.player_name} />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                  {player.metrics.map((m) => (
                    <div
                      key={m.metric_name}
                      className={`p-2 rounded border text-xs ${
                        m.score >= 100
                          ? 'bg-success/10 border-success/20'
                          : 'bg-danger/10 border-danger/20'
                      }`}
                    >
                      <div className="font-medium text-text-primary mb-1">{m.label}</div>
                      <div className="tabular-nums">
                        <span className={m.score >= 100 ? 'text-success' : 'text-danger'}>
                          {m.actual_value % 1 === 0 ? m.actual_value : m.actual_value.toFixed(1)}
                        </span>
                        <span className="text-text-muted"> / {m.target_value}</span>
                      </div>
                      <div className={`text-[10px] mt-0.5 ${m.score >= 100 ? 'text-success' : 'text-danger'}`}>
                        {m.score.toFixed(0)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Death Summary */}
      {deathData && (
        <div className="mt-6">
          <details className="bg-bg-surface border border-border-default rounded-xl overflow-hidden" open>
            <summary className="p-4 cursor-pointer text-sm font-semibold text-text-primary hover:bg-bg-hover transition-colors select-none">
              Deaths
            </summary>
            <div className="p-4 pt-0">
              {/* Death totals */}
              {deathData.totals?.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs text-text-muted mb-2 uppercase font-semibold">Total Deaths</div>
                  <div className="flex flex-wrap gap-2">
                    {deathData.totals.map((t: any) => (
                      <span key={t.player} className={`px-2 py-1 rounded text-xs border ${
                        t.death_count === 0 ? 'bg-success/10 border-success/20 text-success' : 'bg-bg-hover border-border-default text-text-primary'
                      }`}>
                        {t.player}: {t.death_count}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Per-fight deaths */}
              {deathData.per_fight?.map((fight: any, i: number) => (
                fight.deaths.length > 0 && (
                  <div key={i} className="mb-3">
                    <div className="text-sm font-medium text-text-primary mb-1">
                      {fight.fight_name} {fight.kill ? '(Kill)' : '(Wipe)'}
                    </div>
                    <div className="space-y-0.5">
                      {fight.deaths.map((d: any, j: number) => (
                        <div key={j} className="text-xs text-text-secondary flex gap-2">
                          <span className="text-text-muted w-10 tabular-nums">{d.time || `${d.timestamp_pct}%`}</span>
                          <span>{d.player}</span>
                          {d.ability && <span className="text-text-muted">— {d.ability}</span>}
                          {d.damage_taken != null && d.damage_taken > 0 && <span className="text-danger text-text-muted">({d.damage_taken.toLocaleString()} dmg)</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              ))}
            </div>
          </details>
        </div>
      )}

      {/* Wipe Analysis */}
      {wipeData && wipeData.length > 0 && (
        <div className="mt-4">
          <details className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <summary className="p-4 cursor-pointer text-sm font-semibold text-text-primary hover:bg-bg-hover transition-colors select-none">
              Wipe Analysis ({wipeData.reduce((sum: number, e: any) => sum + e.wipe_count, 0)} wipes)
            </summary>
            <div className="p-4 pt-0 space-y-4">
              {wipeData.map((encounter: any) => (
                <div key={encounter.encounter_name}>
                  <div className="text-sm font-medium text-text-primary mb-2">
                    {encounter.encounter_name}
                    <span className="text-text-muted ml-2 text-xs">
                      {encounter.wipe_count} wipe{encounter.wipe_count !== 1 ? 's' : ''}, {encounter.kill_count} kill{encounter.kill_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {encounter.wipes.map((wipe: any, i: number) => (
                      <div key={i} className="p-2 rounded bg-danger/5 border border-danger/10 text-xs">
                        <div className="flex gap-3 mb-1">
                          <span className="text-text-secondary">{wipe.duration_s}s</span>
                          <span className="text-danger">Boss at {wipe.boss_pct}%</span>
                          <span className="text-text-muted">{wipe.deaths.length} deaths</span>
                        </div>
                        {wipe.deaths.length > 0 && (
                          <div className="space-y-0.5 text-text-muted">
                            {wipe.deaths.slice(0, 5).map((d: any, j: number) => (
                              <div key={j}>{d.timestamp_pct}% — {d.player} ({d.ability})</div>
                            ))}
                            {wipe.deaths.length > 5 && <div>...and {wipe.deaths.length - 5} more</div>}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* Gear Check */}
      {gearData && gearData.total_players > 0 && (
        <div className="mt-4">
          <details className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <summary className="p-4 cursor-pointer text-sm font-semibold text-text-primary hover:bg-bg-hover transition-colors select-none">
              Gear Check — <span className="text-success">{gearData.passed} passed</span>
              {gearData.flagged > 0 && <>, <span className="text-danger">{gearData.flagged} flagged</span></>}
            </summary>
            <div className="p-4 pt-0">
              {gearData.gear_config && (
                <div className="text-xs text-text-muted mb-3">
                  Min ilvl: {gearData.gear_config.min_avg_ilvl} | Min quality: {gearData.gear_config.min_quality === 4 ? 'Epic' : gearData.gear_config.min_quality === 3 ? 'Rare' : 'Uncommon'} | Enchants: {gearData.gear_config.check_enchants ? 'Yes' : 'No'} | Gems: {gearData.gear_config.check_gems ? 'Yes' : 'No'}
                </div>
              )}
              {gearData.players.filter(p => p.issue_count > 0 || !p.ilvl_ok).length > 0 ? (
                <div className="space-y-3">
                  {gearData.players.filter(p => p.issue_count > 0 || !p.ilvl_ok).map(p => (
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
                        {!p.ilvl_ok && (
                          <div className="text-xs text-danger">Average ilvl below minimum ({gearData.gear_config?.min_avg_ilvl})</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-success">All players passed gear check</div>
              )}
              {gearData.passed > 0 && gearData.flagged > 0 && (
                <div className="text-xs text-text-muted mt-3">{gearData.passed} player(s) passed all checks</div>
              )}
            </div>
          </details>
        </div>
      )}

      {/* Boss Scorecards */}
      {fights && fights.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-text-primary mb-3">Boss Scorecards</h2>
          <div className="space-y-2">
            {fights.map((fight: any) => (
              <div key={fight.fight_id} className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedFight(expandedFight === fight.fight_id ? null : fight.fight_id)}
                  className="w-full p-3 flex items-center justify-between text-left cursor-pointer bg-transparent border-none hover:bg-bg-hover transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${fight.kill ? 'bg-success' : 'bg-danger'}`} />
                    <span className="text-sm font-medium text-text-primary">{fight.encounter_name}</span>
                    <span className="text-xs text-text-muted">{fight.duration_s}s</span>
                    {!fight.kill && <span className="text-xs text-danger">{fight.fight_percentage}%</span>}
                  </div>
                  <svg className={`w-4 h-4 text-text-muted transition-transform ${expandedFight === fight.fight_id ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {expandedFight === fight.fight_id && fightDetail && (
                  <div className="p-4 border-t border-border-default">
                    <div className="flex gap-3 text-xs text-text-muted mb-3">
                      <span>{fightDetail.attempts} attempt{fightDetail.attempts !== 1 ? 's' : ''}</span>
                      <span>{fightDetail.duration_s}s duration</span>
                      <span>{fightDetail.players.length} players</span>
                    </div>

                    {/* DPS Chart */}
                    {fightDetail.players.some((p: any) => p.dps > 0) && (
                      <div className="mb-4">
                        <div className="text-xs text-text-muted mb-2">DPS</div>
                        <ResponsiveContainer width="100%" height={Math.max(150, fightDetail.players.filter((p: any) => p.dps > 0).length * 28)}>
                          <BarChart data={fightDetail.players.filter((p: any) => p.dps > 0)} layout="vertical">
                            <CartesianGrid stroke={CHART_DEFAULTS.gridStroke} strokeDasharray="3 3" />
                            <XAxis type="number" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
                            <YAxis type="category" dataKey="name" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} width={90} />
                            <Tooltip contentStyle={{ backgroundColor: CHART_COLORS.bg, border: `1px solid ${CHART_COLORS.grid}`, borderRadius: 8 }} />
                            <Bar dataKey="dps" fill={CHART_COLORS.danger} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {/* HPS Chart */}
                    {fightDetail.players.some((p: any) => p.hps > 0) && (
                      <div className="mb-4">
                        <div className="text-xs text-text-muted mb-2">HPS</div>
                        <ResponsiveContainer width="100%" height={Math.max(100, fightDetail.players.filter((p: any) => p.hps > 0).length * 28)}>
                          <BarChart data={fightDetail.players.filter((p: any) => p.hps > 0)} layout="vertical">
                            <CartesianGrid stroke={CHART_DEFAULTS.gridStroke} strokeDasharray="3 3" />
                            <XAxis type="number" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
                            <YAxis type="category" dataKey="name" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} width={90} />
                            <Tooltip contentStyle={{ backgroundColor: CHART_COLORS.bg, border: `1px solid ${CHART_COLORS.grid}`, borderRadius: 8 }} />
                            <Bar dataKey="hps" fill={CHART_COLORS.success} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    {/* Player table */}
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border-default">
                          <th className="p-2 text-left text-text-muted">Player</th>
                          <th className="p-2 text-left text-text-muted">DPS</th>
                          <th className="p-2 text-left text-text-muted">HPS</th>
                          <th className="p-2 text-left text-text-muted">Parse %</th>
                          <th className="p-2 text-left text-text-muted">Deaths</th>
                        </tr>
                      </thead>
                      <tbody>
                        {fightDetail.players.map((p: any) => {
                          const bossRankings = report?.boss_rankings?.[fight.encounter_name]
                          const ranking = bossRankings?.find((r: any) => r.player_name === p.name)
                          return (
                            <tr key={p.name} className="border-b border-border-default/50">
                              <td className="p-2 text-text-primary">{p.name}</td>
                              <td className="p-2 text-text-secondary tabular-nums">{p.dps.toLocaleString()}</td>
                              <td className="p-2 text-text-secondary tabular-nums">{p.hps.toLocaleString()}</td>
                              <td className="p-2">{ranking ? <ParseBar percent={ranking.rank_percent} /> : <span className="text-text-muted">—</span>}</td>
                              <td className="p-2">{p.deaths > 0 ? <span className="text-danger">{p.deaths}</span> : <span className="text-success">0</span>}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </Layout>
  )
}
