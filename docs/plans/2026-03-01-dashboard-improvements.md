# Dashboard Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Four improvements: player blacklist for checklist, leaderboard split (parses vs performance score), attendance filter to only show attended raids, and flask/elixir presence-based consumable check.

**Architecture:** Add `active` column to Player model, add `sort_by` param to leaderboard endpoint, filter attendance to attended-only, add `combo_presence` consumable type for flask/elixir check. Frontend changes to Home, Checklist, and PlayerProfile pages.

**Tech Stack:** FastAPI, SQLAlchemy async, React + TanStack Query, PostgreSQL

---

### Task 1: Add `active` column to Player model

**Files:**
- Modify: `web/api/models.py:11-20`
- Modify: `web/api/sync/run.py:19-21`

**Step 1: Add `active` column to Player model**

In `web/api/models.py`, add after line 19 (`region` column):

```python
active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
```

Also add `Boolean` to the import if not already there (it is already imported on line 2).

**Step 2: Add ALTER TABLE migration to sync startup**

In `web/api/sync/run.py`, add after `create_all` (line 21):

```python
# Add 'active' column if it doesn't exist (no Alembic in this project)
from sqlalchemy import text, inspect as sa_inspect
def _add_missing_columns(connection):
    inspector = sa_inspect(connection)
    cols = [c["name"] for c in inspector.get_columns("players")]
    if "active" not in cols:
        connection.execute(text("ALTER TABLE players ADD COLUMN active BOOLEAN NOT NULL DEFAULT true"))

await conn.run_sync(_add_missing_columns)
```

**Step 3: Run tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass (model change is additive with server_default)

**Step 4: Commit**

```bash
git add web/api/models.py web/api/sync/run.py
git commit -m "feat: add active column to Player model for blacklist support"
```

---

### Task 2: Add activate/deactivate endpoints and re-activate on roster sync

**Files:**
- Modify: `web/api/routes/players.py:1-10` (add imports + endpoints)
- Modify: `web/api/sync/worker.py:57-64` (re-activate on roster sync)
- Modify: `web/frontend/src/api/client.ts` (add deactivate call)

**Step 1: Add deactivate/activate endpoints to players.py**

Add at the end of `web/api/routes/players.py`:

```python
@router.post("/{name}/deactivate")
async def deactivate_player(name: str, officer: User = Depends(get_current_officer), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.active = False
    await db.commit()
    return {"status": "ok", "name": name, "active": False}


@router.post("/{name}/activate")
async def activate_player(name: str, officer: User = Depends(get_current_officer), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.active = True
    await db.commit()
    return {"status": "ok", "name": name, "active": True}
```

Add imports at top of `players.py`:
```python
from web.api.auth import get_current_officer
from web.api.models import User
```

**Step 2: Re-activate players on roster sync**

In `web/api/sync/worker.py`, in the `run_roster_sync` method (line 58), add after `existing.last_synced_at = _utcnow()`:

```python
existing.active = True
```

**Step 3: Add API client method**

In `web/frontend/src/api/client.ts`, add to the `players` object:

```typescript
deactivate: (name: string) => postJson(`/players/${name}/deactivate`),
activate: (name: string) => postJson(`/players/${name}/activate`),
```

**Step 4: Run tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

**Step 5: Commit**

```bash
git add web/api/routes/players.py web/api/sync/worker.py web/frontend/src/api/client.ts
git commit -m "feat: add player activate/deactivate endpoints and roster re-activation"
```

---

### Task 3: Filter inactive players from Checklist, Leaderboard, and Attendance

**Files:**
- Modify: `web/api/routes/checklist.py:14`
- Modify: `web/api/routes/leaderboard.py:16-28`
- Modify: `web/api/routes/attendance.py:13-17`

**Step 1: Filter inactive players in checklist**

In `web/api/routes/checklist.py`, change line 14:

```python
# Before:
players_result = await db.execute(select(Player).order_by(Player.name))

# After:
players_result = await db.execute(select(Player).where(Player.active == True).order_by(Player.name))
```

**Step 2: Filter inactive players in leaderboard**

In `web/api/routes/leaderboard.py`, add `Player.active == True` to the where clause. Change line 27:

