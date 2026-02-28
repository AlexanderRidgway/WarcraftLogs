import logging
import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_NAME, GUILD_SERVER, GUILD_REGION, ZONE_IDS
from src.scoring.engine import score_player, score_consistency

logger = logging.getLogger(__name__)

_BATCH_SIZE = 15


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
        logger.exception("Failed to fetch guild roster")
        await interaction.followup.send("Failed to fetch guild roster from WarcraftLogs.")
        return

    logger.info("Roster has %d members, checking zones %s", len(roster), ZONE_IDS)

    # Build character tuples and class ID lookup
    characters = []
    class_ids = {}
    for member in roster:
        name = member["name"]
        server_slug = member["server"]["slug"]
        region = member["server"]["region"]["slug"].upper()
        characters.append((name, server_slug, region))
        class_ids[name] = member.get("classID", 0)

    # Fetch rankings in batched GraphQL queries (15 chars per query × 2 zones)
    all_rankings: dict[str, list] = {}
    for zone_id in ZONE_IDS:
        for i in range(0, len(characters), _BATCH_SIZE):
            batch = characters[i:i + _BATCH_SIZE]
            try:
                batch_results = await bot.wcl.get_character_rankings_batch(batch, zone_id)
                for name, rankings in batch_results.items():
                    all_rankings.setdefault(name, []).extend(rankings)
            except Exception:
                logger.exception("Batch ranking query failed for zone %d batch %d", zone_id, i)
                continue

    scores = []
    for name, rankings in all_rankings.items():
        spec = (rankings[0].get("spec") or "").lower()
        class_name = _class_id_to_name(class_ids.get(name, 0))
        spec_key = f"{class_name}:{spec}"
        profile = bot.config.get_spec(spec_key)

        _fallback_profile = {"utility_weight": 0.0, "parse_weight": 1.0, "contributions": []}
        boss_scores = []
        for ranking in rankings:
            parse = ranking.get("rankPercent") or 0
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
    """Map WarcraftLogs Classic Fresh class IDs to lowercase class names."""
    mapping = {
        2: "druid", 3: "hunter", 4: "mage", 6: "paladin",
        7: "priest", 8: "rogue", 9: "shaman", 10: "warlock",
        11: "warrior",
    }
    return mapping.get(class_id, "unknown")
