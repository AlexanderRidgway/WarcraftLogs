# Attendance Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add weekly raid attendance tracking with per-player and guild-wide Discord commands, configurable raid requirements in config.yaml, and a `/setattendance` command for officers.

**Architecture:** A new `get_guild_reports()` method on `WarcraftLogsClient` queries `reportData.reports` filtered by guild and time range, returning reports with zone and player data. An `attendance.py` module in `src/commands/` provides `/attendance` and `/attendancereport` commands. A separate `setattendance.py` handles config changes. `ConfigLoader` gains `get_attendance()` and attendance mutation methods. Reports are grouped by ISO week (Mon–Sun) and compared against configurable per-zone weekly requirements.

**Tech Stack:** Python 3.11, discord.py 2.3.2, aiohttp 3.9.1, pyyaml 6.0.1, pytest + pytest-asyncio.

---

## Task 1: Add `get_attendance()` to ConfigLoader

**Files:**
- Modify: `src/config/loader.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
SAMPLE_CONFIG_WITH_ATTENDANCE = {
    **SAMPLE_CONFIG,
    "attendance": [
        {"zone_id": 1002, "label": "Karazhan", "required_per_week": 1},
        {"zone_id": 1004, "label": "Gruul's Lair", "required_per_week": 1},
    ],
}


@pytest.fixture
def config_file_with_attendance(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG_WITH_ATTENDANCE, f)
    return str(path)


def test_get_attendance_returns_list(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    result = loader.get_attendance()
    assert len(result) == 2
    assert result[0]["zone_id"] == 1002
    assert result[0]["label"] == "Karazhan"
    assert result[0]["required_per_week"] == 1


def test_get_attendance_missing_returns_empty(config_file):
    loader = ConfigLoader(config_file)
    assert loader.get_attendance() == []


def test_all_specs_excludes_attendance_key(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    specs = loader.all_specs()
    assert "attendance" not in specs
    assert "warrior:protection" in specs
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_get_attendance_returns_list tests/test_config.py::test_get_attendance_missing_returns_empty tests/test_config.py::test_all_specs_excludes_attendance_key -v`
Expected: FAIL — `ConfigLoader` has no `get_attendance` method, and `all_specs` does not exclude `attendance`.

**Step 3: Write minimal implementation**

In `src/config/loader.py`, add a `get_attendance` method:

```python
def get_attendance(self) -> list:
    """Return the attendance requirements list, or empty list if not configured."""
    return self._data.get("attendance", [])
```

Update `all_specs` to also exclude the `attendance` key:

```python
def all_specs(self) -> list[str]:
    """Return all configured spec keys, excluding non-spec top-level keys."""
    return [k for k in self._data.keys() if k not in ("consumables", "attendance")]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All config tests pass (12 total — 9 existing + 3 new).

**Step 5: Commit**

```bash
git add src/config/loader.py tests/test_config.py
git commit -m "feat: add get_attendance() to ConfigLoader"
```

---

## Task 2: Add attendance mutation methods to ConfigLoader

**Files:**
- Modify: `src/config/loader.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_add_attendance_zone(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.add_attendance_zone(1005, "Magtheridon's Lair", 1)
    result = loader.get_attendance()
    assert len(result) == 3
    assert result[2]["zone_id"] == 1005


def test_add_attendance_zone_duplicate_raises(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    with pytest.raises(ValueError, match="already exists"):
        loader.add_attendance_zone(1002, "Karazhan", 1)


def test_remove_attendance_zone(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.remove_attendance_zone(1002)
    result = loader.get_attendance()
    assert len(result) == 1
    assert result[0]["zone_id"] == 1004


def test_remove_attendance_zone_not_found_raises(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    with pytest.raises(ValueError, match="not found"):
        loader.remove_attendance_zone(9999)


def test_update_attendance_zone(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.update_attendance_zone(1002, 2)
    result = loader.get_attendance()
    entry = next(e for e in result if e["zone_id"] == 1002)
    assert entry["required_per_week"] == 2


def test_update_attendance_zone_not_found_raises(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    with pytest.raises(ValueError, match="not found"):
        loader.update_attendance_zone(9999, 2)


def test_add_attendance_zone_persists(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.add_attendance_zone(1005, "Magtheridon's Lair", 1)
    loader2 = ConfigLoader(config_file_with_attendance)
    assert len(loader2.get_attendance()) == 3
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_add_attendance_zone tests/test_config.py::test_remove_attendance_zone tests/test_config.py::test_update_attendance_zone -v`
Expected: FAIL — methods don't exist yet.

**Step 3: Write minimal implementation**

Add to `src/config/loader.py`:

```python
def add_attendance_zone(self, zone_id: int, label: str, required_per_week: int) -> None:
    """Add a new zone to attendance requirements and persist to disk."""
    attendance = self._data.setdefault("attendance", [])
    if any(e["zone_id"] == zone_id for e in attendance):
        raise ValueError(f"Zone {zone_id} already exists in attendance config")
    attendance.append({
        "zone_id": zone_id,
        "label": label,
        "required_per_week": required_per_week,
    })
    self._save()

def remove_attendance_zone(self, zone_id: int) -> None:
    """Remove a zone from attendance requirements and persist to disk."""
    attendance = self._data.get("attendance", [])
    original_len = len(attendance)
    self._data["attendance"] = [e for e in attendance if e["zone_id"] != zone_id]
    if len(self._data["attendance"]) == original_len:
        raise ValueError(f"Zone {zone_id} not found in attendance config")
    self._save()

def update_attendance_zone(self, zone_id: int, required_per_week: int) -> None:
    """Update the required_per_week for a zone and persist to disk."""
    attendance = self._data.get("attendance", [])
    for entry in attendance:
        if entry["zone_id"] == zone_id:
            entry["required_per_week"] = required_per_week
            self._save()
            return
    raise ValueError(f"Zone {zone_id} not found in attendance config")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All config tests pass (19 total — 12 from Task 1 + 7 new).

**Step 5: Commit**

```bash
git add src/config/loader.py tests/test_config.py
git commit -m "feat: add attendance mutation methods to ConfigLoader"
```

---

## Task 3: Add `get_guild_reports()` to API client

**Files:**
- Modify: `src/api/warcraftlogs.py`
- Test: `tests/test_api.py`

**Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::test_get_guild_reports tests/test_api.py::test_get_guild_reports_empty tests/test_api.py::test_get_guild_reports_null_zone_skipped -v`
Expected: FAIL — `get_guild_reports` method does not exist.

**Step 3: Write minimal implementation**

Add to `src/api/warcraftlogs.py`:

```python
async def get_guild_reports(
    self,
    guild_name: str,
    server_slug: str,
    region: str,
    start_time: int,
    end_time: int,
) -> list:
    """Fetch all guild reports within a time range, with zone and player data."""
    gql = """
    query($guildName: String!, $guildServerSlug: String!, $guildServerRegion: String!,
          $startTime: Float!, $endTime: Float!) {
      reportData {
        reports(guildName: $guildName, guildServerSlug: $guildServerSlug,
                guildServerRegion: $guildServerRegion,
                startTime: $startTime, endTime: $endTime) {
          data {
            code
            startTime
            zone { id name }
            rankedCharacters { name }
          }
        }
      }
    }
    """
    result = await self.query(gql, {
        "guildName": guild_name,
        "guildServerSlug": server_slug,
        "guildServerRegion": region,
        "startTime": float(start_time),
        "endTime": float(end_time),
    })
    reports_data = result["data"]["reportData"]["reports"]["data"]
    return [
        {
            "code": r["code"],
            "startTime": r["startTime"],
            "zone": r["zone"],
            "players": [c["name"] for c in (r.get("rankedCharacters") or [])],
        }
        for r in reports_data
        if r.get("zone") is not None
    ]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: All API tests pass (13 total — 10 existing + 3 new).

**Step 5: Commit**

```bash
git add src/api/warcraftlogs.py tests/test_api.py
git commit -m "feat: add get_guild_reports() to WarcraftLogsClient"
```

---

## Task 4: Add attendance checking logic

**Files:**
- Create: `src/attendance/checker.py`
- Create: `src/attendance/__init__.py`
- Create: `tests/test_attendance.py`

This module contains the pure logic for grouping reports by week and checking attendance — no Discord or API dependencies.

**Step 1: Write the failing tests**

Create `tests/test_attendance.py`:

```python
import pytest
from datetime import datetime, timezone
from src.attendance.checker import group_reports_by_week, check_player_attendance


def _ms(year, month, day):
    """Helper: return epoch milliseconds for a date at midnight UTC."""
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


SAMPLE_REQUIREMENTS = [
    {"zone_id": 1002, "label": "Karazhan", "required_per_week": 1},
    {"zone_id": 1004, "label": "Gruul's Lair", "required_per_week": 1},
    {"zone_id": 1005, "label": "Magtheridon's Lair", "required_per_week": 1},
]


def test_group_reports_by_week():
    # Feb 17 2026 is a Tuesday, Feb 24 2026 is a Tuesday
    # ISO week: Feb 16 (Mon) - Feb 22 (Sun) = week 8
    # ISO week: Feb 23 (Mon) - Mar 1 (Sun) = week 9
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 18), "zone": {"id": 1004, "name": "Gruul's Lair"}, "players": ["Thrallbro"]},
        {"code": "c", "startTime": _ms(2026, 2, 24), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro", "Healbot"]},
    ]
    grouped = group_reports_by_week(reports)
    # Should have 2 weeks
    assert len(grouped) == 2


def test_check_player_attendance_perfect():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 18), "zone": {"id": 1004, "name": "Gruul's Lair"}, "players": ["Thrallbro"]},
        {"code": "c", "startTime": _ms(2026, 2, 19), "zone": {"id": 1005, "name": "Magtheridon's Lair"}, "players": ["Thrallbro"]},
    ]
    result = check_player_attendance("Thrallbro", reports, SAMPLE_REQUIREMENTS)
    # One week, all 3 raids attended
    assert len(result) == 1
    week = result[0]
    assert week["attended"] == 3
    assert week["required"] == 3
    assert all(z["met"] for z in week["zones"])


def test_check_player_attendance_missed_one():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 18), "zone": {"id": 1004, "name": "Gruul's Lair"}, "players": ["Thrallbro"]},
        # No Magtheridon's
    ]
    result = check_player_attendance("Thrallbro", reports, SAMPLE_REQUIREMENTS)
    assert len(result) == 1
    week = result[0]
    assert week["attended"] == 2
    assert week["required"] == 3
    mag = next(z for z in week["zones"] if z["zone_id"] == 1005)
    assert mag["met"] is False


def test_check_player_attendance_not_in_any_report():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Healbot"]},
    ]
    result = check_player_attendance("Thrallbro", reports, SAMPLE_REQUIREMENTS)
    assert len(result) == 1
    assert result[0]["attended"] == 0


def test_check_player_attendance_multiple_reports_same_zone_same_week():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 19), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
    ]
    reqs = [{"zone_id": 1002, "label": "Karazhan", "required_per_week": 2}]
    result = check_player_attendance("Thrallbro", reports, reqs)
    assert len(result) == 1
    kara = result[0]["zones"][0]
    assert kara["met"] is True
    assert kara["count"] == 2


def test_check_player_attendance_required_2_only_did_1():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
    ]
    reqs = [{"zone_id": 1002, "label": "Karazhan", "required_per_week": 2}]
    result = check_player_attendance("Thrallbro", reports, reqs)
    kara = result[0]["zones"][0]
    assert kara["met"] is False
    assert kara["count"] == 1


def test_group_reports_empty():
    assert group_reports_by_week([]) == {}
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_attendance.py -v`
Expected: FAIL — module `src.attendance.checker` does not exist.

**Step 3: Write minimal implementation**

Create `src/attendance/__init__.py` (empty file).

Create `src/attendance/checker.py`:

```python
from datetime import datetime, timezone


def group_reports_by_week(reports: list) -> dict:
    """
    Group reports by ISO week.

    Returns dict of (year, week_number) -> list of reports.
    """
    weeks: dict[tuple[int, int], list] = {}
    for report in reports:
        dt = datetime.fromtimestamp(report["startTime"] / 1000, tz=timezone.utc)
        iso = dt.isocalendar()
        key = (iso[0], iso[1])  # (year, week)
        weeks.setdefault(key, []).append(report)
    return weeks


def check_player_attendance(
    player_name: str,
    reports: list,
    requirements: list,
) -> list:
    """
    Check a player's attendance against weekly requirements.

    Returns a list of week records sorted most recent first, each containing:
    - week_start: date string for the Monday of that week
    - attended: number of required zones the player attended
    - required: total number of required zone slots
    - zones: list of {zone_id, label, required, count, met}
    """
    weeks = group_reports_by_week(reports)
    result = []

    for (year, week_num), week_reports in sorted(weeks.items(), reverse=True):
        week_monday = datetime.fromisocalendar(year, week_num, 1)
        zone_results = []
        attended = 0

        for req in requirements:
            zone_id = req["zone_id"]
            required = req["required_per_week"]
            count = sum(
                1 for r in week_reports
                if r["zone"]["id"] == zone_id and player_name in r["players"]
            )
            met = count >= required
            if met:
                attended += 1
            zone_results.append({
                "zone_id": zone_id,
                "label": req["label"],
                "required": required,
                "count": count,
                "met": met,
            })

        result.append({
            "week_start": week_monday.strftime("%b %d"),
            "attended": attended,
            "required": len(requirements),
            "zones": zone_results,
        })

    return result
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_attendance.py -v`
Expected: All 7 attendance tests pass.

**Step 5: Commit**

```bash
git add src/attendance/__init__.py src/attendance/checker.py tests/test_attendance.py
git commit -m "feat: add attendance checking logic with week grouping"
```

---

## Task 5: Add attendance config to config.yaml

**Files:**
- Modify: `config.yaml`

**Step 1: Add the attendance section**

Append to the end of `config.yaml`:

```yaml
# ──────────────────────────────────────────────
# ATTENDANCE REQUIREMENTS
# Officers can add/remove zones as the guild progresses.
# required_per_week: how many clears of this zone are expected per week.
# Use /setattendance in Discord to manage, or edit this file directly.
# ──────────────────────────────────────────────

attendance:
  - zone_id: 1002
    label: "Karazhan"
    required_per_week: 1
  - zone_id: 1004
    label: "Gruul's Lair"
    required_per_week: 1
  - zone_id: 1005
    label: "Magtheridon's Lair"
    required_per_week: 1
```

**Step 2: Run all existing tests to make sure nothing breaks**

Run: `pytest -v`
Expected: All tests pass (existing + new).

**Step 3: Commit**

```bash
git add config.yaml
git commit -m "feat: add attendance requirements to config.yaml"
```

---

## Task 6: Add `/attendance` command (per-player)

**Files:**
- Create: `src/commands/attendance.py`
- Modify: `src/bot.py` (add to `_COMMAND_MODULES`)

**Step 1: Create the command module**

Create `src/commands/attendance.py`:

```python
import time
import discord
from discord import app_commands
from src.bot import bot, GUILD_NAME, GUILD_SERVER, GUILD_REGION
from src.attendance.checker import check_player_attendance


@bot.tree.command(name="attendance", description="Show a player's raid attendance")
@app_commands.describe(
    character="Character name (e.g. Thrallbro)",
    weeks="Number of recent weeks to check (default: 4)",
)
async def attendance_cmd(interaction: discord.Interaction, character: str, weeks: int = 4):
    await interaction.response.defer()

    requirements = bot.config.get_attendance()
    if not requirements:
        await interaction.followup.send("No attendance requirements configured. Use `/setattendance add` to set them up.")
        return

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (weeks * 7 * 24 * 60 * 60 * 1000)

    try:
        reports = await bot.wcl.get_guild_reports(GUILD_NAME, GUILD_SERVER, GUILD_REGION, start_ms, now_ms)
    except Exception:
        await interaction.followup.send("Failed to fetch guild reports from WarcraftLogs.")
        return

    if not reports:
        await interaction.followup.send(f"No raid data found for the last {weeks} weeks.")
        return

    result = check_player_attendance(character, reports, requirements)

    if not result:
        await interaction.followup.send(f"No raid data found for **{character}** in the last {weeks} weeks.")
        return

    total_attended = sum(w["attended"] for w in result)
    total_required = sum(w["required"] for w in result)
    pct = (total_attended / total_required * 100) if total_required > 0 else 0

    embed = discord.Embed(
        title=f"{character} — Attendance (last {weeks} weeks)",
        color=discord.Color.blue(),
    )

    lines = []
    for week in result:
        zone_parts = []
        for z in week["zones"]:
            icon = "\u2705" if z["met"] else "\u274c"
            zone_parts.append(f"{icon} {z['label']}")
        lines.append(f"**Week of {week['week_start']}:** {' | '.join(zone_parts)}")

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Attendance Rate: {pct:.1f}% ({total_attended}/{total_required})")

    await interaction.followup.send(embed=embed)
```

**Step 2: Register the module in bot.py**

In `src/bot.py`, add `"attendance"` to the `_COMMAND_MODULES` list:

```python
_COMMAND_MODULES = ["topconsistent", "player", "raidrecap", "setconfig", "attendance"]
```

**Step 3: Run all tests to verify nothing breaks**

Run: `pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/commands/attendance.py src/bot.py
git commit -m "feat: add /attendance command for per-player attendance"
```

---

## Task 7: Add `/attendancereport` command (guild-wide)

**Files:**
- Modify: `src/commands/attendance.py`

**Step 1: Add the guild-wide command**

Append to `src/commands/attendance.py`:

```python
@bot.tree.command(name="attendancereport", description="Show guild-wide raid attendance")
@app_commands.describe(weeks="Number of recent weeks to check (default: 4)")
async def attendancereport_cmd(interaction: discord.Interaction, weeks: int = 4):
    await interaction.response.defer()

    requirements = bot.config.get_attendance()
    if not requirements:
        await interaction.followup.send("No attendance requirements configured. Use `/setattendance add` to set them up.")
        return

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (weeks * 7 * 24 * 60 * 60 * 1000)

    try:
        reports = await bot.wcl.get_guild_reports(GUILD_NAME, GUILD_SERVER, GUILD_REGION, start_ms, now_ms)
    except Exception:
        await interaction.followup.send("Failed to fetch guild reports from WarcraftLogs.")
        return

    if not reports:
        await interaction.followup.send(f"No raid data found for the last {weeks} weeks.")
        return

    # Collect all unique player names across reports
    all_players = set()
    for report in reports:
        all_players.update(report["players"])

    # Check each player's attendance
    missed_players = []
    perfect_count = 0

    for player_name in sorted(all_players):
        result = check_player_attendance(player_name, reports, requirements)
        total_attended = sum(w["attended"] for w in result)
        total_required = sum(w["required"] for w in result)

        if total_attended >= total_required:
            perfect_count += 1
        else:
            missed = []
            for week in result:
                for z in week["zones"]:
                    if not z["met"]:
                        missed.append(f"{z['label']} wk {week['week_start']}")
            missed_players.append((player_name, total_required - total_attended, missed))

    missed_players.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title=f"Guild Attendance Report (last {weeks} weeks)",
        color=discord.Color.gold(),
    )

    lines = []
    for name, miss_count, details in missed_players:
        detail_str = ", ".join(details[:5])
        if len(details) > 5:
            detail_str += f" +{len(details) - 5} more"
        lines.append(f"\u274c **{name}** — missed {miss_count} ({detail_str})")

    if lines:
        embed.description = "\n".join(lines)
    else:
        embed.description = "Everyone has perfect attendance!"

    if perfect_count > 0:
        embed.set_footer(text=f"\u2705 {perfect_count} player(s) with perfect attendance")

    await interaction.followup.send(embed=embed)
```

**Step 2: Run all tests**

Run: `pytest -v`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add src/commands/attendance.py
git commit -m "feat: add /attendancereport command for guild-wide attendance"
```

---

## Task 8: Add `/setattendance` command

**Files:**
- Create: `src/commands/setattendance.py`
- Modify: `src/bot.py` (add to `_COMMAND_MODULES`)

**Step 1: Create the command module**

Create `src/commands/setattendance.py`:

```python
import discord
from discord import app_commands
from src.bot import bot, is_officer


group = app_commands.Group(name="setattendance", description="Manage attendance requirements")


@group.command(name="add", description="Add a raid zone to attendance requirements")
@app_commands.describe(
    zone_id="WarcraftLogs zone ID (e.g. 1002 for Karazhan)",
    label="Display name for the zone",
    required_per_week="Number of clears required per week",
)
async def setattendance_add(interaction: discord.Interaction, zone_id: int, label: str, required_per_week: int):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        bot.config.add_attendance_zone(zone_id, label, required_per_week)
        await interaction.followup.send(
            f"\u2705 Added **{label}** (zone {zone_id}) — {required_per_week}x per week"
        )
    except ValueError as e:
        await interaction.followup.send(f"Error: {e}")


@group.command(name="remove", description="Remove a raid zone from attendance requirements")
@app_commands.describe(zone_id="WarcraftLogs zone ID to remove")
async def setattendance_remove(interaction: discord.Interaction, zone_id: int):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        # Get label before removing for display
        attendance = bot.config.get_attendance()
        entry = next((e for e in attendance if e["zone_id"] == zone_id), None)
        label = entry["label"] if entry else str(zone_id)
        bot.config.remove_attendance_zone(zone_id)
        await interaction.followup.send(f"\u2705 Removed **{label}** (zone {zone_id}) from attendance requirements")
    except ValueError as e:
        await interaction.followup.send(f"Error: {e}")


@group.command(name="update", description="Update required clears per week for a zone")
@app_commands.describe(
    zone_id="WarcraftLogs zone ID to update",
    required_per_week="New number of clears required per week",
)
async def setattendance_update(interaction: discord.Interaction, zone_id: int, required_per_week: int):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        attendance = bot.config.get_attendance()
        entry = next((e for e in attendance if e["zone_id"] == zone_id), None)
        old_val = entry["required_per_week"] if entry else "?"
        label = entry["label"] if entry else str(zone_id)
        bot.config.update_attendance_zone(zone_id, required_per_week)
        await interaction.followup.send(
            f"\u2705 Updated **{label}** (zone {zone_id}): **{old_val}** → **{required_per_week}** per week"
        )
    except ValueError as e:
        await interaction.followup.send(f"Error: {e}")


@group.command(name="list", description="Show current attendance requirements")
async def setattendance_list(interaction: discord.Interaction):
    attendance = bot.config.get_attendance()
    if not attendance:
        await interaction.response.send_message("No attendance requirements configured.", ephemeral=True)
        return

    lines = []
    for entry in attendance:
        lines.append(f"• **{entry['label']}** (zone {entry['zone_id']}) — {entry['required_per_week']}x per week")

    embed = discord.Embed(
        title="Attendance Requirements",
        description="\n".join(lines),
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(group)
```

**Step 2: Register the module in bot.py**

In `src/bot.py`, add `"setattendance"` to the `_COMMAND_MODULES` list:

```python
_COMMAND_MODULES = ["topconsistent", "player", "raidrecap", "setconfig", "attendance", "setattendance"]
```

**Step 3: Run all tests**

Run: `pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/commands/setattendance.py src/bot.py
git commit -m "feat: add /setattendance command group for managing attendance requirements"
```

---

## Task 9: Update CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update CLAUDE.md**

Add to the project structure section:
- `src/attendance/checker.py` — week grouping and attendance checking logic
- `src/commands/attendance.py` — `/attendance` and `/attendancereport` commands
- `src/commands/setattendance.py` — `/setattendance` officer command group

Add to the Discord Commands table:
- `/attendance <character> [weeks]` — Per-player raid attendance report
- `/attendancereport [weeks]` — Guild-wide attendance summary
- `/setattendance add/remove/update/list` — Officers manage attendance requirements

Add to the config.yaml Format section: document the `attendance:` key.

Update test count to reflect the new tests.

**Step 2: Update README.md**

Add command documentation for `/attendance`, `/attendancereport`, and `/setattendance`.
Add a section on attendance tracking explaining how it works and how to configure it.

**Step 3: Run all tests one final time**

Run: `pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add attendance tracking to CLAUDE.md and README"
```
