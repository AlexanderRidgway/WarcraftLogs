import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'never'
  const now = Date.now()
  const then = new Date(dateStr + 'Z').getTime()
  const seconds = Math.floor((now - then) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const { data: syncStatus } = useQuery({
    queryKey: ['sync-status'],
    queryFn: api.sync.status,
    refetchInterval: 15000,
  })

  const syncMutation = useMutation({
    mutationFn: api.sync.trigger,
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['sync-status'] }), 2000)
    },
  })

  const reportsSync = syncStatus?.find(s => s.sync_type === 'reports')
  const lastSynced = reportsSync?.last_run_at

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '1rem', fontFamily: 'system-ui, sans-serif', color: '#e0e0e0', background: '#0d1117', minHeight: '100vh' }}>
      <nav style={{ display: 'flex', gap: '1.5rem', marginBottom: '0.5rem', borderBottom: '1px solid #30363d', paddingBottom: '0.75rem', alignItems: 'center' }}>
        <Link to="/" style={{ color: '#58a6ff', textDecoration: 'none', fontWeight: 'bold' }}>Home</Link>
        <Link to="/raids" style={{ color: '#58a6ff', textDecoration: 'none' }}>Raids</Link>
        <Link to="/attendance" style={{ color: '#58a6ff', textDecoration: 'none' }}>Attendance</Link>
        <Link to="/config" style={{ color: '#58a6ff', textDecoration: 'none' }}>Config</Link>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: 13 }}>
          <span style={{ color: '#8b949e' }}>
            Last synced: {timeAgo(lastSynced ?? null)}
          </span>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            style={{
              padding: '4px 12px',
              background: syncMutation.isPending ? '#21262d' : '#238636',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: syncMutation.isPending ? 'not-allowed' : 'pointer',
              fontSize: 13,
            }}
          >
            {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </nav>
      {children}
    </div>
  )
}
