# Weekly Recap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `/weeklyrecap` command that automatically pulls all guild reports for a week and produces a multi-embed digest: top performers, zone summaries, attendance, and gear issues.

**Architecture:** A new `src/commands/weeklyrecap.py` command module uses existing API methods (`get_guild_reports`, `get_report_rankings`, `get_report_gear`) and existing logic modules (`check_player_attendance`, `check_raid_gear`, `score_player`) to aggregate data across multiple reports. A small helper function `aggregate_weekly_scores` in `src/scoring/engine.py` averages player scores across reports. The command sends 4 Discord embeds.

**Tech Stack:** Python 3.11, discord.py 2.3.2, aiohttp 3.9.1, pyyaml 6.0.1, pytest + pytest-asyncio.

---

## Task 1: Add `aggregate_weekly_scores()` to scoring engine

**Files:**
- Modify: `src/scoring/engine.py`
- Test: `tests/test_scoring.py`

**Step 1: Write the failing tests**

Add to `tests/test_scoring.py`:

```python
from src.scoring.engine import aggregate_weekly_scores


def test_aggregate_weekly_scores_averages_per_player():
    """Averages scores across multiple reports per player."""
    report_scores = [
        # Report 1
        [("Thrallbro", "fury", 90.0, 85.0), ("Healbot", "holy", 80.0, 75.0)],
        # Report 2
        [("Thrallbro", "fury", 70.0, 65.0), ("Leetmage", "arcane", 95.0, 92.0)],
    ]
    result = aggregate_weekly_scores(report_scores)
    # Thrallbro: avg score (90+70)/2=80, avg parse (85+65)/2=75, 2 fights
    thrall = next(r for r in result if r["name"] == "Thrallbro")
    assert thrall["avg_score"] == pytest.approx(80.0, abs=0.1)
    assert thrall["avg_parse"] == pytest.approx(75.0, abs=0.1)
    assert thrall["fight_count"] == 2
    # Healbot: 1 fight
    healbot = next(r for r in result if r["name"] == "Healbot")
    assert healbot["fight_count"] == 1
    # Result should be sorted by avg_score descending
    assert result[0]["avg_score"] >= result[1]["avg_score"]


def test_aggregate_weekly_scores_empty():
    assert aggregate_weekly_scores([]) == []


def test_aggregate_weekly_scores_single_report():
    report_scores = [
        [("Thrallbro", "fury", 90.0, 85.0)],
    ]
    result = aggregate_weekly_scores(report_scores)
    assert len(result) == 1
    assert result[0]["name"] == "Thrallbro"
    assert result[0]["avg_score"] == 90.0
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring.py::test_aggregate_weekly_scores_averages_per_player tests/test_scoring.py::test_aggregate_weekly_scores_empty tests/test_scoring.py::test_aggregate_weekly_scores_single_report -v`
Expected: FAIL — `aggregate_weekly_scores` does not exist.

**Step 3: Write minimal implementation**

Add to `src/scoring/engine.py`:

```python
def aggregate_weekly_scores(report_scores: list[list[tuple]]) -> list[dict]:
    """
    Aggregate player scores across multiple reports.

    Args:
        report_scores: List of reports, each a list of (name, spec, score, parse) tuples.

    Returns:
        List of {name, spec, avg_score, avg_parse, fight_count} dicts, sorted by avg_score desc.
    """
    player_data: dict[str, dict] = {}
    for report in report_scores:
        for name, spec, score, parse in report:
            if name not in player_data:
                player_data[name] = {"spec": spec, "scores": [], "parses": []}
            player_data[name]["scores"].append(score)
            player_data[name]["parses"].append(parse)

    result = []
    for name, data in player_data.items():
        result.append({
            "name": name,
            "spec": data["spec"],
            "avg_score": sum(data["scores"]) / len(data["scores"]),
            "avg_parse": sum(data["parses"]) / len(data["parses"]),
            "fight_count": len(data["scores"]),
        })

    result.sort(key=lambda x: x["avg_score"], reverse=True)
    return result
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: All scoring tests pass.

**Step 5: Commit**

```bash
git add src/scoring/engine.py tests/test_scoring.py
git commit -m "feat: add aggregate_weekly_scores() to scoring engine"
```

---

## Task 2: Create `/weeklyrecap` command

**Files:**
- Create: `src/commands/weeklyrecap.py`
- Modify: `src/bot.py` (add to `_COMMAND_MODULES`)

**Step 1: Create the command module**

Create `src/commands/weeklyrecap.py`:

```python
import time
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from src.bot import bot, GUILD_NAME, GUILD_SERVER, GUILD_REGION
from src.scoring.engine import score_player, aggregate_weekly_scores
from src.attendance.checker import check_player_attendance
from src.gear.checker import check_raid_gear


