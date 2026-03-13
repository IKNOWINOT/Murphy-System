# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""HiveMind Bot Bridge Adapter — MTX-BOT-001

Owner: Platform Engineering · Dep: message_router, room_topology

Translates the original HiveMind bot concepts (TriageBot, SecurityBot,
CADBot, EngineeringBot, KeyManagerBot, LibrarianBot, SimulationBot,
VisualizationBot, FeedbackBot, CommissioningBot, MonitoringBot, ScalingBot,
JSONBot, MemoryManagerBot, CacheManagerBot, AnalysisBot, OptimizationBot,
SchedulerBot, RubixCubeBot) into Matrix "personas" — virtual bot identities
that route messages to/from the appropriate Matrix rooms via the router.

Each bot persona has:
- A canonical name and Matrix display name
- A primary room alias it "lives in"
- A set of commands it handles (routed by :class:`MessageRouter`)
- A set of Murphy subsystem names it delegates to

Classes
-------
BotPersona : dataclass
    Represents a virtual HiveMind bot persona in Matrix.
BotBridgeAdapter : class
    Registry + dispatcher for all bot personas.
get_adapter() : function
    Return the singleton :class:`BotBridgeAdapter`.

Usage::

    from matrix_bridge.bot_bridge_adapter import get_adapter

    adapter = get_adapter()
    persona = adapter.get_persona("TriageBot")
    print(persona.matrix_display_name)
    await adapter.send_as_bot("TriageBot", "Task #42 assigned to EngineeringBot")
