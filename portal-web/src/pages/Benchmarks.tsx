import { useState, useEffect } from 'react'
import { apiClient } from '../api'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface Benchmark {
  id: number
  name: string
  category: string
  origin: string
  created_ts: string
}

interface TrendData {
  trend: Array<{
    version_id: number
    label: string
    score: number
    timestamp: string
  }>
  total_versions: number
}

export default function Benchmarks() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([])
  const [trend, setTrend] = useState<TrendData | null>(null)
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

  if (loading) {
    return <div className="text-gray-400">Loading benchmarks...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Benchmarks</h2>
      
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
        </div>
      )}
      
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="min-w-full">
          <thead className="bg-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Category</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Origin</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Created</th>
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
