# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Matrix Bot Configuration — environment-based settings for Murphy Matrix integration.

Provides two configuration classes:

* :class:`MatrixConfig` — the original flat dataclass used by the v1 bot.
* :class:`MatrixBotConfig` — the enhanced dataclass with ``from_env()`` /
  ``from_yaml()`` classmethods used by :class:`~bots.matrix_bot.MurphyMatrixBot`.

All settings are read from environment variables.  No defaults embed
credentials; only interval / prefix / threshold values carry safe defaults.
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
    """Read a single environment variable, returning *default* if unset."""
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# v1 config dataclass (kept for backward compatibility)
# ---------------------------------------------------------------------------


@dataclass
class MatrixConfig:
    """Validated configuration for the Murphy Matrix bot (v1)."""

    # ------------------------------------------------------------------
    # Matrix homeserver / account
    # ------------------------------------------------------------------
    homeserver: str
    user_id: str
    password: Optional[str]
    access_token: Optional[str]

    # ------------------------------------------------------------------
    # Room IDs
    # ------------------------------------------------------------------
    default_room: str
    hitl_room: str
    alerts_room: str
    comms_room: str

    # ------------------------------------------------------------------
    # Murphy API
    # ------------------------------------------------------------------
    murphy_api_url: str
    murphy_api_key: str
    murphy_web_base_url: str

    # ------------------------------------------------------------------
    # Bot behaviour
    # ------------------------------------------------------------------
    command_prefix: str = "!murphy"

    # ------------------------------------------------------------------
    # Poll intervals (seconds)
    # ------------------------------------------------------------------
    health_poll_interval: int = 15
    hitl_poll_interval: int = 30
    status_poll_interval: int = 10
    comms_poll_interval: int = 20

    # ------------------------------------------------------------------
    # Email pass-through (consumed by EmailService.from_env())
    # These are kept here for documentation / validation purposes only;
    # the email integration reads them directly from os.environ.
    # ------------------------------------------------------------------
    sendgrid_api_key: Optional[str] = field(default=None, repr=False)
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = field(default=None, repr=False)
    smtp_password: Optional[str] = field(default=None, repr=False)
    smtp_use_tls: bool = True
    smtp_from_email: Optional[str] = None


def load_config() -> MatrixConfig:
    """Load and validate :class:`MatrixConfig` from environment variables.

    Raises
    ------
    ValueError
        When a required variable is missing or authentication info is absent.
    """

    def _require(name: str) -> str:
        val = os.environ.get(name, "").strip()
        if not val:
            raise ValueError(f"Required environment variable {name!r} is not set.")
        return val

    def _optional(name: str) -> Optional[str]:
        val = os.environ.get(name, "").strip()
        return val if val else None

    def _int(name: str, default: int) -> int:
        val = os.environ.get(name, "")
        try:
            return int(val) if val.strip() else default
        except ValueError:
            return default

    def _bool(name: str, default: bool) -> bool:
        val = os.environ.get(name, "").strip().lower()
        if val in ("1", "true", "yes"):
            return True
        if val in ("0", "false", "no"):
            return False
        return default

    homeserver = _require("MATRIX_HOMESERVER")
    user_id = _require("MATRIX_USER_ID")
    password = _optional("MATRIX_PASSWORD")
    access_token = _optional("MATRIX_ACCESS_TOKEN")

    if not password and not access_token:
        raise ValueError(
            "Either MATRIX_PASSWORD or MATRIX_ACCESS_TOKEN must be set."
        )

    default_room = _require("MATRIX_DEFAULT_ROOM")
    hitl_room = _require("MATRIX_HITL_ROOM")
    alerts_room = _require("MATRIX_ALERTS_ROOM")
    comms_room = _require("MATRIX_COMMS_ROOM")

    murphy_api_url = _require("MURPHY_API_URL").rstrip("/")
    murphy_api_key = _require("MURPHY_API_KEY")
    murphy_web_base_url = _require("MURPHY_WEB_BASE_URL").rstrip("/")

    smtp_port_raw = os.environ.get("SMTP_PORT", "").strip()
    smtp_port: Optional[int] = int(smtp_port_raw) if smtp_port_raw.isdigit() else None

    return MatrixConfig(
        homeserver=homeserver,
        user_id=user_id,
        password=password,
        access_token=access_token,
        default_room=default_room,
        hitl_room=hitl_room,
        alerts_room=alerts_room,
        comms_room=comms_room,
        murphy_api_url=murphy_api_url,
        murphy_api_key=murphy_api_key,
        murphy_web_base_url=murphy_web_base_url,
        command_prefix=os.environ.get("BOT_COMMAND_PREFIX", "!murphy").strip() or "!murphy",
        health_poll_interval=_int("HEALTH_POLL_INTERVAL", 15),
        hitl_poll_interval=_int("HITL_POLL_INTERVAL", 30),
        status_poll_interval=_int("STATUS_POLL_INTERVAL", 10),
        comms_poll_interval=_int("COMMS_POLL_INTERVAL", 20),
        sendgrid_api_key=_optional("SENDGRID_API_KEY"),
        smtp_host=_optional("SMTP_HOST"),
        smtp_port=smtp_port,
        smtp_user=_optional("SMTP_USER"),
        smtp_password=_optional("SMTP_PASSWORD"),
        smtp_use_tls=_bool("SMTP_USE_TLS", True),
        smtp_from_email=_optional("SMTP_FROM_EMAIL"),
    )