"""
from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .matrix_client import MessageContent, SendResult, _MatrixClientBase
from .message_router import MessageRouter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BotPersona dataclass
# ---------------------------------------------------------------------------


@dataclass
class BotPersona:
    """A virtual HiveMind bot persona exposed as a Matrix entity.

    Attributes
    ----------
    name:
        Canonical HiveMind bot name, e.g. ``"TriageBot"``.
    matrix_display_name:
        Human-readable name shown in Matrix room member lists.
    matrix_localpart:
        Matrix user localpart, e.g. ``"murphy-triage"``.
        Full user ID: ``@murphy-triage:<homeserver>``.
    primary_room_alias:
        The room this persona primarily sends to.
    description:
        Short description of the bot's function.
    subsystems:
        Murphy module names this bot persona delegates to.
    commands:
        Command tokens this persona handles (e.g. ``["triage", "assign"]``).
    """

    name: str
    matrix_display_name: str
    matrix_localpart: str
    primary_room_alias: str
    description: str = ""
    subsystems: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Canonical HiveMind personas
# ---------------------------------------------------------------------------

_HIVEMIND_PERSONAS: List[BotPersona] = [
    BotPersona(
        name="TriageBot",
        matrix_display_name="Murphy · TriageBot",
        matrix_localpart="murphy-triage",
        primary_room_alias="murphy-triage-queue",
        description="Splits and assigns tasks, manages load balancing and scaling.",
        subsystems=[
            "triage_rollcall_adapter",
            "ticket_triage_engine",
            "task_executor",
            "workflow_dag_engine",
        ],
        commands=["triage", "assign", "task", "workflow"],
    ),
    BotPersona(
        name="SecurityBot",
        matrix_display_name="Murphy · SecurityBot",
        matrix_localpart="murphy-security",
        primary_room_alias="murphy-security-alerts",
        description="Threat detection, access control, audit reporting.",
        subsystems=[
            "security_audit_scanner",
            "security_hardening_config",
            "security_plane_adapter",
            "fastapi_security",
            "flask_security",
            "rbac_governance",
            "authority_gate",
            "murphy_credential_gate",
        ],
        commands=["security", "scan", "audit", "keys"],
    ),
    BotPersona(
        name="CADBot",
        matrix_display_name="Murphy · CADBot",
        matrix_localpart="murphy-cad",
        primary_room_alias="murphy-cad-output",
        description="3D model creation, refinement, validation, and archive.",
        subsystems=["murphy_drawing_engine", "murphy_engineering_toolbox"],
        commands=["cad", "model", "design"],
    ),
    BotPersona(
        name="EngineeringBot",
        matrix_display_name="Murphy · EngineeringBot",
        matrix_localpart="murphy-engineering",
        primary_room_alias="murphy-engineering-tasks",
        description="Multi-discipline engineering tasks and commissioning.",
        subsystems=[
            "murphy_engineering_toolbox",
            "simulation_engine",
            "digital_twin_engine",
        ],
        commands=["engineer", "engineering", "simulate"],
    ),
    BotPersona(
        name="KeyManagerBot",
        matrix_display_name="Murphy · KeyManagerBot",
        matrix_localpart="murphy-keymanager",
        primary_room_alias="murphy-deployments",
        description="API key allocation, monitoring, and security.",
        subsystems=[
            "secure_key_manager",
            "groq_key_rotator",
            "key_harvester",
        ],
        commands=["keys", "key", "keymanager"],
    ),
    BotPersona(
        name="LibrarianBot",
        matrix_display_name="Murphy · LibrarianBot",
        matrix_localpart="murphy-librarian",
        primary_room_alias="murphy-knowledge-base",
        description="Knowledge indexing, retrieval, and search.",
        subsystems=[
            "system_librarian",
            "librarian_adapter",
            "librarian_integration",
            "knowledge_base_manager",
            "knowledge_graph_builder",
        ],
        commands=["library", "librarian", "knowledge", "search"],
    ),
    BotPersona(
        name="SimulationBot",
        matrix_display_name="Murphy · SimulationBot",
        matrix_localpart="murphy-simulation",
        primary_room_alias="murphy-simulation-results",
        description="Predictive simulation, workflow validation, archiving.",
        subsystems=["simulation_engine", "digital_twin_engine"],
        commands=["simulate", "simulation"],
    ),
    BotPersona(
        name="VisualizationBot",
        matrix_display_name="Murphy · VisualizationBot",
        matrix_localpart="murphy-visualization",
        primary_room_alias="murphy-content-output",
        description="Charts, graphs, 3D model rendering, interactive visuals.",
        subsystems=[
            "image_generation_engine",
            "murphy_drawing_engine",
            "analytics_dashboard",
            "digital_asset_generator",
        ],
        commands=["visualize", "chart", "graph", "render"],
    ),
    BotPersona(
        name="FeedbackBot",
        matrix_display_name="Murphy · FeedbackBot",
        matrix_localpart="murphy-feedback",
        primary_room_alias="murphy-feedback",
        description="Error logging, feedback collection, optimization reports.",
        subsystems=["feedback_integrator"],
        commands=["feedback", "error", "report"],
    ),
    BotPersona(
        name="CommissioningBot",
        matrix_display_name="Murphy · CommissioningBot",
        matrix_localpart="murphy-commissioning",
        primary_room_alias="murphy-compliance-reports",
        description="Benchmarking, verification, and classification.",
        subsystems=[
            "audit_logging_system",
            "compliance_engine",
            "contractual_audit",
        ],
        commands=["commissioning", "commission", "benchmark", "verify"],
    ),
    BotPersona(
        name="MonitoringBot",
        matrix_display_name="Murphy · MonitoringBot",
        matrix_localpart="murphy-monitoring",
        primary_room_alias="murphy-health-alerts",
        description="System health polling, alert broadcasting.",
        subsystems=[
            "health_monitor",
            "unified_observability_engine",
            "prometheus_metrics_exporter",
            "agent_monitor_dashboard",
            "telemetry_adapter",
        ],
        commands=["monitor", "health", "metrics", "status"],
    ),
    BotPersona(
        name="ScalingBot",
        matrix_display_name="Murphy · ScalingBot",
        matrix_localpart="murphy-scaling",
        primary_room_alias="murphy-business-tasks",
        description="Dynamic instance scaling and resource allocation.",
        subsystems=[
            "business_scaling_engine",
            "resource_scaling_controller",
            "automation_scaler",
        ],
        commands=["scale", "scaling", "resources"],
    ),
    BotPersona(
        name="JSONBot",
        matrix_display_name="Murphy · JSONBot",
        matrix_localpart="murphy-json",
        primary_room_alias="murphy-bot-output",
        description="Schema validation, data formatting, error correction.",
        subsystems=["llm_output_validator"],
        commands=["json", "validate", "schema"],
    ),
    BotPersona(
        name="MemoryManagerBot",
        matrix_display_name="Murphy · MemoryManagerBot",
        matrix_localpart="murphy-memory",
        primary_room_alias="murphy-memory-stm",
        description="STM/LTM management, context retrieval, archiving.",
        subsystems=[
            "memory_management",
            "memory_artifact_system",
            "immune_memory",
        ],
        commands=["memory", "stm", "ltm", "context"],
    ),
    BotPersona(
        name="CacheManagerBot",
        matrix_display_name="Murphy · CacheManagerBot",
        matrix_localpart="murphy-cache",
        primary_room_alias="murphy-memory-stm",
        description="Fast retrieval and memory optimization.",
        subsystems=["cache"],
        commands=["cache", "flush", "cached"],
    ),
    BotPersona(
        name="AnalysisBot",
        matrix_display_name="Murphy · AnalysisBot",
        matrix_localpart="murphy-analysis",
        primary_room_alias="murphy-llm-responses",
        description="Data analysis, insights generation, archiving.",
        subsystems=[
            "llm_controller",
            "llm_integration_layer",
            "local_inference_engine",
            "safe_llm_wrapper",
            "enhanced_local_llm",
        ],
        commands=["analyze", "analysis", "insights", "ai", "llm", "chat"],
    ),
    BotPersona(
        name="OptimizationBot",
        matrix_display_name="Murphy · OptimizationBot",
        matrix_localpart="murphy-optimization",
        primary_room_alias="murphy-self-healing",
        description="Workflow refinement, resource allocation, iteration.",
        subsystems=[
            "self_optimisation_engine",
            "self_improvement_engine",
            "cost_optimization_advisor",
        ],
        commands=["optimize", "optimise", "improve"],
    ),
    BotPersona(
        name="SchedulerBot",
        matrix_display_name="Murphy · SchedulerBot",
        matrix_localpart="murphy-scheduler",
        primary_room_alias="murphy-task-status",
        description="ETC prediction, dynamic scheduling, conflict resolution.",
        subsystems=["scheduler", "automation_scheduler"],
        commands=["schedule", "scheduler", "eta"],
    ),
    BotPersona(
        name="RubixCubeBot",
        matrix_display_name="Murphy · RubixCubeBot",
        matrix_localpart="murphy-rubix",
        primary_room_alias="murphy-swarm-coordinator",
        description="Real-time workflow optimization and collaborative chains.",
        subsystems=["rubix_evidence_adapter", "murphy_crew_system"],
        commands=["rubix", "chain", "collaborate"],
    ),
]


# ---------------------------------------------------------------------------
# BotBridgeAdapter
# ---------------------------------------------------------------------------


class BotBridgeAdapter:
    """Registry and dispatcher for all HiveMind bot personas.

    Parameters
    ----------
    client:
        Connected :class:`~matrix_client._MatrixClientBase`.
    router:
        :class:`~message_router.MessageRouter` instance.
    homeserver:
        Homeserver domain, used to construct full Matrix user IDs.
    """

    def __init__(
        self,
        client: _MatrixClientBase,
        router: MessageRouter,
        homeserver: str = "matrix.org",
    ) -> None:
        self._client = client
        self._router = router
        self._homeserver = homeserver.replace("https://", "").replace("http://", "")
        # name → BotPersona
        self._personas: Dict[str, BotPersona] = {}
        # subsystem_name → persona_name
        self._subsystem_index: Dict[str, str] = {}

        for persona in _HIVEMIND_PERSONAS:
            self._register_persona(persona)

    # -----------------------------------------------------------------------
    # Registration
    # -----------------------------------------------------------------------

    def _register_persona(self, persona: BotPersona) -> None:
        """Internal: register a persona and update the subsystem index."""
        self._personas[persona.name] = persona
        for sub in persona.subsystems:
            self._subsystem_index.setdefault(sub, persona.name)
        logger.debug("Registered persona %r → %s", persona.name, persona.primary_room_alias)

    def register_persona(self, persona: BotPersona) -> None:
        """Register a custom :class:`BotPersona` (e.g. for extensions)."""
        self._register_persona(persona)

    # -----------------------------------------------------------------------
    # Lookups
    # -----------------------------------------------------------------------

    def get_persona(self, name: str) -> Optional[BotPersona]:
        """Return the :class:`BotPersona` for *name*, or ``None``."""
        return self._personas.get(name)

    def get_persona_for_subsystem(self, subsystem_name: str) -> Optional[BotPersona]:
        """Return the persona responsible for *subsystem_name*, or ``None``."""
        name = self._subsystem_index.get(subsystem_name)
        if name:
            return self._personas.get(name)
        return None

    def all_personas(self) -> List[BotPersona]:
        """Return all registered :class:`BotPersona` objects."""
        return list(self._personas.values())

    def full_matrix_user_id(self, persona: BotPersona) -> str:
        """Return the fully-qualified Matrix user ID for *persona*."""
        return f"@{persona.matrix_localpart}:{self._homeserver}"

    # -----------------------------------------------------------------------
    # Messaging
    # -----------------------------------------------------------------------

    async def send_as_bot(
        self,
        bot_name: str,
        text: str,
        html: Optional[str] = None,
        room_alias: Optional[str] = None,
    ) -> SendResult:
        """Send a message attributed to *bot_name*.

        If *room_alias* is not provided, the persona's primary room is used.
        """
        persona = self.get_persona(bot_name)
        if not persona:
            logger.warning("send_as_bot: unknown bot %r", bot_name)
            target = room_alias or "murphy-general"
        else:
            target = room_alias or persona.primary_room_alias

        # Add bot attribution prefix to the message
        prefix = f"**[{persona.matrix_display_name if persona else bot_name}]** "
        attributed_text = prefix + text
        attributed_html: Optional[str] = None
        if html:
            attributed_html = f"<strong>[{persona.matrix_display_name if persona else bot_name}]</strong> {html}"

        content = MessageContent(text=attributed_text, html=attributed_html)
        return await self._client.send_message(room_alias=target, content=content)

    async def bot_to_bot(
        self,
        from_bot: str,
        to_bot: str,
        message: str,
        html: Optional[str] = None,
    ) -> SendResult:
        """Send a bot-to-bot delegation message.

        The message is posted to the *to_bot*'s primary room, attributed
        to *from_bot*, enabling visible inter-bot communication.
        """
        to_persona = self.get_persona(to_bot)
        if not to_persona:
            logger.warning("bot_to_bot: unknown target bot %r", to_bot)
            return SendResult(success=False, error=f"Unknown bot {to_bot!r}")

        from_persona = self.get_persona(from_bot)
        from_label = (
            from_persona.matrix_display_name if from_persona else from_bot
        )
        delegation_text = (
            f"**[{from_label} → {to_persona.matrix_display_name}]** {message}"
        )
        delegation_html: Optional[str] = None
        if html:
            delegation_html = (
                f"<strong>[{from_label} → {to_persona.matrix_display_name}]</strong> {html}"
            )

        content = MessageContent(text=delegation_text, html=delegation_html)
        return await self._client.send_message(
            room_alias=to_persona.primary_room_alias, content=content
        )

    async def delegate_task(
        self,
        from_bot: str,
        task_description: str,
        target_subsystem: str,
    ) -> Optional[SendResult]:
        """Delegate *task_description* from *from_bot* to *target_subsystem*'s bot.

        Looks up the persona responsible for *target_subsystem* and sends
        the delegation message to its primary room.
        """
        to_persona = self.get_persona_for_subsystem(target_subsystem)
        if not to_persona:
            logger.warning(
                "delegate_task: no persona for subsystem %r", target_subsystem
            )
            return None
        return await self.bot_to_bot(
            from_bot=from_bot,
            to_bot=to_persona.name,
            message=f"DELEGATE [{target_subsystem}]: {task_description}",
        )

    # -----------------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------------

    def register_command_handlers(
        self,
        router: MessageRouter,
        handler_factory: Optional[Callable[[BotPersona], Callable[..., Any]]] = None,
    ) -> None:
        """Register all persona command tokens with *router*.

        If *handler_factory* is provided, it is called with each persona to
        produce a command handler callable.  Otherwise a no-op handler is
        registered that logs the invocation.
        """
        for persona in self._personas.values():
            for cmd in persona.commands:
                if handler_factory:
                    handler = handler_factory(persona)
                else:

                    async def _noop_handler(
                        parsed: Any, _p: BotPersona
                    ) -> str:
                        logger.info(
                            "Command %r dispatched to %r (no-op handler)",
                            parsed.command,
                            _p.name,
                        )
                        return f"Command received by {_p.matrix_display_name}"

                    handler = functools.partial(_noop_handler, _p=persona)

                router.register_command_handler(cmd, handler)

    def stats(self) -> Dict[str, object]:
        """Return adapter statistics for health checks."""
        return {
            "persona_count": len(self._personas),
            "subsystem_index_size": len(self._subsystem_index),
            "personas": [p.name for p in self._personas.values()],
        }


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_adapter_singleton: Optional[BotBridgeAdapter] = None


def get_adapter(
    client: Optional[_MatrixClientBase] = None,
    router: Optional[MessageRouter] = None,
    homeserver: str = "matrix.org",
) -> BotBridgeAdapter:
    """Return the singleton :class:`BotBridgeAdapter`.

    The first call must supply *client* and *router*.  Subsequent calls
    return the cached instance regardless of parameters.
    """
    global _adapter_singleton  # noqa: PLW0603
    if _adapter_singleton is None:
        if client is None or router is None:
            raise RuntimeError(
                "get_adapter() requires client and router on first call"
            )
        _adapter_singleton = BotBridgeAdapter(
            client=client, router=router, homeserver=homeserver
        )
    return _adapter_singleton


def reset_adapter() -> None:
    """Clear the cached adapter singleton (useful in tests)."""
    global _adapter_singleton  # noqa: PLW0603
    _adapter_singleton = None
