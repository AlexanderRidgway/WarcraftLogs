# WarcraftLogs Discord Bot — Project Context

## What This Is

A Discord bot for a World of Warcraft: The Burning Crusade (TBC Classic) guild. Officers use it to identify outstanding raiders for loot priority by scoring players on both parse percentiles and utility contributions (buffs/debuffs).

## Owner

- **Name:** Alex
- **Git email:** ridgway_alex93@yahoo.com
- **Role:** Guild officer

## Project Structure

```
WarcraftLogs/
├── src/
│   ├── bot.py                  # Bot entry point, GuildBot class, officer check
│   ├── api/
│   │   └── warcraftlogs.py     # WarcraftLogs GraphQL client (OAuth2 + queries)
│   ├── attendance/
│   │   └── checker.py          # group_reports_by_week(), check_player_attendance()
│   ├── commands/
│   │   ├── topconsistent.py    # /topconsistent — ranks guild members by consistency
│   │   ├── player.py           # /player — per-boss breakdown for one character
│   │   ├── raidrecap.py        # /raidrecap — scores everyone in a log URL
│   │   ├── setconfig.py        # /setconfig — officers update metric targets
│   │   ├── attendance.py       # /attendance, /attendancereport — player & guild attendance
│   │   ├── setattendance.py    # /setattendance add/remove/update/list — officer commands
│   │   └── gearcheck.py        # /gearcheck — gear readiness check from a raid report
│   ├── gear/
│   │   └── checker.py          # gear quality, enchant, and gem validation logic
│   ├── config/
│   │   └── loader.py           # ConfigLoader: reads/writes config.yaml
│   └── scoring/
│       └── engine.py           # score_player(), score_consistency()
├── tests/
│   ├── test_api.py             # 13 tests — OAuth2, roster, rankings, utility, spell_ids, report players/timerange, guild_reports
│   ├── test_config.py          # 19 tests — load, get_spec, update_target, get_consumables, all_specs, attendance CRUD
│   ├── test_scoring.py         # 12 tests — weighted scoring, consumables_weight, optional flag
│   ├── test_attendance.py      # 7 tests — group_reports_by_week, check_player_attendance
│   └── test_gear.py            # 11 tests — gear quality, enchant, gem, ilvl checks
├── config.yaml                 # Officer-maintained class:spec profiles
├── .env.example                # Template for required environment variables
├── requirements.txt            # Python dependencies
├── pytest.ini                  # pythonpath=., asyncio_mode=auto
└── README.md                   # Setup guide and command reference
```

## Tech Stack

- Python 3.11+
- discord.py 2.3.2 (slash commands via `app_commands`)
- aiohttp 3.9.1 (async HTTP + WarcraftLogs API)
- pyyaml 6.0.1 (config.yaml)
- python-dotenv 1.0.0 (`.env` file)
- pytest + pytest-asyncio (67 tests, all passing)

## Environment Variables (see .env.example)

| Variable | Description |
|---|---|
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `WARCRAFTLOGS_CLIENT_ID` | WCL OAuth2 client ID |
| `WARCRAFTLOGS_CLIENT_SECRET` | WCL OAuth2 client secret |
| `GUILD_NAME` | WoW guild name |
| `GUILD_SERVER` | Server slug (e.g. `stormrage`) |
| `GUILD_REGION` | Region (default: `US`) |
| `OFFICER_ROLE_NAME` | Discord role name for officers (default: `Officer`) |
| `DEV_GUILD_ID` | (Optional) Discord server ID for fast slash command sync during dev |

## Scoring System

```
score = (utility_score × utility_weight) + (parse_percentile × parse_weight) + (consumables_score × consumables_weight)
```

- `utility_score` = average of per-metric scores, each capped at 100
- `consumables_score` = average of non-optional consumable metric scores, each capped at 100
- Each metric score = `min(actual / target, 1.0) × 100`
- `consumables_weight` defaults to `0.00` on all specs — consumables are informational only until an officer raises it
- Metrics with `optional: true` are shown in reports but never included in any score calculation (used for profession-gated items like Engineering explosives or LW drums, and situational items like Dark/Demonic Runes)
- If a spec has no `contributions`, parse is the entire score (weights ignored)
- Unconfigured specs fall back to `{"utility_weight": 0.0, "parse_weight": 1.0, "contributions": []}` — pure parse
- All three weights must sum to `1.0`

## config.yaml Format

Keyed by `class:spec`. Officers configure weights and contributions per spec. A top-level `consumables:` key holds the global consumables list (not a spec).

