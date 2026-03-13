# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Murphy System — Matrix Bridge Package.

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
- :class:`~room_registry.RoomRegistry` — subsystem→room mapping
- :class:`~command_router.CommandRouter` — ``!murphy`` command dispatcher
- :class:`~event_bridge.EventBridge` — Murphy events → Matrix notifications
- :class:`~bot_personas.BotPersonas` — named bot personalities
- :class:`~space_manager.SpaceManager` — Matrix Spaces hierarchy
- :class:`~hitl_matrix_adapter.HITLMatrixAdapter` — Human-in-the-loop via Matrix

.. note::
    Network calls to the Matrix homeserver are **stubbed** in this
    release.  Real delivery will be wired via the ``matrix-nio`` SDK in
    a subsequent PR.
"""

from __future__ import annotations

__version__ = "0.1.0"
__codename__ = "Bridge Layer"

# PR #208 — Application Service layer
from .appservice import AppService, AppserviceRegistration, AppServiceState
from .auth_bridge import COMMAND_ROLE_REQUIREMENTS, AuthBridge, MurphyRole, UserMapping

# PR #207 — Communication Bridge Foundation
from .bot_bridge_adapter import (
    BotBridgeAdapter,
    BotPersona,
    get_adapter,
    reset_adapter,
)
from .bot_personas import BotPersonas, Persona
from .command_dispatcher import CommandDispatcher, CommandResponse, ParsedCommand
from .command_router import CommandRouter
from .config import (
    DEFAULT_ROOM_DEFINITIONS,
    MatrixBridgeConfig,
    RoomMapping,
    build_default_config,
)
from .e2ee_manager import E2EEManager, E2EEState, MegolmSession, OlmSession
from .event_bridge import EventBridge
from .event_streamer import EVENT_FORMAT_TEMPLATES, EventStreamer, StreamedEvent
from .hitl_matrix_adapter import HITLMatrixAdapter
from .management_features import (
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
from .media_handler import MediaHandler, MediaType, MediaUpload
from .message_router import (
    CommandParseResult,
    MessagePriority,
    MessageRouter,
    QueuedMessage,
    RoutingEntry,
)
from .module_manifest import MODULE_MANIFEST

# PR #206 — Integration Layer
from .room_registry import SUBSYSTEM_ROOMS, RoomRegistry
from .room_router import MODULE_TO_ROOM, RoomRouter
from .room_topology import (
    MurphyRoomTopology,
    RoomDefinition,
    RoomType,
    SpaceDefinition,
    get_topology,
    reset_topology,
)
from .space_manager import SpaceManager
from .subsystem_registry import (
    SubsystemDomain,
    SubsystemEntry,
    SubsystemRegistry,
    get_registry,
    reset_registry,
)
from .webhook_receiver import WebhookEvent, WebhookEventType, WebhookReceiver

__all__ = [
    # Package metadata
    "__version__",
    "__codename__",
    # PR #208 — config
    "MatrixBridgeConfig",
    "RoomMapping",
    "DEFAULT_ROOM_DEFINITIONS",
    "build_default_config",
    # PR #208 — room_router
    "RoomRouter",
    "MODULE_TO_ROOM",
    # PR #208 — command_dispatcher
    "CommandDispatcher",
    "ParsedCommand",
    "CommandResponse",
    # PR #208 — event_streamer
    "EventStreamer",
    "StreamedEvent",
    "EVENT_FORMAT_TEMPLATES",
    # PR #208 — auth_bridge
    "AuthBridge",
    "UserMapping",
    "MurphyRole",
    "COMMAND_ROLE_REQUIREMENTS",
    # PR #208 — media_handler
    "MediaHandler",
    "MediaUpload",
    "MediaType",
    # PR #208 — e2ee_manager
    "E2EEManager",
    "OlmSession",
    "MegolmSession",
    "E2EEState",
    # PR #208 — appservice
    "AppService",
    "AppserviceRegistration",
    "AppServiceState",
    # PR #208 — webhook_receiver
    "WebhookReceiver",
    "WebhookEvent",
    "WebhookEventType",
    # PR #207 — Config
    "MatrixConfig",
    "MatrixBridgeSettings",
    "RoomMappingConfig",
    "get_settings",
    "reset_settings",
    # PR #207 — Client
    "MatrixClient",
    "MockMatrixClient",
    "MatrixClientError",
    "MessageContent",
    "SendResult",
    "create_client",
    # PR #207 — Topology
    "MurphyRoomTopology",
    "SpaceDefinition",
    "RoomDefinition",
    "RoomType",
    "get_topology",
    "reset_topology",
    # PR #207 — Router
    "MessageRouter",
    "CommandParseResult",
    "RoutingEntry",
    "MessagePriority",
    "QueuedMessage",
    # PR #207 — Bot adapter
    "BotBridgeAdapter",
    "BotPersona",
    "get_adapter",
    "reset_adapter",
    # PR #207 — Event handler
    "MatrixEventHandler",
    "IncomingEvent",
    "MatrixEventType",
    "EventHandlerResult",
    # PR #207 — Subsystem registry
    "SubsystemRegistry",
    "SubsystemEntry",
    "SubsystemDomain",
    "get_registry",
    "reset_registry",
    # PR #207 — Monday features
    "BoardManager",
    "DashboardManager",
    "AutomationEngine",
    "AutomationTrigger",
    "MurphyBoard",
    "BoardItem",
    "ColumnType",
    "ItemStatus",
    "ItemPriority",
    # PR #206 — Integration layer
    "RoomRegistry",
    "SUBSYSTEM_ROOMS",
    "CommandRouter",
    "EventBridge",
    "BotPersonas",
    "Persona",
    "SpaceManager",
    "HITLMatrixAdapter",
    "MODULE_MANIFEST",
]
