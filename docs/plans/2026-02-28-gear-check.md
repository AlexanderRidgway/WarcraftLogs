# Gear Check Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add gear readiness validation from WarcraftLogs report data — flag green items, missing enchants, empty gems, and low average ilvl. Standalone `/gearcheck` command plus a condensed summary in `/raidrecap`.

**Architecture:** A new `get_report_gear()` method on `WarcraftLogsClient` queries the Summary table to get gear snapshots. A `src/gear/checker.py` module contains pure checking logic. A `gearcheck.py` command module provides the `/gearcheck` command. The existing `/raidrecap` command gets a gear summary field. All thresholds are configurable via a `gear_check` section in `config.yaml`.

**Tech Stack:** Python 3.11, discord.py 2.3.2, aiohttp 3.9.1, pyyaml 6.0.1, pytest + pytest-asyncio.

---

## Task 1: Add `get_gear_check()` to ConfigLoader

**Files:**
- Modify: `src/config/loader.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
SAMPLE_CONFIG_WITH_GEAR_CHECK = {
    **SAMPLE_CONFIG,
    "gear_check": {
        "min_avg_ilvl": 100,
        "min_quality": 3,
        "check_enchants": True,
        "check_gems": True,
        "enchant_slots": [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15],
    },
}


@pytest.fixture
def config_file_with_gear_check(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG_WITH_GEAR_CHECK, f)
    return str(path)


def test_get_gear_check_returns_config(config_file_with_gear_check):
    loader = ConfigLoader(config_file_with_gear_check)
    result = loader.get_gear_check()
    assert result["min_avg_ilvl"] == 100
    assert result["min_quality"] == 3
    assert result["check_enchants"] is True
    assert result["check_gems"] is True
    assert 0 in result["enchant_slots"]


def test_get_gear_check_missing_returns_defaults(config_file):
    loader = ConfigLoader(config_file)
    result = loader.get_gear_check()
    assert result["min_avg_ilvl"] == 100
    assert result["min_quality"] == 3
    assert result["check_enchants"] is True
    assert result["check_gems"] is True
    assert isinstance(result["enchant_slots"], list)


def test_all_specs_excludes_gear_check_key(config_file_with_gear_check):
    loader = ConfigLoader(config_file_with_gear_check)
    specs = loader.all_specs()
    assert "gear_check" not in specs
    assert "warrior:protection" in specs
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py::test_get_gear_check_returns_config tests/test_config.py::test_get_gear_check_missing_returns_defaults tests/test_config.py::test_all_specs_excludes_gear_check_key -v`
Expected: FAIL — `get_gear_check` method does not exist.

**Step 3: Write minimal implementation**

In `src/config/loader.py`, add:

```python
_GEAR_CHECK_DEFAULTS = {
    "min_avg_ilvl": 100,
    "min_quality": 3,
    "check_enchants": True,
    "check_gems": True,
    "enchant_slots": [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15],
}


def get_gear_check(self) -> dict:
    """Return the gear check config, or defaults if not configured."""
    config = self._data.get("gear_check")
    if config is None:
        return dict(_GEAR_CHECK_DEFAULTS)
    return {**_GEAR_CHECK_DEFAULTS, **config}
```

Add the `_GEAR_CHECK_DEFAULTS` dict at the module level (outside the class), and `get_gear_check` as a method on `ConfigLoader`.

Update `all_specs` to also exclude `gear_check`:

