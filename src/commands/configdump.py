import discord
from discord import app_commands
from src.bot import bot, is_officer


@bot.tree.command(name="configdump", description="Display the current bot configuration")
async def configdump(interaction: discord.Interaction):
    if not is_officer(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    embeds = []

    # --- Spec Profiles ---
    spec_keys = bot.config.all_specs()
    if spec_keys:
        lines = []
        for spec_key in spec_keys:
            profile = bot.config.get_spec(spec_key)
            if profile is None:
                continue
            pw = profile.get("parse_weight", 0)
            uw = profile.get("utility_weight", 0)
            cw = profile.get("consumables_weight", 0)
            contribs = profile.get("contributions", [])
            contrib_strs = []
            for c in contribs:
                label = c.get("label", c["metric"])
                target = c.get("target", "?")
                contrib_strs.append(f"{label} (target: {target})")
            lines.append(
                f"**{spec_key}** — parse {pw:.0%} / utility {uw:.0%} / cons {cw:.0%}\n"
                + ("  " + ", ".join(contrib_strs) if contrib_strs else "  No contributions")
            )

        # Split into chunks if too long for one embed
        chunk = []
        chunk_len = 0
        for line in lines:
            if chunk_len + len(line) > 3800:
                embed = discord.Embed(title="Spec Profiles", color=discord.Color.blue())
                embed.description = "\n".join(chunk)
                embeds.append(embed)
                chunk = []
                chunk_len = 0
            chunk.append(line)
            chunk_len += len(line)

        if chunk:
            title = "Spec Profiles" if not embeds else "Spec Profiles (cont.)"
            embed = discord.Embed(title=title, color=discord.Color.blue())
            embed.description = "\n".join(chunk)
            embeds.append(embed)

    # --- Attendance ---
    attendance = bot.config.get_attendance()
    att_embed = discord.Embed(title="Attendance Requirements", color=discord.Color.green())
    if attendance:
        att_lines = [
            f"**{a['label']}** (zone {a['zone_id']}) — {a['required_per_week']}/week"
            for a in attendance
        ]
        att_embed.description = "\n".join(att_lines)
    else:
        att_embed.description = "No attendance requirements configured."
    embeds.append(att_embed)

    # --- Gear Check ---
    gear = bot.config.get_gear_check()
    gear_embed = discord.Embed(title="Gear Check", color=discord.Color.orange())
    slot_names = {
        0: "Head", 2: "Shoulder", 4: "Chest", 6: "Legs", 7: "Feet",
        8: "Wrist", 9: "Hands", 14: "Cloak", 15: "Main Hand",
    }
    enchant_slot_names = [slot_names.get(s, f"Slot {s}") for s in gear.get("enchant_slots", [])]
    gear_embed.description = (
        f"Min avg ilvl: **{gear.get('min_avg_ilvl')}**\n"
        f"Min quality: **{gear.get('min_quality')}** (3=Blue, 4=Epic)\n"
        f"Check enchants: **{gear.get('check_enchants')}**\n"
        f"Check gems: **{gear.get('check_gems')}**\n"
        f"Enchant slots: {', '.join(enchant_slot_names)}"
    )
    embeds.append(gear_embed)

    # --- Consumables ---
    consumables = bot.config.get_consumables()
    if consumables:
        cons_embed = discord.Embed(title="Consumables", color=discord.Color.purple())
        cons_lines = []
        for c in consumables:
            label = c.get("label", c["metric"])
            target = c.get("target", "?")
            optional = " *(optional)*" if c.get("optional") else ""
            cons_lines.append(f"**{label}** — target: {target}{optional}")
        cons_embed.description = "\n".join(cons_lines)
        embeds.append(cons_embed)

    # Discord allows max 10 embeds per message
    await interaction.followup.send(embeds=embeds[:10])
