import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import { useScoreAccess } from '../hooks/useScoreAccess'

interface ChecklistPlayer {
  name: string
  class_name: string
  readiness: 'green' | 'yellow' | 'red'
  gear_issues: string[]
  attendance_missed: boolean
  consumables_avg: number | null
}

const READINESS_STYLES = {
  green: 'bg-success/10 border-success/30 text-success',
  yellow: 'bg-warning/10 border-warning/30 text-warning',
  red: 'bg-danger/10 border-danger/30 text-danger',
}

const READINESS_LABEL = { green: 'Ready', yellow: 'Warning', red: 'Not Ready' }

export default function Checklist() {
  const { canViewScores } = useScoreAccess()
  const [filter, setFilter] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const isOfficer = !!localStorage.getItem('auth_token')

  const deactivateMutation = useMutation({
    mutationFn: (name: string) => api.players.deactivate(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['checklist'] }),
  })

  const { data, isLoading } = useQuery({
    queryKey: ['checklist'],
    queryFn: () => api.checklist(),
  })

  const players = data?.players || []
  const filtered = filter ? players.filter((p: ChecklistPlayer) => p.readiness === filter) : players

  const counts = {
    green: players.filter((p: ChecklistPlayer) => p.readiness === 'green').length,
    yellow: players.filter((p: ChecklistPlayer) => p.readiness === 'yellow').length,
    red: players.filter((p: ChecklistPlayer) => p.readiness === 'red').length,
  }

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Pre-Raid Checklist</h1>

      {/* Summary cards */}
      <div className="flex gap-3 mb-6">
        {(['green', 'yellow', 'red'] as const).map(status => (
          <button
            key={status}
            onClick={() => setFilter(filter === status ? null : status)}
            className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all cursor-pointer ${
              filter === status ? READINESS_STYLES[status] : 'bg-bg-surface border-border-default text-text-secondary hover:border-border-hover'
            }`}
          >
            {READINESS_LABEL[status]} ({counts[status]})
          </button>
        ))}
      </div>

      {/* Player list */}
      <div className="space-y-2">
        {isLoading ? (
          <div className="text-text-muted text-sm">Loading checklist...</div>
        ) : (
          filtered.map((p: ChecklistPlayer) => (
            <div
              key={p.name}
              className="bg-bg-surface border border-border-default rounded-xl p-4 flex items-start gap-4"
            >
              <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                p.readiness === 'green' ? 'bg-success' : p.readiness === 'yellow' ? 'bg-warning' : 'bg-danger'
              }`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Link to={`/player/${p.name}`} className="no-underline">
                    <ClassIcon className={p.class_name} name={p.name} />
                  </Link>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  {p.gear_issues.map((issue, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-danger/10 text-danger border border-danger/20">{issue}</span>
                  ))}
                  {p.attendance_missed && (
                    <span className="px-2 py-0.5 rounded bg-danger/10 text-danger border border-danger/20">Missed attendance last week</span>
                  )}
                  {canViewScores && p.consumables_avg !== null && p.consumables_avg < 80 && (
                    <span className="px-2 py-0.5 rounded bg-warning/10 text-warning border border-warning/20">
                      Consumables: {p.consumables_avg}%
                    </span>
                  )}
                  {p.readiness === 'green' && (
                    <span className="px-2 py-0.5 rounded bg-success/10 text-success border border-success/20">All clear</span>
                  )}
                </div>
              </div>
              {isOfficer && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (confirm(`Remove ${p.name} from checklist?`)) deactivateMutation.mutate(p.name)
                  }}
                  className="ml-2 p-1.5 text-text-muted hover:text-danger transition-colors cursor-pointer bg-transparent border-none flex-shrink-0"
                  title={`Remove ${p.name}`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </Layout>
  )
}
