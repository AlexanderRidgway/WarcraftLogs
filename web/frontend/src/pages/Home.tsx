import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'

export default function Home() {
  const [search, setSearch] = useState('')
  const [weeks, setWeeks] = useState(4)
  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ['leaderboard', weeks],
    queryFn: () => api.leaderboard(weeks),
  })

  const filtered = leaderboard?.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <Layout>
      <h1 style={{ marginBottom: '1rem' }}>CRANK Guild Dashboard</h1>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search player..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ padding: '0.5rem', flex: 1, background: '#161b22', border: '1px solid #30363d', borderRadius: 4, color: '#e0e0e0' }}
        />
        <select value={weeks} onChange={e => setWeeks(Number(e.target.value))} style={{ padding: '0.5rem', background: '#161b22', border: '1px solid #30363d', borderRadius: 4, color: '#e0e0e0' }}>
          <option value={2}>2 weeks</option>
          <option value={4}>4 weeks</option>
          <option value={8}>8 weeks</option>
        </select>
      </div>

      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left' }}>
              <th style={{ padding: '0.5rem' }}>Rank</th>
              <th style={{ padding: '0.5rem' }}>Player</th>
              <th style={{ padding: '0.5rem' }}>Class</th>
              <th style={{ padding: '0.5rem' }}>Score</th>
              <th style={{ padding: '0.5rem' }}>Avg Parse</th>
              <th style={{ padding: '0.5rem' }}>Fights</th>
            </tr>
          </thead>
          <tbody>
            {filtered?.map(entry => (
              <tr key={entry.name} style={{ borderBottom: '1px solid #21262d' }}>
                <td style={{ padding: '0.5rem' }}>{entry.rank}</td>
                <td style={{ padding: '0.5rem' }}>
                  <Link to={`/player/${entry.name}`} style={{ textDecoration: 'none' }}>
                    <ClassIcon className={entry.class_name} name={entry.name} />
                  </Link>
                </td>
                <td style={{ padding: '0.5rem', textTransform: 'capitalize' }}>{entry.class_name}</td>
                <td style={{ padding: '0.5rem' }}>{entry.avg_score}</td>
                <td style={{ padding: '0.5rem' }}>{entry.avg_parse}</td>
                <td style={{ padding: '0.5rem' }}>{entry.fight_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Layout>
  )
}
