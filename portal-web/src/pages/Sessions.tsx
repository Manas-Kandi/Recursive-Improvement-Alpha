import { useState, useEffect } from 'react'
import { apiClient } from '../api'
import type { SessionItem, SessionDetail } from '../types'

export default function Sessions() {
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      const response = await apiClient.getSessions()
      setSessions(response.data)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadSessionDetail = async (id: number) => {
    try {
      const response = await apiClient.getSession(id)
      setSelectedSession(response.data)
    } catch (error) {
      console.error('Failed to load session detail:', error)
    }
  }

  if (loading) {
    return <div className="text-gray-400">Loading sessions...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Sessions</h2>
      
      {selectedSession ? (
        <div>
          <button
            onClick={() => setSelectedSession(null)}
            className="mb-4 text-blue-400 hover:text-blue-300"
          >
            ← Back to sessions
          </button>
          
          <div className="bg-gray-800 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-semibold mb-2">Task</h3>
            <p className="text-gray-300 mb-2"><strong>Prompt:</strong> {selectedSession.task.prompt}</p>
            <p className="text-gray-300 mb-2"><strong>Model:</strong> {selectedSession.task.model}</p>
            <p className="text-gray-300 mb-2"><strong>Status:</strong> {selectedSession.task.status}</p>
            <p className="text-gray-300 mb-2"><strong>Duration:</strong> {selectedSession.task.duration_ms}ms</p>
          </div>

          <div className="bg-gray-800 rounded-lg p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Steps ({selectedSession.steps.length})</h3>
            <div className="space-y-2">
              {selectedSession.steps.map((step) => (
                <div key={step.id} className="bg-gray-700 rounded p-3">
                  <span className="text-sm text-gray-400">Step {step.idx}</span>
                  <span className="ml-2 text-sm bg-blue-600 px-2 py-1 rounded">{step.type}</span>
                  <pre className="mt-2 text-xs text-gray-300 overflow-auto">{JSON.stringify(step.content, null, 2)}</pre>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Tool Calls ({selectedSession.tool_calls.length})</h3>
            <div className="space-y-2">
              {selectedSession.tool_calls.map((tc) => (
                <div key={tc.id} className="bg-gray-700 rounded p-3">
                  <span className="text-sm text-gray-400">Tool ID: {tc.tool_id}</span>
                  <span className={`ml-2 text-sm px-2 py-1 rounded ${tc.success ? 'bg-green-600' : 'bg-red-600'}`}>
                    {tc.success ? 'Success' : 'Failed'}
                  </span>
                  <pre className="mt-2 text-xs text-gray-300 overflow-auto">Args: {JSON.stringify(tc.args, null, 2)}</pre>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="min-w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Prompt</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Model</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Duration</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {sessions.map((session) => (
                <tr
                  key={session.id}
                  className="hover:bg-gray-700 cursor-pointer"
                  onClick={() => loadSessionDetail(session.id)}
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{session.id}</td>
                  <td className="px-6 py-4 text-sm text-gray-300 max-w-xs truncate">{session.prompt}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{session.model}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-1 rounded ${session.status === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>
                      {session.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{session.duration_ms}ms</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{new Date(session.ts).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
