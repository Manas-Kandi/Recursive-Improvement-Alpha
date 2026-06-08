import { useState, useEffect } from 'react'
import { apiClient } from '../api'

interface HealthState {
  harness: 'ok' | 'error' | 'loading'
  api: 'ok' | 'error' | 'loading'
  token: string | null
}

export default function Health() {
  const [health, setHealth] = useState<HealthState>({
    harness: 'loading',
    api: 'loading',
    token: localStorage.getItem('siha_token'),
  })

  useEffect(() => {
    checkHealth()
  }, [])

  const checkHealth = async () => {
    setHealth((h) => ({ ...h, harness: 'loading', api: 'loading' }))

    try {
      await apiClient.getHarnessState()
      setHealth((h) => ({ ...h, api: 'ok', harness: 'ok' }))
    } catch {
      setHealth((h) => ({ ...h, api: 'error', harness: 'error' }))
    }
  }

  const clearToken = () => {
    localStorage.removeItem('siha_token')
    setHealth((h) => ({ ...h, token: null }))
    window.location.reload()
  }

  const StatusBadge = ({ status }: { status: string }) => {
    const color =
      status === 'ok'
        ? 'bg-green-600 text-green-100'
        : status === 'error'
          ? 'bg-red-600 text-red-100'
          : 'bg-yellow-600 text-yellow-100'
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${color}`}>
        {status.toUpperCase()}
      </span>
    )
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">System Health</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">API Connectivity</h3>
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-300">Backend</span>
            <StatusBadge status={health.api} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-300">Harness State</span>
            <StatusBadge status={health.harness} />
          </div>
          <button
            onClick={checkHealth}
            className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm"
          >
            Refresh Check
          </button>
        </div>

        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Authentication</h3>
          <div className="mb-2">
            <span className="text-gray-400 text-sm">Stored Token</span>
            <p className="text-gray-200 font-mono text-sm mt-1">
              {health.token ? `${health.token.slice(0, 8)}...` : 'None'}
            </p>
          </div>
          <button
            onClick={clearToken}
            className="mt-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded text-sm"
          >
            Clear Token
          </button>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Endpoints</h3>
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-300">Backend API</span>
            <span className="text-gray-400 font-mono">http://localhost:8000</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-300">Frontend</span>
            <span className="text-gray-400 font-mono">http://localhost:3000</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-300">SSE Stream</span>
            <span className="text-gray-400 font-mono">/stream/logs</span>
          </div>
        </div>
      </div>
    </div>
  )
}
