# Spec Profiles and Consumables Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 16 missing TBC spec profiles to config.yaml, a global consumables config section, and wire consumables data into /player and /raidrecap commands as informational display (optionally scoreable via consumables_weight).

**Architecture:** The consumables list lives once at the top level of config.yaml; each spec profile gains a `consumables_weight: 0.00` field (default = informational only). The API client gains `spell_ids` list support for multi-spell metrics and two new report query methods. The scoring engine gains a third weight dimension that is a no-op at 0.0. Both commands display a consumables section when report data is available.

**Tech Stack:** Python 3.11, discord.py 2.3.2, aiohttp 3.9.1, pyyaml 6.0.1, pytest + pytest-asyncio.

---

## Task 1: Support `spell_ids` list in API client

**Files:**
- Modify: `src/api/warcraftlogs.py`
- Test: `tests/test_api.py`

The current `get_utility_data` matches by `entry["id"] == contrib["spell_id"]` (single ID). Consumable metrics like flasks and elixirs need to match any one of several spell IDs. Add a static helper and update both the uptime and count matching paths. Backwards compatible — `spell_id` (singular) still works.

**Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

```
pytest tests/test_api.py::test_get_utility_data_with_spell_ids_list tests/test_api.py::test_get_utility_data_spell_ids_list_no_match_returns_zero -v
```
Expected: FAIL — `spell_ids` key is not handled yet.

**Step 3: Add `_contrib_matches` and update `get_utility_data`**

In `src/api/warcraftlogs.py`, add this static method to `WarcraftLogsClient`:

```python
@staticmethod
def _contrib_matches(entry: dict, contrib: dict) -> bool:
    """Return True if a WCL aura/cast entry matches the contribution's spell definition."""
    if "spell_ids" in contrib:
        return entry["id"] in contrib["spell_ids"]
    return entry["id"] == contrib.get("spell_id")
```

Then replace the two matching lines in `get_utility_data`:

```python
# Uptime section — replace:
match = next((a for a in all_auras if a["id"] == contrib["spell_id"]), None)
# With:
match = next((a for a in all_auras if self._contrib_matches(a, contrib)), None)

# Count section — replace:
match = next((e for e in entries if e["id"] == contrib["spell_id"]), None)
# With:
match = next((e for e in entries if self._contrib_matches(e, contrib)), None)
```

**Step 4: Run tests to verify they pass**

```
pytest tests/test_api.py -v
```
Expected: All 8 tests PASS (6 existing + 2 new).

**Step 5: Commit**

```bash
git add tests/test_api.py src/api/warcraftlogs.py
git commit -m "feat: support spell_ids list in API utility matching"
```

---

## Task 2: Update scoring engine for consumables_weight and optional flag

**Files:**
- Modify: `src/scoring/engine.py`
- Test: `tests/test_scoring.py`

Add two optional parameters to `score_player`: `consumables_profile` (the global list) and `consumables_data` (fetched values). When `consumables_weight > 0`, score consumables excluding `optional: true` entries. Fully backwards compatible — default args mean existing callers are unaffected.

**Step 1: Write the failing tests**

Add to `tests/test_scoring.py`:

