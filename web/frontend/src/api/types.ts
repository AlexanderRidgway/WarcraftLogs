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
  informational?: boolean
}

export interface Ranking {
  encounter_name: string
  spec: string
  rank_percent: number
  zone_id: number
  report_code: string
  recorded_at: string
  zone_name?: string
  player_count?: number
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
  spec?: string
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
  kill_count?: number
  wipe_count?: number
  death_count?: number
  avg_parse?: number | null
  informational?: boolean
}

export interface BossRankingEntry {
  player_name: string
  spec: string
  rank_percent: number
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
  boss_rankings?: Record<string, BossRankingEntry[]>
  consumable_flags?: ConsumableFlag[]
}

export interface UtilityMetric {
  metric_name: string
  label: string
  actual_value: number
  target_value: number
  score: number
}

export interface PlayerUtility {
  player_name: string
  class_name: string
  metrics: UtilityMetric[]
}

export interface ReportGearPlayer {
  name: string
  class_name: string
  avg_ilvl: number
  ilvl_ok: boolean
  issues: { slot: string; problem: string }[]
  issue_count: number
}

export interface ReportGearCheck {
  total_players: number
  passed: number
  flagged: number
  gear_config: Record<string, any>
  players: ReportGearPlayer[]
}

export interface ConsumableFlag {
  player_name: string
  flask_ok: boolean
  potion_ok: boolean
  passed: boolean
  reasons: string[]
}

export interface AttendanceReport {
  code: string
  date: string
  zone_name: string
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
    reports?: AttendanceReport[]
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

export interface MvpEntry {
  name: string
  class_name: string
  spec: string
  overall_score: number
  parse_score: number
  utility_score: number | null
  consumables_score: number | null
  fight_count: number
  week_start: string
}

export interface InsightEntry {
  type: 'warning' | 'success' | 'info'
  message: string
  metric: string | null
}

export interface GuildTrendPoint {
  date: string
  report_code: string
  avg_parse: number
  avg_score: number
  player_count: number
}

export interface WeeklyTopPerformer {
  name: string
  class_name: string
  avg_score: number
  avg_parse: number
  fight_count: number
}

export interface WeeklyZoneSummary {
  zone_name: string
  run_count: number
  unique_players: number
  top_players: { name: string; class_name: string; avg_score: number }[]
}

export interface WeeklyAttendanceMiss {
  player_name: string
  zone_label: string
  clear_count: number
  required: number
}

export interface WeeklyGearIssue {
  name: string
  class_name: string
  avg_ilvl: number
  ilvl_ok: boolean
  issue_count: number
  issues: { slot: string; problem: string }[]
}

export interface WeeklyRecap {
  week_start: string
  week_end: string
  report_count: number
  top_performers: WeeklyTopPerformer[]
  zone_summaries: WeeklyZoneSummary[]
  attendance: WeeklyAttendanceMiss[]
  gear_issues: WeeklyGearIssue[]
}