```python
# Before:
.where(Score.recorded_at >= cutoff)

# After:
.where(Score.recorded_at >= cutoff, Player.active == True)
```

**Step 3: Filter inactive players in attendance**

In `web/api/routes/attendance.py`, add a join filter. Change line 13-16:

```python
# Before:
result = await db.execute(
    select(Player.name, Player.class_name, AttendanceRecord)
    .join(AttendanceRecord, AttendanceRecord.player_id == Player.id)
    .order_by(Player.name, AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
)

# After:
result = await db.execute(
    select(Player.name, Player.class_name, AttendanceRecord)
    .join(AttendanceRecord, AttendanceRecord.player_id == Player.id)
    .where(Player.active == True)
    .order_by(Player.name, AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
)
```

**Step 4: Run tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

**Step 5: Commit**

```bash
git add web/api/routes/checklist.py web/api/routes/leaderboard.py web/api/routes/attendance.py
git commit -m "feat: filter inactive players from checklist, leaderboard, and attendance"
```

---

### Task 4: Add dismiss button to Checklist frontend

**Files:**
- Modify: `web/frontend/src/pages/Checklist.tsx`

**Step 1: Add dismiss button to each player row**

In `web/frontend/src/pages/Checklist.tsx`:

1. Add imports:
```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
```
(Replace the existing `useQuery` import from `@tanstack/react-query`)

2. Inside the `Checklist` component, add after `const [filter, setFilter]`:
```typescript
const queryClient = useQueryClient()
const isOfficer = !!localStorage.getItem('auth_token')

const deactivateMutation = useMutation({
  mutationFn: (name: string) => api.players.deactivate(name),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['checklist'] }),
})
```

3. Add an X button inside each player row, after the `<div className="flex-1 min-w-0">` closing `</div>` (before the outer row's closing `</div>`):
```tsx
{isOfficer && (
  <button
    onClick={(e) => {
      e.stopPropagation()
      if (confirm(`Remove ${p.name} from checklist?`)) deactivateMutation.mutate(p.name)
    }}
    className="ml-2 p-1.5 text-text-muted hover:text-danger transition-colors cursor-pointer bg-transparent border-none flex-shrink-0"
    title={`Remove ${p.name}`}
  >
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  </button>
)}
```

**Step 2: Commit**

```bash
git add web/frontend/src/pages/Checklist.tsx
git commit -m "feat: add dismiss button to checklist for officers"
```

---

### Task 5: Split Leaderboard into Parse and Performance Score tabs

**Files:**
- Modify: `web/api/routes/leaderboard.py`
- Modify: `web/frontend/src/pages/Home.tsx`

**Step 1: Add `sort_by` param to leaderboard endpoint**

Replace the entire `web/api/routes/leaderboard.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Score

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def leaderboard(
    weeks: int = Query(default=4, ge=1, le=52),
    sort_by: str = Query(default="parse"),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)

    order_col = func.avg(Score.parse_score) if sort_by == "parse" else func.avg(Score.overall_score)

    result = await db.execute(
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.count(Score.id).label("fight_count"),
            func.max(Score.spec).label("spec"),
        )
        .join(Score, Score.player_id == Player.id)
        .where(Score.recorded_at >= cutoff, Player.active == True)
        .group_by(Player.name, Player.class_name)
        .order_by(order_col.desc())
    )
    rows = result.all()

    return [
        {
            "rank": i + 1,
            "name": r.name,
            "class_name": r.class_name,
            "spec": r.spec,
            "avg_score": round(r.avg_score, 1),
            "avg_parse": round(r.avg_parse, 1),
            "fight_count": r.fight_count,
        }
        for i, r in enumerate(rows)
    ]
```

**Step 2: Add tab switcher to Home.tsx**

In `web/frontend/src/pages/Home.tsx`:

1. Add state for the active tab after `const [sortAsc, setSortAsc]` (line 50):
```typescript
const [leaderboardTab, setLeaderboardTab] = useState<'parse' | 'score'>('parse')
```

2. Update the query to include `leaderboardTab`:
```typescript
const { data: leaderboard, isLoading } = useQuery({
  queryKey: ['leaderboard', weeks, leaderboardTab],
  queryFn: () => api.leaderboard(weeks, leaderboardTab),
})
```

3. Update `SortKey` type:
```typescript
type SortKey = 'rank' | 'avg_score' | 'avg_parse' | 'fight_count'
```

4. Add the tab switcher in the JSX. Replace the header `<h1>` with:
```tsx
<h1 className="text-2xl font-bold text-text-primary">Guild Leaderboard</h1>
```

Then add tab buttons right after the header div (after closing `</div>` of the header flex):

```tsx
{/* Leaderboard tabs */}
<div className="flex gap-1 mb-5">
  <button
    onClick={() => setLeaderboardTab('parse')}
    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer border ${
      leaderboardTab === 'parse'
        ? 'border-accent-gold bg-accent-gold/10 text-accent-gold'
        : 'border-border-default bg-bg-surface text-text-secondary hover:border-border-hover'
    }`}
  >
    Parses
  </button>
  <button
    onClick={() => setLeaderboardTab('score')}
    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer border ${
      leaderboardTab === 'score'
        ? 'border-accent-gold bg-accent-gold/10 text-accent-gold'
        : 'border-border-default bg-bg-surface text-text-secondary hover:border-border-hover'
    }`}
  >
    Performance Score
  </button>
</div>
```

