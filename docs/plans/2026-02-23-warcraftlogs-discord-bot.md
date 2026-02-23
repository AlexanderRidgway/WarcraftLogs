# WarcraftLogs Discord Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python Discord bot that queries the WarcraftLogs GraphQL API to score TBC raiders on parse percentile + utility/debuff contribution, with officer slash commands for rankings, individual reports, raid recaps, and config management.

**Architecture:** A single `discord.py` process handles slash commands. Each command triggers async calls to the WarcraftLogs GraphQL API to fetch parse and cast/uptime data. A scoring engine applies per-spec weights from a `config.yaml` to produce consistency scores.

**Tech Stack:** Python 3.11+, discord.py 2.x, aiohttp, pyyaml, python-dotenv, pytest, pytest-asyncio

---

## Project Structure

```
WarcraftLogs/
├── docs/plans/
├── src/
│   ├── bot.py                  # Entry point, bot init, command registration
│   ├── api/
│   │   └── warcraftlogs.py     # GraphQL API client (auth + queries)
│   ├── commands/
│   │   ├── topconsistent.py    # /topconsistent command
│   │   ├── player.py           # /player command
│   │   ├── raidrecap.py        # /raidrecap command
│   │   └── setconfig.py        # /setconfig command
│   ├── scoring/
│   │   └── engine.py           # Weighted score calculations
│   └── config/
│       └── loader.py           # YAML config read/write
├── tests/
│   ├── test_api.py
│   ├── test_scoring.py
│   └── test_config.py
├── config.yaml                 # Class/spec profiles (officer-maintained)
├── .env                        # Credentials — DO NOT COMMIT
├── .env.example                # Template for .env
├── requirements.txt
└── .gitignore
```

---

## Pre-requisites (Complete Before Coding)

### WarcraftLogs API Setup
1. Go to https://www.warcraftlogs.com/api/clients/
2. Log in and click "Create Client"
3. Name it anything (e.g. "Guild Bot"), set redirect URL to `https://localhost`
4. Save the **Client ID** and **Client Secret**

### Discord Bot Setup
1. Go to https://discord.com/developers/applications
2. Create new application → Bot → copy the **Bot Token**
3. Under OAuth2 → URL Generator: select `bot` + `applications.commands` scopes
4. Bot permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`
5. Use the generated URL to invite the bot to your server

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `config.yaml`

**Step 1: Create requirements.txt**

```
discord.py==2.3.2
aiohttp==3.9.1
pyyaml==6.0.1
python-dotenv==1.0.0
pytest==7.4.3
pytest-asyncio==0.23.2
```

**Step 2: Create .env.example**

```
DISCORD_BOT_TOKEN=your_discord_bot_token_here
WARCRAFTLOGS_CLIENT_ID=your_client_id_here
WARCRAFTLOGS_CLIENT_SECRET=your_client_secret_here
GUILD_NAME=YourGuildName
GUILD_SERVER=your-server-slug
GUILD_REGION=US
OFFICER_ROLE_NAME=Officer
```

**Step 3: Create .gitignore**

```
.env
__pycache__/
*.pyc
.pytest_cache/
```

**Step 4: Create config.yaml with sample TBC specs**

```yaml
# Class:Spec profiles for scoring raiders.
# utility_weight + parse_weight must equal 1.0
# metric types: "uptime" (% of fight) or "count" (number of casts)
# spell_id: the WarcraftLogs spell ID for querying cast/uptime data

warrior:protection:
  utility_weight: 0.75
  parse_weight: 0.25
  contributions:
    - metric: sunder_armor_uptime
      label: "Sunder Armor"
      spell_id: 7386
      type: uptime
      target: 90
    - metric: demoralizing_shout_uptime
      label: "Demo Shout"
      spell_id: 1160
      type: uptime
      target: 85
    - metric: thunderclap_count
      label: "Thunderclap"
      spell_id: 6343
      type: count
      target: 15

warrior:fury:
  utility_weight: 0.40
  parse_weight: 0.60
  contributions:
    - metric: battle_shout_uptime
      label: "Battle Shout"
      spell_id: 6673
      type: uptime
      target: 95
    - metric: demoralizing_shout_uptime
      label: "Demo Shout"
      spell_id: 1160
      type: uptime
      target: 75

