"""
Room Router for the Murphy Matrix Bridge.

Maps every Murphy System module (200+) to its corresponding Matrix room alias,
and provides lookup helpers for both module names and event types.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import ClassVar

from .config import MatrixBridgeConfig, RoomMapping

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Master module-to-room mapping (200+ modules)
# ---------------------------------------------------------------------------

MODULE_TO_ROOM: dict[str, str] = {
    # ── Core ────────────────────────────────────────────────────────────
    "system_integrator": "murphy-core",
    "modular_runtime": "murphy-runtime",
    "config": "murphy-config",
    "env_manager": "murphy-config",
    "murphy_terminal": "murphy-terminal",
    "command_system": "murphy-terminal",
    "command_parser": "murphy-terminal",
    "module_manager": "murphy-runtime",
    "module_registry": "murphy-runtime",
    "secure_key_manager": "murphy-config",
    "setup_wizard": "murphy-core",
    "murphy_core": "murphy-core",
    # ── Governance ───────────────────────────────────────────────────────
    "governance_kernel": "murphy-governance",
    "governance_toggle": "murphy-governance",
    "rbac_governance": "murphy-governance",
    "gate_builder": "murphy-gates",
    "gate_bypass_controller": "murphy-gates",
    "authority_gate": "murphy-gates",
    "cost_explosion_gate": "murphy-gates",
    "niche_viability_gate": "murphy-gates",
    "inference_gate_engine": "murphy-gates",
    # ── HITL ────────────────────────────────────────────────────────────
    "hitl_autonomy_controller": "murphy-hitl",
    "hitl_graduation_engine": "murphy-hitl",
    # ── Execution ────────────────────────────────────────────────────────
    "execution_compiler": "murphy-execution",
    "deterministic_routing_engine": "murphy-execution",
    "deterministic_compute": "murphy-execution",
    "finish_line_controller": "murphy-execution",
    "murphy_action_engine": "murphy-execution",
    "full_automation_controller": "murphy-automation",
    "automation_mode_controller": "murphy-automation",
    "automation_scheduler": "murphy-automation",
    "automation_scaler": "murphy-automation",
    "probabilistic_layer": "murphy-confidence",
    # ── Security ────────────────────────────────────────────────────────
    "fastapi_security": "murphy-security",
    "flask_security": "murphy-security",
    "oauth_oidc_provider": "murphy-security",
    "murphy_credential_gate": "murphy-security",
    "security_audit_scanner": "murphy-security",
    "security_hardening_config": "murphy-security",
    "security_plane_adapter": "murphy-security",
    "input_validation": "murphy-security",
    # ── Audit ────────────────────────────────────────────────────────────
    "audit_logging_system": "murphy-audit",
    "blockchain_audit_trail": "murphy-audit",
    "contractual_audit": "murphy-audit",
    "dependency_audit_engine": "murphy-audit",
    # ── Compliance ───────────────────────────────────────────────────────
    "compliance_engine": "murphy-compliance",
    "compliance_as_code_engine": "murphy-compliance",
    "compliance_automation_bridge": "murphy-compliance",
    "compliance_monitoring_completeness": "murphy-compliance",
    "compliance_orchestration_bridge": "murphy-compliance",
    "compliance_region_validator": "murphy-compliance",
    "compliance_report_aggregator": "murphy-compliance",
    # ── LLM ──────────────────────────────────────────────────────────────
    "llm_integration": "murphy-llm",
    "llm_integration_layer": "murphy-llm",
    "llm_controller": "murphy-llm",
    "llm_output_validator": "murphy-llm",
    "llm_provider_router": "murphy-llm",
    "openai_compatible_provider": "murphy-llm",
    "enhanced_local_llm": "murphy-llm",
    "local_llm_fallback": "murphy-llm",
    "local_inference_engine": "murphy-llm",
    "local_model_layer": "murphy-llm",
    "prompt_amplifier": "murphy-llm",
    # ── Intelligence ─────────────────────────────────────────────────────
    "reasoning_engine": "murphy-intelligence",
    "concept_graph_engine": "murphy-intelligence",
    "knowledge_graph_builder": "murphy-intelligence",
    "knowledge_base_manager": "murphy-intelligence",
    "knowledge_gap_system": "murphy-intelligence",
    "rag_vector_integration": "murphy-data",
    "neuro_symbolic_adapter": "murphy-intelligence",
    "large_action_model": "murphy-intelligence",
    "domain_engine": "murphy-intelligence",
    # ── Swarm ────────────────────────────────────────────────────────────
    "advanced_swarm_system": "murphy-swarm",
    "domain_swarms": "murphy-swarm",
    "durable_swarm_orchestrator": "murphy-swarm",
    "murphy_crew_system": "murphy-swarm",
    # ── Learning ─────────────────────────────────────────────────────────
    "learning_system": "murphy-learning",
    "federated_learning_coordinator": "murphy-learning",
    "feedback_integrator": "murphy-learning",
    "murphy_shadow_trainer": "murphy-learning",
    # ── Finance ──────────────────────────────────────────────────────────
    "invoice_processing_pipeline": "murphy-finance",
    "financial_reporting_engine": "murphy-finance",
    "budget_aware_processor": "murphy-finance",
    "kpi_tracker": "murphy-finance",
    "cost_optimization_advisor": "murphy-finance",
    "market_data_feed": "murphy-finance",
    # ── Crypto ───────────────────────────────────────────────────────────
    "crypto_exchange_connector": "murphy-crypto",
    "crypto_portfolio_tracker": "murphy-crypto",
    "crypto_risk_manager": "murphy-crypto",
    "crypto_wallet_manager": "murphy-crypto",
    "coinbase_connector": "murphy-crypto",
    # ── Business ─────────────────────────────────────────────────────────
    "niche_business_generator": "murphy-business",
    "business_scaling_engine": "murphy-business",
    "executive_planning_engine": "murphy-business",
    "competitive_intelligence_engine": "murphy-business",
    "innovation_farmer": "murphy-business",
    # ── Marketing ────────────────────────────────────────────────────────
    "marketing_analytics_aggregator": "murphy-marketing",
    "adaptive_campaign_engine": "murphy-marketing",
    "campaign_orchestrator": "murphy-marketing",
    # ── Content ──────────────────────────────────────────────────────────
    "content_pipeline_engine": "murphy-content",
    "content_creator_platform_modulator": "murphy-content",
    "digital_asset_generator": "murphy-content",
    "image_generation_engine": "murphy-content",
    "murphy_drawing_engine": "murphy-content",
    "faq_generation_engine": "murphy-content",
    "video_packager": "murphy-content",
    "youtube_uploader": "murphy-content",
    "auto_documentation_engine": "murphy-content",
    # ── CRM / Org ────────────────────────────────────────────────────────
    "customer_communication_manager": "murphy-crm",
    "multi_tenant_workspace": "murphy-crm",
    "organization_chart_system": "murphy-org",
    "org_chart_enforcement": "murphy-org",
    "inoni_org_bootstrap": "murphy-org",
    "organizational_context_system": "murphy-org",
    # ── Onboarding ───────────────────────────────────────────────────────
    "onboarding_flow": "murphy-onboarding",
    "onboarding_automation_engine": "murphy-onboarding",
    "onboarding_team_pipeline": "murphy-onboarding",
    "agentic_onboarding_engine": "murphy-onboarding",
    # ── Infrastructure ────────────────────────────────────────────────────
    "docker_containerization": "murphy-infra",
    "kubernetes_deployment": "murphy-infra",
    "hetzner_deploy": "murphy-infra",
    "cloudflare_deploy": "murphy-infra",
    "multi_cloud_orchestrator": "murphy-infra",
    "ci_cd_pipeline_manager": "murphy-infra",
    "deployment_automation_controller": "murphy-infra",
    "geographic_load_balancer": "murphy-infra",
    "resource_scaling_controller": "murphy-infra",
    "capacity_planning_engine": "murphy-infra",
    "backup_disaster_recovery": "murphy-infra",
    "blackstart_controller": "murphy-infra",
    "emergency_stop_controller": "murphy-infra",
    # ── Health ───────────────────────────────────────────────────────────
    "health_monitor": "murphy-health",
    "heartbeat_liveness_protocol": "murphy-health",
    "chaos_resilience_loop": "murphy-health",
    "autonomous_repair_system": "murphy-health",
    "murphy_code_healer": "murphy-health",
    "code_repair_engine": "murphy-health",
    "predictive_failure_engine": "murphy-health",
    "predictive_maintenance_engine": "murphy-health",
    "bug_pattern_detector": "murphy-health",
    "self_fix_loop": "murphy-health",
    "self_healing_coordinator": "murphy-health",
    "activated_heartbeat_runner": "murphy-health",
    # ── IoT ──────────────────────────────────────────────────────────────
    "building_automation_connectors": "murphy-iot",
    "energy_management_connectors": "murphy-iot",
    "additive_manufacturing_connectors": "murphy-iot",
    "manufacturing_automation_standards": "murphy-iot",
    "murphy_sensor_fusion": "murphy-iot",
    "digital_twin_engine": "murphy-iot",
    "murphy_autonomous_perception": "murphy-iot",
    "computer_vision_pipeline": "murphy-iot",
    # ── Telemetry ────────────────────────────────────────────────────────
    "logging_system": "murphy-telemetry",
    "murphy_trace": "murphy-telemetry",
    "metrics": "murphy-telemetry",
    "prometheus_metrics_exporter": "murphy-telemetry",
    "observability_counters": "murphy-telemetry",
    "log_analysis_engine": "murphy-telemetry",
    "causal_spike_analyzer": "murphy-telemetry",
    "bot_telemetry_normalizer": "murphy-telemetry",
    "statistics_collector": "murphy-telemetry",
    # ── Dashboards ───────────────────────────────────────────────────────
    "analytics_dashboard": "murphy-dashboards",
    "agent_monitor_dashboard": "murphy-dashboards",
    "operational_dashboard_aggregator": "murphy-dashboards",
    "operational_slo_tracker": "murphy-dashboards",
    "operational_completeness": "murphy-dashboards",
    "functionality_heatmap": "murphy-dashboards",
    "advanced_reports": "murphy-dashboards",
    "viewport_content_resolver": "murphy-dashboards",
    "artifact_viewport": "murphy-dashboards",
    "artifact_viewport_api": "murphy-dashboards",
    # ── Alerts ───────────────────────────────────────────────────────────
    "alert_rules_engine": "murphy-alerts",
    # ── Integrations ─────────────────────────────────────────────────────
    "integration_bus": "murphy-integrations",
    "enterprise_integrations": "murphy-integrations",
    "platform_connector_framework": "murphy-integrations",
    "cross_platform_data_sync": "murphy-integrations",
    "remote_access_connector": "murphy-integrations",
    "api_gateway_adapter": "murphy-integrations",
    "agentic_api_provisioner": "murphy-integrations",
    "graphql_api_layer": "murphy-integrations",
    "universal_integration_adapter": "murphy-integrations",
    "api_collection_agent": "murphy-integrations",
    # ── Comms ────────────────────────────────────────────────────────────
    "email_integration": "murphy-comms",
    "notification_system": "murphy-comms",
    "announcer_voice_engine": "murphy-comms",
    "webhook_dispatcher": "murphy-comms",
    # ── Dev ──────────────────────────────────────────────────────────────
    "code_generation_gateway": "murphy-bots-engineering",
    "multi_language_codegen": "murphy-bots-engineering",
    "architecture_evolution": "murphy-dev",
    "ab_testing_framework": "murphy-dev",
    "ai_workflow_generator": "murphy-dev",
    "advanced_research": "murphy-bots-analysis",
    # ── Data ─────────────────────────────────────────────────────────────
    "data_pipeline_orchestrator": "murphy-data",
    "data_archive_manager": "murphy-data",
    # ── ML ───────────────────────────────────────────────────────────────
    "ml_model_registry": "murphy-ml",
    "ml_strategy_engine": "murphy-ml",
    # ── MFGC ─────────────────────────────────────────────────────────────
    "mfgc_core": "murphy-mfgc",
    "mfgc_adapter": "murphy-mfgc",
    "mfgc_metrics": "murphy-mfgc",
    "mfgc_v1_1": "murphy-mfgc",
    # ── Foundation ───────────────────────────────────────────────────────
    "murphy_foundation_model": "murphy-foundation",
    # ── Auar ─────────────────────────────────────────────────────────────
    "auar": "murphy-governance",
    "auar_api": "murphy-governance",
    # ── Agent/Persona ────────────────────────────────────────────────────
    "agent_run_recorder": "murphy-telemetry",
    "agent_persona_library": "murphy-personas",
    # ── Account/Workspace ────────────────────────────────────────────────
    "account_management": "murphy-crm",
    # ── Adapter frameworks ───────────────────────────────────────────────
    "adapter_framework": "murphy-integrations",
    # ── Automations sub-package ──────────────────────────────────────────
    "automations": "murphy-automation",
    "automations_engine": "murphy-automation",
    "automations_models": "murphy-automation",
    "automations_api": "murphy-automation",
    # ── Aionmind ─────────────────────────────────────────────────────────
    "aionmind": "murphy-intelligence",
}

# ---------------------------------------------------------------------------
# Event-type-to-room mapping (derived from event_backbone.EventType)
# ---------------------------------------------------------------------------

EVENT_TYPE_TO_ROOM: dict[str, str] = {
    "task_submitted": "murphy-execution",
    "task_completed": "murphy-execution",
    "task_failed": "murphy-execution",
    "gate_evaluated": "murphy-gates",
    "gate_blocked": "murphy-gates",
    "delivery_requested": "murphy-execution",
    "delivery_completed": "murphy-execution",
    "audit_logged": "murphy-audit",
    "learning_feedback": "murphy-learning",
    "swarm_spawned": "murphy-swarm",
    "hitl_required": "murphy-hitl",
    "hitl_resolved": "murphy-hitl",
    "persistence_snapshot": "murphy-core",
    "system_health": "murphy-health",
    "recalibration_start": "murphy-health",
    "rosetta_updated": "murphy-core",
    "self_fix_started": "murphy-health",
    "self_fix_plan_created": "murphy-health",
    "self_fix_executed": "murphy-health",
    "self_fix_tested": "murphy-health",
    "self_fix_verified": "murphy-health",
    "self_fix_completed": "murphy-health",
    "self_fix_rolled_back": "murphy-health",
    "bot_heartbeat_ok": "murphy-telemetry",
    "bot_heartbeat_failed": "murphy-alerts",
    "bot_heartbeat_missed": "murphy-alerts",
    "bot_heartbeat_recovery_started": "murphy-health",
    "bot_heartbeat_recovered": "murphy-health",
    "supervisor_child_started": "murphy-ops",
    "supervisor_child_stopped": "murphy-ops",
    "supervisor_child_restarted": "murphy-ops",
    "supervisor_child_failed": "murphy-alerts",
    "supervisor_child_escalated": "murphy-alerts",
    "supervisor_critical": "murphy-alerts",
    "alert_fired": "murphy-alerts",
    "alert_resolved": "murphy-alerts",
    "metric_recorded": "murphy-telemetry",
    "anomaly_detected": "murphy-alerts",
    "chaos_experiment_started": "murphy-health",
    "chaos_experiment_completed": "murphy-health",
    "chaos_scorecard_generated": "murphy-health",
    "chaos_gaps_submitted": "murphy-health",
    "fleet_reconciliation_started": "murphy-infra",
    "fleet_bot_spawned": "murphy-infra",
    "fleet_bot_despawned": "murphy-infra",
    "fleet_bot_updated": "murphy-infra",
    "fleet_reconciled": "murphy-infra",
    "fleet_drift_detected": "murphy-infra",
    "prediction_generated": "murphy-intelligence",
    "prediction_preempted": "murphy-intelligence",
    "prediction_materialized": "murphy-intelligence",
    "prediction_false_positive": "murphy-intelligence",
    "immune_cycle_started": "murphy-health",
    "immune_cycle_completed": "murphy-health",
    "drift_detected": "murphy-health",
    "failure_predicted": "murphy-health",
    "immunity_recalled": "murphy-health",
    "chaos_validated": "murphy-health",
    "cascade_checked": "murphy-health",
}


# ---------------------------------------------------------------------------
# RoomRouter class
# ---------------------------------------------------------------------------


class RoomRouter:
    """Routes Murphy modules and event types to Matrix rooms.

    The router is initialised from a :class:`~config.MatrixBridgeConfig`
    and provides O(1) lookups from module name or event type to a
    ``#room-alias:domain`` string.

    Args:
        config: The active :class:`~config.MatrixBridgeConfig`.
    """

    def __init__(self, config: MatrixBridgeConfig) -> None:
        self._config = config
        # Mutable per-instance overrides on top of the class-level constant
        self._module_map: dict[str, str] = dict(MODULE_TO_ROOM)
        self._event_map: dict[str, str] = dict(EVENT_TYPE_TO_ROOM)
        logger.debug(
            "RoomRouter initialised with %d module mappings and %d event mappings",
            len(self._module_map),
            len(self._event_map),
        )

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def get_room_for_module(self, module_name: str) -> str | None:
        """Return the fully-qualified Matrix room alias for a Murphy module.

        Args:
            module_name: The Python module/component name (e.g.
                ``"health_monitor"``).

        Returns:
            A room alias string like ``"#murphy-health:example.com"``, or
            ``None`` if no mapping exists.
        """
        room_key = self._module_map.get(module_name)
        if room_key is None:
            logger.debug("No room mapping found for module '%s'", module_name)
            return None
        mapping = self._config.room_mappings.get(room_key)
        if mapping is None:
            return f"#{room_key}:{self._config.domain}"
        return mapping.room_alias

    def get_room_for_event_type(self, event_type: str) -> str | None:
        """Return the fully-qualified Matrix room alias for a Murphy event type.

        Args:
            event_type: An :class:`~event_backbone.EventType` value string
                (e.g. ``"system_health"``).

        Returns:
            A room alias string, or ``None`` if no mapping exists.
        """
        room_key = self._event_map.get(event_type)
        if room_key is None:
            logger.debug("No room mapping found for event type '%s'", event_type)
            return None
        mapping = self._config.room_mappings.get(room_key)
        if mapping is None:
            return f"#{room_key}:{self._config.domain}"
        return mapping.room_alias

    def get_all_rooms(self) -> list[RoomMapping]:
        """Return all :class:`~config.RoomMapping` objects from the config.

        Returns:
            List of all registered :class:`~config.RoomMapping` instances.
        """
        return list(self._config.room_mappings.values())

    def get_subsystem_rooms(self, subsystem: str) -> list[RoomMapping]:
        """Return rooms that list *subsystem* in their ``subsystems`` field.

        Args:
            subsystem: The Murphy module/subsystem name to search for.

        Returns:
            List of matching :class:`~config.RoomMapping` objects.
        """
        return [
            rm
            for rm in self._config.room_mappings.values()
            if subsystem in rm.subsystems
        ]

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_mapping(self, module_name: str, room_alias: str) -> None:
        """Add or update a module-to-room mapping at runtime.

        Args:
            module_name: Murphy module name.
            room_alias: Target room alias or room key (e.g.
                ``"murphy-health"``).
        """
        self._module_map[module_name] = room_alias
        logger.info(
            "Added module mapping: %s → %s", module_name, room_alias
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the router's runtime state to a JSON-compatible dict.

        Returns:
            Dictionary with ``module_map`` and ``event_map`` keys.
        """
        return {
            "module_map": dict(self._module_map),
            "event_map": dict(self._event_map),
        }

    @classmethod
    def from_dict(
        cls, data: dict, config: MatrixBridgeConfig
    ) -> "RoomRouter":
        """Restore a :class:`RoomRouter` from a serialised dict.

        Args:
            data: Dictionary previously produced by :meth:`to_dict`.
            config: The active :class:`~config.MatrixBridgeConfig`.

        Returns:
            A new :class:`RoomRouter` with the stored mappings applied.
        """
        router = cls(config)
        router._module_map.update(data.get("module_map", {}))
        router._event_map.update(data.get("event_map", {}))
        logger.debug("RoomRouter restored from dict")
        return router
