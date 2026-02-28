import logging
import os

import yaml
from typing import Optional

logger = logging.getLogger(__name__)

_GEAR_CHECK_DEFAULTS = {
    "min_avg_ilvl": 100,
    "min_quality": 3,
    "check_enchants": True,
    "check_gems": True,
    "enchant_slots": [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15],
}


class ConfigLoader:
    def __init__(self, path: str = "config.yaml"):
        self._path = path
        self._s3_bucket = os.environ.get("CONFIG_S3_BUCKET")
        if self._s3_bucket:
            self._sync_from_s3()
        self._data = self._load()

    def _load(self) -> dict:
        with open(self._path, "r") as f:
            return yaml.safe_load(f) or {}

    def get_spec(self, spec_key: str) -> Optional[dict]:
        """Return the profile for a class:spec key, or None if not configured."""
        return self._data.get(spec_key)

    def get_consumables(self) -> list:
        """Return the global consumables list, or empty list if not configured."""
        return self._data.get("consumables", [])

    def get_attendance(self) -> list:
        """Return the attendance requirements list, or empty list if not configured."""
        return self._data.get("attendance", [])

    def get_gear_check(self) -> dict:
        """Return the gear check config, or defaults if not configured."""
        config = self._data.get("gear_check")
        if config is None:
            return dict(_GEAR_CHECK_DEFAULTS)
        return {**_GEAR_CHECK_DEFAULTS, **config}

    def all_specs(self) -> list[str]:
        """Return all configured spec keys, excluding non-spec top-level keys."""
        return [k for k in self._data.keys() if k not in ("consumables", "attendance", "gear_check")]

    def update_target(self, spec_key: str, metric: str, new_target: int) -> None:
        """Update the target for a metric in a spec profile and persist to disk."""
        profile = self._data.get(spec_key)
        if profile is None:
            raise ValueError(f"Spec '{spec_key}' not found in config")

        for contrib in profile["contributions"]:
            if contrib["metric"] == metric:
                contrib["target"] = new_target
                self._save()
                return

        raise ValueError(f"metric '{metric}' not found in spec '{spec_key}'")

    def add_attendance_zone(self, zone_id: int, label: str, required_per_week: int) -> None:
        """Add a new zone to attendance requirements and persist to disk."""
        attendance = self._data.setdefault("attendance", [])
        if any(e["zone_id"] == zone_id for e in attendance):
            raise ValueError(f"Zone {zone_id} already exists in attendance config")
        attendance.append({
            "zone_id": zone_id,
            "label": label,
            "required_per_week": required_per_week,
        })
        self._save()

    def remove_attendance_zone(self, zone_id: int) -> None:
        """Remove a zone from attendance requirements and persist to disk."""
        attendance = self._data.get("attendance", [])
        original_len = len(attendance)
        self._data["attendance"] = [e for e in attendance if e["zone_id"] != zone_id]
        if len(self._data["attendance"]) == original_len:
            raise ValueError(f"Zone {zone_id} not found in attendance config")
        self._save()

    def update_attendance_zone(self, zone_id: int, required_per_week: int) -> None:
        """Update the required_per_week for a zone and persist to disk."""
        attendance = self._data.get("attendance", [])
        for entry in attendance:
            if entry["zone_id"] == zone_id:
                entry["required_per_week"] = required_per_week
                self._save()
                return
        raise ValueError(f"Zone {zone_id} not found in attendance config")

    def _save(self) -> None:
        with open(self._path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)
        if self._s3_bucket:
            self._sync_to_s3()

    def _sync_to_s3(self) -> None:
        """Upload config.yaml to S3 bucket for persistence across deploys."""
        try:
            import boto3
            s3 = boto3.client("s3")
            s3.upload_file(self._path, self._s3_bucket, "config.yaml")
            logger.info("Uploaded config to s3://%s/config.yaml", self._s3_bucket)
        except Exception:
            logger.warning("Failed to upload config to S3", exc_info=True)

    def _sync_from_s3(self) -> None:
        """Download config.yaml from S3 bucket (graceful if missing)."""
        try:
            import boto3
            s3 = boto3.client("s3")
            s3.download_file(self._s3_bucket, "config.yaml", self._path)
            logger.info("Downloaded config from s3://%s/config.yaml", self._s3_bucket)
        except Exception:
            logger.info("No config found in S3 (first deploy?), using local file", exc_info=True)
