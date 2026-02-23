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
    embed.set_footer(text=f"Report: {report_code}")

    await interaction.followup.send(embed=embed)


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
