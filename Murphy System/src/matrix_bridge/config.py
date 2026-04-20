"""
Matrix Bridge Configuration.

Defines configuration dataclasses and room definitions for the Murphy System
Matrix Application Service bridge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RoomMapping:
    """Represents a single Matrix room mapping for a Murphy subsystem.

    Attributes:
        room_alias: Human-readable alias e.g. ``#murphy-core:example.com``.
        room_id: Internal Matrix room ID (``!xxx:example.com``), populated
            after the room has been created via the homeserver.
        display_name: Friendly name shown in Matrix clients.
        subsystems: List of Murphy module names that publish to this room.
        encrypted: Whether end-to-end encryption is required.
        topic: Room topic string displayed in Matrix clients.
    """

    room_alias: str
    room_id: str
    display_name: str
    subsystems: list[str]
    encrypted: bool = False
    topic: str = ""


@dataclass
class MatrixBridgeConfig:
    """Top-level configuration for the Murphy Matrix bridge.

    All values have safe defaults suitable for local development.  Override
    with real credentials and URLs before deploying to production.

    Attributes:
        homeserver_url: Base URL of the Matrix homeserver.
        bot_user_id: Fully-qualified Matrix user ID for the Murphy bot.
        bot_access_token: Access token used by the bot user.
        appservice_token: Token the appservice presents to the homeserver.
        homeserver_token: Token the homeserver presents to the appservice.
        appservice_port: TCP port on which the appservice HTTP server listens.
        murphy_api_url: Base URL of the Murphy REST API.
        domain: Matrix server-name component (e.g. ``example.com``).
        room_mappings: Mapping of short room keys to :class:`RoomMapping`.
        command_prefix: Prefix for Murphy bot commands (e.g. ``!murphy``).
        max_event_queue_size: Maximum events held in the in-process queue.
        retry_attempts: Number of delivery retries before dead-lettering.
        retry_delay_seconds: Base delay between retry attempts.
        enable_e2ee: Master switch for end-to-end encryption support.
        media_upload_max_bytes: Maximum size for a single media upload.
    """

    homeserver_url: str = "https://matrix.example.com"
    bot_user_id: str = "@murphy:example.com"
    bot_access_token: str = ""
    appservice_token: str = ""
    homeserver_token: str = ""
    appservice_port: int = 9000
    murphy_api_url: str = "http://localhost:8000"
    domain: str = "example.com"
    room_mappings: dict[str, RoomMapping] = field(default_factory=dict)
    command_prefix: str = "!murphy"
    max_event_queue_size: int = 1000
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    enable_e2ee: bool = False
    media_upload_max_bytes: int = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Default room definitions — covers all 50 rooms in the integration plan
# ---------------------------------------------------------------------------

DEFAULT_ROOM_DEFINITIONS: dict[str, dict] = {
    # ── Core ──────────────────────────────────────────────────────────────
    "murphy-core": {
        "display_name": "Murphy Core",
        "topic": "Central command and system integration hub",
        "encrypted": False,
        "subsystems": [
            "system_integrator",
            "modular_runtime",
            "config",
            "env_manager",
            "module_manager",
            "module_registry",
        ],
    },
    "murphy-terminal": {
        "display_name": "Murphy Terminal",
        "topic": "Interactive terminal and command interface",
        "encrypted": False,
        "subsystems": ["murphy_terminal", "command_system", "command_parser"],
    },
    "murphy-runtime": {
        "display_name": "Murphy Runtime",
        "topic": "Runtime lifecycle and module orchestration",
        "encrypted": False,
        "subsystems": ["modular_runtime", "module_manager", "module_registry"],
    },
    "murphy-config": {
        "display_name": "Murphy Config",
        "topic": "Configuration management and environment variables",
        "encrypted": True,
        "subsystems": ["config", "env_manager", "secure_key_manager"],
    },
    "murphy-ops": {
        "display_name": "Murphy Ops",
        "topic": "Operational tasks, deployments, and lifecycle management",
        "encrypted": False,
        "subsystems": ["deployment_automation_controller", "ci_cd_pipeline_manager"],
    },
    # ── Governance ────────────────────────────────────────────────────────
    "murphy-governance": {
        "display_name": "Murphy Governance",
        "topic": "Policy enforcement and governance kernel decisions",
        "encrypted": False,
        "subsystems": [
            "governance_kernel",
            "governance_toggle",
            "rbac_governance",
        ],
    },
    "murphy-gates": {
        "display_name": "Murphy Gates",
        "topic": "Gate evaluations, authority gates, and bypass events",
        "encrypted": False,
        "subsystems": [
            "gate_builder",
            "gate_bypass_controller",
            "authority_gate",
            "cost_explosion_gate",
            "niche_viability_gate",
            "inference_gate_engine",
        ],
    },
    "murphy-hitl": {
        "display_name": "Murphy HITL",
        "topic": "Human-in-the-loop escalations and approvals",
        "encrypted": False,
        "subsystems": ["hitl_autonomy_controller", "hitl_graduation_engine"],
    },
    # ── Execution ─────────────────────────────────────────────────────────
    "murphy-execution": {
        "display_name": "Murphy Execution",
        "topic": "Task execution, deterministic routing, and finish-line tracking",
        "encrypted": False,
        "subsystems": [
            "execution_compiler",
            "deterministic_routing_engine",
            "deterministic_compute",
            "finish_line_controller",
            "murphy_action_engine",
        ],
    },
    "murphy-automation": {
        "display_name": "Murphy Automation",
        "topic": "Full-automation controller and scheduling",
        "encrypted": False,
        "subsystems": [
            "full_automation_controller",
            "automation_mode_controller",
            "automation_scheduler",
            "automation_scaler",
        ],
    },
    "murphy-confidence": {
        "display_name": "Murphy Confidence",
        "topic": "Confidence scoring and probabilistic execution",
        "encrypted": False,
        "subsystems": ["probabilistic_layer"],
    },
    # ── Intelligence ──────────────────────────────────────────────────────
    "murphy-llm": {
        "display_name": "Murphy LLM",
        "topic": "LLM integration, key rotation, and output validation",
        "encrypted": True,
        "subsystems": [
            "llm_integration",
            "llm_integration_layer",
            "llm_controller",
            "llm_output_validator",
            "llm_provider_router",
            "openai_compatible_provider",
            "enhanced_local_llm",
            "local_llm_fallback",
            "local_inference_engine",
            "local_model_layer",
            "prompt_amplifier",
        ],
    },
    "murphy-intelligence": {
        "display_name": "Murphy Intelligence",
        "topic": "Reasoning, knowledge graphs, and RAG vector integration",
        "encrypted": False,
        "subsystems": [
            "reasoning_engine",
            "concept_graph_engine",
            "knowledge_graph_builder",
            "knowledge_base_manager",
            "knowledge_gap_system",
            "rag_vector_integration",
            "neuro_symbolic_adapter",
            "large_action_model",
        ],
    },
    "murphy-swarm": {
        "display_name": "Murphy Swarm",
        "topic": "Swarm orchestration and multi-agent coordination",
        "encrypted": False,
        "subsystems": [
            "advanced_swarm_system",
            "domain_swarms",
            "durable_swarm_orchestrator",
            "murphy_crew_system",
        ],
    },
    "murphy-learning": {
        "display_name": "Murphy Learning",
        "topic": "Federated learning, feedback loops, and shadow training",
        "encrypted": False,
        "subsystems": [
            "learning_system",
            "federated_learning_coordinator",
            "feedback_integrator",
            "murphy_shadow_trainer",
        ],
    },
    # ── Security ──────────────────────────────────────────────────────────
    "murphy-security": {
        "display_name": "Murphy Security",
        "topic": "Security policies, RBAC, and credential management",
        "encrypted": True,
        "subsystems": [
            "fastapi_security",
            "flask_security",
            "oauth_oidc_provider",
            "murphy_credential_gate",
            "rbac_governance",
            "security_audit_scanner",
            "security_hardening_config",
            "security_plane_adapter",
            "input_validation",
        ],
    },
    "murphy-audit": {
        "display_name": "Murphy Audit",
        "topic": "Audit logs, blockchain trail, and dependency audits",
        "encrypted": True,
        "subsystems": [
            "audit_logging_system",
            "blockchain_audit_trail",
            "contractual_audit",
            "dependency_audit_engine",
        ],
    },
    "murphy-compliance": {
        "display_name": "Murphy Compliance",
        "topic": "Compliance-as-code, regional validation, and reporting",
        "encrypted": False,
        "subsystems": [
            "compliance_engine",
            "compliance_as_code_engine",
            "compliance_automation_bridge",
            "compliance_monitoring_completeness",
            "compliance_orchestration_bridge",
            "compliance_region_validator",
            "compliance_report_aggregator",
        ],
    },
    # ── Finance & Crypto ──────────────────────────────────────────────────
    "murphy-finance": {
        "display_name": "Murphy Finance",
        "topic": "Invoice processing, reporting, KPIs, and cost optimization",
        "encrypted": True,
        "subsystems": [
            "invoice_processing_pipeline",
            "financial_reporting_engine",
            "budget_aware_processor",
            "kpi_tracker",
            "cost_optimization_advisor",
            "market_data_feed",
        ],
    },
    "murphy-crypto": {
        "display_name": "Murphy Crypto",
        "topic": "Crypto exchange connectors, portfolio, and risk management",
        "encrypted": True,
        "subsystems": [
            "crypto_exchange_connector",
            "crypto_portfolio_tracker",
            "crypto_risk_manager",
            "crypto_wallet_manager",
            "coinbase_connector",
        ],
    },
    # ── Business ──────────────────────────────────────────────────────────
    "murphy-business": {
        "display_name": "Murphy Business",
        "topic": "Business generation, scaling, and competitive intelligence",
        "encrypted": False,
        "subsystems": [
            "niche_business_generator",
            "business_scaling_engine",
            "executive_planning_engine",
            "competitive_intelligence_engine",
            "innovation_farmer",
        ],
    },
    "murphy-marketing": {
        "display_name": "Murphy Marketing",
        "topic": "Campaign analytics, orchestration, and adaptive campaigns",
        "encrypted": False,
        "subsystems": [
            "marketing_analytics_aggregator",
            "adaptive_campaign_engine",
            "campaign_orchestrator",
        ],
    },
    "murphy-content": {
        "display_name": "Murphy Content",
        "topic": "Content pipelines, digital assets, and video packaging",
        "encrypted": False,
        "subsystems": [
            "content_pipeline_engine",
            "content_creator_platform_modulator",
            "digital_asset_generator",
            "image_generation_engine",
            "murphy_drawing_engine",
            "faq_generation_engine",
            "video_packager",
            "youtube_uploader",
        ],
    },
    "murphy-crm": {
        "display_name": "Murphy CRM",
        "topic": "Customer communications and multi-tenant workspace",
        "encrypted": False,
        "subsystems": [
            "customer_communication_manager",
            "multi_tenant_workspace",
        ],
    },
    "murphy-org": {
        "display_name": "Murphy Org",
        "topic": "Org chart management, enforcement, and bootstrap",
        "encrypted": False,
        "subsystems": [
            "organization_chart_system",
            "org_chart_enforcement",
            "inoni_org_bootstrap",
        ],
    },
    "murphy-onboarding": {
        "display_name": "Murphy Onboarding",
        "topic": "Onboarding flows, automation, and agentic pipelines",
        "encrypted": False,
        "subsystems": [
            "onboarding_flow",
            "onboarding_automation_engine",
            "onboarding_team_pipeline",
            "agentic_onboarding_engine",
        ],
    },
    # ── Infrastructure ────────────────────────────────────────────────────
    "murphy-infra": {
        "display_name": "Murphy Infra",
        "topic": "Docker, Kubernetes, cloud deployments, and CI/CD",
        "encrypted": False,
        "subsystems": [
            "docker_containerization",
            "kubernetes_deployment",
            "hetzner_deploy",
            "cloudflare_deploy",
            "multi_cloud_orchestrator",
            "ci_cd_pipeline_manager",
            "deployment_automation_controller",
            "geographic_load_balancer",
            "resource_scaling_controller",
            "capacity_planning_engine",
            "backup_disaster_recovery",
            "blackstart_controller",
            "emergency_stop_controller",
        ],
    },
    "murphy-health": {
        "display_name": "Murphy Health",
        "topic": "System health, self-healing, and predictive failure",
        "encrypted": False,
        "subsystems": [
            "health_monitor",
            "heartbeat_liveness_protocol",
            "chaos_resilience_loop",
            "autonomous_repair_system",
            "murphy_code_healer",
            "code_repair_engine",
            "predictive_failure_engine",
            "predictive_maintenance_engine",
            "bug_pattern_detector",
            "self_fix_loop",
            "self_healing_coordinator",
        ],
    },
    "murphy-iot": {
        "display_name": "Murphy IoT",
        "topic": "IoT connectors, digital twins, and computer vision",
        "encrypted": False,
        "subsystems": [
            "building_automation_connectors",
            "energy_management_connectors",
            "additive_manufacturing_connectors",
            "manufacturing_automation_standards",
            "murphy_sensor_fusion",
            "digital_twin_engine",
            "murphy_autonomous_perception",
            "computer_vision_pipeline",
        ],
    },
    "murphy-rpa": {
        "display_name": "Murphy RPA",
        "topic": "Robotic process automation and browser automation",
        "encrypted": False,
        "subsystems": [],
    },
    # ── Observability ─────────────────────────────────────────────────────
    "murphy-telemetry": {
        "display_name": "Murphy Telemetry",
        "topic": "Logging, tracing, metrics, and observability",
        "encrypted": False,
        "subsystems": [
            "logging_system",
            "murphy_trace",
            "metrics",
            "prometheus_metrics_exporter",
            "observability_counters",
            "log_analysis_engine",
            "causal_spike_analyzer",
            "bot_telemetry_normalizer",
            "statistics_collector",
        ],
    },
    "murphy-dashboards": {
        "display_name": "Murphy Dashboards",
        "topic": "Analytics dashboards, SLO tracking, and reports",
        "encrypted": False,
        "subsystems": [
            "analytics_dashboard",
            "agent_monitor_dashboard",
            "operational_dashboard_aggregator",
            "operational_slo_tracker",
            "operational_completeness",
            "functionality_heatmap",
            "advanced_reports",
        ],
    },
    "murphy-alerts": {
        "display_name": "Murphy Alerts",
        "topic": "Alert rules engine and incident notifications",
        "encrypted": False,
        "subsystems": ["alert_rules_engine"],
    },
    # ── Integrations & Comms ──────────────────────────────────────────────
    "murphy-integrations": {
        "display_name": "Murphy Integrations",
        "topic": "Integration bus, enterprise connectors, and API gateway",
        "encrypted": False,
        "subsystems": [
            "integration_bus",
            "enterprise_integrations",
            "platform_connector_framework",
            "cross_platform_data_sync",
            "remote_access_connector",
            "api_gateway_adapter",
            "agentic_api_provisioner",
            "graphql_api_layer",
            "universal_integration_adapter",
        ],
    },
    "murphy-comms": {
        "display_name": "Murphy Comms",
        "topic": "Email, notifications, voice, and webhooks",
        "encrypted": False,
        "subsystems": [
            "email_integration",
            "notification_system",
            "announcer_voice_engine",
            "webhook_dispatcher",
        ],
    },
    # ── Bots ──────────────────────────────────────────────────────────────
    "murphy-bots": {
        "display_name": "Murphy Bots",
        "topic": "Top-level bot activity and coordination",
        "encrypted": False,
        "subsystems": [],
    },
    "murphy-bots-analysis": {
        "display_name": "Murphy Bots — Analysis",
        "topic": "Bot-driven analysis and research tasks",
        "encrypted": False,
        "subsystems": [],
    },
    "murphy-bots-engineering": {
        "display_name": "Murphy Bots — Engineering",
        "topic": "Bot-driven engineering and code-generation tasks",
        "encrypted": False,
        "subsystems": ["code_generation_gateway", "multi_language_codegen"],
    },
    "murphy-bots-knowledge": {
        "display_name": "Murphy Bots — Knowledge",
        "topic": "Bot-driven knowledge management and RAG tasks",
        "encrypted": False,
        "subsystems": [],
    },
    "murphy-bots-execution": {
        "display_name": "Murphy Bots — Execution",
        "topic": "Bot-driven execution and automation tasks",
        "encrypted": False,
        "subsystems": [],
    },
    "murphy-bots-comms": {
        "display_name": "Murphy Bots — Comms",
        "topic": "Bot-driven communication and outreach",
        "encrypted": False,
        "subsystems": [],
    },
    "murphy-personas": {
        "display_name": "Murphy Personas",
        "topic": "Agent persona definitions and management",
        "encrypted": False,
        "subsystems": [],
    },
    # ── Dev & Experiments ─────────────────────────────────────────────────
    "murphy-dev": {
        "display_name": "Murphy Dev",
        "topic": "Code generation, architecture evolution, and A/B testing",
        "encrypted": False,
        "subsystems": [
            "code_generation_gateway",
            "multi_language_codegen",
            "architecture_evolution",
            "ab_testing_framework",
        ],
    },
    "murphy-experiments": {
        "display_name": "Murphy Experiments",
        "topic": "Experimental features and research prototypes",
        "encrypted": False,
        "subsystems": [],
    },
    "murphy-plugins": {
        "display_name": "Murphy Plugins",
        "topic": "Plugin registry and dynamic extension loading",
        "encrypted": False,
        "subsystems": [],
    },
    "murphy-boards": {
        "display_name": "Murphy Boards",
        "topic": "Kanban boards and project planning",
        "encrypted": False,
        "subsystems": [],
    },
    # ── Data & ML ─────────────────────────────────────────────────────────
    "murphy-data": {
        "display_name": "Murphy Data",
        "topic": "Data pipelines, archiving, and vector stores",
        "encrypted": False,
        "subsystems": [
            "data_pipeline_orchestrator",
            "data_archive_manager",
            "rag_vector_integration",
        ],
    },
    "murphy-mfgc": {
        "display_name": "Murphy MFGC",
        "topic": "Manufacturing core adapter and metrics",
        "encrypted": False,
        "subsystems": ["mfgc_core", "mfgc_adapter", "mfgc_metrics", "mfgc_v1_1"],
    },
    "murphy-foundation": {
        "display_name": "Murphy Foundation",
        "topic": "Foundation model layer and base capabilities",
        "encrypted": False,
        "subsystems": ["murphy_foundation_model"],
    },
    "murphy-ml": {
        "display_name": "Murphy ML",
        "topic": "ML model registry and strategy engine",
        "encrypted": False,
        "subsystems": ["ml_model_registry", "ml_strategy_engine"],
    },
}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_default_config(domain: str) -> MatrixBridgeConfig:
    """Build a :class:`MatrixBridgeConfig` with all default rooms populated.

    Args:
        domain: Matrix server-name component, e.g. ``"example.com"``.

    Returns:
        A fully populated :class:`MatrixBridgeConfig` ready for use.

    Example::

        cfg = build_default_config("myorg.chat")
    """
    room_mappings: dict[str, RoomMapping] = {}
    for key, defn in DEFAULT_ROOM_DEFINITIONS.items():
        alias = f"#{key}:{domain}"
        room_mappings[key] = RoomMapping(
            room_alias=alias,
            room_id="",
            display_name=defn["display_name"],
            subsystems=list(defn["subsystems"]),
            encrypted=bool(defn.get("encrypted", False)),
            topic=defn.get("topic", ""),
        )

    cfg = MatrixBridgeConfig(
        homeserver_url=f"https://matrix.{domain}",
        bot_user_id=f"@murphy:{domain}",
        domain=domain,
        room_mappings=room_mappings,
    )
    logger.debug(
        "Built default MatrixBridgeConfig for domain=%s with %d rooms",
        domain,
        len(room_mappings),
    )
    return cfg
