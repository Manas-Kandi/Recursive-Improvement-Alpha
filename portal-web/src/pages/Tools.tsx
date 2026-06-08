import { useState, useEffect } from 'react'
import { apiClient } from '../api'

interface Tool {
  id: number
  name: string
  version: string
  description: string
  status: string
  implementation_kind: string
  source_url: string | null
  created_ts: string
}

export default function Tools() {
  const [tools, setTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTools()
  }, [])

  const loadTools = async () => {
    try {
      const response = await apiClient.getTools()
      setTools(response.data)
    } catch (error) {
      console.error('Failed to load tools:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-600'
      case 'deprecated': return 'bg-red-600'
      default: return 'bg-gray-600'
    }
  }

  const getKindColor = (kind: string) => {
    switch (kind) {
      case 'builtin': return 'bg-blue-600'
      case 'python_code': return 'bg-purple-600'
      default: return 'bg-gray-600'
    }
  }

  if (loading) {
    return <div className="text-gray-400">Loading tools...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Tools</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tools.map((tool) => (
          <div key={tool.id} className="bg-gray-800 rounded-lg p-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-white">{tool.name}</h3>
              <span className={`px-2 py-1 rounded text-xs ${getStatusColor(tool.status)}`}>
                {tool.status}
              </span>
            </div>
            
            <div className="flex items-center space-x-2 mb-3">
              <span className="text-xs text-gray-400">v{tool.version}</span>
              <span className={`px-2 py-1 rounded text-xs ${getKindColor(tool.implementation_kind)}`}>
                {tool.implementation_kind}
              </span>
            </div>
            
            <p className="text-sm text-gray-300 mb-4">{tool.description}</p>
            
            {tool.source_url && (
              <a
                href={tool.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                Source Documentation →
              </a>
            )}
            
            <p className="text-xs text-gray-500 mt-4">
              Created: {new Date(tool.created_ts).toLocaleString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
