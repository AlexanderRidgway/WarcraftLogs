import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import { SkeletonCard } from '../components/Skeleton'

export default function Attendance() {
  const [weeks, setWeeks] = useState(4)
  const { data: attendance, isLoading } = useQuery({
    queryKey: ['attendance', weeks],
    queryFn: () => api.attendance(weeks),
  })

  const WEEK_OPTIONS = [2, 4, 8]

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">Guild Attendance</h1>
        <div className="flex rounded-lg border border-border-default overflow-hidden">
          {WEEK_OPTIONS.map(w => (
            <button
              key={w}
              onClick={() => setWeeks(w)}
              className={`px-4 py-2 text-sm font-medium transition-colors cursor-pointer border-none ${
                weeks === w
                  ? 'bg-accent-gold text-bg-base'
                  : 'bg-bg-surface text-text-secondary hover:text-text-primary'
              }`}
            >
              {w}w
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <div className="space-y-3">
          {attendance?.map((player, i) => (
            <div key={i} className="bg-bg-surface border border-border-default rounded-xl p-4 hover:border-border-hover transition-colors">
              <div className="mb-3">
                <Link to={`/player/${player.name}`} className="no-underline">
                  <ClassIcon className={player.class_name} name={player.name} />
                </Link>
              </div>
              <div className="flex flex-wrap gap-2">
                {player.weeks.map((w, j) => (
                  <span
                    key={j}
                    className={`text-xs px-2.5 py-1 rounded-lg border ${
                      w.met
                        ? 'border-success/30 bg-success/10 text-success'
                        : 'border-danger/30 bg-danger/10 text-danger'
                    }`}
                  >
                    {w.met ? '\u2705' : '\u274C'} W{w.week} {w.zone_label}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
