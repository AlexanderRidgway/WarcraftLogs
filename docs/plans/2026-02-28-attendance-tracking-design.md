# Attendance Tracking — Design Document

**Date:** 2026-02-28
**Context:** Add attendance tracking to the TBC guild Discord bot so officers can see which raiders missed required weekly raids.

---

## Goal

Track per-player raid attendance against configurable weekly requirements. Officers can see who missed raids (per-player or guild-wide) and adjust which raids are required as the guild progresses through content phases. Attendance is informational only — it does not affect player scores.

---

## Config Schema

New top-level `attendance` section in `config.yaml`:

```yaml
attendance:
  - zone_id: 1002
    label: "Karazhan"
    required_per_week: 1
  - zone_id: 1004
    label: "Gruul's Lair"
    required_per_week: 1
  - zone_id: 1005
    label: "Magtheridon's Lair"
    required_per_week: 1
```

Officers add/remove entries as phases change. `ConfigLoader` gains:
- `get_attendance()` — returns the attendance requirements list
- `update_attendance(zone_id, ...)` — add, remove, or modify entries, persist to disk

---

## API Layer

New method on `WarcraftLogsClient`:

**`get_guild_reports(guild_name, server_slug, region, start_time, end_time)`**
- Uses `reportData.reports` GraphQL query filtered by guild
- Returns list of reports with: `code`, `startTime`, `zone { id name }`, `players` (player names)
- `start_time`/`end_time` limit query to the relevant week range

Uses existing client credentials OAuth2 flow — no auth changes needed.

---

## Discord Commands

### `/attendance <character> [weeks]`
Per-player breakdown over the last N weeks (default: 4).

```
Thrallbro — Attendance (last 4 weeks)

Week of Feb 17: ✅ Karazhan | ✅ Gruul's | ❌ Magtheridon's
Week of Feb 10: ✅ Karazhan | ✅ Gruul's | ✅ Magtheridon's
Week of Feb 3:  ✅ Karazhan | ❌ Gruul's | ✅ Magtheridon's
Week of Jan 27: ✅ Karazhan | ✅ Gruul's | ✅ Magtheridon's

Attendance Rate: 91.7% (11/12)
```

### `/attendancereport [weeks]`
Guild-wide summary over the last N weeks (default: 4). Lists players with missed raids sorted by most missed first. Perfect attendance players summarized as a count.

```
Guild Attendance Report (last 4 weeks)

❌ Thrallbro — missed 1 (Magtheridon's wk Feb 17)
❌ Leetmage — missed 2 (Gruul's wk Feb 10, Karazhan wk Feb 3)

✅ 18 players with perfect attendance
```

### `/setattendance` (Officers only)
Manage attendance requirements via Discord:
- `/setattendance add <zone_id> <label> <required_per_week>`
- `/setattendance remove <zone_id>`
- `/setattendance update <zone_id> <required_per_week>`

---

## Data Flow

1. Command invoked → calculate date range (N weeks back, Monday–Sunday boundaries)
2. Call `get_guild_reports()` for that date range
3. Group reports by ISO week number and zone ID
4. For each player/week, check if they appear in at least `required_per_week` reports for each required zone
5. Format results into Discord embed

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Player appears in report for only some bosses | Counts as attended |
| Multiple reports for same zone in same week | Count all of them |
| Zone has 0 reports for a week (guild didn't run it) | Shows as missed — requirement exists |
| No reports in time range | "No raid data found for this period." |
| Player not found in any reports | "Player not found in any guild reports." |
| New raid added mid-phase | Only applies going forward; past weeks show missed |

---

## Testing

- Unit tests with mocked API responses for `get_guild_reports()`
- Tests for week grouping logic and attendance checking
- Tests for `ConfigLoader` attendance methods (`get_attendance`, `update_attendance`)
- Tests for edge cases (no reports, player not found, multiple reports per zone)
