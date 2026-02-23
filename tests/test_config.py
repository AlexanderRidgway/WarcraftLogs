import pytest
import yaml
import os
from src.config.loader import ConfigLoader

SAMPLE_CONFIG = {
    "warrior:protection": {
        "utility_weight": 0.75,
        "parse_weight": 0.25,
        "contributions": [
            {
                "metric": "sunder_armor_uptime",
                "label": "Sunder Armor",
                "spell_id": 7386,
                "type": "uptime",
                "target": 90,
            }
        ],
    }
}


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG, f)
    return str(path)


def test_load_spec_profile(config_file):
    loader = ConfigLoader(config_file)
    profile = loader.get_spec("warrior:protection")
    assert profile["utility_weight"] == 0.75
    assert profile["parse_weight"] == 0.25
    assert len(profile["contributions"]) == 1


def test_get_unknown_spec_returns_none(config_file):
    loader = ConfigLoader(config_file)
    assert loader.get_spec("paladin:holy") is None


def test_update_target(config_file):
    loader = ConfigLoader(config_file)
    loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
    profile = loader.get_spec("warrior:protection")
    contrib = profile["contributions"][0]
    assert contrib["target"] == 95


def test_update_target_persists(config_file):
    loader = ConfigLoader(config_file)
    loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
    # Reload from disk
    loader2 = ConfigLoader(config_file)
    profile = loader2.get_spec("warrior:protection")
    assert profile["contributions"][0]["target"] == 95


def test_update_target_unknown_metric_raises(config_file):
    loader = ConfigLoader(config_file)
    with pytest.raises(ValueError, match="metric"):
        loader.update_target("warrior:protection", "nonexistent_metric", 50)


def test_all_specs(config_file):
    loader = ConfigLoader(config_file)
    specs = loader.all_specs()
    assert "warrior:protection" in specs
