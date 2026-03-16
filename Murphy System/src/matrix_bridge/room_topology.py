# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Matrix Room Topology — MTX-TOPO-001

Owner: Platform Engineering

Defines the canonical Matrix space / room hierarchy for the Murphy System,
mapping the original HiveMind Discord channel architecture to Matrix spaces
and rooms.

Hierarchy
---------
Murphy System (top-level Space)
├─ Security Space
│   ├─ #murphy-security-alerts
│   ├─ #murphy-security-audit
│   └─ #murphy-security-archive
├─ Engineering Space
│   ├─ #murphy-engineering-tasks
│   ├─ #murphy-cad-output
│   └─ #murphy-simulation-results
├─ Triage / Orchestration Space
│   ├─ #murphy-triage-queue
│   ├─ #murphy-task-status
│   └─ #murphy-rollcall
├─ Monitoring / Observability Space
│   ├─ #murphy-health-alerts
│   ├─ #murphy-metrics
│   └─ #murphy-logs
├─ AI / LLM Space
│   ├─ #murphy-llm-requests
│   ├─ #murphy-llm-responses
│   └─ #murphy-ai-research
├─ Trading / Crypto Space
│   └─ #murphy-trading-signals
├─ Compliance / Governance Space
│   ├─ #murphy-compliance-reports
│   └─ #murphy-audit-trail
├─ Memory / Data Space
│   ├─ #murphy-memory-stm
│   ├─ #murphy-memory-ltm
│   └─ #murphy-data-archive
├─ Communication Space
│   ├─ #murphy-notifications
│   └─ #murphy-announcements
├─ Content / Media Space
│   └─ #murphy-content-output
├─ Deployment / Infra Space
│   ├─ #murphy-deployments
│   └─ #murphy-ci-cd
├─ Business / Operations Space
│   ├─ #murphy-business-tasks
│   └─ #murphy-invoices
├─ Self-Healing / Resilience Space
│   └─ #murphy-self-healing
├─ Onboarding / Setup Space
│   └─ #murphy-onboarding
├─ Knowledge / Research Space
│   ├─ #murphy-knowledge-base
│   └─ #murphy-research
├─ Swarm / Multi-Agent Space
│   ├─ #murphy-swarm-coordinator
│   └─ #murphy-agent-activity
├─ Feedback Space
│   └─ #murphy-feedback
└─ General / Bot Output
    ├─ #murphy-general
    └─ #murphy-bot-output

Classes
-------
RoomType : Enum
    Category of a Matrix room (channel, alert, archive, …).
SpaceDefinition : dataclass
    A named Matrix sub-space.
RoomDefinition : dataclass
    A single Matrix room within a space.
MurphyRoomTopology : dataclass
    Complete room/space hierarchy with lookup helpers.
get_topology() : function
    Return the singleton :class:`MurphyRoomTopology`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RoomType(Enum):
    """Functional category of a Matrix room."""

    GENERAL = "general"
    TASK = "task"
    ALERT = "alert"
    ARCHIVE = "archive"
    OUTPUT = "output"
    STATUS = "status"
    AUDIT = "audit"
    RESEARCH = "research"
    COORDINATION = "coordination"
    ANNOUNCEMENT = "announcement"
    FEEDBACK = "feedback"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RoomDefinition:
    """A single Matrix room within a Murphy space.

    Attributes
    ----------
    alias:
        Short canonical alias, e.g. ``murphy-security-alerts``.  The full
        alias resolves as ``#<alias>:<homeserver>``.
    display_name:
        Human-readable room name shown in Matrix clients.
    room_type:
        Functional category of the room.
    description:
        Room topic / description.
    subsystems:
        Murphy subsystem names that publish to or read from this room.
    is_encrypted:
        Whether the room should use E2E encryption (if supported by client).
    is_read_only:
        Whether only the bridge bot may post in this room.
    """

    alias: str
    display_name: str
    room_type: RoomType = RoomType.GENERAL
    description: str = ""
    subsystems: List[str] = field(default_factory=list)
    is_encrypted: bool = False
    is_read_only: bool = False


