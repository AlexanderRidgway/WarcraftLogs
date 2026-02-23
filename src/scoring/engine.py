def score_player(spec_profile: dict, parse_percentile: float, utility_data: dict) -> float:
    """
    Compute a single-boss performance score for a player.

    Args:
        spec_profile: The class:spec config entry (weights + contributions list)
        parse_percentile: WarcraftLogs parse rank 0-100
        utility_data: Dict of metric_name -> actual value (uptime % or cast count)

    Returns:
        Score from 0-100
    """
    utility_weight = spec_profile["utility_weight"]
    parse_weight = spec_profile["parse_weight"]
    contributions = spec_profile["contributions"]

    if not contributions:
        return parse_percentile * parse_weight

    metric_scores = []
    for contrib in contributions:
        actual = utility_data.get(contrib["metric"], 0)
        target = contrib["target"]
        metric_score = min(actual / target, 1.0) * 100 if target > 0 else 0
        metric_scores.append(metric_score)

    utility_score = sum(metric_scores) / len(metric_scores)
    if utility_score >= 100.0:
        return 100.0
    return (utility_score * utility_weight) + (parse_percentile * parse_weight)


def score_consistency(scores: list[float]) -> float:
    """Average a list of per-boss scores into a consistency score."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
