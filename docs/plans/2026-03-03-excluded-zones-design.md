# Excluded Zones (Informational-Only Raids) Design

## Problem

Karazhan reports should remain visible on the website but not count towards performance metrics, parses, leaderboards, MVP, insights, trends, attendance, or any aggregate calculations.

## Approach

Config-driven `excluded_zones` list in config.yaml. All aggregate queries JOIN Score -> Report and filter out excluded zone_ids. No DB migration needed.

## Changes

### Config Layer
- Add `excluded_zones: [1047]` to config.yaml
- Add `ConfigLoader.get_excluded_zones()` method
- Update `all_specs()` key filter to exclude `excluded_zones`

### Backend Routes (8 files)
All aggregate queries add `.where(Report.zone_id.notin_(excluded_zones))`:
1. `leaderboard.py` — leaderboard + guild-trends
2. `mvp.py` — MVP calculation
3. `weekly.py` — top performers (zone summaries still show all zones)
4. `compare.py` — spec comparison
5. `insights.py` — all 4 insight types
6. `roster.py` — distribution + at-risk
7. `players.py` — get_player scores, get_player_trends
8. `reports.py` — add `informational` flag to list + detail responses

### Attendance
- Sync worker skips excluded zones when computing attendance records
- Attendance API/frontend stops showing excluded zones

### Frontend
- `RaidHistory.tsx` — "Informational" badge on excluded zone raid cards
- `RaidDetail.tsx` — banner indicating scores don't count towards performance

### Behavior
- Reports still synced, processed, stored with full data
- Individual report pages still show all scores, rankings, utility, consumables, gear
- Excluded zone data excluded from ALL aggregates: leaderboard, MVP, weekly top performers, player averages, insights, trends, roster health, attendance
