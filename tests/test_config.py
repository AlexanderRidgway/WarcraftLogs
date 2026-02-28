import pytest
import yaml
from unittest.mock import patch, MagicMock
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


SAMPLE_CONFIG_WITH_GEAR_CHECK = {
    **SAMPLE_CONFIG,
    "gear_check": {
        "min_avg_ilvl": 100,
        "min_quality": 3,
        "check_enchants": True,
        "check_gems": True,
        "enchant_slots": [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15],
    },
}


@pytest.fixture
def config_file_with_gear_check(tmp_path):
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(SAMPLE_CONFIG_WITH_GEAR_CHECK, f)
    return str(path)


def test_get_gear_check_returns_config(config_file_with_gear_check):
    loader = ConfigLoader(config_file_with_gear_check)
    result = loader.get_gear_check()
    assert result["min_avg_ilvl"] == 100
    assert result["min_quality"] == 3
    assert result["check_enchants"] is True
    assert result["check_gems"] is True
    assert 0 in result["enchant_slots"]


def test_get_gear_check_missing_returns_defaults(config_file):
    loader = ConfigLoader(config_file)
    result = loader.get_gear_check()
    assert result["min_avg_ilvl"] == 100
    assert result["min_quality"] == 3
    assert result["check_enchants"] is True
    assert result["check_gems"] is True
    assert isinstance(result["enchant_slots"], list)


def test_all_specs_excludes_gear_check_key(config_file_with_gear_check):
    loader = ConfigLoader(config_file_with_gear_check)
    specs = loader.all_specs()
    assert "gear_check" not in specs
    assert "warrior:protection" in specs


def test_save_calls_sync_to_s3_when_bucket_set(config_file, monkeypatch):
    """_save() should call _sync_to_s3() when CONFIG_S3_BUCKET is set."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    loader = ConfigLoader(config_file)
    with patch.object(loader, "_sync_to_s3") as mock_sync:
        loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
        mock_sync.assert_called_once()


def test_save_skips_s3_when_no_bucket(config_file, monkeypatch):
    """_save() should not attempt S3 when CONFIG_S3_BUCKET is not set."""
    monkeypatch.delenv("CONFIG_S3_BUCKET", raising=False)
    loader = ConfigLoader(config_file)
    with patch.object(loader, "_sync_to_s3") as mock_sync:
        loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
        mock_sync.assert_not_called()


def test_init_calls_sync_from_s3_when_bucket_set(config_file, monkeypatch):
    """__init__ should attempt S3 download when CONFIG_S3_BUCKET is set."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    with patch("src.config.loader.ConfigLoader._sync_from_s3") as mock_sync:
        ConfigLoader(config_file)
        mock_sync.assert_called_once()


def test_init_skips_s3_when_no_bucket(config_file, monkeypatch):
    """__init__ should skip S3 when CONFIG_S3_BUCKET is not set."""
    monkeypatch.delenv("CONFIG_S3_BUCKET", raising=False)
    with patch("src.config.loader.ConfigLoader._sync_from_s3") as mock_sync:
        ConfigLoader(config_file)
        mock_sync.assert_not_called()


def test_sync_to_s3_uploads_file(config_file, monkeypatch):
    """_sync_to_s3() should upload config.yaml to the S3 bucket."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        loader = ConfigLoader(config_file)
        loader._sync_to_s3()
        mock_client.upload_file.assert_called_once_with(
            config_file, "my-bucket", "config.yaml"
        )


def test_sync_from_s3_downloads_file(config_file, monkeypatch):
    """_sync_from_s3() should download config.yaml from the S3 bucket."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        loader = ConfigLoader.__new__(ConfigLoader)
        loader._path = config_file
        loader._s3_bucket = "my-bucket"
        loader._sync_from_s3()
        mock_client.download_file.assert_called_once_with(
            "my-bucket", "config.yaml", config_file
        )


def test_sync_from_s3_graceful_on_error(config_file, monkeypatch):
    """_sync_from_s3() should not crash if S3 download fails (first deploy)."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    mock_client = MagicMock()
    from botocore.exceptions import ClientError
    mock_client.download_file.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject"
    )
    with patch("boto3.client", return_value=mock_client):
        loader = ConfigLoader.__new__(ConfigLoader)
        loader._path = config_file
        loader._s3_bucket = "my-bucket"
        # Should not raise
        loader._sync_from_s3()
