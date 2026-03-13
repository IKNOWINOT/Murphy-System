# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Matrix homeserver client wrapper for the Murphy System.

Uses ``matrix-nio`` for all Matrix API operations with:
- Token or password authentication
- Room management (create, join, invite, set topic)
- Message sending (text, formatted, notices)
- Event listening with callback dispatch
- Reconnection with exponential back-off
- Health check / presence reporting
- Circuit-breaker pattern consistent with integration_framework.py

Configuration (environment variables)
--------------------------------------
MATRIX_HOMESERVER_URL   homeserver base URL
MATRIX_BOT_USER         full Matrix user ID, e.g. ``@murphy:example.com``
MATRIX_BOT_TOKEN        access token (preferred over password)
MATRIX_BOT_PASSWORD     password (fallback when no token)
MATRIX_DEVICE_ID        device ID to reuse (optional)
MATRIX_E2E_ENABLED      ``true`` to enable E2E encryption (default ``false``)
MATRIX_CB_THRESHOLD     circuit-breaker failure threshold (default ``5``)
MATRIX_CB_TIMEOUT       circuit-breaker reset timeout in seconds (default ``60``)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional matrix-nio import
# ---------------------------------------------------------------------------
try:
    import nio  # type: ignore
    from nio import (  # type: ignore
        AsyncClient,
        AsyncClientConfig,
        InviteMemberEvent,
        LoginResponse,
        MatrixRoom,
        RoomCreateResponse,
        RoomMessageText,
        RoomSendResponse,
        SyncResponse,
    )
    _NIO_AVAILABLE = True
except ImportError:  # pragma: no cover
    nio = None  # type: ignore
    AsyncClient = None  # type: ignore
    AsyncClientConfig = None  # type: ignore
    InviteMemberEvent = None  # type: ignore
    LoginResponse = None  # type: ignore
    MatrixRoom = None  # type: ignore
    RoomCreateResponse = None  # type: ignore
    RoomMessageText = None  # type: ignore
    RoomSendResponse = None  # type: ignore
    SyncResponse = None  # type: ignore
    _NIO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Circuit-breaker state
# ---------------------------------------------------------------------------

class _CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _CircuitBreaker:
    threshold: int = 5
    timeout: float = 60.0
    _failures: int = field(default=0, init=False, repr=False)
    _state: str = field(default=_CircuitState.CLOSED, init=False, repr=False)
    _opened_at: float = field(default=0.0, init=False, repr=False)

    @property
    def is_open(self) -> bool:
        if self._state == _CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.timeout:
                self._state = _CircuitState.HALF_OPEN
                return False
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._state = _CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            self._state = _CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning("MatrixClient circuit breaker OPEN after %d failures", self._failures)


# ---------------------------------------------------------------------------
# MatrixClient
# ---------------------------------------------------------------------------

