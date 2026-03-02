import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.auth.forgotPassword(email)
      setSubmitted(true)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      setError(msg || 'Something went wrong. Please try again.')
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
        <h2 className="text-lg font-semibold text-text-primary mb-6 text-center">Reset Password</h2>

        {submitted ? (
          <div className="text-center">
            <p className="text-sm text-text-secondary mb-4">
              If that email is registered, you'll receive a password reset link shortly.
            </p>
            <Link to="/login" className="text-sm text-accent-gold hover:text-accent-gold-light no-underline transition-colors">
              Back to Login
            </Link>
          </div>
        ) : (
          <>
            <p className="text-sm text-text-secondary mb-4 text-center">
              Enter your email and we'll send you a link to reset your password.
            </p>
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
              {error && <p className="text-sm text-danger">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 bg-accent-gold text-bg-base font-semibold rounded-lg hover:bg-accent-gold-light disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </form>
            <div className="mt-4 text-center">
              <Link to="/login" className="text-sm text-text-muted hover:text-accent-gold no-underline transition-colors">
                Back to Login
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
