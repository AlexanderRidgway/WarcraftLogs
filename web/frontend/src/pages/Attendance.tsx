import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'

export default function Attendance() {
  const [weeks, setWeeks] = useState(4)
  const { data, isLoading } = useQuery({
    queryKey: ['guild-attendance', weeks],
    queryFn: () => api.attendance(weeks),
  })

  return (
    <Layout>
      <h1 style={{ marginBottom: '1rem' }}>Guild Attendance</h1>
      <select value={weeks} onChange={e => setWeeks(Number(e.target.value))} style={{ padding: '0.5rem', background: '#161b22', border: '1px solid #30363d', borderRadius: 4, color: '#e0e0e0', marginBottom: '1rem' }}>
        <option value={2}>2 weeks</option>
        <option value={4}>4 weeks</option>
        <option value={8}>8 weeks</option>
      </select>

      {isLoading ? <p>Loading...</p> : (
        <div>
          {data?.map(player => (
            <div key={player.name} style={{ marginBottom: '0.5rem', padding: '0.75rem', background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
              <ClassIcon className={player.class_name} name={player.name} />
              <div style={{ marginTop: '0.25rem' }}>
                {player.weeks.map((w, i) => (
                  <span key={i} style={{ marginRight: '0.75rem', fontSize: 13 }}>
                    {w.met ? '✅' : '❌'} {w.zone_label}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {data?.length === 0 && <p style={{ color: '#8b949e' }}>No attendance data synced yet.</p>}
        </div>
      )}
    </Layout>
  )
}
