# Dashboard Improvements Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Four improvements: player blacklist for checklist, leaderboard split (parses vs performance score), attendance filter to only show attended raids, and flask/elixir presence-based consumable check.

**Architecture:** Backend changes to Player model, leaderboard/checklist/attendance endpoints, consumables sync logic. Frontend changes to Checklist, Home (leaderboard), and PlayerProfile pages.

**Tech Stack:** FastAPI, SQLAlchemy async, React, TanStack Query

---

## Feature 1: Player Blacklist

### Problem
Former guild members still appear in the Checklist tab and other list views.

### Design
- Add `active: bool = True` column to `Player` model via Alembic migration
- Add `POST /api/players/{name}/deactivate` and `POST /api/players/{name}/activate` officer-only endpoints
- Filter `WHERE Player.active == True` in Checklist, Leaderboard, and Attendance list endpoints
- Individual player profile (`/player/{name}`) still accessible for historical data
- Roster sync: if a player reappears in the WCL guild roster, set `active = True`
- Frontend: add a small dismiss/X button on each player row in Checklist (officer-only, calls deactivate endpoint)

### Files
- `web/api/models.py` — add `active` column
- `web/api/routes/checklist.py` — filter active players
- `web/api/routes/leaderboard.py` — filter active players
- `web/api/routes/attendance.py` — filter active players
- `web/api/routes/players.py` — add activate/deactivate endpoints
- `web/api/sync/roster.py` — re-activate on roster appearance
- `web/frontend/src/pages/Checklist.tsx` — add dismiss button
- `web/frontend/src/api/client.ts` — add deactivate/activate API calls

---

## Feature 2: Leaderboard Split

### Problem
Leaderboard currently ranks by `overall_score` (weighted parse + utility + consumables). User wants pure parse ranking as primary, with performance score as a separate tab.

### Design
- **"Leaderboard" tab (default):** Rank, Player, Spec, Avg Parse, Fights. Sorted by Avg Parse desc.
- **"Performance Score" tab:** Rank, Player, Spec, Score, Avg Parse, Fights. Sorted by Score desc.
- Backend: add `sort_by` query param to leaderboard endpoint (`parse` or `score`, default `parse`)
- Frontend: add tab switcher above the leaderboard table on Home page
- Both tabs share the same filters (weeks, role, class, search)
- MVP of the Week stays on the Performance Score tab only

### Files
- `web/api/routes/leaderboard.py` — add `sort_by` param
- `web/frontend/src/pages/Home.tsx` — add tab UI, adjust columns per tab

---

## Feature 3: Attendance — Only Show Attended Raids

### Problem
Player attendance tab shows all weeks including ones with zero attendance, making it noisy.

### Design
- Backend: filter attendance records to only return zones where `clear_count > 0`
- Skip entire weeks where the player has zero clears across all zones
- Within a shown week, only show zones the player actually attended (clear_count > 0)

### Files
- `web/api/routes/players.py` — filter attendance response

---

## Feature 4: Flask/Elixir Presence Check

### Problem
WCL reports flask uptime as percentage of fight time, which shows misleadingly low values even when a flask was used the entire raid (due to death time, pre-pull gaps, etc.). Also, some players use Battle + Guardian Elixir combos instead of Flasks.

### Design
Replace the three separate consumable metrics (`flask_uptime`, `battle_elixir_uptime`, `guardian_elixir_uptime`) with a single combined presence check.

**New consumable config:**
```yaml
- metric: flask_or_elixir
  label: "Flask / Elixirs"
  type: combo_presence
  flask_ids: [17628, 17627, 28518, 28520, 28521]
  battle_elixir_ids: [28490, 28491, 28493, 28494, 28497, 17538, 17539, 28543]
  guardian_elixir_ids: [39625, 39627, 39628, 28502, 28503]
  target: 100
```

**Sync logic for `combo_presence` type:**
1. Query WCL Buffs table for the player in the report
2. Check if any `flask_ids` buff appeared (uptime > 0) → pass
3. If no flask, check if ANY `battle_elixir_ids` buff appeared AND ANY `guardian_elixir_ids` buff appeared → pass
4. Otherwise → fail
5. Store `actual_value = 100` (pass) or `0` (fail)

**Remove** the old `flask_uptime`, `battle_elixir_uptime`, `guardian_elixir_uptime` entries from config.yaml.

### Files
- `config.yaml` — replace 3 metrics with 1 `combo_presence` metric
- `src/api/warcraftlogs.py` — add `combo_presence` handling in `get_utility_data`
- `web/api/sync/reports.py` — handle new metric type in consumables processing