```python
CONSUMABLES_PROFILE = [
    {"metric": "flask_uptime", "type": "uptime", "target": 100},
    {"metric": "drums_count", "type": "count", "target": 4, "optional": True},
    {"metric": "sapper_count", "type": "count", "target": 2, "optional": True},
]

PROFILE_WITH_CONSUMABLES = {
    "utility_weight": 0.50,
    "parse_weight": 0.40,
    "consumables_weight": 0.10,
    "contributions": [
        {"metric": "sunder_armor_uptime", "type": "uptime", "target": 90},
    ],
}


def test_consumables_weight_zero_ignores_consumables():
    """consumables_weight: 0.00 means consumables never affect the score."""
    profile = {**PROT_WARRIOR_PROFILE, "consumables_weight": 0.00}
    consumables_data = {"flask_uptime": 0}
    result = score_player(
        profile, 100.0, {"sunder_armor_uptime": 90, "thunderclap_count": 15},
        CONSUMABLES_PROFILE, consumables_data
    )
    # Same as no consumables: utility=100, parse=100 => 100*0.75 + 100*0.25 = 100
    assert result == pytest.approx(100.0, abs=0.1)


def test_consumables_scored_when_weight_nonzero():
    """consumables_weight > 0 adds consumables score to total."""
    consumables_data = {"flask_uptime": 100, "drums_count": 0, "sapper_count": 0}
    utility_data = {"sunder_armor_uptime": 90}
    result = score_player(
        PROFILE_WITH_CONSUMABLES, 80.0, utility_data,
        CONSUMABLES_PROFILE, consumables_data
    )
    # utility: 100*0.50=50; parse: 80*0.40=32; consumables: 100*0.10=10 => 92
    assert result == pytest.approx(92.0, abs=0.1)


def test_optional_metrics_not_included_in_consumables_score():
    """optional: true metrics are shown in display but excluded from scoring."""
    consumables_data = {"flask_uptime": 100, "drums_count": 0, "sapper_count": 0}
    utility_data = {"sunder_armor_uptime": 90}
    result = score_player(
        PROFILE_WITH_CONSUMABLES, 80.0, utility_data,
        CONSUMABLES_PROFILE, consumables_data
    )
    # drums and sapper are optional=True, so only flask_uptime (100) is scored
    # consumables_score = 100; total = 50 + 32 + 10 = 92
    assert result == pytest.approx(92.0, abs=0.1)


def test_all_consumables_optional_returns_zero_consumables_score():
    """If all consumables are optional, consumables_score is 0 even with weight."""
    all_optional = [
        {"metric": "drums_count", "type": "count", "target": 4, "optional": True},
    ]
    profile = {**PROFILE_WITH_CONSUMABLES}
    result = score_player(
        profile, 80.0, {"sunder_armor_uptime": 90},
        all_optional, {"drums_count": 4}
    )
    # consumables_score = 0 (all optional); utility=100*0.50=50; parse=80*0.40=32
    assert result == pytest.approx(82.0, abs=0.1)
```

**Step 2: Run tests to verify they fail**

```
pytest tests/test_scoring.py::test_consumables_weight_zero_ignores_consumables tests/test_scoring.py::test_consumables_scored_when_weight_nonzero tests/test_scoring.py::test_optional_metrics_not_included_in_consumables_score tests/test_scoring.py::test_all_consumables_optional_returns_zero_consumables_score -v
```
Expected: FAIL — `score_player` doesn't accept the new parameters yet.

**Step 3: Update `score_player`**

Replace the entire function in `src/scoring/engine.py`:

```python
def score_player(
    spec_profile: dict,
    parse_percentile: float,
    utility_data: dict,
    consumables_profile: list | None = None,
    consumables_data: dict | None = None,
) -> float:
    """
    Compute a single-boss performance score for a player.

    Args:
        spec_profile: The class:spec config entry (weights + contributions list)
        parse_percentile: WarcraftLogs parse rank 0-100
        utility_data: Dict of metric_name -> actual value (uptime % or cast count)
        consumables_profile: Optional global consumables list from config
        consumables_data: Optional dict of consumable metric_name -> actual value

    Returns:
        Score from 0-100
    """
    utility_weight = spec_profile.get("utility_weight", 0.0)
    parse_weight = spec_profile.get("parse_weight", 1.0)
    consumables_weight = spec_profile.get("consumables_weight", 0.0)
    contributions = spec_profile.get("contributions", [])

    if not contributions:
        return float(parse_percentile)

    metric_scores = []
    for contrib in contributions:
        actual = utility_data.get(contrib["metric"], 0)
        target = contrib["target"]
        metric_score = min(actual / target, 1.0) * 100 if target > 0 else 0
        metric_scores.append(metric_score)

    utility_score = sum(metric_scores) / len(metric_scores)

    consumables_score = 0.0
    if consumables_weight > 0 and consumables_profile and consumables_data is not None:
        scored = [c for c in consumables_profile if not c.get("optional")]
        if scored:
            c_scores = []
            for contrib in scored:
                actual = consumables_data.get(contrib["metric"], 0)
                target = contrib.get("target", 1)
                c_score = min(actual / target, 1.0) * 100 if target > 0 else 0
                c_scores.append(c_score)
            consumables_score = sum(c_scores) / len(c_scores)

    return (
        (utility_score * utility_weight)
        + (parse_percentile * parse_weight)
        + (consumables_score * consumables_weight)
    )
```

