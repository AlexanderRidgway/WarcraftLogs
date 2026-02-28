import logging
import time
import discord
from discord import app_commands
from src.bot import bot, GUILD_NAME, GUILD_SERVER, GUILD_REGION

logger = logging.getLogger(__name__)
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
        logger.exception("Failed to fetch guild reports")
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
        logger.exception("Failed to fetch guild reports")
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
