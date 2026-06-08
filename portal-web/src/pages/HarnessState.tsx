import { useState, useEffect } from 'react'
import { apiClient } from '../api'

interface HarnessState {
  prompts: any[]
  tools: any[]
  strategies: any[]
}

export default function HarnessState() {
  const [state, setState] = useState<HarnessState | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadState()
  }, [])

  const loadState = async () => {
    try {
      const response = await apiClient.getHarnessState()
      setState(response.data)
    } catch (error) {
      console.error('Failed to load harness state:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-gray-400">Loading harness state...</div>
  }

  if (!state) {
    return <div className="text-gray-400">No harness state available</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Harness State</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Prompts ({state.prompts.length})</h3>
          <div className="space-y-3">
            {state.prompts.map((prompt) => (
              <div key={prompt.id} className="bg-gray-700 rounded p-3">
                <span className="text-sm font-medium text-blue-400">{prompt.role}</span>
                <span className="text-xs text-gray-400 ml-2">v{prompt.version}</span>
                <p className="text-xs text-gray-300 mt-2 line-clamp-3">{prompt.text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Tools ({state.tools.length})</h3>
          <div className="space-y-3">
            {state.tools.map((tool) => (
              <div key={tool.id} className="bg-gray-700 rounded p-3">
                <span className="text-sm font-medium text-green-400">{tool.name}</span>
                <span className="text-xs text-gray-400 ml-2">v{tool.version}</span>
                <p className="text-xs text-gray-300 mt-2">{tool.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Strategies ({state.strategies.length})</h3>
          <div className="space-y-3">
            {state.strategies.map((strategy) => (
              <div key={strategy.id} className="bg-gray-700 rounded p-3">
                <span className="text-sm font-medium text-purple-400">{strategy.key}</span>
                <span className="text-xs text-gray-400 ml-2">v{strategy.version}</span>
                <pre className="text-xs text-gray-300 mt-2 overflow-auto">{JSON.stringify(strategy.value, null, 2)}</pre>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
