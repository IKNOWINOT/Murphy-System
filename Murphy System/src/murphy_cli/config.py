"""
Murphy CLI — Configuration manager
===================================

Persists API key, URL, and default preferences to ``~/.murphy/config.json``.
Loads from environment variables first, then config file, then defaults.

Module label: CLI-CONFIG-001

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post · License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults  (CLI-CONFIG-DEFAULTS-001)
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".murphy"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: Dict[str, Any] = {
    "api_url": "http://localhost:8000",
    "output": "text",
    "timeout": 30,
    "no_color": False,
    "verbose": False,
    "quiet": False,
    "non_interactive": False,
}


# ---------------------------------------------------------------------------
# Config class  (CLI-CONFIG-MGR-001)
# ---------------------------------------------------------------------------

class CLIConfig:
    """Read / write Murphy CLI configuration.  (CLI-CONFIG-MGR-001)"""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._path = config_path or CONFIG_FILE
        self._data: Dict[str, Any] = dict(DEFAULTS)
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        """Load config from disk if it exists.  (CLI-CONFIG-LOAD-001)"""
        if self._path.is_file():
            try:
                raw = self._path.read_text(encoding="utf-8")
                stored = json.loads(raw)
                if isinstance(stored, dict):
                    self._data.update(stored)
            except (json.JSONDecodeError, OSError) as exc:  # CLI-CONFIG-ERR-001
                logger.warning("CLI-CONFIG-ERR-001: Cannot read config %s: %s", self._path, exc)

    def save(self) -> None:
        """Persist current config to disk.  (CLI-CONFIG-SAVE-001)"""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:  # CLI-CONFIG-ERR-002
            logger.warning("CLI-CONFIG-ERR-002: Cannot write config %s: %s", self._path, exc)

    # -- accessors ----------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value.  Env vars override file values.  (CLI-CONFIG-GET-001)"""
        env_key = f"MURPHY_{key.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist.  (CLI-CONFIG-SET-001)"""
        self._data[key] = value
        self.save()

    def delete(self, key: str) -> bool:
        """Remove a config key and persist.  (CLI-CONFIG-DEL-001)"""
        if key in self._data:
            del self._data[key]
            self.save()
            return True
        return False

    def all(self) -> Dict[str, Any]:
        """Return a copy of all config values.  (CLI-CONFIG-ALL-001)"""
        return dict(self._data)

    # -- convenience --------------------------------------------------------

    @property
    def api_url(self) -> str:
        return str(self.get("api_url", DEFAULTS["api_url"]))

    @property
    def api_key(self) -> Optional[str]:
        return self.get("api_key") or os.environ.get("MURPHY_API_KEY")

    @property
    def output_format(self) -> str:
        return str(self.get("output", "text"))

    @property
    def timeout(self) -> int:
        try:
            return int(self.get("timeout", DEFAULTS["timeout"]))
        except (TypeError, ValueError):
            return DEFAULTS["timeout"]
