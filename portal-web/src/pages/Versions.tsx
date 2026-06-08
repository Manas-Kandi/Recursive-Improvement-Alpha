import { useState, useEffect } from 'react'
import { apiClient } from '../api'
import type { HarnessVersionItem, VersionDiffResponse } from '../types'

export default function Versions() {
  const [versions, setVersions] = useState<HarnessVersionItem[]>([])
  const [selectedA, setSelectedA] = useState<number | null>(null)
  const [selectedB, setSelectedB] = useState<number | null>(null)
  const [diff, setDiff] = useState<VersionDiffResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [diffLoading, setDiffLoading] = useState(false)

  useEffect(() => {
    loadVersions()
  }, [])

  const loadVersions = async () => {
    try {
      const res = await apiClient.getHarnessVersions()
      setVersions(res.data)
    } catch (error) {
      console.error('Failed to load versions:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadDiff = async () => {
    if (selectedA == null || selectedB == null) return
    setDiffLoading(true)
    try {
      const res = await apiClient.diffVersions(selectedA, selectedB)
      setDiff(res.data)
    } catch (error) {
      console.error('Failed to load diff:', error)
    } finally {
      setDiffLoading(false)
    }
  }

  if (loading) {
    return <div className="text-gray-400">Loading versions...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Harness Versions</h2>

      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Compare Versions</h3>
        <div className="flex items-end space-x-4">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-1">Version A</label>
            <select
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
              value={selectedA ?? ''}
              onChange={(e) => { setSelectedA(Number(e.target.value) || null); setDiff(null) }}
            >
              <option value="">Select...</option>
              {versions.map((v) => (
                <option key={`a-${v.id}`} value={v.id}>{v.label} ({v.ts})</option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-1">Version B</label>
            <select
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
              value={selectedB ?? ''}
              onChange={(e) => { setSelectedB(Number(e.target.value) || null); setDiff(null) }}
            >
              <option value="">Select...</option>
              {versions.map((v) => (
                <option key={`b-${v.id}`} value={v.id}>{v.label} ({v.ts})</option>
              ))}
            </select>
          </div>
          <button
            onClick={loadDiff}
            disabled={selectedA == null || selectedB == null || diffLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded text-sm font-medium"
          >
            {diffLoading ? 'Loading...' : 'Compare'}
          </button>
        </div>

        {diff && (
          <div className="mt-6 grid grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-semibold text-blue-400 mb-2">{diff.version_a.label}</h4>
              <DiffSet prompts={diff.version_a.prompts} tools={diff.version_a.tools} strategies={diff.version_a.strategies} />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-green-400 mb-2">{diff.version_b.label}</h4>
              <DiffSet prompts={diff.version_b.prompts} tools={diff.version_b.tools} strategies={diff.version_b.strategies} />
            </div>
          </div>
        )}
      </div>

      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="min-w-full">
          <thead className="bg-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Label</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Prompts</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Tools</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Strategies</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {versions.map((v) => (
              <tr key={v.id} className="hover:bg-gray-700">
                <td className="px-6 py-4 text-sm text-gray-300">{v.id}</td>
                <td className="px-6 py-4 text-sm font-medium text-white">{v.label}</td>
                <td className="px-6 py-4 text-sm text-gray-300">{v.prompt_count}</td>
                <td className="px-6 py-4 text-sm text-gray-300">{v.tool_count}</td>
                <td className="px-6 py-4 text-sm text-gray-300">{v.strategy_count}</td>
                <td className="px-6 py-4 text-sm text-gray-300">{new Date(v.ts).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DiffSet({ prompts, tools, strategies }: { prompts: number[]; tools: number[]; strategies: number[] }) {
  return (
    <div className="space-y-3 text-sm">
      <div>
        <span className="text-gray-400">Prompts:</span>{' '}
        <span className="text-gray-200">{prompts.length > 0 ? prompts.join(', ') : 'none'}</span>
      </div>
      <div>
        <span className="text-gray-400">Tools:</span>{' '}
        <span className="text-gray-200">{tools.length > 0 ? tools.join(', ') : 'none'}</span>
      </div>
      <div>
        <span className="text-gray-400">Strategies:</span>{' '}
        <span className="text-gray-200">{strategies.length > 0 ? strategies.join(', ') : 'none'}</span>
      </div>
    </div>
  )
}