**Step 4: Run tests**

```
pytest tests/test_scoring.py -v
```
Expected: All 12 tests PASS (8 existing + 4 new).

**Step 5: Commit**

```bash
git add tests/test_scoring.py src/scoring/engine.py
git commit -m "feat: add consumables_weight and optional flag to scoring engine"
```

---

## Task 3: Add `get_consumables()` to ConfigLoader and fix `all_specs()`

**Files:**
- Modify: `src/config/loader.py`
- Test: `tests/test_config.py`

`all_specs()` currently returns all keys including the new `consumables` top-level key. Fix it to exclude non-spec keys. Add `get_consumables()` to return the global list.

**Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
SAMPLE_CONFIG_WITH_CONSUMABLES = {
    **SAMPLE_CONFIG,
    "consumables": [
        {
            "metric": "flask_uptime",
            "label": "Flask",
            "spell_ids": [17628, 28520],
            "type": "uptime",
            "subtype": "buff",
            "target": 100,
        }
    ],
}


@pytest.fixture
def config_file_with_consumables(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG_WITH_CONSUMABLES, f)
    return str(path)


def test_get_consumables_returns_list(config_file_with_consumables):
    loader = ConfigLoader(config_file_with_consumables)
    result = loader.get_consumables()
    assert len(result) == 1
    assert result[0]["metric"] == "flask_uptime"


def test_get_consumables_missing_returns_empty(config_file):
    loader = ConfigLoader(config_file)
    assert loader.get_consumables() == []


def test_all_specs_excludes_consumables_key(config_file_with_consumables):
    loader = ConfigLoader(config_file_with_consumables)
    specs = loader.all_specs()
    assert "consumables" not in specs
    assert "warrior:protection" in specs
```

**Step 2: Run tests to verify they fail**

```
pytest tests/test_config.py::test_get_consumables_returns_list tests/test_config.py::test_get_consumables_missing_returns_empty tests/test_config.py::test_all_specs_excludes_consumables_key -v
```
Expected: FAIL — `get_consumables` doesn't exist yet; `all_specs` includes `consumables` key.

**Step 3: Update `ConfigLoader`**

In `src/config/loader.py`, add `get_consumables` and update `all_specs`:

```python
def get_consumables(self) -> list:
    """Return the global consumables list, or empty list if not configured."""
    return self._data.get("consumables", [])

def all_specs(self) -> list[str]:
    """Return all configured spec keys, excluding non-spec top-level keys."""
    return [k for k in self._data.keys() if k != "consumables"]
```

**Step 4: Run tests**

```
pytest tests/test_config.py -v
```
Expected: All 9 tests PASS (6 existing + 3 new).

**Step 5: Commit**

```bash
git add tests/test_config.py src/config/loader.py
git commit -m "feat: add get_consumables() to ConfigLoader, fix all_specs() to exclude non-spec keys"
```

---

## Task 4: Add `get_report_players()` and `get_report_timerange()` to API client

**Files:**
- Modify: `src/api/warcraftlogs.py`
- Test: `tests/test_api.py`

Both `/raidrecap` and `/player` (with optional log_url) need to look up a player's `sourceID` within a report, and the report's total time range, before fetching consumables. These two methods provide that data.

**Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

```
pytest tests/test_api.py::test_get_report_players tests/test_api.py::test_get_report_timerange -v
```
Expected: FAIL — methods don't exist yet.

**Step 3: Add the two methods to `WarcraftLogsClient`**

Add to `src/api/warcraftlogs.py`:

```python
async def get_report_players(self, report_code: str) -> list:
    """Return all player actors in a report as [{id, name}]."""
    gql = """
    query($code: String!) {
      reportData {
        report(code: $code) {
          masterData {
            actors { id name type }
          }
        }
      }
    }
    """
    result = await self.query(gql, {"code": report_code})
    report = result["data"]["reportData"]["report"]
    if report is None:
        return []
    actors = report.get("masterData", {}).get("actors", [])
    return [{"id": a["id"], "name": a["name"]} for a in actors if a["type"] == "Player"]


