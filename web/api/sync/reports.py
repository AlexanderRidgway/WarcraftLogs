import logging
import time
from datetime import datetime, timezone

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from src.scoring.engine import score_player

logger = logging.getLogger(__name__)

# Valid spec names per WoW class (TBC Classic)
VALID_SPECS: dict[str, set[str]] = {
    "warrior": {"protection", "fury", "arms"},
    "paladin": {"holy", "protection", "retribution"},
    "rogue": {"combat", "assassination", "subtlety"},
    "hunter": {"beast mastery", "marksmanship", "survival"},
    "shaman": {"restoration", "elemental", "enhancement"},
    "druid": {"feral", "restoration", "balance"},
    "mage": {"arcane", "fire", "frost"},
    "warlock": {"affliction", "destruction", "demonology"},
    "priest": {"holy", "discipline", "shadow"},
}


def _validate_spec_key(cls: str, spec: str) -> str:
    """Build a spec_key, validating that the spec is valid for the class."""
    cls_lower = cls.lower()
    spec_lower = spec.lower()
    valid = VALID_SPECS.get(cls_lower, set())
    if spec_lower in valid:
        return f"{cls_lower}:{spec_lower}"
    logger.warning("Invalid spec '%s' for class '%s', using class only", spec, cls)
    return cls_lower


async def fetch_new_reports(
    wcl: WarcraftLogsClient,
    guild_name: str,
    server_slug: str,
    region: str,
    days_back: int = 7,
    existing_codes: set[str] | None = None,
) -> list[dict]:
    """Fetch guild reports from WCL, filtering out already-synced ones."""
    existing_codes = existing_codes or set()
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (days_back * 86400 * 1000)

    raw_reports = await wcl.get_guild_reports(guild_name, server_slug, region, start_ms, now_ms)

    new_reports = []
    for r in raw_reports:
        if r["code"] in existing_codes:
            continue
        new_reports.append({
            "code": r["code"],
            "zone_id": r["zone"]["id"],
            "zone_name": r["zone"]["name"],
            "start_time": datetime.utcfromtimestamp(r["startTime"] / 1000),
            "end_time": datetime.utcfromtimestamp((r["startTime"] + 3600000) / 1000),
            "player_names": r.get("players", []),
        })

    logger.info("Found %d new reports (of %d total)", len(new_reports), len(raw_reports))
    return new_reports


