import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.warcraftlogs import WarcraftLogsClient

@pytest.mark.asyncio
async def test_get_access_token():
    client = WarcraftLogsClient(client_id="test_id", client_secret="test_secret")

    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"access_token": "abc123", "expires_in": 3600})
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.post", return_value=mock_response):
        token = await client._fetch_token()

    assert token == "abc123"


@pytest.mark.asyncio
async def test_token_cached_until_expiry():
    client = WarcraftLogsClient(client_id="test_id", client_secret="test_secret")
    client._token = "cached_token"
    client._token_expiry = float("inf")

    token = await client._get_token()
    assert token == "cached_token"


@pytest.mark.asyncio
async def test_expired_token_triggers_refetch():
    client = WarcraftLogsClient(client_id="test_id", client_secret="test_secret")
    client._token = "old_token"
    client._token_expiry = 0  # expired

    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"access_token": "new_token", "expires_in": 3600})
    mock_response.raise_for_status = MagicMock()
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession.post", return_value=mock_response):
        token = await client._get_token()

    assert token == "new_token"


@pytest.mark.asyncio
async def test_get_guild_roster():
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response_data = {
        "data": {
            "guildData": {
                "guild": {
                    "members": {
                        "data": [
                            {
                                "name": "Thrallbro",
                                "classID": 1,
                                "server": {"slug": "stormrage", "region": {"slug": "us"}},
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response_data):
        roster = await client.get_guild_roster("TestGuild", "stormrage", "US")

    assert len(roster) == 1
    assert roster[0]["name"] == "Thrallbro"


@pytest.mark.asyncio
async def test_get_character_rankings():
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response_data = {
        "data": {
            "characterData": {
                "character": {
                    "zoneRankings": {
                        "rankings": [
                            {
                                "encounter": {"name": "Gruul the Dragonkiller"},
                                "rankPercent": 87.5,
                                "spec": "Protection",
                            }
                        ]
                    }
                }
            }
        }
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response_data):
        rankings = await client.get_character_rankings(
            "Thrallbro", "stormrage", "US", zone_id=1007
        )

    assert len(rankings) == 1
    assert rankings[0]["rankPercent"] == 87.5
    assert rankings[0]["encounter"]["name"] == "Gruul the Dragonkiller"


@pytest.mark.asyncio
async def test_get_report_utility_data():
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_uptime_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "auras": [
                                {"name": "Sunder Armor", "id": 7386, "totalUptime": 85000, "type": "debuff"},
                            ],
                            "totalTime": 100000,
                        }
                    }
                }
            }
        }
    }

    mock_cast_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [
                                {"name": "Thunderclap", "id": 6343, "total": 12},
                            ]
                        }
                    }
                }
            }
        }
    }

    contributions = [
        {"spell_id": 7386, "metric": "sunder_armor_uptime", "type": "uptime"},
        {"spell_id": 6343, "metric": "thunderclap_count", "type": "count"},
    ]

    call_count = 0
    async def mock_query(gql, variables=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_uptime_response
        return mock_cast_response

    client.query = mock_query
    result = await client.get_utility_data("abc123", source_id=5, start=0, end=100000, contributions=contributions)

    assert result["sunder_armor_uptime"] == pytest.approx(85.0, abs=0.1)
    assert result["thunderclap_count"] == 12
    assert call_count == 2