async def get_report_timerange(self, report_code: str) -> dict:
    """Return {start, end} timestamps (relative to report start) for the full report."""
    gql = """
    query($code: String!) {
      reportData {
        report(code: $code) {
          startTime
          endTime
        }
      }
    }
    """
    result = await self.query(gql, {"code": report_code})
    report = result["data"]["reportData"]["report"]
    if report is None:
        return {"start": 0, "end": 0}
    start = int(report["startTime"])
    end = int(report["endTime"])
    return {"start": 0, "end": end - start}
```

**Step 4: Run tests**

```
pytest tests/test_api.py -v
```
Expected: All 12 tests PASS (10 existing + 2 new).

**Step 5: Commit**

```bash
git add tests/test_api.py src/api/warcraftlogs.py
git commit -m "feat: add get_report_players() and get_report_timerange() to API client"
```

---

## Task 5: Update `config.yaml` with 16 new specs and global consumables section

**Files:**
- Modify: `config.yaml`

No tests — this is data only. Spell IDs are best-effort TBC values; officers should verify against actual WCL data and use `/setconfig` to tune targets.

**Replace the contents of `config.yaml` with the following:**

```yaml
# Class:Spec profiles for scoring raiders.
# utility_weight + parse_weight + consumables_weight must equal 1.0
# consumables_weight: 0.00 = consumables shown as informational only (never scored)
# metric types: "uptime" (% of fight) or "count" (number of casts/uses)
# subtype: "buff" queries WCL Buffs table; omit for Debuffs table
# spell_id: single WCL spell ID; spell_ids: list of IDs (matches any one)
# optional: true = shown in display but never included in score

# ──────────────────────────────────────────────
# WARRIOR
# ──────────────────────────────────────────────

warrior:protection:
  utility_weight: 0.75
  parse_weight: 0.25
  consumables_weight: 0.00
  contributions:
    - metric: sunder_armor_uptime
      label: "Sunder Armor"
      spell_id: 7386
      type: uptime
      target: 90
    - metric: demoralizing_shout_uptime
      label: "Demo Shout"
      spell_id: 25203
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
  consumables_weight: 0.00
  contributions:
    - metric: battle_shout_uptime
      label: "Battle Shout"
      spell_id: 6673
      type: uptime
      subtype: buff
      target: 95
    - metric: demoralizing_shout_uptime
      label: "Demo Shout"
      spell_id: 25203
      type: uptime
      target: 75

warrior:arms:
  utility_weight: 0.30
  parse_weight: 0.70
  consumables_weight: 0.00
  contributions:
    - metric: battle_shout_uptime
      label: "Battle Shout"
      spell_id: 6673
      type: uptime
      subtype: buff
      target: 95
    - metric: demoralizing_shout_uptime
      label: "Demo Shout"
      spell_id: 25203
      type: uptime
      target: 75

# ──────────────────────────────────────────────
# PALADIN
# ──────────────────────────────────────────────

paladin:holy:
  utility_weight: 0.50
  parse_weight: 0.50
  consumables_weight: 0.00
  contributions:
    - metric: cleanse_count
      label: "Cleanse"
      spell_id: 4987
      type: count
      target: 10
    - metric: judgement_count
      label: "Judgement"
      spell_id: 20271
      type: count
      target: 15
    - metric: devotion_aura_uptime
      label: "Devotion Aura"
      spell_id: 10293
      type: uptime
      subtype: buff
      target: 90

paladin:protection:
  utility_weight: 0.70
  parse_weight: 0.30
  consumables_weight: 0.00
  contributions:
    - metric: judgement_count
      label: "Judgement"
      spell_id: 20271
      type: count
      target: 20
    - metric: blessing_of_kings_uptime
      label: "Blessing of Kings"
      spell_id: 20217
      type: uptime
      subtype: buff
      target: 90
    - metric: cleanse_count
      label: "Cleanse"
      spell_id: 4987
      type: count
      target: 8

paladin:retribution:
  utility_weight: 0.35
  parse_weight: 0.65
  consumables_weight: 0.00
  contributions:
    - metric: judgement_count
      label: "Judgement"
      spell_id: 20271
      type: count
      target: 20
    - metric: blessing_of_might_uptime
      label: "Blessing of Might"
      spell_id: 25291
      type: uptime
      subtype: buff
      target: 90

# ──────────────────────────────────────────────
# ROGUE
# ──────────────────────────────────────────────

