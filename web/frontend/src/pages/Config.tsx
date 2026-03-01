import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../components/Toast'
import { SkeletonCard } from '../components/Skeleton'

export default function Config() {
  const { isAuthenticated } = useAuth()
  const { addToast } = useToast()
  const queryClient = useQueryClient()

  const { data: specs, isLoading: specsLoading } = useQuery({
    queryKey: ['config-specs'],
    queryFn: api.config.specs,
  })
  const { data: consumables } = useQuery({
    queryKey: ['config-consumables'],
    queryFn: api.config.consumables,
  })
  const { data: attendanceConfig } = useQuery({
    queryKey: ['config-attendance'],
    queryFn: api.config.attendance,
  })
  const { data: gearConfig } = useQuery({
    queryKey: ['config-gear'],
    queryFn: api.config.gear,
  })

  const [expandedSpec, setExpandedSpec] = useState<string | null>(null)
  const [editingTarget, setEditingTarget] = useState<{ spec: string; metric: string } | null>(null)
  const [editValue, setEditValue] = useState('')
  const [editingWeights, setEditingWeights] = useState<string | null>(null)
  const [weights, setWeights] = useState({ parse: 0, utility: 0, consumables: 0 })
  const [editingAttendance, setEditingAttendance] = useState<number | null>(null)
  const [attendanceValue, setAttendanceValue] = useState(0)

  const targetMutation = useMutation({
    mutationFn: ({ spec, metric, target }: { spec: string; metric: string; target: number }) =>
      api.config.updateTarget(spec, metric, target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-specs'] })
      addToast('Target updated', 'success')
      setEditingTarget(null)
    },
    onError: () => addToast('Failed to update target', 'error'),
  })

  const weightsMutation = useMutation({
    mutationFn: ({ spec, w }: { spec: string; w: { parse_weight: number; utility_weight: number; consumables_weight: number } }) =>
      api.config.updateWeights(spec, w),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-specs'] })
      addToast('Weights updated', 'success')
      setEditingWeights(null)
    },
    onError: () => addToast('Weights must sum to 100%', 'error'),
  })

  const attendanceMutation = useMutation({
    mutationFn: ({ zoneId, required }: { zoneId: number; required: number }) =>
      api.config.updateAttendance(zoneId, required),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-attendance'] })
      addToast('Attendance updated', 'success')
      setEditingAttendance(null)
    },
    onError: () => addToast('Failed to update attendance', 'error'),
  })

  if (specsLoading) return <Layout><div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}</div></Layout>

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Configuration</h1>
      {!isAuthenticated && (
        <div className="mb-6 p-4 bg-accent-gold/10 border border-accent-gold/20 rounded-xl text-sm text-accent-gold">
          Viewing as guest. Log in as an officer to edit configuration.
        </div>
      )}

      {/* Spec Profiles */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Spec Profiles</h2>
      <div className="space-y-2 mb-8">
        {specs && Object.entries(specs).map(([key, spec]: [string, any]) => (
          <div key={key} className="bg-bg-surface border border-border-default rounded-xl overflow-hidden">
            <button
              onClick={() => setExpandedSpec(expandedSpec === key ? null : key)}
              className="w-full flex items-center justify-between p-4 text-left bg-transparent border-none cursor-pointer hover:bg-bg-hover transition-colors"
            >
              <span className="text-sm font-semibold text-text-primary capitalize">{key.replace(':', ' — ')}</span>
              <div className="flex items-center gap-3 text-xs text-text-muted">
                <span>Parse {((spec.parse_weight || 0) * 100).toFixed(0)}%</span>
                <span>Utility {((spec.utility_weight || 0) * 100).toFixed(0)}%</span>
                <span>Consumes {((spec.consumables_weight || 0) * 100).toFixed(0)}%</span>
                <svg className={`w-4 h-4 transition-transform ${expandedSpec === key ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
            </button>
            {expandedSpec === key && (
              <div className="border-t border-border-default p-4">
                {/* Weights editor */}
                {isAuthenticated && editingWeights === key ? (
                  <div className="flex items-center gap-2 mb-4 text-sm">
                    <label className="text-text-muted">Parse:</label>
                    <input type="number" value={weights.parse} onChange={e => setWeights({ ...weights, parse: +e.target.value })} className="w-16 px-2 py-1 bg-bg-base border border-border-default rounded text-text-primary text-center" />
                    <label className="text-text-muted">Utility:</label>
                    <input type="number" value={weights.utility} onChange={e => setWeights({ ...weights, utility: +e.target.value })} className="w-16 px-2 py-1 bg-bg-base border border-border-default rounded text-text-primary text-center" />
                    <label className="text-text-muted">Consumes:</label>
                    <input type="number" value={weights.consumables} onChange={e => setWeights({ ...weights, consumables: +e.target.value })} className="w-16 px-2 py-1 bg-bg-base border border-border-default rounded text-text-primary text-center" />
                    <button onClick={() => weightsMutation.mutate({ spec: key, w: { parse_weight: weights.parse / 100, utility_weight: weights.utility / 100, consumables_weight: weights.consumables / 100 } })} className="px-2 py-1 bg-success text-white rounded text-xs cursor-pointer border-none">Save</button>
                    <button onClick={() => setEditingWeights(null)} className="px-2 py-1 bg-bg-hover text-text-secondary rounded text-xs cursor-pointer border-none">Cancel</button>
                  </div>
                ) : isAuthenticated ? (
                  <button onClick={() => { setEditingWeights(key); setWeights({ parse: (spec.parse_weight || 0) * 100, utility: (spec.utility_weight || 0) * 100, consumables: (spec.consumables_weight || 0) * 100 }) }} className="text-xs text-info hover:underline cursor-pointer bg-transparent border-none mb-4 block">Edit weights</button>
                ) : null}

                {/* Contributions */}
                {spec.contributions?.length > 0 ? (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-text-muted uppercase">
                        <th className="pb-2 text-left font-semibold">Metric</th>
                        <th className="pb-2 text-left font-semibold">Type</th>
                        <th className="pb-2 text-right font-semibold">Target</th>
                      </tr>
                    </thead>
                    <tbody>
                      {spec.contributions.map((c: any) => (
                        <tr key={c.metric} className="border-t border-border-default/50">
                          <td className="py-2 text-text-primary">{c.label}</td>
                          <td className="py-2 text-text-muted">{c.type}{c.subtype ? ` (${c.subtype})` : ''}</td>
                          <td className="py-2 text-right">
                            {isAuthenticated && editingTarget?.spec === key && editingTarget?.metric === c.metric ? (
                              <span className="inline-flex items-center gap-1">
                                <input type="number" value={editValue} onChange={e => setEditValue(e.target.value)} className="w-16 px-2 py-0.5 bg-bg-base border border-border-default rounded text-text-primary text-right" autoFocus />
                                <button onClick={() => targetMutation.mutate({ spec: key, metric: c.metric, target: +editValue })} className="px-1.5 py-0.5 bg-success text-white rounded text-xs cursor-pointer border-none">OK</button>
                                <button onClick={() => setEditingTarget(null)} className="px-1.5 py-0.5 bg-bg-hover text-text-secondary rounded text-xs cursor-pointer border-none">X</button>
                              </span>
                            ) : (
                              <span
                                className={`tabular-nums ${isAuthenticated ? 'cursor-pointer hover:text-accent-gold' : ''}`}
                                onClick={isAuthenticated ? () => { setEditingTarget({ spec: key, metric: c.metric }); setEditValue(String(c.target)) } : undefined}
                              >
                                {c.target}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-sm text-text-muted">No contributions configured (pure parse scoring)</p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Consumables */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Consumables</h2>
      <div className="bg-bg-surface border border-border-default rounded-xl p-4 mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-text-muted uppercase">
              <th className="pb-2 text-left font-semibold">Label</th>
              <th className="pb-2 text-left font-semibold">Type</th>
              <th className="pb-2 text-right font-semibold">Target</th>
              <th className="pb-2 text-right font-semibold">Optional</th>
            </tr>
          </thead>
          <tbody>
            {consumables?.map((c: any, i: number) => (
              <tr key={i} className="border-t border-border-default/50">
                <td className="py-2 text-text-primary">{c.label}</td>
                <td className="py-2 text-text-muted">{c.type}</td>
                <td className="py-2 text-right tabular-nums">{c.target}</td>
                <td className="py-2 text-right">{c.optional ? '\u2705' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Attendance Requirements */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Attendance Requirements</h2>
      <div className="bg-bg-surface border border-border-default rounded-xl p-4 mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-text-muted uppercase">
              <th className="pb-2 text-left font-semibold">Zone</th>
              <th className="pb-2 text-right font-semibold">Required / Week</th>
            </tr>
          </thead>
          <tbody>
            {attendanceConfig?.map((z: any) => (
              <tr key={z.zone_id} className="border-t border-border-default/50">
                <td className="py-2 text-text-primary">{z.label}</td>
                <td className="py-2 text-right">
                  {isAuthenticated && editingAttendance === z.zone_id ? (
                    <span className="inline-flex items-center gap-1">
                      <input type="number" value={attendanceValue} onChange={e => setAttendanceValue(+e.target.value)} className="w-16 px-2 py-0.5 bg-bg-base border border-border-default rounded text-text-primary text-right" autoFocus />
                      <button onClick={() => attendanceMutation.mutate({ zoneId: z.zone_id, required: attendanceValue })} className="px-1.5 py-0.5 bg-success text-white rounded text-xs cursor-pointer border-none">OK</button>
                      <button onClick={() => setEditingAttendance(null)} className="px-1.5 py-0.5 bg-bg-hover text-text-secondary rounded text-xs cursor-pointer border-none">X</button>
                    </span>
                  ) : (
                    <span
                      className={`tabular-nums ${isAuthenticated ? 'cursor-pointer hover:text-accent-gold' : ''}`}
                      onClick={isAuthenticated ? () => { setEditingAttendance(z.zone_id); setAttendanceValue(z.required_per_week) } : undefined}
                    >
                      {z.required_per_week}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Gear Check Config */}
      <h2 className="text-lg font-semibold text-text-primary mb-3">Gear Check</h2>
      <div className="bg-bg-surface border border-border-default rounded-xl p-4">
        {gearConfig && (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="text-text-muted">Min Avg iLvl</div>
            <div className="text-text-primary font-medium">{gearConfig.min_avg_ilvl}</div>
            <div className="text-text-muted">Min Quality</div>
            <div className="text-text-primary font-medium">{gearConfig.min_quality}</div>
            <div className="text-text-muted">Check Enchants</div>
            <div className="text-text-primary">{gearConfig.check_enchants ? '\u2705' : '\u274C'}</div>
            <div className="text-text-muted">Check Gems</div>
            <div className="text-text-primary">{gearConfig.check_gems ? '\u2705' : '\u274C'}</div>
          </div>
        )}
      </div>
    </Layout>
  )
}
