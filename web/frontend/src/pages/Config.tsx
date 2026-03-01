import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'

export default function Config() {
  const { data: specs } = useQuery({ queryKey: ['config-specs'], queryFn: api.config.specs })
  const { data: consumables } = useQuery({ queryKey: ['config-consumables'], queryFn: api.config.consumables })
  const { data: attendance } = useQuery({ queryKey: ['config-attendance'], queryFn: api.config.attendance })
  const { data: gear } = useQuery({ queryKey: ['config-gear'], queryFn: api.config.gear })

  return (
    <Layout>
      <h1 style={{ marginBottom: '1.5rem' }}>Configuration Reference</h1>

      <h2>Spec Profiles</h2>
      <div style={{ display: 'grid', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {specs && Object.entries(specs).map(([key, profile]: [string, any]) => (
          <div key={key} style={{ padding: '0.75rem', background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
            <strong style={{ textTransform: 'capitalize' }}>{key.replace(':', ' — ')}</strong>
            <span style={{ marginLeft: '1rem', fontSize: 12, color: '#8b949e' }}>
              parse: {(profile.parse_weight * 100).toFixed(0)}% | utility: {(profile.utility_weight * 100).toFixed(0)}% | consumables: {((profile.consumables_weight || 0) * 100).toFixed(0)}%
            </span>
            {profile.contributions?.map((c: any) => (
              <div key={c.metric} style={{ fontSize: 13, marginLeft: '1rem', color: '#8b949e' }}>
                {c.label} — target: {c.target} ({c.type})
              </div>
            ))}
          </div>
        ))}
      </div>

      <h2>Consumables</h2>
      <div style={{ marginBottom: '1.5rem' }}>
        {consumables?.map((c: any) => (
          <div key={c.metric} style={{ fontSize: 14, padding: '0.25rem 0' }}>
            {c.label} — target: {c.target} {c.optional ? <span style={{ color: '#8b949e' }}>(optional)</span> : ''}
          </div>
        ))}
      </div>

      <h2>Attendance Requirements</h2>
      <div style={{ marginBottom: '1.5rem' }}>
        {attendance?.map((a: any) => (
          <div key={a.zone_id} style={{ fontSize: 14, padding: '0.25rem 0' }}>
            {a.label} — {a.required_per_week}x per week
          </div>
        ))}
      </div>

      <h2>Gear Check</h2>
      {gear && (
        <pre style={{ background: '#161b22', padding: '1rem', borderRadius: 8, fontSize: 13, border: '1px solid #30363d', overflow: 'auto' }}>
          {JSON.stringify(gear, null, 2)}
        </pre>
      )}
    </Layout>
  )
}
