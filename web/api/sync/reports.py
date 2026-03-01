import logging
import time
from datetime import datetime, timezone

from src.api.warcraftlogs import WarcraftLogsClient
from src.config.loader import ConfigLoader
from src.scoring.engine import score_player

logger = logging.getLogger(__name__)


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
            "start_time": datetime.fromtimestamp(r["startTime"] / 1000, tz=timezone.utc),
            "end_time": datetime.fromtimestamp(
                (r["startTime"] + 3600000) / 1000, tz=timezone.utc
            ),
            "player_names": r.get("players", []),
        })

    logger.info("Found %d new reports (of %d total)", len(new_reports), len(raw_reports))
    return new_reports


async def process_report(
    wcl: WarcraftLogsClient,
    report_code: str,
    config: ConfigLoader,
) -> dict:
    """Process a single report: fetch rankings, gear, utility, consumables."""
    rankings_raw = await wcl.get_report_rankings(report_code)
    players_raw = await wcl.get_report_players(report_code)
    timerange = await wcl.get_report_timerange(report_code)
    gear_raw = await wcl.get_report_gear(report_code)

    source_map = {p["name"]: p["id"] for p in players_raw}
    consumables_profile = config.get_consumables()

    rankings = []
    scores = []
    utility_entries = []
    consumables_entries = []

    for player in rankings_raw:
        name = player["name"]
        spec = player.get("spec", "")
        cls = player.get("class", "")
        parse = player.get("rankPercent", 0)
        spec_key = f"{cls.lower()}:{spec.lower()}" if cls and spec else None
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
                c_data = await wcl.get_utility_data(
                    report_code, source_map[name],
                    timerange["start"], timerange["end"],
                    consumables_profile,
                )
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

    return {
        "rankings": rankings,
        "scores": scores,
        "gear": gear,
        "utility": utility_entries,
        "consumables": consumables_entries,
    }
