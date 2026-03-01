import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
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
                  <ClassIcon className={s.class_name} name={s.player_name} />
                </td>
                <td className="p-3 text-sm text-text-secondary hidden sm:table-cell">{s.spec}</td>
                <td className="p-3 text-sm font-semibold text-accent-gold tabular-nums">{s.overall_score.toFixed(1)}</td>
                <td className="p-3"><ParseBar percent={s.parse_score} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Consumables */}
      {consumables.length > 0 && (
        <details className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
          <summary className="p-4 cursor-pointer text-sm font-semibold text-text-primary hover:bg-bg-hover transition-colors select-none">
            Consumables ({consumables.length})
          </summary>
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
                          <span className="text-text-muted w-10">{d.timestamp_pct}%</span>
                          <span>{d.player}</span>
                          <span className="text-text-muted">— {d.ability}</span>
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
    </Layout>
  )
}