def _week_range_ms(weeks_ago: int = 0) -> tuple[int, int, str]:
    """
    Calculate Monday 00:00 UTC to Sunday 23:59:59 UTC for the target week.
    Returns (start_ms, end_ms, week_label).
    """
    now = datetime.now(timezone.utc)
    # Find Monday of the current week
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    # Go back N weeks
    monday = monday - timedelta(weeks=weeks_ago)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    label = monday.strftime("%b %d")
    return int(monday.timestamp() * 1000), int(sunday.timestamp() * 1000), label


@bot.tree.command(name="weeklyrecap", description="Full weekly raid digest from guild reports")
@app_commands.describe(weeks_ago="How many weeks back to look (0 = current week, 1 = last week)")
async def weeklyrecap_cmd(interaction: discord.Interaction, weeks_ago: int = 0):
    await interaction.response.defer()

    start_ms, end_ms, week_label = _week_range_ms(weeks_ago)

    # 1. Fetch all guild reports for the week
    try:
        reports = await bot.wcl.get_guild_reports(GUILD_NAME, GUILD_SERVER, GUILD_REGION, start_ms, end_ms)
    except Exception:
        await interaction.followup.send("Failed to fetch guild reports from WarcraftLogs.")
        return

    if not reports:
        await interaction.followup.send(f"No guild reports found for the week of {week_label}.")
        return

    # 2. Score players across all reports
    all_report_scores = []
    zone_report_scores: dict[str, list] = {}  # zone_name -> list of scored tuples

    for report in reports:
        try:
            rankings = await bot.wcl.get_report_rankings(report["code"])
        except Exception:
            continue

        if not rankings:
            continue

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

        if scored:
            all_report_scores.append(scored)
            zone_name = report["zone"]["name"]
            zone_report_scores.setdefault(zone_name, []).append(scored)

    # --- Embed 1: Top Performers ---
    top_embed = discord.Embed(
        title=f"Weekly Top Performers — Week of {week_label}",
        color=discord.Color.gold(),
    )

    if all_report_scores:
        aggregated = aggregate_weekly_scores(all_report_scores)
        lines = []
        for i, player in enumerate(aggregated[:10], 1):
            medal = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}.get(i, f"**{i}.**")
            lines.append(f"{medal} **{player['name']}** — {player['avg_score']:.1f} ({player['fight_count']} fights)")
        top_embed.description = "\n".join(lines)
    else:
        top_embed.description = "No ranking data found in any reports."

    top_embed.set_footer(text=f"{len(reports)} report(s) found")

    # --- Embed 2: Zone Summaries ---
    zone_embed = discord.Embed(
        title=f"Zone Summaries — Week of {week_label}",
        color=discord.Color.blue(),
    )

    zone_lines = []
    for zone_name, zone_scores in zone_report_scores.items():
        zone_agg = aggregate_weekly_scores(zone_scores)
        all_players_in_zone = set()
        for scored_list in zone_scores:
            for name, *_ in scored_list:
                all_players_in_zone.add(name)
        run_count = len(zone_scores)
        player_count = len(all_players_in_zone)

        top3 = zone_agg[:3]
        top3_str = " | ".join(
            f"{medal} {p['name']} — {p['avg_score']:.1f}"
            for medal, p in zip(["\U0001f947", "\U0001f948", "\U0001f949"], top3)
        )

        zone_lines.append(f"**{zone_name}** ({run_count} run{'s' if run_count != 1 else ''}, {player_count} players)\n  {top3_str}")

    zone_embed.description = "\n\n".join(zone_lines) if zone_lines else "No zone data available."

    # --- Embed 3: Attendance ---
    attendance_embed = discord.Embed(
        title=f"Attendance — Week of {week_label}",
        color=discord.Color.green(),
    )

    requirements = bot.config.get_attendance()
    if requirements:
        all_players = set()
        for report in reports:
            all_players.update(report["players"])

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
                            missed.append(z["label"])
                missed_players.append((player_name, missed))

        missed_players.sort(key=lambda x: len(x[1]), reverse=True)

        att_lines = []
        for name, missed in missed_players:
            att_lines.append(f"\u274c **{name}** — missed {', '.join(missed)}")

        if att_lines:
            attendance_embed.description = "\n".join(att_lines)
            attendance_embed.color = discord.Color.orange()
        else:
            attendance_embed.description = "\u2705 Everyone met all attendance requirements!"

        if perfect_count > 0:
            attendance_embed.set_footer(text=f"\u2705 {perfect_count} player(s) met all requirements")
    else:
        attendance_embed.description = "No attendance requirements configured."

    # --- Embed 4: Gear Issues ---
    gear_embed = discord.Embed(
        title=f"Gear Issues — Week of {week_label}",
        color=discord.Color.green(),
    )

    gear_config = bot.config.get_gear_check()
    all_gear_issues: dict[str, dict] = {}  # player_name -> worst result

    for report in reports:
        try:
            players_gear = await bot.wcl.get_report_gear(report["code"])
            if players_gear:
                flagged = check_raid_gear(players_gear, gear_config)
                for player in flagged:
                    name = player["name"]
                    if name not in all_gear_issues or len(player["issues"]) > len(all_gear_issues[name]["issues"]):
                        all_gear_issues[name] = player
        except Exception:
            continue

    if all_gear_issues:
        gear_lines = []
        sorted_issues = sorted(all_gear_issues.values(), key=lambda x: len(x["issues"]), reverse=True)
        for player in sorted_issues[:15]:
            issue_count = len(player["issues"])
            ilvl_note = f", avg ilvl {player['avg_ilvl']:.0f}" if not player["ilvl_ok"] else ""
            gear_lines.append(f"\u26a0\ufe0f **{player['name']}** — {issue_count} issue{'s' if issue_count != 1 else ''}{ilvl_note}")
        gear_embed.description = "\n".join(gear_lines)
        gear_embed.color = discord.Color.orange()

        clean_count = len(set().union(*(set(p["name"] for p in (await bot.wcl.get_report_gear(r["code"]) or []) if True) for r in [])) or set())
        # Simplified: count from reports
    else:
        gear_embed.description = "\u2705 All players passed gear checks!"

    # Count total unique players for gear footer
    all_gear_players = set()
    for report in reports:
        all_gear_players.update(report["players"])
    clean_gear_count = len(all_gear_players) - len(all_gear_issues)
    if clean_gear_count > 0 and all_gear_issues:
        gear_embed.set_footer(text=f"\u2705 {clean_gear_count} player(s) passed all gear checks")

    # Send all embeds
    await interaction.followup.send(embeds=[top_embed, zone_embed, attendance_embed, gear_embed])
