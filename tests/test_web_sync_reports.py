import pytest
from unittest.mock import AsyncMock


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
    wcl.get_report_fights.return_value = [
        {"id": 1, "name": "Gruul", "kill": True, "startTime": 0,
         "endTime": 180000, "fightPercentage": 0, "encounterID": 649},
    ]
    wcl.get_report_deaths.return_value = [
        {"name": "Testplayer", "type": "Player", "deathTime": 90000,
         "damage": {"total": 15000, "entries": [
             {"ability": {"name": "Shatter"}, "amount": 15000}
         ]}}
    ]
    wcl.get_fight_stats.return_value = {
        "Testplayer": {"damage_done": 216000, "dps": 1200, "healing_done": 0, "hps": 0},
        "Healbot": {"damage_done": 0, "dps": 0, "healing_done": 300000, "hps": 1666.7},
    }
    wcl.get_report_player_specs.return_value = {}
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


@pytest.mark.asyncio
async def test_process_report_includes_fights_and_deaths(mock_wcl):
    from web.api.sync.reports import process_report
    from src.config.loader import ConfigLoader

    config = ConfigLoader()
    result = await process_report(
        wcl=mock_wcl,
        report_code="abc123",
        config=config,
    )
    assert "fights" in result
    assert "deaths" in result
    assert "fight_stats" in result
    assert len(result["fights"]) == 1
    assert result["fights"][0]["encounter_name"] == "Gruul"
    assert len(result["deaths"]) == 1
    assert result["deaths"][0]["player_name"] == "Testplayer"
    assert len(result["fight_stats"]) == 2