```yaml
warrior:protection:
  utility_weight: 0.75
  parse_weight: 0.25
  consumables_weight: 0.00   # raise this (and lower parse_weight) to score consumables
  contributions:
    - metric: sunder_armor_uptime
      label: "Sunder Armor"
      spell_id: 7386
      type: uptime       # queries WCL Debuffs table
      target: 90         # % uptime target
    - metric: thunderclap_count
      label: "Thunderclap"
      spell_id: 6343
      type: count        # queries WCL Casts table
      target: 15

warrior:fury:
  utility_weight: 0.30
  parse_weight: 0.70
  consumables_weight: 0.00
  contributions:
    - metric: battle_shout_uptime
      label: "Battle Shout"
      spell_id: 6673
      type: uptime
      subtype: buff      # IMPORTANT: queries Buffs table (not Debuffs)
      target: 95

consumables:
  - metric: flask_uptime
    label: "Flask"
    spell_ids: [17628, 17627, 28518, 28520, 28521]   # matches any flask buff
    type: uptime
    subtype: buff
    target: 100
  - metric: sapper_count
    label: "Goblin Sapper"
    spell_id: 13241
    type: count
    target: 2
    optional: true   # Engineering only — shown in display, never affects score
```

**Important:** Use `subtype: buff` for buff spells. Without it, WCL's Debuffs endpoint is queried, which won't find buffs.

**`spell_ids` list:** Use instead of `spell_id` when a metric can match any of several spell IDs (e.g. flasks, elixirs, drums). The API client checks `entry["id"] in spell_ids`.

**`optional: true`:** Metric is displayed in reports but excluded from score calculations. Use for profession-gated items (Engineering, Leatherworking) and situational consumables (Dark/Demonic Runes).

**`gear_check:` key:** A top-level key with gear validation thresholds. Used by `/gearcheck` and `/raidrecap` gear summary.

```yaml
gear_check:
  min_avg_ilvl: 100
  min_quality: 3          # 2=green, 3=blue, 4=epic
  check_enchants: true
  check_gems: true
  enchant_slots: [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]   # WoW slot IDs that should be enchanted
```

**`attendance:` key:** A top-level key listing raid zones and their weekly clear requirements. Officers manage this via `/setattendance` or by editing `config.yaml` directly.

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

**Configured specs (22 total):** warrior:protection, warrior:fury, warrior:arms, paladin:holy, paladin:protection, paladin:retribution, rogue:combat, hunter:beast mastery, hunter:survival, shaman:restoration, shaman:elemental, shaman:enhancement, druid:feral, druid:restoration, druid:balance, mage:arcane, mage:fire, warlock:affliction, warlock:destruction, priest:holy, priest:discipline, priest:shadow

## Key TBC Spell IDs

| Spell | ID | Notes |
|---|---|---|
| Sunder Armor | 7386 | Warrior debuff |
| Demoralizing Shout | 25203 | TBC max rank (not 1160 rank 1) |
| Thunderclap | 6343 | Warrior AoE |
| Battle Shout | 6673 | Warrior buff — use `subtype: buff` |
| Expose Armor | 8647 | Rogue debuff |
| Faerie Fire (Feral) | 16857 | Druid debuff (feral form) |
| Faerie Fire | 770 | Druid debuff (caster form — Balance) |
| Curse of Elements | 27228 | TBC max rank (not 1490 rank 1) |
| Remove Curse (Mage) | 475 | Mage utility — tracked as count |
| Remove Curse (Druid) | 2782 | Druid utility — tracked as count |
| Misdirection | 34477 | Hunter — tracked as count |
| Expose Weakness | 34503 | Survival Hunter proc debuff — tracked as uptime |
| Hunter's Mark | 14325 | Hunter debuff |
| Judgement | 20271 | Paladin — tracked as count |
| Cleanse | 4987 | Paladin dispel — tracked as count |
| Blessing of Kings | 20217 | Paladin buff — use `subtype: buff` |
| Blessing of Might | 25291 | Paladin buff — use `subtype: buff` |
| Devotion Aura | 10293 | Paladin buff — use `subtype: buff` |
| Windfury Totem | 25587 | Shaman buff (rank 5) — use `subtype: buff` |
| Mana Spring Totem | 25570 | Shaman buff (rank 5) — use `subtype: buff` |
| Wrath of Air Totem | 3738 | Shaman buff (spell haste) — use `subtype: buff` |
| Totem of Wrath | 30706 | Elemental Shaman buff — use `subtype: buff` |
| Grace of Air Totem | 25359 | Shaman buff (rank 3) — use `subtype: buff` |
| Strength of Earth Totem | 25361 | Shaman buff (rank 6) — use `subtype: buff` |
| Purge | 370 | Shaman dispel — tracked as count |
| Innervate | 29166 | Druid — tracked as count |
| Abolish Poison | 2893 | Druid — tracked as count |
| Fire Vulnerability | 22959 | Improved Scorch debuff (Fire Mage) |
| Dispel Magic | 527 | Priest — tracked as count |
| Power Word: Fortitude | 25392 | Priest buff (TBC max rank) — use `subtype: buff` |
| Abolish Disease | 552 | Priest — tracked as count |
| Shadow Weaving | 15258 | Shadow Priest debuff |
| Misery | 33198 | Shadow Priest debuff |
| Vampiric Embrace | 15286 | Shadow Priest buff — use `subtype: buff` |