rogue:combat:
  utility_weight: 0.55
  parse_weight: 0.45
  contributions:
    - metric: expose_armor_uptime
      label: "Expose Armor"
      spell_id: 8647
      type: uptime
      target: 85

druid:feral:
  utility_weight: 0.60
  parse_weight: 0.40
  contributions:
    - metric: faerie_fire_uptime
      label: "Faerie Fire"
      spell_id: 16857
      type: uptime
      target: 90

mage:arcane:
  utility_weight: 0.20
  parse_weight: 0.80
  contributions:
    - metric: amplify_curse_uptime
      label: "Amplify Curse"
      spell_id: 12579
      type: uptime
      target: 60

warlock:affliction:
  utility_weight: 0.45
  parse_weight: 0.55
  contributions:
    - metric: curse_of_elements_uptime
      label: "Curse of Elements"
      spell_id: 1490
      type: uptime
      target: 90
```

**Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install without error.

**Step 6: Copy .env.example to .env and fill in credentials**

```bash
cp .env.example .env
# Then edit .env with your actual values
```

**Step 7: Commit**

```bash
git add requirements.txt .env.example .gitignore config.yaml
git commit -m "chore: project setup, dependencies, and initial config"
```

---

## Task 2: Config Loader

**Files:**
- Create: `src/config/loader.py`
- Create: `src/config/__init__.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
import pytest
import yaml
import os
from src.config.loader import ConfigLoader

SAMPLE_CONFIG = {
    "warrior:protection": {
        "utility_weight": 0.75,
        "parse_weight": 0.25,
        "contributions": [
            {
                "metric": "sunder_armor_uptime",
                "label": "Sunder Armor",
                "spell_id": 7386,
                "type": "uptime",
                "target": 90,
            }
        ],
    }
}


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG, f)
    return str(path)


def test_load_spec_profile(config_file):
    loader = ConfigLoader(config_file)
    profile = loader.get_spec("warrior:protection")
    assert profile["utility_weight"] == 0.75
    assert profile["parse_weight"] == 0.25
    assert len(profile["contributions"]) == 1


def test_get_unknown_spec_returns_none(config_file):
    loader = ConfigLoader(config_file)
    assert loader.get_spec("paladin:holy") is None


def test_update_target(config_file):
    loader = ConfigLoader(config_file)
    loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
    profile = loader.get_spec("warrior:protection")
    contrib = profile["contributions"][0]
    assert contrib["target"] == 95


def test_update_target_persists(config_file):
    loader = ConfigLoader(config_file)
    loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
    # Reload from disk
    loader2 = ConfigLoader(config_file)
    profile = loader2.get_spec("warrior:protection")
    assert profile["contributions"][0]["target"] == 95


def test_update_target_unknown_metric_raises(config_file):
    loader = ConfigLoader(config_file)
    with pytest.raises(ValueError, match="metric"):
        loader.update_target("warrior:protection", "nonexistent_metric", 50)


def test_all_specs(config_file):
    loader = ConfigLoader(config_file)
    specs = loader.all_specs()
    assert "warrior:protection" in specs
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError` or similar — `src/config/loader.py` does not exist yet.

**Step 3: Create `src/config/__init__.py`**

```python
```
(empty file)

**Step 4: Create `src/config/loader.py`**

```python
import yaml
from typing import Optional


