import discord
from discord import app_commands
from src.bot import bot, is_officer, GUILD_REGION, TBC_ZONE_ID
from src.scoring.engine import score_player, score_consistency
from src.commands.topconsistent import _class_id_to_name


@bot.tree.command(name="player", description="Show a player's parse and utility breakdown")
@app_commands.describe(character="Character name (e.g. Thrallbro-Stormrage)")
async def player_cmd(interaction: discord.Interaction, character: str):
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

    try:
        rankings = await bot.wcl.get_character_rankings(
            name, server_slug or "unknown", GUILD_REGION, TBC_ZONE_ID
        )
    except Exception:
        await interaction.followup.send(
            f"Could not find **{character}** on WarcraftLogs. Check the spelling and try `Name-Server` format."
        )
        return

    if not rankings:
        await interaction.followup.send(f"No recent logs found for **{character}**.")
        return

    spec = rankings[0].get("spec", "Unknown")
    spec_key = f"unknown:{spec.lower()}"
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
        if profile:
            score = score_player(profile, parse, {})
        else:
            score = parse
        boss_scores.append(score)
        parse_label = _parse_color(parse)
        boss_lines.append(f"{boss}: parse {parse_label} | score **{score:.1f}**")

    consistency = score_consistency(boss_scores)
    embed.description = "\n".join(boss_lines)
    embed.set_footer(text=f"Consistency Score: {consistency:.1f}/100")

    if profile is None:
        embed.description += f"\n\n⚠️ Spec `{spec_key}` not configured — utility metrics not included."

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
