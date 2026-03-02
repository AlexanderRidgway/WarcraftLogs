import pytest
from httpx import AsyncClient, ASGITransport
from web.api.main import app


@pytest.fixture
def transport():
    return ASGITransport(app=app)


@pytest.mark.asyncio
async def test_health(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_config_specs(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/specs")
    assert response.status_code == 200
    data = response.json()
    assert "warrior:protection" in data


@pytest.mark.asyncio
async def test_config_consumables(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/consumables")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_config_attendance(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/attendance")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_gear(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config/gear")
    assert response.status_code == 200
    data = response.json()
    assert "min_avg_ilvl" in data


@pytest.fixture
async def db_transport():
    """Create a test transport with an in-memory SQLite database."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from web.api.models import Base
    from web.api.database import get_db

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield ASGITransport(app=app)
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_report_utility_not_found(db_transport):
    async with AsyncClient(transport=db_transport, base_url="http://test") as client:
        response = await client.get("/api/reports/NONEXISTENT/utility")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_report_gear_not_found(db_transport):
    async with AsyncClient(transport=db_transport, base_url="http://test") as client:
        response = await client.get("/api/reports/NONEXISTENT/gear")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_weekly_recap_default(db_transport):
    async with AsyncClient(transport=db_transport, base_url="http://test") as client:
        response = await client.get("/api/weekly")
    assert response.status_code == 200
    data = response.json()
    assert "week_start" in data
    assert "week_end" in data
    assert "report_count" in data
    assert "top_performers" in data
    assert "zone_summaries" in data
    assert "attendance" in data
    assert "gear_issues" in data


@pytest.mark.asyncio
async def test_weekly_recap_past_week(db_transport):
    async with AsyncClient(transport=db_transport, base_url="http://test") as client:
        response = await client.get("/api/weekly?weeks_ago=1")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["top_performers"], list)
    assert isinstance(data["zone_summaries"], list)


@pytest.mark.asyncio
async def test_report_with_consumable_flags(db_transport):
    """Test that get_report includes consumable_flags in response."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from web.api.models import Base, Report, Player, ConsumablesData
    from web.api.database import get_db
    from datetime import datetime

    # Get the session from the override
    override = app.dependency_overrides[get_db]
    async for session in override():
        # Create test data
        report = Report(
            code="TESTFLAGS", zone_id=1007, zone_name="The Eye",
            start_time=datetime(2025, 1, 1), end_time=datetime(2025, 1, 1, 3),
            player_names=["TestPlayer"],
        )
        player = Player(name="TestPlayer", class_id=1, class_name="warrior", server="test", region="US")
        session.add_all([report, player])
        await session.flush()

        # Add consumable data with no flask and no potions
        c1 = ConsumablesData(
            player_id=player.id, report_code="TESTFLAGS",
            metric_name="flask_uptime", label="Flask", actual_value=0, target_value=100,
        )
        session.add(c1)
        await session.commit()

    async with AsyncClient(transport=db_transport, base_url="http://test") as client:
        response = await client.get("/api/reports/TESTFLAGS")
    assert response.status_code == 200
    data = response.json()
    assert "consumable_flags" in data
    flags = data["consumable_flags"]
    assert len(flags) == 1
    assert flags[0]["player_name"] == "TestPlayer"
    assert flags[0]["passed"] is False
    assert "No flask/elixirs" in flags[0]["reasons"]