```python
def all_specs(self) -> list[str]:
    """Return all configured spec keys, excluding non-spec top-level keys."""
    return [k for k in self._data.keys() if k not in ("consumables", "attendance", "gear_check")]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All config tests pass.

**Step 5: Commit**

```bash
git add src/config/loader.py tests/test_config.py
git commit -m "feat: add get_gear_check() to ConfigLoader"
```

---

## Task 2: Add `get_report_gear()` to API client

**Files:**
- Modify: `src/api/warcraftlogs.py`
- Test: `tests/test_api.py`

**Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_get_report_gear():
    """Returns list of players with their gear arrays from a report summary."""
    client = WarcraftLogsClient(client_id="id", client_secret="secret")
    client._token = "mock_token"
    client._token_expiry = float("inf")

    mock_table_data = {
        "playerDetails": [
            {
                "name": "Thrallbro",
                "id": 5,
                "gear": [
                    {"id": 28785, "slot": 0, "quality": 4, "itemLevel": 125, "permanentEnchant": 3003, "gems": [{"id": 24027}]},
                    {"id": 27803, "slot": 4, "quality": 3, "itemLevel": 112, "permanentEnchant": 2661, "gems": []},
                ],
            },
            {
                "name": "Healbot",
                "id": 7,
                "gear": [
                    {"id": 12345, "slot": 0, "quality": 2, "itemLevel": 87, "gems": []},
                ],
            },
        ]
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
        return {"playerDetails": []}

    client._query_table = mock_query_table
    result = await client.get_report_gear("abc123")

    assert result == []
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py::test_get_report_gear tests/test_api.py::test_get_report_gear_empty -v`
Expected: FAIL — `get_report_gear` does not exist.

**Step 3: Write minimal implementation**

Add to `src/api/warcraftlogs.py`:

```python
async def get_report_gear(self, report_code: str) -> list:
    """Fetch gear snapshots for all players in a report from the Summary table."""
    table_data = await self._query_table(report_code, None, 0, 999999999999, "Summary")
    player_details = table_data.get("playerDetails", [])
    return [
        {
            "name": p["name"],
            "gear": p.get("gear", []),
        }
        for p in player_details
    ]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -v`
Expected: All API tests pass.

**Step 5: Commit**

```bash
git add src/api/warcraftlogs.py tests/test_api.py
git commit -m "feat: add get_report_gear() to WarcraftLogsClient"
```

---

## Task 3: Add gear checking logic

**Files:**
- Create: `src/gear/__init__.py`
- Create: `src/gear/checker.py`
- Create: `tests/test_gear.py`

**Step 1: Write the failing tests**

Create `tests/test_gear.py`:

