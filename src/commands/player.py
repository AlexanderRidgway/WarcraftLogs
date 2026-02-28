import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_REGION, ZONE_IDS
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

    rankings = []
    for zone_id in ZONE_IDS:
        try:
            zone_rankings = await bot.wcl.get_character_rankings(
                name, server_slug or "unknown", GUILD_REGION, zone_id
            )
            rankings.extend(zone_rankings)
        except Exception:
            continue

    if not rankings:
        await interaction.followup.send(f"No recent logs found for **{character}**.")
        return

    spec = rankings[0].get("spec", "Unknown")
    # zoneRankings JSON has class as numeric ID in bestRank, not as a top-level string
    best_rank = rankings[0].get("bestRank") or {}
    class_id = best_rank.get("class", 0)
    class_name = _class_id_to_name(class_id)
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
