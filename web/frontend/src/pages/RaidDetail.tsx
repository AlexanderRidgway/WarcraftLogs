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
    </Layout>
  )
}
