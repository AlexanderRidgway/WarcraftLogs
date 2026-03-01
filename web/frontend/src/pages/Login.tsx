import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-base">
      <div className="w-full max-w-sm p-8 bg-bg-surface border border-border-default rounded-xl">
        <div className="flex items-center justify-center gap-3 mb-8">
          <img src="/favicon.jpg" alt="CRANK" className="w-10 h-10 rounded" />
          <h1 className="text-2xl font-bold text-text-primary">CRANK</h1>
        </div>
        <h2 className="text-lg font-semibold text-text-primary mb-6 text-center">Officer Login</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full px-3 py-2 bg-bg-base border border-border-default rounded-lg text-text-primary focus:outline-none focus:border-accent-gold transition-colors"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-bg-base border border-border-default rounded-lg text-text-primary focus:outline-none focus:border-accent-gold transition-colors"
              required
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-accent-gold text-bg-base font-semibold rounded-lg hover:bg-accent-gold-light disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        <div className="mt-4 text-center">
          <Link to="/forgot-password" className="text-sm text-text-muted hover:text-accent-gold no-underline transition-colors">
            Forgot Password?
          </Link>
        </div>
      </div>
    </div>
  )
}
