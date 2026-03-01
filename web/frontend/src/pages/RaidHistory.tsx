import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import { SkeletonCard } from '../components/Skeleton'

export default function RaidHistory() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: api.reports.list,
  })

  return (
    <Layout>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Raid History</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
          : reports?.map(r => (
              <Link
                key={r.code}
                to={`/raids/${r.code}`}
                className="no-underline group"
              >
                <div className="bg-bg-surface border border-border-default rounded-xl p-5 transition-all duration-200 group-hover:-translate-y-1 group-hover:shadow-xl group-hover:shadow-accent-gold/5 group-hover:border-accent-gold/30">
                  <div className="font-semibold text-text-primary group-hover:text-accent-gold transition-colors">
                    {r.zone_name}
                  </div>
                  <div className="text-sm text-text-secondary mt-1">
                    {new Date(r.start_time).toLocaleDateString()}
                  </div>
                  <div className="flex items-center gap-2 mt-3">
                    <span className="text-xs px-2 py-0.5 bg-bg-hover rounded-full text-text-muted">
                      {r.player_count} players
                    </span>
                    <span className="text-xs text-text-muted font-mono">{r.code}</span>
                  </div>
                </div>
              </Link>
            ))}
      </div>
    </Layout>
  )
}
