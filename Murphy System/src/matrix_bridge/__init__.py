"""
Murphy System — Matrix Bridge Package.

This package implements the Matrix Application Service (AS) bridge that
connects every Murphy subsystem to Matrix chat rooms.  It provides:

- :class:`~config.MatrixBridgeConfig` — centralised configuration
- :class:`~room_router.RoomRouter` — maps 200+ modules to Matrix rooms
- :class:`~command_dispatcher.CommandDispatcher` — ``!murphy`` command handler
- :class:`~event_streamer.EventStreamer` — routes Murphy events to rooms
- :class:`~auth_bridge.AuthBridge` — Matrix ↔ Murphy RBAC mapping
- :class:`~media_handler.MediaHandler` — artifact upload management
- :class:`~e2ee_manager.E2EEManager` — Olm/Megolm session stubs
- :class:`~appservice.AppService` — Matrix AS entry point
- :class:`~webhook_receiver.WebhookReceiver` — inbound webhook ingestion

.. note::
    Network calls to the Matrix homeserver are **stubbed** in this
    release.  Real delivery will be wired via the ``matrix-nio`` SDK in
    a subsequent PR.

Example::

    from src.matrix_bridge import build_default_config, AppService, RoomRouter
    from src.matrix_bridge import CommandDispatcher, EventStreamer, AuthBridge

    cfg = build_default_config("myorg.chat")
    router = RoomRouter(cfg)
    auth = AuthBridge(cfg)
    dispatcher = CommandDispatcher(cfg, router)
    streamer = EventStreamer(cfg, router)
    service = AppService(cfg, router, dispatcher, streamer, auth)
    service.start()
"""

from __future__ import annotations

__version__ = "0.1.0"
__codename__ = "Bridge Layer"

from .appservice import AppService, AppserviceRegistration, AppServiceState
from .auth_bridge import AuthBridge, COMMAND_ROLE_REQUIREMENTS, MurphyRole, UserMapping
from .command_dispatcher import CommandDispatcher, CommandResponse, ParsedCommand
from .config import (
    DEFAULT_ROOM_DEFINITIONS,
    MatrixBridgeConfig,
    RoomMapping,
    build_default_config,
)
from .e2ee_manager import E2EEManager, E2EEState, MegolmSession, OlmSession
from .event_streamer import EVENT_FORMAT_TEMPLATES, EventStreamer, StreamedEvent
from .media_handler import MediaHandler, MediaType, MediaUpload
from .room_router import MODULE_TO_ROOM, RoomRouter
from .webhook_receiver import WebhookEvent, WebhookEventType, WebhookReceiver

__all__ = [
    # Package metadata
    "__version__",
    "__codename__",
    # config
    "MatrixBridgeConfig",
    "RoomMapping",
    "DEFAULT_ROOM_DEFINITIONS",
    "build_default_config",
    # room_router
    "RoomRouter",
    "MODULE_TO_ROOM",
    # command_dispatcher
    "CommandDispatcher",
    "ParsedCommand",
    "CommandResponse",
    # event_streamer
    "EventStreamer",
    "StreamedEvent",
    "EVENT_FORMAT_TEMPLATES",
    # auth_bridge
    "AuthBridge",
    "UserMapping",
    "MurphyRole",
    "COMMAND_ROLE_REQUIREMENTS",
    # media_handler
    "MediaHandler",
    "MediaUpload",
    "MediaType",
    # e2ee_manager
    "E2EEManager",
    "OlmSession",
    "MegolmSession",
    "E2EEState",
    # appservice
    "AppService",
    "AppserviceRegistration",
    "AppServiceState",
    # webhook_receiver
    "WebhookReceiver",
    "WebhookEvent",
    "WebhookEventType",
]