class ConfigLoader:
    def __init__(self, path: str = "config.yaml"):
        self._path = path
        self._data = self._load()

    def _load(self) -> dict:
        with open(self._path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_spec(self, spec_key: str) -> Optional[dict]:
        """Return the profile for a class:spec key, or None if not configured."""
        return self._data.get(spec_key)

    def all_specs(self) -> list[str]:
        """Return all configured spec keys."""
        return list(self._data.keys())

    def update_target(self, spec_key: str, metric: str, new_target: int) -> None:
        """Update the target for a metric in a spec profile and persist to disk."""
        profile = self._data.get(spec_key)
        if profile is None:
            raise ValueError(f"Spec '{spec_key}' not found in config")

        for contrib in profile["contributions"]:
            if contrib["metric"] == metric:
                contrib["target"] = new_target
                self._save()
                return

        raise ValueError(f"metric '{metric}' not found in spec '{spec_key}'")

    def _save(self) -> None:
        with open(self._path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False)
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: All 7 tests PASS.

**Step 6: Commit**

```bash
git add src/config/ tests/test_config.py
git commit -m "feat: config loader with spec profiles and target update"
```

---

## Task 3: Scoring Engine

**Files:**
- Create: `src/scoring/__init__.py`
- Create: `src/scoring/engine.py`
- Create: `tests/test_scoring.py`

**Step 1: Write the failing tests**

Create `tests/test_scoring.py`:

```python
import pytest
from src.scoring.engine import score_player, score_consistency

PROT_WARRIOR_PROFILE = {
    "utility_weight": 0.75,
    "parse_weight": 0.25,
    "contributions": [
        {"metric": "sunder_armor_uptime", "type": "uptime", "target": 90},
        {"metric": "thunderclap_count", "type": "count", "target": 15},
    ],
}


def test_perfect_utility_and_parse():
    utility_data = {"sunder_armor_uptime": 95, "thunderclap_count": 20}
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=80, utility_data=utility_data)
    assert result == pytest.approx(100.0, abs=1.0)


def test_zero_utility():
    utility_data = {"sunder_armor_uptime": 0, "thunderclap_count": 0}
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=99, utility_data=utility_data)
    # 0 * 0.75 + 99 * 0.25 = 24.75
    assert result == pytest.approx(24.75, abs=0.1)


def test_partial_utility_capped_at_100():
    # Exceeding target should not exceed 100 per metric
    utility_data = {"sunder_armor_uptime": 200, "thunderclap_count": 100}
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=100, utility_data=utility_data)
    assert result == pytest.approx(100.0, abs=0.1)


def test_missing_utility_metric_scores_zero():
    utility_data = {"sunder_armor_uptime": 90}  # thunderclap_count missing
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=50, utility_data=utility_data)
    # utility: (100 + 0) / 2 = 50; score: 50 * 0.75 + 50 * 0.25 = 50
    assert result == pytest.approx(50.0, abs=0.1)


def test_consistency_averages_scores():
    scores = [80.0, 90.0, 70.0]
    assert score_consistency(scores) == pytest.approx(80.0, abs=0.1)


def test_consistency_empty_returns_zero():
    assert score_consistency([]) == 0.0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scoring.py -v
```

Expected: `ModuleNotFoundError` — `src/scoring/engine.py` does not exist.

**Step 3: Create `src/scoring/__init__.py`**

```python
```
(empty file)

**Step 4: Create `src/scoring/engine.py`**

```python
def score_player(spec_profile: dict, parse_percentile: float, utility_data: dict) -> float:
    """
    Compute a single-boss performance score for a player.

    Args:
        spec_profile: The class:spec config entry (weights + contributions list)
        parse_percentile: WarcraftLogs parse rank 0-100
        utility_data: Dict of metric_name -> actual value (uptime % or cast count)

    Returns:
        Score from 0-100
    """
    utility_weight = spec_profile["utility_weight"]
    parse_weight = spec_profile["parse_weight"]
    contributions = spec_profile["contributions"]

    if not contributions:
        return parse_percentile * parse_weight

    metric_scores = []
    for contrib in contributions:
        actual = utility_data.get(contrib["metric"], 0)
        target = contrib["target"]
        metric_score = min(actual / target, 1.0) * 100 if target > 0 else 0
        metric_scores.append(metric_score)

    utility_score = sum(metric_scores) / len(metric_scores)
    return (utility_score * utility_weight) + (parse_percentile * parse_weight)


def score_consistency(scores: list[float]) -> float:
    """Average a list of per-boss scores into a consistency score."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_scoring.py -v
```

Expected: All 6 tests PASS.

**Step 6: Commit**

```bash
git add src/scoring/ tests/test_scoring.py
git commit -m "feat: scoring engine with utility + parse weighted scoring"
```

---

## Task 4: WarcraftLogs API Client — Authentication

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/warcraftlogs.py`
- Create: `tests/test_api.py`

**Background:** WarcraftLogs uses OAuth2 client credentials flow. You POST your client ID and secret to get a bearer token, then include it in all GraphQL requests. Tokens expire after 1 hour — the client handles re-auth automatically.

**Step 1: Write the failing auth test**

Create `tests/test_api.py`:

```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.warcraftlogs import WarcraftLogsClient

@pytest.mark.asyncio
async def test_get_access_token():
    client = WarcraftLogsClient(client_id="test_id", client_secret="test_secret")

    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"access_token": "abc123", "expires_in": 3600})
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
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: `ModuleNotFoundError`.

