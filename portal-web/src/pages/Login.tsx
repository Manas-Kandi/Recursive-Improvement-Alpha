import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { apiClient } from '../api'

export default function Login() {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)
  const { login } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setChecking(true)

    try {
      localStorage.setItem('siha_token', token)
      await apiClient.getHarnessState()
      login(token)
    } catch (err: any) {
      localStorage.removeItem('siha_token')
      setError(err.response?.status === 403 ? 'Invalid token' : 'Connection failed')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900">
      <div className="bg-gray-800 rounded-lg p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-white mb-2">SIHA Portal</h1>
        <p className="text-gray-400 text-sm mb-6">Enter your developer token to continue.</p>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Auth Token
            </label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="dev"
              autoFocus
            />
          </div>

          {error && (
            <div className="mb-4 text-sm text-red-400 bg-red-900/20 rounded p-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={checking || !token.trim()}
            className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded font-medium text-white"
          >
            {checking ? 'Verifying...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
