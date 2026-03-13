# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Matrix Client Wrapper — MTX-CLIENT-001

Owner: Platform Engineering · Dep: matrix_config (MatrixConfig)

Core Matrix client wrapper for the Murphy System bridge.  Uses
``matrix-nio`` (async) when available and falls back to a lightweight
HTTP-only mock client for environments where ``nio`` is not installed
(e.g. test environments without network access).

Classes
-------
MatrixClientError : Exception
    Raised on unrecoverable Matrix API errors.
MessageContent : dataclass
    Structured message payload (plain text + optional HTML body).
SendResult : dataclass
    Result returned from :meth:`MatrixClient.send_message`.
MatrixClient : class
    Async Matrix client wrapper — connect, join rooms, send/receive.
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
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .matrix_config import MatrixConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional matrix-nio import
# ---------------------------------------------------------------------------
try:
    import nio  # type: ignore[import-untyped]

    _HAS_NIO = True
except ImportError:  # pragma: no cover
    _HAS_NIO = False
    nio = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Optional aiohttp import (used for raw HTTP fallback)
# ---------------------------------------------------------------------------
try:
    import aiohttp  # type: ignore[import-untyped]

    _HAS_AIOHTTP = True
except ImportError:  # pragma: no cover
    _HAS_AIOHTTP = False
    aiohttp = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MatrixClientError(Exception):
    """Raised on unrecoverable Matrix API or connection errors."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Base interface (for type-checking mock vs real)
# ---------------------------------------------------------------------------


class _MatrixClientBase(abc.ABC):
    """Shared interface for real and mock Matrix clients."""

    def __init__(self, config: MatrixConfig) -> None:
        self._config = config
        self._event_handlers: Dict[str, List[Callable[..., Any]]] = {}
        self._room_cache: Dict[str, RoomInfo] = {}

    # -----------------------------------------------------------------------
    # Event handler registration
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Async context manager
    # -----------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Real Matrix client (nio-backed)
# ---------------------------------------------------------------------------


class MatrixClient(_MatrixClientBase):
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

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Sync
    # -----------------------------------------------------------------------

    async def start_sync(self) -> None:
        """Start the background sync loop (non-blocking)."""
        if not self._client:
            raise MatrixClientError("Not connected — call connect() first")
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def _sync_loop(self) -> None:
        """Internal sync loop — runs until cancelled."""
        assert self._client is not None
        await self._client.sync_forever(timeout=30000, full_state=True)

    # -----------------------------------------------------------------------
    # Event callbacks
    # -----------------------------------------------------------------------

    async def _on_message_event(
        self, room: Any, event: Any
    ) -> None:
        await self._dispatch("m.room.message", {"room": room, "event": event})

    async def _on_room_event(
        self, room: Any, event: Any
    ) -> None:
        event_type = getattr(event, "type", "unknown")
        await self._dispatch(event_type, {"room": room, "event": event})

    # -----------------------------------------------------------------------
    # Room operations
    # -----------------------------------------------------------------------

    def _resolve_room_id(self, room_alias: str) -> str:
        """Return the Matrix room ID from alias cache, or the alias itself."""
        info = self._room_cache.get(room_alias)
        if info:
            return info.room_id
        # Treat the alias as a raw room id / alias if not cached
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
        logger.debug("Joined room %r → %s", room_alias, resp.room_id)
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
        logger.debug("Created room %r → %s", alias, resp.room_id)
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

    # -----------------------------------------------------------------------
    # Message sending (with retry)
    # -----------------------------------------------------------------------

    async def send_message(
        self, room_alias: str, content: MessageContent
    ) -> SendResult:
        """Send a Matrix room message with automatic retry.

        Parameters
        ----------
        room_alias:
            Short alias or full Matrix room alias / ID.
        content:
            :class:`MessageContent` describing the message to send.

        Returns
        -------
        SendResult
            Indicates success/failure and the assigned event ID.
        """
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


# ---------------------------------------------------------------------------
# Mock client (no network I/O)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_client(config: MatrixConfig) -> _MatrixClientBase:
    """Return a real or mock Matrix client based on *config*.

    If ``matrix-nio`` is available **and** the config has a non-empty
    ``access_token``, a :class:`MatrixClient` is returned.  Otherwise a
    :class:`MockMatrixClient` is returned so the rest of the bridge can
    function in offline / test mode without raising at import time.
    """
    if _HAS_NIO and config.access_token:
        logger.info("Creating real MatrixClient (matrix-nio backend)")
        return MatrixClient(config)
    mode = "no access token" if not config.access_token else "matrix-nio not installed"
    logger.warning(
        "Creating MockMatrixClient (%s); bridge operates in offline mode.", mode
    )
    return MockMatrixClient(config)
