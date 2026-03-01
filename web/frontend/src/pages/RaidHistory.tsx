import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'

export default function RaidHistory() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.reports.list(),
  })

  return (
    <Layout>
      <h1 style={{ marginBottom: '1rem' }}>Raid History</h1>
      {isLoading ? <p>Loading...</p> : (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {reports?.map(r => (
            <Link
              key={r.code}
              to={`/raids/${r.code}`}
              style={{
                padding: '1rem',
                background: '#161b22',
                borderRadius: 8,
                textDecoration: 'none',
                color: 'inherit',
                border: '1px solid #30363d',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <strong>{r.zone_name}</strong>
              <span style={{ color: '#8b949e', fontSize: 14 }}>
                {new Date(r.start_time).toLocaleDateString()} — {r.player_count} players
              </span>
            </Link>
          ))}
          {reports?.length === 0 && <p style={{ color: '#8b949e' }}>No raids synced yet.</p>}
        </div>
      )}
    </Layout>
  )
}