```

**Step 2: Register the module in bot.py**

In `src/bot.py`, add `"weeklyrecap"` to the `_COMMAND_MODULES` list.

**Step 3: Run all tests**

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/commands/weeklyrecap.py src/bot.py
git commit -m "feat: add /weeklyrecap command for full weekly guild digest"
```

---

## Task 3: Add tests for week range calculation

**Files:**
- Create: `tests/test_weeklyrecap.py`

**Step 1: Write the tests**

Create `tests/test_weeklyrecap.py`:

```python
import pytest
from datetime import datetime, timezone
from src.commands.weeklyrecap import _week_range_ms


def test_week_range_returns_monday_to_sunday():
    start_ms, end_ms, label = _week_range_ms(0)
    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
    # Start should be a Monday
    assert start_dt.weekday() == 0
    # End should be a Sunday
    assert end_dt.weekday() == 6
    # Start should be midnight
    assert start_dt.hour == 0 and start_dt.minute == 0
    # End should be 23:59:59
    assert end_dt.hour == 23 and end_dt.minute == 59


def test_week_range_weeks_ago_goes_back():
    current_start, _, _ = _week_range_ms(0)
    prev_start, _, _ = _week_range_ms(1)
    # Previous week start should be exactly 7 days before current
    diff_days = (current_start - prev_start) / (1000 * 60 * 60 * 24)
    assert diff_days == pytest.approx(7.0, abs=0.01)


def test_week_range_label_format():
    _, _, label = _week_range_ms(0)
    # Label should be "Mon DD" format (e.g. "Feb 23")
    assert len(label.split()) == 2
```

**Step 2: Run tests**

Run: `python -m pytest tests/test_weeklyrecap.py -v`
Expected: All 3 tests pass.

**Step 3: Commit**

```bash
git add tests/test_weeklyrecap.py
git commit -m "test: add week range calculation tests for /weeklyrecap"
```

---

## Task 4: Update CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update CLAUDE.md**

Add to the project structure:
- `src/commands/weeklyrecap.py` — `/weeklyrecap` full weekly digest command

Add to the Discord Commands table:
- `/weeklyrecap [weeks_ago]` | All | Full weekly raid digest from guild reports

Update test count.

Add a Known Design Decision about the multi-embed output.

**Step 2: Update README.md**

Add command documentation for `/weeklyrecap` with usage examples.
Add a "Weekly Recap" section explaining the 4-embed output.

**Step 3: Run all tests one final time**

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add /weeklyrecap to CLAUDE.md and README"
```
