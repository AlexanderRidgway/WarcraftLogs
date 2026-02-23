import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_NAME, GUILD_SERVER, GUILD_REGION, TBC_ZONE_ID
from src.scoring.engine import score_player, score_consistency


@bot.tree.command(name="topconsistent", description="Rank raiders by consistency score")
@app_commands.describe(weeks="Number of recent weeks to include (default: 4)")
async def topconsistent(interaction: discord.Interaction, weeks: int = 4):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        roster = await bot.wcl.get_guild_roster(GUILD_NAME, GUILD_SERVER, GUILD_REGION)
    except Exception:
        await interaction.followup.send("Failed to fetch guild roster from WarcraftLogs.")
        return

    scores = []
    for member in roster:
        name = member["name"]
        server_slug = member["server"]["slug"]
        region = member["server"]["region"]["slug"].upper()

        try:
            rankings = await bot.wcl.get_character_rankings(name, server_slug, region, TBC_ZONE_ID)
        except Exception:
            continue

        if not rankings:
            continue

        spec = rankings[0].get("spec", "").lower()
        class_name = _class_id_to_name(member.get("classID", 0))
        spec_key = f"{class_name}:{spec}"
        profile = bot.config.get_spec(spec_key)

        _fallback_profile = {"utility_weight": 0.0, "parse_weight": 1.0, "contributions": []}
        boss_scores = []
        for ranking in rankings:
            parse = ranking.get("rankPercent", 0)
            active_profile = profile or _fallback_profile
            boss_scores.append(score_player(active_profile, parse, {}))

        if boss_scores:
            scores.append((name, score_consistency(boss_scores)))

    scores.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title=f"Top Consistent Raiders (last {weeks} weeks)",
        color=discord.Color.gold(),
    )

    if not scores:
        embed.description = "No data found."
    else:
        lines = []
        for i, (name, score) in enumerate(scores[:15], 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"**{i}.**")
            lines.append(f"{medal} **{name}** — {score:.1f}")
        embed.description = "\n".join(lines)

    await interaction.followup.send(embed=embed)


def _class_id_to_name(class_id: int) -> str:
    """Map WarcraftLogs class IDs to lowercase class names."""
    mapping = {
        1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue",
        5: "priest", 6: "deathknight", 7: "shaman", 8: "mage",
        9: "warlock", 11: "druid",
    }
    return mapping.get(class_id, "unknown")
