import discord
from discord import app_commands
from src.bot import bot, is_officer


group = app_commands.Group(name="setattendance", description="Manage attendance requirements")


@group.command(name="add", description="Add a raid zone to attendance requirements")
@app_commands.describe(
    zone_id="WarcraftLogs zone ID (e.g. 1002 for Karazhan)",
    label="Display name for the zone",
    required_per_week="Number of clears required per week",
)
async def setattendance_add(interaction: discord.Interaction, zone_id: int, label: str, required_per_week: int):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        bot.config.add_attendance_zone(zone_id, label, required_per_week)
        await interaction.followup.send(
            f"\u2705 Added **{label}** (zone {zone_id}) — {required_per_week}x per week"
        )
    except ValueError as e:
        await interaction.followup.send(f"Error: {e}")


@group.command(name="remove", description="Remove a raid zone from attendance requirements")
@app_commands.describe(zone_id="WarcraftLogs zone ID to remove")
async def setattendance_remove(interaction: discord.Interaction, zone_id: int):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        # Get label before removing for display
        attendance = bot.config.get_attendance()
        entry = next((e for e in attendance if e["zone_id"] == zone_id), None)
        label = entry["label"] if entry else str(zone_id)
        bot.config.remove_attendance_zone(zone_id)
        await interaction.followup.send(f"\u2705 Removed **{label}** (zone {zone_id}) from attendance requirements")
    except ValueError as e:
        await interaction.followup.send(f"Error: {e}")


@group.command(name="update", description="Update required clears per week for a zone")
@app_commands.describe(
    zone_id="WarcraftLogs zone ID to update",
    required_per_week="New number of clears required per week",
)
async def setattendance_update(interaction: discord.Interaction, zone_id: int, required_per_week: int):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        attendance = bot.config.get_attendance()
        entry = next((e for e in attendance if e["zone_id"] == zone_id), None)
        old_val = entry["required_per_week"] if entry else "?"
        label = entry["label"] if entry else str(zone_id)
        bot.config.update_attendance_zone(zone_id, required_per_week)
        await interaction.followup.send(
            f"\u2705 Updated **{label}** (zone {zone_id}): **{old_val}** \u2192 **{required_per_week}** per week"
        )
    except ValueError as e:
        await interaction.followup.send(f"Error: {e}")


@group.command(name="list", description="Show current attendance requirements")
async def setattendance_list(interaction: discord.Interaction):
    attendance = bot.config.get_attendance()
    if not attendance:
        await interaction.response.send_message("No attendance requirements configured.", ephemeral=True)
        return

    lines = []
    for entry in attendance:
        lines.append(f"\u2022 **{entry['label']}** (zone {entry['zone_id']}) \u2014 {entry['required_per_week']}x per week")

    embed = discord.Embed(
        title="Attendance Requirements",
        description="\n".join(lines),
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(group)
