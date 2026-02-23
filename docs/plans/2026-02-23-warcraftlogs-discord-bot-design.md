# WarcraftLogs Discord Bot — Design Document

**Date:** 2026-02-23
**Context:** TBC (The Burning Crusade) guild officer tool for identifying outstanding raiders to reward with loot priority.

---

## Goal

Build a Discord bot that analyzes WarcraftLogs raid data to help officers identify consistently outstanding performers. Performance is measured by a weighted combination of parse percentile and utility/buff/debuff contribution, with weights and targets fully configurable per class and specialization.

---

## Architecture

```
Discord Server
    └── Officer types slash command
            │
            ▼
    discord.py Bot (Python)
            │
            ├── /topconsistent  ──┐
            ├── /player <name>  ──┼──► WarcraftLogs GraphQL API
            ├── /raidrecap <url>──┘          │
            └── /setconfig ...          Returns parse + cast
                                        data per boss/player
                                             │
                                             ▼
                                    Consistency Scorer
                                    (weighted utility +
                                     parse percentile)
                                             │
                                             ▼
                                    Formatted Discord Embed
```

- Single Python process using `discord.py`
- Data fetched live from WarcraftLogs GraphQL API on each command — no database in v1
- WarcraftLogs API credentials obtained via https://www.warcraftlogs.com/api/clients/

---

## Scoring System

Each player's score is computed per boss attempt, then averaged across recent raids to produce a **consistency score**.

**Formula:**
```
score = (utility_score × utility_weight) + (parse_percentile × parse_weight)
```
Normalized to 100. Weights and targets are defined per `class:spec` in `config.yaml`.

### Why utility-first?

In TBC, raid-wide debuffs and buffs (Sunder Armor, Expose Armor, Faerie Fire, Curse of Elements, etc.) have an outsized impact on overall raid performance. A player fulfilling their utility role fully is considered more valuable than raw DPS numbers alone suggest. Classes with lower utility toolkits are weighted more heavily on parse performance to compensate.

---

## Configuration (`config.yaml`)

Officers maintain a `config.yaml` file keyed by `class:spec`. Each entry defines:
- `utility_weight` — fraction of score derived from utility metrics
- `parse_weight` — fraction of score derived from parse percentile
- `contributions` — list of metrics to track, with labels and target thresholds

**Example:**
```yaml
warrior:protection:
  utility_weight: 0.75
  parse_weight: 0.25
  contributions:
    - metric: sunder_armor_uptime
      label: "Sunder Armor"
      target: 90        # % uptime expected
    - metric: demoralizing_shout_uptime
      label: "Demo Shout"
      target: 85
    - metric: thunderclap_count
      label: "Thunderclap"
      target: 15        # casts per boss

warrior:fury:
  utility_weight: 0.40
  parse_weight: 0.60
  contributions:
    - metric: battle_shout_uptime
      label: "Battle Shout"
      target: 95
    - metric: demoralizing_shout_uptime
      label: "Demo Shout"
      target: 75

rogue:combat:
  utility_weight: 0.55
  parse_weight: 0.45
  contributions:
    - metric: expose_armor_uptime
      label: "Expose Armor"
      target: 85

mage:arcane:
  utility_weight: 0.20
  parse_weight: 0.80
  contributions:
    - metric: amplify_curse_uptime
      label: "Amplify Curse"
      target: 60
```

---

## Commands

| Command | Description | Access |
|---|---|---|
| `/topconsistent [weeks]` | Ranks raiders by consistency score over N recent raids | Officer |
| `/player <name>` | Individual breakdown: utility + parse scores per boss | Officer |
| `/raidrecap <log-url>` | Standout performers from a specific raid log | Officer |
| `/setconfig <spec> <metric> <target>` | Update a target value in config | Officer role only |

### `/setconfig` example
```
/setconfig warrior:protection sunder_armor_uptime 95
→ ✅ Updated warrior:protection › sunder_armor_uptime target: 90 → 95
```

Access control: gated to Discord officer role. Non-officers receive a silent permission denied message.

---

## Data Flow

```
/player Thrallbro-Stormrage
        │
        ▼
1. Look up character on WarcraftLogs API
   → Fetch recent raid logs where character appears
        │
        ▼
2. For each log/boss, pull:
   → Parse percentile (vs. class+spec worldwide)
   → Cast counts / uptime data for configured utility metrics
        │
        ▼
3. Score each boss attempt using config weights
   → Average across recent raids for consistency score
        │
        ▼
4. Post formatted Discord embed with results
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Character not found on WarcraftLogs | Friendly message with spelling tip |
| Character has no recent logs | Notifies officer, shows last-seen date if available |
| WarcraftLogs API down / rate-limited | Clear error message, no silent failures |
| Spec not present in config | Warns officer, shows parse-only score |
| `/setconfig` used by non-officer | Permission denied message |

---

## Roster Source

The bot pulls the guild's raider roster automatically from the guild's WarcraftLogs page via the API, eliminating manual roster maintenance.

---

## Tech Stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| Discord library | discord.py |
| WarcraftLogs data | WarcraftLogs GraphQL API |
| Config format | YAML (`config.yaml`) |
| Deployment | Single Python process (local or VPS) |

---

## Out of Scope (v1)

- Database / historical data persistence
- Automated weekly reports
- Web dashboard
- Recruitment applicant analysis