**Step 3: Create `src/api/__init__.py`**

```python
```
(empty file)

**Step 4: Create `src/api/warcraftlogs.py` with auth**

```python
import time
import aiohttp
from typing import Optional

TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
API_URL = "https://www.warcraftlogs.com/api/v2/client"


class WarcraftLogsClient:
    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    async def _fetch_token(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
            ) as resp:
                data = await resp.json()
                self._token_expiry = time.time() + data["expires_in"] - 60
                return data["access_token"]

    async def _get_token(self) -> str:
        if self._token is None or time.time() >= self._token_expiry:
            self._token = await self._fetch_token()
        return self._token

    async def query(self, graphql_query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query against the WarcraftLogs API."""
        token = await self._get_token()
        payload = {"query": graphql_query}
        if variables:
            payload["variables"] = variables

        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                return await resp.json()
```

**Step 5: Run auth tests**

```bash
pytest tests/test_api.py -v
```

Expected: Both auth tests PASS.

**Step 6: Commit**

```bash
git add src/api/ tests/test_api.py
git commit -m "feat: WarcraftLogs API client with OAuth2 authentication"
```

---

## Task 5: WarcraftLogs API Client — Guild Roster & Parse Rankings

**Files:**
- Modify: `src/api/warcraftlogs.py`
- Modify: `tests/test_api.py`

**Background:** The WarcraftLogs GraphQL API returns guild members with their character names, class IDs, and server slugs. Parse rankings return percentile scores per boss encounter, along with the player's spec at time of kill.

**Step 1: Add guild roster and rankings tests to `tests/test_api.py`**

Append to the existing file:

```python
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

    with patch.object(client, "query", return_value=mock_response_data):
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

    with patch.object(client, "query", return_value=mock_response_data):
        rankings = await client.get_character_rankings(
            "Thrallbro", "stormrage", "US", zone_id=1007
        )

    assert len(rankings) == 1
    assert rankings[0]["rankPercent"] == 87.5
    assert rankings[0]["encounter"]["name"] == "Gruul the Dragonkiller"
```

**Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_api.py::test_get_guild_roster tests/test_api.py::test_get_character_rankings -v
```

Expected: `AttributeError` — methods don't exist yet.

**Step 3: Add methods to `src/api/warcraftlogs.py`**

Append to the `WarcraftLogsClient` class:

```python
    async def get_guild_roster(self, guild_name: str, server_slug: str, region: str) -> list:
        """Fetch all members of a guild from WarcraftLogs."""
        gql = """
        query($name: String!, $serverSlug: String!, $serverRegion: String!) {
          guildData {
            guild(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
              members {
                data {
                  name
                  classID
                  server { slug region { slug } }
                }
              }
            }
          }
        }
        """
        result = await self.query(gql, {
            "name": guild_name,
            "serverSlug": server_slug,
            "serverRegion": region,
        })
        return result["data"]["guildData"]["guild"]["members"]["data"]

    async def get_character_rankings(
        self, name: str, server_slug: str, region: str, zone_id: int
    ) -> list:
        """Fetch parse percentile rankings per boss for a character."""
        gql = """
        query($name: String!, $serverSlug: String!, $serverRegion: String!, $zoneID: Int!) {
          characterData {
            character(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
              zoneRankings(zoneID: $zoneID) {
                rankings {
                  encounter { name }
                  rankPercent
                  spec
                }
              }
            }
          }
        }
        """
        result = await self.query(gql, {
            "name": name,
            "serverSlug": server_slug,
            "serverRegion": region,
            "zoneID": zone_id,
        })
        char = result["data"]["characterData"]["character"]
        if char is None:
            return []
        return char["zoneRankings"]["rankings"]
