# Guild Website Design

**Date:** 2026-02-28
**Status:** Approved

## Overview

A fully public website for \<CRANK\> guild members to look up their character, view gear, parse history, utility/consumable metrics, attendance, and raid recaps. Replaces the need to run Discord commands for read-only data access.

## Decisions

| Decision | Choice |
|---|---|
| Audience | Fully public, no auth |
| Data strategy | Cached/scheduled sync to PostgreSQL |
| Frontend | React (Vite) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| Scope | Full dashboard (player profiles, roster, raid recaps, attendance, gear, config) |
| Hosting | Same EC2 instance as the bot |
| Repo structure | Monorepo — `web/` directory alongside existing `src/` |

## Architecture

Monorepo with shared data layer. The API backend imports and reuses existing bot modules (`src/scoring/engine.py`, `src/gear/checker.py`, `src/config/loader.py`, `src/api/warcraftlogs.py`) directly.

```
[WarcraftLogs API] --> [Sync Worker] --> [PostgreSQL]
                                              |
[React Frontend] <-- [FastAPI Backend] <------+
                                              |
[config.yaml] <-- [ConfigLoader] -------------+
```

Four processes on EC2 via docker-compose:
1. **Discord bot** (existing)
2. **PostgreSQL** container
3. **FastAPI web API** serving REST endpoints + React static build
4. **Sync worker** background process pulling WCL data into Postgres

## Database Schema

### `players` — Guild roster cache
- `id` (PK), `name`, `class_id`, `class_name`, `server`, `region`, `last_synced_at`

### `rankings` — Per-boss parse history
- `id` (PK), `player_id` (FK), `encounter_name`, `spec`, `rank_percent` (float), `zone_id`, `report_code`, `recorded_at`

### `scores` — Computed consistency/utility/consumable scores per report
- `id` (PK), `player_id` (FK), `report_code`, `spec`, `overall_score`, `parse_score`, `utility_score`, `consumables_score`, `fight_count`, `recorded_at`

### `gear_snapshots` — Gear from raid reports
- `id` (PK), `player_id` (FK), `report_code`, `slot`, `item_id`, `item_level`, `quality`, `permanent_enchant`, `gems` (JSON), `recorded_at`

### `utility_data` — Per-player per-report utility metric actuals
- `id` (PK), `player_id` (FK), `report_code`, `metric_name`, `label`, `actual_value`, `target_value`, `score`

### `consumables_data` — Per-player per-report consumable usage
- `id` (PK), `player_id` (FK), `report_code`, `metric_name`, `label`, `actual_value`, `target_value`, `optional` (bool)

### `reports` — Raid report metadata
- `id` (PK), `code` (unique), `zone_id`, `zone_name`, `start_time`, `end_time`, `player_names` (JSON)

### `attendance_records` — Computed attendance per player per week
- `id` (PK), `player_id` (FK), `year`, `week_number`, `zone_id`, `zone_label`, `clear_count`, `required`, `met` (bool)

### `sync_status` — Sync tracking
- `id` (PK), `sync_type`, `last_run_at`, `next_run_at`, `status`, `error_message`

## API Endpoints

All endpoints are read-only. No authentication required.

### Player
- `GET /api/players` — List all guild members (name, class, spec, latest consistency score)
- `GET /api/players/{name}` — Full player profile
- `GET /api/players/{name}/rankings` — Parse history (`?weeks=N`)
- `GET /api/players/{name}/gear` — Latest gear snapshot with issues
- `GET /api/players/{name}/attendance` — Attendance records (`?weeks=N`)

### Guild
- `GET /api/leaderboard` — Players ranked by consistency score (`?weeks=N`)

### Raids
- `GET /api/reports` — List of synced reports
- `GET /api/reports/{code}` — Full raid recap with scores, consumables, gear issues

### Attendance
- `GET /api/attendance` — Guild-wide attendance summary (`?weeks=N`)

### Config (read-only)
- `GET /api/config/specs` — Spec profiles
- `GET /api/config/consumables` — Consumable definitions
- `GET /api/config/attendance` — Attendance requirements
- `GET /api/config/gear` — Gear check thresholds

### Sync
- `GET /api/sync/status` — Last sync time, next scheduled sync

## Frontend Pages

### Home / Guild Roster (`/`)
- Search bar to find a player by name
- Leaderboard table: Rank, Name, Class (color-coded), Spec, Consistency Score, Avg Parse
- Filterable by class, sortable by columns

### Player Profile (`/player/{name}`)
- Header: name, class/spec (class color), consistency score badge
- Gear Panel: visual grid with ilvl, quality colors, enchant/gem status, issue warnings
- Performance Tab: per-boss breakdown (parse percentile color-coded, utility score, overall score)
- Utility Tab: each metric with actual vs target, progress bars
- Consumables Tab: per-raid consumable usage
- Attendance Tab: week-by-week with check/cross per zone

### Raid History (`/raids`)
- List of synced reports sorted by date
- Cards: zone name, date, player count

### Raid Detail (`/raids/{code}`)
- Standout performers, full player table, consumables breakdown, gear issues

### Attendance (`/attendance`)
- Guild-wide summary, players with missed requirements highlighted, week filter

### Config Reference (`/config`)
- Read-only view of spec profiles, contribution targets, consumable definitions, gear thresholds

## Sync Worker

### Schedule
- **Roster sync:** Every 6 hours
- **Reports sync:** Every 2 hours
- **Initial backfill:** Last 8 weeks on first run (empty DB)

### Behavior
- Reports keyed by `code` — skip if already in DB
- Players keyed by `name` — upsert on roster sync
- Per-report processing: rankings, scores, gear, utility, consumables, attendance in one pass
- WCL API failures log warnings, don't crash
- Individual report failures skipped and retried next cycle
- Rate limiting with backoff

## Project Structure

```
WarcraftLogs/
├── src/                          # existing bot (unchanged)
├── web/
│   ├── api/
│   │   ├── main.py               # FastAPI app + startup
│   │   ├── database.py           # SQLAlchemy async engine + session
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   ├── routes/
│   │   │   ├── players.py
│   │   │   ├── reports.py
│   │   │   ├── leaderboard.py
│   │   │   ├── attendance.py
│   │   │   ├── config.py
│   │   │   └── sync_status.py
│   │   └── sync/
│   │       ├── worker.py         # APScheduler sync scheduler
│   │       ├── roster.py
│   │       └── reports.py
│   ├── frontend/
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── index.html
│   │   └── src/
│   │       ├── App.tsx
│   │       ├── pages/
│   │       │   ├── Home.tsx
│   │       │   ├── PlayerProfile.tsx
│   │       │   ├── RaidHistory.tsx
│   │       │   ├── RaidDetail.tsx
│   │       │   ├── Attendance.tsx
│   │       │   └── Config.tsx
│   │       ├── components/
│   │       │   ├── GearGrid.tsx
│   │       │   ├── ParseBar.tsx
│   │       │   ├── ScoreCard.tsx
│   │       │   └── ClassIcon.tsx
│   │       └── api/
│   │           └── client.ts
│   └── requirements.txt
├── docker-compose.yml
├── Dockerfile.web
└── config.yaml                   # shared with bot
```

## Deployment

- `docker-compose.yml` adds: `postgres`, `web-api`, `sync-worker` services
- FastAPI serves React production build from `/static`
- New env vars: `DATABASE_URL`, `SYNC_INTERVAL_HOURS`
- Reuses existing WCL credentials from Secrets Manager
