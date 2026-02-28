import yaml
from typing import Optional


class ConfigLoader:
    def __init__(self, path: str = "config.yaml"):
        self._path = path
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

    def all_specs(self) -> list[str]:
        """Return all configured spec keys, excluding non-spec top-level keys."""
        return [k for k in self._data.keys() if k not in ("consumables", "attendance")]

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

    def _save(self) -> None:
        with open(self._path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)
