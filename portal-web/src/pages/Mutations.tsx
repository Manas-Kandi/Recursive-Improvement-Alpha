import { useState, useEffect } from 'react'
import { apiClient } from '../api'

interface Mutation {
  id: number
  kind: string
  target_id: number
  before: any
  after: any
  rationale: string
  status: string
  benchmark_delta: number | null
  created_ts: string
  decided_ts: string | null
}

export default function Mutations() {
  const [mutations, setMutations] = useState<Mutation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadMutations()
  }, [])

  const loadMutations = async () => {
    try {
      const response = await apiClient.getMutations()
      setMutations(response.data)
    } catch (error) {
      console.error('Failed to load mutations:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (id: number) => {
    try {
      await apiClient.approveMutation(id)
      loadMutations()
    } catch (error) {
      console.error('Failed to approve mutation:', error)
    }
  }

  const handleReject = async (id: number) => {
    try {
      await apiClient.rejectMutation(id)
      loadMutations()
    } catch (error) {
      console.error('Failed to reject mutation:', error)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-600'
      case 'pending': return 'bg-yellow-600'
      case 'rejected': return 'bg-red-600'
      case 'reverted': return 'bg-gray-600'
      default: return 'bg-gray-600'
    }
  }

  if (loading) {
    return <div className="text-gray-400">Loading mutations...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Mutations</h2>
      
      <div className="space-y-4">
        {mutations.map((mutation) => (
          <div key={mutation.id} className="bg-gray-800 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-sm font-medium text-blue-400">{mutation.kind}</span>
                <span className="text-xs text-gray-400 ml-2">Target: {mutation.target_id}</span>
              </div>
              <span className={`px-2 py-1 rounded text-xs ${getStatusColor(mutation.status)}`}>
                {mutation.status}
              </span>
            </div>
            
            <p className="text-sm text-gray-300 mb-4">{mutation.rationale}</p>
            
            {mutation.benchmark_delta !== null && (
              <p className={`text-sm mb-4 ${mutation.benchmark_delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                Benchmark Delta: {mutation.benchmark_delta >= 0 ? '+' : ''}{mutation.benchmark_delta.toFixed(3)}
              </p>
            )}
            
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <h4 className="text-xs font-medium text-gray-400 mb-2">Before</h4>
                <pre className="text-xs text-gray-300 bg-gray-700 rounded p-2 overflow-auto max-h-32">
                  {JSON.stringify(mutation.before, null, 2)}
                </pre>
              </div>
              <div>
                <h4 className="text-xs font-medium text-gray-400 mb-2">After</h4>
                <pre className="text-xs text-gray-300 bg-gray-700 rounded p-2 overflow-auto max-h-32">
                  {JSON.stringify(mutation.after, null, 2)}
                </pre>
              </div>
            </div>
            
            {mutation.status === 'pending' && (
              <div className="flex space-x-2">
                <button
                  onClick={() => handleApprove(mutation.id)}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-sm"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleReject(mutation.id)}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded text-sm"
                >
                  Reject
                </button>
              </div>
            )}
            
            <p className="text-xs text-gray-500 mt-4">
              Created: {new Date(mutation.created_ts).toLocaleString()}
              {mutation.decided_ts && ` • Decided: ${new Date(mutation.decided_ts).toLocaleString()}`}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
