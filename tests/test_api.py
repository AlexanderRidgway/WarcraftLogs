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


@pytest.mark.asyncio
async def test_get_utility_data_with_spell_ids_list():
    """spell_ids list should match any aura whose id is in the list."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "auras": [
                                {"name": "Flask of Relentless Assault", "id": 28520, "totalUptime": 90000},
                            ],
                            "totalTime": 100000,
                        }
                    }
                }
            }
        }
    }

    contributions = [
        {
            "spell_ids": [17628, 17627, 28518, 28520, 28521],
            "metric": "flask_uptime",
            "type": "uptime",
            "subtype": "buff",
        }
    ]

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_utility_data("abc", source_id=1, start=0, end=100000, contributions=contributions)
    assert result["flask_uptime"] == pytest.approx(90.0, abs=0.1)


@pytest.mark.asyncio
async def test_get_utility_data_spell_ids_list_no_match_returns_zero():
    """spell_ids list with no matching aura should return 0.0."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "auras": [],
                            "totalTime": 100000,
                        }
                    }
                }
            }
        }
    }

    contributions = [
        {"spell_ids": [17628, 28520], "metric": "flask_uptime", "type": "uptime", "subtype": "buff"}
    ]

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_utility_data("abc", source_id=1, start=0, end=100000, contributions=contributions)
    assert result["flask_uptime"] == 0.0


@pytest.mark.asyncio
async def test_get_report_players():
    """Returns list of player actors with name and id."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "masterData": {
                        "actors": [
                            {"id": 3, "name": "Thrallbro", "type": "Player"},
                            {"id": 7, "name": "Healbot", "type": "Player"},
                            {"id": 12, "name": "Some NPC", "type": "NPC"},
                        ]
                    }
                }
            }
        }
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response):
        players = await client.get_report_players("abc123")

    assert len(players) == 2
    assert players[0] == {"id": 3, "name": "Thrallbro"}
    assert players[1] == {"id": 7, "name": "Healbot"}


@pytest.mark.asyncio
async def test_get_report_timerange():
    """Returns start and end timestamps for the full report."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "startTime": 1000000,
                    "endTime": 1090000,
                }
            }
        }
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response):
        timerange = await client.get_report_timerange("abc123")

    assert timerange == {"start": 0, "end": 90000}