rogue:combat:
  utility_weight: 0.55
  parse_weight: 0.45
  consumables_weight: 0.00
  contributions:
    - metric: expose_armor_uptime
      label: "Expose Armor"
      spell_id: 8647
      type: uptime
      target: 85

# ──────────────────────────────────────────────
# HUNTER
# ──────────────────────────────────────────────

hunter:beast mastery:
  utility_weight: 0.20
  parse_weight: 0.80
  consumables_weight: 0.00
  contributions:
    - metric: misdirection_count
      label: "Misdirection"
      spell_id: 34477
      type: count
      target: 5

hunter:survival:
  utility_weight: 0.35
  parse_weight: 0.65
  consumables_weight: 0.00
  contributions:
    - metric: expose_weakness_uptime
      label: "Expose Weakness"
      spell_id: 34503
      type: uptime
      target: 50
    - metric: hunters_mark_uptime
      label: "Hunter's Mark"
      spell_id: 14325
      type: uptime
      target: 90
    - metric: misdirection_count
      label: "Misdirection"
      spell_id: 34477
      type: count
      target: 5

# ──────────────────────────────────────────────
# SHAMAN
# ──────────────────────────────────────────────

shaman:restoration:
  utility_weight: 0.50
  parse_weight: 0.50
  consumables_weight: 0.00
  contributions:
    - metric: windfury_totem_uptime
      label: "Windfury Totem"
      spell_id: 25587
      type: uptime
      subtype: buff
      target: 90
    - metric: mana_spring_totem_uptime
      label: "Mana Spring Totem"
      spell_id: 25570
      type: uptime
      subtype: buff
      target: 90
    - metric: purge_count
      label: "Purge"
      spell_id: 370
      type: count
      target: 5

shaman:elemental:
  utility_weight: 0.40
  parse_weight: 0.60
  consumables_weight: 0.00
  contributions:
    - metric: totem_of_wrath_uptime
      label: "Totem of Wrath"
      spell_id: 30706
      type: uptime
      subtype: buff
      target: 90
    - metric: wrath_of_air_uptime
      label: "Wrath of Air Totem"
      spell_id: 3738
      type: uptime
      subtype: buff
      target: 90

shaman:enhancement:
  utility_weight: 0.45
  parse_weight: 0.55
  consumables_weight: 0.00
  contributions:
    - metric: windfury_totem_uptime
      label: "Windfury Totem"
      spell_id: 25587
      type: uptime
      subtype: buff
      target: 90
    - metric: grace_of_air_uptime
      label: "Grace of Air Totem"
      spell_id: 25359
      type: uptime
      subtype: buff
      target: 90
    - metric: strength_of_earth_uptime
      label: "Strength of Earth Totem"
      spell_id: 25361
      type: uptime
      subtype: buff
      target: 90

# ──────────────────────────────────────────────
# DRUID
# ──────────────────────────────────────────────

druid:feral:
  utility_weight: 0.60
  parse_weight: 0.40
  consumables_weight: 0.00
  contributions:
    - metric: faerie_fire_uptime
      label: "Faerie Fire"
      spell_id: 16857
      type: uptime
      target: 90

druid:restoration:
  utility_weight: 0.45
  parse_weight: 0.55
  consumables_weight: 0.00
  contributions:
    - metric: innervate_count
      label: "Innervate"
      spell_id: 29166
      type: count
      target: 2
    - metric: remove_curse_count
      label: "Remove Curse"
      spell_id: 2782
      type: count
      target: 5
    - metric: abolish_poison_count
      label: "Abolish Poison"
      spell_id: 2893
      type: count
      target: 5

druid:balance:
  utility_weight: 0.30
  parse_weight: 0.70
  consumables_weight: 0.00
  contributions:
    - metric: faerie_fire_uptime
      label: "Faerie Fire"
      spell_id: 770
      type: uptime
      target: 85
    - metric: innervate_count
      label: "Innervate"
      spell_id: 29166
      type: count
      target: 2
    - metric: remove_curse_count
      label: "Remove Curse"
      spell_id: 2782
      type: count
      target: 5

# ──────────────────────────────────────────────
# MAGE
# ──────────────────────────────────────────────