```python
import pytest
from src.gear.checker import check_player_gear, check_raid_gear, SLOT_NAMES

DEFAULT_CONFIG = {
    "min_avg_ilvl": 100,
    "min_quality": 3,
    "check_enchants": True,
    "check_gems": True,
    "enchant_slots": [0, 4, 5, 6, 7, 8, 9, 14, 15],
}


def _item(slot, quality=4, ilvl=120, enchant=3003, gems=None):
    """Helper to build a gear item dict."""
    item = {"id": 28000 + slot, "slot": slot, "quality": quality, "itemLevel": ilvl}
    if enchant is not None:
        item["permanentEnchant"] = enchant
    if gems is not None:
        item["gems"] = gems
    else:
        item["gems"] = []
    return item


def test_clean_gear_no_issues():
    gear = [_item(s) for s in [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    assert result["ilvl_ok"] is True
    assert result["issues"] == []
    assert result["avg_ilvl"] == 120.0


def test_green_item_flagged():
    gear = [_item(4, quality=2, ilvl=87)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    issues = [i for i in result["issues"] if "quality" in i["problem"].lower()]
    assert len(issues) == 1
    assert "Chest" in issues[0]["slot"]


def test_missing_enchant_flagged():
    gear = [_item(4, enchant=None)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    issues = [i for i in result["issues"] if "enchant" in i["problem"].lower()]
    assert len(issues) == 1


def test_non_enchantable_slot_not_flagged():
    # Slot 12 (trinket) is not in enchant_slots — should not be flagged
    gear = [_item(12, enchant=None)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    enchant_issues = [i for i in result["issues"] if "enchant" in i["problem"].lower()]
    assert len(enchant_issues) == 0


def test_empty_gem_socket_flagged():
    gear = [_item(0, gems=[{"id": 24027}, {"id": 0}])]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    issues = [i for i in result["issues"] if "gem" in i["problem"].lower()]
    assert len(issues) == 1


def test_no_gems_field_not_flagged():
    # Item without gem sockets — should not be flagged
    gear = [_item(0, gems=[])]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    gem_issues = [i for i in result["issues"] if "gem" in i["problem"].lower()]
    assert len(gem_issues) == 0


def test_low_avg_ilvl_flagged():
    gear = [_item(s, ilvl=90) for s in [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    assert result["ilvl_ok"] is False
    assert result["avg_ilvl"] == 90.0


def test_shirt_tabard_excluded():
    # Shirt (slot 3) and tabard (slot 18) should be excluded from all checks
    gear = [_item(3, quality=2, ilvl=1, enchant=None), _item(18, quality=2, ilvl=1, enchant=None)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    assert result["issues"] == []


def test_check_raid_gear_returns_only_issues():
    players = [
        {"name": "Thrallbro", "gear": [_item(4, quality=2, ilvl=87)]},
        {"name": "Cleanplayer", "gear": [_item(s) for s in [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]]},
        {"name": "Leetmage", "gear": [_item(7, enchant=None)]},
    ]
    result = check_raid_gear(players, DEFAULT_CONFIG)
    names = [r["name"] for r in result]
    assert "Thrallbro" in names
    assert "Leetmage" in names
    assert "Cleanplayer" not in names


def test_check_enchants_disabled():
    config = {**DEFAULT_CONFIG, "check_enchants": False}
    gear = [_item(4, enchant=None)]
    result = check_player_gear(gear, config)
    enchant_issues = [i for i in result["issues"] if "enchant" in i["problem"].lower()]
    assert len(enchant_issues) == 0


def test_check_gems_disabled():
    config = {**DEFAULT_CONFIG, "check_gems": False}
    gear = [_item(0, gems=[{"id": 0}])]
    result = check_player_gear(gear, config)
    gem_issues = [i for i in result["issues"] if "gem" in i["problem"].lower()]
    assert len(gem_issues) == 0
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_gear.py -v`
Expected: FAIL — module `src.gear.checker` does not exist.

**Step 3: Write minimal implementation**

Create `src/gear/__init__.py` (empty file).

Create `src/gear/checker.py`:

