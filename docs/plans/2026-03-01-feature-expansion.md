# Feature Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 10 features to the CRANK web dashboard — pre-raid checklist, trend graphs, spec comparison, personal improvement suggestions, death log summary, wipe analysis, boss scorecards, roster health dashboard, achievement/badge system, and MVP of the week.

**Architecture:** Incremental expansion on the existing stack. New WCL API queries for fights/deaths/stats are added to the sync pipeline. New database tables store the fight-level data. Recharts provides charting. Each feature is a self-contained slice: new model(s) → new sync logic → new API route(s) → new frontend page/component.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy (backend), React 19 / Tailwind CSS 4 / Recharts (frontend), WarcraftLogs GraphQL API v2

**Design doc:** `docs/plans/2026-03-01-feature-expansion-design.md`

---

## Task 1: New Database Models (fights, deaths, fight_player_stats, badges)

**Files:**
- Modify: `web/api/models.py`
- Test: `tests/test_web_models.py` (new)

**Step 1: Add Fight model to models.py**

Add after the `Report` class:

```python
class Fight(Base):
    __tablename__ = "fights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fight_id: Mapped[int] = mapped_column(Integer, nullable=False)
    encounter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    kill: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    fight_percentage: Mapped[float] = mapped_column(Float, nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)

    deaths: Mapped[list["Death"]] = relationship(back_populates="fight")
    player_stats: Mapped[list["FightPlayerStats"]] = relationship(back_populates="fight")

    __table_args__ = (
        UniqueConstraint("report_code", "fight_id", name="uq_fight_report_fight"),
    )
```

**Step 2: Add Death model**

```python
class Death(Base):
    __tablename__ = "deaths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fight_db_id: Mapped[int] = mapped_column(ForeignKey("fights.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    killing_ability: Mapped[str] = mapped_column(String(100), nullable=True)
    damage_taken: Mapped[int] = mapped_column(Integer, nullable=True)

    fight: Mapped["Fight"] = relationship(back_populates="deaths")
    player: Mapped["Player"] = relationship()
```

**Step 3: Add FightPlayerStats model**

```python
class FightPlayerStats(Base):
    __tablename__ = "fight_player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fight_db_id: Mapped[int] = mapped_column(ForeignKey("fights.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    dps: Mapped[float] = mapped_column(Float, nullable=True)
    hps: Mapped[float] = mapped_column(Float, nullable=True)
    damage_done: Mapped[int] = mapped_column(Integer, nullable=True)
    healing_done: Mapped[int] = mapped_column(Integer, nullable=True)
    deaths_count: Mapped[int] = mapped_column(Integer, default=0)

    fight: Mapped["Fight"] = relationship(back_populates="player_stats")
    player: Mapped["Player"] = relationship()

    __table_args__ = (
        UniqueConstraint("fight_db_id", "player_id", name="uq_fight_player_stats"),
    )
```

**Step 4: Add Badge model**

```python
class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    badge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    details: Mapped[str] = mapped_column(String(255), nullable=True)

    player: Mapped["Player"] = relationship()

    __table_args__ = (
        UniqueConstraint("player_id", "badge_type", "details", name="uq_badge_player_type_details"),
    )
```

**Step 5: Add Boolean import and update Player relationships**

Add `Boolean` to the imports from sqlalchemy. Add relationships to the Player class:

```python
fights_deaths: Mapped[list["Death"]] = relationship(back_populates="player", viewonly=True)
badges: Mapped[list["Badge"]] = relationship(back_populates="player", viewonly=True)
```

Note: Don't add back_populates for Death and FightPlayerStats on Player since those go through Fight — use viewonly relationships or skip them.

**Step 6: Write test to verify models can be created**