**Consumable spell IDs (see config.yaml for full lists):**

| Item | ID(s) | Type |
|---|---|---|
| Flask of Supreme Power | 17628 | uptime, subtype: buff |
| Flask of Relentless Assault | 28520 | uptime, subtype: buff |
| Flask of Fortification | 28518 | uptime, subtype: buff |
| Flask of Distilled Wisdom | 17627 | uptime, subtype: buff |
| Haste Potion | 28507 | count |
| Destruction Potion | 28508 | count |
| Super Mana Potion | 28499 | count |
| Dark Rune | 27869 | count, optional: true |
| Demonic Rune | 12662 | count, optional: true |
| Drums (all types) | 35476, 35475, 35478, 35477 | count, optional: true |
| Goblin Sapper Charge | 13241 | count, optional: true |
| Grenades / Bombs | 30216, 30217, 19769 | count, optional: true |

## WarcraftLogs Zone IDs (TBC)

- **The Eye (Tempest Keep):** 1007 — update `TBC_ZONE_ID` in `src/bot.py` as the guild progresses

## Discord Commands

| Command | Access | Description |
|---|---|---|
| `/topconsistent [weeks]` | All | Ranks guild members by consistency score (default: last 4 weeks) |
| `/player <character> [log_url]` | All | Per-boss parse + utility breakdown; add a log URL to include consumables |
| `/raidrecap <log_url>` | All | Scores standout performers in a report; includes consumables section |
| `/setconfig <spec> <metric> <target>` | Officers only | Updates a target value in config.yaml |
| `/attendance <character> [weeks]` | All | Per-player raid attendance report |
| `/attendancereport [weeks]` | All | Guild-wide attendance summary |
| `/setattendance add/remove/update/list` | Officers only | Manage attendance requirements |
| `/gearcheck <log_url>` | All | Check gear readiness from a raid report |

## Running Tests

```bash
pytest
```

All 67 tests should pass. Tests use mocked WCL API responses — no real credentials needed.

## Running the Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in .env
cp .env.example .env

# Run
python -m src.bot
```

## Known Design Decisions

1. **No worktree** — all development was done directly on `main`. The repo is at `https://github.com/AlexanderRidgway/WarcraftLogs`.
2. **Graceful import loop** — `src/bot.py` uses `importlib` with `try/except ImportError` to register command modules, allowing incremental development without crashes.
3. **Path-independent config** — `ConfigLoader` resolves `config.yaml` relative to `src/bot.py`'s location, not the working directory.
4. **`is_officer` DM guard** — Returns `False` in DM context (no `roles` attribute on user).
5. **`setconfig` uses defer+followup** — Avoids double-response errors in Discord interactions.
6. **`playerMetric: default`** in `/raidrecap` — Uses WCL's default metric so healers and tanks are included (not just DPS).
7. **`get_character_rankings` includes `class` field** — Required so `/player` can build the correct `class:spec` config key.
8. **`consumables_weight: 0.00` default** — All specs default to informational-only consumables. To score them, raise `consumables_weight` and lower `parse_weight` by the same amount so all three weights sum to `1.0`. Use `/setconfig` or edit `config.yaml` directly.
9. **`optional: true` consumables** — Drums (Leatherworking), Goblin Sapper/Grenades (Engineering), Dark Rune, and Demonic Rune are marked optional. They appear in display output but are never included in any score average, so players without those professions or who don't need mana restoration are not penalized.
10. **`spell_ids` list in contributions** — Supports matching any one of multiple spell IDs per metric. Used for flasks (multiple flask types), elixirs, and drums. The `_contrib_matches` helper in `WarcraftLogsClient` handles both `spell_id` (single) and `spell_ids` (list) — backwards compatible.
11. **Consumables fetched from report actors** — `/raidrecap` and `/player` (with `log_url`) use `get_report_players()` to look up source IDs and `get_report_timerange()` for the full report window before querying consumable data. The consumables block is wrapped in `try/except` so failures never surface to the user.
12. **`_format_consumables` and `_extract_report_code` live in `raidrecap.py`** — `/player` imports them from there at call time to avoid circular imports.
13. **Attendance is informational only** — Attendance tracking does not affect player scores. It is a separate reporting tool for officers to monitor raid participation. WCL reports are grouped by ISO week (Monday–Sunday) and compared against per-zone weekly requirements.
14. **Gear data is per-report snapshot** — Gear check uses the equipment snapshot stored in WarcraftLogs reports, not live Armory data. This means it reflects what players actually wore during the raid, not what they have equipped now.
