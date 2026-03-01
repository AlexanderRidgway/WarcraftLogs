# Guild Website Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fully public React + FastAPI website that surfaces all WarcraftLogs bot data (player profiles, gear, scores, raid recaps, attendance) via a cached/scheduled sync to PostgreSQL.

**Architecture:** Monorepo with `web/` directory alongside existing `src/`. FastAPI backend imports existing bot modules (scoring, gear, config, WCL client) directly. Sync worker pulls WCL data into Postgres on a schedule. React frontend served as static build.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (async), APScheduler, PostgreSQL, React 18, Vite, TypeScript

**Design doc:** `docs/plans/2026-02-28-guild-website-design.md`

---

## Phase 1: Backend Foundation

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `web/api/__init__.py`
- Create: `web/api/main.py`
- Create: `web/requirements.txt`
- Create: `web/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p web/api/routes web/api/sync
touch web/__init__.py web/api/__init__.py web/api/routes/__init__.py web/api/sync/__init__.py
```

**Step 2: Create web/requirements.txt**

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy[asyncio]==2.0.25
asyncpg==0.29.0
alembic==1.13.1
apscheduler==3.10.4
pydantic==2.5.3
python-dotenv==1.0.0
aiohttp==3.9.1
pyyaml==6.0.1
boto3>=1.34.0
```

**Step 3: Create minimal FastAPI app in `web/api/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CRANK Guild Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Verify the app starts**

Run: `cd web && pip install -r requirements.txt && python -m uvicorn api.main:app --port 8000 &`
Then: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`
Kill the server after verifying.

**Step 5: Commit**

```bash
git add web/
git commit -m "feat(web): scaffold FastAPI backend with health endpoint"
```

---

### Task 2: Database models and connection

**Files:**
- Create: `web/api/database.py`
- Create: `web/api/models.py`

**Step 1: Create `web/api/database.py`**

```python
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/crankguild")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

**Step 2: Create `web/api/models.py`**

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(20), nullable=False)
    server: Mapped[str] = mapped_column(String(50), nullable=False)
    region: Mapped[str] = mapped_column(String(10), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rankings: Mapped[list["Ranking"]] = relationship(back_populates="player")
    scores: Mapped[list["Score"]] = relationship(back_populates="player")
    gear_snapshots: Mapped[list["GearSnapshot"]] = relationship(back_populates="player")
    utility_data: Mapped[list["UtilityData"]] = relationship(back_populates="player")
    consumables_data: Mapped[list["ConsumablesData"]] = relationship(back_populates="player")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="player")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    zone_id: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    player_names: Mapped[dict] = mapped_column(JSON, nullable=False)


class Ranking(Base):
    __tablename__ = "rankings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    encounter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(30), nullable=False)
    rank_percent: Mapped[float] = mapped_column(Float, nullable=False)
    zone_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="rankings")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    spec: Mapped[str] = mapped_column(String(30), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    parse_score: Mapped[float] = mapped_column(Float, nullable=False)
    utility_score: Mapped[float] = mapped_column(Float, nullable=True)
    consumables_score: Mapped[float] = mapped_column(Float, nullable=True)
    fight_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="scores")


class GearSnapshot(Base):
    __tablename__ = "gear_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_level: Mapped[int] = mapped_column(Integer, nullable=False)
    quality: Mapped[int] = mapped_column(Integer, nullable=False)
    permanent_enchant: Mapped[int] = mapped_column(Integer, nullable=True)
    gems: Mapped[dict] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="gear_snapshots")


class UtilityData(Base):
    __tablename__ = "utility_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)

    player: Mapped["Player"] = relationship(back_populates="utility_data")


class ConsumablesData(Base):
    __tablename__ = "consumables_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    player: Mapped["Player"] = relationship(back_populates="consumables_data")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_id: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_label: Mapped[str] = mapped_column(String(50), nullable=False)
    clear_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[int] = mapped_column(Integer, nullable=False)
    met: Mapped[bool] = mapped_column(Boolean, nullable=False)

    player: Mapped["Player"] = relationship(back_populates="attendance_records")

    __table_args__ = (
        UniqueConstraint("player_id", "year", "week_number", "zone_id", name="uq_attendance_player_week_zone"),
    )


class SyncStatus(Base):
    __tablename__ = "sync_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_type: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
```

**Step 3: Write test for model imports**

Create `tests/test_web_models.py`:

```python
def test_models_importable():
    from web.api.models import Base, Player, Report, Ranking, Score
    from web.api.models import GearSnapshot, UtilityData, ConsumablesData
    from web.api.models import AttendanceRecord, SyncStatus
    assert len(Base.metadata.tables) == 9


def test_player_table_columns():
    from web.api.models import Player
    columns = {c.name for c in Player.__table__.columns}
    assert columns == {"id", "name", "class_id", "class_name", "server", "region", "last_synced_at"}
```

**Step 4: Run tests**

Run: `pytest tests/test_web_models.py -v`
Expected: 2 PASS

**Step 5: Commit**

```bash
git add web/api/database.py web/api/models.py tests/test_web_models.py
git commit -m "feat(web): add SQLAlchemy database models for all tables"
```

---

### Task 3: Alembic migrations setup

**Files:**
- Create: `web/alembic.ini`
- Create: `web/alembic/env.py`
- Create: `web/alembic/versions/` (auto-generated)

**Step 1: Initialize alembic in web/ directory**

```bash
cd web && alembic init alembic
```

**Step 2: Update `web/alembic/env.py`**

Replace the target_metadata line with:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from web.api.models import Base
target_metadata = Base.metadata
```

And update the `run_migrations_online` function to use the `DATABASE_URL` env var.

**Step 3: Update `web/alembic.ini`**

Set: `sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/crankguild`

**Step 4: Generate initial migration**

```bash
cd web && alembic revision --autogenerate -m "initial schema"
```

**Step 5: Commit**

```bash
git add web/alembic.ini web/alembic/
git commit -m "feat(web): add Alembic migrations with initial schema"
```

---

## Phase 2: Sync Worker

### Task 4: Roster sync

**Files:**
- Create: `web/api/sync/roster.py`
- Create: `tests/test_web_sync_roster.py`

**Step 1: Write failing test**

Create `tests/test_web_sync_roster.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


CLASS_ID_TO_NAME = {
    1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue",
    5: "priest", 6: "death knight", 7: "shaman", 8: "mage",
    9: "warlock", 11: "druid",
}


@pytest.fixture
def mock_wcl():
    wcl = AsyncMock()
    wcl.get_guild_roster.return_value = [
        {"name": "Testplayer", "classID": 1, "server": {"slug": "stormrage", "region": {"slug": "us"}}},
        {"name": "Healbot", "classID": 5, "server": {"slug": "stormrage", "region": {"slug": "us"}}},
    ]
    return wcl


@pytest.mark.asyncio
async def test_sync_roster_inserts_new_players(mock_wcl):
    from web.api.sync.roster import sync_roster

    upserted = []

    async def fake_upsert(session, roster_data):
        upserted.extend(roster_data)

    result = await sync_roster(
        wcl=mock_wcl,
        guild_name="CRANK",
        server_slug="stormrage",
        region="us",
    )
    mock_wcl.get_guild_roster.assert_called_once_with("CRANK", "stormrage", "us")
    assert len(result) == 2
    assert result[0]["name"] == "Testplayer"
    assert result[0]["class_name"] == "warrior"
    assert result[1]["name"] == "Healbot"
    assert result[1]["class_name"] == "priest"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_sync_roster.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'web.api.sync.roster'`

**Step 3: Implement `web/api/sync/roster.py`**

