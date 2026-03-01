import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from './Sidebar'

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
  const { isAuthenticated } = useAuth()

  const { data: syncStatus } = useQuery({
    queryKey: ['sync-status'],
    queryFn: api.sync.status,
    refetchInterval: 15000,
  })

  const syncMutation = useMutation({
    mutationFn: () => api.sync.trigger(false),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['sync-status'] }), 2000)
    },
  })

  const fullResyncMutation = useMutation({
    mutationFn: () => api.sync.trigger(true),
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['sync-status'] }), 2000)
    },
  })

  const isSyncing = syncMutation.isPending || fullResyncMutation.isPending
  const reportsSync = syncStatus?.find(s => s.sync_type === 'reports')
  const lastSynced = reportsSync?.last_run_at

  return (
    <div className="min-h-screen bg-bg-base">
      <Sidebar />

      {/* Main content */}
      <main className="lg:ml-[240px] min-h-screen">
        {/* Top bar */}
        <div className="sticky top-0 z-30 bg-bg-base/80 backdrop-blur-md border-b border-border-default px-6 py-3 flex items-center justify-between">
          <div />
          <div className="flex items-center gap-4 text-sm">
            <span className="text-text-muted">
              Synced {timeAgo(lastSynced ?? null)}
            </span>
            {isAuthenticated && (
              <>
                <button
                  onClick={() => syncMutation.mutate()}
                  disabled={isSyncing}
                  className="px-3 py-1.5 bg-success/20 text-success border border-success/30 rounded-lg text-xs font-medium hover:bg-success/30 disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
                >
                  {isSyncing ? 'Syncing...' : 'Sync Now'}
                </button>
                <button
                  onClick={() => { if (confirm('This will re-fetch and re-process all reports. Continue?')) fullResyncMutation.mutate() }}
                  disabled={isSyncing}
                  className="px-3 py-1.5 bg-danger/20 text-danger border border-danger/30 rounded-lg text-xs font-medium hover:bg-danger/30 disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
                >
                  Full Resync
                </button>
              </>
            )}
          </div>
        </div>

        {/* Page content */}
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
