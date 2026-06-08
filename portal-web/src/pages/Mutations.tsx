import { useState, useEffect } from 'react'
import { apiClient } from '../api'
import type { MutationItem } from '../types'

export default function Mutations() {
  const [mutations, setMutations] = useState<MutationItem[]>([])
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
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

  const toggleExpand = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-600'
      case 'promoted': return 'bg-emerald-600'
      case 'candidate': return 'bg-blue-600'
      case 'evaluating': return 'bg-purple-600'
      case 'proposed': return 'bg-yellow-600'
      case 'pending': return 'bg-yellow-600'
      case 'rejected': return 'bg-red-600'
      case 'rolled_back': return 'bg-orange-600'
      case 'reverted': return 'bg-gray-600'
      default: return 'bg-gray-600'
    }
  }

  const isActionable = (status: string) =>
    status === 'proposed' || status === 'pending'

  if (loading) {
    return <div className="text-gray-400">Loading mutations...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Mutations</h2>

      <div className="space-y-4">
        {mutations.map((mutation) => {
          const isOpen = expanded.has(mutation.id)
          return (
            <div key={mutation.id} className="bg-gray-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <span className="text-sm font-medium text-blue-400">{mutation.kind}</span>
                  <span className="text-xs text-gray-400">Target: {mutation.target_id}</span>
                  <button
                    onClick={() => toggleExpand(mutation.id)}
                    className="text-xs text-gray-400 hover:text-white underline"
                  >
                    {isOpen ? 'Collapse' : 'View Diff'}
                  </button>
                </div>
                <span className={`px-2 py-1 rounded text-xs ${getStatusColor(mutation.status)}`}>
                  {mutation.status}
                </span>
              </div>

              <p className="text-sm text-gray-300 mb-2">{mutation.rationale}</p>

              {mutation.benchmark_delta !== null && (
                <p className={`text-sm mb-2 ${mutation.benchmark_delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  Benchmark Delta: {mutation.benchmark_delta >= 0 ? '+' : ''}{mutation.benchmark_delta.toFixed(3)}
                </p>
              )}

              {isOpen && <DiffViewer before={mutation.before} after={mutation.after} />}

              {isActionable(mutation.status) && (
                <div className="flex space-x-2 mt-4">
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
          )
        })}
      </div>
    </div>
  )
}

function DiffViewer({ before, after }: { before: unknown; after: unknown }) {
  const beforeStr = JSON.stringify(before, null, 2)
  const afterStr = JSON.stringify(after, null, 2)
  const hasDiff = beforeStr !== afterStr

  return (
    <div className="grid grid-cols-2 gap-4 mt-4 mb-4">
      <div>
        <h4 className="text-xs font-medium text-red-400 mb-2">Before</h4>
        <pre className="text-xs text-gray-300 bg-gray-900 rounded p-3 overflow-auto max-h-48 border border-red-900/30">
          {beforeStr}
        </pre>
      </div>
      <div>
        <h4 className="text-xs font-medium text-green-400 mb-2">After</h4>
        <pre className="text-xs text-gray-300 bg-gray-900 rounded p-3 overflow-auto max-h-48 border border-green-900/30">
          {afterStr}
        </pre>
      </div>
      {!hasDiff && (
        <div className="col-span-2 text-xs text-yellow-400 bg-yellow-900/20 rounded p-2">
          No structural difference detected.
        </div>
      )}
    </div>
  )
}
