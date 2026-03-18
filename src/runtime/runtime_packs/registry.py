# Copyright © 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1
"""
src/runtime/runtime_packs/registry.py
=======================================
Canonical pack definitions for the Murphy System tiered runtime.

This module owns:
- The ``KERNEL``, ``PLATFORM``, and ``DOMAIN`` :class:`RuntimePack`
  definitions that are registered into a fresh
  :class:`~src.runtime.tiered_orchestrator.TieredOrchestrator`.
- The ``CAPABILITY_TO_PACK`` mapping that translates onboarding capability
  strings (as produced by ``onboarding_flow._infer_capabilities()``) to the
  domain pack that satisfies them.

Module paths reference Python import paths relative to the repository root
(e.g. ``src.confidence_engine``).  All imports are **lazy** — they only
happen when the pack is actually loaded via
:meth:`~src.runtime.tiered_orchestrator.TieredOrchestrator.load_pack`.

Python 3.9+ compatible.
"""

from __future__ import annotations

from typing import Dict, List

from src.runtime.tiered_orchestrator import RuntimePack, RuntimeTier


# ---------------------------------------------------------------------------
# Capability → Pack mapping
# ---------------------------------------------------------------------------

#: Maps onboarding capability tag strings to the domain pack that satisfies
#: them.  Keys are the strings returned by
#: ``onboarding_flow._infer_capabilities()``.
CAPABILITY_TO_PACK: Dict[str, str] = {
    "crm_automation": "domain_crm",
    "communication_automation": "domain_matrix",
    "reporting_automation": "domain_observability",
    "notification_automation": "domain_matrix",
    "code_management": "domain_onboarding",
    "project_tracking": "domain_onboarding",
    "data_processing": "domain_ml",
    "scheduling_automation": "domain_onboarding",
    # Extended mappings
    "hvac_control": "domain_hvac",
    "industrial_control": "domain_hvac",
    "payment_processing": "domain_payments",
    "billing_automation": "domain_payments",
    "content_generation": "domain_content",
    "digital_asset_management": "domain_content",
    "ml_pipeline": "domain_ml",
    "shadow_learning": "domain_ml",
    "matrix_bridge": "domain_matrix",
    "monitoring": "domain_observability",
    "metrics": "domain_observability",
    "alerting": "domain_observability",
    "onboarding": "domain_onboarding",
    "team_pipeline": "domain_onboarding",
}


# ---------------------------------------------------------------------------
# KERNEL packs  (Tier 0 — always loaded, system dies without these)
# ---------------------------------------------------------------------------

_KERNEL_PACKS: List[RuntimePack] = [
    RuntimePack(
        name="kernel_security",
        tier=RuntimeTier.KERNEL,
        modules=[
            "src.security_plane",
            "src.authority_gate",
        ],
        dependencies=[],
        capabilities=["security", "auth_gate"],
        api_routers=[],
        idle_timeout_minutes=0,  # never unloaded
        max_memory_mb=128,
    ),
    RuntimePack(
        name="kernel_events",
        tier=RuntimeTier.KERNEL,
        modules=[
            "src.event_backbone",
        ],
        dependencies=[],
        capabilities=["event_bus", "event_routing"],
        api_routers=[],
        idle_timeout_minutes=0,
        max_memory_mb=128,
    ),
    RuntimePack(
        name="kernel_governance",
        tier=RuntimeTier.KERNEL,
        modules=[
            "src.governance_kernel",
        ],
        dependencies=["kernel_security", "kernel_events"],
        capabilities=["governance", "policy_enforcement"],
        api_routers=[],
        idle_timeout_minutes=0,
        max_memory_mb=128,
    ),
    RuntimePack(
        name="kernel_health",
        tier=RuntimeTier.KERNEL,
        modules=[
            "src.health_monitor",
            "src.shutdown_manager",
        ],
        dependencies=["kernel_events"],
        capabilities=["health_check", "graceful_shutdown"],
        api_routers=[],
        idle_timeout_minutes=0,
        max_memory_mb=64,
    ),
]

# ---------------------------------------------------------------------------
# PLATFORM packs  (Tier 1 — loaded at startup, needed for basic operation)
# ---------------------------------------------------------------------------

