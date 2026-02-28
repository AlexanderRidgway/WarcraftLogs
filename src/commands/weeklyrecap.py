from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_NAME, GUILD_SERVER, GUILD_REGION
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
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    if weeks_ago < 0 or weeks_ago > 52:
        await interaction.followup.send("weeks_ago must be between 0 and 52.")
        return

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
