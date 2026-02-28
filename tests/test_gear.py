import pytest
from src.gear.checker import check_player_gear, check_raid_gear, SLOT_NAMES

DEFAULT_CONFIG = {
    "min_avg_ilvl": 100,
    "min_quality": 3,
    "check_enchants": True,
    "check_gems": True,
    "enchant_slots": [0, 4, 5, 6, 7, 8, 9, 14, 15],
}


def _item(slot, quality=4, ilvl=120, enchant=3003, gems=None):
    """Helper to build a gear item dict."""
    item = {"id": 28000 + slot, "slot": slot, "quality": quality, "itemLevel": ilvl}
    if enchant is not None:
        item["permanentEnchant"] = enchant
    if gems is not None:
        item["gems"] = gems
    else:
        item["gems"] = []
    return item


def test_clean_gear_no_issues():
    gear = [_item(s) for s in [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    assert result["ilvl_ok"] is True
    assert result["issues"] == []
    assert result["avg_ilvl"] == 120.0


def test_green_item_flagged():
    gear = [_item(4, quality=2, ilvl=87)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    issues = [i for i in result["issues"] if "quality" in i["problem"].lower()]
    assert len(issues) == 1
    assert "Chest" in issues[0]["slot"]


def test_missing_enchant_flagged():
    gear = [_item(4, enchant=None)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    issues = [i for i in result["issues"] if "enchant" in i["problem"].lower()]
    assert len(issues) == 1


def test_non_enchantable_slot_not_flagged():
    # Slot 12 (trinket) is not in enchant_slots — should not be flagged
    gear = [_item(12, enchant=None)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    enchant_issues = [i for i in result["issues"] if "enchant" in i["problem"].lower()]
    assert len(enchant_issues) == 0


def test_empty_gem_socket_flagged():
    gear = [_item(0, gems=[{"id": 24027}, {"id": 0}])]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    issues = [i for i in result["issues"] if "gem" in i["problem"].lower()]
    assert len(issues) == 1


def test_no_gems_field_not_flagged():
    # Item without gem sockets — should not be flagged
    gear = [_item(0, gems=[])]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    gem_issues = [i for i in result["issues"] if "gem" in i["problem"].lower()]
    assert len(gem_issues) == 0


def test_low_avg_ilvl_flagged():
    gear = [_item(s, ilvl=90) for s in [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    assert result["ilvl_ok"] is False
    assert result["avg_ilvl"] == 90.0


def test_shirt_tabard_excluded():
    # Shirt (slot 3) and tabard (slot 18) should be excluded from all checks
    gear = [_item(3, quality=2, ilvl=1, enchant=None), _item(18, quality=2, ilvl=1, enchant=None)]
    result = check_player_gear(gear, DEFAULT_CONFIG)
    assert result["issues"] == []


def test_check_raid_gear_returns_only_issues():
    players = [
        {"name": "Thrallbro", "gear": [_item(4, quality=2, ilvl=87)]},
        {"name": "Cleanplayer", "gear": [_item(s) for s in [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15]]},
        {"name": "Leetmage", "gear": [_item(7, enchant=None)]},
    ]
    result = check_raid_gear(players, DEFAULT_CONFIG)
    names = [r["name"] for r in result]
    assert "Thrallbro" in names
    assert "Leetmage" in names
    assert "Cleanplayer" not in names


def test_check_enchants_disabled():
    config = {**DEFAULT_CONFIG, "check_enchants": False}
    gear = [_item(4, enchant=None)]
    result = check_player_gear(gear, config)
    enchant_issues = [i for i in result["issues"] if "enchant" in i["problem"].lower()]
    assert len(enchant_issues) == 0


def test_check_gems_disabled():
    config = {**DEFAULT_CONFIG, "check_gems": False}
    gear = [_item(0, gems=[{"id": 0}])]
    result = check_player_gear(gear, config)
    gem_issues = [i for i in result["issues"] if "gem" in i["problem"].lower()]
    assert len(gem_issues) == 0
