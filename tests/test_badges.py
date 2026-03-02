import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from web.api.models import (
    Base, Player, Score, Report, Fight, Death, Badge,
    ConsumablesData, GearSnapshot,
)
from web.api.badges import (
    _check_flask_master, _check_deathless, _check_geared_up, _award_badge,
)


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def player(db):
    p = Player(name="TestPlayer", class_id=1, class_name="warrior", server="test", region="US")
    db.add(p)
    await db.flush()
    return p


def _add_report_and_score(db, player, code, zone_name="The Eye"):
    """Helper to add a report and score for a player."""
    report = Report(
        code=code, zone_id=1007, zone_name=zone_name,
        start_time=datetime(2026, 1, 1), end_time=datetime(2026, 1, 1, 1),
        player_names=[player.name],
    )
    db.add(report)
    score = Score(
        player_id=player.id, report_code=code, spec="warrior:fury",
        overall_score=80, parse_score=80,
    )
    db.add(score)
    return report, score


@pytest.mark.asyncio
async def test_flask_master_awarded(db, player):
    """Flask master badge awarded with 4+ consecutive raids at >= 95% flask uptime."""
    for i in range(5):
        code = f"RPT{i:03d}"
        _add_report_and_score(db, player, code)
        db.add(ConsumablesData(
            player_id=player.id, report_code=code,
            metric_name="flask_uptime", label="Flask",
            actual_value=98.0, target_value=100.0, optional=False,
        ))
    await db.flush()

    await _check_flask_master(db, player)
    await db.flush()

    badges = [b for b in (await db.execute(
        __import__('sqlalchemy').select(Badge).where(Badge.player_id == player.id, Badge.badge_type == "flask_master")
    )).scalars().all()]
    assert len(badges) == 1
    assert "consecutive" in badges[0].details


@pytest.mark.asyncio
async def test_flask_master_not_awarded_below_threshold(db, player):
    """Flask master not awarded when uptime is below 95%."""
    for i in range(4):
        code = f"RPT{i:03d}"
        _add_report_and_score(db, player, code)
        db.add(ConsumablesData(
            player_id=player.id, report_code=code,
            metric_name="flask_uptime", label="Flask",
            actual_value=80.0, target_value=100.0, optional=False,
        ))
    await db.flush()

    await _check_flask_master(db, player)
    await db.flush()

    badges = [b for b in (await db.execute(
        __import__('sqlalchemy').select(Badge).where(Badge.player_id == player.id, Badge.badge_type == "flask_master")
    )).scalars().all()]
    assert len(badges) == 0


@pytest.mark.asyncio
async def test_deathless_awarded(db, player):
    """Deathless badge awarded for zero deaths in a full clear."""
    report, score = _add_report_and_score(db, player, "CLEAR01", "Karazhan")
    await db.flush()

    # Add a fight that is a kill with no deaths for this player
    fight = Fight(
        report_code="CLEAR01", fight_id=1, encounter_name="Attumen",
        kill=True, duration_ms=120000, fight_percentage=0,
        start_time=0, end_time=120000,
    )
    db.add(fight)
    await db.flush()
    # No deaths added for this player

    await _check_deathless(db, player)
    await db.flush()

    badges = [b for b in (await db.execute(
        __import__('sqlalchemy').select(Badge).where(Badge.player_id == player.id, Badge.badge_type == "deathless")
    )).scalars().all()]
    assert len(badges) == 1
    assert "Karazhan" in badges[0].details


@pytest.mark.asyncio
async def test_deathless_not_awarded_with_deaths(db, player):
    """Deathless not awarded when player has deaths."""
    report, score = _add_report_and_score(db, player, "DEATH01")
    await db.flush()

    fight = Fight(
        report_code="DEATH01", fight_id=1, encounter_name="Gruul",
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
    await db.flush()

    await _check_deathless(db, player)
    await db.flush()

    badges = [b for b in (await db.execute(
        __import__('sqlalchemy').select(Badge).where(Badge.player_id == player.id, Badge.badge_type == "deathless")
    )).scalars().all()]
    assert len(badges) == 0


@pytest.mark.asyncio
async def test_geared_up_awarded(db, player):
    """Geared up badge awarded when all items are epic+ with enchants."""
    report, score = _add_report_and_score(db, player, "GEAR01")
    await db.flush()

    # Add gear: all epic (quality=4), enchanted slots have enchants
    for slot in [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]:
        db.add(GearSnapshot(
            player_id=player.id, report_code="GEAR01",
            slot=slot, item_id=30000 + slot, item_level=128,
            quality=4, permanent_enchant=2600 + slot, gems=[],
        ))
    # Non-enchantable slots
    for slot in [3, 10, 11, 12, 13]:
        db.add(GearSnapshot(
            player_id=player.id, report_code="GEAR01",
            slot=slot, item_id=30000 + slot, item_level=128,
            quality=4, permanent_enchant=None, gems=[],
        ))
    await db.flush()

    await _check_geared_up(db, player)
    await db.flush()

    badges = [b for b in (await db.execute(
        __import__('sqlalchemy').select(Badge).where(Badge.player_id == player.id, Badge.badge_type == "geared_up")
    )).scalars().all()]
    assert len(badges) == 1
    assert "GEAR01" in badges[0].details


@pytest.mark.asyncio
async def test_geared_up_not_awarded_green_items(db, player):
    """Geared up not awarded when items are below epic quality."""
    report, score = _add_report_and_score(db, player, "GEAR02")
    await db.flush()

    # quality=2 (green) — should fail
    db.add(GearSnapshot(
        player_id=player.id, report_code="GEAR02",
        slot=0, item_id=30000, item_level=100,
        quality=2, permanent_enchant=2600, gems=[],
    ))
    await db.flush()

    await _check_geared_up(db, player)
    await db.flush()

    badges = [b for b in (await db.execute(
        __import__('sqlalchemy').select(Badge).where(Badge.player_id == player.id, Badge.badge_type == "geared_up")
    )).scalars().all()]
    assert len(badges) == 0