```python
import logging
from src.api.warcraftlogs import WarcraftLogsClient

logger = logging.getLogger(__name__)

CLASS_ID_TO_NAME = {
    1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue",
    5: "priest", 6: "death knight", 7: "shaman", 8: "mage",
    9: "warlock", 11: "druid",
}


async def sync_roster(wcl: WarcraftLogsClient, guild_name: str, server_slug: str, region: str) -> list[dict]:
    """Fetch guild roster from WCL and return normalized player dicts."""
    raw = await wcl.get_guild_roster(guild_name, server_slug, region)
    players = []
    for member in raw:
        players.append({
            "name": member["name"],
            "class_id": member["classID"],
            "class_name": CLASS_ID_TO_NAME.get(member["classID"], "unknown"),
            "server": member["server"]["slug"],
            "region": member["server"]["region"]["slug"],
        })
    logger.info("Synced %d players from guild roster", len(players))
    return players
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_sync_roster.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/api/sync/roster.py tests/test_web_sync_roster.py
git commit -m "feat(web): add roster sync from WarcraftLogs API"
```

---

### Task 5: Report sync — fetch and process reports

**Files:**
- Create: `web/api/sync/reports.py`
- Create: `tests/test_web_sync_reports.py`

**Step 1: Write failing test for report fetching**

Create `tests/test_web_sync_reports.py`:

```python
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone


@pytest.fixture
def mock_wcl():
    wcl = AsyncMock()
    wcl.get_guild_reports.return_value = [
        {
            "code": "abc123",
            "startTime": 1700000000000,
            "zone": {"id": 1007, "name": "The Eye"},
            "players": ["Testplayer", "Healbot"],
        },
    ]
    wcl.get_report_rankings.return_value = [
        {"name": "Testplayer", "class": "Warrior", "spec": "Fury", "rankPercent": 85.5},
        {"name": "Healbot", "class": "Priest", "spec": "Holy", "rankPercent": 72.0},
    ]
    wcl.get_report_players.return_value = [
        {"id": 1, "name": "Testplayer"},
        {"id": 2, "name": "Healbot"},
    ]
    wcl.get_report_timerange.return_value = {"start": 0, "end": 3600000}
    wcl.get_utility_data.return_value = {}
    wcl.get_report_gear.return_value = [
        {"name": "Testplayer", "gear": []},
        {"name": "Healbot", "gear": []},
    ]
    return wcl


@pytest.mark.asyncio
async def test_fetch_new_reports(mock_wcl):
    from web.api.sync.reports import fetch_new_reports

    reports = await fetch_new_reports(
        wcl=mock_wcl,
        guild_name="CRANK",
        server_slug="stormrage",
        region="us",
        days_back=7,
        existing_codes=set(),
    )
    assert len(reports) == 1
    assert reports[0]["code"] == "abc123"
    assert reports[0]["zone_name"] == "The Eye"


@pytest.mark.asyncio
async def test_fetch_new_reports_skips_existing(mock_wcl):
    from web.api.sync.reports import fetch_new_reports

    reports = await fetch_new_reports(
        wcl=mock_wcl,
        guild_name="CRANK",
        server_slug="stormrage",
        region="us",
        days_back=7,
        existing_codes={"abc123"},
    )
    assert len(reports) == 0


@pytest.mark.asyncio
async def test_process_report_returns_player_data(mock_wcl):
    from web.api.sync.reports import process_report
    from src.config.loader import ConfigLoader

    config = ConfigLoader()
    result = await process_report(
        wcl=mock_wcl,
        report_code="abc123",
        config=config,
    )
    assert "rankings" in result
    assert "scores" in result
    assert "gear" in result
    assert len(result["rankings"]) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_sync_reports.py -v`
Expected: FAIL

**Step 3: Implement `web/api/sync/reports.py`**

```python
import logging
import time
from datetime import datetime, timezone

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from src.scoring.engine import score_player

logger = logging.getLogger(__name__)


async def fetch_new_reports(
    wcl: WarcraftLogsClient,
    guild_name: str,
    server_slug: str,
    region: str,
    days_back: int = 7,
    existing_codes: set[str] | None = None,
) -> list[dict]:
    """Fetch guild reports from WCL, filtering out already-synced ones."""
    existing_codes = existing_codes or set()
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (days_back * 86400 * 1000)

    raw_reports = await wcl.get_guild_reports(guild_name, server_slug, region, start_ms, now_ms)

    new_reports = []
    for r in raw_reports:
        if r["code"] in existing_codes:
            continue
        new_reports.append({
            "code": r["code"],
            "zone_id": r["zone"]["id"],
            "zone_name": r["zone"]["name"],
            "start_time": datetime.fromtimestamp(r["startTime"] / 1000, tz=timezone.utc),
            "end_time": datetime.fromtimestamp(
                (r["startTime"] + 3600000) / 1000, tz=timezone.utc
            ),
            "player_names": r.get("players", []),
        })

    logger.info("Found %d new reports (of %d total)", len(new_reports), len(raw_reports))
    return new_reports


async def process_report(
    wcl: WarcraftLogsClient,
    report_code: str,
    config: ConfigLoader,
) -> dict:
    """Process a single report: fetch rankings, gear, utility, consumables."""
    rankings_raw = await wcl.get_report_rankings(report_code)
    players_raw = await wcl.get_report_players(report_code)
    timerange = await wcl.get_report_timerange(report_code)
    gear_raw = await wcl.get_report_gear(report_code)

    source_map = {p["name"]: p["id"] for p in players_raw}
    consumables_profile = config.get_consumables()

    rankings = []
    scores = []
    utility_entries = []
    consumables_entries = []

    for player in rankings_raw:
        name = player["name"]
        spec = player.get("spec", "")
        cls = player.get("class", "")
        parse = player.get("rankPercent", 0)
        spec_key = f"{cls.lower()}:{spec.lower()}" if cls and spec else None
        spec_profile = config.get_spec(spec_key) if spec_key else None

        rankings.append({
            "player_name": name,
            "spec": spec_key or "unknown",
            "rank_percent": parse,
            "encounter_name": "Average",
        })

        # Utility data
        utility_data = {}
        if spec_profile and spec_profile.get("contributions") and name in source_map:
            try:
                utility_data = await wcl.get_utility_data(
                    report_code, source_map[name],
                    timerange["start"], timerange["end"],
                    spec_profile["contributions"],
                )
            except Exception:
                logger.warning("Failed to fetch utility for %s in %s", name, report_code)

            for contrib in spec_profile.get("contributions", []):
                metric = contrib["metric"]
                actual = utility_data.get(metric, 0)
                target = contrib["target"]
                metric_score = min(actual / target, 1.0) * 100 if target > 0 else 0
                utility_entries.append({
                    "player_name": name,
                    "report_code": report_code,
                    "metric_name": metric,
                    "label": contrib["label"],
                    "actual_value": actual,
                    "target_value": target,
                    "score": metric_score,
                })

        # Consumables data
        if consumables_profile and name in source_map:
            try:
                c_data = await wcl.get_utility_data(
                    report_code, source_map[name],
                    timerange["start"], timerange["end"],
                    consumables_profile,
                )
                for cons in consumables_profile:
                    metric = cons["metric"]
                    actual = c_data.get(metric, 0)
                    consumables_entries.append({
                        "player_name": name,
                        "report_code": report_code,
                        "metric_name": metric,
                        "label": cons["label"],
                        "actual_value": actual,
                        "target_value": cons["target"],
                        "optional": cons.get("optional", False),
                    })
            except Exception:
                logger.warning("Failed to fetch consumables for %s in %s", name, report_code)

        # Score
        overall = score_player(
            spec_profile or {"utility_weight": 0, "parse_weight": 1, "contributions": []},
            parse,
            utility_data,
            consumables_profile,
            {c["metric_name"]: c["actual_value"] for c in consumables_entries if c["player_name"] == name},
        )
        scores.append({
            "player_name": name,
            "report_code": report_code,
            "spec": spec_key or "unknown",
            "overall_score": overall,
            "parse_score": parse,
            "utility_score": None,
            "consumables_score": None,
        })

    gear = []
    for pg in gear_raw:
        for item in pg.get("gear", []):
            if not item or item.get("id", 0) == 0:
                continue
            gear.append({
                "player_name": pg["name"],
                "report_code": report_code,
                "slot": item.get("slot", 0),
                "item_id": item.get("id", 0),
                "item_level": item.get("itemLevel", 0),
                "quality": item.get("quality", 0),
                "permanent_enchant": item.get("permanentEnchant"),
                "gems": item.get("gems", []),
            })

    return {
        "rankings": rankings,
        "scores": scores,
        "gear": gear,
        "utility": utility_entries,
        "consumables": consumables_entries,
    }
```