```python
SLOT_NAMES = {
    0: "Head", 1: "Neck", 2: "Shoulder", 3: "Shirt", 4: "Chest",
    5: "Waist", 6: "Legs", 7: "Feet", 8: "Wrist", 9: "Hands",
    10: "Ring 1", 11: "Ring 2", 12: "Trinket 1", 13: "Trinket 2",
    14: "Cloak", 15: "Main Hand", 16: "Off Hand", 17: "Ranged",
    18: "Tabard",
}

EXCLUDED_SLOTS = {3, 18}  # Shirt, Tabard — cosmetic only


def check_player_gear(gear_items: list, gear_config: dict) -> dict:
    """
    Check a player's gear against config thresholds.

    Returns:
        dict with avg_ilvl, ilvl_ok, and issues list.
    """
    min_quality = gear_config.get("min_quality", 3)
    check_enchants = gear_config.get("check_enchants", True)
    check_gems = gear_config.get("check_gems", True)
    enchant_slots = set(gear_config.get("enchant_slots", []))
    min_avg_ilvl = gear_config.get("min_avg_ilvl", 100)

    issues = []
    ilvl_sum = 0
    ilvl_count = 0

    for item in gear_items:
        slot = item.get("slot")
        if slot in EXCLUDED_SLOTS:
            continue

        slot_name = SLOT_NAMES.get(slot, f"Slot {slot}")
        item_level = item.get("itemLevel", 0)
        quality = item.get("quality", 0)

        ilvl_sum += item_level
        ilvl_count += 1

        # Check quality
        if quality < min_quality:
            quality_names = {0: "Poor", 1: "Common", 2: "Uncommon (Green)", 3: "Rare (Blue)", 4: "Epic", 5: "Legendary"}
            q_name = quality_names.get(quality, f"quality {quality}")
            issues.append({"slot": slot_name, "problem": f"{q_name} quality item (ilvl {item_level})"})

        # Check enchants
        if check_enchants and slot in enchant_slots:
            if "permanentEnchant" not in item or not item["permanentEnchant"]:
                issues.append({"slot": slot_name, "problem": "Missing enchant"})

        # Check gems
        if check_gems:
            gems = item.get("gems", [])
            empty_gems = sum(1 for g in gems if g.get("id", 0) == 0)
            if empty_gems > 0:
                issues.append({"slot": slot_name, "problem": f"Empty gem socket ({empty_gems})"})

    avg_ilvl = (ilvl_sum / ilvl_count) if ilvl_count > 0 else 0
    ilvl_ok = avg_ilvl >= min_avg_ilvl

    return {
        "avg_ilvl": round(avg_ilvl, 1),
        "ilvl_ok": ilvl_ok,
        "issues": issues,
    }


def check_raid_gear(players_gear: list, gear_config: dict) -> list:
    """
    Check gear for all players. Returns only players with issues.

    Each entry: {name, avg_ilvl, ilvl_ok, issues}
    """
    results = []
    for player in players_gear:
        result = check_player_gear(player["gear"], gear_config)
        if result["issues"] or not result["ilvl_ok"]:
            results.append({
                "name": player["name"],
                **result,
            })
    return results
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_gear.py -v`
Expected: All 12 gear tests pass.

**Step 5: Commit**

```bash
git add src/gear/__init__.py src/gear/checker.py tests/test_gear.py
git commit -m "feat: add gear checking logic with quality, enchant, and gem validation"
```

---

## Task 4: Add gear_check config to config.yaml

**Files:**
- Modify: `config.yaml`

**Step 1: Add the gear_check section**

Append to the end of `config.yaml` (after the attendance section):

```yaml
# ──────────────────────────────────────────────
# GEAR CHECK
# Flag raiders with subpar gear in reports.
# min_avg_ilvl: average item level floor
# min_quality: minimum acceptable quality (2=green, 3=blue, 4=epic)
# check_enchants/check_gems: toggle enchant/gem validation
# enchant_slots: WoW slot IDs that should be enchanted
# ──────────────────────────────────────────────

gear_check:
  min_avg_ilvl: 100
  min_quality: 3
  check_enchants: true
  check_gems: true
  enchant_slots: [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]
```

**Step 2: Run all tests**

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add config.yaml
git commit -m "feat: add gear_check config to config.yaml"
```

---

## Task 5: Add `/gearcheck` command

**Files:**
- Create: `src/commands/gearcheck.py`
- Modify: `src/bot.py` (add to `_COMMAND_MODULES`)

**Step 1: Create the command module**

Create `src/commands/gearcheck.py`:

```python
import discord
from discord import app_commands
from src.bot import bot
from src.commands.raidrecap import _extract_report_code
from src.gear.checker import check_raid_gear


