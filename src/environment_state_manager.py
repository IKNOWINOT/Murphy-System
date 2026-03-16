"""
Environment State Manager — Murphy System

Manages the ``~/.murphy/`` directory on the user's computer, persisting
a working snapshot of the environment so that subsequent launches can skip
the full probe and just validate the saved state.

Directory layout::

    ~/.murphy/
    ├── user_profile.json       — who they are (from signup)
    ├── environment_state.json  — frozen snapshot of working env config
    ├── shadow_agent.json       — their shadow agent config
    ├── terminal_config.json    — which UI features they see
    ├── setup_audit_log.json    — every setup action taken, with approvals
    └── .env                    — their specific environment variables

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MURPHY_HOME = os.path.join(os.path.expanduser("~"), ".murphy")

_FILE_USER_PROFILE = "user_profile.json"
_FILE_ENV_STATE = "environment_state.json"
_FILE_SHADOW_AGENT = "shadow_agent.json"
_FILE_TERMINAL_CONFIG = "terminal_config.json"
_FILE_SETUP_AUDIT_LOG = "setup_audit_log.json"
_FILE_ENV = ".env"

_STATE_VERSION = "1"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class EnvironmentState:
    """Frozen snapshot of a verified working environment configuration."""

    state_version: str = _STATE_VERSION
    user_id: str = ""
    org_id: str = ""
    python_version: str = ""
    venv_path: str = ""
    murphy_home: str = MURPHY_HOME
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    playwright_installed: bool = False
    env_vars: Dict[str, str] = field(default_factory=dict)
    valid: bool = True
    saved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    invalidated_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state_version": self.state_version,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "python_version": self.python_version,
            "venv_path": self.venv_path,
            "murphy_home": self.murphy_home,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "playwright_installed": self.playwright_installed,
            "env_vars": self.env_vars,
            "valid": self.valid,
            "saved_at": self.saved_at,
            "invalidated_reason": self.invalidated_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentState":
        state = cls()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state


# ---------------------------------------------------------------------------
# EnvironmentStateManager
# ---------------------------------------------------------------------------


class StateError(Exception):
    """Raised when a state operation fails."""


class EnvironmentStateManager:
    """Manages the ``~/.murphy/`` directory for persisting environment state.

    All public methods are thread-safe.

    Usage::

        mgr = EnvironmentStateManager()
        state = EnvironmentState(user_id="abc", python_version="3.11.0")
        mgr.save_state(state)

        loaded = mgr.load_state()
        assert loaded.user_id == "abc"

        assert mgr.validate_state() is True
        mgr.invalidate_state("OS upgraded")
    """

    def __init__(self, home_dir: Optional[str] = None) -> None:
        self._home = home_dir or MURPHY_HOME
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    def _ensure_home(self) -> None:
        os.makedirs(self._home, exist_ok=True)

    def _path(self, filename: str) -> str:
        return os.path.join(self._home, filename)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def save_state(self, state: EnvironmentState) -> None:
        """Snapshot the current working configuration to disk."""
        self._ensure_home()
        with self._lock:
            self._write_json(_FILE_ENV_STATE, state.to_dict())
        logger.info("Environment state saved to %s", self._path(_FILE_ENV_STATE))

    def load_state(self) -> Optional[EnvironmentState]:
        """Read the saved environment state, or None if not found."""
        with self._lock:
            data = self._read_json(_FILE_ENV_STATE)
        if data is None:
            return None
        return EnvironmentState.from_dict(data)

    def validate_state(self) -> bool:
        """Quick health check: is the saved state still valid?

        Checks:
          - State file exists and is parsable
          - ``valid`` flag is True
          - Python version still matches
          - venv path still exists (if configured)
        """
        state = self.load_state()
        if state is None:
            return False
        if not state.valid:
            return False

        import sys

        current_python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if state.python_version and state.python_version != current_python:
            logger.warning(
                "Python version changed: saved=%s current=%s",
                state.python_version,
                current_python,
            )
            return False

        if state.venv_path and not os.path.isdir(state.venv_path):
            logger.warning("venv no longer exists at %s", state.venv_path)
            return False

        return True

    def invalidate_state(self, reason: str = "") -> None:
        """Mark the saved state as invalid so the next launch triggers re-probe."""
        state = self.load_state()
        if state is None:
            return
        state.valid = False
        state.invalidated_reason = reason
        self.save_state(state)
        logger.info("Environment state invalidated: %s", reason)

    # ------------------------------------------------------------------
    # User profile
    # ------------------------------------------------------------------

    def save_user_profile(self, profile: Dict[str, Any]) -> None:
        self._ensure_home()
        with self._lock:
            self._write_json(_FILE_USER_PROFILE, profile)

    def load_user_profile(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read_json(_FILE_USER_PROFILE)

    # ------------------------------------------------------------------
    # Shadow agent
    # ------------------------------------------------------------------

    def save_shadow_agent(self, config: Dict[str, Any]) -> None:
        self._ensure_home()
        with self._lock:
            self._write_json(_FILE_SHADOW_AGENT, config)

    def load_shadow_agent(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read_json(_FILE_SHADOW_AGENT)

    # ------------------------------------------------------------------
    # Terminal config
    # ------------------------------------------------------------------

    def save_terminal_config(self, config: Dict[str, Any]) -> None:
        self._ensure_home()
        with self._lock:
            self._write_json(_FILE_TERMINAL_CONFIG, config)

    def load_terminal_config(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read_json(_FILE_TERMINAL_CONFIG)

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def append_audit_entry(self, entry: Dict[str, Any]) -> None:
        """Append a single entry to the setup audit log on disk."""
        self._ensure_home()
        with self._lock:
            existing = self._read_json(_FILE_SETUP_AUDIT_LOG) or []
            if not isinstance(existing, list):
                existing = []
            existing.append(entry)
            self._write_json(_FILE_SETUP_AUDIT_LOG, existing)

    def load_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read_json(_FILE_SETUP_AUDIT_LOG)
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # .env file
    # ------------------------------------------------------------------

    def save_env_vars(self, env_vars: Dict[str, str]) -> None:
        """Write a ``~/.murphy/.env`` file from a dict."""
        self._ensure_home()
        lines = [f"{k}={v}" for k, v in env_vars.items()]
        env_path = self._path(_FILE_ENV)
        with self._lock:
            with open(env_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        logger.info("Env vars saved to %s", env_path)

    def load_env_vars(self) -> Dict[str, str]:
        """Read ``~/.murphy/.env`` into a dict."""
        env_path = self._path(_FILE_ENV)
        result: Dict[str, str] = {}
        if not os.path.isfile(env_path):
            return result
        with self._lock:
            with open(env_path, "r", encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip()
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_json(self, filename: str, data: Any) -> None:
        path = self._path(filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)

    def _read_json(self, filename: str) -> Optional[Any]:
        path = self._path(filename)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None

    def home_dir(self) -> str:
        """Return the ~/.murphy directory path used by this manager."""
        return self._home