Create `tests/test_web_models.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from web.api.models import Base, Player, Fight, Death, FightPlayerStats, Badge


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_fight_and_death_models(db):
    player = Player(name="TestPlayer", class_id=1, class_name="warrior", server="test", region="US")
    db.add(player)
    await db.flush()

    fight = Fight(
        report_code="TEST123", fight_id=1, encounter_name="Gruul",
        kill=True, duration_ms=180000, fight_percentage=0,
        start_time=0, end_time=180000,
    )
    db.add(fight)
    await db.flush()

    death = Death(
        fight_db_id=fight.id, player_id=player.id,
        timestamp_ms=90000, killing_ability="Shatter", damage_taken=15000,
    )
    db.add(death)

    stats = FightPlayerStats(
        fight_db_id=fight.id, player_id=player.id,
        dps=1200.5, hps=0, damage_done=216090, healing_done=0, deaths_count=1,
    )
    db.add(stats)

    badge = Badge(
        player_id=player.id, badge_type="parse_god",
        details="99.8% on Gruul",
    )
    db.add(badge)

    await db.commit()
    assert fight.id is not None
    assert death.id is not None
    assert stats.id is not None
    assert badge.id is not None
```

**Step 7: Run tests**

```bash
pytest tests/test_web_models.py -v
```

**Step 8: Commit**

```bash
git add web/api/models.py tests/test_web_models.py
git commit -m "feat: add Fight, Death, FightPlayerStats, Badge database models"
```

---

## Task 2: New WCL API Queries (fights, deaths, damage, healing)

**Files:**
- Modify: `src/api/warcraftlogs.py`
- Test: `tests/test_api.py` (add tests)

**Step 1: Add `get_report_fights` method**

Add to `WarcraftLogsClient` class:

```python
async def get_report_fights(self, report_code: str) -> list:
    """Fetch all boss fights for a report (excludes trash)."""
    gql = """
    query($code: String!) {
      reportData {
        report(code: $code) {
          fights(killType: Encounters) {
            id
            name
            kill
            startTime
            endTime
            fightPercentage
            encounterID
          }
        }
      }
    }
    """
    result = await self.query(gql, {"code": report_code})
    report = result.get("reportData", {}).get("report")
    if not report:
        return []
    return report.get("fights", [])
```

**Step 2: Add `get_report_deaths` method**

```python
async def get_report_deaths(self, report_code: str, start: float, end: float) -> list:
    """Fetch death events for a time window. Returns list of death entries."""
    data = await self._query_table(report_code, None, start, end, "Deaths")
    return data.get("entries", [])
```

**Step 3: Add `get_fight_stats` method**

This queries DamageDone and Healing for a specific fight window and returns per-player totals:

```python
async def get_fight_stats(self, report_code: str, start: float, end: float) -> dict:
    """Fetch per-player damage and healing for a fight time window.

    Returns: {player_name: {damage_done, healing_done, dps, hps}}
    """
    duration_s = (end - start) / 1000.0
    if duration_s <= 0:
        return {}

    dmg_data = await self._query_table(report_code, None, start, end, "DamageDone")
    heal_data = await self._query_table(report_code, None, start, end, "Healing")

    stats = {}
    for entry in dmg_data.get("entries", []):
        if entry.get("type") != "Player":
            continue
        name = entry["name"]
        total = entry.get("total", 0)
        stats[name] = {
            "damage_done": total,
            "dps": round(total / duration_s, 1) if duration_s > 0 else 0,
            "healing_done": 0,
            "hps": 0,
        }

    for entry in heal_data.get("entries", []):
        if entry.get("type") != "Player":
            continue
        name = entry["name"]
        total = entry.get("total", 0)
        if name not in stats:
            stats[name] = {"damage_done": 0, "dps": 0, "healing_done": 0, "hps": 0}
        stats[name]["healing_done"] = total
        stats[name]["hps"] = round(total / duration_s, 1) if duration_s > 0 else 0

    return stats
```

**Step 4: Write tests with mocked API responses**

Add to `tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_get_report_fights(mock_client):
    mock_client._mock_response = {
        "reportData": {
            "report": {
                "fights": [
                    {"id": 1, "name": "Gruul", "kill": True, "startTime": 0,
                     "endTime": 180000, "fightPercentage": 0, "encounterID": 649},
                    {"id": 2, "name": "Maulgar", "kill": False, "startTime": 200000,
                     "endTime": 350000, "fightPercentage": 45.2, "encounterID": 650},
                ]
            }
        }
    }
    fights = await mock_client.get_report_fights("TEST")
    assert len(fights) == 2
    assert fights[0]["name"] == "Gruul"
    assert fights[0]["kill"] is True
    assert fights[1]["kill"] is False


@pytest.mark.asyncio
async def test_get_report_deaths(mock_client):
    mock_client._mock_response = {
        "reportData": {
            "report": {
                "table": {
                    "data": {
                        "entries": [
                            {"name": "Thrall", "id": 3, "type": "Player",
                             "deathTime": 145000,
                             "damage": {"total": 25000, "entries": [
                                 {"ability": {"name": "Shatter"}, "amount": 25000}
                             ]}}
                        ]
                    }
                }
            }
        }
    }
    deaths = await mock_client.get_report_deaths("TEST", 0, 180000)
    assert len(deaths) == 1
    assert deaths[0]["name"] == "Thrall"
```