@dataclass
class SpaceDefinition:
    """A Matrix sub-space grouping related rooms.

    Attributes
    ----------
    alias:
        Short canonical alias for the space.
    display_name:
        Human-readable space name.
    description:
        Space description.
    rooms:
        Ordered list of :class:`RoomDefinition` within this space.
    hivemind_bot:
        Name of the HiveMind bot this space corresponds to (if any).
    """

    alias: str
    display_name: str
    description: str = ""
    rooms: List[RoomDefinition] = field(default_factory=list)
    hivemind_bot: str = ""


# ---------------------------------------------------------------------------
# Canonical topology
# ---------------------------------------------------------------------------

_CANONICAL_SPACES: List[SpaceDefinition] = [
    # -----------------------------------------------------------------------
    # Triage / Orchestration
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-triage",
        display_name="Triage & Orchestration",
        description="Task triage, assignment, workflow orchestration.",
        hivemind_bot="TriageBot",
        rooms=[
            RoomDefinition(
                alias="murphy-triage-queue",
                display_name="Triage Queue",
                room_type=RoomType.TASK,
                description="Incoming tasks awaiting assignment.",
                subsystems=[
                    "triage_rollcall_adapter",
                    "ticket_triage_engine",
                    "task_executor",
                    "workflow_dag_engine",
                    "execution_compiler",
                ],
            ),
            RoomDefinition(
                alias="murphy-task-status",
                display_name="Task Status",
                room_type=RoomType.STATUS,
                description="Live task status updates.",
                subsystems=["task_executor", "execution_orchestrator"],
            ),
            RoomDefinition(
                alias="murphy-rollcall",
                display_name="Rollcall",
                room_type=RoomType.COORDINATION,
                description="Bot / module presence and rollcall events.",
                subsystems=["triage_rollcall_adapter"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Security
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-security",
        display_name="Security",
        description="Threat detection, access control, credential management.",
        hivemind_bot="SecurityBot",
        rooms=[
            RoomDefinition(
                alias="murphy-security-alerts",
                display_name="Security Alerts",
                room_type=RoomType.ALERT,
                description="Real-time security alerts and threat notifications.",
                subsystems=[
                    "security_audit_scanner",
                    "security_hardening_config",
                    "security_plane_adapter",
                    "fastapi_security",
                    "flask_security",
                ],
            ),
            RoomDefinition(
                alias="murphy-security-audit",
                display_name="Security Audit",
                room_type=RoomType.AUDIT,
                description="Access control reviews and compliance audit results.",
                subsystems=[
                    "rbac_governance",
                    "authority_gate",
                    "murphy_credential_gate",
                    "audit_logging_system",
                ],
            ),
            RoomDefinition(
                alias="murphy-security-archive",
                display_name="Security Archive",
                room_type=RoomType.ARCHIVE,
                description="Archived security reports and historical audit logs.",
                subsystems=["security_audit_scanner"],
                is_read_only=True,
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Engineering / CAD / Simulation
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-engineering",
        display_name="Engineering",
        description="Engineering tasks, CAD models, simulations.",
        hivemind_bot="EngineeringBot",
        rooms=[
            RoomDefinition(
                alias="murphy-engineering-tasks",
                display_name="Engineering Tasks",
                room_type=RoomType.TASK,
                description="Active engineering work items.",
                subsystems=["murphy_engineering_toolbox", "simulation_engine"],
            ),
            RoomDefinition(
                alias="murphy-cad-output",
                display_name="CAD Output",
                room_type=RoomType.OUTPUT,
                description="Generated CAD models and design artifacts.",
                subsystems=["murphy_drawing_engine", "murphy_engineering_toolbox"],
            ),
            RoomDefinition(
                alias="murphy-simulation-results",
                display_name="Simulation Results",
                room_type=RoomType.OUTPUT,
                description="Simulation runs and predictive results.",
                subsystems=["simulation_engine", "digital_twin_engine"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Monitoring / Observability
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-monitoring",
        display_name="Monitoring & Observability",
        description="System health, metrics, log analysis.",
        hivemind_bot="MonitoringBot",
        rooms=[
            RoomDefinition(
                alias="murphy-health-alerts",
                display_name="Health Alerts",
                room_type=RoomType.ALERT,
                description="Critical health events and circuit-breaker trips.",
                subsystems=[
                    "health_monitor",
                    "unified_observability_engine",
                    "prometheus_metrics_exporter",
                    "agent_monitor_dashboard",
                ],
            ),
            RoomDefinition(
                alias="murphy-metrics",
                display_name="Metrics",
                room_type=RoomType.STATUS,
                description="Live system metrics feed.",
                subsystems=["prometheus_metrics_exporter", "telemetry_adapter"],
            ),
            RoomDefinition(
                alias="murphy-logs",
                display_name="Logs",
                room_type=RoomType.OUTPUT,
                description="Aggregated log stream.",
                subsystems=["logging_system", "log_analysis_engine"],
                is_read_only=True,
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # AI / LLM
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-ai",
        display_name="AI / LLM",
        description="LLM requests, inference, research.",
        hivemind_bot="AnalysisBot",
        rooms=[
            RoomDefinition(
                alias="murphy-llm-requests",
                display_name="LLM Requests",
                room_type=RoomType.TASK,
                description="Incoming LLM inference requests.",
                subsystems=[
                    "llm_controller",
                    "llm_integration",
                    "llm_integration_layer",
                    "safe_llm_wrapper",
                    "enhanced_local_llm",
                    "local_inference_engine",
                ],
            ),
            RoomDefinition(
                alias="murphy-llm-responses",
                display_name="LLM Responses",
                room_type=RoomType.OUTPUT,
                description="LLM output and validated responses.",
                subsystems=["llm_output_validator", "llm_routing_completeness"],
            ),
            RoomDefinition(
                alias="murphy-ai-research",
                display_name="AI Research",
                room_type=RoomType.RESEARCH,
                description="Research queries and results from AI subsystems.",
                subsystems=["research_engine", "advanced_research", "multi_source_research"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Trading / Crypto
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-trading",
        display_name="Trading & Crypto",
        description="Trading signals, crypto portfolio, market data.",
        hivemind_bot="ScalingBot",
        rooms=[
            RoomDefinition(
                alias="murphy-trading-signals",
                display_name="Trading Signals",
                room_type=RoomType.OUTPUT,
                description="Live trading signals and strategy output.",
                subsystems=[
                    "trading_bot_engine",
                    "trading_strategy_engine",
                    "market_data_feed",
                    "ml_strategy_engine",
                    "coinbase_connector",
                    "crypto_exchange_connector",
                ],
            ),
            RoomDefinition(
                alias="murphy-trading-alerts",
                display_name="Trading Alerts",
                room_type=RoomType.ALERT,
                description="Risk and anomaly alerts from trading subsystems.",
                subsystems=["crypto_risk_manager", "trading_hitl_gateway"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Compliance / Governance
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-compliance",
        display_name="Compliance & Governance",
        description="Regulatory compliance, audit trails, governance.",
        hivemind_bot="CommissioningBot",
        rooms=[
            RoomDefinition(
                alias="murphy-compliance-reports",
                display_name="Compliance Reports",
                room_type=RoomType.AUDIT,
                description="Generated compliance reports and assessments.",
                subsystems=[
                    "compliance_engine",
                    "compliance_as_code_engine",
                    "compliance_report_aggregator",
                ],
            ),
            RoomDefinition(
                alias="murphy-audit-trail",
                display_name="Audit Trail",
                room_type=RoomType.AUDIT,
                description="Immutable audit trail events.",
                subsystems=[
                    "audit_logging_system",
                    "blockchain_audit_trail",
                    "contractual_audit",
                ],
                is_read_only=True,
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Memory / Data
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-memory",
        display_name="Memory & Data",
        description="Short/long-term memory, data pipeline, archives.",
        hivemind_bot="MemoryManagerBot",
        rooms=[
            RoomDefinition(
                alias="murphy-memory-stm",
                display_name="Short-Term Memory",
                room_type=RoomType.STATUS,
                description="Active short-term memory store events.",
                subsystems=["memory_management", "memory_artifact_system"],
            ),
            RoomDefinition(
                alias="murphy-memory-ltm",
                display_name="Long-Term Memory",
                room_type=RoomType.ARCHIVE,
                description="Long-term memory consolidation and retrieval.",
                subsystems=["memory_management", "immune_memory"],
            ),
            RoomDefinition(
                alias="murphy-data-archive",
                display_name="Data Archive",
                room_type=RoomType.ARCHIVE,
                description="Archived data pipeline outputs.",
                subsystems=["data_archive_manager", "data_pipeline_orchestrator"],
                is_read_only=True,
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Communication
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-communication",
        display_name="Communication",
        description="Notifications, announcements, comms connectors.",
        hivemind_bot="FeedbackBot",
        rooms=[
            RoomDefinition(
                alias="murphy-notifications",
                display_name="Notifications",
                room_type=RoomType.ANNOUNCEMENT,
                description="System-generated notifications.",
                subsystems=[
                    "notification_system",
                    "customer_communication_manager",
                ],
            ),
            RoomDefinition(
                alias="murphy-announcements",
                display_name="Announcements",
                room_type=RoomType.ANNOUNCEMENT,
                description="Broadcast announcements.",
                subsystems=["announcer_voice_engine"],
                is_read_only=True,
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Content / Media
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-content",
        display_name="Content & Media",
        description="Content generation, video, image output.",
        hivemind_bot="VisualizationBot",
        rooms=[
            RoomDefinition(
                alias="murphy-content-output",
                display_name="Content Output",
                room_type=RoomType.OUTPUT,
                description="Generated content, images, and media artifacts.",
                subsystems=[
                    "content_pipeline_engine",
                    "image_generation_engine",
                    "video_packager",
                    "murphy_drawing_engine",
                    "digital_asset_generator",
                ],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Deployment / Infrastructure
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-deployment",
        display_name="Deployment & Infrastructure",
        description="CI/CD pipelines, container builds, cloud deployments.",
        hivemind_bot="KeyManagerBot",
        rooms=[
            RoomDefinition(
                alias="murphy-deployments",
                display_name="Deployments",
                room_type=RoomType.STATUS,
                description="Deployment events and status.",
                subsystems=[
                    "docker_containerization",
                    "kubernetes_deployment",
                    "hetzner_deploy",
                    "cloudflare_deploy",
                    "multi_cloud_orchestrator",
                    "deployment_automation_controller",
                ],
            ),
            RoomDefinition(
                alias="murphy-ci-cd",
                display_name="CI/CD",
                room_type=RoomType.STATUS,
                description="CI/CD pipeline events.",
                subsystems=["ci_cd_pipeline_manager"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Business / Operations
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-business",
        display_name="Business & Operations",
        description="Business scaling, sales, invoicing.",
        hivemind_bot="ScalingBot",
        rooms=[
            RoomDefinition(
                alias="murphy-business-tasks",
                display_name="Business Tasks",
                room_type=RoomType.TASK,
                description="Active business operation tasks.",
                subsystems=[
                    "business_scaling_engine",
                    "niche_business_generator",
                    "sales_automation",
                    "supply_orchestrator",
                ],
            ),
            RoomDefinition(
                alias="murphy-invoices",
                display_name="Invoices",
                room_type=RoomType.OUTPUT,
                description="Invoice processing output.",
                subsystems=["invoice_processing_pipeline", "financial_reporting_engine"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Self-Healing / Resilience
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-self-healing",
        display_name="Self-Healing & Resilience",
        description="Autonomous repair, chaos resilience, fault recovery.",
        hivemind_bot="OptimizationBot",
        rooms=[
            RoomDefinition(
                alias="murphy-self-healing",
                display_name="Self-Healing Events",
                room_type=RoomType.ALERT,
                description="Self-repair and resilience events.",
                subsystems=[
                    "self_fix_loop",
                    "self_healing_coordinator",
                    "autonomous_repair_system",
                    "chaos_resilience_loop",
                    "blackstart_controller",
                ],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Onboarding / Setup
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-onboarding",
        display_name="Onboarding & Setup",
        description="User onboarding, environment setup, wizard flows.",
        hivemind_bot="TriageBot",
        rooms=[
            RoomDefinition(
                alias="murphy-onboarding",
                display_name="Onboarding",
                room_type=RoomType.TASK,
                description="Onboarding flow events.",
                subsystems=[
                    "setup_wizard",
                    "onboarding_flow",
                    "agentic_onboarding_engine",
                    "onboarding_automation_engine",
                    "environment_setup_agent",
                    "hardware_visual_onboarding",
                    "onboarding_team_pipeline",
                ],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Knowledge / Research
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-knowledge",
        display_name="Knowledge & Research",
        description="Knowledge graph, research queries, librarian.",
        hivemind_bot="LibrarianBot",
        rooms=[
            RoomDefinition(
                alias="murphy-knowledge-base",
                display_name="Knowledge Base",
                room_type=RoomType.RESEARCH,
                description="Knowledge base queries and updates.",
                subsystems=[
                    "knowledge_base_manager",
                    "knowledge_graph_builder",
                    "system_librarian",
                    "generative_knowledge_builder",
                    "knowledge_gap_system",
                ],
            ),
            RoomDefinition(
                alias="murphy-research",
                display_name="Research",
                room_type=RoomType.RESEARCH,
                description="Research engine output and citations.",
                subsystems=["research_engine", "advanced_research", "multi_source_research"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Swarm / Multi-Agent
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-swarm",
        display_name="Swarm & Multi-Agent",
        description="Agent swarms, coordination, delegation.",
        hivemind_bot="TriageBot",
        rooms=[
            RoomDefinition(
                alias="murphy-swarm-coordinator",
                display_name="Swarm Coordinator",
                room_type=RoomType.COORDINATION,
                description="Swarm orchestration and agent delegation events.",
                subsystems=[
                    "advanced_swarm_system",
                    "true_swarm_system",
                    "domain_swarms",
                    "durable_swarm_orchestrator",
                    "murphy_crew_system",
                    "swarm_proposal_generator",
                    "collaborative_task_orchestrator",
                ],
            ),
            RoomDefinition(
                alias="murphy-agent-activity",
                display_name="Agent Activity",
                room_type=RoomType.STATUS,
                description="Individual agent run activity and metrics.",
                subsystems=[
                    "agent_run_recorder",
                    "agent_monitor_dashboard",
                    "declarative_fleet_manager",
                ],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # Feedback
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-feedback",
        display_name="Feedback",
        description="User feedback, error reports, optimization recommendations.",
        hivemind_bot="FeedbackBot",
        rooms=[
            RoomDefinition(
                alias="murphy-feedback",
                display_name="Feedback",
                room_type=RoomType.FEEDBACK,
                description="Error logs, user feedback, optimization reports.",
                subsystems=["feedback_integrator"],
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # General / Catch-all
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-general",
        display_name="General",
        description="General bot output and cross-subsystem coordination.",
        rooms=[
            RoomDefinition(
                alias="murphy-general",
                display_name="General",
                room_type=RoomType.GENERAL,
                description="General messages and cross-subsystem coordination.",
                subsystems=[],
            ),
            RoomDefinition(
                alias="murphy-bot-output",
                display_name="Bot Output",
                room_type=RoomType.OUTPUT,
                description="All bot-generated output not routed elsewhere.",
                subsystems=[],
                is_read_only=True,
            ),
        ],
    ),
    # -----------------------------------------------------------------------
    # UI Trainer / Overlay
    # -----------------------------------------------------------------------
    SpaceDefinition(
        alias="murphy-ui-trainer",
        display_name="UI Trainer & Overlay",
        description=(
            "Highlight overlay, glow-key hints, left-click suggestions, "
            "and golden-path recommendations surfaced to users in the terminal UI."
        ),
        hivemind_bot="TriageBot",
        rooms=[
            RoomDefinition(
                alias="murphy-ui-trainer",
                display_name="Trainer Suggestions",
                room_type=RoomType.COORDINATION,
                description=(
                    "Shadow-agent automation suggestions rendered as "
                    "coloured highlights / glow-key hints. "
                    "Served by OverlayManager via /api/overlay/*."
                ),
                subsystems=[
                    "highlight_overlay",
                    "golden_path_engine",
                    "murphy_shadow_trainer",
                ],
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Topology class
# ---------------------------------------------------------------------------


@dataclass
class MurphyRoomTopology:
    """Complete Murphy System Matrix room / space hierarchy.

    Attributes
    ----------
    spaces:
        Ordered list of all :class:`SpaceDefinition` objects.
    top_level_space_alias:
        Alias of the parent Murphy System space.
    """

    spaces: List[SpaceDefinition] = field(
        default_factory=lambda: list(_CANONICAL_SPACES)
    )
    top_level_space_alias: str = "murphy-system"

    # -----------------------------------------------------------------------
    # Lookup helpers
    # -----------------------------------------------------------------------

    def get_space(self, alias: str) -> Optional[SpaceDefinition]:
        """Return the :class:`SpaceDefinition` for *alias*, or ``None``."""
        for space in self.spaces:
            if space.alias == alias:
                return space
        return None

    def get_room(self, alias: str) -> Optional[RoomDefinition]:
        """Return the :class:`RoomDefinition` for *alias*, or ``None``."""
        for space in self.spaces:
            for room in space.rooms:
                if room.alias == alias:
                    return room
        return None

    def rooms_for_subsystem(self, subsystem_name: str) -> List[RoomDefinition]:
        """Return all rooms whose *subsystems* list includes *subsystem_name*."""
        result: List[RoomDefinition] = []
        for space in self.spaces:
            for room in space.rooms:
                if subsystem_name in room.subsystems:
                    result.append(room)
        return result

    def all_rooms(self) -> List[RoomDefinition]:
        """Return a flat list of all room definitions."""
        result: List[RoomDefinition] = []
        for space in self.spaces:
            result.extend(space.rooms)
        return result

    def all_aliases(self) -> List[str]:
        """Return all room aliases across all spaces."""
        return [r.alias for r in self.all_rooms()]

    def space_for_room(self, room_alias: str) -> Optional[SpaceDefinition]:
        """Return the :class:`SpaceDefinition` that contains *room_alias*."""
        for space in self.spaces:
            for room in space.rooms:
                if room.alias == room_alias:
                    return space
        return None

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------

    def summary(self) -> Dict[str, object]:
        """Return a stats summary dict (safe for logging / health check)."""
        total_rooms = sum(len(s.rooms) for s in self.spaces)
        return {
            "top_level_space": self.top_level_space_alias,
            "total_spaces": len(self.spaces),
            "total_rooms": total_rooms,
            "spaces": [
                {
                    "alias": s.alias,
                    "display_name": s.display_name,
                    "hivemind_bot": s.hivemind_bot,
                    "room_count": len(s.rooms),
                }
                for s in self.spaces
            ],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_topology_singleton: Optional[MurphyRoomTopology] = None


def get_topology() -> MurphyRoomTopology:
    """Return the (lazily created) canonical :class:`MurphyRoomTopology`."""
    global _topology_singleton  # noqa: PLW0603
    if _topology_singleton is None:
        _topology_singleton = MurphyRoomTopology()
    return _topology_singleton


def reset_topology() -> None:
    """Clear the cached topology singleton (useful in tests)."""
    global _topology_singleton  # noqa: PLW0603
    _topology_singleton = None
