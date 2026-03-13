"""Configuration for the Murphy Matrix bot integration.

Reads settings from environment variables with optional YAML override.
All settings have sensible defaults so the bot starts without any configuration.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML loader (optional — falls back gracefully if pyyaml not installed)
# ---------------------------------------------------------------------------
try:
    import yaml as _yaml

    def _load_yaml(path: str) -> dict:
        with open(path) as fh:
            return _yaml.safe_load(fh) or {}
except ImportError:  # pragma: no cover
    def _load_yaml(path: str) -> dict:  # type: ignore[misc]
        logger.warning("pyyaml not installed — skipping YAML config at %s", path)
        return {}


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass
class MatrixBotConfig:
    """All configurable parameters for the Murphy Matrix bot."""

    # ------------------------------------------------------------------ Matrix
    homeserver: str = field(
        default_factory=lambda: _env("MATRIX_HOMESERVER", "http://localhost:8008")
    )
    user_id: str = field(
        default_factory=lambda: _env("MATRIX_USER_ID", "@murphy:localhost")
    )
    password: str = field(
        default_factory=lambda: _env("MATRIX_PASSWORD", "")
    )
    access_token: str = field(
        default_factory=lambda: _env("MATRIX_ACCESS_TOKEN", "")
    )

    # ------------------------------------------------------------------ Murphy
    murphy_api_url: str = field(
        default_factory=lambda: _env("MURPHY_API_URL", "http://localhost:8000/api")
    )
    murphy_web_url: str = field(
        default_factory=lambda: _env("MURPHY_WEB_URL", "http://localhost:8000")
    )

    # ------------------------------------------------------------------ Rooms
    hitl_room: str = field(
        default_factory=lambda: _env("MATRIX_HITL_ROOM", "")
    )
    alerts_room: str = field(
        default_factory=lambda: _env("MATRIX_ALERTS_ROOM", "")
    )

    # ------------------------------------------------------------------ Polling
    hitl_poll_interval: int = field(
        default_factory=lambda: int(_env("HITL_POLL_INTERVAL", "30"))
    )
    health_poll_interval: int = field(
        default_factory=lambda: int(_env("HEALTH_POLL_INTERVAL", "15"))
    )

    # ------------------------------------------------------------------ Circuit breaker
    circuit_breaker_threshold: int = field(
        default_factory=lambda: int(_env("CIRCUIT_BREAKER_THRESHOLD", "5"))
    )
    circuit_breaker_timeout: int = field(
        default_factory=lambda: int(_env("CIRCUIT_BREAKER_TIMEOUT", "60"))
    )

    # ------------------------------------------------------------------ HTTP
    api_timeout: float = field(
        default_factory=lambda: float(_env("MURPHY_API_TIMEOUT", "30.0"))
    )

    @classmethod
    def from_yaml(cls, path: str) -> "MatrixBotConfig":
        """Load config from a YAML file, with env-var overrides on top."""
        data = _load_yaml(path)
        inst = cls()
        for key, value in data.items():
            if hasattr(inst, key):
                setattr(inst, key, value)
        # env-vars always win
        inst._apply_env()
        return inst

    @classmethod
    def from_env(cls) -> "MatrixBotConfig":
        """Load config purely from environment variables."""
        inst = cls()
        inst._apply_env()
        return inst

    def _apply_env(self) -> None:
        """Re-read env vars so they override any YAML values."""
        mapping = {
            "MATRIX_HOMESERVER": "homeserver",
            "MATRIX_USER_ID": "user_id",
            "MATRIX_PASSWORD": "password",
            "MATRIX_ACCESS_TOKEN": "access_token",
            "MURPHY_API_URL": "murphy_api_url",
            "MURPHY_WEB_URL": "murphy_web_url",
            "MATRIX_HITL_ROOM": "hitl_room",
            "MATRIX_ALERTS_ROOM": "alerts_room",
        }
        for env_key, attr in mapping.items():
            val = os.environ.get(env_key)
            if val is not None:
                setattr(self, attr, val)

        int_mapping = {
            "HITL_POLL_INTERVAL": "hitl_poll_interval",
            "HEALTH_POLL_INTERVAL": "health_poll_interval",
            "CIRCUIT_BREAKER_THRESHOLD": "circuit_breaker_threshold",
            "CIRCUIT_BREAKER_TIMEOUT": "circuit_breaker_timeout",
        }
        for env_key, attr in int_mapping.items():
            val = os.environ.get(env_key)
            if val is not None:
                try:
                    setattr(self, attr, int(val))
                except ValueError:
                    logger.warning("Invalid int for %s: %s", env_key, val)

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty = valid)."""
        errors: list[str] = []
        if not self.homeserver:
            errors.append("MATRIX_HOMESERVER is required")
        if not self.user_id:
            errors.append("MATRIX_USER_ID is required")
        if not self.password and not self.access_token:
            errors.append("Either MATRIX_PASSWORD or MATRIX_ACCESS_TOKEN is required")
        if not self.murphy_api_url:
            errors.append("MURPHY_API_URL is required")
        return errors

    # Terminal page URL helpers
    def terminal_url(self, page: str) -> str:
        base = self.murphy_web_url.rstrip("/")
        return f"{base}/ui/{page}"
