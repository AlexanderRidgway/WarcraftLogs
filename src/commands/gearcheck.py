import logging
import discord
from discord import app_commands
from src.bot import bot
from src.commands.raidrecap import _extract_report_code
from src.gear.checker import check_raid_gear

logger = logging.getLogger(__name__)


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
        logger.exception("Failed to fetch gear data for report %s", report_code)
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
