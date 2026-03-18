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