_PLATFORM_PACKS: List[RuntimePack] = [
    RuntimePack(
        name="platform_api",
        tier=RuntimeTier.PLATFORM,
        modules=[
            # Core API factory — health, modules, auth routes only,
            # NOT the full 557-route monolith app
            "src.runtime._deps",
        ],
        dependencies=["kernel_security", "kernel_events"],
        capabilities=["http_api", "health_endpoint", "auth_endpoint"],
        api_routers=[],
        idle_timeout_minutes=0,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="platform_llm",
        tier=RuntimeTier.PLATFORM,
        modules=[
            "src.llm_controller",
            "src.openai_compatible_provider",
        ],
        dependencies=["platform_api"],
        capabilities=["llm_inference", "openai_compatible"],
        api_routers=[],
        idle_timeout_minutes=0,
        max_memory_mb=512,
    ),
    RuntimePack(
        name="platform_persistence",
        tier=RuntimeTier.PLATFORM,
        modules=[
            "src.persistence_manager",
        ],
        dependencies=["kernel_security"],
        capabilities=["data_persistence", "db_access"],
        api_routers=[],
        idle_timeout_minutes=0,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="platform_confidence",
        tier=RuntimeTier.PLATFORM,
        modules=[
            "src.confidence_engine",
        ],
        dependencies=["kernel_governance", "platform_llm"],
        capabilities=["confidence_scoring", "gate_synthesis"],
        api_routers=[],
        idle_timeout_minutes=0,
        max_memory_mb=256,
    ),
]

# ---------------------------------------------------------------------------
# DOMAIN packs  (Tier 2 — loaded on-demand based on team / onboarding profile)
# ---------------------------------------------------------------------------

_DOMAIN_PACKS: List[RuntimePack] = [
    RuntimePack(
        name="domain_crm",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.crm_automation",
            "src.outreach_campaign_planner",
            "src.adaptive_campaign_engine",
            "src.competitive_intelligence_engine",
        ],
        dependencies=["platform_persistence", "platform_llm"],
        capabilities=["crm_automation"],
        api_routers=[],
        idle_timeout_minutes=30,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="domain_matrix",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.matrix_bridge.matrix_client",
            "src.matrix_bridge.event_handler",
            "src.matrix_bridge.module_manifest",
        ],
        dependencies=["kernel_events", "platform_api"],
        capabilities=["communication_automation", "notification_automation", "matrix_bridge"],
        api_routers=[],
        idle_timeout_minutes=30,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="domain_content",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.content_generation_engine",
            "src.digital_asset_manager",
            "src.auto_documentation_engine",
            "src.code_generation_gateway",
        ],
        dependencies=["platform_llm", "platform_persistence"],
        capabilities=["content_generation", "digital_asset_management"],
        api_routers=[],
        idle_timeout_minutes=30,
        max_memory_mb=512,
    ),
    RuntimePack(
        name="domain_hvac",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.hvac_controller",
            "src.industrial_protocols",
            "src.sensor_fusion",
        ],
        dependencies=["kernel_events", "platform_persistence"],
        capabilities=["hvac_control", "industrial_control"],
        api_routers=[],
        idle_timeout_minutes=60,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="domain_payments",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.payment_processor",
            "src.billing_manager",
            "src.subscription_manager",
        ],
        dependencies=["kernel_security", "platform_persistence"],
        capabilities=["payment_processing", "billing_automation"],
        api_routers=[],
        idle_timeout_minutes=30,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="domain_onboarding",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.agentic_onboarding_engine",
            "src.onboarding_flow",
            "src.team_pipeline",
        ],
        dependencies=["platform_llm", "platform_persistence", "kernel_governance"],
        capabilities=[
            "onboarding",
            "team_pipeline",
            "code_management",
            "project_tracking",
            "scheduling_automation",
        ],
        api_routers=[],
        idle_timeout_minutes=30,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="domain_observability",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.observability_engine",
            "src.metrics_collector",
            "src.alert_rules_engine",
        ],
        dependencies=["kernel_events", "platform_persistence"],
        capabilities=["monitoring", "metrics", "alerting", "reporting_automation"],
        api_routers=[],
        idle_timeout_minutes=60,
        max_memory_mb=256,
    ),
    RuntimePack(
        name="domain_ml",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.ml_pipeline",
            "src.shadow_learning_engine",
            "src.learning_engine",
        ],
        dependencies=["platform_llm", "platform_persistence"],
        capabilities=["data_processing", "ml_pipeline", "shadow_learning"],
        api_routers=[],
        idle_timeout_minutes=60,
        max_memory_mb=1024,
    ),
]


# ---------------------------------------------------------------------------
# Public factory function
# ---------------------------------------------------------------------------

def get_default_packs() -> List[RuntimePack]:
    """Return the full list of default packs in boot order.

    The order is: KERNEL → PLATFORM → DOMAIN.  Within each tier packs are
    returned in declaration order.

    Returns
    -------
    List[RuntimePack]
        All default packs ready to be registered with a
        :class:`~src.runtime.tiered_orchestrator.TieredOrchestrator`.
    """
    return list(_KERNEL_PACKS) + list(_PLATFORM_PACKS) + list(_DOMAIN_PACKS)
