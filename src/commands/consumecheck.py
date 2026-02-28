import logging
import discord
from discord import app_commands
from src.bot import bot
from src.commands.raidrecap import _extract_report_code

logger = logging.getLogger(__name__)


@bot.tree.command(name="consumecheck", description="Check consumable usage from a raid log")
@app_commands.describe(log_url="WarcraftLogs report URL")
async def consumecheck_cmd(interaction: discord.Interaction, log_url: str):
    await interaction.response.defer()

    report_code = _extract_report_code(log_url)
    if not report_code:
        await interaction.followup.send(
            "Invalid URL. Use a WarcraftLogs report URL like `https://www.warcraftlogs.com/reports/ABC123`"
        )
        return

    consumables_profile = bot.config.get_consumables()
    if not consumables_profile:
        await interaction.followup.send("No consumables configured in config.yaml.")
        return

    # Non-optional consumables are the ones we check
    required_contribs = [c for c in consumables_profile if not c.get("optional")]

    try:
        report_players = await bot.wcl.get_report_players(report_code)
        timerange = await bot.wcl.get_report_timerange(report_code)
    except Exception:
        logger.exception("Failed to fetch report data for %s", report_code)
        await interaction.followup.send("Could not fetch report data from WarcraftLogs.")
        return

    if not report_players:
        await interaction.followup.send("No players found in this report.")
        return

    flagged = []  # list of (name, reasons, details)

    for player in report_players:
        try:
            c_data = await bot.wcl.get_utility_data(
                report_code, player["id"],
                timerange["start"], timerange["end"],
                consumables_profile,
            )
        except Exception:
            logger.warning("Failed to fetch consumable data for %s", player["name"])
            continue

        # Flask/Elixir check: flask >50% OR (battle elixir >50% AND guardian elixir >50%)
        flask_uptime = c_data.get("flask_uptime", 0)
        battle_elixir_uptime = c_data.get("battle_elixir_uptime", 0)
        guardian_elixir_uptime = c_data.get("guardian_elixir_uptime", 0)

        has_flask = flask_uptime > 50
        has_elixirs = battle_elixir_uptime > 50 and guardian_elixir_uptime > 50
        flask_ok = has_flask or has_elixirs

        # Potion check: at least 1 use of any potion type
        haste_pots = c_data.get("haste_potion_count", 0)
        destro_pots = c_data.get("destruction_potion_count", 0)
        mana_pots = c_data.get("mana_potion_count", 0)
        potion_ok = (haste_pots + destro_pots + mana_pots) >= 1

        if flask_ok and potion_ok:
            continue

        reasons = []
        if not flask_ok:
            reasons.append("No flask/elixirs")
        if not potion_ok:
            reasons.append("No potions")

        # Build detail lines for non-optional consumables
        details = []
        for contrib in required_contribs:
            val = c_data.get(contrib["metric"], 0)
            label = contrib["label"]
            if contrib["type"] == "uptime":
                details.append(f"{label}: {val:.0f}%")
            else:
                details.append(f"{label}: {int(val)}")

        flagged.append((player["name"], reasons, details))

    total = len(report_players)
    pass_count = total - len(flagged)

    embed = discord.Embed(
        title=f"Consumable Check — Report {report_code}",
        color=discord.Color.red() if flagged else discord.Color.green(),
    )

    if flagged:
        lines = []
        for name, reasons, details in flagged:
            header = f"\u26a0\ufe0f **{name}** — {', '.join(reasons)}"
            detail_str = " | ".join(details)
            lines.append(f"{header}\n  {detail_str}")
        embed.description = "\n\n".join(lines)
    else:
        embed.description = "\u2705 All players used their consumables!"

    if pass_count > 0 and flagged:
        embed.set_footer(text=f"\u2705 {pass_count}/{total} player(s) passed consumable checks")
    elif not flagged:
        embed.set_footer(text=f"{total} player(s) checked")

    await interaction.followup.send(embed=embed)