**Step 4: Run tests**

Run: `pytest tests/test_web_sync_reports.py -v`
Expected: 3 PASS

**Step 5: Commit**

```bash
git add web/api/sync/reports.py tests/test_web_sync_reports.py
git commit -m "feat(web): add report fetch and processing for sync worker"
```

---

### Task 6: Sync worker scheduler

**Files:**
- Create: `web/api/sync/worker.py`
- Create: `tests/test_web_sync_worker.py`

**Step 1: Write failing test**

Create `tests/test_web_sync_worker.py`:

```python
def test_worker_importable():
    from web.api.sync.worker import SyncWorker
    assert SyncWorker is not None


def test_worker_has_required_methods():
    from web.api.sync.worker import SyncWorker
    assert hasattr(SyncWorker, "start")
    assert hasattr(SyncWorker, "stop")
    assert hasattr(SyncWorker, "run_roster_sync")
    assert hasattr(SyncWorker, "run_reports_sync")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_sync_worker.py -v`
Expected: FAIL

**Step 3: Implement `web/api/sync/worker.py`**

```python
import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from web.api.database import async_session
from web.api.models import Player, Report, Ranking, Score, GearSnapshot
from web.api.models import UtilityData, ConsumablesData, AttendanceRecord, SyncStatus
from web.api.sync.roster import sync_roster
from web.api.sync.reports import fetch_new_reports, process_report

logger = logging.getLogger(__name__)


class SyncWorker:
    def __init__(self, wcl: WarcraftLogsClient, config: ConfigLoader):
        self.wcl = wcl
        self.config = config
        self.guild_name = os.getenv("GUILD_NAME", "")
        self.server_slug = os.getenv("GUILD_SERVER", "")
        self.region = os.getenv("GUILD_REGION", "US")
        self.scheduler = AsyncIOScheduler()

    def start(self):
        roster_hours = int(os.getenv("ROSTER_SYNC_HOURS", "6"))
        reports_hours = int(os.getenv("SYNC_INTERVAL_HOURS", "2"))

        self.scheduler.add_job(self.run_roster_sync, "interval", hours=roster_hours, id="roster_sync")
        self.scheduler.add_job(self.run_reports_sync, "interval", hours=reports_hours, id="reports_sync")
        self.scheduler.start()
        logger.info("Sync worker started (roster: %dh, reports: %dh)", roster_hours, reports_hours)

    def stop(self):
        self.scheduler.shutdown()

    async def run_roster_sync(self):
        logger.info("Starting roster sync")
        try:
            players = await sync_roster(self.wcl, self.guild_name, self.server_slug, self.region)
            async with async_session() as session:
                for p in players:
                    existing = await session.execute(
                        select(Player).where(Player.name == p["name"])
                    )
                    existing = existing.scalar_one_or_none()
                    if existing:
                        existing.class_id = p["class_id"]
                        existing.class_name = p["class_name"]
                        existing.server = p["server"]
                        existing.region = p["region"]
                        existing.last_synced_at = datetime.now(timezone.utc)
                    else:
                        session.add(Player(**p, last_synced_at=datetime.now(timezone.utc)))
                await session.commit()

                await self._update_sync_status(session, "roster", "success")
            logger.info("Roster sync complete: %d players", len(players))
        except Exception as e:
            logger.error("Roster sync failed: %s", e)
            async with async_session() as session:
                await self._update_sync_status(session, "roster", "error", str(e))

    async def run_reports_sync(self):
        logger.info("Starting reports sync")
        try:
            async with async_session() as session:
                result = await session.execute(select(Report.code))
                existing_codes = {r[0] for r in result.all()}

            new_reports = await fetch_new_reports(
                self.wcl, self.guild_name, self.server_slug, self.region,
                days_back=7, existing_codes=existing_codes,
            )

            for report_data in new_reports:
                try:
                    await self._process_and_store_report(report_data)
                except Exception as e:
                    logger.warning("Failed to process report %s: %s", report_data["code"], e)

            async with async_session() as session:
                await self._update_sync_status(session, "reports", "success")
            logger.info("Reports sync complete: %d new reports", len(new_reports))
        except Exception as e:
            logger.error("Reports sync failed: %s", e)
            async with async_session() as session:
                await self._update_sync_status(session, "reports", "error", str(e))

    async def _process_and_store_report(self, report_data: dict):
        processed = await process_report(self.wcl, report_data["code"], self.config)

        async with async_session() as session:
            # Store report metadata
            session.add(Report(
                code=report_data["code"],
                zone_id=report_data["zone_id"],
                zone_name=report_data["zone_name"],
                start_time=report_data["start_time"],
                end_time=report_data["end_time"],
                player_names=report_data["player_names"],
            ))

            # Build player name -> id map
            player_ids = {}
            for name in {r["player_name"] for r in processed["rankings"]}:
                result = await session.execute(select(Player).where(Player.name == name))
                player = result.scalar_one_or_none()
                if player:
                    player_ids[name] = player.id

            # Store rankings
            for r in processed["rankings"]:
                if r["player_name"] in player_ids:
                    session.add(Ranking(
                        player_id=player_ids[r["player_name"]],
                        encounter_name=r["encounter_name"],
                        spec=r["spec"],
                        rank_percent=r["rank_percent"],
                        zone_id=report_data["zone_id"],
                        report_code=report_data["code"],
                    ))

            # Store scores
            for s in processed["scores"]:
                if s["player_name"] in player_ids:
                    session.add(Score(
                        player_id=player_ids[s["player_name"]],
                        report_code=s["report_code"],
                        spec=s["spec"],
                        overall_score=s["overall_score"],
                        parse_score=s["parse_score"],
                        utility_score=s.get("utility_score"),
                        consumables_score=s.get("consumables_score"),
                    ))

            # Store gear
            for g in processed["gear"]:
                if g["player_name"] in player_ids:
                    session.add(GearSnapshot(
                        player_id=player_ids[g["player_name"]],
                        report_code=g["report_code"],
                        slot=g["slot"],
                        item_id=g["item_id"],
                        item_level=g["item_level"],
                        quality=g["quality"],
                        permanent_enchant=g.get("permanent_enchant"),
                        gems=g.get("gems"),
                    ))

            # Store utility data
            for u in processed["utility"]:
                if u["player_name"] in player_ids:
                    session.add(UtilityData(
                        player_id=player_ids[u["player_name"]],
                        report_code=u["report_code"],
                        metric_name=u["metric_name"],
                        label=u["label"],
                        actual_value=u["actual_value"],
                        target_value=u["target_value"],
                        score=u["score"],
                    ))

            # Store consumables data
            for c in processed["consumables"]:
                if c["player_name"] in player_ids:
                    session.add(ConsumablesData(
                        player_id=player_ids[c["player_name"]],
                        report_code=c["report_code"],
                        metric_name=c["metric_name"],
                        label=c["label"],
                        actual_value=c["actual_value"],
                        target_value=c["target_value"],
                        optional=c.get("optional", False),
                    ))

            await session.commit()

    async def _update_sync_status(self, session: AsyncSession, sync_type: str, status: str, error: str = None):
        result = await session.execute(select(SyncStatus).where(SyncStatus.sync_type == sync_type))
        existing = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            existing.last_run_at = now
            existing.status = status
            existing.error_message = error
        else:
            session.add(SyncStatus(sync_type=sync_type, last_run_at=now, status=status, error_message=error))
        await session.commit()
```