**Step 5: Run tests, commit**

```bash
pytest tests/test_api.py -v
git add src/api/warcraftlogs.py tests/test_api.py
git commit -m "feat: add WCL API queries for fights, deaths, and fight stats"
```

---

## Task 3: Sync Pipeline — Process Fights, Deaths, and Stats

**Files:**
- Modify: `web/api/sync/reports.py` — Add fight/death/stats extraction to `process_report()`
- Modify: `web/api/sync/worker.py` — Store new data, handle force resync cleanup
- Test: `tests/test_web_sync_reports.py` (add tests)

**Step 1: Add fight/death processing to `process_report()` in reports.py**

After the existing gear/utility/consumables extraction, add:

```python
# Fetch fights
fights_raw = await wcl.get_report_fights(report_code)
fights = []
deaths = []
fight_stats = []

for f in fights_raw:
    if f.get("encounterID", 0) == 0:
        continue  # Skip trash
    fight_entry = {
        "report_code": report_code,
        "fight_id": f["id"],
        "encounter_name": f.get("name", "Unknown"),
        "kill": f.get("kill", False),
        "duration_ms": int(f.get("endTime", 0) - f.get("startTime", 0)),
        "fight_percentage": f.get("fightPercentage", 0),
        "start_time": f.get("startTime", 0),
        "end_time": f.get("endTime", 0),
    }
    fights.append(fight_entry)

    # Fetch deaths for this fight
    try:
        death_entries = await wcl.get_report_deaths(report_code, f["startTime"], f["endTime"])
        for d in death_entries:
            if d.get("type") != "Player":
                continue
            killing_ability = None
            damage_taken = None
            if d.get("damage", {}).get("entries"):
                last_hit = d["damage"]["entries"][-1]
                killing_ability = last_hit.get("ability", {}).get("name")
                damage_taken = last_hit.get("amount")
            deaths.append({
                "fight_id": f["id"],
                "player_name": d["name"],
                "timestamp_ms": d.get("deathTime", 0),
                "killing_ability": killing_ability,
                "damage_taken": damage_taken,
            })
    except Exception:
        logger.warning("Failed to fetch deaths for fight %s in %s", f["id"], report_code)

    # Fetch per-player stats for this fight
    try:
        stats = await wcl.get_fight_stats(report_code, f["startTime"], f["endTime"])
        for player_name, s in stats.items():
            # Count deaths for this player in this fight
            player_deaths = sum(1 for d in deaths if d["fight_id"] == f["id"] and d["player_name"] == player_name)
            fight_stats.append({
                "fight_id": f["id"],
                "player_name": player_name,
                "dps": s["dps"],
                "hps": s["hps"],
                "damage_done": s["damage_done"],
                "healing_done": s["healing_done"],
                "deaths_count": player_deaths,
            })
    except Exception:
        logger.warning("Failed to fetch stats for fight %s in %s", f["id"], report_code)
```

Add these to the return dict:

```python
return {
    "rankings": rankings,
    "scores": scores,
    "gear": gear,
    "utility": utility_entries,
    "consumables": consumables_entries,
    "fights": fights,
    "deaths": deaths,
    "fight_stats": fight_stats,
}
```

**Step 2: Store fight data in worker.py `_process_and_store_report()`**

After existing data storage, add:

```python
# Store fights
fight_db_ids = {}  # maps (report_code, fight_id) -> db id
for f in processed["fights"]:
    fight = Fight(**f)
    session.add(fight)
    await session.flush()
    fight_db_ids[f["fight_id"]] = fight.id

# Store deaths
for d in processed["deaths"]:
    db_fight_id = fight_db_ids.get(d["fight_id"])
    player_id = player_ids.get(d["player_name"])
    if db_fight_id and player_id:
        session.add(Death(
            fight_db_id=db_fight_id,
            player_id=player_id,
            timestamp_ms=d["timestamp_ms"],
            killing_ability=d.get("killing_ability"),
            damage_taken=d.get("damage_taken"),
        ))

# Store fight player stats
for s in processed["fight_stats"]:
    db_fight_id = fight_db_ids.get(s["fight_id"])
    player_id = player_ids.get(s["player_name"])
    if db_fight_id and player_id:
        session.add(FightPlayerStats(
            fight_db_id=db_fight_id,
            player_id=player_id,
            dps=s["dps"],
            hps=s["hps"],
            damage_done=s["damage_done"],
            healing_done=s["healing_done"],
            deaths_count=s["deaths_count"],
        ))
```

**Step 3: Add Fight, Death, FightPlayerStats to force resync cleanup**

In `run_reports_sync()`, add deletions before existing ones:

```python
if force:
    async with async_session() as session:
        await session.execute(delete(Death))
        await session.execute(delete(FightPlayerStats))
        await session.execute(delete(Fight))
        # ... existing deletes ...
```

**Step 4: Add imports for new models**

Update imports in `worker.py`:

```python
from web.api.models import (
    Base, Player, Report, Ranking, Score, GearSnapshot,
    UtilityData, ConsumablesData, AttendanceRecord, SyncStatus,
    Fight, Death, FightPlayerStats,
)
```

**Step 5: Run tests, commit**

```bash
pytest tests/ -v
git add web/api/sync/reports.py web/api/sync/worker.py
git commit -m "feat: sync fights, deaths, and per-fight player stats from WCL"
```

---

## Task 4: Install Recharts + Configure Dark Theme

**Files:**
- Modify: `web/frontend/package.json` (via npm install)
- Create: `web/frontend/src/components/ChartTheme.tsx`

**Step 1: Install recharts**

```bash
cd web/frontend && npm install recharts
```

**Step 2: Create chart theme constants**

Create `web/frontend/src/components/ChartTheme.tsx`:

```tsx
// Shared Recharts theme constants matching CRANK dark theme
export const CHART_COLORS = {
  gold: '#c9a959',
  goldLight: '#d4b96a',
  success: '#22c55e',
  danger: '#ef4444',
  info: '#3b82f6',
  text: '#8b95a5',
  textMuted: '#5a6475',
  grid: '#1e2430',
  bg: '#12161f',
}

export const CHART_DEFAULTS = {
  style: { fontSize: 12 },
  tick: { fill: CHART_COLORS.text },
  axisLine: { stroke: CHART_COLORS.grid },
  gridStroke: CHART_COLORS.grid,
}

// Parse color for a percentile value (matches ParseBar colors)
export function parseColor(pct: number): string {
  if (pct >= 99) return '#e268a8'  // legendary/pink
  if (pct >= 95) return '#ff8000'  // orange
  if (pct >= 75) return '#a335ee'  // epic/purple
  if (pct >= 50) return '#0070dd'  // rare/blue
  if (pct >= 25) return '#1eff00'  // uncommon/green
  return '#9d9d9d'                 // common/gray
}
```

**Step 3: Build to verify**

```bash
cd web/frontend && npm run build
```

**Step 4: Commit**

```bash
git add web/frontend/package.json web/frontend/package-lock.json web/frontend/src/components/ChartTheme.tsx
git commit -m "feat: install recharts and add dark theme chart constants"
```

---

## Task 5: Trend Graphs (Player Profile)

**Files:**
- Modify: `web/api/routes/players.py` — Add `/api/players/{name}/trends` endpoint
- Modify: `web/frontend/src/api/client.ts` — Add `api.players.trends()`
- Modify: `web/frontend/src/api/types.ts` — Add `TrendPoint` type
- Create: `web/frontend/src/components/TrendChart.tsx`
- Modify: `web/frontend/src/pages/PlayerProfile.tsx` — Add trend charts to Performance tab

**Step 1: Add trends endpoint to players.py**

