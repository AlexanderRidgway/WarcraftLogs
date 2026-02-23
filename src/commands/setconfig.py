import discord
from discord import app_commands
from src.bot import bot, is_officer


@bot.tree.command(name="setconfig", description="Update a metric target for a class spec")
@app_commands.describe(
    spec="Class:spec key (e.g. warrior:protection)",
    metric="Metric name (e.g. sunder_armor_uptime)",
    target="New target value",
)
async def setconfig(interaction: discord.Interaction, spec: str, metric: str, target: int):
    if not is_officer(interaction):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )
        return

    try:
        old_profile = bot.config.get_spec(spec)
        if old_profile is None:
            await interaction.response.send_message(
                f"Spec `{spec}` not found in config. Available specs:\n"
                + "\n".join(f"• `{s}`" for s in bot.config.all_specs()),
                ephemeral=True,
            )
            return

        old_target = next(
            (c["target"] for c in old_profile["contributions"] if c["metric"] == metric),
            None,
        )
        if old_target is None:
            available = [c["metric"] for c in old_profile["contributions"]]
            await interaction.response.send_message(
                f"Metric `{metric}` not found in `{spec}`. Available metrics:\n"
                + "\n".join(f"• `{m}`" for m in available),
                ephemeral=True,
            )
            return

        bot.config.update_target(spec, metric, target)

        await interaction.response.send_message(
            f"✅ Updated `{spec}` › `{metric}`: **{old_target}** → **{target}**"
        )

    except Exception as e:
        await interaction.response.send_message(f"Error updating config: {e}", ephemeral=True)
