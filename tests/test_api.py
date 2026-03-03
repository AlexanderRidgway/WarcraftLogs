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
                "char0": {
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
                                {"name": "Sunder Armor", "guid": 7386, "totalUptime": 85000, "type": "debuff"},
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
                                {"name": "Thunderclap", "guid": 6343, "total": 12},
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
                                {"name": "Flask of Relentless Assault", "guid": 28520, "totalUptime": 90000},
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


@pytest.mark.asyncio
async def test_get_guild_reports():
    """Returns list of reports with code, startTime, zone, and player names."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "reports": {
                    "data": [
                        {
                            "code": "abc123",
                            "startTime": 1709000000000,
                            "zone": {"id": 1002, "name": "Karazhan"},
                            "rankedCharacters": [
                                {"name": "Thrallbro"},
                                {"name": "Healbot"},
                            ],
                        },
                        {
                            "code": "def456",
                            "startTime": 1709100000000,
                            "zone": {"id": 1004, "name": "Gruul's Lair"},
                            "rankedCharacters": [
                                {"name": "Thrallbro"},
                            ],
                        },
                    ]
                }
            }
        }
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response):
        reports = await client.get_guild_reports("TestGuild", "stormrage", "US", 1709000000000, 1709200000000)

    assert len(reports) == 2
    assert reports[0]["code"] == "abc123"
    assert reports[0]["zone"]["id"] == 1002
    assert len(reports[0]["players"]) == 2
    assert reports[0]["players"][0] == "Thrallbro"


@pytest.mark.asyncio
async def test_get_guild_reports_empty():
    """Returns empty list when no reports found."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "reports": {
                    "data": []
                }
            }
        }
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response):
        reports = await client.get_guild_reports("TestGuild", "stormrage", "US", 1709000000000, 1709200000000)

    assert reports == []


@pytest.mark.asyncio
async def test_get_guild_reports_null_zone_skipped():
    """Reports with null zone are excluded from results."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "reports": {
                    "data": [
                        {
                            "code": "abc123",
                            "startTime": 1709000000000,
                            "zone": None,
                            "rankedCharacters": [{"name": "Thrallbro"}],
                        },
                        {
                            "code": "def456",
                            "startTime": 1709100000000,
                            "zone": {"id": 1002, "name": "Karazhan"},
                            "rankedCharacters": [{"name": "Thrallbro"}],
                        },
                    ]
                }
            }
        }
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response):
        reports = await client.get_guild_reports("TestGuild", "stormrage", "US", 1709000000000, 1709200000000)

    assert len(reports) == 1
    assert reports[0]["code"] == "def456"


@pytest.mark.asyncio
async def test_get_report_gear():
    """Returns list of players with their gear arrays from a report summary."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_table_data = {
        "playerDetails": {
            "tanks": [
                {
                    "name": "Thrallbro",
                    "id": 5,
                    "combatantInfo": {
                        "gear": [
                            {"id": 28785, "slot": 0, "quality": 4, "itemLevel": 125, "permanentEnchant": 3003, "gems": [{"id": 24027}]},
                            {"id": 27803, "slot": 4, "quality": 3, "itemLevel": 112, "permanentEnchant": 2661, "gems": []},
                        ],
                    },
                },
            ],
            "healers": [
                {
                    "name": "Healbot",
                    "id": 7,
                    "combatantInfo": {
                        "gear": [
                            {"id": 12345, "slot": 0, "quality": 2, "itemLevel": 87, "gems": []},
                        ],
                    },
                },
            ],
            "dps": [],
        }
    }

    async def mock_query_table(report_code, source_id, start, end, data_type):
        return mock_table_data

    client._query_table = mock_query_table
    result = await client.get_report_gear("abc123")

    assert len(result) == 2
    assert result[0]["name"] == "Thrallbro"
    assert len(result[0]["gear"]) == 2
    assert result[0]["gear"][0]["quality"] == 4
    assert result[1]["name"] == "Healbot"
    assert result[1]["gear"][0]["quality"] == 2


