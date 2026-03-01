import type {
  Player, PlayerDetail, Ranking, GearCheck,
  LeaderboardEntry, ReportSummary, ReportDetail,
  PlayerAttendance, SyncStatusEntry, AttendanceWeek,
} from './types'

const BASE = '/api'

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  players: {
    list: () => fetchJson<Player[]>('/players'),
    get: (name: string) => fetchJson<PlayerDetail>(`/players/${encodeURIComponent(name)}`),
    rankings: (name: string, weeks = 4) => fetchJson<Ranking[]>(`/players/${encodeURIComponent(name)}/rankings?weeks=${weeks}`),
    gear: (name: string) => fetchJson<GearCheck>(`/players/${encodeURIComponent(name)}/gear`),
    attendance: (name: string, weeks = 4) => fetchJson<AttendanceWeek[]>(`/players/${encodeURIComponent(name)}/attendance?weeks=${weeks}`),
  },
  leaderboard: (weeks = 4) => fetchJson<LeaderboardEntry[]>(`/leaderboard?weeks=${weeks}`),
  reports: {
    list: () => fetchJson<ReportSummary[]>('/reports'),
    get: (code: string) => fetchJson<ReportDetail>(`/reports/${encodeURIComponent(code)}`),
  },
  attendance: (weeks = 4) => fetchJson<PlayerAttendance[]>(`/attendance?weeks=${weeks}`),
  config: {
    specs: () => fetchJson<Record<string, unknown>>('/config/specs'),
    consumables: () => fetchJson<unknown[]>('/config/consumables'),
    attendance: () => fetchJson<unknown[]>('/config/attendance'),
    gear: () => fetchJson<Record<string, unknown>>('/config/gear'),
  },
  sync: () => fetchJson<SyncStatusEntry[]>('/sync/status'),
}