mage:arcane:
  utility_weight: 0.20
  parse_weight: 0.80
  consumables_weight: 0.00
  contributions:
    - metric: decurse_count
      label: "Remove Curse"
      spell_id: 475
      type: count
      target: 5

mage:fire:
  utility_weight: 0.25
  parse_weight: 0.75
  consumables_weight: 0.00
  contributions:
    - metric: decurse_count
      label: "Remove Curse"
      spell_id: 475
      type: count
      target: 5
    - metric: fire_vulnerability_uptime
      label: "Fire Vulnerability (Imp. Scorch)"
      spell_id: 22959
      type: uptime
      target: 80

# ──────────────────────────────────────────────
# WARLOCK
# ──────────────────────────────────────────────

warlock:affliction:
  utility_weight: 0.45
  parse_weight: 0.55
  consumables_weight: 0.00
  contributions:
    - metric: curse_of_elements_uptime
      label: "Curse of Elements"
      spell_id: 27228
      type: uptime
      target: 90

warlock:destruction:
  utility_weight: 0.30
  parse_weight: 0.70
  consumables_weight: 0.00
  contributions:
    - metric: curse_of_elements_uptime
      label: "Curse of Elements"
      spell_id: 27228
      type: uptime
      target: 90

# ──────────────────────────────────────────────
# PRIEST
# ──────────────────────────────────────────────

priest:holy:
  utility_weight: 0.45
  parse_weight: 0.55
  consumables_weight: 0.00
  contributions:
    - metric: dispel_magic_count
      label: "Dispel Magic"
      spell_id: 527
      type: count
      target: 10
    - metric: fortitude_uptime
      label: "Power Word: Fortitude"
      spell_id: 25392
      type: uptime
      subtype: buff
      target: 95
    - metric: abolish_disease_count
      label: "Abolish Disease"
      spell_id: 552
      type: count
      target: 5

priest:discipline:
  utility_weight: 0.40
  parse_weight: 0.60
  consumables_weight: 0.00
  contributions:
    - metric: dispel_magic_count
      label: "Dispel Magic"
      spell_id: 527
      type: count
      target: 10
    - metric: fortitude_uptime
      label: "Power Word: Fortitude"
      spell_id: 25392
      type: uptime
      subtype: buff
      target: 95
    - metric: abolish_disease_count
      label: "Abolish Disease"
      spell_id: 552
      type: count
      target: 5

priest:shadow:
  utility_weight: 0.35
  parse_weight: 0.65
  consumables_weight: 0.00
  contributions:
    - metric: shadow_weaving_uptime
      label: "Shadow Weaving"
      spell_id: 15258
      type: uptime
      target: 85
    - metric: misery_uptime
      label: "Misery"
      spell_id: 33198
      type: uptime
      target: 85
    - metric: vampiric_embrace_uptime
      label: "Vampiric Embrace"
      spell_id: 15286
      type: uptime
      subtype: buff
      target: 90

# ──────────────────────────────────────────────
# GLOBAL CONSUMABLES
# All specs have consumables_weight: 0.00 by default (informational only).
# To score consumables for a spec, raise consumables_weight and lower parse_weight
# by the same amount so all three weights still sum to 1.0.
# optional: true = shown in display but NEVER included in the score
# (used for profession-gated items or situational consumables)
# ──────────────────────────────────────────────

consumables:
  - metric: flask_uptime
    label: "Flask"
    spell_ids: [17628, 17627, 28518, 28520, 28521]
    type: uptime
    subtype: buff
    target: 100

  - metric: battle_elixir_uptime
    label: "Battle Elixir"
    spell_ids: [28490, 28491, 28493, 28494, 28497, 17538, 17539, 28543]
    type: uptime
    subtype: buff
    target: 100

  - metric: guardian_elixir_uptime
    label: "Guardian Elixir"
    spell_ids: [39625, 39627, 39628, 28502, 28503]
    type: uptime
    subtype: buff
    target: 100

  - metric: haste_potion_count
    label: "Haste Potion"
    spell_id: 28507
    type: count
    target: 2

  - metric: destruction_potion_count
    label: "Destruction Potion"
    spell_id: 28508
    type: count
    target: 2

  - metric: mana_potion_count
    label: "Mana Potion"
    spell_id: 28499
    type: count
    target: 2

  - metric: dark_rune_count
    label: "Dark Rune"
    spell_id: 27869
    type: count
    target: 2
    optional: true

  - metric: demonic_rune_count
    label: "Demonic Rune"
    spell_id: 12662
    type: count
    target: 2
    optional: true

  - metric: drums_count
    label: "Drums"
    spell_ids: [35476, 35475, 35478, 35477]
    type: count
    target: 4
    optional: true

  - metric: sapper_count
    label: "Goblin Sapper"
    spell_id: 13241
    type: count
    target: 2
    optional: true

  - metric: grenade_count
    label: "Grenade / Bomb"
    spell_ids: [30216, 30217, 19769]
    type: count
    target: 3
    optional: true
