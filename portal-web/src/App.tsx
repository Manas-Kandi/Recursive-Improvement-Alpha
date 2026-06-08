import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import Sessions from './pages/Sessions'
import HarnessStatePage from './pages/HarnessState'
import Mutations from './pages/Mutations'
import Benchmarks from './pages/Benchmarks'
import Tools from './pages/Tools'
import Versions from './pages/Versions'
import Health from './pages/Health'
import Login from './pages/Login'

function Layout() {
  const { isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  if (!isAuthenticated) {
    return <Login />
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <nav className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-6">
              <h1 className="text-xl font-bold text-white">SIHA</h1>
              <div className="flex space-x-1">
                <Link to="/sessions" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Sessions</Link>
                <Link to="/harness" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Harness</Link>
                <Link to="/mutations" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Mutations</Link>
                <Link to="/benchmarks" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Benchmarks</Link>
                <Link to="/tools" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Tools</Link>
                <Link to="/versions" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Versions</Link>
                <Link to="/health" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium">Health</Link>
              </div>
            </div>
            <button
              onClick={() => { logout(); navigate('/') }}
              className="text-sm text-gray-400 hover:text-white"
            >
              Sign Out
            </button>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Sessions />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/harness" element={<HarnessStatePage />} />
          <Route path="/mutations" element={<Mutations />} />
          <Route path="/benchmarks" element={<Benchmarks />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/versions" element={<Versions />} />
          <Route path="/health" element={<Health />} />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
