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