@pytest.mark.asyncio
async def test_get_report_gear_empty():
    """Returns empty list when no player details found."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    async def mock_query_table(report_code, source_id, start, end, data_type):
        return {"playerDetails": {"tanks": [], "healers": [], "dps": []}}

    client._query_table = mock_query_table
    result = await client.get_report_gear("abc123")

    assert result == []


@pytest.mark.asyncio
async def test_get_report_fights():
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
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
    }

    with patch.object(client, "query", new_callable=AsyncMock, return_value=mock_response):
        fights = await client.get_report_fights("TEST")
    assert len(fights) == 2
    assert fights[0]["name"] == "Gruul"
    assert fights[0]["kill"] is True
    assert fights[1]["kill"] is False


@pytest.mark.asyncio
async def test_get_report_deaths():
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_table_data = {
        "entries": [
            {"name": "Thrall", "id": 3, "type": "Player",
             "deathTime": 145000,
             "damage": {"total": 25000, "entries": [
                 {"ability": {"name": "Shatter"}, "amount": 25000}
             ]}}
        ]
    }

    async def mock_query_table(report_code, source_id, start, end, data_type):
        assert data_type == "Deaths"
        return mock_table_data

    client._query_table = mock_query_table
    deaths = await client.get_report_deaths("TEST", 0, 180000)
    assert len(deaths) == 1
    assert deaths[0]["name"] == "Thrall"


@pytest.mark.asyncio
async def test_get_fight_stats():
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    call_types = []
    async def mock_query_table(report_code, source_id, start, end, data_type):
        call_types.append(data_type)
        if data_type == "DamageDone":
            return {"entries": [
                {"name": "Warrior", "type": "Player", "total": 360000},
                {"name": "Boss", "type": "NPC", "total": 0},
            ]}
        elif data_type == "Healing":
            return {"entries": [
                {"name": "Healer", "type": "Player", "total": 500000},
                {"name": "Warrior", "type": "Player", "total": 10000},
            ]}
        return {"entries": []}

    client._query_table = mock_query_table
    stats = await client.get_fight_stats("TEST", 0, 180000)

    assert "DamageDone" in call_types
    assert "Healing" in call_types
    assert stats["Warrior"]["damage_done"] == 360000
    assert stats["Warrior"]["dps"] == 2000.0
    assert stats["Warrior"]["healing_done"] == 10000
    assert stats["Healer"]["healing_done"] == 500000
    assert stats["Healer"]["damage_done"] == 0


@pytest.mark.asyncio
async def test_get_fight_stats_zero_duration():
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    stats = await client.get_fight_stats("TEST", 100, 100)
    assert stats == {}


@pytest.mark.asyncio
async def test_pull_check_returns_100_when_cast_in_window():
    """pull_check type should return 100 if the spell was cast in the pull window."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [
                                {"name": "Misdirection", "guid": 34477, "total": 1},
                            ],
                        }
                    }
                }
            }
        }
    }

    contributions = [
        {"spell_id": 34477, "metric": "md_pull", "type": "pull_check", "window_ms": 15000}
    ]

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_utility_data("abc", source_id=1, start=0, end=300000, contributions=contributions)
    assert result["md_pull"] == 100.0
    # Verify the query used the pull window (start + 15000), not the full fight end
    call_args = client.query.call_args
    assert call_args[0][1]["endTime"] == 15000


@pytest.mark.asyncio
async def test_pull_check_returns_0_when_not_cast():
    """pull_check type should return 0 if the spell was not cast in the pull window."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [],
                        }
                    }
                }
            }
        }
    }

    contributions = [
        {"spell_id": 34477, "metric": "md_pull", "type": "pull_check", "window_ms": 15000}
    ]

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_utility_data("abc", source_id=1, start=0, end=300000, contributions=contributions)
    assert result["md_pull"] == 0.0


@pytest.mark.asyncio
async def test_get_raid_casts_by_source():
    """get_raid_casts_by_source queries Casts without sourceID and groups by source."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [
                                {"name": "Dispel Magic", "guid": 527, "id": 527, "total": 15,
                                 "sources": [
                                     {"name": "PriestA", "id": 1, "total": 10},
                                     {"name": "PriestB", "id": 2, "total": 5},
                                 ]},
                            ]
                        }
                    }
                }
            }
        }
    }

    contrib = {"spell_id": 527, "metric": "dispel_magic_count"}

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_raid_casts_by_source("abc", 0, 300000, contrib)

    assert result == {1: 10, 2: 5}
    # Verify sourceID was None (no per-player filter)
    call_args = client.query.call_args
    assert call_args[0][1]["sourceID"] is None


