# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Matrix Event Handler — MTX-EVT-001

Owner: Platform Engineering · Dep: message_router, bot_bridge_adapter

Handles incoming Matrix events (messages, state changes, reactions) and
dispatches them to the appropriate Murphy System module handlers.

Classes
-------
MatrixEventType : Enum
    Known Matrix event type strings mapped to friendly names.
IncomingEvent : dataclass
    Normalised representation of a Matrix event received by the bridge.
EventHandlerResult : dataclass
    Result returned by a handler after processing an event.
MatrixEventHandler : class
    Wires raw Matrix events → command parser → Murphy subsystem dispatch.

Usage::

    from matrix_bridge.matrix_event_handler import MatrixEventHandler

    handler = MatrixEventHandler(router=my_router, adapter=my_adapter)

    # Register a custom Murphy module handler
    @handler.on_command("security")
    async def handle_security(event: IncomingEvent) -> EventHandlerResult:
        result = await security_scanner.scan()
        return EventHandlerResult(reply=str(result))

    # Process a raw Matrix message event dict
    await handler.process_event(raw_event_dict)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .bot_bridge_adapter import BotBridgeAdapter
from .message_router import CommandParseResult, MessageRouter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MatrixEventType(Enum):
    """Known Matrix event types handled by the bridge."""

    ROOM_MESSAGE = "m.room.message"
    ROOM_REACTION = "m.reaction"
    ROOM_MEMBER = "m.room.member"
    ROOM_NAME = "m.room.name"
    ROOM_TOPIC = "m.room.topic"
    ROOM_ENCRYPTED = "m.room.encrypted"
    SPACE_CHILD = "m.space.child"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "MatrixEventType":
        for member in cls:
            if member.value == value:
                return member
        return cls.UNKNOWN


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class IncomingEvent:
    """Normalised representation of an inbound Matrix event.

    Attributes
    ----------
    event_type:
        :class:`MatrixEventType` indicating what kind of event this is.
    sender_id:
        Matrix user ID of the event sender.
    room_alias:
        Alias of the room the event occurred in.
    room_id:
        Raw Matrix room ID.
    body:
        Plain-text body of the message (if applicable).
    html_body:
        HTML-formatted body (if present in the original event).
    event_id:
        Unique Matrix event ID.
    raw:
        The original unmodified event dict as received from the client.
    parsed_command:
        Populated by :meth:`MatrixEventHandler.process_event` if the body
        is a ``!murphy`` command.
    """

    event_type: MatrixEventType = MatrixEventType.UNKNOWN
    sender_id: str = ""
    room_alias: str = ""
    room_id: str = ""
    body: str = ""
    html_body: str = ""
    event_id: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    parsed_command: Optional[CommandParseResult] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], room_alias: str = "") -> "IncomingEvent":
        """Construct from a raw Matrix event dict."""
        event_type_str = data.get("type", "unknown")
        event_type = MatrixEventType.from_string(event_type_str)
        content = data.get("content", {})
        body = content.get("body", "")
        html_body = content.get("formatted_body", "")
        return cls(
            event_type=event_type,
            sender_id=data.get("sender", ""),
            room_alias=room_alias,
            room_id=data.get("room_id", ""),
            body=body,
            html_body=html_body,
            event_id=data.get("event_id", ""),
            raw=data,
        )


@dataclass
class EventHandlerResult:
    """Result returned by an event or command handler.

    Attributes
    ----------
    reply:
        Optional reply text to send back to the room.
    reply_html:
        Optional HTML version of the reply.
    handled:
        Whether the event was fully handled.
    error:
        Error message if handling failed.
    """

    reply: Optional[str] = None
    reply_html: Optional[str] = None
    handled: bool = True
    error: str = ""


# ---------------------------------------------------------------------------
# MatrixEventHandler
# ---------------------------------------------------------------------------


