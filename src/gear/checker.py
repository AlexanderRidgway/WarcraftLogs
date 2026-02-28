SLOT_NAMES = {
    0: "Head", 1: "Neck", 2: "Shoulder", 3: "Shirt", 4: "Chest",
    5: "Waist", 6: "Legs", 7: "Feet", 8: "Wrist", 9: "Hands",
    10: "Ring 1", 11: "Ring 2", 12: "Trinket 1", 13: "Trinket 2",
    14: "Cloak", 15: "Main Hand", 16: "Off Hand", 17: "Ranged",
    18: "Tabard",
}

EXCLUDED_SLOTS = {3, 18}  # Shirt, Tabard — cosmetic only


def check_player_gear(gear_items: list, gear_config: dict) -> dict:
    """
    Check a player's gear against config thresholds.

    Returns:
        dict with avg_ilvl, ilvl_ok, and issues list.
    """
    min_quality = gear_config.get("min_quality", 3)
    check_enchants = gear_config.get("check_enchants", True)
    check_gems = gear_config.get("check_gems", True)
    enchant_slots = set(gear_config.get("enchant_slots", []))
    min_avg_ilvl = gear_config.get("min_avg_ilvl", 100)

    issues = []
    ilvl_sum = 0
    ilvl_count = 0

    for item in gear_items:
        slot = item.get("slot")
        if slot in EXCLUDED_SLOTS:
            continue

        slot_name = SLOT_NAMES.get(slot, f"Slot {slot}")
        item_level = item.get("itemLevel", 0)
        quality = item.get("quality", 0)

        # Skip empty slots (e.g. off-hand when using a 2-handed weapon)
        if item.get("id", 0) == 0 or item_level == 0:
            continue

        ilvl_sum += item_level
        ilvl_count += 1

        # Check quality
        if quality < min_quality:
            quality_names = {0: "Poor", 1: "Common", 2: "Uncommon (Green)", 3: "Rare (Blue)", 4: "Epic", 5: "Legendary"}
            q_name = quality_names.get(quality, f"quality {quality}")
            issues.append({"slot": slot_name, "problem": f"{q_name} quality item (ilvl {item_level})"})

        # Check enchants
        if check_enchants and slot in enchant_slots:
            if "permanentEnchant" not in item or not item["permanentEnchant"]:
                issues.append({"slot": slot_name, "problem": "Missing enchant"})

        # Check gems
        if check_gems:
            gems = item.get("gems", [])
            empty_gems = sum(1 for g in gems if g.get("id", 0) == 0)
            if empty_gems > 0:
                issues.append({"slot": slot_name, "problem": f"Empty gem socket ({empty_gems})"})

    avg_ilvl = (ilvl_sum / ilvl_count) if ilvl_count > 0 else 0
    ilvl_ok = avg_ilvl >= min_avg_ilvl

    return {
        "avg_ilvl": round(avg_ilvl, 1),
        "ilvl_ok": ilvl_ok,
        "issues": issues,
    }


def check_raid_gear(players_gear: list, gear_config: dict) -> list:
    """
    Check gear for all players. Returns only players with issues.

    Each entry: {name, avg_ilvl, ilvl_ok, issues}
    """
    results = []
    for player in players_gear:
        result = check_player_gear(player["gear"], gear_config)
        if result["issues"] or not result["ilvl_ok"]:
            results.append({
                "name": player["name"],
                **result,
            })
    return results