5. Conditionally show/hide the Score column and MVP based on tab. The table header and rows should:
   - **Parse tab:** Show Rank, Player, Spec, Avg Parse, Fights (no Score column, no MVP)
   - **Score tab:** Show Rank, Player, Spec, Score, Avg Parse, Fights (show MVP)

In the `<thead>`:
```tsx
<SortHeader label="Rank" field="rank" />
<th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider">Player</th>
<th className="p-3 text-left text-xs font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Spec</th>
{leaderboardTab === 'score' && <SortHeader label="Score" field="avg_score" />}
<SortHeader label="Avg Parse" field="avg_parse" />
<SortHeader label="Fights" field="fight_count" />
```

In each `<tr>` body row:
```tsx
{leaderboardTab === 'score' && (
  <td className="p-3 text-sm font-semibold text-accent-gold tabular-nums">{entry.avg_score}</td>
)}
```

6. Wrap MVP section with `{leaderboardTab === 'score' && mvp && (...)}`

7. Update `api.leaderboard` in `client.ts`:
```typescript
leaderboard: (weeks = 4, sortBy = 'parse') => fetchJson<import('./types').LeaderboardEntry[]>(`/leaderboard?weeks=${weeks}&sort_by=${sortBy}`),
```

**Step 3: Run tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add web/api/routes/leaderboard.py web/frontend/src/pages/Home.tsx web/frontend/src/api/client.ts
git commit -m "feat: split leaderboard into parse and performance score tabs"
```

---

### Task 6: Filter player attendance to only show attended raids

**Files:**
- Modify: `web/api/routes/players.py:182-197`

**Step 1: Filter attendance response**

In `web/api/routes/players.py`, in the `get_player_attendance` endpoint, change the loop that builds `weeks_data` (lines 183-195):

```python
weeks_data = {}
for r in records:
    # Only include zones the player actually attended
    if r.clear_count == 0:
        continue
    key = (r.year, r.week_number)
    if key not in weeks_data:
        weeks_data[key] = {"year": r.year, "week": r.week_number, "zones": []}
    reports = report_lookup.get((r.year, r.week_number, r.zone_id), [])
    weeks_data[key]["zones"].append({
        "zone_id": r.zone_id,
        "zone_label": r.zone_label,
        "clear_count": r.clear_count,
        "required": r.required,
        "met": r.met,
        "reports": reports,
    })
