import logging
from src.api.warcraftlogs import WarcraftLogsClient

logger = logging.getLogger(__name__)

CLASS_ID_TO_NAME = {
    1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue",
    5: "priest", 6: "death knight", 7: "shaman", 8: "mage",
    9: "warlock", 11: "druid",
}


async def sync_roster(wcl: WarcraftLogsClient, guild_name: str, server_slug: str, region: str) -> list[dict]:
    """Fetch guild roster from WCL and return normalized player dicts."""
    raw = await wcl.get_guild_roster(guild_name, server_slug, region)
    players = []
    for member in raw:
        players.append({
            "name": member["name"],
            "class_id": member["classID"],
            "class_name": CLASS_ID_TO_NAME.get(member["classID"], "unknown"),
            "server": member["server"]["slug"],
            "region": member["server"]["region"]["slug"],
        })
    logger.info("Synced %d players from guild roster", len(players))
    return players
