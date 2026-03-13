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