**Step 4: Run tests**

Run: `pytest tests/test_web_sync_worker.py -v`
Expected: 2 PASS

**Step 5: Commit**

```bash
git add web/api/sync/worker.py tests/test_web_sync_worker.py
git commit -m "feat(web): add sync worker with APScheduler for roster and report sync"
```

---

## Phase 3: API Endpoints

### Task 7: Players API routes

**Files:**
- Create: `web/api/routes/players.py`
- Create: `tests/test_web_routes_players.py`

**Step 1: Write failing test**

Create `tests/test_web_routes_players.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from web.api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_list_players():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/players")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_player_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/players/NonExistent")
    assert response.status_code == 404
```

Note: These tests require `httpx` — add it to dev dependencies. The tests will initially mock the DB session or use a test SQLite DB. For Phase 3, tests use the ASGI test client pattern.

**Step 2: Implement `web/api/routes/players.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from web.api.database import get_db
from web.api.models import Player, Ranking, Score, GearSnapshot, UtilityData, ConsumablesData, AttendanceRecord

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("")
async def list_players(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).order_by(Player.name))
    players = result.scalars().all()
    return [
        {
            "name": p.name,
            "class_id": p.class_id,
            "class_name": p.class_name,
            "server": p.server,
            "region": p.region,
        }
        for p in players
    ]


@router.get("/{name}")
async def get_player(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Recent scores
    scores_result = await db.execute(
        select(Score).where(Score.player_id == player.id).order_by(Score.recorded_at.desc()).limit(20)
    )
    scores = scores_result.scalars().all()

    return {
        "name": player.name,
        "class_id": player.class_id,
        "class_name": player.class_name,
        "server": player.server,
        "region": player.region,
        "scores": [
            {
                "report_code": s.report_code,
                "spec": s.spec,
                "overall_score": s.overall_score,
                "parse_score": s.parse_score,
                "utility_score": s.utility_score,
                "consumables_score": s.consumables_score,
                "fight_count": s.fight_count,
                "recorded_at": s.recorded_at.isoformat(),
            }
            for s in scores
        ],
    }


@router.get("/{name}/rankings")
async def get_player_rankings(name: str, weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    rankings_result = await db.execute(
        select(Ranking)
        .where(Ranking.player_id == player.id, Ranking.recorded_at >= cutoff)
        .order_by(Ranking.recorded_at.desc())
    )
    rankings = rankings_result.scalars().all()

    return [
        {
            "encounter_name": r.encounter_name,
            "spec": r.spec,
            "rank_percent": r.rank_percent,
            "zone_id": r.zone_id,
            "report_code": r.report_code,
            "recorded_at": r.recorded_at.isoformat(),
        }
        for r in rankings
    ]


@router.get("/{name}/gear")
async def get_player_gear(name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get most recent report code for this player
    latest = await db.execute(
        select(GearSnapshot.report_code)
        .where(GearSnapshot.player_id == player.id)
        .order_by(GearSnapshot.recorded_at.desc())
        .limit(1)
    )
    latest_code = latest.scalar_one_or_none()
    if not latest_code:
        return {"player": name, "gear": [], "issues": []}

    gear_result = await db.execute(
        select(GearSnapshot)
        .where(GearSnapshot.player_id == player.id, GearSnapshot.report_code == latest_code)
    )
    gear = gear_result.scalars().all()

    from src.config.loader import ConfigLoader
    from src.gear.checker import check_player_gear
    config = ConfigLoader()
    gear_config = config.get_gear_check()

    gear_items = [
        {
            "slot": g.slot,
            "id": g.item_id,
            "itemLevel": g.item_level,
            "quality": g.quality,
            "permanentEnchant": g.permanent_enchant,
            "gems": g.gems or [],
        }
        for g in gear
    ]
    check_result = check_player_gear(gear_items, gear_config)

    return {
        "player": name,
        "report_code": latest_code,
        "avg_ilvl": check_result["avg_ilvl"],
        "ilvl_ok": check_result["ilvl_ok"],
        "gear": [
            {
                "slot": g.slot,
                "item_id": g.item_id,
                "item_level": g.item_level,
                "quality": g.quality,
                "permanent_enchant": g.permanent_enchant,
                "gems": g.gems,
            }
            for g in gear
        ],
        "issues": check_result["issues"],
    }


@router.get("/{name}/attendance")
async def get_player_attendance(name: str, weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == name))
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    records_result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.player_id == player.id)
        .order_by(AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
    )
    records = records_result.scalars().all()

    # Group by week
    weeks_data = {}
    for r in records:
        key = (r.year, r.week_number)
        if key not in weeks_data:
            weeks_data[key] = {"year": r.year, "week": r.week_number, "zones": []}
        weeks_data[key]["zones"].append({
            "zone_id": r.zone_id,
            "zone_label": r.zone_label,
            "clear_count": r.clear_count,
            "required": r.required,
            "met": r.met,
        })

    return list(weeks_data.values())[:weeks]
```

**Step 3: Register router in `web/api/main.py`**

Add to `web/api/main.py`:

```python
from web.api.routes.players import router as players_router
app.include_router(players_router)
```

**Step 4: Run tests**

Run: `pytest tests/test_web_routes_players.py -v`
Expected: 2 PASS (with empty DB these return empty list and 404)

**Step 5: Commit**

```bash
git add web/api/routes/players.py tests/test_web_routes_players.py web/api/main.py
git commit -m "feat(web): add player API routes with rankings, gear, attendance"
```

---

### Task 8: Reports, Leaderboard, Attendance, Config, Sync Status routes

**Files:**
- Create: `web/api/routes/reports.py`
- Create: `web/api/routes/leaderboard.py`
- Create: `web/api/routes/attendance.py`
- Create: `web/api/routes/config.py`
- Create: `web/api/routes/sync_status.py`
- Create: `tests/test_web_routes_other.py`

**Step 1: Write failing tests**

Create `tests/test_web_routes_other.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from web.api.main import app


@pytest.mark.asyncio
async def test_list_reports():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/reports")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_leaderboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/leaderboard")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_attendance():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/attendance")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_specs():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/specs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_consumables():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/consumables")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_sync_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/sync/status")
    assert response.status_code == 200
```

**Step 2: Implement all remaining routes**

