import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ParseBar from '../components/ParseBar'
import ClassIcon from '../components/ClassIcon'

export default function RaidDetail() {
  const { code } = useParams<{ code: string }>()
  const { data: report, isLoading } = useQuery({
    queryKey: ['report', code],
    queryFn: () => api.reports.get(code!),
    enabled: !!code,
  })

  if (isLoading) return <Layout><p>Loading...</p></Layout>
  if (!report) return <Layout><p>Report not found</p></Layout>

  return (
    <Layout>
      <h1>{report.zone_name}</h1>
      <p style={{ color: '#8b949e' }}>{new Date(report.start_time).toLocaleDateString()} — {report.player_names?.length} players</p>

      <h2 style={{ marginTop: '1.5rem' }}>Scores</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left' }}>
            <th style={{ padding: '0.5rem' }}>Player</th>
            <th style={{ padding: '0.5rem' }}>Spec</th>
            <th style={{ padding: '0.5rem' }}>Score</th>
            <th style={{ padding: '0.5rem' }}>Parse</th>
          </tr>
        </thead>
        <tbody>
          {report.scores?.map((s, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #21262d' }}>
              <td style={{ padding: '0.5rem' }}>
                <Link to={`/player/${s.player_name}`} style={{ textDecoration: 'none' }}>
                  <ClassIcon className={s.class_name} name={s.player_name} />
                </Link>
              </td>
              <td style={{ padding: '0.5rem', textTransform: 'capitalize' }}>{s.spec?.replace(':', ' ')}</td>
              <td style={{ padding: '0.5rem' }}>{s.overall_score.toFixed(1)}</td>
              <td style={{ padding: '0.5rem' }}><ParseBar percent={s.parse_score} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      {report.consumables && report.consumables.length > 0 && (
        <>
          <h2 style={{ marginTop: '1.5rem' }}>Consumables</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>Player</th>
                <th style={{ padding: '0.5rem' }}>Metric</th>
                <th style={{ padding: '0.5rem' }}>Value</th>
                <th style={{ padding: '0.5rem' }}>Target</th>
              </tr>
            </thead>
            <tbody>
              {report.consumables.filter(c => c.actual_value > 0).map((c, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #21262d' }}>
                  <td style={{ padding: '0.5rem' }}>{c.player_name}</td>
                  <td style={{ padding: '0.5rem' }}>{c.label}{c.optional ? <span style={{ color: '#8b949e' }}> (optional)</span> : ''}</td>
                  <td style={{ padding: '0.5rem' }}>{c.actual_value.toFixed(1)}</td>
                  <td style={{ padding: '0.5rem' }}>{c.target_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Layout>
  )
}
