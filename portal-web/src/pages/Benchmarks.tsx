import { useState, useEffect } from 'react'
import { apiClient } from '../api'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { BenchmarkItem, BenchmarkTrend, BenchmarkRunResult } from '../types'

export default function Benchmarks() {
  const [benchmarks, setBenchmarks] = useState<BenchmarkItem[]>([])
  const [trend, setTrend] = useState<BenchmarkTrend | null>(null)
  const [runResults, setRunResults] = useState<BenchmarkRunResult[] | null>(null)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [benchmarksRes, trendRes] = await Promise.all([
        apiClient.getBenchmarks(),
        apiClient.getBenchmarkTrend()
      ])
      setBenchmarks(benchmarksRes.data)
      setTrend(trendRes.data)
    } catch (error) {
      console.error('Failed to load benchmarks:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRunAll = async () => {
    setRunning(true)
    setRunResults(null)
    try {
      const res = await apiClient.runAllBenchmarks()
      setRunResults(res.data.results)
    } catch (error) {
      console.error('Failed to run benchmarks:', error)
    } finally {
      setRunning(false)
    }
  }

  if (loading) {
    return <div className="text-gray-400">Loading benchmarks...</div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Benchmarks</h2>
        <button
          onClick={handleRunAll}
          disabled={running}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded text-sm font-medium"
        >
          {running ? 'Running...' : 'Run All'}
        </button>
      </div>

      {runResults && (
        <div className="bg-gray-800 rounded-lg p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Latest Run Results</h3>
          <div className="space-y-2">
            {runResults.map((r) => (
              <div key={r.name} className="flex items-center justify-between bg-gray-700 rounded p-3">
                <span className="text-sm text-gray-200">{r.name}</span>
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-gray-300">{r.score.toFixed(2)}</span>
                  <span className={`px-2 py-1 rounded text-xs ${r.passed ? 'bg-green-600' : 'bg-red-600'}`}>
                    {r.passed ? 'PASS' : 'FAIL'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {trend && trend.trend.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Benchmark Trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trend.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="label"
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
              />
              <YAxis
                stroke="#9CA3AF"
                tick={{ fill: '#9CA3AF' }}
                domain={[0, 1]}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: 'none' }}
                itemStyle={{ color: '#E5E7EB' }}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={{ fill: '#3B82F6' }}
              />
            </LineChart>
          </ResponsiveContainer>
          <p className="text-xs text-gray-400 mt-2">Across {trend.total_versions} versions</p>
        </div>
      )}

      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="min-w-full">
          <thead className="bg-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Category</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Origin</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {benchmarks.map((benchmark) => (
              <tr key={benchmark.id} className="hover:bg-gray-700">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{benchmark.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{benchmark.category}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  <span className={`px-2 py-1 rounded ${benchmark.origin === 'seed' ? 'bg-blue-600' : 'bg-purple-600'}`}>
                    {benchmark.origin}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                  {new Date(benchmark.created_ts).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
