const BASE = '/api'

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  players: {
    list: () => fetchJson<import('./types').Player[]>('/players'),
    get: (name: string) => fetchJson<import('./types').PlayerDetail>(`/players/${name}`),
    rankings: (name: string, weeks = 4) => fetchJson<import('./types').Ranking[]>(`/players/${name}/rankings?weeks=${weeks}`),
    gear: (name: string) => fetchJson<import('./types').GearCheck>(`/players/${name}/gear`),
    attendance: (name: string, weeks = 4) => fetchJson<import('./types').AttendanceWeek[]>(`/players/${name}/attendance?weeks=${weeks}`),
    trends: (name: string, weeks = 8) => fetchJson<import('./types').TrendPoint[]>(`/players/${name}/trends?weeks=${weeks}`),
    insights: (name: string, weeks = 4) => fetchJson<import('./types').InsightEntry[]>(`/players/${name}/insights?weeks=${weeks}`),
  },
  leaderboard: (weeks = 4) => fetchJson<import('./types').LeaderboardEntry[]>(`/leaderboard?weeks=${weeks}`),
  mvp: (weeksAgo = 0) => fetchJson<import('./types').MvpEntry | null>(`/mvp?weeks_ago=${weeksAgo}`),
  checklist: () => fetchJson<{ players: any[] }>('/checklist'),
  reports: {
    list: () => fetchJson<import('./types').ReportSummary[]>('/reports'),
    get: (code: string) => fetchJson<import('./types').ReportDetail>(`/reports/${code}`),
  },
  attendance: (weeks = 4) => fetchJson<import('./types').PlayerAttendance[]>(`/attendance?weeks=${weeks}`),
  config: {
    specs: () => fetchJson<Record<string, any>>('/config/specs'),
    consumables: () => fetchJson<any[]>('/config/consumables'),
    attendance: () => fetchJson<any[]>('/config/attendance'),
    gear: () => fetchJson<Record<string, any>>('/config/gear'),
    updateTarget: (specKey: string, metric: string, target: number) =>
      putJson(`/config/specs/${specKey}/contributions/${metric}`, { target }),
    updateWeights: (specKey: string, weights: { parse_weight: number; utility_weight: number; consumables_weight: number }) =>
      putJson(`/config/specs/${specKey}/weights`, weights),
    updateAttendance: (zoneId: number, required: number) =>
      putJson(`/config/attendance/${zoneId}`, { required_per_week: required }),
  },
  auth: {
    forgotPassword: (email: string) =>
      postJson('/auth/forgot-password', { email }),
    resetPassword: (token: string, newPassword: string) =>
      postJson('/auth/reset-password', { token, new_password: newPassword }),
  },
  sync: {
    status: () => fetchJson<import('./types').SyncStatusEntry[]>('/sync/status'),
    trigger: (force: boolean) => postJson('/sync/trigger?force=' + force),
  },
}