@pytest.mark.asyncio
async def test_get_raid_casts_by_source_spell_ids_list():
    """get_raid_casts_by_source works with spell_ids list and sums matching entries."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [
                                {"name": "Curse of Elements", "guid": 27228, "id": 27228, "total": 8,
                                 "sources": [
                                     {"name": "WarlockA", "id": 3, "total": 5},
                                     {"name": "WarlockB", "id": 4, "total": 3},
                                 ]},
                                {"name": "Curse of Recklessness", "guid": 27226, "id": 27226, "total": 4,
                                 "sources": [
                                     {"name": "WarlockA", "id": 3, "total": 4},
                                 ]},
                                {"name": "Shadow Bolt", "guid": 99999, "id": 99999, "total": 200,
                                 "sources": [
                                     {"name": "WarlockA", "id": 3, "total": 200},
                                 ]},
                            ]
                        }
                    }
                }
            }
        }
    }

    contrib = {"spell_ids": [27228, 27218, 30910, 27226, 11719, 30909], "metric": "curse_count"}

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_raid_casts_by_source("abc", 0, 300000, contrib)

    # WarlockA: 5 (elements) + 4 (recklessness) = 9
    # WarlockB: 3 (elements)
    # Shadow Bolt is NOT matched (not in spell_ids)
    assert result == {3: 9, 4: 3}


@pytest.mark.asyncio
async def test_get_raid_casts_by_source_no_matches():
    """Returns empty dict when no casts match the spell."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_response = {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [
                                {"name": "Shadow Bolt", "guid": 99999, "id": 99999, "total": 200,
                                 "sources": [{"name": "WarlockA", "id": 3, "total": 200}]},
                            ]
                        }
                    }
                }
            }
        }
    }

    contrib = {"spell_id": 527, "metric": "dispel_magic_count"}
    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_raid_casts_by_source("abc", 0, 300000, contrib)
    assert result == {}


@pytest.mark.asyncio
async def test_get_raid_buff_uptime_debuff():
    """get_raid_buff_uptime queries Debuffs with hostilityType=Enemies for enemy debuffs."""
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
                                {"name": "Faerie Fire", "guid": 770, "totalUptime": 85000},
                                {"name": "Faerie Fire (Feral)", "guid": 16857, "totalUptime": 10000},
                            ],
                            "totalTime": 100000,
                        }
                    }
                }
            }
        }
    }

    contrib = {"spell_ids": [770, 16857], "metric": "faerie_fire_uptime", "type": "shared_responsibility", "target": 85}

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_raid_buff_uptime("abc", 0, 100000, contrib)

    # Best matching aura uptime: 85000/100000 = 85%
    assert result == pytest.approx(85.0, abs=0.1)
    # Verify hostilityType=Enemies was used (no subtype=buff)
    call_args = client.query.call_args
    assert call_args[0][1]["hostilityType"] == "Enemies"


@pytest.mark.asyncio
async def test_get_raid_buff_uptime_buff():
    """get_raid_buff_uptime queries Buffs table for subtype=buff."""
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
                                {"name": "Power Word: Fortitude", "guid": 25392, "totalUptime": 90000},
                            ],
                            "totalTime": 100000,
                        }
                    }
                }
            }
        }
    }

    contrib = {"spell_id": 25392, "metric": "fortitude_uptime", "type": "shared_responsibility",
               "subtype": "buff", "target": 95}

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_raid_buff_uptime("abc", 0, 100000, contrib)

    assert result == pytest.approx(90.0, abs=0.1)
    # Verify Buffs table used (no hostilityType)
    call_args = client.query.call_args
    assert "hostilityType" not in call_args[0][1]


@pytest.mark.asyncio
async def test_get_raid_buff_uptime_no_aura():
    """Returns 0.0 when aura not found."""
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

    contrib = {"spell_id": 25392, "metric": "fortitude_uptime", "type": "shared_responsibility",
               "subtype": "buff", "target": 95}

    client.query = AsyncMock(return_value=mock_response)
    result = await client.get_raid_buff_uptime("abc", 0, 100000, contrib)
    assert result == 0.0
