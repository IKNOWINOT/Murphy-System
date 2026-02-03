"""YAML configuration loader with profile support."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any
import os

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None


@dataclass
class AppConfig:
    logging: Dict[str, Any] = field(default_factory=lambda: {"level": "INFO"})
    scaling: Dict[str, Any] = field(default_factory=lambda: {"max_instances": 1})
    bots: Dict[str, bool] = field(default_factory=dict)
    memory_db: str = "memory.db"


def load_config(path: str = "config.yml", profile: str | None = None) -> AppConfig:
    """Load configuration from a YAML file with environment profiles."""
    if yaml is None:
        raise ImportError("PyYAML is required for configuration loading")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    prof_name = profile or os.environ.get("HIVEMIND_ENV", data.get("default", "development"))
    profiles = data.get("profiles", {})
    profile_data = profiles.get(prof_name, {})
    merged = {**profile_data, **{k: v for k, v in data.items() if k not in {"profiles", "default"}}}
    return AppConfig(**merged)