```

**Step 4: Run all API tests**

```bash
pytest tests/test_api.py -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/api/warcraftlogs.py tests/test_api.py
git commit -m "feat: guild roster and character parse rankings queries"
```

---

## Task 6: WarcraftLogs API Client — Utility/Cast Data

**Files:**
- Modify: `src/api/warcraftlogs.py`
- Modify: `tests/test_api.py`

**Background:** To get utility data (uptime % and cast counts), we query a specific report's table data filtered by player and data type. Uptime data comes from `dataType: Debuffs` or `dataType: Buffs`. Cast counts come from `dataType: Casts`. The API returns a JSON blob inside the `data` field of the table response.

**Step 1: Add utility data test**

Append to `tests/test_api.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_api.py::test_get_report_utility_data -v
```

Expected: `AttributeError` — `get_utility_data` doesn't exist.

**Step 3: Add `get_utility_data` to `src/api/warcraftlogs.py`**

Append to `WarcraftLogsClient`:

```python
    async def get_utility_data(
        self,
        report_code: str,
        source_id: int,
        start: int,
        end: int,
        contributions: list,
    ) -> dict:
        """
        Fetch utility metrics (uptime % and cast counts) for a player in a report.

        Returns a dict of metric_name -> value.
        """
        uptime_contribs = [c for c in contributions if c["type"] == "uptime"]
        count_contribs = [c for c in contributions if c["type"] == "count"]

        result = {}

        if uptime_contribs:
            uptime_data = await self._query_table(report_code, source_id, start, end, "Debuffs")
            auras = uptime_data.get("auras", [])
            total_time = uptime_data.get("totalTime", 1)
            for contrib in uptime_contribs:
                match = next((a for a in auras if a["id"] == contrib["spell_id"]), None)
                if match:
                    result[contrib["metric"]] = (match["totalUptime"] / total_time) * 100
                else:
                    result[contrib["metric"]] = 0.0

        if count_contribs:
            cast_data = await self._query_table(report_code, source_id, start, end, "Casts")
            entries = cast_data.get("entries", [])
            for contrib in count_contribs:
                match = next((e for e in entries if e["id"] == contrib["spell_id"]), None)
                result[contrib["metric"]] = match["total"] if match else 0

        return result

    async def _query_table(
        self, report_code: str, source_id: int, start: int, end: int, data_type: str
    ) -> dict:
        gql = """
        query($code: String!, $sourceID: Int, $startTime: Float!, $endTime: Float!, $dataType: TableDataType!) {
          reportData {
            report(code: $code) {
              table(sourceID: $sourceID, startTime: $startTime, endTime: $endTime, dataType: $dataType)
            }
          }
        }
        """
        result = await self.query(gql, {
            "code": report_code,
            "sourceID": source_id,
            "startTime": float(start),
            "endTime": float(end),
            "dataType": data_type,
        })
        return result["data"]["reportData"]["report"]["table"]["data"]
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/api/warcraftlogs.py tests/test_api.py
git commit -m "feat: utility data query for uptime and cast count metrics"
```

---

## Task 7: Discord Bot Foundation

**Files:**
- Create: `src/bot.py`
- Create: `src/__init__.py`

**Background:** `discord.py` 2.x uses a `commands.Bot` with an app commands tree for slash commands. The bot loads credentials from `.env`, registers all slash commands, and checks for the officer role on protected commands.

**Step 1: Create `src/__init__.py`**

```python
```
(empty file)

**Step 2: Create `src/bot.py`**

```python
import os
import discord
from discord import app_commands
from dotenv import load_dotenv
from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader

load_dotenv()

OFFICER_ROLE_NAME = os.getenv("OFFICER_ROLE_NAME", "Officer")
GUILD_NAME = os.getenv("GUILD_NAME")
GUILD_SERVER = os.getenv("GUILD_SERVER")
GUILD_REGION = os.getenv("GUILD_REGION", "US")
TBC_ZONE_ID = 1007  # The Black Temple zone — update to current tier


class GuildBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.wcl = WarcraftLogsClient(
            client_id=os.getenv("WARCRAFTLOGS_CLIENT_ID"),
            client_secret=os.getenv("WARCRAFTLOGS_CLIENT_SECRET"),
        )
        self.config = ConfigLoader("config.yaml")

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"Logged in as {self.user}")


bot = GuildBot()


def is_officer(interaction: discord.Interaction) -> bool:
    """Check if the user has the officer role."""
    role_names = [r.name for r in interaction.user.roles]
    return OFFICER_ROLE_NAME in role_names


# Import commands to register them (must come after bot is defined)
from src.commands import topconsistent, player, raidrecap, setconfig  # noqa: E402, F401


def run():
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))


if __name__ == "__main__":
    run()
