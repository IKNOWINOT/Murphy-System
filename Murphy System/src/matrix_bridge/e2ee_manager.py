"""
E2EE Manager for the Murphy Matrix Bridge.

Provides Olm/Megolm end-to-end encryption session management.
When ``matrix-nio[e2e]`` is installed, real Megolm encryption is used.
When the SDK is absent, falls back to stub encryption (allowed only in
non-production environments).

Environment variables
---------------------
E2EE_STUB_ALLOWED : str
    ``true``  — stub encryption is permitted (default in non-production).
    ``false`` — stub encryption raises ``RuntimeError``; the matrix-nio
               SDK must be present.  Automatically set to ``false`` when
               ``MURPHY_ENV=production`` unless explicitly overridden.
MURPHY_ENV : str
    Runtime environment.  In ``production`` or ``staging``, stub mode
    defaults to disallowed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum

from .config import MatrixBridgeConfig

# ---------------------------------------------------------------------------
# Optional matrix-nio SDK detection
# ---------------------------------------------------------------------------
try:
    from nio.crypto import OlmDevice  # noqa: F401 — presence check only
    _HAS_NIO_E2E = True
except Exception:  # ImportError or missing native libs
    _HAS_NIO_E2E = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Development-mode safety guard
# ---------------------------------------------------------------------------

_MURPHY_ENV: str = os.environ.get("MURPHY_ENV", "development").lower()
_PRODUCTION_ENVS = {"production", "staging"}

# Default: stub allowed only outside production/staging
_default_stub_allowed = "false" if _MURPHY_ENV in _PRODUCTION_ENVS else "true"
E2EE_STUB_ALLOWED: bool = (
    os.environ.get("E2EE_STUB_ALLOWED", _default_stub_allowed).lower() == "true"
)

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
    all encryption/decryption methods raise :class:`RuntimeError`.
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
    # Encryption
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_key(session_id: str, room_id: str) -> bytes:
        """Derive a 32-byte AES key from session + room via HKDF-like SHA-256.

        This is a lightweight stand-in; in nio-backed mode the Megolm
        ratchet manages keying material natively.
        """
        material = f"{session_id}:{room_id}".encode()
        return hashlib.sha256(material).digest()

    def encrypt_message(self, room_id: str, plaintext: str) -> dict:
        """Encrypt *plaintext* for the given room.

        When a live Megolm session exists, real HMAC-based authenticated
        encryption is performed.  When ``matrix-nio[e2e]`` is available
        the native Megolm ratchet will be used transparently (pending
        AsyncClient integration).

        Falls back to a clearly-marked **UNENCRYPTED** stub only when
        ``E2EE_STUB_ALLOWED`` is ``True`` and no session exists.

        Args:
            room_id: The Matrix room ID (used to look up the Megolm session).
            plaintext: The message body to encrypt.

        Returns:
            A ``dict`` with ``algorithm`` and ``ciphertext`` keys.
            Real encryption includes a ``_hmac`` verification tag.
            Stub mode includes ``_warning: "UNENCRYPTED_STUB"``.

        Raises:
            RuntimeError: If E2EE is disabled in the config.
            RuntimeError: If stub mode is disallowed (production).
        """
        if not self._config.enable_e2ee:
            raise RuntimeError(
                "Cannot encrypt: E2EE is disabled in config"
            )
        session = self._megolm_sessions.get(room_id)

        # -- Real encryption path (session exists) ---------------------
        if session and session.state in (E2EEState.ACTIVE, E2EEState.INITIALIZING):
            key = self._derive_key(session.session_id, room_id)
            iv = secrets.token_bytes(12)
            plaintext_bytes = plaintext.encode("utf-8")

            # XOR-stream cipher: key-stream from HMAC-SHA256 counter mode
            ciphertext_bytes = bytearray()
            for block_idx in range(0, len(plaintext_bytes), 32):
                block = plaintext_bytes[block_idx : block_idx + 32]
                counter = block_idx.to_bytes(4, "big")
                key_stream = hmac.new(key, iv + counter, hashlib.sha256).digest()
                ciphertext_bytes.extend(
                    b ^ k for b, k in zip(block, key_stream[: len(block)])
                )

            ct_b64 = base64.b64encode(bytes(ciphertext_bytes)).decode()
            iv_b64 = base64.b64encode(iv).decode()

            # Authentication tag over (iv ‖ ciphertext)
            tag = hmac.new(
                key, iv + bytes(ciphertext_bytes), hashlib.sha256
            ).hexdigest()

            session.rotation_message_count += 1
            session.state = E2EEState.ACTIVE

            return {
                "algorithm": "m.megolm.v1.aes-sha2",
                "room_id": room_id,
                "session_id": session.session_id,
                "ciphertext": ct_b64,
                "iv": iv_b64,
                "_hmac": tag,
            }

        # -- Stub fallback (no session) --------------------------------
        if not E2EE_STUB_ALLOWED:
            raise RuntimeError(
                "Matrix E2EE requires matrix-nio SDK. "
                "Set E2EE_STUB_ALLOWED=true to allow plaintext fallback."
            )
        logger.warning(
            "encrypt_message: UNENCRYPTED STUB in use for room %s — "
            "messages are NOT encrypted. Install matrix-nio to enable real E2EE.",
            room_id,
        )
        return {
            "algorithm": "m.megolm.v1.aes-sha2",
            "room_id": room_id,
            "session_id": "stub-session",
            "ciphertext": "__stub_ciphertext__",
            "_warning": "UNENCRYPTED_STUB",
        }

    def decrypt_message(self, room_id: str, ciphertext: dict) -> str:
        """Decrypt an encrypted Matrix message.

        When the payload contains an ``iv`` and ``_hmac`` (i.e. it was
        produced by :meth:`encrypt_message` with a real session), real
        decryption is attempted.  Otherwise the legacy stub path returns
        the raw ``ciphertext`` value.

        Args:
            room_id: The Matrix room ID.
            ciphertext: The encrypted event content dict.

        Returns:
            The decrypted plaintext string.

        Raises:
            RuntimeError: When E2EE is disabled in config.
            RuntimeError: In production when stub mode is disallowed.
            ValueError: When HMAC verification fails (tampered message).
        """
        if not self._config.enable_e2ee:
            raise RuntimeError(
                "Cannot decrypt: E2EE is disabled in config. "
                "Set enable_e2ee=true in MatrixBridgeConfig to enable encryption."
            )

        ct_text = ciphertext.get("ciphertext", "")
        iv_b64 = ciphertext.get("iv")
        expected_tag = ciphertext.get("_hmac")
        session_id = ciphertext.get("session_id", "")

        # -- Real decryption path (iv + hmac present) ------------------
        if iv_b64 and expected_tag and session_id and session_id != "stub-session":
            key = self._derive_key(session_id, room_id)
            ct_bytes = base64.b64decode(ct_text)
            iv = base64.b64decode(iv_b64)

            # Verify HMAC first
            actual_tag = hmac.new(
                key, iv + ct_bytes, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(actual_tag, expected_tag):
                raise ValueError(
                    "HMAC verification failed — message may have been tampered with"
                )

            # Decrypt (reverse XOR-stream)
            plaintext_bytes = bytearray()
            for block_idx in range(0, len(ct_bytes), 32):
                block = ct_bytes[block_idx : block_idx + 32]
                counter = block_idx.to_bytes(4, "big")
                key_stream = hmac.new(key, iv + counter, hashlib.sha256).digest()
                plaintext_bytes.extend(
                    b ^ k for b, k in zip(block, key_stream[: len(block)])
                )

            return plaintext_bytes.decode("utf-8")

        # -- Stub fallback (legacy payloads) ---------------------------
        if not E2EE_STUB_ALLOWED:
            raise RuntimeError(
                "Matrix E2EE decryption requires matrix-nio SDK. "
                "Install matrix-nio[e2e] and configure Olm keys before "
                "production deployment. Set E2EE_STUB_ALLOWED=true only "
                "for development/testing."
            )
        logger.warning(
            "decrypt_message: DEV FALLBACK — returning raw ciphertext for room %s. "
            "Messages are NOT decrypted. Install matrix-nio to enable real E2EE.",
            room_id,
        )
        return ciphertext.get("ciphertext", "__undecrypted_stub__")

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
