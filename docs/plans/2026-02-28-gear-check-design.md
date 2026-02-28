# Gear Check — Design Document

**Date:** 2026-02-28
**Context:** Add gear readiness checking to the TBC guild Discord bot so officers can identify raiders showing up with subpar gear (green items, missing enchants, empty gems, low ilvl).

---

## Goal

Validate raider gear from WarcraftLogs report data. Flag green/low-quality items, missing enchants, empty gem sockets, and low average item level. Provide a standalone `/gearcheck` command and a condensed summary in `/raidrecap`. All thresholds are configurable so officers can raise standards as the guild progresses through tiers.

---

## Config Schema

New top-level `gear_check` section in `config.yaml`:

```yaml
gear_check:
  min_avg_ilvl: 100
  min_quality: 3
  check_enchants: true
  check_gems: true
  enchant_slots: [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]
```

- `min_avg_ilvl` — average item level floor; anyone below is flagged
- `min_quality` — minimum acceptable item quality (2=green, 3=blue, 4=epic); items below are flagged
- `check_enchants` — whether to flag unenchanted gear in enchantable slots
- `check_gems` — whether to flag empty gem sockets
- `enchant_slots` — WoW equipment slot IDs that should be enchanted (head=0, neck=1, shoulder=2, chest=4, waist=5, legs=6, feet=7, wrist=8, hands=9, cloak=14, mainhand=15)

`ConfigLoader` gains `get_gear_check()` to read this section with sensible defaults.

---

## API Layer

New method on `WarcraftLogsClient`:

**`get_report_gear(report_code)`**
- Queries `reportData.report.table(dataType: Summary)` for fight 0 (first fight)
- Returns list of player gear snapshots: `name`, `gear` (array of items with `id`, `slot`, `quality`, `itemLevel`, `permanentEnchant`, `gems`)
- Reuses existing `_query_table` pattern

---

## Gear Checking Logic

New module `src/gear/checker.py` — pure logic, no Discord/API dependencies.

**`check_player_gear(gear_items, gear_config)`**
Returns:
```python
{
    "avg_ilvl": 108.5,
    "ilvl_ok": True,
    "issues": [
        {"slot": "Chest", "problem": "Green quality item (ilvl 87)"},
        {"slot": "Gloves", "problem": "Missing enchant"},
        {"slot": "Head", "problem": "Empty gem socket"},
    ]
}
```

**`check_raid_gear(players_gear, gear_config)`**
Runs `check_player_gear` for everyone, returns only players with issues.

Slot number to name mapping (0=Head, 1=Neck, 2=Shoulder, etc.) for display.
Shirt (3), tabard (18) excluded from all checks. Off-hand (16) skipped if empty (2H users).

---

## Discord Commands

### `/gearcheck <log_url>`

```
Gear Check — Report abc123

⚠️ Thrallbro (avg ilvl 98 — below 100 minimum)
  • Chest: Green quality item (ilvl 87)
  • Gloves: Missing enchant
  • Head: Empty gem socket

⚠️ Leetmage (avg ilvl 112)
  • Boots: Missing enchant
  • Ring 1: Missing enchant

✅ 18 players passed all gear checks
```

### `/raidrecap` addition

Condensed gear field appended to existing embed:
```
Gear Issues: Thrallbro (3 issues, avg ilvl 98), Leetmage (2 issues)
```
Omitted entirely if everyone passes.

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Report has no summary/gear data | "Could not fetch gear data from this report." |
| Empty gear slots (null items) | Flag as "Empty slot" |
| Item has no gem data (unsocketed) | Not flagged — only flag socketed items missing gems |
| Shirt/tabard slots | Excluded from all checks |
| Off-hand for 2H users | Skip if empty |
| `gear_check` not configured | Default: min_avg_ilvl=100, min_quality=3, check_enchants=true, check_gems=true |
| Everyone passes | `/gearcheck`: "All players passed!" / `/raidrecap`: field omitted |

---

## Testing

- Unit tests for `check_player_gear` with mocked gear arrays (green items, missing enchants, empty gems, below ilvl, clean gear)
- Tests for `check_raid_gear` (multiple players, mix of issues and clean)
- Tests for `ConfigLoader.get_gear_check()` (present, missing/defaults)
- Tests for `get_report_gear()` with mocked API responses
- Tests for edge cases (empty slots, shirt/tabard exclusion, off-hand skip)
