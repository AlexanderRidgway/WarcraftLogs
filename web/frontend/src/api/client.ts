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

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
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
    specs: () => fetchJson<Record<string, any>>('/config/specs'),
    consumables: () => fetchJson<any[]>('/config/consumables'),
    attendance: () => fetchJson<any[]>('/config/attendance'),
    gear: () => fetchJson<Record<string, any>>('/config/gear'),
    updateTarget: (specKey: string, metric: string, target: number) =>
      putJson<any>(`/config/specs/${encodeURIComponent(specKey)}/contributions/${encodeURIComponent(metric)}`, { target }),
    updateWeights: (specKey: string, weights: { parse_weight: number; utility_weight: number; consumables_weight: number }) =>
      putJson<any>(`/config/specs/${encodeURIComponent(specKey)}/weights`, weights),
    updateAttendance: (zoneId: number, requiredPerWeek: number) =>
      putJson<any>(`/config/attendance/${zoneId}`, { required_per_week: requiredPerWeek }),
  },
  sync: {
    status: () => fetchJson<SyncStatusEntry[]>('/sync/status'),
    trigger: (force = false) => postJson<{ status: string; message: string }>(`/sync/trigger?force=${force}`),
  },
}
