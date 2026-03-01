# Feature Expansion Design

**Goal:** Add 10 features that differentiate CRANK from raw WarcraftLogs by providing officer-focused insights, player development tools, and guild health analytics.

**Approach:** Incremental expansion — each feature is a self-contained slice (new models + sync logic + API endpoints + frontend pages/components). No architectural refactor needed.

**Key decisions:**
- Sync all new data (deaths, fights, stats) during the normal hourly sync — no on-demand fetching
- Recharts for all charting/graphing
- Automated-only badge system (no manual officer badges)
- MVP of the Week based on highest overall weighted score

---

## New Data Layer

### New WCL API Queries

| Method | WCL Table | Returns |
|--------|-----------|---------|
| `get_report_fights(report_code)` | `reportData.report.fights` | List of fights: encounter name, kill/wipe, duration, fight ID, boss % |
| `get_report_deaths(report_code, fight_id)` | Deaths table | Death events: player name, timestamp, killing ability, damage taken |
| `get_fight_damage(report_code, fight_id)` | DamageDone table | Per-player damage done for a specific fight |
| `get_fight_healing(report_code, fight_id)` | HealingDone table | Per-player healing done for a specific fight |

### New Database Tables

**`fights`**
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| report_code | String(20) FK | Links to reports table |
| fight_id | Integer | WCL fight ID within the report |
| encounter_name | String(100) | Boss name |
| kill | Boolean | true=kill, false=wipe |
| duration_ms | Integer | Fight length in milliseconds |
| fight_percentage | Float | Boss % reached (100 for kills) |
| start_time | Float | Fight start time (ms offset) |
| end_time | Float | Fight end time (ms offset) |

**`deaths`**
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| fight_id | Integer FK | Links to fights table |
| player_id | Integer FK | Links to players table |
| timestamp_ms | Integer | Time of death (ms offset from fight start) |
| killing_ability | String(100) | Name of the ability that killed them |
| damage_taken | Integer | Damage of the killing blow |

**`fight_player_stats`**
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| fight_id | Integer FK | Links to fights table |
| player_id | Integer FK | Links to players table |
| dps | Float | Damage per second |
| hps | Float | Healing per second |
| damage_done | Integer | Total damage |
| healing_done | Integer | Total healing |
| deaths_count | Integer | Number of deaths this fight |

**`badges`**
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| player_id | Integer FK | Links to players table |
| badge_type | String(50) | Badge identifier (e.g. "parse_god") |
| earned_at | DateTime | When the badge was awarded |
| details | String(255) | Context (e.g. "99.8% on Gruul - 2026-03-01") |

### Sync Pipeline Changes

After the existing report processing (rankings, gear, utility, consumables), add:

1. `get_report_fights()` → Store fight records
2. For each fight: `get_report_deaths()` → Store death records
3. For each fight: `get_fight_damage()` + `get_fight_healing()` → Store fight_player_stats
4. After all reports: Run badge evaluation for all players

---

## Feature 1: Pre-Raid Checklist Dashboard

**Page:** `/checklist` (new sidebar nav item)

**Purpose:** One-glance raid readiness view before raid night.

**Sections:**
- **Gear Issues** — Players with missing enchants, empty gems, low ilvl items (from latest GearSnapshot)
- **Attendance Flags** — Players who missed required raids last week (from AttendanceRecord)
- **Consumables History** — Players with consistently low flask uptime or potion usage (from ConsumablesData, last 4 reports)
- **Overall Readiness** — Per-player green/yellow/red indicator combining all factors

**API endpoint:** `GET /api/checklist`

**Data source:** Existing tables only (GearSnapshot, AttendanceRecord, ConsumablesData, Score). No new WCL API calls.

---

## Feature 2: Trend Graphs

**Location:** Player Profile page, Performance tab (above the rankings table)

**Charts (Recharts):**
- **Score trend** — Line chart: overall_score over time (x: report dates, y: 0-100)
- **Parse trend** — Line chart: parse_score over time
- **Utility trend** — Line chart: utility_score over time (only shown if spec has utility metrics)

**API endpoint:** `GET /api/players/{name}/trends?weeks=N`

Returns time-series array: `[{date, overall_score, parse_score, utility_score, report_code}]`

**Data source:** Existing `Score` table with `recorded_at` timestamps.

---

## Feature 3: Spec Comparison

**Page:** `/compare` (new sidebar nav item)

**UI flow:**
1. Dropdown to select spec (e.g. "Fury Warrior")
2. Shows all players of that spec in a comparison table
3. Bar chart comparing avg parse, avg score, avg utility side-by-side
4. Sortable columns

**API endpoint:** `GET /api/compare?spec=warrior:fury&weeks=N`

Returns: `[{name, avg_score, avg_parse, avg_utility, fight_count, trend_direction}]`

**Data source:** Existing `Score` + `Player` tables, filtered by spec from Score records.

---

## Feature 4: Personal Improvement Suggestions

**Location:** Player Profile page, new "Insights" card below the score cards

**Auto-generated suggestions based on data analysis:**
- Utility metric gaps: "Your Sunder Armor uptime averaged 78% vs. 90% target"
- Consumable consistency: "Flask uptime 100% for 3 consecutive raids"
- Parse trends: "Parsed below 50% on Gruul in 3 of 4 raids"
- Attendance: "Attendance dropped from 100% to 50% this week"
- Improvement: "Overall score improved by 12 points over last 4 weeks"

**API endpoint:** `GET /api/players/{name}/insights`

Returns: `[{type: "warning"|"success"|"info", message: string}]`

**Data source:** Existing tables (UtilityData, ConsumablesData, Ranking, AttendanceRecord, Score). Pure backend analysis logic.

---