`web/api/routes/reports.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Report, Score, GearSnapshot, ConsumablesData

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).order_by(Report.start_time.desc()))
    reports = result.scalars().all()
    return [
        {
            "code": r.code,
            "zone_id": r.zone_id,
            "zone_name": r.zone_name,
            "start_time": r.start_time.isoformat(),
            "end_time": r.end_time.isoformat(),
            "player_count": len(r.player_names) if r.player_names else 0,
        }
        for r in reports
    ]


@router.get("/{code}")
async def get_report(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.code == code))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    scores_result = await db.execute(
        select(Score).where(Score.report_code == code).order_by(Score.overall_score.desc())
    )
    scores = scores_result.scalars().all()

    consumables_result = await db.execute(
        select(ConsumablesData).where(ConsumablesData.report_code == code)
    )
    consumables = consumables_result.scalars().all()

    return {
        "code": report.code,
        "zone_id": report.zone_id,
        "zone_name": report.zone_name,
        "start_time": report.start_time.isoformat(),
        "end_time": report.end_time.isoformat(),
        "player_names": report.player_names,
        "scores": [
            {
                "player_id": s.player_id,
                "spec": s.spec,
                "overall_score": s.overall_score,
                "parse_score": s.parse_score,
                "utility_score": s.utility_score,
                "consumables_score": s.consumables_score,
            }
            for s in scores
        ],
        "consumables": [
            {
                "player_id": c.player_id,
                "metric_name": c.metric_name,
                "label": c.label,
                "actual_value": c.actual_value,
                "target_value": c.target_value,
                "optional": c.optional,
            }
            for c in consumables
        ],
    }
```

`web/api/routes/leaderboard.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from web.api.database import get_db
from web.api.models import Player, Score

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def leaderboard(weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)

    result = await db.execute(
        select(
            Player.name,
            Player.class_name,
            func.avg(Score.overall_score).label("avg_score"),
            func.avg(Score.parse_score).label("avg_parse"),
            func.count(Score.id).label("fight_count"),
        )
        .join(Score, Score.player_id == Player.id)
        .where(Score.recorded_at >= cutoff)
        .group_by(Player.name, Player.class_name)
        .order_by(func.avg(Score.overall_score).desc())
    )
    rows = result.all()

    return [
        {
            "rank": i + 1,
            "name": r.name,
            "class_name": r.class_name,
            "avg_score": round(r.avg_score, 1),
            "avg_parse": round(r.avg_parse, 1),
            "fight_count": r.fight_count,
        }
        for i, r in enumerate(rows)
    ]
```

`web/api/routes/attendance.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import Player, AttendanceRecord

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("")
async def guild_attendance(weeks: int = Query(default=4, ge=1, le=52), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Player.name, Player.class_name, AttendanceRecord)
        .join(AttendanceRecord, AttendanceRecord.player_id == Player.id)
        .order_by(Player.name, AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
    )
    rows = result.all()

    players = {}
    for name, class_name, record in rows:
        if name not in players:
            players[name] = {"name": name, "class_name": class_name, "weeks": []}
        players[name]["weeks"].append({
            "year": record.year,
            "week": record.week_number,
            "zone_label": record.zone_label,
            "met": record.met,
        })

    return list(players.values())
```

`web/api/routes/config.py`:

```python
from fastapi import APIRouter
from src.config.loader import ConfigLoader

router = APIRouter(prefix="/api/config", tags=["config"])

config = ConfigLoader()


@router.get("/specs")
async def get_specs():
    specs = config.all_specs()
    return {
        spec_key: config.get_spec(spec_key)
        for spec_key in specs
    }


@router.get("/consumables")
async def get_consumables():
    return config.get_consumables()


@router.get("/attendance")
async def get_attendance():
    return config.get_attendance()


@router.get("/gear")
async def get_gear():
    return config.get_gear_check()
```

`web/api/routes/sync_status.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.database import get_db
from web.api.models import SyncStatus

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status")
async def sync_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SyncStatus))
    statuses = result.scalars().all()
    return [
        {
            "sync_type": s.sync_type,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
            "status": s.status,
            "error_message": s.error_message,
        }
        for s in statuses
    ]
```

**Step 3: Register all routers in `web/api/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api.routes.players import router as players_router
from web.api.routes.reports import router as reports_router
from web.api.routes.leaderboard import router as leaderboard_router
from web.api.routes.attendance import router as attendance_router
from web.api.routes.config import router as config_router
from web.api.routes.sync_status import router as sync_status_router

app = FastAPI(title="CRANK Guild Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(players_router)
app.include_router(reports_router)
app.include_router(leaderboard_router)
app.include_router(attendance_router)
app.include_router(config_router)
app.include_router(sync_status_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Run tests**

Run: `pytest tests/test_web_routes_other.py -v`
Expected: 6 PASS

**Step 5: Commit**

```bash
git add web/api/routes/ tests/test_web_routes_other.py web/api/main.py
git commit -m "feat(web): add reports, leaderboard, attendance, config, sync status API routes"
```

---

## Phase 4: React Frontend

### Task 9: React project scaffolding

**Step 1: Create Vite + React + TypeScript project**

```bash
cd web && npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install react-router-dom@6 @tanstack/react-query
```

**Step 2: Configure Vite proxy for API calls**

Update `web/frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

**Step 3: Set up React Router and React Query in `web/frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Home from './pages/Home'
import PlayerProfile from './pages/PlayerProfile'
import RaidHistory from './pages/RaidHistory'
import RaidDetail from './pages/RaidDetail'
import Attendance from './pages/Attendance'
import Config from './pages/Config'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/player/:name" element={<PlayerProfile />} />
          <Route path="/raids" element={<RaidHistory />} />
          <Route path="/raids/:code" element={<RaidDetail />} />
          <Route path="/attendance" element={<Attendance />} />
          <Route path="/config" element={<Config />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
```

**Step 4: Create placeholder pages**

Create each page file (`Home.tsx`, `PlayerProfile.tsx`, `RaidHistory.tsx`, `RaidDetail.tsx`, `Attendance.tsx`, `Config.tsx`) with minimal placeholder content:

```tsx
export default function Home() {
  return <div><h1>CRANK Guild Dashboard</h1></div>
}
```

**Step 5: Verify dev server starts**

```bash
cd web/frontend && npm run dev &
curl http://localhost:5173
```

Expected: HTML page loads

**Step 6: Commit**

```bash
git add web/frontend/
git commit -m "feat(web): scaffold React frontend with routing and React Query"
```

---

### Task 10: API client and shared types

**Files:**
- Create: `web/frontend/src/api/client.ts`
- Create: `web/frontend/src/api/types.ts`

**Step 1: Create TypeScript types in `web/frontend/src/api/types.ts`**

```typescript
export interface Player {
  name: string
  class_id: number
  class_name: string
  server: string
  region: string
}

export interface PlayerDetail extends Player {
  scores: PlayerScore[]
}

export interface PlayerScore {
  report_code: string
  spec: string
  overall_score: number
  parse_score: number
  utility_score: number | null
  consumables_score: number | null
  fight_count: number
  recorded_at: string
}

export interface Ranking {
  encounter_name: string
  spec: string
  rank_percent: number
  zone_id: number
  report_code: string
  recorded_at: string
}

export interface GearItem {
  slot: number
  item_id: number
  item_level: number
  quality: number
  permanent_enchant: number | null
  gems: number[] | null
}

export interface GearCheck {
  player: string
  report_code: string
  avg_ilvl: number
  ilvl_ok: boolean
  gear: GearItem[]
  issues: { slot: string; problem: string }[]
}

export interface LeaderboardEntry {
  rank: number
  name: string
  class_name: string
  avg_score: number
  avg_parse: number
  fight_count: number
}

export interface ReportSummary {
  code: string
  zone_id: number
  zone_name: string
  start_time: string
  end_time: string
  player_count: number
}

export interface ReportDetail extends ReportSummary {
  player_names: string[]
  scores: {
    player_id: number
    spec: string
    overall_score: number
    parse_score: number
    utility_score: number | null
    consumables_score: number | null
  }[]
  consumables: {
    player_id: number
    metric_name: string
    label: string
    actual_value: number
    target_value: number
    optional: boolean
  }[]
}

export interface AttendanceWeek {
  year: number
  week: number
  zone_label: string
  met: boolean
}

export interface PlayerAttendance {
  name: string
  class_name: string
  weeks: AttendanceWeek[]
}

export interface SyncStatusEntry {
  sync_type: string
  last_run_at: string | null
  next_run_at: string | null
  status: string
  error_message: string | null
}
```

