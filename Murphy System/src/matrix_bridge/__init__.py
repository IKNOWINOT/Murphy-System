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
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Matrix Bridge — MTX-INIT-001

Owner: Platform Engineering

Matrix Communication Bridge Foundation for the Murphy System.
This package provides the core integration layer that all Murphy
subsystems connect through to communicate via Matrix.

Sub-modules
-----------
matrix_config
    Configuration dataclasses (homeserver URL, tokens, room mappings).
matrix_client
    Async Matrix client wrapper (``matrix-nio`` backed with mock fallback).
room_topology
    Canonical Matrix space / room hierarchy mapping all HiveMind bot domains.
message_router
    Routes messages between Murphy subsystems and Matrix rooms; parses
    ``!murphy`` commands.
bot_bridge_adapter
    Translates HiveMind bot personas to Matrix virtual users.
matrix_event_handler
    Dispatches inbound Matrix events to Murphy module handlers.
subsystem_registry
    Comprehensive registry mapping every ``src/`` module to its Matrix room.
monday_features
    Monday.com-inspired boards, status tracking, dashboards, and automations.

Quick start::

    from src.matrix_bridge import (
        MatrixConfig,
        MatrixBridgeSettings,
        MurphyRoomTopology,
        MessageRouter,
        BotBridgeAdapter,
        MatrixEventHandler,
        SubsystemRegistry,
        BoardManager,
        DashboardManager,
        create_client,
        get_topology,
        get_registry,
        get_settings,
    )

    settings = MatrixBridgeSettings.from_env()
    async with create_client(settings.matrix) as client:
        topology = get_topology()
        router = MessageRouter(settings=settings, client=client)
        adapter = BotBridgeAdapter(client=client, router=router)
        handler = MatrixEventHandler(router=router, adapter=adapter)

        await router.route_to_room("security_audit_scanner", "⚠️ Threat found!")
"""
from __future__ import annotations

from .bot_bridge_adapter import (
    BotBridgeAdapter,
    BotPersona,
    get_adapter,
    reset_adapter,
)
from .matrix_client import (
    MatrixClient,
    MatrixClientError,
    MessageContent,
    MockMatrixClient,
    SendResult,
    create_client,
)
from .matrix_config import (
    MatrixBridgeSettings,
    MatrixConfig,
    RoomMappingConfig,
    get_settings,
    reset_settings,
)
from .matrix_event_handler import (
    EventHandlerResult,
    IncomingEvent,
    MatrixEventHandler,
    MatrixEventType,
)
from .message_router import (
    CommandParseResult,
    MessagePriority,
    MessageRouter,
    QueuedMessage,
    RoutingEntry,
)
from .monday_features import (
    AutomationEngine,
    AutomationTrigger,
    BoardItem,
    BoardManager,
    ColumnType,
    DashboardManager,
    ItemPriority,
    ItemStatus,
    MurphyBoard,
)
from .room_topology import (
    MurphyRoomTopology,
    RoomDefinition,
    RoomType,
    SpaceDefinition,
    get_topology,
    reset_topology,
)
from .subsystem_registry import (
    SubsystemDomain,
    SubsystemEntry,
    SubsystemRegistry,
    get_registry,
    reset_registry,
)

__all__ = [
    # Config
    "MatrixConfig",
    "MatrixBridgeSettings",
    "RoomMappingConfig",
    "get_settings",
    "reset_settings",
    # Client
    "MatrixClient",
    "MockMatrixClient",
    "MatrixClientError",
    "MessageContent",
    "SendResult",
    "create_client",
    # Topology
    "MurphyRoomTopology",
    "SpaceDefinition",
    "RoomDefinition",
    "RoomType",
    "get_topology",
    "reset_topology",
    # Router
    "MessageRouter",
    "CommandParseResult",
    "RoutingEntry",
    "MessagePriority",
    "QueuedMessage",
    # Bot adapter
    "BotBridgeAdapter",
    "BotPersona",
    "get_adapter",
    "reset_adapter",
    # Event handler
    "MatrixEventHandler",
    "IncomingEvent",
    "MatrixEventType",
    "EventHandlerResult",
    # Subsystem registry
    "SubsystemRegistry",
    "SubsystemEntry",
    "SubsystemDomain",
    "get_registry",
    "reset_registry",
    # Monday features
    "BoardManager",
    "DashboardManager",
    "AutomationEngine",
    "AutomationTrigger",
    "MurphyBoard",
    "BoardItem",
    "ColumnType",
    "ItemStatus",
    "ItemPriority",
# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Murphy System — Matrix Bridge Package.

Provides a comprehensive Matrix integration layer that makes every Murphy
module and subsystem accessible via Matrix rooms, commands, and events.

Public API
----------
MatrixClient           — homeserver connection wrapper (matrix_client)
RoomRegistry           — subsystem→room mapping (room_registry)
CommandRouter          — ``!murphy`` command dispatcher (command_router)
EventBridge            — Murphy events → Matrix notifications (event_bridge)
BotPersonas / Persona  — named bot personalities (bot_personas)
SpaceManager           — Matrix Spaces hierarchy (space_manager)
HITLMatrixAdapter      — Human-in-the-loop via Matrix (hitl_matrix_adapter)
WebhookReceiver        — inbound webhook → Matrix fan-out (webhook_receiver)
MODULE_MANIFEST        — complete module→room manifest (module_manifest)
startup                — async startup helper (startup)
"""

from __future__ import annotations

from .matrix_client import MatrixClient
from .room_registry import RoomRegistry, SUBSYSTEM_ROOMS
from .command_router import CommandRouter
from .event_bridge import EventBridge
from .bot_personas import BotPersonas, Persona
from .space_manager import SpaceManager
from .hitl_matrix_adapter import HITLMatrixAdapter
from .webhook_receiver import WebhookReceiver
from .module_manifest import MODULE_MANIFEST

__all__ = [
    "MatrixClient",
    "RoomRegistry",
    "SUBSYSTEM_ROOMS",
    "CommandRouter",
    "EventBridge",
    "BotPersonas",
    "Persona",
    "SpaceManager",
    "HITLMatrixAdapter",
    "WebhookReceiver",
    "MODULE_MANIFEST",
]
