import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from web.api.main import app
from web.api.auth import hash_password, verify_password, create_access_token
from web.api.database import get_db
from web.api.models import Base


@pytest.fixture
def transport():
    return ASGITransport(app=app)


@pytest.fixture
async def db_transport():
    """Transport with an in-memory SQLite database override for get_db."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield ASGITransport(app=app)
    app.dependency_overrides.clear()
    await engine.dispose()


def test_hash_and_verify_password():
    hashed = hash_password("testpass")
    assert verify_password("testpass", hashed)
    assert not verify_password("wrong", hashed)


def test_create_access_token():
    token = create_access_token("admin")
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.asyncio
async def test_login_missing_user(db_transport):
    async with AsyncClient(transport=db_transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={"username": "nobody", "password": "pass"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_no_token(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_bad_token(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_config_no_auth(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/config/specs/warrior:protection/contributions/sunder_armor_uptime",
            json={"target": 90},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_sync_no_auth(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/sync/trigger")
    assert response.status_code == 401
