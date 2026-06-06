"""
R425 — Rosetta Task Config (per-role capability/governance/notify config)
=========================================================================

WHAT THIS IS:
  Extends every Rosetta role with 5 new dimensions that turn a role
  identity into a *complete task configuration*:

    1. capability_allowlist        — which endpoint groups this role can
                                     plan over (filters R424's 1,806 caps)
    2. approved_data_streams        — heartbeat-pull data sources permitted
    3. governance_constraints       — compliance + SLA + dollar gates
    4. notify_chain                 — start/stop/fail/succeed routing
    5. repeat_policy                — cadence rules for recurring tasks

WHY IT EXISTS:
  Founder spec: "Rosetta and DLF configuration that is measured for each
  task as an optimized injection of agent identity permissions governance,
  information perspective of information based on job description and
  contract requirements."

  R424 made 1,806 capabilities reachable. Without R425 the reasoning
  engine treats every role equally — VP Sales can plan over the cost
  ledger, CFO can plan over CRM cadence. That's wrong. Each role needs
  its job-description-derived subset.

HOW IT FITS:
  Loaded at startup. Provides get_task_config(role_title, scope) returning
  the merged config. R426 will call this on every cognitive_execute() entry
  to filter the kernel's capability registry into a role-specific view.

KEY CONCEPTS:
  - role_title: existing Rosetta key (ceo, cto, vp-sales, ...)
  - scope: "platform" (founder) or "tenant" (customer instance)
  - Tenants get same base config minus anything tagged mutates_platform

DLF CONTEXT:
  Data Loom Format — the perspective lens shape over data. R425's
  approved_data_streams field is the DLF-allowlist input: the lens shows
  this role only the streams in this list, projected through their
  cognitive lens (R418).

LAST UPDATED: 2026-06-01 by murphy_assistant via R425
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.r425_rosetta_task_config")

# ── Section: Defaults ──────────────────────────────────────────────────────
# These are role-derived defaults. The founder/tenant scope further filters.
# Capability allowlist values are *endpoint group* names (matching R420's
# group tags — e.g. "trading", "billing", "crm", "self").

_PLATFORM_MUTATING_GROUPS = {
    "self", "patches", "gates", "mfgc", "soul", "infrastructure",
    "deployments", "production", "shadow", "incident",
}

_ROLE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "ceo": {
        "capability_allowlist": [
            "founder", "executive", "strategic", "swarm", "ops",
            "billing", "crm", "comms", "hitl",
        ],
        "approved_data_streams": [
            "tenant_daily_pnl", "event_log", "hitl_queue",
            "outreach.cadence", "pipeline.value", "soul.state",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 5000,
            "requires_founder_for_irreversible": True,
            "kin_actions_forbidden": True,
            "soul_violation_blocks_execution": True,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["start", "succeed", "fail"]},
            {"channel": "sms", "to": "+17164003440", "on": ["fail"]},
        ],
        "repeat_policy": {
            "default_cadence": "fibonacci",
            "max_per_hour": 6,
            "backoff_on_fail": "exponential",
            "reflection_after_n_runs": 13,  # fibonacci
        },
    },
    "cto": {
        "capability_allowlist": [
            "self", "patches", "gates", "mfgc", "infrastructure",
            "deployments", "monitoring", "incident", "audit",
        ],
        "approved_data_streams": [
            "event_log", "build_log", "patch_history", "gate_state",
            "rsc_telemetry", "substrate_health",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 1000,
            "no_deploy_without_test": True,
            "no_bypass_mfgc": True,
            "ship_unaudited_to_prod_forbidden": True,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {
            "default_cadence": "fibonacci",
            "max_per_hour": 12,
            "reflection_after_n_runs": 8,
        },
    },
    "cfo": {
        "capability_allowlist": [
            "billing", "ledger", "payments", "treasury", "tax",
            "reporting", "audit", "compliance",
        ],
        "approved_data_streams": [
            "tenant_daily_pnl", "llm_cost_ledger", "payment_events",
            "subscription_state", "tax_obligations",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 2000,
            "double_entry_required": True,
            "no_unmatched_journals": True,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {
            "default_cadence": "daily",
            "max_per_hour": 4,
        },
    },
    "vp-sales": {
        "capability_allowlist": [
            "crm", "outreach", "comms", "pipeline", "leads",
            "calendar", "billing",
        ],
        "approved_data_streams": [
            "crm.leads", "outreach.cadence", "pipeline.value",
            "calendar.events", "inbox.replies",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 500,
            "no_external_email_unapproved_domain": True,
            "max_outreach_per_lead_per_day": 1,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {
            "default_cadence": "every_4h",
            "max_per_hour": 24,
            "reflection_after_n_runs": 21,
        },
    },
    "vp-marketing": {
        "capability_allowlist": [
            "content", "social", "seo", "analytics", "comms", "leads",
        ],
        "approved_data_streams": [
            "site.traffic", "social.metrics", "lead_attribution",
            "content.performance",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 500,
            "no_public_post_without_review": True,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {"default_cadence": "daily", "max_per_hour": 6},
    },
    "vp-product": {
        "capability_allowlist": [
            "product", "roadmap", "features", "feedback", "analytics",
        ],
        "approved_data_streams": [
            "feature.usage", "user.feedback", "roadmap.state",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 500,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {"default_cadence": "daily", "max_per_hour": 6},
    },
    "vp-engineering": {
        "capability_allowlist": [
            "deployments", "monitoring", "incident", "infrastructure",
            "code", "tests",
        ],
        "approved_data_streams": [
            "ci.builds", "deploy.events", "error.rates", "uptime",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 1000,
            "no_deploy_without_test": True,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {"default_cadence": "hourly", "max_per_hour": 30},
    },
    "vp-ops": {
        "capability_allowlist": [
            "ops", "infrastructure", "monitoring", "incident", "logs",
        ],
        "approved_data_streams": [
            "uptime", "rsc_telemetry", "incident.queue",
        ],
        "governance_constraints": {"requires_hitl_above_usd": 1000},
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {"default_cadence": "hourly", "max_per_hour": 30},
    },
    "cso": {  # chief security officer
        "capability_allowlist": [
            "security", "audit", "compliance", "incident", "monitoring",
        ],
        "approved_data_streams": [
            "audit.events", "auth.failures", "secrets.access",
            "incident.queue",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 1000,
            "no_credential_export": True,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
            {"channel": "sms", "to": "+17164003440", "on": ["fail"]},
        ],
        "repeat_policy": {"default_cadence": "hourly", "max_per_hour": 60},
    },
    "general-counsel": {
        "capability_allowlist": [
            "legal", "compliance", "audit", "contracts",
        ],
        "approved_data_streams": [
            "contract.repo", "compliance.state", "audit.events",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 500,
            "external_communication_review": True,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {"default_cadence": "daily", "max_per_hour": 4},
    },
    "chief-of-staff": {
        "capability_allowlist": [
            "ops", "calendar", "comms", "executive", "reporting",
        ],
        "approved_data_streams": [
            "calendar.events", "hitl_queue", "operating.rhythm",
        ],
        "governance_constraints": {
            "requires_hitl_above_usd": 1000,
        },
        "notify_chain": [
            {"channel": "ui", "to": "founder_dashboard", "on": ["fail"]},
        ],
        "repeat_policy": {"default_cadence": "hourly", "max_per_hour": 12},
    },
}


# ── Section: Public API ────────────────────────────────────────────────────
def get_task_config(
    role_title: str,
    *,
    scope: str = "platform",
) -> Optional[Dict[str, Any]]:
    """Return the merged task config for (role_title, scope).

    Args:
        role_title: Existing Rosetta role key (ceo, cto, vp-sales, ...).
        scope: "platform" for founder, "tenant" for customer-instance roles.
            Tenant scope removes platform-mutating capability groups from
            the allowlist.

    Returns:
        Dict with 5 keys, or None if role unknown:
          capability_allowlist, approved_data_streams,
          governance_constraints, notify_chain, repeat_policy
    """
    cfg = _ROLE_CONFIGS.get(role_title.lower())
    if cfg is None:
        return None

    out = json.loads(json.dumps(cfg))  # deep copy

    if scope == "tenant":
        # Strip platform-mutating groups from the allowlist
        out["capability_allowlist"] = [
            g for g in out["capability_allowlist"]
            if g not in _PLATFORM_MUTATING_GROUPS
        ]
        out["_scope"] = "tenant"
        out["_platform_groups_stripped"] = True
    else:
        out["_scope"] = "platform"

    out["_role_title"] = role_title
    return out


def list_configured_roles() -> List[str]:
    """All role_titles with a task config defined."""
    return sorted(_ROLE_CONFIGS.keys())


def filter_capabilities_for_role(
    capability_ids: List[str],
    role_title: str,
    *,
    scope: str = "platform",
    capability_groups_by_id: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Filter a list of capability_ids to only those allowed for this role.

    Args:
        capability_ids: All capability IDs in the kernel registry.
        role_title: Rosetta role.
        scope: platform or tenant.
        capability_groups_by_id: Optional map of {cap_id -> group}. If
            absent, we parse the group out of the cap_id metadata at the
            caller. R426 will pass this map.

    Returns:
        Subset of capability_ids the role is allowed to plan over.
    """
    cfg = get_task_config(role_title, scope=scope)
    if cfg is None:
        return []  # unknown role gets nothing
    allowlist = set(cfg["capability_allowlist"])
    if not capability_groups_by_id:
        # Conservative — without group info, allow nothing
        return []
    return [
        cid for cid in capability_ids
        if capability_groups_by_id.get(cid) in allowlist
    ]