```

This skips zones with `clear_count == 0`, and since weeks with zero attendance across all zones will have no entries added, they'll be skipped entirely.

**Step 2: Run tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

**Step 3: Commit**

```bash
git add web/api/routes/players.py
git commit -m "feat: filter player attendance to only show attended raids"
```

---

### Task 7: Add `combo_presence` consumable type for flask/elixir check

**Files:**
- Modify: `src/api/warcraftlogs.py:208-259` (add combo_presence handling)
- Modify: `config.yaml:444-464` (replace 3 metrics with 1)
- Modify: `web/api/sync/reports.py:143-167` (handle combo_presence in consumables processing)

**Step 1: Add `check_combo_presence` method to WarcraftLogsClient**

In `src/api/warcraftlogs.py`, add a new method after `get_utility_data` (after line 259):

```python
async def check_combo_presence(
    self,
    report_code: str,
    source_id: int,
    start: int,
    end: int,
    contrib: dict,
) -> float:
    """Check if a player has either a Flask OR (Battle Elixir + Guardian Elixir).

    Returns 100.0 if present, 0.0 if not.
    """
    buff_data = await self._query_table(report_code, source_id, start, end, "Buffs")
    auras = buff_data.get("auras", [])

    def _has_any(ids: list[int]) -> bool:
        return any(
            (a.get("guid") or a.get("id")) in ids and a.get("totalUptime", 0) > 0
            for a in auras
        )

    # Check flasks first
    if _has_any(contrib.get("flask_ids", [])):
        return 100.0

    # Check battle + guardian elixir combo
    has_battle = _has_any(contrib.get("battle_elixir_ids", []))
    has_guardian = _has_any(contrib.get("guardian_elixir_ids", []))
    if has_battle and has_guardian:
        return 100.0

    return 0.0
```

**Step 2: Handle `combo_presence` in consumables processing**

In `web/api/sync/reports.py`, in the consumables loop (around line 145-167), change the consumables block. Replace the entire consumables section:

```python
# Consumables data
player_consumables = []
if consumables_profile and name in source_map:
    try:
        # Separate combo_presence from standard consumables
        standard_consumes = [c for c in consumables_profile if c.get("type") != "combo_presence"]
        combo_consumes = [c for c in consumables_profile if c.get("type") == "combo_presence"]

        # Fetch standard consumables via get_utility_data
        c_data = {}
        if standard_consumes:
            c_data = await wcl.get_utility_data(
                report_code, source_map[name],
                timerange["start"], timerange["end"],
                standard_consumes,
            )

        # Fetch combo_presence consumables
        for combo in combo_consumes:
            value = await wcl.check_combo_presence(
                report_code, source_map[name],
                timerange["start"], timerange["end"],
                combo,
            )
            c_data[combo["metric"]] = value

        for cons in consumables_profile:
            metric = cons["metric"]
            actual = c_data.get(metric, 0)
            entry = {
                "player_name": name,
                "report_code": report_code,
                "metric_name": metric,
                "label": cons["label"],
                "actual_value": actual,
                "target_value": cons["target"],
                "optional": cons.get("optional", False),
            }
            player_consumables.append(entry)
            consumables_entries.append(entry)
    except Exception:
        logger.warning("Failed to fetch consumables for %s in %s", name, report_code)
```

**Step 3: Update config.yaml**

Replace the three flask/elixir entries in `config.yaml` (lines 445-464):

```yaml
consumables:
  - metric: flask_or_elixir
    label: "Flask / Elixirs"
    type: combo_presence
    flask_ids: [17628, 17627, 28518, 28520, 28521]
    battle_elixir_ids: [28490, 28491, 28493, 28494, 28497, 17538, 17539, 28543]
    guardian_elixir_ids: [39625, 39627, 39628, 28502, 28503]
    target: 100
```

Remove the old `flask_uptime`, `battle_elixir_uptime`, and `guardian_elixir_uptime` entries entirely.

**Step 4: Run tests**

Run: `python -m pytest tests/ -q`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/api/warcraftlogs.py web/api/sync/reports.py config.yaml
git commit -m "feat: add combo_presence consumable type for flask/elixir check"
```

---

### Task 8: Deploy and force resync

After all code changes are committed and pushed:

**Step 1: Push to main**
```bash
git push
```

**Step 2: Wait for deploy**
Monitor with: `gh run list --limit 3`

**Step 3: Verify new code deployed**
Check that the `active` column migration runs and the new `check_combo_presence` method exists on the server.

**Step 4: Force resync**
Trigger a force resync to re-process all reports with the new flask/elixir logic and populate the `active` column.