```

**Step 3: Commit**

```bash
git add src/__init__.py src/bot.py
git commit -m "feat: Discord bot foundation with slash command tree and officer check"
```

---

## Task 8: /topconsistent Command

**Files:**
- Create: `src/commands/__init__.py`
- Create: `src/commands/topconsistent.py`

**What it does:** Fetches the guild roster, scores each raider's recent parses + utility across all bosses in the current zone, averages across weeks, and returns an embed ranked list.

**Step 1: Create `src/commands/__init__.py`**

```python
```
(empty file)

**Step 2: Create `src/commands/topconsistent.py`**

```python
import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_NAME, GUILD_SERVER, GUILD_REGION, TBC_ZONE_ID
from src.scoring.engine import score_player, score_consistency


@bot.tree.command(name="topconsistent", description="Rank raiders by consistency score")
@app_commands.describe(weeks="Number of recent weeks to include (default: 4)")
async def topconsistent(interaction: discord.Interaction, weeks: int = 4):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        roster = await bot.wcl.get_guild_roster(GUILD_NAME, GUILD_SERVER, GUILD_REGION)
    except Exception:
        await interaction.followup.send("Failed to fetch guild roster from WarcraftLogs.")
        return

    scores = []
    for member in roster:
        name = member["name"]
        server_slug = member["server"]["slug"]
        region = member["server"]["region"]["slug"].upper()

        try:
            rankings = await bot.wcl.get_character_rankings(name, server_slug, region, TBC_ZONE_ID)
        except Exception:
            continue

        if not rankings:
            continue

        spec = rankings[0].get("spec", "").lower()
        class_name = _class_id_to_name(member.get("classID", 0))
        spec_key = f"{class_name}:{spec}"
        profile = bot.config.get_spec(spec_key)

        boss_scores = []
        for ranking in rankings[-weeks * 8:]:  # rough approximation
            parse = ranking.get("rankPercent", 0)
            if profile:
                boss_scores.append(score_player(profile, parse, {}))
            else:
                boss_scores.append(parse)

        if boss_scores:
            scores.append((name, score_consistency(boss_scores)))

    scores.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title=f"Top Consistent Raiders (last {weeks} weeks)",
        color=discord.Color.gold(),
    )

    if not scores:
        embed.description = "No data found."
    else:
        lines = []
        for i, (name, score) in enumerate(scores[:15], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"**{i}.**")
            lines.append(f"{medal} **{name}** — {score:.1f}")
        embed.description = "\n".join(lines)

    await interaction.followup.send(embed=embed)


def _class_id_to_name(class_id: int) -> str:
    """Map WarcraftLogs class IDs to lowercase class names."""
    mapping = {
        1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue",
        5: "priest", 6: "deathknight", 7: "shaman", 8: "mage",
        9: "warlock", 11: "druid",
    }
    return mapping.get(class_id, "unknown")
```

**Step 3: Verify bot imports without error**

```bash
python -c "from src.commands.topconsistent import topconsistent; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add src/commands/
git commit -m "feat: /topconsistent command with consistency ranking"
```

---

## Task 9: /player Command

**Files:**
- Create: `src/commands/player.py`

**What it does:** Shows a breakdown of a specific player's parse percentile and utility scores per boss, plus their overall consistency score.

**Step 1: Create `src/commands/player.py`**

```python
import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_REGION, TBC_ZONE_ID
from src.scoring.engine import score_player, score_consistency
from src.commands.topconsistent import _class_id_to_name


@bot.tree.command(name="player", description="Show a player's parse and utility breakdown")
@app_commands.describe(character="Character name (e.g. Thrallbro-Stormrage)")
async def player_cmd(interaction: discord.Interaction, character: str):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    # Parse "Name-Server" or just "Name"
    if "-" in character:
        name, server_slug = character.split("-", 1)
        server_slug = server_slug.lower().replace(" ", "-")
    else:
        name = character
        server_slug = None

    try:
        rankings = await bot.wcl.get_character_rankings(
            name, server_slug or "unknown", GUILD_REGION, TBC_ZONE_ID
        )
    except Exception:
        await interaction.followup.send(
            f"Could not find **{character}** on WarcraftLogs. Check the spelling and try `Name-Server` format."
        )
        return

    if not rankings:
        await interaction.followup.send(f"No recent logs found for **{character}**.")
        return

    spec = rankings[0].get("spec", "Unknown")
    spec_key = f"unknown:{spec.lower()}"
    profile = bot.config.get_spec(spec_key)

    embed = discord.Embed(
        title=f"{name} — {spec}",
        color=discord.Color.blue(),
    )

    boss_lines = []
    boss_scores = []
    for ranking in rankings:
        boss = ranking["encounter"]["name"]
        parse = ranking.get("rankPercent", 0)
        if profile:
            score = score_player(profile, parse, {})
        else:
            score = parse
        boss_scores.append(score)
        parse_color = _parse_color(parse)
        boss_lines.append(f"{boss}: parse {parse_color} | score **{score:.1f}**")

    consistency = score_consistency(boss_scores)
    embed.description = "\n".join(boss_lines)
    embed.set_footer(text=f"Consistency Score: {consistency:.1f}/100")

    if profile is None:
        embed.description += f"\n\n⚠️ Spec `{spec_key}` not configured — utility metrics not included."

    await interaction.followup.send(embed=embed)