## Feature 5: Death Log Summary

**Location:** Raid Detail page, new "Deaths" section/tab

**Display:**
- Per-fight death list: player name, time of death (as fight %), killing ability
- Death count per player across the entire raid (sorted most to fewest)
- "Deathless" highlight for players with zero deaths

**API endpoint:** `GET /api/reports/{code}/deaths`

Returns: `{per_fight: [{fight_name, kill, deaths: [{player, timestamp_pct, ability}]}], totals: [{player, death_count}]}`

**Data source:** New `fights` + `deaths` tables.

---

## Feature 6: Wipe Analysis

**Location:** Raid Detail page, alongside Death Log

**Display:**
- List of wipe pulls grouped by boss
- Per-wipe: duration, boss % reached, deaths leading to wipe
- Pattern summary: "3 wipes on Void Reaver — tank died before 40% in all wipes"

**API endpoint:** `GET /api/reports/{code}/wipes`

Returns: `[{encounter_name, wipe_count, kill_count, wipes: [{fight_id, duration, boss_pct, deaths: [...]}]}]`

**Data source:** New `fights` table (kill=false) + `deaths` table.

---

## Feature 7: Boss-Specific Scorecards

**Location:** Raid Detail page, expandable per-boss accordion sections

**Per-boss display:**
- Kill time / attempt count
- Per-player DPS and HPS for that fight (table + bar chart)
- Utility compliance for that specific fight
- Deaths during the fight

**API endpoint:** `GET /api/reports/{code}/fights/{fight_id}`

Returns: `{encounter_name, kill, duration, players: [{name, dps, hps, damage_done, healing_done, deaths}], utility: [{player, metric, actual, target}]}`

**Data source:** New `fights` + `fight_player_stats` tables, existing `UtilityData` filtered by report.

---

## Feature 8: Roster Health Dashboard

**Page:** `/roster` (new sidebar nav item)

**Sections:**
- **Class/Spec Distribution** — Pie chart or horizontal bar chart showing roster composition
- **Bench Depth** — Specs with only 1 player highlighted as "at risk"
- **Attendance Heatmap** — Grid: players (y-axis) x weeks (x-axis), green/red cells
- **At Risk Players** — Players with declining attendance or performance trends

**API endpoint:** `GET /api/roster/health?weeks=N`

Returns: `{distribution: [{spec, count}], at_risk: [{name, reason}], attendance_grid: [{name, weeks: [{year, week, met}]}]}`

**Data source:** Existing `Player`, `AttendanceRecord`, `Score` tables.

---

## Feature 9: Achievement/Badge System

**Location:** Player Profile page (badge display) + `/achievements` page

**Automated badges:**

| Badge | ID | Criteria |
|-------|-----|----------|
| Parse God | `parse_god` | 99+ parse on any boss |
| Consistency King | `consistency_king` | 90+ overall score for 4+ consecutive weeks |
| Iron Raider | `iron_raider` | 100% attendance for 4+ consecutive weeks |
| Flask Master | `flask_master` | 100% flask uptime for 4+ consecutive raids |
| Most Improved | `most_improved` | Largest score increase over a 4-week window |
| Deathless | `deathless` | Zero deaths in a full raid clear (all bosses killed) |
| Utility Star | `utility_star` | 95%+ utility score for 4+ consecutive weeks |
| Geared Up | `geared_up` | All equipped items epic+ quality, fully enchanted and gemmed |

**Badge evaluation:** Runs after each report sync completes. Checks all players, awards new badges (doesn't re-award duplicates).

**API endpoints:**
- `GET /api/players/{name}/badges` — Badges for a specific player
- `GET /api/achievements` — All badges across the guild

**Data source:** New `badges` table + existing Score, Ranking, AttendanceRecord, ConsumablesData, GearSnapshot, deaths tables.

---

## Feature 10: MVP of the Week

**Location:** Home/Leaderboard page, hero section at the top

**Display:**
- Highlighted card with crown/star visual treatment
- Player name, class icon, spec
- Score breakdown (overall, parse, utility, consumables)
- Compared to previous week's MVP

**API endpoint:** `GET /api/mvp?weeks_ago=0`

Returns: `{name, class_name, spec, overall_score, parse_score, utility_score, consumables_score, fight_count}`

**Data source:** Existing `Score` table, grouped by ISO week, highest average overall_score.

---

## New Navigation

Updated sidebar nav items:
1. Leaderboard (existing `/`)
2. Raids (existing `/raids`)
3. Attendance (existing `/attendance`)
4. Checklist (new `/checklist`)
5. Compare (new `/compare`)
6. Roster (new `/roster`)
7. Achievements (new `/achievements`)
8. Config (existing `/config`)

---

## Frontend Dependencies

**Add:** `recharts` (for trend graphs, spec comparison charts, roster distribution charts, boss scorecard bars)

---

## Implementation Order

Recommended build order (dependencies flow downward):

1. **New data layer** — WCL API queries, database tables, sync pipeline changes (fights, deaths, fight_player_stats)
2. **Recharts setup** — Install and configure with dark theme
3. **Trend Graphs** — Simplest chart feature, proves Recharts integration
4. **MVP of the Week** — Simple aggregation, high-visibility feature
5. **Personal Improvement Suggestions** — Backend logic only, minimal frontend
6. **Pre-Raid Checklist** — Uses existing data, new page
7. **Spec Comparison** — New page with charts
8. **Roster Health Dashboard** — New page with charts and heatmap
9. **Death Log Summary** — Depends on new data layer
10. **Wipe Analysis** — Depends on death log data
11. **Boss-Specific Scorecards** — Depends on fight_player_stats
12. **Achievement/Badge System** — Depends on deaths data for "Deathless" badge