```

**Step 1: Replace config.yaml with the above content.**

**Step 2: Verify the file loads without YAML errors**

```
python -c "import yaml; d=yaml.safe_load(open('config.yaml')); print(len(d), 'top-level keys')"
```
Expected output: `23 top-level keys` (22 specs + consumables).

**Step 3: Run existing test suite to confirm nothing broken**

```
pytest -v
```
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add config.yaml
git commit -m "feat: add 16 spec profiles and global consumables section to config.yaml"
```

---

## Task 6: Update `/raidrecap` to display consumables

**Files:**
- Modify: `src/commands/raidrecap.py`

After scoring standout performers, fetch the report's players and time range, then fetch consumables for each standout player. Display a "Consumables" field in the embed showing each player's usage.

**Step 1: Update `raidrecap.py`**

Replace the full file content:

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

    scored = []
    for entry in rankings:
        name = entry.get("name", "Unknown")
        spec = entry.get("spec", "").lower()
        class_name = entry.get("class", "").lower()
        parse = entry.get("rankPercent", 0)
        spec_key = f"{class_name}:{spec}"
        profile = bot.config.get_spec(spec_key)
        _fallback = {"utility_weight": 0.0, "parse_weight": 1.0, "contributions": []}
        score = score_player(profile or _fallback, parse, {})
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

    # Fetch and display consumables for each standout player
    consumables_profile = bot.config.get_consumables()
    if consumables_profile:
        try:
            report_players = await bot.wcl.get_report_players(report_code)
            timerange = await bot.wcl.get_report_timerange(report_code)
            player_id_map = {p["name"]: p["id"] for p in report_players}

            consumables_lines = []
            for name, spec, score, parse in standouts:
                source_id = player_id_map.get(name)
                if source_id is None:
                    continue
                c_data = await bot.wcl.get_utility_data(
                    report_code, source_id,
                    timerange["start"], timerange["end"],
                    consumables_profile,
                )
                c_parts = _format_consumables(c_data, consumables_profile)
                if c_parts:
                    consumables_lines.append(f"**{name}:** {', '.join(c_parts)}")

            if consumables_lines:
                embed.add_field(
                    name="Consumables",
                    value="\n".join(consumables_lines),
                    inline=False,
                )
        except Exception:
            pass  # Consumables are informational — don't fail the whole command

    embed.set_footer(text=f"Report: {report_code}")
    await interaction.followup.send(embed=embed)


def _format_consumables(c_data: dict, consumables_profile: list) -> list[str]:
    """Return a list of non-zero consumable usage strings for display."""
    parts = []
    for contrib in consumables_profile:
        val = c_data.get(contrib["metric"], 0)
        if val and val > 0:
            label = contrib["label"]
            if contrib["type"] == "uptime":
                parts.append(f"{label} {val:.0f}%")
            else:
                parts.append(f"{label} ×{int(val)}")
    return parts


def _extract_report_code(url: str) -> str | None:
    """Extract the report code from a WarcraftLogs URL."""
    url = url.rstrip("/")
    parts = url.split("/")
    if "reports" in parts:
        idx = parts.index("reports")
        if idx + 1 < len(parts):
            code = parts[idx + 1].split("#")[0].split("?")[0]
            if code.isalnum() and len(code) >= 8:
                return code
    return None
