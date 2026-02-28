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
