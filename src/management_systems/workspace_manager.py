"""
Management Systems – Workspace Manager
=====================================

Workspace definitions mapped to all Murphy System subsystem domains.

Each workspace corresponds to a functional domain in the Murphy System,
grouping related subsystem modules under a project management umbrella.
Boards, timelines, and dashboards are scoped within workspaces.

Murphy subsystem domain coverage (15+ categories):
    - Automation & Orchestration
    - AI & ML Pipeline
    - Security & Compliance
    - Trading & Finance
    - Communication & Delivery
    - Infrastructure & Deployment
    - Knowledge & Research
    - Monitoring & Observability
    - Self-Healing & Resilience
    - Content & Media
    - Governance & Policy
    - Onboarding & Setup
    - Data & Pipeline
    - Business & Strategy
    - Integration & Connectivity

Integration points:
    - Workspace IDs scope boards in ``board_engine.py``
    - Module mappings reference actual ``murphy_system/src/`` modules
    - Space manager from PR 2 (``space_manager.py``) maps rooms to workspaces

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MURPHY_SUBSYSTEM_DOMAINS: Dict[str, List[str]] = {
    "automation_orchestration": [
        "automation_scaler",
        "automation_scheduler",
        "full_automation_controller",
        "automation_integration_hub",
        "automation_loop_connector",
        "automation_mode_controller",
        "automation_rbac_controller",
        "automation_readiness_evaluator",
        "automation_type_registry",
        "automation_marketplace",
        "murphy_native_automation",
        "self_automation_orchestrator",
        "workflow_dag_engine",
        "workflow_template_marketplace",
    ],
    "ai_ml_pipeline": [
        "llm_controller",
        "llm_integration_layer",
        "ml_model_registry",
        "inference_gate_engine",
        "openai_compatible_provider",
        "murphy_foundation_model",
        "ai_workflow_generator",
        "aionmind",
        "advanced_swarm_system",
        "simulation_engine",
        "shadow_deployment",
        "self_improvement_loop",
        "rlef_engine",
        "mfm_trainer",
    ],
    "security_compliance": [
        "compliance_engine",
        "security_audit_scanner",
        "rbac_governance",
        "authority_gate",
        "fastapi_security",
        "secure_key_manager",
        "cryptographic_anchor",
        "blockchain_audit_trail",
        "audit_logging_system",
        "murphy_credential_gate",
        "auar",
        "base_governance_runtime",
        "security_plane",
    ],
    "trading_finance": [
        "trading_bot_engine",
        "crypto_exchange_connector",
        "coinbase_connector",
        "defi_yield_optimizer",
        "financial_modeling_engine",
        "market_data_aggregator",
        "portfolio_risk_engine",
        "smart_contract_executor",
    ],
    "communication_delivery": [
        "notification_system",
        "email_integration",
        "webhook_dispatcher",
        "announcer_voice_engine",
        "communication_system",
        "matrix_bridge",
        "bridge_layer",
        "hitl_matrix_adapter",
        "webhook_receiver",
    ],
    "infrastructure_deployment": [
        "kubernetes_deployment",
        "docker_containerization",
        "cloudflare_deploy",
        "hetzner_deploy",
        "backup_disaster_recovery",
        "blackstart_controller",
        "deployment_automation_controller",
        "container_orchestration",
        "cloud_provider_adapter",
    ],
    "knowledge_research": [
        "knowledge_graph_builder",
        "research_engine",
        "advanced_research",
        "rag_vector_integration",
        "document_intelligence_engine",
        "semantic_memory_manager",
        "knowledge_distillation_engine",
    ],
    "monitoring_observability": [
        "health_monitor",
        "analytics_dashboard",
        "prometheus_metrics_exporter",
        "agent_monitor_dashboard",
        "alert_rules_engine",
        "performance_profiler",
        "operational_dashboard_aggregator",
        "governance_dashboard_snapshot",
        "cost_dashboard",
        "analytics_pipeline",
    ],
    "self_healing_resilience": [
        "self_fix_loop",
        "autonomous_repair_system",
        "chaos_resilience_loop",
        "error_recovery_engine",
        "fault_injection_controller",
        "circuit_breaker_manager",
        "adaptive_retry_engine",
    ],
    "content_media": [
        "video_packager",
        "youtube_uploader",
        "image_generation_engine",
        "content_pipeline",
        "media_asset_manager",
        "transcription_engine",
        "content_moderation_engine",
    ],
    "governance_policy": [
        "governance_kernel",
        "bot_governance_policy_mapper",
        "authority_gate",
        "policy_enforcement_engine",
        "compliance_automation_bridge",
        "regulatory_framework_adapter",
        "ethics_constraint_engine",
    ],
    "onboarding_setup": [
        "onboarding_flow",
        "setup_wizard",
        "agentic_onboarding_engine",
        "onboarding_team_pipeline",
        "hardware_visual_onboarding",
        "nocode_onboarding_flow",
    ],
    "data_pipeline": [
        "data_pipeline_orchestrator",
        "data_archive_manager",
        "rag_vector_integration",
        "etl_transform_engine",
        "stream_processing_engine",
        "data_quality_validator",
        "data_lineage_tracker",
    ],
    "business_strategy": [
        "business_scaling_engine",
        "niche_business_generator",
        "executive_planning_engine",
        "market_intelligence_engine",
        "competitive_analysis_engine",
        "strategic_roadmap_planner",
        "revenue_optimization_engine",
    ],
    "integration_connectivity": [
        "enterprise_integrations",
        "platform_connector_framework",
        "universal_integration_adapter",
        "integration_engine",
        "adapter_framework",
        "api_gateway_adapter",
        "api_collection_agent",
    ],
}

WORKSPACE_DISPLAY_NAMES: Dict[str, str] = {
    "automation_orchestration": "Automation & Orchestration",
    "ai_ml_pipeline": "AI & ML Pipeline",
    "security_compliance": "Security & Compliance",
    "trading_finance": "Trading & Finance",
    "communication_delivery": "Communication & Delivery",
    "infrastructure_deployment": "Infrastructure & Deployment",
    "knowledge_research": "Knowledge & Research",
    "monitoring_observability": "Monitoring & Observability",
    "self_healing_resilience": "Self-Healing & Resilience",
    "content_media": "Content & Media",
    "governance_policy": "Governance & Policy",
    "onboarding_setup": "Onboarding & Setup",
    "data_pipeline": "Data & Pipeline",
    "business_strategy": "Business & Strategy",
    "integration_connectivity": "Integration & Connectivity",
}

WORKSPACE_DESCRIPTIONS: Dict[str, str] = {
    "automation_orchestration": "Workflow automation, task scheduling, and orchestration engines.",
    "ai_ml_pipeline": "LLM controllers, ML training/inference, and AI workflow management.",
    "security_compliance": "Security auditing, RBAC governance, compliance engines, and key management.",
    "trading_finance": "Crypto trading bots, exchange connectors, DeFi optimizers, and financial modeling.",
    "communication_delivery": "Notification systems, email, webhooks, Matrix bridge, and voice delivery.",
    "infrastructure_deployment": "Kubernetes, Docker, cloud deployments, and disaster recovery.",
    "knowledge_research": "Knowledge graphs, RAG systems, document intelligence, and research engines.",
    "monitoring_observability": "Health monitors, metrics exporters, dashboards, and alerting.",
    "self_healing_resilience": "Autonomous repair, chaos resilience, circuit breakers, and retry logic.",
    "content_media": "Video packaging, YouTube upload, image generation, and media management.",
    "governance_policy": "Policy enforcement, ethical constraints, regulatory compliance, and audit.",
    "onboarding_setup": "Agent and user onboarding flows, setup wizards, and provisioning.",
    "data_pipeline": "ETL, data archival, stream processing, quality validation, and lineage.",
    "business_strategy": "Business scaling, market intelligence, executive planning, and strategy.",
    "integration_connectivity": "Enterprise integrations, platform connectors, and API gateways.",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceMapping:
    """Maps a Murphy subsystem module to a workspace domain.

    Args:
        module_name: Python module name (as found in ``src/``).
        domain_key: Domain key from ``MURPHY_SUBSYSTEM_DOMAINS``.
        module_path: Relative path to the module.
        description: Brief description of the module's role.
    """

    module_name: str
    domain_key: str
    module_path: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "domain_key": self.domain_key,
            "module_path": self.module_path,
            "description": self.description,
        }


@dataclass
class Workspace:
    """A named project management workspace scoped to a Murphy domain.

    Args:
        name: Display name for the workspace.
        domain_key: Murphy subsystem domain identifier.
        description: Optional description.
        matrix_room_id: Associated Matrix room (if any).
        board_ids: Boards contained in this workspace.
        linked_workspace_ids: Cross-workspace links.
    """

    name: str
    domain_key: str = ""
    description: str = ""
    matrix_room_id: str = ""
    board_ids: List[str] = field(default_factory=list)
    linked_workspace_ids: List[str] = field(default_factory=list)
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def module_list(self) -> List[str]:
        """Return the list of Murphy modules mapped to this workspace's domain."""
        return MURPHY_SUBSYSTEM_DOMAINS.get(self.domain_key, [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "domain_key": self.domain_key,
            "description": self.description,
            "matrix_room_id": self.matrix_room_id,
            "board_ids": self.board_ids,
            "linked_workspace_ids": self.linked_workspace_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workspace":
        obj = cls(
            name=data["name"],
            domain_key=data.get("domain_key", ""),
            description=data.get("description", ""),
            matrix_room_id=data.get("matrix_room_id", ""),
            board_ids=data.get("board_ids", []),
            linked_workspace_ids=data.get("linked_workspace_ids", []),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.updated_at = data.get("updated_at", obj.updated_at)
        return obj


# ---------------------------------------------------------------------------
# Workspace Manager
# ---------------------------------------------------------------------------


class WorkspaceManager:
    """Manages workspaces mapped to Murphy System subsystem domains.

    Provides CRUD for workspaces, domain-to-workspace lookup, dashboard
    summaries, and cross-workspace board linking.

    Example::

        mgr = WorkspaceManager()
        mgr.bootstrap_murphy_workspaces()
        ws = mgr.get_workspace_by_domain("ai_ml_pipeline")
        print(ws.module_list)
        print(mgr.render_workspace_summary())
    """

    def __init__(self) -> None:
        self._workspaces: Dict[str, Workspace] = {}

    # -- Workspace CRUD -----------------------------------------------------

    def create_workspace(
        self,
        name: str,
        *,
        domain_key: str = "",
        description: str = "",
        matrix_room_id: str = "",
    ) -> Workspace:
        """Create a new workspace.

        Args:
            name: Display name.
            domain_key: Murphy domain key from ``MURPHY_SUBSYSTEM_DOMAINS``.
            description: Human-readable description.
            matrix_room_id: Associated Matrix room.

        Returns:
            The new :class:`Workspace`.
        """
        ws = Workspace(
            name=name,
            domain_key=domain_key,
            description=description,
            matrix_room_id=matrix_room_id,
        )
        self._workspaces[ws.id] = ws
        logger.info("Workspace created: %s (%s)", name, ws.id)
        return ws

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Return a workspace by ID or *None*."""
        return self._workspaces.get(workspace_id)

    def get_workspace_by_domain(self, domain_key: str) -> Optional[Workspace]:
        """Return the workspace for a given Murphy domain key or *None*."""
        return next(
            (ws for ws in self._workspaces.values() if ws.domain_key == domain_key),
            None,
        )

    def get_workspace_by_module(self, module_name: str) -> Optional[Workspace]:
        """Find the workspace that contains a given Murphy module.

        Args:
            module_name: Module name (e.g. ``"llm_controller"``).

        Returns:
            The matching workspace or *None*.
        """
        for domain_key, modules in MURPHY_SUBSYSTEM_DOMAINS.items():
            if module_name in modules:
                return self.get_workspace_by_domain(domain_key)
        return None

    def list_workspaces(self) -> List[Workspace]:
        """Return all workspaces sorted by name."""
        return sorted(self._workspaces.values(), key=lambda w: w.name)

    def update_workspace(
        self,
        workspace_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        matrix_room_id: Optional[str] = None,
    ) -> Optional[Workspace]:
        """Update workspace metadata."""
        ws = self._workspaces.get(workspace_id)
        if ws is None:
            return None
        if name is not None:
            ws.name = name
        if description is not None:
            ws.description = description
        if matrix_room_id is not None:
            ws.matrix_room_id = matrix_room_id
        ws.updated_at = _now()
        return ws

    def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace by ID."""
        if workspace_id in self._workspaces:
            del self._workspaces[workspace_id]
            return True
        return False

    # -- Board linking ------------------------------------------------------

    def link_board(self, workspace_id: str, board_id: str) -> bool:
        """Associate a board with a workspace."""
        ws = self._workspaces.get(workspace_id)
        if ws is None:
            return False
        if board_id not in ws.board_ids:
            ws.board_ids.append(board_id)
            ws.updated_at = _now()
        return True

    def unlink_board(self, workspace_id: str, board_id: str) -> bool:
        """Remove a board association from a workspace."""
        ws = self._workspaces.get(workspace_id)
        if ws is None:
            return False
        if board_id in ws.board_ids:
            ws.board_ids.remove(board_id)
            ws.updated_at = _now()
            return True
        return False

    def link_workspaces(self, ws_id_a: str, ws_id_b: str) -> bool:
        """Create a bidirectional cross-workspace link."""
        ws_a = self._workspaces.get(ws_id_a)
        ws_b = self._workspaces.get(ws_id_b)
        if ws_a is None or ws_b is None:
            return False
        if ws_id_b not in ws_a.linked_workspace_ids:
            ws_a.linked_workspace_ids.append(ws_id_b)
        if ws_id_a not in ws_b.linked_workspace_ids:
            ws_b.linked_workspace_ids.append(ws_id_a)
        return True

    # -- Bootstrap ----------------------------------------------------------

    def bootstrap_murphy_workspaces(self) -> List[Workspace]:
        """Create one workspace for each Murphy subsystem domain.

        Idempotent: domains that already have a workspace are skipped.

        Returns:
            List of newly created workspaces.
        """
        created: List[Workspace] = []
        existing_domains = {ws.domain_key for ws in self._workspaces.values()}
        for domain_key, display_name in WORKSPACE_DISPLAY_NAMES.items():
            if domain_key in existing_domains:
                continue
            ws = self.create_workspace(
                name=display_name,
                domain_key=domain_key,
                description=WORKSPACE_DESCRIPTIONS.get(domain_key, ""),
            )
            created.append(ws)
        logger.info("Bootstrapped %d Murphy workspaces", len(created))
        return created

    # -- Module lookup ------------------------------------------------------

    @staticmethod
    def list_modules_for_domain(domain_key: str) -> List[str]:
        """Return all Murphy modules in a subsystem domain.

        Args:
            domain_key: One of the keys in ``MURPHY_SUBSYSTEM_DOMAINS``.

        Returns:
            List of module name strings.
        """
        return list(MURPHY_SUBSYSTEM_DOMAINS.get(domain_key, []))

    @staticmethod
    def list_all_domains() -> List[str]:
        """Return all domain keys."""
        return list(MURPHY_SUBSYSTEM_DOMAINS.keys())

    def get_workspace_mapping(self, module_name: str) -> Optional[WorkspaceMapping]:
        """Return a ``WorkspaceMapping`` for a given module name.

        Args:
            module_name: Murphy module name.

        Returns:
            :class:`WorkspaceMapping` or *None*.
        """
        for domain_key, modules in MURPHY_SUBSYSTEM_DOMAINS.items():
            if module_name in modules:
                return WorkspaceMapping(
                    module_name=module_name,
                    domain_key=domain_key,
                    module_path=f"src/{module_name}.py",
                )
        return None

    # -- Dashboard summary --------------------------------------------------

    def render_workspace_summary(self) -> str:
        """Render a Markdown summary of all workspaces for Matrix.

        Returns:
            Multi-line Markdown string listing all workspaces with their
            board counts and module counts.
        """
        workspaces = self.list_workspaces()
        if not workspaces:
            return "No workspaces configured."

        lines = ["**Murphy System – Workspace Overview**", "```"]
        header = f"{'Workspace':<35} {'Domain':<30} {'Boards':>6} {'Modules':>7}"
        sep = "─" * len(header)
        lines += [header, sep]

        for ws in workspaces:
            module_count = len(MURPHY_SUBSYSTEM_DOMAINS.get(ws.domain_key, []))
            name = ws.name[:33]
            domain = ws.domain_key[:28] if ws.domain_key else "—"
            lines.append(
                f"{name:<35} {domain:<30} {len(ws.board_ids):>6} {module_count:>7}"
            )
        lines += [sep, f"Total: {len(workspaces)} workspaces", "```"]
        return "\n".join(lines)

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {wid: ws.to_dict() for wid, ws in self._workspaces.items()}

    def load_dict(self, data: Dict[str, Any]) -> None:
        self._workspaces = {
            wid: Workspace.from_dict(wdata) for wid, wdata in data.items()
        }