**Step 2: Create API client in `web/frontend/src/api/client.ts`**

```typescript
import type {
  Player, PlayerDetail, Ranking, GearCheck,
  LeaderboardEntry, ReportSummary, ReportDetail,
  PlayerAttendance, SyncStatusEntry,
} from './types'

const BASE = '/api'

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  players: {
    list: () => fetchJson<Player[]>('/players'),
    get: (name: string) => fetchJson<PlayerDetail>(`/players/${name}`),
    rankings: (name: string, weeks = 4) => fetchJson<Ranking[]>(`/players/${name}/rankings?weeks=${weeks}`),
    gear: (name: string) => fetchJson<GearCheck>(`/players/${name}/gear`),
    attendance: (name: string, weeks = 4) => fetchJson<AttendanceWeek[]>(`/players/${name}/attendance?weeks=${weeks}`),
  },
  leaderboard: (weeks = 4) => fetchJson<LeaderboardEntry[]>(`/leaderboard?weeks=${weeks}`),
  reports: {
    list: () => fetchJson<ReportSummary[]>('/reports'),
    get: (code: string) => fetchJson<ReportDetail>(`/reports/${code}`),
  },
  attendance: (weeks = 4) => fetchJson<PlayerAttendance[]>(`/attendance?weeks=${weeks}`),
  config: {
    specs: () => fetchJson<Record<string, unknown>>('/config/specs'),
    consumables: () => fetchJson<unknown[]>('/config/consumables'),
    attendance: () => fetchJson<unknown[]>('/config/attendance'),
    gear: () => fetchJson<Record<string, unknown>>('/config/gear'),
  },
  sync: () => fetchJson<SyncStatusEntry[]>('/sync/status'),
}
```

**Step 3: Commit**

```bash
git add web/frontend/src/api/
git commit -m "feat(web): add TypeScript API client and type definitions"
```

---

### Task 11: Shared components

**Files:**
- Create: `web/frontend/src/components/ParseBar.tsx`
- Create: `web/frontend/src/components/ScoreCard.tsx`
- Create: `web/frontend/src/components/ClassIcon.tsx`
- Create: `web/frontend/src/components/GearGrid.tsx`
- Create: `web/frontend/src/components/Layout.tsx`

**Step 1: Create WoW class color map and Layout component**

`web/frontend/src/components/Layout.tsx`:

```tsx
import { Link } from 'react-router-dom'

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '1rem' }}>
      <nav style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid #333', paddingBottom: '0.5rem' }}>
        <Link to="/">Home</Link>
        <Link to="/raids">Raids</Link>
        <Link to="/attendance">Attendance</Link>
        <Link to="/config">Config</Link>
      </nav>
      {children}
    </div>
  )
}
```

**Step 2: Create `ClassIcon.tsx`**

```tsx
const CLASS_COLORS: Record<string, string> = {
  warrior: '#C79C6E',
  paladin: '#F58CBA',
  hunter: '#ABD473',
  rogue: '#FFF569',
  priest: '#FFFFFF',
  shaman: '#0070DE',
  mage: '#69CCF0',
  warlock: '#9482C9',
  druid: '#FF7D0A',
}

export default function ClassIcon({ className, name }: { className: string; name: string }) {
  const color = CLASS_COLORS[className.toLowerCase()] || '#999'
  return <span style={{ color, fontWeight: 'bold' }}>{name}</span>
}
```

**Step 3: Create `ParseBar.tsx`**

```tsx
function parseColor(percent: number): string {
  if (percent >= 95) return '#e268a8' // pink/legendary
  if (percent >= 75) return '#a335ee' // purple/epic
  if (percent >= 50) return '#0070dd' // blue/rare
  if (percent >= 25) return '#1eff00' // green/uncommon
  return '#999'                       // gray
}

export default function ParseBar({ percent }: { percent: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div style={{ width: 100, height: 12, background: '#222', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${percent}%`, height: '100%', background: parseColor(percent) }} />
      </div>
      <span style={{ color: parseColor(percent), fontWeight: 'bold', fontSize: 14 }}>
        {percent.toFixed(1)}%
      </span>
    </div>
  )
}
```

**Step 4: Create `ScoreCard.tsx`**

```tsx
export default function ScoreCard({ label, value }: { label: string; value: number | null }) {
  if (value === null) return null
  return (
    <div style={{ padding: '0.5rem 1rem', background: '#1a1a2e', borderRadius: 8, textAlign: 'center' }}>
      <div style={{ fontSize: 12, color: '#888' }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 'bold', color: '#e0e0e0' }}>{value.toFixed(1)}</div>
    </div>
  )
}
```

**Step 5: Create `GearGrid.tsx`**

```tsx
import type { GearItem } from '../api/types'

const SLOT_NAMES: Record<number, string> = {
  0: 'Head', 1: 'Neck', 2: 'Shoulder', 4: 'Chest', 5: 'Waist',
  6: 'Legs', 7: 'Feet', 8: 'Wrist', 9: 'Hands', 10: 'Ring 1',
  11: 'Ring 2', 12: 'Trinket 1', 13: 'Trinket 2', 14: 'Cloak',
  15: 'Main Hand', 16: 'Off Hand', 17: 'Ranged',
}

const QUALITY_COLORS: Record<number, string> = {
  0: '#9d9d9d', 1: '#fff', 2: '#1eff00', 3: '#0070dd', 4: '#a335ee', 5: '#ff8000',
}

export default function GearGrid({ gear, issues }: { gear: GearItem[]; issues: { slot: string; problem: string }[] }) {
  const issueMap = new Map(issues.map(i => [i.slot, i.problem]))

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.25rem' }}>
      {gear.map(item => {
        const slotName = SLOT_NAMES[item.slot] || `Slot ${item.slot}`
        const issue = issueMap.get(slotName)
        return (
          <div
            key={item.slot}
            style={{
              padding: '0.5rem',
              background: issue ? '#2a1515' : '#1a1a2e',
              borderRadius: 4,
              borderLeft: `3px solid ${QUALITY_COLORS[item.quality] || '#999'}`,
            }}
          >
            <div style={{ fontSize: 11, color: '#888' }}>{slotName}</div>
            <div style={{ color: QUALITY_COLORS[item.quality], fontSize: 14 }}>
              ilvl {item.item_level}
              {item.permanent_enchant ? ' ✨' : ''}
            </div>
            {issue && <div style={{ fontSize: 11, color: '#ff6b6b' }}>{issue}</div>}
          </div>
        )
      })}
    </div>
  )
}
```

**Step 6: Commit**

```bash
git add web/frontend/src/components/
git commit -m "feat(web): add shared UI components (Layout, ParseBar, ScoreCard, ClassIcon, GearGrid)"
```

---

### Task 12: Home page (roster + leaderboard)

**Files:**
- Modify: `web/frontend/src/pages/Home.tsx`

**Step 1: Implement Home page**

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'

export default function Home() {
  const [search, setSearch] = useState('')
  const [weeks, setWeeks] = useState(4)
  const { data: leaderboard, isLoading } = useQuery({
    queryKey: ['leaderboard', weeks],
    queryFn: () => api.leaderboard(weeks),
  })

  const filtered = leaderboard?.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <Layout>
      <h1>CRANK Guild Dashboard</h1>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
        <input
          type="text"
          placeholder="Search player..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ padding: '0.5rem', flex: 1 }}
        />
        <select value={weeks} onChange={e => setWeeks(Number(e.target.value))}>
          <option value={2}>2 weeks</option>
          <option value={4}>4 weeks</option>
          <option value={8}>8 weeks</option>
        </select>
      </div>

      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Player</th>
              <th>Class</th>
              <th>Score</th>
              <th>Avg Parse</th>
              <th>Fights</th>
            </tr>
          </thead>
          <tbody>
            {filtered?.map(entry => (
              <tr key={entry.name}>
                <td>{entry.rank}</td>
                <td>
                  <Link to={`/player/${entry.name}`}>
                    <ClassIcon className={entry.class_name} name={entry.name} />
                  </Link>
                </td>
                <td>{entry.class_name}</td>
                <td>{entry.avg_score}</td>
                <td>{entry.avg_parse}</td>
                <td>{entry.fight_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Layout>
  )
}
```

