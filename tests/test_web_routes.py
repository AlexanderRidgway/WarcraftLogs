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