async def process_report(
    wcl: WarcraftLogsClient,
    report_code: str,
    config: ConfigLoader,
    player_classes: dict[str, str] | None = None,
) -> dict:
    """Process a single report: fetch rankings, gear, utility, consumables.

    Args:
        player_classes: Optional mapping of player name -> class_name from roster.
                        When provided, overrides the (sometimes incorrect) class from WCL rankings.
    """
    player_classes = player_classes or {}
    rankings_raw, per_fight_rankings = await wcl.get_report_rankings(report_code)
    players_raw = await wcl.get_report_players(report_code)
    timerange = await wcl.get_report_timerange(report_code)
    gear_raw = await wcl.get_report_gear(report_code)

    # Get accurate spec info from Summary table (more reliable than rankings)
    player_specs = await wcl.get_report_player_specs(report_code)

    source_map = {p["name"]: p["id"] for p in players_raw}
    consumables_profile = config.get_consumables()

    rankings = []
    scores = []
    utility_entries = []
    consumables_entries = []

    for player in rankings_raw:
        name = player["name"]
        # Prefer spec from Summary table playerDetails, fall back to rankings
        if name in player_specs:
            spec_key = player_specs[name].lower()
        else:
            spec = player.get("spec", "")
            cls = player_classes.get(name, player.get("class", ""))
            spec_key = _validate_spec_key(cls, spec) if cls else None
        parse = player.get("rankPercent", 0)
        spec_profile = config.get_spec(spec_key) if spec_key else None

        rankings.append({
            "player_name": name,
            "spec": spec_key or "unknown",
            "rank_percent": parse,
            "encounter_name": "Average",
        })

        # Utility data
        utility_data = {}
        if spec_profile and spec_profile.get("contributions") and name in source_map:
            try:
                utility_data = await wcl.get_utility_data(
                    report_code, source_map[name],
                    timerange["start"], timerange["end"],
                    spec_profile["contributions"],
                )
            except Exception:
                logger.warning("Failed to fetch utility for %s in %s", name, report_code)

            for contrib in spec_profile.get("contributions", []):
                metric = contrib["metric"]
                actual = utility_data.get(metric, 0)
                target = contrib["target"]
                metric_score = min(actual / target, 1.0) * 100 if target > 0 else 0
                utility_entries.append({
                    "player_name": name,
                    "report_code": report_code,
                    "metric_name": metric,
                    "label": contrib["label"],
                    "actual_value": actual,
                    "target_value": target,
                    "score": metric_score,
                })

        # Consumables data
        player_consumables = []
        if consumables_profile and name in source_map:
            try:
                # Separate combo_presence from standard consumables
                standard_consumes = [c for c in consumables_profile if c.get("type") != "combo_presence"]
                combo_consumes = [c for c in consumables_profile if c.get("type") == "combo_presence"]

                # Fetch standard consumables via get_utility_data
                c_data = {}
                if standard_consumes:
                    c_data = await wcl.get_utility_data(
                        report_code, source_map[name],
                        timerange["start"], timerange["end"],
                        standard_consumes,
                    )

                # Fetch combo_presence consumables
                for combo in combo_consumes:
                    value = await wcl.check_combo_presence(
                        report_code, source_map[name],
                        timerange["start"], timerange["end"],
                        combo,
                    )
                    c_data[combo["metric"]] = value

                for cons in consumables_profile:
                    metric = cons["metric"]
                    actual = c_data.get(metric, 0)
                    entry = {
                        "player_name": name,
                        "report_code": report_code,
                        "metric_name": metric,
                        "label": cons["label"],
                        "actual_value": actual,
                        "target_value": cons["target"],
                        "optional": cons.get("optional", False),
                    }
                    player_consumables.append(entry)
                    consumables_entries.append(entry)
            except Exception:
                logger.warning("Failed to fetch consumables for %s in %s", name, report_code)

        # Score
        consumables_data_dict = (
            {c["metric_name"]: c["actual_value"] for c in player_consumables}
            if player_consumables
            else None
        )
        overall = score_player(
            spec_profile or {"utility_weight": 0, "parse_weight": 1, "contributions": []},
            parse,
            utility_data,
            consumables_profile if consumables_profile else None,
            consumables_data_dict,
        )
        scores.append({
            "player_name": name,
            "report_code": report_code,
            "spec": spec_key or "unknown",
            "overall_score": overall,
            "parse_score": parse,
            "utility_score": None,
            "consumables_score": None,
        })

    # Per-boss rankings (for Parse God badge, etc.)
    for pf in per_fight_rankings:
        pf_name = pf["name"]
        if pf_name in player_specs:
            pf_spec = player_specs[pf_name].lower()
        else:
            pf_spec = "unknown"
        rankings.append({
            "player_name": pf_name,
            "spec": pf_spec,
            "rank_percent": pf["rankPercent"],
            "encounter_name": pf["encounter_name"],
        })

    gear = []
    for pg in gear_raw:
        for item in pg.get("gear", []):
            if not item or item.get("id", 0) == 0:
                continue
            gear.append({
                "player_name": pg["name"],
                "report_code": report_code,
                "slot": item.get("slot", 0),
                "item_id": item.get("id", 0),
                "item_level": item.get("itemLevel", 0),
                "quality": item.get("quality", 0),
                "permanent_enchant": item.get("permanentEnchant"),
                "gems": item.get("gems", []),
            })

    # Fetch fights, deaths, and per-fight stats
    fights = []
    deaths = []
    fight_stats = []

    try:
        fights_raw = await wcl.get_report_fights(report_code)
    except Exception:
        logger.warning("Failed to fetch fights for %s", report_code)
        fights_raw = []

    for f in fights_raw:
        if f.get("encounterID", 0) == 0:
            continue
        fight_entry = {
            "report_code": report_code,
            "fight_id": f["id"],
            "encounter_name": f.get("name", "Unknown"),
            "kill": f.get("kill", False),
            "duration_ms": int(f.get("endTime", 0) - f.get("startTime", 0)),
            "fight_percentage": f.get("fightPercentage", 0),
            "start_time": f.get("startTime", 0),
            "end_time": f.get("endTime", 0),
        }
        fights.append(fight_entry)

        # Fetch deaths for this fight
        try:
            death_entries = await wcl.get_report_deaths(report_code, f["startTime"], f["endTime"])
            # WCL Deaths table uses class name as "type" (e.g. "Warrior"),
            # not "Player". Exclude known non-player types instead.
            non_player = {"Pet", "NPC", "Boss", "Unknown"}
            for d in death_entries:
                if d.get("type") in non_player:
                    continue
                killing_ability = None
                damage_taken = None
                if d.get("damage", {}).get("entries"):
                    last_hit = d["damage"]["entries"][-1]
                    killing_ability = last_hit.get("ability", {}).get("name")
                    damage_taken = last_hit.get("amount")
                # deathTime is relative to report start; convert to fight-relative
                death_time = d.get("deathTime", 0) - f.get("startTime", 0)
                deaths.append({
                    "fight_id": f["id"],
                    "player_name": d["name"],
                    "timestamp_ms": max(death_time, 0),
                    "killing_ability": killing_ability,
                    "damage_taken": damage_taken,
                })
        except Exception as e:
            logger.warning("Failed to fetch deaths for fight %s in %s: %s", f["id"], report_code, e)

        # Fetch per-player stats for this fight
        try:
            stats = await wcl.get_fight_stats(report_code, f["startTime"], f["endTime"])
            for player_name, s in stats.items():
                player_deaths = sum(1 for d in deaths if d["fight_id"] == f["id"] and d["player_name"] == player_name)
                fight_stats.append({
                    "fight_id": f["id"],
                    "player_name": player_name,
                    "dps": s["dps"],
                    "hps": s["hps"],
                    "damage_done": s["damage_done"],
                    "healing_done": s["healing_done"],
                    "deaths_count": player_deaths,
                })
        except Exception as e:
            logger.warning("Failed to fetch stats for fight %s in %s: %s", f["id"], report_code, e)

    return {
        "rankings": rankings,
        "scores": scores,
        "gear": gear,
        "utility": utility_entries,
        "consumables": consumables_entries,
        "fights": fights,
        "deaths": deaths,
        "fight_stats": fight_stats,
    }
