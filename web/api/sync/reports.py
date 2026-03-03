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

# WCL sometimes returns non-standard spec names; map them to canonical names
WCL_SPEC_ALIASES: dict[str, str] = {
    "justicar": "protection",
    "guardian": "feral",
    "beastmastery": "beast mastery",
    "beast-mastery": "beast mastery",
    "warden": "protection",
    "gladiator": "protection",
}


def _validate_spec_key(cls: str, spec: str) -> str:
    """Build a spec_key, validating that the spec is valid for the class."""
    cls_lower = cls.lower()
    spec_lower = spec.lower()
    spec_lower = WCL_SPEC_ALIASES.get(spec_lower, spec_lower)
    valid = VALID_SPECS.get(cls_lower, set())
    if spec_lower in valid:
        return f"{cls_lower}:{spec_lower}"
    logger.warning("Invalid spec '%s' for class '%s', using class only", spec, cls)
    return cls_lower


def compute_relative_scores(
    casts_by_source: dict[int, int],
    source_to_player: dict[int, str],
    class_players: dict[str, list[str]],
    responsible_class: str,
    contrib: dict,
) -> dict[str, float]:
    """Compute peer-relative scores for a dispel/utility metric.

    Each player is scored on their share of total class-peer casts vs expected share.
    Score = min(player_share / expected_share, 1.0) * 100

    Args:
        casts_by_source: {source_id: cast_count} from get_raid_casts_by_source
        source_to_player: {source_id: player_name} for all players in the raid
        class_players: {class_name: [player_names]} grouping
        responsible_class: which class is responsible for this metric
        contrib: the contribution config entry

    Returns: {player_name: score} for all players of the responsible class
    """
    peers = class_players.get(responsible_class, [])
    if not peers:
        return {}

    # Map player names to their cast counts
    player_to_source = {}
    for sid, name in source_to_player.items():
        if name in peers:
            player_to_source[name] = sid

    # Sum total casts from class peers only
    total_casts = 0
    player_casts: dict[str, int] = {}
    for name in peers:
        sid = player_to_source.get(name)
        count = casts_by_source.get(sid, 0) if sid is not None else 0
        player_casts[name] = count
        total_casts += count

    if total_casts == 0:
        return {name: 0.0 for name in peers}

    expected_share = 1.0 / len(peers)
    result = {}
    for name in peers:
        player_share = player_casts[name] / total_casts
        ratio = player_share / expected_share
        result[name] = min(ratio, 1.0) * 100
    return result


