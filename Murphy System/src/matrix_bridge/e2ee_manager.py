"""
E2EE Manager for the Murphy Matrix Bridge.

Provides stub management of Olm/Megolm end-to-end encryption sessions.
Real cryptographic operations will be delegated to ``matrix-nio``'s
``AsyncClient`` in a later PR.  This module maintains session metadata
and state, and raises :class:`NotImplementedError` for operations that
require the SDK.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum

from .config import MatrixBridgeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------


class E2EEState(str, Enum):
    """Lifecycle state of an E2EE session or the E2EE subsystem.

    Attributes:
        DISABLED: E2EE is disabled in the configuration.
        INITIALIZING: Keys are being established with the homeserver.
        ACTIVE: Session is active and can encrypt/decrypt.
        ERROR: A non-recoverable error has occurred.
    """

    DISABLED = "disabled"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class OlmSession:
    """Metadata for a per-device Olm 1-to-1 session.

    Attributes:
        session_id: Unique session identifier.
        peer_user_id: Matrix user ID of the remote peer.
        peer_device_id: Device ID of the remote peer.
        state: Current :class:`E2EEState`.
        created_at: ISO-8601 UTC creation timestamp.
        last_used: ISO-8601 UTC timestamp of last use.
    """

    session_id: str
    peer_user_id: str
    peer_device_id: str
    state: E2EEState
    created_at: str
    last_used: str


@dataclass
class MegolmSession:
    """Metadata for a per-room Megolm group session.

    Attributes:
        session_id: Unique session identifier.
        room_id: Matrix room ID this session belongs to.
        state: Current :class:`E2EEState`.
        created_at: ISO-8601 UTC creation timestamp.
        rotation_message_count: Number of messages sent with this session.
        rotation_period_ms: Maximum session age in milliseconds before
            rotation (default: 1 week).
    """

    session_id: str
    room_id: str
    state: E2EEState
    created_at: str
    rotation_message_count: int = 0
    rotation_period_ms: int = 604_800_000  # 1 week


# ---------------------------------------------------------------------------
# E2EEManager
# ---------------------------------------------------------------------------


class E2EEManager:
    """Manages Olm and Megolm session stubs for encrypted Matrix rooms.

    When :attr:`~config.MatrixBridgeConfig.enable_e2ee` is ``False``,
    all encryption/decryption methods raise :class:`NotImplementedError`.
    When E2EE is enabled but the SDK is absent, the same exception is
    raised — it will be caught and replaced with a real implementation
    once ``matrix-nio`` is integrated.

    Args:
        config: The active :class:`~config.MatrixBridgeConfig`.
    """

    # Default rotation threshold (100 messages per spec recommendation)
    _ROTATION_MSG_THRESHOLD: int = 100

    def __init__(self, config: MatrixBridgeConfig) -> None:
        self._config = config
        self._state: E2EEState = (
            E2EEState.INITIALIZING if config.enable_e2ee else E2EEState.DISABLED
        )
        self._olm_sessions: dict[str, OlmSession] = {}   # session_id → session
        self._megolm_sessions: dict[str, MegolmSession] = {}  # room_id → session
        logger.debug(
            "E2EEManager initialised — state=%s", self._state.value
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Return whether E2EE is enabled in the configuration.

        Returns:
            ``True`` when :attr:`~config.MatrixBridgeConfig.enable_e2ee`
            is ``True``.
        """
        return self._config.enable_e2ee

    def get_state(self) -> E2EEState:
        """Return the current :class:`E2EEState` of the manager.

        Returns:
            One of the :class:`E2EEState` enum values.
        """
        return self._state

    # ------------------------------------------------------------------
    # Session creation
    # ------------------------------------------------------------------

    def create_olm_session(
        self, peer_user_id: str, peer_device_id: str
    ) -> OlmSession:
        """Create a new stub Olm 1-to-1 session record.

        .. note::
            No actual Olm handshake is performed here; that requires
            ``matrix-nio`` (pending PR).

        Args:
            peer_user_id: Matrix user ID of the remote device owner.
            peer_device_id: Device ID of the remote device.

        Returns:
            A new :class:`OlmSession` in :attr:`E2EEState.INITIALIZING`.

        Raises:
            RuntimeError: If E2EE is disabled in the config.
        """
        if not self._config.enable_e2ee:
            raise RuntimeError(
                "Cannot create Olm session: E2EE is disabled in config"
            )
        now = datetime.now(timezone.utc).isoformat()
        session = OlmSession(
            session_id=str(uuid.uuid4()),
            peer_user_id=peer_user_id,
            peer_device_id=peer_device_id,
            state=E2EEState.INITIALIZING,
            created_at=now,
            last_used=now,
        )
        self._olm_sessions[session.session_id] = session
        logger.debug(
            "Created Olm session %s for %s/%s",
            session.session_id,
            peer_user_id,
            peer_device_id,
        )
        return session

    def create_megolm_session(self, room_id: str) -> MegolmSession:
        """Create a new stub Megolm group session record for *room_id*.

        An existing session for the room is replaced.

        .. note::
            No actual Megolm keys are generated here; that requires
            ``matrix-nio`` (pending PR).

        Args:
            room_id: The Matrix room ID for this group session.

        Returns:
            A new :class:`MegolmSession` in :attr:`E2EEState.INITIALIZING`.

        Raises:
            RuntimeError: If E2EE is disabled in the config.
        """
        if not self._config.enable_e2ee:
            raise RuntimeError(
                "Cannot create Megolm session: E2EE is disabled in config"
            )
        session = MegolmSession(
            session_id=str(uuid.uuid4()),
            room_id=room_id,
            state=E2EEState.INITIALIZING,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._megolm_sessions[room_id] = session
        logger.debug(
            "Created Megolm session %s for room %s", session.session_id, room_id
        )
        return session

    # ------------------------------------------------------------------
    # Session access
    # ------------------------------------------------------------------

    def get_session(self, room_id: str) -> MegolmSession | None:
        """Return the current Megolm session for *room_id*, if any.

        Args:
            room_id: The Matrix room ID to look up.

        Returns:
            The :class:`MegolmSession` or ``None``.
        """
        return self._megolm_sessions.get(room_id)

    def needs_rotation(self, session: MegolmSession) -> bool:
        """Check whether a Megolm session should be rotated.

        Rotation is triggered either by exceeding the message count
        threshold or the time-based ``rotation_period_ms``.

        Args:
            session: The :class:`MegolmSession` to evaluate.

        Returns:
            ``True`` if the session should be replaced.
        """
        if session.rotation_message_count >= self._ROTATION_MSG_THRESHOLD:
            return True

        created_dt = datetime.fromisoformat(session.created_at)
        now = datetime.now(timezone.utc)
        age_ms = (now - created_dt).total_seconds() * 1000
        if age_ms >= session.rotation_period_ms:
            return True

        return False

    # ------------------------------------------------------------------
    # Encryption stubs
    # ------------------------------------------------------------------

    def encrypt_message(self, room_id: str, plaintext: str) -> dict:
        """Return a stub encrypted payload for *plaintext*.

        .. note::
            Real Megolm encryption via ``matrix-nio`` is pending.  This
            method returns a placeholder dict so callers can be written
            today without blocking on the SDK.

        Args:
            room_id: The Matrix room ID (used to look up the Megolm session).
            plaintext: The message body to encrypt.

        Returns:
            A ``dict`` with ``algorithm`` and ``ciphertext`` keys.  The
            ``ciphertext`` value is a stub string, not real ciphertext.

        Raises:
            RuntimeError: If E2EE is disabled in the config.
        """
        if not self._config.enable_e2ee:
            raise RuntimeError(
                "Cannot encrypt: E2EE is disabled in config"
            )
        session = self._megolm_sessions.get(room_id)
        try:
            raise NotImplementedError(
                "Real Megolm encryption requires matrix-nio SDK (pending PR)"
            )
        except NotImplementedError:
            logger.debug(
                "encrypt_message: returning stub payload for room %s", room_id
            )
            if session:
                session.rotation_message_count += 1
            return {
                "algorithm": "m.megolm.v1.aes-sha2",
                "room_id": room_id,
                "session_id": session.session_id if session else "stub-session",
                "ciphertext": "__stub_ciphertext__",
            }

    def decrypt_message(self, room_id: str, ciphertext: dict) -> str:
        """Decrypt an encrypted Matrix message.

        .. note::
            Real decryption via ``matrix-nio`` is pending.

        Args:
            room_id: The Matrix room ID.
            ciphertext: The encrypted event content dict.

        Returns:
            The decrypted plaintext string (stub implementation).

        Raises:
            NotImplementedError: When E2EE is disabled.
            NotImplementedError: Always, until matrix-nio is integrated.
        """
        if not self._config.enable_e2ee:
            raise NotImplementedError(
                "Cannot decrypt: E2EE is disabled in config"
            )
        raise NotImplementedError(
            "Real Megolm decryption requires matrix-nio SDK (pending PR)"
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise all session metadata to a JSON-compatible dict.

        Returns:
            Dictionary with ``state``, ``olm_sessions``, and
            ``megolm_sessions`` keys.
        """
        return {
            "state": self._state.value,
            "olm_sessions": {
                sid: {**asdict(s), "state": s.state.value}
                for sid, s in self._olm_sessions.items()
            },
            "megolm_sessions": {
                rid: {**asdict(s), "state": s.state.value}
                for rid, s in self._megolm_sessions.items()
            },
        }
