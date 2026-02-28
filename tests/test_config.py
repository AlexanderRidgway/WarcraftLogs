import pytest
import yaml
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


SAMPLE_CONFIG_WITH_CONSUMABLES = {
    **SAMPLE_CONFIG,
    "consumables": [
        {
            "metric": "flask_uptime",
            "label": "Flask",
            "spell_ids": [17628, 28520],
            "type": "uptime",
            "subtype": "buff",
            "target": 100,
        }
    ],
}


@pytest.fixture
def config_file_with_consumables(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG_WITH_CONSUMABLES, f)
    return str(path)


def test_get_consumables_returns_list(config_file_with_consumables):
    loader = ConfigLoader(config_file_with_consumables)
    result = loader.get_consumables()
    assert len(result) == 1
    assert result[0]["metric"] == "flask_uptime"


def test_get_consumables_missing_returns_empty(config_file):
    loader = ConfigLoader(config_file)
    assert loader.get_consumables() == []


def test_all_specs_excludes_consumables_key(config_file_with_consumables):
    loader = ConfigLoader(config_file_with_consumables)
    specs = loader.all_specs()
    assert "consumables" not in specs
    assert "warrior:protection" in specs


SAMPLE_CONFIG_WITH_ATTENDANCE = {
    **SAMPLE_CONFIG,
    "attendance": [
        {"zone_id": 1002, "label": "Karazhan", "required_per_week": 1},
        {"zone_id": 1004, "label": "Gruul's Lair", "required_per_week": 1},
    ],
}


@pytest.fixture
def config_file_with_attendance(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG_WITH_ATTENDANCE, f)
    return str(path)


def test_get_attendance_returns_list(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    result = loader.get_attendance()
    assert len(result) == 2
    assert result[0]["zone_id"] == 1002
    assert result[0]["label"] == "Karazhan"
    assert result[0]["required_per_week"] == 1


def test_get_attendance_missing_returns_empty(config_file):
    loader = ConfigLoader(config_file)
    assert loader.get_attendance() == []


def test_all_specs_excludes_attendance_key(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    specs = loader.all_specs()
    assert "attendance" not in specs
    assert "warrior:protection" in specs


def test_add_attendance_zone(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.add_attendance_zone(1005, "Magtheridon's Lair", 1)
    result = loader.get_attendance()
    assert len(result) == 3
    assert result[2]["zone_id"] == 1005


def test_add_attendance_zone_duplicate_raises(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    with pytest.raises(ValueError, match="already exists"):
        loader.add_attendance_zone(1002, "Karazhan", 1)


def test_remove_attendance_zone(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.remove_attendance_zone(1002)
    result = loader.get_attendance()
    assert len(result) == 1
    assert result[0]["zone_id"] == 1004


def test_remove_attendance_zone_not_found_raises(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    with pytest.raises(ValueError, match="not found"):
        loader.remove_attendance_zone(9999)


def test_update_attendance_zone(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.update_attendance_zone(1002, 2)
    result = loader.get_attendance()
    entry = next(e for e in result if e["zone_id"] == 1002)
    assert entry["required_per_week"] == 2


def test_update_attendance_zone_not_found_raises(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    with pytest.raises(ValueError, match="not found"):
        loader.update_attendance_zone(9999, 2)


def test_add_attendance_zone_persists(config_file_with_attendance):
    loader = ConfigLoader(config_file_with_attendance)
    loader.add_attendance_zone(1005, "Magtheridon's Lair", 1)
    loader2 = ConfigLoader(config_file_with_attendance)
    assert len(loader2.get_attendance()) == 3
