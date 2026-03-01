import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import Home from './pages/Home'
import PlayerProfile from './pages/PlayerProfile'
import RaidHistory from './pages/RaidHistory'
import RaidDetail from './pages/RaidDetail'
import Attendance from './pages/Attendance'
import Config from './pages/Config'
import Login from './pages/Login'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Home />} />
            <Route path="/player/:name" element={<PlayerProfile />} />
            <Route path="/raids" element={<RaidHistory />} />
            <Route path="/raids/:code" element={<RaidDetail />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/config" element={<Config />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
