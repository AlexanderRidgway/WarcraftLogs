import { Link } from 'react-router-dom'

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '1rem', fontFamily: 'system-ui, sans-serif', color: '#e0e0e0', background: '#0d1117', minHeight: '100vh' }}>
      <nav style={{ display: 'flex', gap: '1.5rem', marginBottom: '2rem', borderBottom: '1px solid #30363d', paddingBottom: '0.75rem' }}>
        <Link to="/" style={{ color: '#58a6ff', textDecoration: 'none', fontWeight: 'bold' }}>Home</Link>
        <Link to="/raids" style={{ color: '#58a6ff', textDecoration: 'none' }}>Raids</Link>
        <Link to="/attendance" style={{ color: '#58a6ff', textDecoration: 'none' }}>Attendance</Link>
        <Link to="/config" style={{ color: '#58a6ff', textDecoration: 'none' }}>Config</Link>
      </nav>
      {children}
    </div>
  )
}