def _parse_color(parse: float) -> str:
    """Return a colored label for a parse percentile."""
    if parse >= 95:
        return f"**{parse:.0f}** 🟠"   # legendary
    if parse >= 75:
        return f"**{parse:.0f}** 🟣"   # epic
    if parse >= 50:
        return f"**{parse:.0f}** 🔵"   # rare
    return f"**{parse:.0f}** ⚪"        # common
```

**Step 2: Verify import**

```bash
python -c "from src.commands.player import player_cmd; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add src/commands/player.py
git commit -m "feat: /player command with per-boss parse and utility breakdown"
```

---

## Task 10: /raidrecap Command

**Files:**
- Create: `src/commands/raidrecap.py`

**What it does:** Takes a WarcraftLogs report URL, extracts the report code, fetches rankings for all players in the report, scores them, and posts a standout performer summary.

**Background:** A WarcraftLogs report URL looks like `https://www.warcraftlogs.com/reports/ABC123XYZ`. The report code is the last path segment (`ABC123XYZ`).

**Step 1: Create `src/commands/raidrecap.py`**

```python
import discord
from discord import app_commands
from src.bot import bot, is_officer
from src.scoring.engine import score_player


@bot.tree.command(name="raidrecap", description="Show standout performers from a raid log")
@app_commands.describe(log_url="WarcraftLogs report URL")
async def raidrecap(interaction: discord.Interaction, log_url: str):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    report_code = _extract_report_code(log_url)
    if not report_code:
        await interaction.followup.send(
            "Invalid URL. Use a WarcraftLogs report URL like `https://www.warcraftlogs.com/reports/ABC123`"
        )
        return

    try:
        rankings = await bot.wcl.get_report_rankings(report_code)
    except Exception as e:
        await interaction.followup.send(f"Failed to fetch report data: {e}")
        return

    if not rankings:
        await interaction.followup.send("No ranking data found in this report.")
        return

    # Score each player and find standouts (top 25%)
    scored = []
    for entry in rankings:
        name = entry.get("name", "Unknown")
        spec = entry.get("spec", "").lower()
        class_name = entry.get("class", "").lower()
        parse = entry.get("rankPercent", 0)
        spec_key = f"{class_name}:{spec}"
        profile = bot.config.get_spec(spec_key)
        score = score_player(profile, parse, {}) if profile else parse
        scored.append((name, spec, score, parse))

    scored.sort(key=lambda x: x[2], reverse=True)
    cutoff = len(scored) // 4 or 1
    standouts = scored[:cutoff]

    embed = discord.Embed(
        title="Raid Recap — Standout Performers",
        color=discord.Color.gold(),
    )

    lines = []
    for name, spec, score, parse in standouts:
        lines.append(f"**{name}** ({spec}) — Score: **{score:.1f}** | Parse: {parse:.0f}")

    embed.description = "\n".join(lines) or "No standouts found."
    embed.set_footer(text=f"Report: {report_code}")

    await interaction.followup.send(embed=embed)


def _extract_report_code(url: str) -> str | None:
    """Extract the report code from a WarcraftLogs URL."""
    url = url.rstrip("/")
    parts = url.split("/")
    if "reports" in parts:
        idx = parts.index("reports")
        if idx + 1 < len(parts):
            code = parts[idx + 1]
            if code.isalnum() and len(code) >= 8:
                return code
    return None
```

**Step 2: Add `get_report_rankings` to `src/api/warcraftlogs.py`**

Append to `WarcraftLogsClient`:

```python
    async def get_report_rankings(self, report_code: str) -> list:
        """Fetch per-player rankings for all fights in a report."""
        gql = """
        query($code: String!) {
          reportData {
            report(code: $code) {
              rankings(playerMetric: dps)
            }
          }
        }
        """
        result = await self.query(gql, {"code": report_code})
        report = result["data"]["reportData"]["report"]
        if report is None:
            return []
        rankings_data = report.get("rankings", {})
        return rankings_data.get("data", [])
