import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import { ToastProvider } from './components/Toast'
import Home from './pages/Home'
import PlayerProfile from './pages/PlayerProfile'
import RaidHistory from './pages/RaidHistory'
import RaidDetail from './pages/RaidDetail'
import Attendance from './pages/Attendance'
import Config from './pages/Config'
import Checklist from './pages/Checklist'
import Login from './pages/Login'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/" element={<Home />} />
              <Route path="/player/:name" element={<PlayerProfile />} />
              <Route path="/raids" element={<RaidHistory />} />
              <Route path="/raids/:code" element={<RaidDetail />} />
              <Route path="/attendance" element={<Attendance />} />
              <Route path="/checklist" element={<Checklist />} />
              <Route path="/config" element={<Config />} />
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