**Step 2: Commit**

```bash
git add web/frontend/src/pages/Home.tsx
git commit -m "feat(web): implement Home page with leaderboard table and search"
```

---

### Task 13: Player Profile page

**Files:**
- Modify: `web/frontend/src/pages/PlayerProfile.tsx`

**Step 1: Implement Player Profile page with tabs**

```tsx
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'
import ScoreCard from '../components/ScoreCard'
import ParseBar from '../components/ParseBar'
import GearGrid from '../components/GearGrid'

type Tab = 'performance' | 'gear' | 'attendance'

export default function PlayerProfile() {
  const { name } = useParams<{ name: string }>()
  const [tab, setTab] = useState<Tab>('performance')
  const [weeks, setWeeks] = useState(4)

  const { data: player, isLoading } = useQuery({
    queryKey: ['player', name],
    queryFn: () => api.players.get(name!),
    enabled: !!name,
  })

  const { data: rankings } = useQuery({
    queryKey: ['rankings', name, weeks],
    queryFn: () => api.players.rankings(name!, weeks),
    enabled: !!name && tab === 'performance',
  })

  const { data: gear } = useQuery({
    queryKey: ['gear', name],
    queryFn: () => api.players.gear(name!),
    enabled: !!name && tab === 'gear',
  })

  const { data: attendance } = useQuery({
    queryKey: ['attendance', name, weeks],
    queryFn: () => api.players.attendance(name!, weeks),
    enabled: !!name && tab === 'attendance',
  })

  if (isLoading) return <Layout><p>Loading...</p></Layout>
  if (!player) return <Layout><p>Player not found</p></Layout>

  const avgScore = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.overall_score, 0) / player.scores.length
    : null

  const avgParse = player.scores.length
    ? player.scores.reduce((sum, s) => sum + s.parse_score, 0) / player.scores.length
    : null

  return (
    <Layout>
      <h1><ClassIcon className={player.class_name} name={player.name} /></h1>
      <p>{player.class_name} — {player.server} ({player.region})</p>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
        <ScoreCard label="Consistency" value={avgScore} />
        <ScoreCard label="Avg Parse" value={avgParse} />
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button onClick={() => setTab('performance')} disabled={tab === 'performance'}>Performance</button>
        <button onClick={() => setTab('gear')} disabled={tab === 'gear'}>Gear</button>
        <button onClick={() => setTab('attendance')} disabled={tab === 'attendance'}>Attendance</button>
      </div>

      {tab === 'performance' && rankings && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Boss</th><th>Spec</th><th>Parse</th><th>Report</th></tr>
          </thead>
          <tbody>
            {rankings.map((r, i) => (
              <tr key={i}>
                <td>{r.encounter_name}</td>
                <td>{r.spec}</td>
                <td><ParseBar percent={r.rank_percent} /></td>
                <td>{r.report_code}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'gear' && gear && (
        <div>
          <p>Avg iLvl: {gear.avg_ilvl.toFixed(1)} {gear.ilvl_ok ? '✅' : '⚠️'}</p>
          <GearGrid gear={gear.gear} issues={gear.issues} />
        </div>
      )}

      {tab === 'attendance' && attendance && (
        <div>
          {attendance.map((week: any, i: number) => (
            <div key={i} style={{ marginBottom: '0.5rem' }}>
              <strong>Week {week.week}, {week.year}</strong>
              <div>
                {week.zones?.map((z: any, j: number) => (
                  <span key={j} style={{ marginRight: '1rem' }}>
                    {z.met ? '✅' : '❌'} {z.zone_label} ({z.clear_count}/{z.required})
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
```

**Step 2: Commit**

```bash
git add web/frontend/src/pages/PlayerProfile.tsx
git commit -m "feat(web): implement Player Profile page with performance, gear, attendance tabs"
```

---

### Task 14: Raid History and Raid Detail pages

**Files:**
- Modify: `web/frontend/src/pages/RaidHistory.tsx`
- Modify: `web/frontend/src/pages/RaidDetail.tsx`

**Step 1: Implement Raid History**

```tsx
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Layout from '../components/Layout'

export default function RaidHistory() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.reports.list(),
  })

  return (
    <Layout>
      <h1>Raid History</h1>
      {isLoading ? <p>Loading...</p> : (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {reports?.map(r => (
            <Link
              key={r.code}
              to={`/raids/${r.code}`}
              style={{ padding: '1rem', background: '#1a1a2e', borderRadius: 8, textDecoration: 'none', color: 'inherit' }}
            >
              <strong>{r.zone_name}</strong>
              <span style={{ marginLeft: '1rem', color: '#888' }}>
                {new Date(r.start_time).toLocaleDateString()} — {r.player_count} players
              </span>
            </Link>
          ))}
        </div>
      )}
    </Layout>
  )
}
```

**Step 2: Implement Raid Detail**

```tsx
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ParseBar from '../components/ParseBar'

export default function RaidDetail() {
  const { code } = useParams<{ code: string }>()
  const { data: report, isLoading } = useQuery({
    queryKey: ['report', code],
    queryFn: () => api.reports.get(code!),
    enabled: !!code,
  })

  if (isLoading) return <Layout><p>Loading...</p></Layout>
  if (!report) return <Layout><p>Report not found</p></Layout>

  return (
    <Layout>
      <h1>{report.zone_name}</h1>
      <p>{new Date(report.start_time).toLocaleDateString()} — {report.player_names?.length} players</p>

      <h2>Scores</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr><th>Player</th><th>Spec</th><th>Score</th><th>Parse</th></tr>
        </thead>
        <tbody>
          {report.scores?.map((s, i) => (
            <tr key={i}>
              <td>{s.player_id}</td>
              <td>{s.spec}</td>
              <td>{s.overall_score.toFixed(1)}</td>
              <td><ParseBar percent={s.parse_score} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Consumables</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr><th>Player</th><th>Metric</th><th>Value</th><th>Target</th></tr>
        </thead>
        <tbody>
          {report.consumables?.filter(c => c.actual_value > 0).map((c, i) => (
            <tr key={i}>
              <td>{c.player_id}</td>
              <td>{c.label}{c.optional ? ' (optional)' : ''}</td>
              <td>{c.actual_value.toFixed(1)}</td>
              <td>{c.target_value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Layout>
  )
}
```

**Step 3: Commit**

```bash
git add web/frontend/src/pages/RaidHistory.tsx web/frontend/src/pages/RaidDetail.tsx
git commit -m "feat(web): implement Raid History and Raid Detail pages"
```

---

### Task 15: Attendance and Config pages

**Files:**
- Modify: `web/frontend/src/pages/Attendance.tsx`
- Modify: `web/frontend/src/pages/Config.tsx`