```python
@router.get("/{name}/trends")
async def get_player_trends(name: str, weeks: int = Query(default=8, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    scores_result = await db.execute(
        select(Score)
        .where(Score.player_id == player.id, Score.recorded_at >= cutoff)
        .order_by(Score.recorded_at.asc())
    )
    scores = scores_result.scalars().all()

    return [
        {
            "date": s.recorded_at.isoformat() if s.recorded_at else None,
            "report_code": s.report_code,
            "overall_score": round(s.overall_score, 1),
            "parse_score": round(s.parse_score, 1),
            "utility_score": round(s.utility_score, 1) if s.utility_score is not None else None,
            "consumables_score": round(s.consumables_score, 1) if s.consumables_score is not None else None,
        }
        for s in scores
    ]
```

**Step 2: Add frontend type and API method**

In `types.ts`:
```typescript
export interface TrendPoint {
  date: string
  report_code: string
  overall_score: number
  parse_score: number
  utility_score: number | null
  consumables_score: number | null
}
```

In `client.ts`, add to `api.players`:
```typescript
trends: (name: string, weeks = 8) => fetchJson<import('./types').TrendPoint[]>(`/players/${name}/trends?weeks=${weeks}`),
```

**Step 3: Create TrendChart component**

Create `web/frontend/src/components/TrendChart.tsx`:

```tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { CHART_COLORS, CHART_DEFAULTS } from './ChartTheme'
import type { TrendPoint } from '../api/types'

export default function TrendChart({ data }: { data: TrendPoint[] }) {
  const formatted = data.map(d => ({
    ...d,
    label: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  }))

  const hasUtility = data.some(d => d.utility_score !== null)

  return (
    <div className="bg-bg-surface border border-border-default rounded-xl p-4">
      <h3 className="text-sm font-semibold text-text-primary mb-3">Score Trends</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={formatted}>
          <CartesianGrid stroke={CHART_DEFAULTS.gridStroke} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
          <YAxis domain={[0, 100]} tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
          <Tooltip
            contentStyle={{ backgroundColor: CHART_COLORS.bg, border: `1px solid ${CHART_COLORS.grid}`, borderRadius: 8 }}
            labelStyle={{ color: CHART_COLORS.text }}
          />
          <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
          <Line type="monotone" dataKey="overall_score" name="Overall" stroke={CHART_COLORS.gold} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="parse_score" name="Parse" stroke={CHART_COLORS.info} strokeWidth={2} dot={false} />
          {hasUtility && (
            <Line type="monotone" dataKey="utility_score" name="Utility" stroke={CHART_COLORS.success} strokeWidth={2} dot={false} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

**Step 4: Add TrendChart to PlayerProfile Performance tab**

In `PlayerProfile.tsx`, add a query for trends and render the chart above the rankings table:

```tsx
const { data: trends } = useQuery({
  queryKey: ['trends', name, weeks],
  queryFn: () => api.players.trends(name!, weeks),
  enabled: !!name && tab === 'performance',
})

// In the performance tab JSX, above the rankings table:
{trends && trends.length > 1 && <TrendChart data={trends} />}
```

**Step 5: Build, commit**

```bash
cd web/frontend && npm run build
pytest tests/ -q
git add web/api/routes/players.py web/frontend/src/
git commit -m "feat: add score trend graphs to player profile"
```

---

## Task 6: MVP of the Week (Leaderboard Hero)

**Files:**
- Create: `web/api/routes/mvp.py` — MVP endpoint
- Modify: `web/api/main.py` — Register mvp router
- Modify: `web/frontend/src/api/client.ts` — Add `api.mvp()`
- Modify: `web/frontend/src/api/types.ts` — Add `MvpEntry` type
- Modify: `web/frontend/src/pages/Home.tsx` — Add MVP hero section

**Step 1: Create MVP API route**

Create `web/api/routes/mvp.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from web.api.database import get_db
from web.api.models import Player, Score

router = APIRouter(prefix="/api/mvp", tags=["mvp"])


