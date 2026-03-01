export interface Player {
  name: string
  class_id: number
  class_name: string
  server: string
  region: string
}

export interface PlayerDetail extends Player {
  scores: PlayerScore[]
}

export interface PlayerScore {
  report_code: string
  spec: string
  overall_score: number
  parse_score: number
  utility_score: number | null
  consumables_score: number | null
  fight_count: number
  recorded_at: string
}

export interface Ranking {
  encounter_name: string
  spec: string
  rank_percent: number
  zone_id: number
  report_code: string
  recorded_at: string
}

export interface GearGem {
  id: number
}

export interface GearItem {
  slot: number
  item_id: number
  item_level: number
  quality: number
  permanent_enchant: number | null
  gems: GearGem[] | null
}

export interface GearCheck {
  player: string
  report_code: string
  avg_ilvl: number
  ilvl_ok: boolean
  gear: GearItem[]
  issues: { slot: string; problem: string }[]
}

export interface LeaderboardEntry {
  rank: number
  name: string
  class_name: string
  avg_score: number
  avg_parse: number
  fight_count: number
}

export interface ReportSummary {
  code: string
  zone_id: number
  zone_name: string
  start_time: string
  end_time: string
  player_count: number
}

export interface ReportDetail extends ReportSummary {
  player_names: string[]
  scores: {
    player_name: string
    class_name: string
    spec: string
    overall_score: number
    parse_score: number
    utility_score: number | null
    consumables_score: number | null
  }[]
  consumables: {
    player_name: string
    metric_name: string
    label: string
    actual_value: number
    target_value: number
    optional: boolean
  }[]
}

export interface AttendanceWeek {
  year: number
  week: number
  zones: {
    zone_id: number
    zone_label: string
    clear_count: number
    required: number
    met: boolean
  }[]
}

export interface PlayerAttendance {
  name: string
  class_name: string
  weeks: {
    year: number
    week: number
    zone_label: string
    met: boolean
  }[]
}

export interface SyncStatusEntry {
  sync_type: string
  last_run_at: string | null
  next_run_at: string | null
  status: string
  error_message: string | null
}

export interface TrendPoint {
  date: string
  report_code: string
  overall_score: number
  parse_score: number
  utility_score: number | null
  consumables_score: number | null
}
