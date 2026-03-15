# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
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

Classes
-------
MatrixClientError : Exception
    Raised on unrecoverable Matrix API errors.
MessageContent : dataclass
    Structured message payload (plain text + optional HTML body).
SendResult : dataclass
    Result returned from :meth:`MatrixClient.send_message`.
MatrixClient : class
    Async Matrix client wrapper --- connect, join rooms, send/receive.
MockMatrixClient : class
    In-memory stub that satisfies the same interface without network I/O.
create_client(config) : function
    Factory: returns a real or mock client based on token availability.

Usage (async)::

    from matrix_bridge.matrix_config import MatrixConfig
    from matrix_bridge.matrix_client import create_client

    cfg = MatrixConfig.from_env()
    async with create_client(cfg) as client:
        await client.send_text(room_alias="murphy-general", text="Hello!")
"""
from __future__ import annotations

import abc
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .matrix_config import MatrixConfig

logger = logging.getLogger(__name__)

# Optional matrix-nio import
try:
    import nio  # type: ignore[import-untyped]
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
    _HAS_NIO = True
    _NIO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _HAS_NIO = False
    _NIO_AVAILABLE = False
    nio = None  # type: ignore[assignment]
    AsyncClient = None  # type: ignore
    AsyncClientConfig = None  # type: ignore
    InviteMemberEvent = None  # type: ignore
    LoginResponse = None  # type: ignore
    MatrixRoom = None  # type: ignore
    RoomCreateResponse = None  # type: ignore
    RoomMessageText = None  # type: ignore
    RoomSendResponse = None  # type: ignore
    SyncResponse = None  # type: ignore

# Optional aiohttp import (used for raw HTTP fallback)
try:
    import aiohttp  # type: ignore[import-untyped]
    _HAS_AIOHTTP = True
except ImportError:  # pragma: no cover
    _HAS_AIOHTTP = False
    aiohttp = None  # type: ignore[assignment]

# Errors

class MatrixClientError(Exception):
    """Raised on unrecoverable Matrix API or connection errors."""

# Data structures

@dataclass
class MessageContent:
    """Structured Matrix message payload.

    Attributes
    ----------
    text:
        Plain-text fallback body (required).
    html:
        Optional HTML-formatted body.  If *None*, only the plain body is sent.
    msgtype:
        Matrix ``msgtype`` value; defaults to ``m.text``.
    """

    text: str
    html: Optional[str] = None
    msgtype: str = "m.text"

    def to_content_dict(self) -> Dict[str, object]:
        """Return a Matrix ``content`` dictionary."""
        content: Dict[str, object] = {
            "msgtype": self.msgtype,
            "body": self.text,
        }
        if self.html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = self.html
        return content

@dataclass
class SendResult:
    """Result returned by :meth:`MatrixClient.send_message`.

    Attributes
    ----------
    success:
        Whether the message was accepted by the homeserver.
    event_id:
        Matrix event ID assigned by the homeserver on success.
    room_alias:
        Alias of the target room.
    error:
        Error message if *success* is ``False``.
    """

    success: bool
    event_id: str = ""
    room_alias: str = ""
    error: str = ""

@dataclass
class RoomInfo:
    """Basic information about a joined Matrix room."""

    room_id: str
    alias: str
    display_name: str = ""
    member_count: int = 0

# Base interface (for type-checking mock vs real)

class _MatrixClientBase(abc.ABC):
    """Shared interface for real and mock Matrix clients."""

    def __init__(self, config: MatrixConfig) -> None:
        self._config = config
        self._event_handlers: Dict[str, List[Callable[..., Any]]] = {}
        self._room_cache: Dict[str, RoomInfo] = {}

    # Event handler registration

    def on_event(self, event_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register an async event handler for *event_type*."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._event_handlers.setdefault(event_type, []).append(fn)
            return fn

        return decorator

    def add_event_handler(self, event_type: str, handler: Callable[..., Any]) -> None:
        """Register *handler* for *event_type* programmatically."""
        self._event_handlers.setdefault(event_type, []).append(handler)

    async def _dispatch(self, event_type: str, event: Any) -> None:
        """Dispatch *event* to all registered handlers for *event_type*."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Event handler %r raised an exception", handler)

    # Async context manager

    async def __aenter__(self) -> "_MatrixClientBase":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @abc.abstractmethod
    async def connect(self) -> None:
        """Connect to the Matrix homeserver."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the Matrix connection."""

    @abc.abstractmethod
    async def send_message(
        self, room_alias: str, content: MessageContent
    ) -> SendResult:
        """Send a Matrix room message."""

    async def send_text(self, room_alias: str, text: str) -> SendResult:
        return await self.send_message(
            room_alias=room_alias, content=MessageContent(text=text)
        )

    async def send_html(
        self, room_alias: str, text: str, html: str
    ) -> SendResult:
        return await self.send_message(
            room_alias=room_alias,
            content=MessageContent(text=text, html=html),
        )

    @abc.abstractmethod
    async def join_room(self, room_alias: str) -> Optional[RoomInfo]:
        """Join the room identified by *room_alias*."""

    @abc.abstractmethod
    async def create_room(
        self,
        alias: str,
        name: str,
        topic: str = "",
        is_public: bool = False,
        encrypted: bool = False,
    ) -> Optional[RoomInfo]:
        """Create a new Matrix room."""

    @abc.abstractmethod
    async def invite_user(self, room_alias: str, user_id: str) -> bool:
        """Invite *user_id* to the room identified by *room_alias*."""

    @abc.abstractmethod
    async def start_sync(self) -> None:
        """Start the background sync loop."""

    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Return whether the client is currently connected."""

# Circuit-breaker state

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

# MatrixClient (standalone --- used by tests and most consumers)

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
        self._known_rooms: Dict[str, str] = {}  # alias -> room_id

    # Connection / auth

    async def connect(self) -> bool:
        """Log in to the homeserver and start sync.

        Returns ``True`` on success, ``False`` when nio is unavailable or
        credentials are missing.
        """
        if not _NIO_AVAILABLE:
            logger.warning(
                "matrix-nio is not installed --- Matrix integration disabled. "
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
                logger.warning("MatrixClient sync error: %s --- reconnecting in %ss", exc, backoff)
                self._connected = False
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    # Room management

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
                logger.info("Created Matrix room %s -> %s", alias, resp.room_id)
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
            logger.warning("invite_user(%s -> %s) failed: %s", user_id, room_id, exc)
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

    # Messaging

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

    # Presence / health

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

    # Event callbacks

    def add_event_callback(self, callback: Callable[..., Awaitable[None]]) -> None:
        """Register an async callback invoked for every incoming room event."""
        capped_append(self._event_callbacks, callback)

    # Internal helpers

    def _is_available(self) -> bool:
        if not _NIO_AVAILABLE or self._client is None or not self._connected:
            return False
        if self._cb.is_open:
            logger.warning("MatrixClient circuit breaker is OPEN --- skipping API call")
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

# nio-backed Matrix client (ABC implementation)

class _NioMatrixClient(_MatrixClientBase):
    """Async Matrix client backed by ``matrix-nio``.

    Requires the ``matrix-nio`` package to be installed::

        pip install matrix-nio

    If ``nio`` is not available the factory :func:`create_client` will
    return a :class:`MockMatrixClient` instead.
    """

    def __init__(self, config: MatrixConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._connected = False
        self._sync_task: Optional[asyncio.Task[None]] = None

    # Lifecycle

    async def connect(self) -> None:
        """Authenticate with the homeserver and start the event loop."""
        if not _HAS_NIO:
            raise MatrixClientError(
                "matrix-nio is not installed.  "
                "Install it with: pip install matrix-nio"
            )
        cfg = self._config
        store_path = cfg.store_path if cfg.encryption_enabled else None
        self._client = nio.AsyncClient(
            homeserver=cfg.homeserver_url,
            user=cfg.user_id,
            store_path=store_path,
            config=nio.AsyncClientConfig(max_limit_exceeded=0),
        )
        self._client.access_token = cfg.access_token
        self._client.user_id = cfg.user_id
        # Register internal event handler bridge
        self._client.add_event_callback(self._on_message_event, nio.RoomMessageText)
        self._client.add_event_callback(self._on_room_event, nio.Event)
        self._connected = True
        logger.info(
            "MatrixClient connected to %s as %s", cfg.homeserver_url, cfg.user_id
        )

    async def close(self) -> None:
        """Gracefully close the Matrix connection."""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.close()
        self._connected = False
        logger.info("MatrixClient closed")

    def is_connected(self) -> bool:
        return self._connected

    # Sync

    async def start_sync(self) -> None:
        """Start the background sync loop (non-blocking)."""
        if not self._client:
            raise MatrixClientError("Not connected --- call connect() first")
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def _sync_loop(self) -> None:
        """Internal sync loop --- runs until cancelled."""
        if self._client is None:
            raise MatrixClientError("sync loop requires an active client")
        await self._client.sync_forever(timeout=30000, full_state=True)

    # Event callbacks

    async def _on_message_event(
        self, room: Any, event: Any
    ) -> None:
        await self._dispatch("m.room.message", {"room": room, "event": event})

    async def _on_room_event(
        self, room: Any, event: Any
    ) -> None:
        event_type = getattr(event, "type", "unknown")
        await self._dispatch(event_type, {"room": room, "event": event})

    # Room operations

    def _resolve_room_id(self, room_alias: str) -> str:
        """Return the Matrix room ID from alias cache, or the alias itself."""
        info = self._room_cache.get(room_alias)
        if info:
            return info.room_id
        if not room_alias.startswith("#") and not room_alias.startswith("!"):
            return f"#{room_alias}:{self._config.homeserver_url.split('://')[-1]}"
        return room_alias

    async def join_room(self, room_alias: str) -> Optional[RoomInfo]:
        """Join the room identified by *room_alias* and cache its info."""
        if not self._client:
            raise MatrixClientError("Not connected")
        resolved = self._resolve_room_id(room_alias)
        resp = await self._client.join(resolved)
        if isinstance(resp, nio.JoinError):
            logger.error("Failed to join room %r: %s", room_alias, resp.message)
            return None
        info = RoomInfo(room_id=resp.room_id, alias=room_alias)
        self._room_cache[room_alias] = info
        logger.debug("Joined room %r -> %s", room_alias, resp.room_id)
        return info

    async def create_room(
        self,
        alias: str,
        name: str,
        topic: str = "",
        is_public: bool = False,
        encrypted: bool = False,
    ) -> Optional[RoomInfo]:
        """Create a new Matrix room and return its :class:`RoomInfo`."""
        if not self._client:
            raise MatrixClientError("Not connected")
        initial_state: List[Dict[str, Any]] = []
        if encrypted:
            initial_state.append(
                {
                    "type": "m.room.encryption",
                    "state_key": "",
                    "content": {"algorithm": "m.megolm.v1.aes-sha2"},
                }
            )
        resp = await self._client.room_create(
            alias=alias,
            name=name,
            topic=topic,
            is_direct=False,
            preset=(
                nio.RoomPreset.public_chat
                if is_public
                else nio.RoomPreset.private_chat
            ),
            initial_state=initial_state,
        )
        if isinstance(resp, nio.RoomCreateError):
            logger.error("Failed to create room %r: %s", alias, resp.message)
            return None
        info = RoomInfo(room_id=resp.room_id, alias=alias, display_name=name)
        self._room_cache[alias] = info
        logger.debug("Created room %r -> %s", alias, resp.room_id)
        return info

    async def invite_user(self, room_alias: str, user_id: str) -> bool:
        """Invite *user_id* to the room identified by *room_alias*."""
        if not self._client:
            raise MatrixClientError("Not connected")
        room_id = self._resolve_room_id(room_alias)
        resp = await self._client.room_invite(room_id, user_id)
        if isinstance(resp, nio.RoomInviteError):
            logger.error(
                "Failed to invite %r to %r: %s", user_id, room_alias, resp.message
            )
            return False
        return True

    # Message sending (with retry)

    async def send_message(
        self, room_alias: str, content: MessageContent
    ) -> SendResult:
        """Send a Matrix room message with automatic retry."""
        if not self._client:
            return SendResult(
                success=False,
                room_alias=room_alias,
                error="Not connected",
            )
        room_id = self._resolve_room_id(room_alias)
        cfg = self._config
        last_error = ""
        for attempt in range(cfg.max_retries + 1):
            try:
                resp = await self._client.room_send(
                    room_id=room_id,
                    message_type=content.msgtype,
                    content=content.to_content_dict(),
                )
                if isinstance(resp, nio.RoomSendError):
                    last_error = resp.message
                    logger.warning(
                        "Send attempt %d/%d failed for %r: %s",
                        attempt + 1,
                        cfg.max_retries + 1,
                        room_alias,
                        resp.message,
                    )
                    await asyncio.sleep(cfg.retry_delay_seconds * (2**attempt))
                    continue
                return SendResult(
                    success=True,
                    event_id=resp.event_id,
                    room_alias=room_alias,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Send attempt %d/%d raised: %s",
                    attempt + 1,
                    cfg.max_retries + 1,
                    exc,
                )
                await asyncio.sleep(cfg.retry_delay_seconds * (2**attempt))

        return SendResult(success=False, room_alias=room_alias, error=last_error)

# Mock client (no network I/O)

@dataclass
class _MockSentMessage:
    room_alias: str
    content: MessageContent
    timestamp: float = field(default_factory=time.time)

class MockMatrixClient(_MatrixClientBase):
    """In-memory Matrix client stub for testing and offline environments.

    Stores all sent messages in :attr:`sent_messages` for inspection.
    No network connections are made.
    """

    def __init__(self, config: MatrixConfig) -> None:
        super().__init__(config)
        self.sent_messages: List[_MockSentMessage] = []
        self.joined_rooms: List[str] = []
        self.created_rooms: List[RoomInfo] = []
        self._connected = False
        self._event_counter = 0

    async def connect(self) -> None:
        self._connected = True
        logger.debug("MockMatrixClient: connected (offline mode)")

    async def close(self) -> None:
        self._connected = False
        logger.debug("MockMatrixClient: closed")

    def is_connected(self) -> bool:
        return self._connected

    async def start_sync(self) -> None:
        logger.debug("MockMatrixClient: start_sync() is a no-op in mock mode")

    async def send_message(
        self, room_alias: str, content: MessageContent
    ) -> SendResult:
        self._event_counter += 1
        event_id = f"$mock-event-{self._event_counter}"
        self.sent_messages.append(_MockSentMessage(room_alias=room_alias, content=content))
        logger.debug("MockMatrixClient: sent to %r: %r", room_alias, content.text[:80])
        return SendResult(success=True, event_id=event_id, room_alias=room_alias)

    async def join_room(self, room_alias: str) -> Optional[RoomInfo]:
        self.joined_rooms.append(room_alias)
        info = RoomInfo(room_id=f"!mock-{room_alias}", alias=room_alias)
        self._room_cache[room_alias] = info
        return info

    async def create_room(
        self,
        alias: str,
        name: str,
        topic: str = "",
        is_public: bool = False,
        encrypted: bool = False,
    ) -> Optional[RoomInfo]:
        info = RoomInfo(room_id=f"!mock-{alias}", alias=alias, display_name=name)
        self._room_cache[alias] = info
        self.created_rooms.append(info)
        return info

    async def invite_user(self, room_alias: str, user_id: str) -> bool:
        logger.debug("MockMatrixClient: invited %r to %r", user_id, room_alias)
        return True

# Factory

def create_client(config: MatrixConfig) -> _MatrixClientBase:
    """Return a real or mock Matrix client based on *config*.

    If ``matrix-nio`` is available **and** the config has a non-empty
    ``access_token``, a :class:`_NioMatrixClient` is returned.  Otherwise a
    :class:`MockMatrixClient` is returned so the rest of the bridge can
    function in offline / test mode without raising at import time.
    """
    if _HAS_NIO and config.access_token:
        logger.info("Creating real MatrixClient (matrix-nio backend)")
        return _NioMatrixClient(config)
    mode = "no access token" if not config.access_token else "matrix-nio not installed"
    logger.warning(
        "Creating MockMatrixClient (%s); bridge operates in offline mode.", mode
    )
    return MockMatrixClient(config)

__all__ = [
    "MatrixClient",
    "MatrixClientError",
    "MessageContent",
    "SendResult",
    "RoomInfo",
    "MockMatrixClient",
    "create_client",
    "_CircuitBreaker",
    "_CircuitState",
    "_NioMatrixClient",
    "_MatrixClientBase",
]
