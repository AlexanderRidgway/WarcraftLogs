import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Home from './pages/Home'
import PlayerProfile from './pages/PlayerProfile'
import RaidHistory from './pages/RaidHistory'
import RaidDetail from './pages/RaidDetail'
import Attendance from './pages/Attendance'
import Config from './pages/Config'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/player/:name" element={<PlayerProfile />} />
          <Route path="/raids" element={<RaidHistory />} />
          <Route path="/raids/:code" element={<RaidDetail />} />
          <Route path="/attendance" element={<Attendance />} />
          <Route path="/config" element={<Config />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