@router.get("")
async def get_mvp(weeks_ago: int = Query(default=0, ge=0, le=8), db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    # ISO week: Monday-Sunday
    today = now.date()
    start_of_week = today - timedelta(days=today.weekday() + (weeks_ago * 7))
    end_of_week = start_of_week + timedelta(days=7)

    result = await db.execute(
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.avg(Score.utility_score).label("avg_utility"),
            func.avg(Score.consumables_score).label("avg_consumables"),
            func.count(Score.id).label("fight_count"),
            func.max(Score.spec).label("spec"),
        )
        .join(Score, Score.player_id == Player.id)
        .where(
            Score.recorded_at >= datetime.combine(start_of_week, datetime.min.time()),
            Score.recorded_at < datetime.combine(end_of_week, datetime.min.time()),
        )
        .group_by(Player.name, Player.class_name)
        .order_by(func.avg(Score.overall_score).desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return None

    return {
        "name": row.name,
        "class_name": row.class_name,
        "spec": row.spec,
        "overall_score": round(row.avg_score, 1),
        "parse_score": round(row.avg_parse, 1),
        "utility_score": round(row.avg_utility, 1) if row.avg_utility else None,
        "consumables_score": round(row.avg_consumables, 1) if row.avg_consumables else None,
        "fight_count": row.fight_count,
        "week_start": start_of_week.isoformat(),
    }
```

**Step 2: Register router in main.py**

Add import and include: `from web.api.routes.mvp import router as mvp_router` and `app.include_router(mvp_router)`.

**Step 3: Add frontend type, API method, and render in Home.tsx**

Add `MvpEntry` type, `api.mvp()` method, and a gold-bordered hero card at the top of the leaderboard page showing the MVP with a crown/star icon.

**Step 4: Build, test, commit**

```bash
git commit -m "feat: add MVP of the Week hero section to leaderboard"
```

---

## Task 7: Personal Improvement Suggestions

**Files:**
- Create: `web/api/routes/insights.py` — Insights endpoint
- Modify: `web/api/main.py` — Register insights router
- Modify: `web/frontend/src/pages/PlayerProfile.tsx` — Add insights card
- Modify: `web/frontend/src/api/client.ts` and `types.ts`

**Step 1: Create insights API route**

Create `web/api/routes/insights.py` with `GET /api/players/{name}/insights`:

Logic:
1. Query last N weeks of UtilityData — find metrics below target, generate "Your X averaged Y% vs Z% target"
2. Query ConsumablesData — find consistently good/bad consumable usage
3. Query Rankings — find bosses where player consistently parses low
4. Query Scores — detect improvement or decline trends
5. Query AttendanceRecords — detect attendance drops

Return: `[{type: "warning"|"success"|"info", message: string, metric: string|null}]`

**Step 2: Add to PlayerProfile as an "Insights" card below score cards**

Show colored cards: green for positive, yellow for warnings, blue for info.

**Step 3: Build, test, commit**

```bash
git commit -m "feat: add personal improvement suggestions to player profile"
```

---

## Task 8: Pre-Raid Checklist Dashboard

**Files:**
- Create: `web/api/routes/checklist.py`
- Modify: `web/api/main.py`
- Create: `web/frontend/src/pages/Checklist.tsx`
- Modify: `web/frontend/src/App.tsx` — Add route
- Modify: `web/frontend/src/components/Sidebar.tsx` — Add nav item

**Step 1: Create checklist API route**

`GET /api/checklist` returns:

```python
{
    "players": [
        {
            "name": "...",
            "class_name": "...",
            "readiness": "green" | "yellow" | "red",
            "gear_issues": ["Missing enchant on Head", ...],
            "attendance_missed": True/False,
            "consumables_avg": 85.2,  # avg consumable compliance last 4 raids
        }
    ]
}
```

Logic: Query latest GearSnapshot per player (check enchants/gems), recent AttendanceRecords (last week), recent ConsumablesData (last 4 reports avg). Compute readiness color.

**Step 2: Create Checklist page**

Table showing all players with readiness indicators, expandable rows showing specific issues. Color-coded rows (green/yellow/red background tint).

**Step 3: Add to sidebar and routes**

Add `/checklist` route to App.tsx, add "Checklist" nav item to Sidebar with a clipboard icon.

**Step 4: Build, test, commit**

```bash
git commit -m "feat: add pre-raid checklist dashboard"
```

---

## Task 9: Spec Comparison Page

**Files:**
- Create: `web/api/routes/compare.py`
- Modify: `web/api/main.py`
- Create: `web/frontend/src/pages/Compare.tsx`
- Modify: `web/frontend/src/App.tsx` and `Sidebar.tsx`

**Step 1: Create compare API route**

`GET /api/compare?spec=warrior:fury&weeks=4` returns list of players who played that spec, with their avg scores.

**Step 2: Create Compare page**

Spec dropdown at top. Shows bar chart comparing players side by side (Recharts BarChart). Table below with detailed scores. Sortable columns.

**Step 3: Add to sidebar and routes**

**Step 4: Build, test, commit**

```bash
git commit -m "feat: add spec comparison page with bar charts"
```

---

## Task 10: Roster Health Dashboard

**Files:**
- Create: `web/api/routes/roster.py`
- Modify: `web/api/main.py`
- Create: `web/frontend/src/pages/Roster.tsx`
- Modify: `web/frontend/src/App.tsx` and `Sidebar.tsx`

**Step 1: Create roster health API route**

`GET /api/roster/health?weeks=4` returns:
- `distribution`: class/spec counts `[{spec, class_name, count}]`
- `at_risk`: players with declining trends `[{name, reason}]`
- `attendance_grid`: per-player per-week attendance data

**Step 2: Create Roster page**

- PieChart or horizontal BarChart for class distribution (Recharts)
- Highlighted "at risk" specs with only 1 player
- Attendance heatmap: grid of colored cells (green=attended, red=missed)
- At-risk player cards with reasons

**Step 3: Add to sidebar and routes**

**Step 4: Build, test, commit**

```bash
git commit -m "feat: add roster health dashboard with distribution charts"
```

---

## Task 11: Death Log Summary + Wipe Analysis

**Files:**
- Create: `web/api/routes/fights.py` — Death log and wipe analysis endpoints
- Modify: `web/api/main.py`
- Modify: `web/frontend/src/pages/RaidDetail.tsx` — Add Deaths and Wipes tabs
- Modify: `web/frontend/src/api/client.ts` and `types.ts`

**Step 1: Create fights API routes**

`GET /api/reports/{code}/deaths`:
```python
{
    "per_fight": [{
        "fight_name": "Gruul",
        "kill": True,
        "deaths": [{"player": "...", "timestamp_pct": 45.2, "ability": "Shatter"}]
    }],
    "totals": [{"player": "...", "death_count": 3, "class_name": "..."}]
}
```

`GET /api/reports/{code}/wipes`:
```python
[{
    "encounter_name": "Void Reaver",
    "wipe_count": 3,
    "kill_count": 1,
    "wipes": [{
        "fight_id": 5,
        "duration_s": 120,
        "boss_pct": 45.2,
        "deaths": [{"player": "...", "timestamp_pct": 30.1, "ability": "Arcane Orb"}]
    }]
}]
```

**Step 2: Add Deaths and Wipes sections to RaidDetail page**

Add tabs or accordion sections to the existing raid detail page. Death leaderboard (most deaths → fewest). Wipe timeline per boss.

**Step 3: Build, test, commit**

```bash
git commit -m "feat: add death log summary and wipe analysis to raid detail"
```

---

## Task 12: Boss-Specific Scorecards

**Files:**
- Modify: `web/api/routes/fights.py` — Add per-fight detail endpoint
- Modify: `web/frontend/src/pages/RaidDetail.tsx` — Add boss accordion with DPS/HPS charts

**Step 1: Add fight detail endpoint**

`GET /api/reports/{code}/fights/{fight_id}`:
```python
{
    "encounter_name": "Gruul",
    "kill": True,
    "duration_s": 180,
    "attempts": 3,  # total pulls for this boss in this report
    "players": [
        {"name": "...", "class_name": "...", "dps": 1200, "hps": 0,
         "damage_done": 216000, "healing_done": 0, "deaths": 0}
    ]
}
```

**Step 2: Add boss accordion with Recharts BarChart**

Per-boss expandable section showing player DPS/HPS as horizontal bar chart, death markers, utility compliance.

**Step 3: Build, test, commit**

```bash
git commit -m "feat: add boss-specific scorecards with DPS/HPS charts"
```

---

## Task 13: Achievement/Badge System

**Files:**
- Create: `web/api/badges.py` — Badge evaluation engine
- Modify: `web/api/sync/worker.py` — Run badge evaluation after sync
- Create: `web/api/routes/badges.py` — Badge API routes
- Modify: `web/api/main.py`
- Create: `web/frontend/src/pages/Achievements.tsx`
- Modify: `web/frontend/src/pages/PlayerProfile.tsx` — Show badges
- Modify: `web/frontend/src/App.tsx` and `Sidebar.tsx`
- Test: `tests/test_web_badges.py`

**Step 1: Create badge evaluation engine**

Create `web/api/badges.py`:

```python
BADGE_DEFINITIONS = [
    {"type": "parse_god", "label": "Parse God", "description": "99+ parse on any boss", "icon": "crown"},
    {"type": "consistency_king", "label": "Consistency King", "description": "90+ score for 4+ weeks", "icon": "star"},
    {"type": "iron_raider", "label": "Iron Raider", "description": "100% attendance for 4+ weeks", "icon": "shield"},
    {"type": "flask_master", "label": "Flask Master", "description": "100% flask uptime 4+ raids", "icon": "flask"},
    {"type": "most_improved", "label": "Most Improved", "description": "Biggest score increase over 4 weeks", "icon": "trending-up"},
    {"type": "deathless", "label": "Deathless", "description": "Zero deaths in a full raid clear", "icon": "heart"},
    {"type": "utility_star", "label": "Utility Star", "description": "95%+ utility score for 4+ weeks", "icon": "zap"},
    {"type": "geared_up", "label": "Geared Up", "description": "All items epic+ fully enchanted/gemmed", "icon": "gem"},
]


async def evaluate_badges(session):
    """Check all players against badge criteria and award new badges."""
    # For each badge type, query relevant data and check thresholds
    # Only insert if badge doesn't already exist (unique constraint handles this)
    ...
```

Each badge check function queries the relevant tables and inserts Badge records.

**Step 2: Call badge evaluation from worker.py after report sync**

```python
# At end of run_reports_sync, after attendance computation:
from web.api.badges import evaluate_badges
await evaluate_badges(session)
```

**Step 3: Create badge API routes**

- `GET /api/players/{name}/badges` — Returns badges for a player
- `GET /api/achievements` — Returns all badges across guild with counts

**Step 4: Create Achievements page and add badges to PlayerProfile**

Achievements page: Grid of all badge types with icons, descriptions, and who has earned them. PlayerProfile: Row of badge icons below the hero header.

**Step 5: Write tests for badge evaluation logic**

Test each badge check function with mock data.

**Step 6: Build, test, commit**

```bash
git commit -m "feat: add automated achievement/badge system"
```

---

## Task 14: Final Integration — Navigation, Build, Deploy

**Files:**
- Modify: `web/frontend/src/components/Sidebar.tsx` — Finalize nav order
- Verify: All routes in `App.tsx`
- Build: `web/frontend`
- Test: All tests

**Step 1: Finalize sidebar navigation order**

```
Leaderboard (/)
Raids (/raids)
Attendance (/attendance)
Checklist (/checklist)
Compare (/compare)
Roster (/roster)
Achievements (/achievements)
Config (/config)
```

**Step 2: Full build and test**

```bash
cd web/frontend && npm run build
cd ../.. && pytest tests/ -q
```

**Step 3: Commit and push**

```bash
git add .
git commit -m "feat: complete feature expansion — 10 new features"
git push
```

---

## Implementation Order Summary

| Task | Feature | Dependencies | Estimated API calls added per report |
|------|---------|-------------|--------------------------------------|
| 1 | Database models | None | 0 |
| 2 | WCL API queries | None | 0 |
| 3 | Sync pipeline | Tasks 1, 2 | ~3-4 per fight (fights + deaths + damage + healing) |
| 4 | Recharts setup | None | 0 |
| 5 | Trend Graphs | Task 4 | 0 (uses existing Score data) |
| 6 | MVP of the Week | None | 0 (uses existing Score data) |
| 7 | Improvement Suggestions | None | 0 (uses existing data) |
| 8 | Pre-Raid Checklist | None | 0 (uses existing data) |
| 9 | Spec Comparison | Task 4 | 0 (uses existing Score data) |
| 10 | Roster Health | Task 4 | 0 (uses existing data) |
| 11 | Death Log + Wipe Analysis | Task 3 | 0 (uses synced fights/deaths) |
| 12 | Boss Scorecards | Task 3 | 0 (uses synced fight_player_stats) |
| 13 | Achievement/Badge System | Task 3 | 0 (uses all synced data) |
| 14 | Final Integration | All above | 0 |
