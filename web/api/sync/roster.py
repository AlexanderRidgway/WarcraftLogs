import logging
from src.api.warcraftlogs import WarcraftLogsClient

logger = logging.getLogger(__name__)

# Fallback class mapping (standard WoW Classic)
FALLBACK_CLASS_MAP = {
    1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue",
    5: "priest", 6: "death knight", 7: "shaman", 8: "mage",
    9: "warlock", 11: "druid",
}


async def sync_roster(wcl: WarcraftLogsClient, guild_name: str, server_slug: str, region: str) -> list[dict]:
    """Fetch guild roster from WCL and return normalized player dicts."""
    # Fetch class mapping dynamically from WCL (different game versions use different IDs)
    try:
        class_map = await wcl.get_game_classes()
        logger.info("Loaded %d game classes from WCL: %s", len(class_map), class_map)
    except Exception as e:
        logger.warning("Failed to fetch game classes, using fallback: %s", e)
        class_map = FALLBACK_CLASS_MAP

    raw = await wcl.get_guild_roster(guild_name, server_slug, region)
    players = []
    for member in raw:
        players.append({
            "name": member["name"],
            "class_id": member["classID"],
            "class_name": class_map.get(member["classID"], "unknown"),
            "server": member["server"]["slug"],
            "region": member["server"]["region"]["slug"],
        })
    logger.info("Synced %d players from guild roster", len(players))
    return players
