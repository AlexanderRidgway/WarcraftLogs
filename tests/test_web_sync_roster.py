import pytest
from unittest.mock import AsyncMock


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
