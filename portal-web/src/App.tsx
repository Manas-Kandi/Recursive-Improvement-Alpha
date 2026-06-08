import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Sessions from './pages/Sessions'
import HarnessState from './pages/HarnessState'
import Mutations from './pages/Mutations'
import Benchmarks from './pages/Benchmarks'
import Tools from './pages/Tools'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <nav className="bg-gray-800 border-b border-gray-700">
          <div className="max-w-7xl mx-auto px-4">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center space-x-8">
                <h1 className="text-xl font-bold text-white">✦ 9xf-code</h1>
                <div className="flex space-x-4">
                  <Link to="/sessions" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Sessions</Link>
                  <Link to="/harness" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Harness State</Link>
                  <Link to="/mutations" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Mutations</Link>
                  <Link to="/benchmarks" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Benchmarks</Link>
                  <Link to="/tools" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Tools</Link>
                </div>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Sessions />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/harness" element={<HarnessState />} />
            <Route path="/mutations" element={<Mutations />} />
            <Route path="/benchmarks" element={<Benchmarks />} />
            <Route path="/tools" element={<Tools />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