@bot.tree.command(name="gearcheck", description="Check gear readiness from a raid log")
@app_commands.describe(log_url="WarcraftLogs report URL")
async def gearcheck_cmd(interaction: discord.Interaction, log_url: str):
    await interaction.response.defer()

    report_code = _extract_report_code(log_url)
    if not report_code:
        await interaction.followup.send(
            "Invalid URL. Use a WarcraftLogs report URL like `https://www.warcraftlogs.com/reports/ABC123`"
        )
        return

    gear_config = bot.config.get_gear_check()

    try:
        players_gear = await bot.wcl.get_report_gear(report_code)
    except Exception:
        await interaction.followup.send("Could not fetch gear data from this report.")
        return

    if not players_gear:
        await interaction.followup.send("No player gear data found in this report.")
        return

    flagged = check_raid_gear(players_gear, gear_config)
    total_players = len(players_gear)
    clean_count = total_players - len(flagged)

    embed = discord.Embed(
        title=f"Gear Check — Report {report_code}",
        color=discord.Color.red() if flagged else discord.Color.green(),
    )

    if flagged:
        lines = []
        for player in flagged:
            ilvl_note = f" — below {gear_config['min_avg_ilvl']} minimum" if not player["ilvl_ok"] else ""
            header = f"\u26a0\ufe0f **{player['name']}** (avg ilvl {player['avg_ilvl']:.0f}{ilvl_note})"
            issue_lines = [f"  \u2022 {i['slot']}: {i['problem']}" for i in player["issues"][:10]]
            if len(player["issues"]) > 10:
                issue_lines.append(f"  \u2022 +{len(player['issues']) - 10} more issues")
            lines.append(header + "\n" + "\n".join(issue_lines))

        embed.description = "\n\n".join(lines)
    else:
        embed.description = "\u2705 All players passed gear checks!"

    if clean_count > 0 and flagged:
        embed.set_footer(text=f"\u2705 {clean_count} player(s) passed all gear checks")

    await interaction.followup.send(embed=embed)
```

**Step 2: Register the module in bot.py**

In `src/bot.py`, add `"gearcheck"` to the `_COMMAND_MODULES` list:

```python
_COMMAND_MODULES = ["topconsistent", "player", "raidrecap", "setconfig", "attendance", "setattendance", "gearcheck"]
```

**Step 3: Run all tests**

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/commands/gearcheck.py src/bot.py
git commit -m "feat: add /gearcheck command for raid gear validation"
```

---

## Task 6: Add gear summary to `/raidrecap`

**Files:**
- Modify: `src/commands/raidrecap.py`

**Step 1: Add gear summary to raidrecap**

In `src/commands/raidrecap.py`, after the consumables section (around line 91, after `embed.set_footer`), add a gear check block:

```python
    # Fetch and display gear issues
    gear_config = bot.config.get_gear_check()
    try:
        players_gear = await bot.wcl.get_report_gear(report_code)
        if players_gear:
            from src.gear.checker import check_raid_gear
            flagged = check_raid_gear(players_gear, gear_config)
            if flagged:
                gear_parts = []
                for player in flagged:
                    issue_count = len(player["issues"])
                    ilvl_note = f", avg ilvl {player['avg_ilvl']:.0f}" if not player["ilvl_ok"] else ""
                    gear_parts.append(f"**{player['name']}** ({issue_count} issue{'s' if issue_count != 1 else ''}{ilvl_note})")
                embed.add_field(
                    name="Gear Issues",
                    value=", ".join(gear_parts),
                    inline=False,
                )
    except Exception:
        pass  # Gear check is informational — don't fail the whole command
```

This block should be added BEFORE the `embed.set_footer` line in the `raidrecap` function. The import is done at call time to avoid circular imports (matching the existing pattern used for consumables in `player.py`).

**Step 2: Run all tests**

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add src/commands/raidrecap.py
git commit -m "feat: add gear summary to /raidrecap command"
```

---

## Task 7: Update CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update CLAUDE.md**

Add to the project structure section:
- `src/gear/checker.py` — gear quality, enchant, and gem validation logic
- `src/commands/gearcheck.py` — `/gearcheck` command

Add to the Discord Commands table:
- `/gearcheck <log_url>` | All | Check gear readiness from a raid report

Add to the config.yaml Format section: document the `gear_check:` key.

Update test count to reflect new tests.

Add a Known Design Decision about gear data being per-report (not live armory).

**Step 2: Update README.md**

Add command documentation for `/gearcheck`.
Add a "Gear Check" section explaining how it works and how to configure thresholds.

**Step 3: Run all tests one final time**

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add gear check to CLAUDE.md and README"
```
