"""
Murphy System Runtime Pack Registry
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1

Central catalogue of all available domain packs and the capabilities each
pack provides.  When adding a new module to Murphy System, register it here.

Developer Guide (see also docs/CONTRIBUTING_RUNTIME.md):
  1. Create a RuntimePack in this file describing your domain.
  2. Add its capability strings to CAPABILITY_TO_PACK.
  3. Implement an optional router_factory if your pack exposes API routes.
  4. Add optional on_load / on_unload hooks for resource setup/teardown.

src/runtime/runtime_packs/registry.py
Canonical pack definitions for the Murphy System tiered runtime.

This module owns:
- The ``KERNEL``, ``PLATFORM``, and ``DOMAIN`` :class:`RuntimePack`
  definitions that are registered into a fresh
  :class:`~src.runtime.tiered_orchestrator.TieredOrchestrator`.
- The ``CAPABILITY_TO_PACK`` mapping that translates onboarding capability
  strings (as produced by ``onboarding_flow._infer_capabilities()``) to the
  domain pack that satisfies them.

Module paths reference Python import paths relative to the repository root
(e.g. ``src.confidence_engine``).  All imports are **lazy** -- they only
happen when the pack is actually loaded via
:meth:`~src.runtime.tiered_orchestrator.TieredOrchestrator.load_pack`.

Python 3.9+ compatible.

Copyright (c) 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1
"""

from __future__ import annotations

from typing import Dict, List

from src.runtime.tiered_orchestrator import RuntimePack


# ---------------------------------------------------------------------------
# Capability → pack-name mapping
#
# Used by the boot dispatcher to answer: "which pack do I need to serve
# capability X?"  Keep in alphabetical order within each pack group.
# ---------------------------------------------------------------------------

CAPABILITY_TO_PACK: Dict[str, str] = {
    # ── Core ────────────────────────────────────────────────────────────────
    "auth": "core",
    "health": "core",
    "profiles": "core",
    "sessions": "core",
    # ── Compliance ──────────────────────────────────────────────────────────
    "compliance": "compliance",
    "gdpr": "compliance",
    "hipaa": "compliance",
    "soc2": "compliance",
    # ── Analytics ───────────────────────────────────────────────────────────
    "analytics": "analytics",
    "dashboards": "analytics",
    "metrics": "analytics",
    "reporting": "analytics",
    # ── Workflows ───────────────────────────────────────────────────────────
    "automations": "workflows",
    "scheduling": "workflows",
    "workflows": "workflows",
    # ── Integrations ────────────────────────────────────────────────────────
    "crm": "integrations",
    "integrations": "integrations",
    "oauth": "integrations",
    "webhooks": "integrations",
    # ── Communications ──────────────────────────────────────────────────────
    "communications": "communications",
    "email": "communications",
    "matrix": "communications",
    "messaging": "communications",
    # ── AI / ML ─────────────────────────────────────────────────────────────
    "ai": "ai_ml",
    "embeddings": "ai_ml",
    "llm": "ai_ml",
    "nlp": "ai_ml",
    # ── HVAC (domain-specific, not loaded by default) ────────────────────────
    "energy_management": "hvac",
    "hvac": "hvac",
    # ── Finance ─────────────────────────────────────────────────────────────
    "billing": "finance",
    "finance": "finance",
    "invoicing": "finance",
    "payments": "finance",
    # ── Self-Healing ────────────────────────────────────────────────────────
    "self_fix": "self_healing",
    "self_healing": "self_healing",
    "self_improvement": "self_healing",
}


# ---------------------------------------------------------------------------
# Pack definitions
#
# Each pack should declare the superset of capabilities it provides so the
# boot dispatcher can load it on demand.
# ---------------------------------------------------------------------------

def _make_core_pack() -> RuntimePack:
    return RuntimePack(
        name="core",
        capabilities={"auth", "health", "profiles", "sessions"},
        description="Authentication, health checks, and user profile management.",
        version="1.0.0",
    )


def _make_compliance_pack() -> RuntimePack:
    return RuntimePack(
        name="compliance",
        capabilities={"compliance", "gdpr", "hipaa", "soc2"},
        description="Regulatory compliance frameworks: GDPR, HIPAA, SOC 2, and more.",
        version="1.0.0",
    )


def _make_analytics_pack() -> RuntimePack:
    return RuntimePack(
        name="analytics",
        capabilities={"analytics", "dashboards", "metrics", "reporting"},
        description="Analytics dashboards, reporting, and metric aggregation.",
        version="1.0.0",
    )


def _make_workflows_pack() -> RuntimePack:
    return RuntimePack(
        name="workflows",
        capabilities={"automations", "scheduling", "workflows"},
        description="Workflow generation, scheduling, and automation execution.",
        version="1.0.0",
    )


def _make_integrations_pack() -> RuntimePack:
    return RuntimePack(
        name="integrations",
        capabilities={"crm", "integrations", "oauth", "webhooks"},
        description="Third-party integrations: CRM, OAuth providers, webhooks.",
        version="1.0.0",
    )


