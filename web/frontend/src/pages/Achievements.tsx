import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import { useScoreAccess } from '../hooks/useScoreAccess'

const BADGE_ICONS: Record<string, string> = {
  parse_god: '\u{1F451}',
  consistency_king: '\u2B50',
  iron_raider: '\u{1F6E1}\uFE0F',
  flask_master: '\u{1F9EA}',
  most_improved: '\u{1F4C8}',
  deathless: '\u2764\uFE0F',
  utility_star: '\u26A1',
  geared_up: '\u{1F48E}',
}

export default function Achievements() {
  const { canViewScores } = useScoreAccess()

  const { data: achievements, isLoading } = useQuery({
    queryKey: ['achievements'],
    queryFn: () => api.achievements(),
    enabled: canViewScores,
  })

  if (!canViewScores) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20">
          <h1 className="text-xl font-bold text-text-primary mb-2">Officer Access Required</h1>
          <p className="text-sm text-text-secondary">Log in as an officer to view performance data.</p>
        </div>
      </Layout>
    )
  }

  if (isLoading) return <Layout><div className="text-text-muted text-sm">Loading achievements...</div></Layout>

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Achievements</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {achievements?.map((badge: any) => (
          <div key={badge.type} className="bg-bg-surface border border-border-default rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xl">{BADGE_ICONS[badge.type] || '\u{1F3C6}'}</span>
              <div>
                <div className="text-sm font-semibold text-text-primary">{badge.label}</div>
                <div className="text-xs text-text-muted">{badge.description}</div>
              </div>
              <span className="ml-auto text-xs text-accent-gold font-semibold">{badge.count} earned</span>
            </div>
            {badge.recent_earners.length > 0 && (
              <div className="mt-2 space-y-1">
                {badge.recent_earners.map((e: any, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <Link to={`/player/${e.name}`} className="text-text-primary no-underline hover:text-accent-gold">{e.name}</Link>
                    <span className="text-text-muted">{e.details}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </Layout>
  )
}
