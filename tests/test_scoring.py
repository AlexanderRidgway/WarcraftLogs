import pytest
from src.scoring.engine import score_player, score_consistency

PROT_WARRIOR_PROFILE = {
    "utility_weight": 0.75,
    "parse_weight": 0.25,
    "contributions": [
        {"metric": "sunder_armor_uptime", "type": "uptime", "target": 90},
        {"metric": "thunderclap_count", "type": "count", "target": 15},
    ],
}


def test_perfect_utility_and_parse():
    utility_data = {"sunder_armor_uptime": 95, "thunderclap_count": 20}
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=100, utility_data=utility_data)
    assert result == pytest.approx(100.0, abs=0.1)


def test_zero_utility():
    utility_data = {"sunder_armor_uptime": 0, "thunderclap_count": 0}
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=99, utility_data=utility_data)
    # 0 * 0.75 + 99 * 0.25 = 24.75
    assert result == pytest.approx(24.75, abs=0.1)


def test_partial_utility_capped_at_100():
    # Exceeding target should not exceed 100 per metric
    utility_data = {"sunder_armor_uptime": 200, "thunderclap_count": 100}
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=100, utility_data=utility_data)
    assert result == pytest.approx(100.0, abs=0.1)


def test_missing_utility_metric_scores_zero():
    utility_data = {"sunder_armor_uptime": 90}  # thunderclap_count missing
    result = score_player(PROT_WARRIOR_PROFILE, parse_percentile=50, utility_data=utility_data)
    # utility: (100 + 0) / 2 = 50; score: 50 * 0.75 + 50 * 0.25 = 50
    assert result == pytest.approx(50.0, abs=0.1)


def test_consistency_averages_scores():
    scores = [80.0, 90.0, 70.0]
    assert score_consistency(scores) == pytest.approx(80.0, abs=0.1)


def test_consistency_empty_returns_zero():
    assert score_consistency([]) == 0.0


def test_no_contributions_returns_parse():
    # parse_weight is intentionally ignored when contributions is empty —
    # the raw parse is the entire score regardless of configured weights
    no_utility_profile = {
        "utility_weight": 0.0,
        "parse_weight": 1.0,
        "contributions": [],
    }
    result = score_player(no_utility_profile, parse_percentile=75, utility_data={})
    assert result == pytest.approx(75.0, abs=0.1)


def test_no_contributions_ignores_parse_weight():
    # Same parse, different parse_weight — result must be identical (parse_weight ignored)
    profile_low_weight = {
        "utility_weight": 0.75,
        "parse_weight": 0.25,
        "contributions": [],
    }
    result = score_player(profile_low_weight, parse_percentile=75, utility_data={})
    assert result == pytest.approx(75.0, abs=0.1)


CONSUMABLES_PROFILE = [
    {"metric": "flask_uptime", "type": "uptime", "target": 100},
    {"metric": "drums_count", "type": "count", "target": 4, "optional": True},
    {"metric": "sapper_count", "type": "count", "target": 2, "optional": True},
]

PROFILE_WITH_CONSUMABLES = {
    "utility_weight": 0.50,
    "parse_weight": 0.40,
    "consumables_weight": 0.10,
    "contributions": [
        {"metric": "sunder_armor_uptime", "type": "uptime", "target": 90},
    ],
}


def test_consumables_weight_zero_ignores_consumables():
    """consumables_weight: 0.00 means consumables never affect the score."""
    profile = {**PROT_WARRIOR_PROFILE, "consumables_weight": 0.00}
    consumables_data = {"flask_uptime": 0}
    result = score_player(
        profile, 100.0, {"sunder_armor_uptime": 90, "thunderclap_count": 15},
        CONSUMABLES_PROFILE, consumables_data
    )
    # Same as no consumables: utility=100, parse=100 => 100*0.75 + 100*0.25 = 100
    assert result == pytest.approx(100.0, abs=0.1)


def test_consumables_scored_when_weight_nonzero():
    """consumables_weight > 0 adds consumables score to total."""
    consumables_data = {"flask_uptime": 100, "drums_count": 0, "sapper_count": 0}
    utility_data = {"sunder_armor_uptime": 90}
    result = score_player(
        PROFILE_WITH_CONSUMABLES, 80.0, utility_data,
        CONSUMABLES_PROFILE, consumables_data
    )
    # utility: 100*0.50=50; parse: 80*0.40=32; consumables: 100*0.10=10 => 92
    assert result == pytest.approx(92.0, abs=0.1)


def test_optional_metrics_not_included_in_consumables_score():
    """optional: true metrics are shown in display but excluded from scoring."""
    consumables_data = {"flask_uptime": 100, "drums_count": 0, "sapper_count": 0}
    utility_data = {"sunder_armor_uptime": 90}
    result = score_player(
        PROFILE_WITH_CONSUMABLES, 80.0, utility_data,
        CONSUMABLES_PROFILE, consumables_data
    )
    # drums and sapper are optional=True, so only flask_uptime (100) is scored
    # consumables_score = 100; total = 50 + 32 + 10 = 92
    assert result == pytest.approx(92.0, abs=0.1)


def test_all_consumables_optional_returns_zero_consumables_score():
    """If all consumables are optional, consumables_score is 0 even with weight."""
    all_optional = [
        {"metric": "drums_count", "type": "count", "target": 4, "optional": True},
    ]
    profile = {**PROFILE_WITH_CONSUMABLES}
    result = score_player(
        profile, 80.0, {"sunder_armor_uptime": 90},
        all_optional, {"drums_count": 4}
    )
    # consumables_score = 0 (all optional); utility=100*0.50=50; parse=80*0.40=32
    assert result == pytest.approx(82.0, abs=0.1)
