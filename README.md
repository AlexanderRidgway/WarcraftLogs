# WarcraftLogs Guild Bot

A Discord bot for TBC guild officers to analyze raid performance and identify outstanding raiders for loot priority.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Get WarcraftLogs API credentials: https://www.warcraftlogs.com/api/clients/
3. Create a Discord bot: https://discord.com/developers/applications
4. Copy `.env.example` to `.env` and fill in all values
5. Edit `config.yaml` to configure your specs and utility metrics
6. Run the bot: `python -m src.bot`

## Commands

### `/topconsistent [weeks]`
Ranks all guild members by consistency score over the last N weeks (default: 4).

```
/topconsistent
/topconsistent weeks:8
```

### `/player <character> [log_url]`
Shows a per-boss parse and utility breakdown for one player. Optionally pass a WarcraftLogs report URL to also display consumable usage from that specific raid.

```
/player Thrallbro-Stormrage
/player Thrallbro-Stormrage log_url:https://www.warcraftlogs.com/reports/ABC12345
```

### `/raidrecap <log_url>`
Shows standout performers from a specific raid report, scored by parse + utility. Also displays a consumables section for each standout player.

```
/raidrecap https://www.warcraftlogs.com/reports/ABC12345
```

### `/setconfig <spec> <metric> <target>` *(Officers only)*
Updates a metric target value in `config.yaml` without restarting the bot.

```
/setconfig warrior:protection sunder_armor_uptime 95
/setconfig priest:shadow misery_uptime 80
/setconfig warrior:protection consumables_weight 0.10
```

### `/attendance <character> [weeks]`
Shows a player's raid attendance over the last N weeks (default: 4). Displays per-zone check/cross marks for each week.

```
/attendance Thrallbro
/attendance Thrallbro weeks:8
```

### `/attendancereport [weeks]`
Shows a guild-wide attendance summary over the last N weeks (default: 4). Lists players who missed required raids and counts those with perfect attendance.

```
/attendancereport
/attendancereport weeks:8
```

### `/setattendance add/remove/update/list` *(Officers only)*
Manage raid attendance requirements. Add or remove zones, update the required number of clears per week, or list the current configuration.

```
/setattendance add zone_id:1002 label:Karazhan required_per_week:1
/setattendance remove zone_id:1002
/setattendance update zone_id:1002 required_per_week:2
/setattendance list
```

## Consumables Tracking

All specs have `consumables_weight: 0.00` by default — consumables are shown as **informational only** and do not affect scores. To enable scoring, raise `consumables_weight` (and lower `parse_weight` by the same amount) so all three weights still sum to `1.0`.

**Tracked consumables:**

| Item | Scored by default | Notes |
|---|---|---|
| Flask | Yes (when weight > 0) | Matches any TBC flask buff |
| Battle Elixir | Yes (when weight > 0) | Matches common battle elixirs |
| Guardian Elixir | Yes (when weight > 0) | Matches common guardian elixirs |
| Haste Potion | Yes (when weight > 0) | |
| Destruction Potion | Yes (when weight > 0) | |
| Mana Potion | Yes (when weight > 0) | |
| Dark Rune | Never | Informational only — situational mana recovery |
| Demonic Rune | Never | Informational only — situational mana recovery |
| Drums | Never | Informational only — Leatherworking required |
| Goblin Sapper | Never | Informational only — Engineering required |
| Grenade / Bomb | Never | Informational only — Engineering required |

## Attendance Tracking

The bot tracks raid attendance by fetching guild reports from WarcraftLogs and grouping them by ISO week (Monday through Sunday). Each player's participation is compared against the configured per-zone weekly requirements.

**Default configuration:**

| Zone | Zone ID | Required per week |
|---|---|---|
| Karazhan | 1002 | 1 |
| Gruul's Lair | 1004 | 1 |
| Magtheridon's Lair | 1005 | 1 |

Attendance is **informational only** — it does not affect player scores.

**Adjusting requirements:**
- Use `/setattendance add`, `/setattendance remove`, or `/setattendance update` in Discord
- Or edit the `attendance:` section in `config.yaml` directly and restart the bot

See the **TBC Zone IDs** table below for zone IDs as the guild progresses through content.

## Updating Config

Use `/setconfig` in Discord, or edit `config.yaml` directly and restart the bot.

**Tuning weights example** — to score consumables at 10% for a spec:
```yaml
warrior:fury:
  utility_weight: 0.40
  parse_weight: 0.50   # reduced from 0.60
  consumables_weight: 0.10
```

## TBC Zone IDs (for `TBC_ZONE_ID` in bot.py)

Update this as the guild progresses through content:

| Zone | ID |
|---|---|
| Karazhan | 1002 |
| Gruul's Lair | 1004 |
| Magtheridon's Lair | 1005 |
| Serpentshrine Cavern | 1006 |
| The Eye (Tempest Keep) | 1007 |
| Mount Hyjal | 1008 |
| Black Temple | 1010 |
| Sunwell Plateau | 1011 |

## Running Tests

```bash
pytest
```

All 51 tests should pass. No real credentials needed — all WCL API responses are mocked.
