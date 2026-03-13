# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Matrix Bot Configuration — environment-based settings for Murphy Matrix integration.

All settings are read from environment variables.  No defaults embed credentials;
only interval / prefix / threshold values carry safe defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MatrixConfig:
    """Validated configuration for the Murphy Matrix bot."""

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


__all__ = ["MatrixConfig", "load_config"]
