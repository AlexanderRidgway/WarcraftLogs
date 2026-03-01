import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      await api.auth.resetPassword(token, password)
      setSuccess(true)
    } catch (err: any) {
      setError(err.message || 'Failed to reset password')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-base">
        <div className="w-full max-w-sm p-8 bg-bg-surface border border-border-default rounded-xl text-center">
          <p className="text-sm text-danger mb-4">Invalid reset link. No token provided.</p>
          <Link to="/forgot-password" className="text-sm text-accent-gold hover:text-accent-gold-light no-underline transition-colors">
            Request a new reset link
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-base">
      <div className="w-full max-w-sm p-8 bg-bg-surface border border-border-default rounded-xl">
        <div className="flex items-center justify-center gap-3 mb-8">
          <img src="/favicon.jpg" alt="CRANK" className="w-10 h-10 rounded" />
          <h1 className="text-2xl font-bold text-text-primary">CRANK</h1>
        </div>
        <h2 className="text-lg font-semibold text-text-primary mb-6 text-center">Set New Password</h2>

        {success ? (
          <div className="text-center">
            <p className="text-sm text-success mb-4">Your password has been reset successfully.</p>
            <Link to="/login" className="text-sm text-accent-gold hover:text-accent-gold-light no-underline transition-colors">
              Sign In
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">New Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2 bg-bg-base border border-border-default rounded-lg text-text-primary focus:outline-none focus:border-accent-gold transition-colors"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
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
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
