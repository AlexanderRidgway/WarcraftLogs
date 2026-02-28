def score_player(
    spec_profile: dict,
    parse_percentile: float,
    utility_data: dict,
    consumables_profile: list | None = None,
    consumables_data: dict | None = None,
) -> float:
    """
    Compute a single-boss performance score for a player.

    Args:
        spec_profile: The class:spec config entry (weights + contributions list)
        parse_percentile: WarcraftLogs parse rank 0-100
        utility_data: Dict of metric_name -> actual value (uptime % or cast count)
        consumables_profile: Optional global consumables list from config
        consumables_data: Optional dict of consumable metric_name -> actual value

    Returns:
        Score from 0-100
    """
    utility_weight = spec_profile.get("utility_weight", 0.0)
    parse_weight = spec_profile.get("parse_weight", 1.0)
    consumables_weight = spec_profile.get("consumables_weight", 0.0)
    contributions = spec_profile.get("contributions", [])

    if not contributions:
        return float(parse_percentile)

    metric_scores = []
    for contrib in contributions:
        actual = utility_data.get(contrib["metric"], 0)
        target = contrib["target"]
        metric_score = min(actual / target, 1.0) * 100 if target > 0 else 0
        metric_scores.append(metric_score)

    utility_score = sum(metric_scores) / len(metric_scores)

    consumables_score = 0.0
    if consumables_weight > 0 and consumables_profile and consumables_data is not None:
        scored = [c for c in consumables_profile if not c.get("optional")]
        if scored:
            c_scores = []
            for contrib in scored:
                actual = consumables_data.get(contrib["metric"], 0)
                target = contrib.get("target", 1)
                c_score = min(actual / target, 1.0) * 100 if target > 0 else 0
                c_scores.append(c_score)
            consumables_score = sum(c_scores) / len(c_scores)

    return (
        (utility_score * utility_weight)
        + (parse_percentile * parse_weight)
        + (consumables_score * consumables_weight)
    )


def score_consistency(scores: list[float]) -> float:
    """Average a list of per-boss scores into a consistency score."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def aggregate_weekly_scores(report_scores: list[list[tuple]]) -> list[dict]:
    """
    Aggregate player scores across multiple reports.

    Args:
        report_scores: List of reports, each a list of (name, spec, score, parse) tuples.

    Returns:
        List of {name, spec, avg_score, avg_parse, fight_count} dicts, sorted by avg_score desc.
    """
    player_data: dict[str, dict] = {}
    for report in report_scores:
        for name, spec, score, parse in report:
            if name not in player_data:
                player_data[name] = {"spec": spec, "scores": [], "parses": []}
            player_data[name]["scores"].append(score)
            player_data[name]["parses"].append(parse)

    result = []
    for name, data in player_data.items():
        result.append({
            "name": name,
            "spec": data["spec"],
            "avg_score": sum(data["scores"]) / len(data["scores"]),
            "avg_parse": sum(data["parses"]) / len(data["parses"]),
            "fight_count": len(data["scores"]),
        })

    result.sort(key=lambda x: x["avg_score"], reverse=True)
    return result