# ---------------------------------------------------------------------------
# v2 config dataclass (used by MurphyMatrixBot)
# ---------------------------------------------------------------------------


@dataclass
class MatrixBotConfig:
    """All configurable parameters for the Murphy Matrix bot (v2).

    Supports loading from environment variables via :meth:`from_env` or
    from a YAML file via :meth:`from_yaml`.
    """

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
        default_factory=lambda: int(
            os.environ.get("MATRIX_HITL_POLL_INTERVAL")
            or os.environ.get("HITL_POLL_INTERVAL")
            or "30"
        )
    )
    health_poll_interval: int = field(
        default_factory=lambda: int(
            os.environ.get("MATRIX_HEALTH_POLL_INTERVAL")
            or os.environ.get("HEALTH_POLL_INTERVAL")
            or "60"
        )
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
        """Load config from a YAML file, with env-var overrides on top.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            A :class:`MatrixBotConfig` populated from the file, with any
            environment variables taking precedence.
        """
        logger.info("Loading Matrix bot config from %s", path)
        data = _load_yaml(path)
        inst = cls()
        for key, value in data.items():
            if hasattr(inst, key):
                setattr(inst, key, value)
        # env-vars always win
        inst._apply_env()
        logger.info("Matrix bot config loaded (homeserver=%s, user=%s)", inst.homeserver, inst.user_id)
        return inst

    @classmethod
    def from_env(cls) -> "MatrixBotConfig":
        """Load config purely from environment variables.

        Returns:
            A :class:`MatrixBotConfig` populated from environment variables.
        """
        inst = cls()
        inst._apply_env()
        logger.info("Matrix bot config loaded from env (homeserver=%s, user=%s)", inst.homeserver, inst.user_id)
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

        int_mapping: dict[str, str] = {
            "MATRIX_HITL_POLL_INTERVAL": "hitl_poll_interval",
            "HITL_POLL_INTERVAL": "hitl_poll_interval",
            "MATRIX_HEALTH_POLL_INTERVAL": "health_poll_interval",
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
        """Return a list of validation errors (empty list means config is valid).

        Returns:
            List of error strings, empty if the config is valid.
        """
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

    def terminal_url(self, page: str) -> str:
        """Return the full URL for a Murphy terminal page.

        Args:
            page: Terminal page name (e.g. ``"dashboard"``).

        Returns:
            Full URL string.
        """
        base = self.murphy_web_url.rstrip("/")
        return f"{base}/ui/{page}"


__all__ = ["MatrixConfig", "load_config", "MatrixBotConfig"]