class MatrixClient:
    """Async Matrix homeserver client with reconnection and circuit-breaker.

    Parameters
    ----------
    homeserver:
        Homeserver base URL.  Defaults to ``MATRIX_HOMESERVER_URL`` env var.
    user_id:
        Full Matrix user ID.  Defaults to ``MATRIX_BOT_USER`` env var.
    token:
        Access token.  Defaults to ``MATRIX_BOT_TOKEN`` env var.
    password:
        Password (used when no token is set).  Defaults to
        ``MATRIX_BOT_PASSWORD`` env var.
    device_id:
        Reuse a specific device ID for E2EE continuity.
    e2e_enabled:
        Enable end-to-end encryption.  Defaults to ``MATRIX_E2E_ENABLED``.
    cb_threshold:
        Circuit-breaker failure threshold.
    cb_timeout:
        Circuit-breaker reset timeout in seconds.
    """

    def __init__(
        self,
        homeserver: Optional[str] = None,
        user_id: Optional[str] = None,
        token: Optional[str] = None,
        password: Optional[str] = None,
        device_id: Optional[str] = None,
        e2e_enabled: bool = False,
        cb_threshold: int = 5,
        cb_timeout: float = 60.0,
    ) -> None:
        self.homeserver: str = (
            homeserver or os.environ.get("MATRIX_HOMESERVER_URL", "http://localhost:8008")
        ).rstrip("/")
        self.user_id: str = user_id or os.environ.get("MATRIX_BOT_USER", "")
        self.token: Optional[str] = token or os.environ.get("MATRIX_BOT_TOKEN") or None
        self.password: Optional[str] = password or os.environ.get("MATRIX_BOT_PASSWORD") or None
        self.device_id: Optional[str] = device_id or os.environ.get("MATRIX_DEVICE_ID") or None
        self.e2e_enabled: bool = e2e_enabled or (
            os.environ.get("MATRIX_E2E_ENABLED", "false").lower() in ("1", "true", "yes")
        )
        self._cb = _CircuitBreaker(threshold=cb_threshold, timeout=cb_timeout)
        self._client: Optional[Any] = None  # nio.AsyncClient
        self._connected: bool = False
        self._event_callbacks: List[Callable[..., Awaitable[None]]] = []
        self._known_rooms: Dict[str, str] = {}  # alias → room_id

    # ------------------------------------------------------------------
    # Connection / auth
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Log in to the homeserver and start sync.

        Returns ``True`` on success, ``False`` when nio is unavailable or
        credentials are missing.
        """
        if not _NIO_AVAILABLE:
            logger.warning(
                "matrix-nio is not installed — Matrix integration disabled. "
                "Install with: pip install 'matrix-nio[e2e]'"
            )
            return False

        if not self.user_id:
            logger.error("MATRIX_BOT_USER is not configured")
            return False

        cfg = AsyncClientConfig(
            max_limit_exceeded=0,
            max_timeouts=0,
            store_sync_tokens=True,
            encryption_enabled=self.e2e_enabled,
        )
        self._client = AsyncClient(
            self.homeserver,
            self.user_id,
            device_id=self.device_id,
            config=cfg,
        )
        self._register_internal_callbacks()

        if self.token:
            self._client.access_token = self.token
            self._connected = True
            logger.info("MatrixClient authenticated via access token for %s", self.user_id)
        elif self.password:
            resp = await self._client.login(self.password, device_name="MurphyBot")
            if isinstance(resp, LoginResponse):
                self._connected = True
                logger.info("MatrixClient logged in as %s", self.user_id)
            else:
                logger.error("MatrixClient login failed: %s", resp)
                return False
        else:
            logger.error("No MATRIX_BOT_TOKEN or MATRIX_BOT_PASSWORD configured")
            return False

        return True

    async def disconnect(self) -> None:
        """Close the Matrix client connection."""
        if self._client is not None:
            await self._client.close()
            self._connected = False
            logger.info("MatrixClient disconnected")

    async def sync_forever(
        self,
        timeout_ms: int = 30_000,
        reconnect_backoff: float = 5.0,
        max_backoff: float = 300.0,
    ) -> None:
        """Run the sync loop with automatic reconnection and exponential back-off."""
        backoff = reconnect_backoff
        while True:
            if not self._connected:
                ok = await self.connect()
                if not ok:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)
                    continue
                backoff = reconnect_backoff

            try:
                if self._client is not None:
                    await self._client.sync_forever(timeout=timeout_ms, full_state=True)
            except Exception as exc:  # pragma: no cover
                logger.warning("MatrixClient sync error: %s — reconnecting in %ss", exc, backoff)
                self._connected = False
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    # ------------------------------------------------------------------
    # Room management
    # ------------------------------------------------------------------

    async def create_room(
        self,
        alias: str,
        name: str,
        topic: str = "",
        is_public: bool = False,
        invite: Optional[List[str]] = None,
        encrypted: bool = False,
    ) -> Optional[str]:
        """Create a Matrix room and return its room ID.

        Returns ``None`` if nio is unavailable or the circuit breaker is open.
        Idempotent: if the room already exists (tracked by alias), returns the
        cached room ID.
        """
        if alias in self._known_rooms:
            return self._known_rooms[alias]

        if not self._is_available():
            return None

        preset = "public_chat" if is_public else "private_chat"
        initial_state: List[Dict[str, Any]] = []
        if encrypted:
            initial_state.append(
                {
                    "type": "m.room.encryption",
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                }
            )
        try:
            resp = await self._client.room_create(  # type: ignore[union-attr]
                alias=alias,
                name=name,
                topic=topic,
                preset=preset,
                invite=invite or [],
                initial_state=initial_state,
            )
            self._cb.record_success()
            if hasattr(resp, "room_id"):
                self._known_rooms[alias] = resp.room_id
                logger.info("Created Matrix room %s → %s", alias, resp.room_id)
                return resp.room_id
            logger.warning("Unexpected room_create response: %s", resp)
        except Exception as exc:
            self._cb.record_failure()
            logger.warning("room_create(%s) failed: %s", alias, exc)
        return None

    async def join_room(self, room_id_or_alias: str) -> bool:
        """Join a room by ID or alias."""
        if not self._is_available():
            return False
        try:
            resp = await self._client.join(room_id_or_alias)  # type: ignore[union-attr]
            self._cb.record_success()
            return not hasattr(resp, "status_code")
        except Exception as exc:
            self._cb.record_failure()
            logger.warning("join_room(%s) failed: %s", room_id_or_alias, exc)
            return False

    async def invite_user(self, room_id: str, user_id: str) -> bool:
        """Invite *user_id* to *room_id*."""
        if not self._is_available():
            return False
        try:
            await self._client.room_invite(room_id, user_id)  # type: ignore[union-attr]
            self._cb.record_success()
            return True
        except Exception as exc:
            self._cb.record_failure()
            logger.warning("invite_user(%s → %s) failed: %s", user_id, room_id, exc)
            return False

    async def set_room_topic(self, room_id: str, topic: str) -> bool:
        """Update the topic of *room_id*."""
        if not self._is_available():
            return False
        try:
            await self._client.room_put_state(  # type: ignore[union-attr]
                room_id,
                "m.room.topic",
                {"topic": topic},
            )
            self._cb.record_success()
            return True
        except Exception as exc:
            self._cb.record_failure()
            logger.warning("set_room_topic(%s) failed: %s", room_id, exc)
            return False

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send_text(self, room_id: str, text: str) -> bool:
        """Send a plain-text ``m.text`` message to *room_id*."""
        return await self._send_message(room_id, "m.text", {"body": text, "msgtype": "m.text"})

    async def send_notice(self, room_id: str, text: str) -> bool:
        """Send an ``m.notice`` message (bot output convention)."""
        return await self._send_message(
            room_id, "m.notice", {"body": text, "msgtype": "m.notice"}
        )

    async def send_formatted(
        self, room_id: str, plain: str, html: str, msgtype: str = "m.text"
    ) -> bool:
        """Send a message with both plain-text and HTML formatted bodies."""
        content = {
            "msgtype": msgtype,
            "body": plain,
            "format": "org.matrix.custom.html",
            "formatted_body": html,
        }
        return await self._send_message(room_id, msgtype, content)

    async def send_file(
        self,
        room_id: str,
        filename: str,
        data: bytes,
        mimetype: str = "application/octet-stream",
    ) -> bool:
        """Upload *data* and post it as a file message to *room_id*."""
        if not self._is_available():
            return False
        try:
            resp = await self._client.upload(data, content_type=mimetype)  # type: ignore[union-attr]
            if not hasattr(resp, "content_uri"):
                return False
            content = {
                "msgtype": "m.file",
                "body": filename,
                "url": resp.content_uri,
                "info": {"mimetype": mimetype, "size": len(data)},
            }
            self._cb.record_success()
            return await self._send_message(room_id, "m.file", content)
        except Exception as exc:
            self._cb.record_failure()
            logger.warning("send_file(%s) failed: %s", filename, exc)
            return False

    # ------------------------------------------------------------------
    # Presence / health
    # ------------------------------------------------------------------

    async def set_presence(self, presence: str = "online", status_msg: str = "") -> bool:
        """Report bot presence to the homeserver."""
        if not self._is_available():
            return False
        try:
            await self._client.set_presence(presence, status_msg)  # type: ignore[union-attr]
            return True
        except Exception as exc:
            logger.debug("set_presence failed: %s", exc)
            return False

    def is_connected(self) -> bool:
        """Return ``True`` if the client has an active connection."""
        return self._connected and self._client is not None

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    def add_event_callback(self, callback: Callable[..., Awaitable[None]]) -> None:
        """Register an async callback invoked for every incoming room event."""
        self._event_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_available(self) -> bool:
        if not _NIO_AVAILABLE or self._client is None or not self._connected:
            return False
        if self._cb.is_open:
            logger.warning("MatrixClient circuit breaker is OPEN — skipping API call")
            return False
        return True

    async def _send_message(self, room_id: str, _msgtype: str, content: Dict[str, Any]) -> bool:
        if not self._is_available():
            return False
        try:
            resp = await self._client.room_send(  # type: ignore[union-attr]
                room_id, message_type="m.room.message", content=content
            )
            self._cb.record_success()
            return hasattr(resp, "event_id")
        except Exception as exc:
            self._cb.record_failure()
            logger.warning("send_message(%s) failed: %s", room_id, exc)
            return False

    def _register_internal_callbacks(self) -> None:
        if self._client is None:
            return
        if RoomMessageText is not None:
            self._client.add_event_callback(self._on_room_message, RoomMessageText)
        if InviteMemberEvent is not None:
            self._client.add_event_callback(self._on_invite, InviteMemberEvent)

    async def _on_room_message(self, room: Any, event: Any) -> None:
        for cb in self._event_callbacks:
            try:
                await cb(room, event)
            except Exception as exc:
                logger.warning("Event callback error: %s", exc)

    async def _on_invite(self, room: Any, event: Any) -> None:
        if self._client is not None:
            await self._client.join(room.room_id)
            logger.info("Auto-joined room %s", room.room_id)


__all__ = ["MatrixClient"]
