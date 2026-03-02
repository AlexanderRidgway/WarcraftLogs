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
    wcl.get_report_rankings.return_value = (
        [
            {"name": "Testplayer", "class": "Warrior", "spec": "Fury", "rankPercent": 85.5},
            {"name": "Healbot", "class": "Priest", "spec": "Holy", "rankPercent": 72.0},
        ],
        [
            {"name": "Testplayer", "encounter_name": "Void Reaver", "rankPercent": 85.5},
            {"name": "Healbot", "encounter_name": "Void Reaver", "rankPercent": 72.0},
        ],
    )
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


def test_validate_spec_key_alias_normalization():
    from web.api.sync.reports import _validate_spec_key

    assert _validate_spec_key("Paladin", "Justicar") == "paladin:protection"
    assert _validate_spec_key("Druid", "Guardian") == "druid:feral"
    assert _validate_spec_key("Hunter", "BeastMastery") == "hunter:beast mastery"
    assert _validate_spec_key("Hunter", "beast-mastery") == "hunter:beast mastery"
    assert _validate_spec_key("Warrior", "Warden") == "warrior:protection"
    assert _validate_spec_key("Warrior", "Gladiator") == "warrior:protection"
    # Standard names still work
    assert _validate_spec_key("Warrior", "Fury") == "warrior:fury"
    assert _validate_spec_key("Priest", "Shadow") == "priest:shadow"


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
    assert len(result["rankings"]) == 4  # 2 averages + 2 per-fight


@pytest.mark.asyncio
async def test_fetch_new_reports_skips_duplicate_zone_time(mock_wcl):
    from datetime import datetime
    from web.api.sync.reports import fetch_new_reports

    # Existing report has same zone and start_time within 90 min
    existing_reports = [
        {"zone_id": 1007, "start_time": datetime.utcfromtimestamp(1700000000000 / 1000)},
    ]
    reports = await fetch_new_reports(
        wcl=mock_wcl,
        guild_name="CRANK",
        server_slug="stormrage",
        region="us",
        days_back=7,
        existing_codes=set(),
        existing_reports=existing_reports,
    )
    assert len(reports) == 0


@pytest.mark.asyncio
async def test_fetch_new_reports_allows_different_zone(mock_wcl):
    from datetime import datetime
    from web.api.sync.reports import fetch_new_reports

    # Existing report has different zone_id — should not be considered a duplicate
    existing_reports = [
        {"zone_id": 1004, "start_time": datetime.utcfromtimestamp(1700000000000 / 1000)},
    ]
    reports = await fetch_new_reports(
        wcl=mock_wcl,
        guild_name="CRANK",
        server_slug="stormrage",
        region="us",
        days_back=7,
        existing_codes=set(),
        existing_reports=existing_reports,
    )
    assert len(reports) == 1


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