class MatrixEventHandler:
    """Dispatches inbound Matrix events to Murphy System module handlers.

    Parameters
    ----------
    router:
        :class:`~message_router.MessageRouter` for outbound delivery and
        command parsing.
    adapter:
        :class:`~bot_bridge_adapter.BotBridgeAdapter` for bot-attributed
        replies.
    """

    def __init__(
        self,
        router: MessageRouter,
        adapter: Optional[BotBridgeAdapter] = None,
    ) -> None:
        self._router = router
        self._adapter = adapter
        # event_type_str → list of handlers
        self._event_handlers: Dict[str, List[Callable[[IncomingEvent], Any]]] = {}
        # command_token → handler
        self._command_handlers: Dict[str, Callable[[IncomingEvent], Any]] = {}
        # Ignored sender IDs (e.g. the bridge bot itself)
        self._ignored_senders: set[str] = set()

    # -----------------------------------------------------------------------
    # Handler registration
    # -----------------------------------------------------------------------

    def on_event(
        self, event_type: str
    ) -> Callable[[Callable[[IncomingEvent], Any]], Callable[[IncomingEvent], Any]]:
        """Decorator: register *fn* as a handler for *event_type* events."""

        def decorator(
            fn: Callable[[IncomingEvent], Any]
        ) -> Callable[[IncomingEvent], Any]:
            self._event_handlers.setdefault(event_type, []).append(fn)
            return fn

        return decorator

    def on_command(
        self, command: str
    ) -> Callable[[Callable[[IncomingEvent], Any]], Callable[[IncomingEvent], Any]]:
        """Decorator: register *fn* as a handler for the ``!murphy <command>`` token."""

        def decorator(
            fn: Callable[[IncomingEvent], Any]
        ) -> Callable[[IncomingEvent], Any]:
            self._command_handlers[command.lower()] = fn
            return fn

        return decorator

    def add_event_handler(
        self, event_type: str, handler: Callable[[IncomingEvent], Any]
    ) -> None:
        """Register *handler* for *event_type* programmatically."""
        self._event_handlers.setdefault(event_type, []).append(handler)

    def add_command_handler(
        self, command: str, handler: Callable[[IncomingEvent], Any]
    ) -> None:
        """Register *handler* for command token *command* programmatically."""
        self._command_handlers[command.lower()] = handler

    def ignore_sender(self, sender_id: str) -> None:
        """Prevent events from *sender_id* from being dispatched (e.g. the bot itself)."""
        self._ignored_senders.add(sender_id)

    # -----------------------------------------------------------------------
    # Event processing
    # -----------------------------------------------------------------------

    async def process_event(
        self,
        raw: Dict[str, Any],
        room_alias: str = "",
    ) -> Optional[EventHandlerResult]:
        """Parse and dispatch a raw Matrix event dict.

        Returns an :class:`EventHandlerResult` if a handler ran, else ``None``.
        """
        event = IncomingEvent.from_dict(raw, room_alias=room_alias)
        return await self.handle(event)

    async def handle(self, event: IncomingEvent) -> Optional[EventHandlerResult]:
        """Dispatch a normalised :class:`IncomingEvent` to handlers.

        Processing order:
        1. Ignore events from blacklisted senders.
        2. Run all registered event-type handlers.
        3. If the event is a room message, attempt command parsing.
        4. If a command is found, run the command handler.
        """
        if event.sender_id in self._ignored_senders:
            return None

        # Run generic event-type handlers
        type_key = event.event_type.value
        result: Optional[EventHandlerResult] = None
        for handler in self._event_handlers.get(type_key, []):
            try:
                res = handler(event)
                if asyncio.iscoroutine(res):
                    res = await res
                if isinstance(res, EventHandlerResult):
                    result = res
            except Exception:
                logger.exception("Event handler raised an exception for %r", type_key)

        # Command handling only for room messages
        if event.event_type == MatrixEventType.ROOM_MESSAGE and event.body:
            cmd_result = await self._handle_command(event)
            if cmd_result is not None:
                result = cmd_result

        return result

    async def _handle_command(
        self, event: IncomingEvent
    ) -> Optional[EventHandlerResult]:
        """Parse *event.body* as a command and dispatch to the handler."""
        parsed = self._router.parse_command(
            body=event.body,
            sender_id=event.sender_id,
            room_alias=event.room_alias,
        )
        if not parsed:
            return None

        event.parsed_command = parsed
        logger.info(
            "Command %r.%r received from %r in %r",
            parsed.command,
            parsed.subcommand,
            parsed.sender_id,
            parsed.room_alias,
        )

        # Check for a specific command handler
        cmd_handler = self._command_handlers.get(parsed.command)
        if cmd_handler:
            try:
                res = cmd_handler(event)
                if asyncio.iscoroutine(res):
                    res = await res
                if isinstance(res, EventHandlerResult):
                    return res
                # Handler returned a plain string
                if isinstance(res, str):
                    return EventHandlerResult(reply=res)
                return EventHandlerResult(handled=True)
            except Exception as exc:
                logger.exception(
                    "Command handler for %r raised: %s", parsed.command, exc
                )
                return EventHandlerResult(
                    handled=True,
                    error=str(exc),
                    reply=f"⚠️ Error processing command: {exc}",
                )

        # Fallback: dispatch via router
        dispatch_result = await self._router.dispatch_command(parsed)
        if isinstance(dispatch_result, str):
            return EventHandlerResult(reply=dispatch_result)
        if dispatch_result is not None:
            return EventHandlerResult(handled=True)
        return None

    # -----------------------------------------------------------------------
    # Reply helpers
    # -----------------------------------------------------------------------

    async def reply(
        self,
        event: IncomingEvent,
        text: str,
        html: Optional[str] = None,
        bot_name: str = "TriageBot",
    ) -> None:
        """Send a reply to the room *event* came from.

        If an adapter is available, the reply is attributed to *bot_name*.
        """
        room = event.room_alias or "murphy-general"
        if self._adapter:
            await self._adapter.send_as_bot(
                bot_name=bot_name, text=text, html=html, room_alias=room
            )
        else:
            from .matrix_client import MessageContent  # local import

            content = MessageContent(text=text, html=html)
            await self._router._client.send_message(  # noqa: SLF001
                room_alias=room, content=content
            )

    # -----------------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------------

    def stats(self) -> Dict[str, object]:
        """Return handler statistics for monitoring."""
        return {
            "event_handler_types": list(self._event_handlers.keys()),
            "command_handlers": list(self._command_handlers.keys()),
            "ignored_senders": len(self._ignored_senders),
        }
