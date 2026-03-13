# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Matrix Bridge Configuration — MTX-CFG-001

Owner: Platform Engineering

Configuration dataclasses and loader for the Matrix communication bridge.
All sensitive values (access tokens, passwords) are sourced from environment
variables; nothing is hard-coded.  Encryption support is optional and
controlled via :attr:`MatrixConfig.encryption_enabled`.

Classes
-------
MatrixConfig
    Top-level configuration loaded from environment / supplied dict.
RoomMappingConfig
    A single subsystem-to-room mapping entry.
MatrixBridgeSettings
    Combined settings container used throughout the bridge.

Usage::

    cfg = MatrixConfig.from_env()
    print(cfg.homeserver_url)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_DEFAULT_HOMESERVER = "https://matrix.org"
_DEFAULT_DEVICE_NAME = "MurphySystemBridge"
_DEFAULT_STORE_PATH = "/tmp/murphy_matrix_store"  # noqa: S108


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RoomMappingConfig:
    """Maps a Murphy subsystem name to a Matrix room alias."""

    subsystem_name: str
    room_alias: str
    space_alias: str
    description: str = ""
    read_only: bool = False


@dataclass
class MatrixConfig:
    """Core Matrix bridge configuration.

    Attributes
    ----------
    homeserver_url:
        Full URL of the Matrix homeserver, e.g. ``https://matrix.example.com``.
    user_id:
        Fully-qualified Matrix user ID, e.g. ``@murphy:matrix.example.com``.
    access_token:
        Bearer token used to authenticate API calls.  Never log this value.
    device_name:
        Logical name for this bridge device.
    store_path:
        Local filesystem path for the matrix-nio session/E2E store.
    encryption_enabled:
        Whether to enable end-to-end encryption for rooms that support it.
    room_mappings:
        Per-subsystem room mapping overrides (merged with topology defaults).
    max_retries:
        Number of times to retry a failed Matrix API call.
    retry_delay_seconds:
        Base delay between retries (exponential back-off is applied).
    """

    homeserver_url: str = _DEFAULT_HOMESERVER
    user_id: str = ""
    access_token: str = field(default="", repr=False)
    device_name: str = _DEFAULT_DEVICE_NAME
    store_path: str = _DEFAULT_STORE_PATH
    encryption_enabled: bool = False
    room_mappings: List[RoomMappingConfig] = field(default_factory=list)
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # -----------------------------------------------------------------------
    # Factory
    # -----------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "MatrixConfig":
        """Build a :class:`MatrixConfig` from environment variables.

        Environment variables
        ---------------------
        MATRIX_HOMESERVER_URL   : Homeserver URL (default: https://matrix.org)
        MATRIX_USER_ID          : Fully-qualified Matrix user ID
        MATRIX_ACCESS_TOKEN     : Bearer access token  *(required)*
        MATRIX_DEVICE_NAME      : Logical device name
        MATRIX_STORE_PATH       : Local E2E store path
        MATRIX_ENCRYPTION       : ``"true"`` to enable E2E encryption
        MATRIX_MAX_RETRIES      : Integer retry count (default: 3)
        MATRIX_RETRY_DELAY      : Float base delay in seconds (default: 1.0)
        """
        token = os.environ.get("MATRIX_ACCESS_TOKEN", "")
        if not token:
            logger.warning(
                "MATRIX_ACCESS_TOKEN is not set; bridge will operate in "
                "offline/mock mode."
            )

        encryption_raw = os.environ.get("MATRIX_ENCRYPTION", "false").lower()
        encryption = encryption_raw in ("1", "true", "yes")

        try:
            max_retries = int(os.environ.get("MATRIX_MAX_RETRIES", "3"))
        except ValueError:
            max_retries = 3

        try:
            retry_delay = float(os.environ.get("MATRIX_RETRY_DELAY", "1.0"))
        except ValueError:
            retry_delay = 1.0

        return cls(
            homeserver_url=os.environ.get(
                "MATRIX_HOMESERVER_URL", _DEFAULT_HOMESERVER
            ),
            user_id=os.environ.get("MATRIX_USER_ID", ""),
            access_token=token,
            device_name=os.environ.get("MATRIX_DEVICE_NAME", _DEFAULT_DEVICE_NAME),
            store_path=os.environ.get("MATRIX_STORE_PATH", _DEFAULT_STORE_PATH),
            encryption_enabled=encryption,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "MatrixConfig":
        """Build a :class:`MatrixConfig` from a plain dictionary."""
        room_mappings: List[RoomMappingConfig] = []
        for rm in data.get("room_mappings", []):
            if isinstance(rm, dict):
                room_mappings.append(
                    RoomMappingConfig(
                        subsystem_name=str(rm.get("subsystem_name", "")),
                        room_alias=str(rm.get("room_alias", "")),
                        space_alias=str(rm.get("space_alias", "")),
                        description=str(rm.get("description", "")),
                        read_only=bool(rm.get("read_only", False)),
                    )
                )
        return cls(
            homeserver_url=str(data.get("homeserver_url", _DEFAULT_HOMESERVER)),
            user_id=str(data.get("user_id", "")),
            access_token=str(data.get("access_token", "")),
            device_name=str(data.get("device_name", _DEFAULT_DEVICE_NAME)),
            store_path=str(data.get("store_path", _DEFAULT_STORE_PATH)),
            encryption_enabled=bool(data.get("encryption_enabled", False)),
            room_mappings=room_mappings,
            max_retries=int(data.get("max_retries", 3)),
            retry_delay_seconds=float(data.get("retry_delay_seconds", 1.0)),
        )

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Return a list of validation error messages (empty → valid)."""
        errors: List[str] = []
        if not self.homeserver_url.startswith(("http://", "https://")):
            errors.append(
                f"homeserver_url must start with http:// or https://; "
                f"got {self.homeserver_url!r}"
            )
        if not self.access_token:
            errors.append("access_token is required for authenticated operation")
        if not self.user_id:
            errors.append("user_id is required for authenticated operation")
        if self.max_retries < 0:
            errors.append("max_retries must be >= 0")
        if self.retry_delay_seconds < 0:
            errors.append("retry_delay_seconds must be >= 0")
        return errors

    # -----------------------------------------------------------------------
    # Safe representation (no secrets)
    # -----------------------------------------------------------------------

    def safe_repr(self) -> Dict[str, object]:
        """Return a dict safe for logging — access_token is redacted."""
        return {
            "homeserver_url": self.homeserver_url,
            "user_id": self.user_id,
            "access_token": "***REDACTED***" if self.access_token else "(not set)",
            "device_name": self.device_name,
            "store_path": self.store_path,
            "encryption_enabled": self.encryption_enabled,
            "room_mappings_count": len(self.room_mappings),
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
        }


@dataclass
class MatrixBridgeSettings:
    """Aggregated settings container for the full bridge stack."""

    matrix: MatrixConfig = field(default_factory=MatrixConfig)
    #: Alias prefix used when creating/resolving room aliases.
    room_alias_prefix: str = "murphy"
    #: Top-level space alias for the Murphy System space.
    top_level_space_alias: str = "#murphy-system"
    #: Maximum messages to buffer per room before dropping oldest.
    message_buffer_size: int = 256
    #: How often (seconds) the health-check loop polls room memberships.
    health_check_interval_seconds: float = 60.0
    #: Command prefix used to identify bot commands in Matrix messages.
    command_prefix: str = "!murphy"

    @classmethod
    def from_env(cls) -> "MatrixBridgeSettings":
        """Load settings from environment variables."""
        matrix_cfg = MatrixConfig.from_env()
        return cls(
            matrix=matrix_cfg,
            room_alias_prefix=os.environ.get("MATRIX_ROOM_ALIAS_PREFIX", "murphy"),
            top_level_space_alias=os.environ.get(
                "MATRIX_TOP_SPACE_ALIAS", "#murphy-system"
            ),
            message_buffer_size=int(
                os.environ.get("MATRIX_MESSAGE_BUFFER_SIZE", "256")
            ),
            health_check_interval_seconds=float(
                os.environ.get("MATRIX_HEALTH_CHECK_INTERVAL", "60.0")
            ),
            command_prefix=os.environ.get("MATRIX_COMMAND_PREFIX", "!murphy"),
        )


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_cached_settings: Optional[MatrixBridgeSettings] = None


def get_settings() -> MatrixBridgeSettings:
    """Return the (lazily cached) bridge settings from environment."""
    global _cached_settings  # noqa: PLW0603
    if _cached_settings is None:
        _cached_settings = MatrixBridgeSettings.from_env()
    return _cached_settings


def reset_settings() -> None:
    """Clear the cached settings (useful in tests)."""
    global _cached_settings  # noqa: PLW0603
    _cached_settings = None