```

**Step 2: Run the full test suite**

```
pytest -v
```
Expected: All tests PASS (command logic is not unit tested — manual verification during bot run).

**Step 3: Commit**

```bash
git add src/commands/raidrecap.py
git commit -m "feat: display consumables section in /raidrecap for standout players"
```

---

## Task 7: Update `/player` to display consumables with optional log_url

**Files:**
- Modify: `src/commands/player.py`

Add an optional `log_url` parameter. When provided, the command fetches consumables for that player from the specified report and appends a consumables section to the embed.

**Step 1: Update `player.py`**

Replace the full file content:

```python
import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_REGION, TBC_ZONE_ID
from src.scoring.engine import score_player, score_consistency
from src.commands.topconsistent import _class_id_to_name


@bot.tree.command(name="player", description="Show a player's parse and utility breakdown")
@app_commands.describe(
    character="Character name (e.g. Thrallbro-Stormrage)",
    log_url="(Optional) WarcraftLogs report URL to include consumable usage",
)
async def player_cmd(interaction: discord.Interaction, character: str, log_url: str = None):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

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
    class_name = rankings[0].get("class", "").lower()
    spec_key = f"{class_name}:{spec.lower()}"
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
        _fallback = {"utility_weight": 0.0, "parse_weight": 1.0, "contributions": []}
        active_profile = profile or _fallback
        score = score_player(active_profile, parse, {})
        boss_scores.append(score)
        parse_label = _parse_color(parse)
        boss_lines.append(f"{boss}: parse {parse_label} | score **{score:.1f}**")

    consistency = score_consistency(boss_scores)
    embed.description = "\n".join(boss_lines)
    embed.set_footer(text=f"Consistency Score: {consistency:.1f}/100")

    if profile is None:
        embed.description += f"\n\n⚠️ Spec `{spec_key}` not configured — utility metrics not included."

    # Fetch consumables if a log URL was provided
    if log_url:
        from src.commands.raidrecap import _extract_report_code, _format_consumables
        report_code = _extract_report_code(log_url)
        consumables_profile = bot.config.get_consumables()
        if report_code and consumables_profile:
            try:
                report_players = await bot.wcl.get_report_players(report_code)
                timerange = await bot.wcl.get_report_timerange(report_code)
                player_id_map = {p["name"]: p["id"] for p in report_players}
                source_id = player_id_map.get(name)
                if source_id is not None:
                    c_data = await bot.wcl.get_utility_data(
                        report_code, source_id,
                        timerange["start"], timerange["end"],
                        consumables_profile,
                    )
                    c_parts = _format_consumables(c_data, consumables_profile)
                    embed.add_field(
                        name="Consumables",
                        value=", ".join(c_parts) if c_parts else "None detected",
                        inline=False,
                    )
                else:
                    embed.add_field(name="Consumables", value="Player not found in that report.", inline=False)
            except Exception:
                embed.add_field(name="Consumables", value="Could not fetch consumable data.", inline=False)
        elif report_code is None:
            embed.add_field(name="Consumables", value="Invalid log URL provided.", inline=False)

    await interaction.followup.send(embed=embed)


def _parse_color(parse: float) -> str:
    """Return a colored label for a parse percentile."""
    if parse >= 95:
        return f"**{parse:.0f}** 🟠"
    if parse >= 75:
        return f"**{parse:.0f}** 🟣"
    if parse >= 50:
        return f"**{parse:.0f}** 🔵"
    return f"**{parse:.0f}** ⚪"
```

**Step 2: Run the full test suite**

```
pytest -v
```
Expected: All tests PASS.

**Step 3: Commit**

```bash
git add src/commands/player.py
git commit -m "feat: add optional log_url to /player command for consumables display"
```

---

## Task 8: Final verification

**Step 1: Run full test suite**

```
pytest -v
```
Expected: All tests PASS. Count should be 24 total (6 API + 4 scoring + 6 config + 2 new API + 4 new scoring + 3 new config = 25, minus the original 20 = +5 new net, so 25 total).

**Step 2: Verify config loads cleanly**

```
python -c "
from src.config.loader import ConfigLoader
c = ConfigLoader('config.yaml')
print('Specs:', len(c.all_specs()))
print('Consumables:', len(c.get_consumables()))
print('consumables key excluded from specs:', 'consumables' not in c.all_specs())
"
```
Expected:
```
Specs: 22
Consumables: 11
consumables key excluded from specs: True
```

**Step 3: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: final cleanup after spec profiles and consumables feature"
```
