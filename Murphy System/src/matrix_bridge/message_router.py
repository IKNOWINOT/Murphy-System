# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Message Router — MTX-ROUTER-001

Owner: Platform Engineering · Dep: room_topology, matrix_client

Routes messages between Murphy System subsystems and Matrix rooms.
Translates legacy ``/command``-style commands (Discord/HiveMind) to
``!murphy``-style Matrix commands, dispatches events to the appropriate
Murphy module handlers, and maintains a priority queue for critical alerts.

Classes
-------
CommandParseResult : dataclass
    Parsed command extracted from a Matrix message body.
RoutingEntry : dataclass
    Maps a subsystem name to its target room alias.
MessagePriority : Enum
    Priority levels for outgoing messages.
QueuedMessage : dataclass
    A message pending delivery, with priority and metadata.
MessageRouter : class
    Core routing engine — subsystem → room, command parsing, dispatch.

Usage::

    from matrix_bridge.message_router import MessageRouter
    from matrix_bridge.matrix_config import MatrixBridgeSettings

    settings = MatrixBridgeSettings.from_env()
    router = MessageRouter(settings=settings, client=my_client)

    # Route a message from a subsystem
    await router.route_to_room("security_audit_scanner", "⚠️ Threat detected!")

    # Parse a Matrix command
    result = router.parse_command("!murphy security scan --full")
    if result:
        await router.dispatch_command(result)
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .matrix_client import MessageContent, SendResult, _MatrixClientBase
from .matrix_config import MatrixBridgeSettings
from .room_topology import MurphyRoomTopology, get_topology

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MessagePriority(Enum):
    """Priority levels used by the internal message queue."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CommandParseResult:
    """Parsed command extracted from a Matrix room message.

    Attributes
    ----------
    raw:
        The original, unmodified message body.
    command:
        Primary command token, e.g. ``"security"``.
    subcommand:
        Secondary token, e.g. ``"scan"``.
    args:
        Remaining positional arguments.
    flags:
        Named flags extracted from ``--flag value`` pairs.
    sender_id:
        Matrix user ID of the message author.
    room_alias:
        Alias of the room the command was received in.
    """

    raw: str
    command: str = ""
    subcommand: str = ""
    args: List[str] = field(default_factory=list)
    flags: Dict[str, str] = field(default_factory=dict)
    sender_id: str = ""
    room_alias: str = ""


@dataclass
class RoutingEntry:
    """Maps a Murphy subsystem name to a Matrix room alias.

    Attributes
    ----------
    subsystem_name:
        Canonical Murphy module/subsystem name.
    room_alias:
        Target Matrix room alias for messages from this subsystem.
    priority:
        Default priority for messages from this subsystem.
    fallback_alias:
        Room alias used if the primary room is unavailable.
    """

    subsystem_name: str
    room_alias: str
    priority: MessagePriority = MessagePriority.NORMAL
    fallback_alias: str = "murphy-general"


@dataclass
class QueuedMessage:
    """A message pending delivery via the priority queue."""

    priority: MessagePriority
    room_alias: str
    content: MessageContent
    subsystem: str = ""
    queued_at: float = field(default_factory=time.time)
    attempt: int = 0

    def __lt__(self, other: "QueuedMessage") -> bool:
        return self.priority.value < other.priority.value


# ---------------------------------------------------------------------------
# Command-to-subsystem dispatch table
# ---------------------------------------------------------------------------

#: Maps ``!murphy <command>`` tokens to subsystem handler keys.
_COMMAND_DISPATCH_TABLE: Dict[str, str] = {
    "status": "health_monitor",
    "health": "health_monitor",
    "triage": "triage_rollcall_adapter",
    "security": "security_audit_scanner",
    "audit": "audit_logging_system",
    "scan": "security_audit_scanner",
    "monitor": "agent_monitor_dashboard",
    "metrics": "prometheus_metrics_exporter",
    "memory": "memory_management",
    "llm": "llm_controller",
    "ai": "llm_controller",
    "chat": "llm_controller",
    "research": "research_engine",
    "knowledge": "knowledge_base_manager",
    "library": "system_librarian",
    "deploy": "deployment_automation_controller",
    "ci": "ci_cd_pipeline_manager",
    "compliance": "compliance_engine",
    "data": "data_pipeline_orchestrator",
    "trading": "trading_bot_engine",
    "crypto": "coinbase_connector",
    "swarm": "advanced_swarm_system",
    "agent": "agent_monitor_dashboard",
    "workflow": "workflow_dag_engine",
    "task": "task_executor",
    "board": "board_system",
    "feedback": "feedback_integrator",
    "keys": "secure_key_manager",
    "notify": "notification_system",
    "scale": "business_scaling_engine",
    "fix": "self_fix_loop",
    "heal": "self_healing_coordinator",
    "simulate": "simulation_engine",
    "cad": "murphy_drawing_engine",
    "engineer": "murphy_engineering_toolbox",
    "commissioning": "audit_logging_system",
    "module": "module_registry",
    "help": "_help",
    "version": "_version",
    "ping": "_ping",
}

#: Maps legacy Discord ``/command`` tokens to their ``!murphy`` equivalents.
_DISCORD_TO_MATRIX_COMMANDS: Dict[str, str] = {
    "/create_model": "!murphy cad create",
    "/scan_system": "!murphy security scan",
    "/triage": "!murphy triage assign",
    "/status": "!murphy status",
    "/health": "!murphy health",
    "/metrics": "!murphy metrics",
    "/swarm": "!murphy swarm",
    "/workflow": "!murphy workflow",
    "/help": "!murphy help",
    "/keys": "!murphy keys",
    "/deploy": "!murphy deploy",
    "/compliance": "!murphy compliance",
    "/research": "!murphy research",
    "/library": "!murphy library",
    "/memory": "!murphy memory",
    "/feedback": "!murphy feedback",
    "/board": "!murphy board",
    "/notify": "!murphy notify",
}


# ---------------------------------------------------------------------------
# MessageRouter
# ---------------------------------------------------------------------------


class MessageRouter:
    """Routes outbound Murphy messages to Matrix rooms and inbound Matrix
    commands to Murphy subsystem handlers.

    Parameters
    ----------
    settings:
        :class:`~matrix_config.MatrixBridgeSettings` instance.
    client:
        A connected :class:`~matrix_client._MatrixClientBase` instance.
    topology:
        :class:`~room_topology.MurphyRoomTopology` instance; if *None*
        the singleton from :func:`~room_topology.get_topology` is used.
    """

    def __init__(
        self,
        settings: MatrixBridgeSettings,
        client: _MatrixClientBase,
        topology: Optional[MurphyRoomTopology] = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._topology = topology or get_topology()
        self._lock = threading.Lock()

        # subsystem_name → RoutingEntry
        self._routing_table: Dict[str, RoutingEntry] = {}
        # command_token → async handler
        self._command_handlers: Dict[
            str, Callable[[CommandParseResult], Any]
        ] = {}
        # Priority queue (list used as heap; asyncio.PriorityQueue for async delivery)
        self._message_queue: asyncio.Queue[QueuedMessage] = asyncio.Queue()

        self._build_default_routing_table()

    # -----------------------------------------------------------------------
    # Routing table
    # -----------------------------------------------------------------------

    def _build_default_routing_table(self) -> None:
        """Populate the routing table from the topology's room definitions."""
        for space in self._topology.spaces:
            for room in space.rooms:
                for subsystem in room.subsystems:
                    prio = (
                        MessagePriority.HIGH
                        if room.alias.endswith("-alerts")
                        else MessagePriority.NORMAL
                    )
                    entry = RoutingEntry(
                        subsystem_name=subsystem,
                        room_alias=room.alias,
                        priority=prio,
                    )
                    with self._lock:
                        self._routing_table.setdefault(subsystem, entry)

    def add_route(self, entry: RoutingEntry) -> None:
        """Add or replace a routing entry for *entry.subsystem_name*."""
        with self._lock:
            self._routing_table[entry.subsystem_name] = entry

    def get_route(self, subsystem_name: str) -> Optional[RoutingEntry]:
        """Return the :class:`RoutingEntry` for *subsystem_name*, or ``None``."""
        with self._lock:
            return self._routing_table.get(subsystem_name)

    def routing_table_snapshot(self) -> Dict[str, RoutingEntry]:
        """Return a shallow copy of the current routing table."""
        with self._lock:
            return dict(self._routing_table)

    # -----------------------------------------------------------------------
    # Outbound: subsystem → Matrix room
    # -----------------------------------------------------------------------

    async def route_to_room(
        self,
        subsystem_name: str,
        text: str,
        html: Optional[str] = None,
        priority: Optional[MessagePriority] = None,
    ) -> SendResult:
        """Send *text* from *subsystem_name* to its registered Matrix room.

        Falls back to ``murphy-general`` if no route is found.
        """
        entry = self.get_route(subsystem_name)
        room_alias = entry.room_alias if entry else "murphy-general"
        if priority is not None:
            effective_priority = priority
        elif entry is not None:
            effective_priority = entry.priority
        else:
            effective_priority = MessagePriority.NORMAL

        content = MessageContent(text=text, html=html)

        if effective_priority == MessagePriority.CRITICAL:
            # Bypass queue for critical messages
            return await self._client.send_message(
                room_alias=room_alias, content=content
            )

        queued = QueuedMessage(
            priority=effective_priority,
            room_alias=room_alias,
            content=content,
            subsystem=subsystem_name,
        )
        await self._message_queue.put(queued)
        # For non-critical messages, immediately flush the queue
        return await self._flush_one()

    async def _flush_one(self) -> SendResult:
        """Dequeue and send the highest-priority pending message."""
        try:
            msg = self._message_queue.get_nowait()
        except asyncio.QueueEmpty:
            return SendResult(success=True, room_alias="", error="queue empty")
        result = await self._client.send_message(
            room_alias=msg.room_alias, content=msg.content
        )
        self._message_queue.task_done()
        return result

    async def broadcast(
        self,
        text: str,
        room_aliases: Optional[List[str]] = None,
        html: Optional[str] = None,
    ) -> List[SendResult]:
        """Broadcast *text* to multiple rooms simultaneously.

        If *room_aliases* is ``None``, broadcasts to all registered rooms.
        """
        targets = room_aliases or self._topology.all_aliases()
        content = MessageContent(text=text, html=html)
        tasks = [
            self._client.send_message(room_alias=alias, content=content)
            for alias in targets
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error("broadcast to room %s failed: %s", targets[i], result)
        return [r for r in results if not isinstance(r, BaseException)]

    # -----------------------------------------------------------------------
    # Inbound: Matrix message → command
    # -----------------------------------------------------------------------

    def parse_command(
        self,
        body: str,
        sender_id: str = "",
        room_alias: str = "",
    ) -> Optional[CommandParseResult]:
        """Parse *body* as a ``!murphy`` command.

        Also accepts legacy Discord ``/command`` syntax (translated
        transparently).  Returns ``None`` if *body* is not a command.
        """
        stripped = body.strip()
        prefix = self._settings.command_prefix  # e.g. "!murphy"

        # Translate legacy Discord commands
        for discord_cmd, matrix_cmd in _DISCORD_TO_MATRIX_COMMANDS.items():
            if stripped.startswith(discord_cmd):
                stripped = matrix_cmd + stripped[len(discord_cmd):]
                break

        if not stripped.startswith(prefix):
            return None

        rest = stripped[len(prefix):].strip()
        tokens = rest.split() if rest else []

        command = tokens[0].lower() if tokens else ""
        subcommand = tokens[1].lower() if len(tokens) > 1 else ""

        # Extract --flag value pairs
        flags: Dict[str, str] = {}
        remaining_args: List[str] = []
        i = 2
        while i < len(tokens):
            if tokens[i].startswith("--") and i + 1 < len(tokens):
                flags[tokens[i][2:]] = tokens[i + 1]
                i += 2
            elif tokens[i].startswith("--"):
                flags[tokens[i][2:]] = "true"
                i += 1
            else:
                remaining_args.append(tokens[i])
                i += 1

        return CommandParseResult(
            raw=body,
            command=command,
            subcommand=subcommand,
            args=remaining_args,
            flags=flags,
            sender_id=sender_id,
            room_alias=room_alias,
        )

    # -----------------------------------------------------------------------
    # Command dispatch
    # -----------------------------------------------------------------------

    def register_command_handler(
        self,
        command: str,
        handler: Callable[[CommandParseResult], Any],
    ) -> None:
        """Register an async *handler* for the given *command* token."""
        self._command_handlers[command.lower()] = handler

    async def dispatch_command(self, parsed: CommandParseResult) -> Any:
        """Dispatch *parsed* to the registered handler for its command token.

        Falls back to the subsystem lookup table if no explicit handler is
        registered.  Returns ``None`` for unknown commands.
        """
        handler = self._command_handlers.get(parsed.command)
        if handler:
            result = handler(parsed)
            if asyncio.iscoroutine(result):
                return await result
            return result

        # Fallback: route via subsystem lookup
        subsystem = _COMMAND_DISPATCH_TABLE.get(parsed.command)
        if subsystem and subsystem.startswith("_"):
            return await self._builtin_command(subsystem, parsed)
        if subsystem:
            logger.info(
                "Command %r routed to subsystem %r (no explicit handler)",
                parsed.command,
                subsystem,
            )
            return subsystem

        logger.warning("Unknown command %r from %r", parsed.command, parsed.sender_id)
        return None

    async def _builtin_command(
        self, builtin: str, parsed: CommandParseResult
    ) -> Optional[str]:
        """Handle built-in bridge commands (``_help``, ``_ping``, etc.)."""
        if builtin == "_help":
            commands = sorted(_COMMAND_DISPATCH_TABLE.keys())
            return f"Available commands: {', '.join(commands)}"
        if builtin == "_ping":
            return "pong"
        if builtin == "_version":
            return "Murphy System Matrix Bridge v1.0"
        return None

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    def translate_discord_command(self, discord_body: str) -> str:
        """Translate a legacy Discord ``/command`` string to Matrix syntax."""
        for discord_cmd, matrix_cmd in _DISCORD_TO_MATRIX_COMMANDS.items():
            if discord_body.strip().startswith(discord_cmd):
                return matrix_cmd + discord_body.strip()[len(discord_cmd):]
        return discord_body

    def get_subsystem_for_command(self, command: str) -> Optional[str]:
        """Return the subsystem key for a given command token."""
        return _COMMAND_DISPATCH_TABLE.get(command.lower())

    def stats(self) -> Dict[str, object]:
        """Return router statistics for monitoring."""
        return {
            "routing_table_size": len(self._routing_table),
            "command_handlers": len(self._command_handlers),
            "queue_depth": self._message_queue.qsize(),
            "command_prefix": self._settings.command_prefix,
        }