```

**Step 3: Verify import**

```bash
python -c "from src.commands.raidrecap import raidrecap; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add src/commands/raidrecap.py src/api/warcraftlogs.py
git commit -m "feat: /raidrecap command and report rankings query"
```

---

## Task 11: /setconfig Command

**Files:**
- Create: `src/commands/setconfig.py`

**What it does:** Allows officers to update a metric target in config.yaml directly from Discord. Writes the change to disk immediately.

**Step 1: Create `src/commands/setconfig.py`**

```python
import discord
from discord import app_commands
from src.bot import bot, is_officer


@bot.tree.command(name="setconfig", description="Update a metric target for a class spec")
@app_commands.describe(
    spec="Class:spec key (e.g. warrior:protection)",
    metric="Metric name (e.g. sunder_armor_uptime)",
    target="New target value",
)
async def setconfig(interaction: discord.Interaction, spec: str, metric: str, target: int):
    if not is_officer(interaction):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )
        return

    try:
        old_profile = bot.config.get_spec(spec)
        if old_profile is None:
            await interaction.response.send_message(
                f"Spec `{spec}` not found in config. Available specs:\n"
                + "\n".join(f"• `{s}`" for s in bot.config.all_specs()),
                ephemeral=True,
            )
            return

        old_target = next(
            (c["target"] for c in old_profile["contributions"] if c["metric"] == metric),
            None,
        )
        if old_target is None:
            available = [c["metric"] for c in old_profile["contributions"]]
            await interaction.response.send_message(
                f"Metric `{metric}` not found in `{spec}`. Available metrics:\n"
                + "\n".join(f"• `{m}`" for m in available),
                ephemeral=True,
            )
            return

        bot.config.update_target(spec, metric, target)

        await interaction.response.send_message(
            f"✅ Updated `{spec}` › `{metric}`: **{old_target}** → **{target}**"
        )

    except Exception as e:
        await interaction.response.send_message(f"Error updating config: {e}", ephemeral=True)
```

**Step 2: Verify import**

```bash
python -c "from src.commands.setconfig import setconfig; print('OK')"
```

Expected: `OK`

**Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

**Step 4: Commit**

```bash
git add src/commands/setconfig.py
git commit -m "feat: /setconfig officer command to update metric targets"
```

---

## Task 12: Final Wiring & Smoke Test

**Files:**
- Create: `README.md`

**Step 1: Create README.md**

```markdown
# WarcraftLogs Guild Bot

A Discord bot for TBC guild officers to analyze raid performance and identify outstanding raiders for loot priority.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Get WarcraftLogs API credentials: https://www.warcraftlogs.com/api/clients/
3. Create a Discord bot: https://discord.com/developers/applications
4. Copy `.env.example` to `.env` and fill in all values
5. Edit `config.yaml` to configure your specs and utility metrics
6. Run the bot: `python -m src.bot`

## Commands (Officer only)

| Command | Description |
|---|---|
| `/topconsistent [weeks]` | Rank raiders by consistency score |
| `/player <Name-Server>` | Individual parse + utility breakdown |
| `/raidrecap <url>` | Standout performers from a log |
| `/setconfig <spec> <metric> <target>` | Update a metric target |

## Updating Config

Use `/setconfig` in Discord, or edit `config.yaml` directly and restart the bot.

## TBC Zone IDs (for `TBC_ZONE_ID` in bot.py)

- Karazhan: 1002
- Gruul's Lair: 1004
- Magtheridon's Lair: 1005
- Serpentshrine Cavern: 1006
- The Eye: 1007
- Mount Hyjal: 1008
- Black Temple: 1010
- Sunwell Plateau: 1011
```

**Step 2: Run full test suite one final time**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

**Step 3: Verify bot starts without import errors**

```bash
python -c "import src.bot; print('Bot imports OK')"
```

Expected: `Bot imports OK`

**Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions and zone IDs"
```

---

## Running the Bot

```bash
python -m src.bot
```

The bot will log `Logged in as <BotName>` when ready. Slash commands sync automatically on startup (may take up to 1 hour to appear globally in Discord).