**Step 1: Implement Attendance page**

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'
import ClassIcon from '../components/ClassIcon'

export default function Attendance() {
  const [weeks, setWeeks] = useState(4)
  const { data, isLoading } = useQuery({
    queryKey: ['guild-attendance', weeks],
    queryFn: () => api.attendance(weeks),
  })

  return (
    <Layout>
      <h1>Guild Attendance</h1>
      <select value={weeks} onChange={e => setWeeks(Number(e.target.value))}>
        <option value={2}>2 weeks</option>
        <option value={4}>4 weeks</option>
        <option value={8}>8 weeks</option>
      </select>

      {isLoading ? <p>Loading...</p> : (
        <div>
          {data?.map(player => (
            <div key={player.name} style={{ marginBottom: '1rem', padding: '0.5rem', background: '#1a1a2e', borderRadius: 8 }}>
              <ClassIcon className={player.class_name} name={player.name} />
              <div style={{ marginTop: '0.25rem' }}>
                {player.weeks.map((w, i) => (
                  <span key={i} style={{ marginRight: '0.5rem', fontSize: 12 }}>
                    {w.met ? '✅' : '❌'} {w.zone_label}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
```

**Step 2: Implement Config page**

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'

export default function Config() {
  const { data: specs } = useQuery({ queryKey: ['config-specs'], queryFn: api.config.specs })
  const { data: consumables } = useQuery({ queryKey: ['config-consumables'], queryFn: api.config.consumables })
  const { data: attendance } = useQuery({ queryKey: ['config-attendance'], queryFn: api.config.attendance })
  const { data: gear } = useQuery({ queryKey: ['config-gear'], queryFn: api.config.gear })

  return (
    <Layout>
      <h1>Configuration Reference</h1>

      <h2>Spec Profiles</h2>
      {specs && Object.entries(specs).map(([key, profile]: [string, any]) => (
        <div key={key} style={{ marginBottom: '1rem', padding: '0.5rem', background: '#1a1a2e', borderRadius: 8 }}>
          <strong>{key}</strong>
          <span style={{ marginLeft: '1rem', fontSize: 12, color: '#888' }}>
            parse: {(profile.parse_weight * 100).toFixed(0)}% | utility: {(profile.utility_weight * 100).toFixed(0)}% | consumables: {((profile.consumables_weight || 0) * 100).toFixed(0)}%
          </span>
          {profile.contributions?.map((c: any) => (
            <div key={c.metric} style={{ fontSize: 12, marginLeft: '1rem' }}>
              {c.label} — target: {c.target} ({c.type})
            </div>
          ))}
        </div>
      ))}

      <h2>Consumables</h2>
      {consumables?.map((c: any) => (
        <div key={c.metric} style={{ fontSize: 14 }}>
          {c.label} — target: {c.target} {c.optional ? '(optional)' : ''}
        </div>
      ))}

      <h2>Attendance Requirements</h2>
      {attendance?.map((a: any) => (
        <div key={a.zone_id} style={{ fontSize: 14 }}>
          {a.label} — {a.required_per_week}x per week
        </div>
      ))}

      <h2>Gear Check</h2>
      {gear && (
        <pre style={{ background: '#1a1a2e', padding: '1rem', borderRadius: 8, fontSize: 12 }}>
          {JSON.stringify(gear, null, 2)}
        </pre>
      )}
    </Layout>
  )
}
```

**Step 3: Commit**

```bash
git add web/frontend/src/pages/Attendance.tsx web/frontend/src/pages/Config.tsx
git commit -m "feat(web): implement Attendance and Config reference pages"
```

---

## Phase 5: Deployment

### Task 16: Docker Compose setup

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile.web`
- Modify: `web/api/main.py` (add static file serving)

**Step 1: Create `Dockerfile.web`**

```dockerfile
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY web/frontend/package*.json ./
RUN npm ci
COPY web/frontend/ .
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
COPY web/requirements.txt web-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r web-requirements.txt

COPY src/ src/
COPY web/ web/
COPY config.yaml .

COPY --from=frontend-build /frontend/dist web/frontend/dist

CMD ["uvicorn", "web.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create `docker-compose.yml`**

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: crankguild
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  bot:
    build:
      context: .
      dockerfile: Dockerfile
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped

  web-api:
    build:
      context: .
      dockerfile: Dockerfile.web
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/crankguild
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    restart: unless-stopped

  sync-worker:
    build:
      context: .
      dockerfile: Dockerfile.web
    command: ["python", "-m", "web.api.sync.run"]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/crankguild
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  pgdata:
```

**Step 3: Add static file serving to `web/api/main.py`**

Add to the end of main.py:

```python
import os
from fastapi.staticfiles import StaticFiles

# Serve React build in production
static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
```

**Step 4: Create sync worker entry point `web/api/sync/run.py`**

```python
import asyncio
import os
import logging

from dotenv import load_dotenv
load_dotenv()

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from web.api.sync.worker import SyncWorker
from web.api.database import engine
from web.api.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    wcl = WarcraftLogsClient(
        client_id=os.getenv("WARCRAFTLOGS_CLIENT_ID", ""),
        client_secret=os.getenv("WARCRAFTLOGS_CLIENT_SECRET", ""),
    )
    config = ConfigLoader()

    worker = SyncWorker(wcl, config)

    # Run initial sync
    logger.info("Running initial sync...")
    await worker.run_roster_sync()
    await worker.run_reports_sync()

    # Start scheduler
    worker.start()
    logger.info("Sync worker running. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 5: Commit**

```bash
git add docker-compose.yml Dockerfile.web web/api/main.py web/api/sync/run.py
git commit -m "feat(web): add Docker Compose with postgres, web-api, sync-worker services"
```

---

### Task 17: Integration test — full stack smoke test

**Files:**
- Create: `tests/test_web_integration.py`

**Step 1: Write integration test**

```python
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_endpoint():
    from web.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_config_specs_returns_data():
    from web.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/specs")
    assert response.status_code == 200
    data = response.json()
    assert "warrior:protection" in data


@pytest.mark.asyncio
async def test_config_consumables_returns_list():
    from web.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/consumables")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Step 2: Run tests**

Run: `pytest tests/test_web_integration.py -v`
Expected: 3 PASS (config endpoints read from config.yaml directly, no DB needed)

**Step 3: Commit**

```bash
git add tests/test_web_integration.py
git commit -m "test(web): add integration smoke tests for health and config endpoints"
```

---

### Task 18: Update CI and documentation

**Files:**
- Modify: `.github/workflows/ci.yml` (add web deps to test matrix)
- Modify: `requirements-dev.txt` (add httpx for route tests)

**Step 1: Add httpx to dev dependencies**

Add to `requirements-dev.txt`:

```
httpx==0.27.0
```

**Step 2: Update CI workflow to install web requirements**

Add to the install step in `.github/workflows/ci.yml`:

```yaml
- run: pip install -r web/requirements.txt
```

**Step 3: Run all tests to ensure nothing is broken**

Run: `pytest -v`
Expected: All existing 80 tests pass + new web tests pass

**Step 4: Commit**

```bash
git add .github/workflows/ci.yml requirements-dev.txt
git commit -m "ci: add web dependencies to test pipeline"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-3 | Backend foundation: FastAPI scaffold, DB models, Alembic |
| 2 | 4-6 | Sync worker: roster sync, report processing, scheduler |
| 3 | 7-8 | API endpoints: all REST routes |
| 4 | 9-15 | React frontend: all pages and components |
| 5 | 16-18 | Deployment: Docker Compose, integration tests, CI |

**Total: 18 tasks, ~45 commits**