async def fetch_new_reports(
    wcl: WarcraftLogsClient,
    guild_name: str,
    server_slug: str,
    region: str,
    days_back: int = 7,
    existing_codes: set[str] | None = None,
) -> list[dict]:
    """Fetch guild reports from WCL, filtering out already-synced ones.

    Deduplication is by report code only.  Different loggers may capture
    different bosses from the same raid night (e.g. one logs Gruul's Lair,
    another logs Magtheridon's Lair) so zone+time overlap cannot be used.
    """
    existing_codes = existing_codes or set()
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (days_back * 86400 * 1000)

    raw_reports = await wcl.get_guild_reports(guild_name, server_slug, region, start_ms, now_ms)

    new_reports = []
    for r in raw_reports:
        if r["code"] in existing_codes:
            continue
        start_time = datetime.utcfromtimestamp(r["startTime"] / 1000)
        zone_id = r["zone"]["id"]

        report = {
            "code": r["code"],
            "zone_id": zone_id,
            "zone_name": r["zone"]["name"],
            "start_time": start_time,
            "end_time": datetime.utcfromtimestamp((r["startTime"] + 3600000) / 1000),
            "player_names": r.get("players", []),
        }
        new_reports.append(report)

    logger.info("Found %d new reports (of %d total, %d already synced)",
                len(new_reports), len(raw_reports),
                len(raw_reports) - len(new_reports))
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
    source_to_player = {p["id"]: p["name"] for p in players_raw}
    consumables_profile = config.get_consumables()

    # Build class -> [player_names] mapping for relative/shared_responsibility metrics
    class_players: dict[str, list[str]] = {}
    for pname, spec_key_raw in player_specs.items():
        cls_name = spec_key_raw.split(":")[0].lower() if ":" in spec_key_raw else spec_key_raw.lower()
        class_players.setdefault(cls_name, []).append(pname)

    # Fetch fights early so we can use per-fight windows for utility
    try:
        fights_raw = await wcl.get_report_fights(report_code)
    except Exception:
        logger.warning("Failed to fetch fights for %s", report_code)
        fights_raw = []

    boss_fight_windows = []
    for f in fights_raw:
        if f.get("encounterID", 0) == 0:
            continue
        boss_fight_windows.append((f.get("startTime", 0), f.get("endTime", 0)))

    # Pre-compute relative and shared_responsibility metrics (once per metric, not per player)
    relative_cache: dict[str, dict[str, float]] = {}   # metric -> {player: score}
    shared_cache: dict[str, float] = {}                  # metric -> uptime%

    seen_metrics: set[str] = set()
    for player in rankings_raw:
        name = player["name"]
        if name in player_specs:
            sk = player_specs[name].lower()
        else:
            spec = player.get("spec", "")
            cls = player_classes.get(name, player.get("class", ""))
            sk = _validate_spec_key(cls, spec) if cls else None
        sp = config.get_spec(sk) if sk else None
        if not sp or not sp.get("contributions"):
            continue
        for c in sp["contributions"]:
            metric = c["metric"]
            if metric in seen_metrics:
                continue
            seen_metrics.add(metric)
            if c["type"] == "relative":
                resp_class = sk.split(":")[0] if sk and ":" in sk else ""
                try:
                    casts_data = await wcl.get_raid_casts_by_source(
                        report_code, timerange["start"], timerange["end"], c,
                    )
                    scores_rel = compute_relative_scores(
                        casts_data, source_to_player, class_players, resp_class, c,
                    )
                    relative_cache[metric] = scores_rel
                except Exception:
                    logger.warning("Failed relative metric %s in %s", metric, report_code)
            elif c["type"] == "shared_responsibility":
                resp_class = c.get("responsible_class", sk.split(":")[0] if sk and ":" in sk else "")
                if boss_fight_windows:
                    totals = []
                    for f_start, f_end in boss_fight_windows:
                        try:
                            uptime = await wcl.get_raid_buff_uptime(report_code, f_start, f_end, c)
                            totals.append(uptime)
                        except Exception:
                            pass
                    shared_cache[metric] = sum(totals) / len(totals) if totals else 0.0
                else:
                    try:
                        shared_cache[metric] = await wcl.get_raid_buff_uptime(
                            report_code, timerange["start"], timerange["end"], c,
                        )
                    except Exception:
                        logger.warning("Failed shared metric %s in %s", metric, report_code)
                        shared_cache[metric] = 0.0

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

        # Utility data — uptime/pull_check per boss fight (averaged), counts over full report
        utility_data = {}
        if spec_profile and spec_profile.get("contributions") and name in source_map:
            contribs = spec_profile["contributions"]
            # Only fetch individual metrics via get_utility_data (skip relative/shared_responsibility)
            individual_contribs = [c for c in contribs if c["type"] in ("uptime", "count", "pull_check")]
            uptime_contribs = [c for c in individual_contribs if c["type"] == "uptime"]
            count_contribs = [c for c in individual_contribs if c["type"] == "count"]
            pull_check_contribs = [c for c in individual_contribs if c["type"] == "pull_check"]

            # Per-fight metrics (uptime + pull_check): calculate per boss fight and average
            per_fight_contribs = uptime_contribs + pull_check_contribs
            if per_fight_contribs and boss_fight_windows:
                per_metric_totals: dict[str, float] = {}
                per_metric_counts: dict[str, int] = {}
                for f_start, f_end in boss_fight_windows:
                    try:
                        fight_data = await wcl.get_utility_data(
                            report_code, source_map[name],
                            f_start, f_end, per_fight_contribs,
                        )
                        for metric, value in fight_data.items():
                            per_metric_totals[metric] = per_metric_totals.get(metric, 0) + value
                            per_metric_counts[metric] = per_metric_counts.get(metric, 0) + 1
                    except Exception:
                        pass
                for metric in per_metric_totals:
                    if per_metric_counts.get(metric, 0) > 0:
                        utility_data[metric] = per_metric_totals[metric] / per_metric_counts[metric]
            elif uptime_contribs:
                # No boss fights found — fall back to full report (uptime only)
                try:
                    utility_data = await wcl.get_utility_data(
                        report_code, source_map[name],
                        timerange["start"], timerange["end"], uptime_contribs,
                    )
                except Exception:
                    logger.warning("Failed to fetch utility for %s in %s", name, report_code)

            # Count metrics: use full report timerange (counts accumulate over whole raid)
            if count_contribs:
                try:
                    count_data = await wcl.get_utility_data(
                        report_code, source_map[name],
                        timerange["start"], timerange["end"], count_contribs,
                    )
                    utility_data.update(count_data)
                except Exception:
                    logger.warning("Failed to fetch count utility for %s in %s", name, report_code)

            for contrib in spec_profile.get("contributions", []):
                metric = contrib["metric"]
                target = contrib["target"]

                if contrib["type"] == "relative":
                    # Use pre-computed relative scores
                    rel_scores = relative_cache.get(metric, {})
                    actual = rel_scores.get(name, 0.0)
                elif contrib["type"] == "shared_responsibility":
                    # Use pre-computed shared uptime
                    actual = shared_cache.get(metric, 0.0)
                else:
                    # Individual metrics (uptime, count, pull_check) — from utility_data
                    actual = utility_data.get(metric, 0)

                # Also add to utility_data for score_player
                utility_data[metric] = actual

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

    # Process fights for deaths and per-fight stats (fights_raw fetched above)
    fights = []
    deaths = []
    fight_stats = []

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
                damage_info = d.get("damage") or {}
                entries = damage_info.get("entries") or []
                if entries:
                    last_hit = entries[-1]
                    killing_ability = last_hit.get("ability", {}).get("name")
                    damage_taken = last_hit.get("amount")
                if not killing_ability:
                    # Fallback: use total damage if available
                    damage_taken = damage_taken or damage_info.get("total")
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
