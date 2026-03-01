import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from web.api.models import Base, Player, Fight, Death, FightPlayerStats, Badge


def test_models_importable():
    from web.api.models import Base, Player, Report, Ranking, Score
    from web.api.models import GearSnapshot, UtilityData, ConsumablesData
    from web.api.models import AttendanceRecord, SyncStatus, User
    from web.api.models import Fight, Death, FightPlayerStats, Badge
    assert len(Base.metadata.tables) == 14


def test_player_table_columns():
    from web.api.models import Player
    columns = {c.name for c in Player.__table__.columns}
    assert columns == {"id", "name", "class_id", "class_name", "server", "region", "last_synced_at"}


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