def _make_communications_pack() -> RuntimePack:
    return RuntimePack(
        name="communications",
        capabilities={"communications", "email", "matrix", "messaging"},
        description="Email, Matrix, and general messaging integrations.",
        version="1.0.0",
    )


def _make_ai_ml_pack() -> RuntimePack:
    return RuntimePack(
        name="ai_ml",
        capabilities={"ai", "embeddings", "llm", "nlp"},
        description="LLM inference, NLP pipelines, and vector embeddings.",
        version="1.0.0",
    )


def _make_hvac_pack() -> RuntimePack:
    return RuntimePack(
        name="hvac",
        capabilities={"energy_management", "hvac"},
        description="HVAC and energy management — only loaded when explicitly requested.",
        version="1.0.0",
    )


def _make_finance_pack() -> RuntimePack:
    return RuntimePack(
        name="finance",
        capabilities={"billing", "finance", "invoicing", "payments"},
        description="Billing, invoicing, and payment processing.",
        version="1.0.0",
    )


def _make_self_healing_pack() -> RuntimePack:
    return RuntimePack(
        name="self_healing",
        capabilities={"self_fix", "self_healing", "self_improvement"},
        description="Self-fix loop, autonomous repair, and self-improvement engine.",
        version="1.0.0",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PACK_FACTORIES = [
    _make_core_pack,
    _make_compliance_pack,
    _make_analytics_pack,
    _make_workflows_pack,
    _make_integrations_pack,
    _make_communications_pack,
    _make_ai_ml_pack,
    _make_hvac_pack,
    _make_finance_pack,
    _make_self_healing_pack,
]


def get_all_packs() -> List[RuntimePack]:
    """Return a fresh list of all registered RuntimePack instances."""
    return [factory() for factory in _PACK_FACTORIES]


def get_pack_for_capability(capability: str) -> str | None:
    """Return the pack name that provides *capability*, or None if unknown."""
    return CAPABILITY_TO_PACK.get(capability)


def get_capabilities_for_pack(pack_name: str) -> List[str]:
    """Return the list of capabilities provided by *pack_name*."""
    return [cap for cap, pname in CAPABILITY_TO_PACK.items() if pname == pack_name]
from src.runtime.tiered_orchestrator import RuntimePack, RuntimeTier

# ---------------------------------------------------------------------------
# Capability → Pack mapping
# ---------------------------------------------------------------------------

#: Maps onboarding capability tag strings to the domain pack that satisfies
#: them.  Merged from both simple and tiered pack naming schemes.
CAPABILITY_TO_PACK: Dict[str, str] = {
    # ── Core (simple packs) ────────────────────────────────────────────────
    "auth": "core",
    "health": "core",
    "profiles": "core",
    "sessions": "core",
    # ── Compliance ─────────────────────────────────────────────────────────
    "compliance": "compliance",
    "gdpr": "compliance",
    "hipaa": "compliance",
    "soc2": "compliance",
    # ── Analytics ──────────────────────────────────────────────────────────
    "analytics": "analytics",
    "dashboards": "analytics",
    "metrics": "analytics",
    "reporting": "analytics",
    # ── Workflows ──────────────────────────────────────────────────────────
    "automations": "workflows",
    "scheduling": "workflows",
    "workflows": "workflows",
    # ── Integrations ───────────────────────────────────────────────────────
    "crm": "integrations",
    "integrations": "integrations",
    "oauth": "integrations",
    "webhooks": "integrations",
    # ── Communications ─────────────────────────────────────────────────────
    "communications": "communications",
    "email": "communications",
    "matrix": "communications",
    "messaging": "communications",
    # ── AI / ML ────────────────────────────────────────────────────────────
    "ai": "ai_ml",
    "embeddings": "ai_ml",
    "llm": "ai_ml",
    "nlp": "ai_ml",
    # ── HVAC ───────────────────────────────────────────────────────────────
    "energy_management": "hvac",
    "hvac": "hvac",
    # ── Finance ────────────────────────────────────────────────────────────
    "billing": "finance",
    "finance": "finance",
    "invoicing": "finance",
    "payments": "finance",
    # ── Self-Healing ───────────────────────────────────────────────────────
    "self_fix": "self_healing",
    "self_healing": "self_healing",
    "self_improvement": "self_healing",
    # ── Domain packs (tiered runtime) ──────────────────────────────────────
    "crm_automation": "domain_crm",
    "communication_automation": "domain_matrix",
    "reporting_automation": "domain_observability",
    "notification_automation": "domain_matrix",
    "code_management": "domain_onboarding",
    "project_tracking": "domain_onboarding",
    "data_processing": "domain_ml",
    "scheduling_automation": "domain_onboarding",
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
    # ── Ambient Intelligence ────────────────────────────────────────────────
    "ambient_intelligence": "domain_ambient",
    "ambient_context": "domain_ambient",
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
    RuntimePack(
        name="domain_ambient",
        tier=RuntimeTier.DOMAIN,
        modules=[
            "src.ambient_context_store",
            "src.ambient_api_router",
        ],
        dependencies=["platform_persistence"],
        capabilities=["ambient_intelligence", "ambient_context"],
        api_routers=["src.ambient_api_router:router"],
        idle_timeout_minutes=30,
        max_memory_mb=128,
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
