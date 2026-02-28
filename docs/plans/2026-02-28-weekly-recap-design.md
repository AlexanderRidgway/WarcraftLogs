# Weekly Recap — Design Document

**Date:** 2026-02-28
**Context:** Add a single command that pulls all guild reports for a week and produces a full digest: top performers, per-zone summaries, attendance, and gear issues.

---

## Goal

Replace the need to run `/raidrecap` on each log URL individually. Officers run `/weeklyrecap` once and get a complete picture of the guild's week — top performers across all raids, zone-by-zone highlights, attendance compliance, and gear readiness — all automatically pulled from the guild's WarcraftLogs page.

---

## Command

```
/weeklyrecap              # current week (Mon-Sun)
/weeklyrecap weeks_ago:1  # last week
```

---

## Output — 4 Embeds

### Embed 1: Top Performers (guild-wide)
Top 10 raiders ranked by average score across all reports they appeared in that week.

```
Weekly Top Performers — Week of Feb 23

🥇 Thrallbro — 94.2 (5 fights)
🥈 Leetmage — 91.7 (4 fights)
🥉 Healbot — 89.1 (5 fights)
4. Tankbro — 87.3 (3 fights)
...
```

### Embed 2: Per-Zone Summaries
For each zone found in the week's reports:

```
Zone Summaries — Week of Feb 23

Karazhan (4 runs, 32 players)
  🥇 Leetmage — 96.1 | 🥈 Stabguy — 93.4 | 🥉 Healbot — 91.0

Gruul's Lair (1 run, 25 players)
  🥇 Thrallbro — 97.8 | 🥈 Tankbro — 92.1 | 🥉 Leetmage — 88.4

Magtheridon's Lair (1 run, 25 players)
  🥇 Thrallbro — 95.3 | 🥈 Healbot — 91.7 | 🥉 Stabguy — 89.0
```

### Embed 3: Attendance
Same logic as `/attendancereport` but scoped to this single week.

```
Attendance — Week of Feb 23

❌ Slackguy — missed Karazhan, Magtheridon's
❌ Afkdude — missed Gruul's

✅ 28 players met all attendance requirements
```

### Embed 4: Gear Issues
Aggregated gear check across all reports that week.

```
Gear Issues — Week of Feb 23

⚠️ Newguy — 4 issues (avg ilvl 94)
⚠️ Altchar — 2 issues

✅ 30 players passed gear checks
```

---

## Data Flow

1. Calculate Monday 00:00 UTC → Sunday 23:59 UTC for target week
2. Call `get_guild_reports()` for that time range → list of reports with zone and player names
3. For each report, call `get_report_rankings()` → per-player parse scores
4. Aggregate scores: per player across all reports (guild-wide top performers) and per zone (zone summaries)
5. Run `check_player_attendance()` against the week's reports and attendance config
6. For each report, call `get_report_gear()` and run `check_raid_gear()` — deduplicate by player name (use worst result if player appears in multiple reports)
7. Send 4 embeds in sequence

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| No reports found for the week | "No guild reports found for this week." |
| Player in multiple reports (e.g. Kara + Gruul) | Scores averaged across all appearances for guild-wide ranking |
| Player in multiple Kara runs | All appearances counted for zone summary; averaged for guild-wide |
| weeks_ago=0 and week is in progress | Shows data for reports uploaded so far this week |
| Report has no ranking data | Skipped for scoring (but still counts for attendance) |
| Gear issues in multiple reports for same player | Deduplicate — show worst/most issues |
| Embed exceeds Discord limits | Truncate player lists with "+N more" |

---

## Reuse

This command reuses all existing infrastructure:
- `get_guild_reports()` — already built for attendance
- `get_report_rankings()` — already built for /raidrecap
- `score_player()` / `score_consistency()` — existing scoring engine
- `check_player_attendance()` — already built
- `get_report_gear()` / `check_raid_gear()` — already built
- `_extract_report_code()` — not needed (we get report codes from guild reports)

Only new code: the `/weeklyrecap` command module and a helper to aggregate scores across multiple reports.
