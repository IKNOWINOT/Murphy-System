# © 2020 Inoni Limited Liability Company by Corey Post — License: BSL 1.1
"""
Room Cognitive Roles — Murphy System
======================================

Maps every Matrix subsystem room to its MSS cognitive role:

  MAGNIFY  — room adds depth, context, and sub-tasks (+2 RM levels)
  SIMPLIFY — room distils to actionable essentials      (−2 RM levels)
  SOLIDIFY — room locks a plan at RM5 via MFGC gate    (requires ≥ 85 % confidence)

Rules of thumb used for assignment:
  • Knowledge / data / research rooms        → MAGNIFY  (need more context)
  • Monitoring / alerting / triage rooms     → SIMPLIFY (cut noise, surface signal)
  • Governance / compliance / safety rooms   → SOLIDIFY (lock decisions, require confidence)
  • Execution / engineering rooms            → MAGNIFY  (expand specs into tasks)
  • LLM / AI inference rooms                → MAGNIFY  (generative enrichment)
  • Security / audit rooms                   → SOLIDIFY (zero ambiguity allowed)
  • Comms / notification rooms               → SIMPLIFY (short, actionable output)
  • Self-healing / repair rooms              → SOLIDIFY (commit fix plans)

Design:  ROOM-COG-001
Owner:   Platform AI
License: BSL 1.1
Copyright © 2020 Inoni Limited Liability Company — Created by Corey Post
"""

from __future__ import annotations

# Import here so this module can be imported standalone before room_llm_brain
try:
    from room_llm_brain import CognitiveRole
except ImportError:
    try:
        from src.room_llm_brain import CognitiveRole
    except ImportError:
        from enum import Enum
        class CognitiveRole(str, Enum):  # type: ignore[no-redef]
            MAGNIFY  = "magnify"
            SIMPLIFY = "simplify"
            SOLIDIFY = "solidify"
            CALIBRATE = "calibrate"

M = CognitiveRole.MAGNIFY
S = CognitiveRole.SIMPLIFY
L = CognitiveRole.SOLIDIFY  # L for Locked / soLidify


# ---------------------------------------------------------------------------
# Complete room → cognitive role mapping
# One entry per room key in SUBSYSTEM_ROOMS.
# ---------------------------------------------------------------------------

ROOM_COGNITIVE_ROLES: dict[str, CognitiveRole] = {
    # ── Core Engines ────────────────────────────────────────────────────────
    "confidence-engine":              M,   # expand confidence metrics into detail
    "execution-engine":               M,   # expand tasks into execution steps
    "execution-orchestrator":         M,   # magnify flows into sub-orchestrations
    "gate-synthesis":                 L,   # lock gate decisions (MFGC gate)
    "domain-engine":                  M,   # expand domain knowledge
    "domain-expert-system":           M,
    "domain-expert-integration":      M,
    "domain-gate-generator":          L,
    "llm-controller":                 M,   # generative enrichment
    "integration-engine":             M,

    # ── Module System ────────────────────────────────────────────────────────
    "librarian":                      M,   # expand knowledge graph
    "knowledge-graph-builder":        M,
    "knowledge-base-manager":         M,
    "knowledge-gap-system":           M,
    "semantic-search-engine":         M,
    "document-manager":               M,
    "capability-map":                 M,
    "module-compiler":                M,

    # ── Monitoring ──────────────────────────────────────────────────────────
    "learning-engine":                S,   # distil patterns from noise
    "agent-monitor-dashboard":        S,
    "agent-run-recorder":             S,
    "capacity-planning-engine":       S,
    "observability-engine":           S,
    "metrics-collector":              S,
    "alert-manager":                  S,
    "health-checker":                 S,
    "telemetry-system":               S,
    "telemetry-learning":             S,
    "telemetry-evidence":             S,
    "audit-trail-manager":            S,
    "unified-observability-engine":   S,
    "runtime-profile-compiler":       S,
    "operational-dashboard":          S,

    # ── Safety & HITL ────────────────────────────────────────────────────────
    "safety-orchestrator":            L,   # lock safety decisions
    "hitl-graduation-engine":         L,
    "emergency-stop-controller":      L,
    "automation-safeguard-engine":    L,
    "hitl-execution-gate":            L,
    "tos-acceptance-gate":            L,
    "immune-memory":                  L,

    # ── Security ────────────────────────────────────────────────────────────
    "security-plane":                 L,
    "security-plane-adapter":         L,
    "security-audit-scanner":         L,
    "security-hardening-config":      L,
    "fastapi-security":               L,
    "flask-security":                 L,
    "oauth-oidc-provider":            L,
    "csrf-protection":                L,
    "input-validation":               L,
    "secure-key-manager":             L,

    # ── Governance ──────────────────────────────────────────────────────────
    "governance-framework":           L,
    "base-governance-runtime":        L,
    "compliance-engine":              L,
    "governance-kernel":              L,
    "governance-toggle":              L,
    "outreach-compliance-integration":L,
    "contact-compliance-governor":    L,
    "self-marketing-orchestrator":    S,   # simplify marketing output
    "self-introspection":             M,   # expand self-analysis
    "self-codebase-swarm":            M,

    # ── Self-Healing ─────────────────────────────────────────────────────────
    "self-healing-coordinator":       L,   # commit fix plans
    "autonomous-repair-system":       L,
    "bug-pattern-detector":           S,   # simplify bug signals
    "causality-sandbox":              M,   # expand causal analysis
    "simulation-engine":              M,
    "chaos-resilience-loop":          M,
    "error-calibrator":               L,
    "immune-memory":                  L,
    "self-fix-loop":                  L,
    "recursive-stability-controller": L,

    # ── LLM / AI ────────────────────────────────────────────────────────────
    "llm-integration":                M,
    "large-action-model":             M,
    "large-control-model":            M,
    "ml-model-registry":              M,
    "ml-strategy-engine":             M,
    "neuro-symbolic-adapter":         M,
    "federated-learning-coordinator": M,
    "murphy-foundation-model":        M,
    "aionmind":                       M,
    "observation-model":              M,
    "probabilistic-layer":            M,
    "mss-controls":                   M,   # MSS itself is expansion-first
    "mss-sequence-optimizer":         M,

    # ── Data / Knowledge ────────────────────────────────────────────────────
    "persistence-manager":            S,
    "cache":                          S,
    "schema-registry":                S,
    "rosetta":                        M,   # expand agent state context
    "rosetta-stone-heartbeat":        M,
    "swarm-rosetta-bridge":           M,
    "global-aggregator":              S,   # aggregate → simplify
    "rosetta-platform-state":         M,

    # ── Comms / Notifications ────────────────────────────────────────────────
    "comms":                          S,
    "communication-system":           S,
    "email-integration":              S,
    "slack-integration":              S,
    "matrix-bridge":                  S,
    "ambient-intelligence":           M,   # ambient context needs magnification
    "voice-command-interface":        S,
    "ai-comms-orchestrator":          S,
    "comms-hub":                      S,
    "founder-updates":                S,

    # ── Business / Finance ───────────────────────────────────────────────────
    "niche-business-generator":       M,
    "niche-viability-gate":           L,
    "business-scaling-engine":        M,
    "invoice-processing-pipeline":    S,
    "unit-economics-analyzer":        S,
    "cost-optimization-advisor":      S,
    "hidden-cost-tracker":            S,
    "kpi-tracker":                    S,
    "financial-planning":             M,
    "profit-sweep":                   S,

    # ── CRM / Account ────────────────────────────────────────────────────────
    "crm":                            M,
    "account-manager":                M,
    "org-portal":                     M,

    # ── Execution / Automation ───────────────────────────────────────────────
    "full-automation-controller":     M,
    "automation-scheduler":           M,
    "automation-scaler":              M,
    "ci-cd-pipeline-manager":         M,
    "deployment-automation":          L,   # lock deploy plans
    "task-executor":                  M,
    "task-router":                    S,
    "dispatch":                       S,
    "supply-orchestrator":            M,
    "operations-cycle-engine":        M,
    "efficiency-orchestrator":        S,

    # ── Swarm / Agents ───────────────────────────────────────────────────────
    "swarm-agents":                   M,
    "agent-persona-library":          M,
    "true-swarm-system":              M,
    "shadow-agent-integration":       M,
    "all-hands":                      S,   # all-hands meeting → simplify output
    "ceo-branch":                     L,   # CEO decisions must be locked
    "production-assistant-engine":    M,
    "executive-planning-engine":      M,

    # ── Infrastructure ───────────────────────────────────────────────────────
    "runtime":                        S,
    "control-plane":                  L,
    "compute-plane":                  L,
    "deterministic-compute-plane":    L,
    "environment-state-manager":      S,
    "multi-tenant-workspace":         M,
    "tenant-resource-governor":       L,
    "api-gateway-adapter":            S,
    "integration-bus":                S,

    # ── Trading ─────────────────────────────────────────────────────────────
    "trading-strategy-engine":        M,
    "crypto-risk-manager":            L,   # risk decisions locked
    "live-trading-engine":            L,
    "paper-trading-engine":           M,
    "trading-compliance-engine":      L,
    "trading-orchestrator":           M,
    "risk-mitigation-tracker":        S,
    "market-positioning-engine":      M,

    # ── Game Creation ────────────────────────────────────────────────────────
    "game-creation-pipeline":         M,
    "eq-mod-system":                  M,
    "world-generator":                M,
    "balance-engine":                 L,   # lock balance numbers
    "monetization-rules":             L,

    # ── IoT / Industrial ─────────────────────────────────────────────────────
    "building-automation-connectors": M,
    "energy-management-connectors":   S,
    "robotics":                       L,   # actuator commands locked
    "iot-sensors":                    S,   # simplify sensor streams
    "lcm-engine":                     M,

    # ── Key Management ───────────────────────────────────────────────────────
    "deepinfra-key-rotator":               L,
    "secure-key-manager":             L,
    "key-harvester":                  L,
    "credential-profile-system":      L,

    # ── Misc / Additional ────────────────────────────────────────────────────
    "cutsheet-engine":                S,   # distil hardware specs
    "visual-swarm-builder":           M,
    "org-chart-enforcement":          L,
    "org-compiler":                   M,
    "golden-path-engine":             S,   # distil best path
    "golden-path-bridge":             S,
    "triage-rollcall-adapter":        S,
    "ticket-triage-engine":           S,
    "agentic-onboarding-engine":      M,
    "onboarding-flow":                M,
    "ambient-synthesis":              M,
    "historical-greatness-engine":    M,
    "networking-mastery-engine":      M,
    "seo-optimisation-engine":        M,
    "youtube-channel-bootstrap":      M,
    "video-packager":                 S,
    "skill-catalogue-engine":         S,
    "rubix-evidence-adapter":         L,   # evidence locking
    "cyclic-trends-engine":           M,
    "world-knowledge-calibrator":     L,   # calibration sensors → SOLIDIFY
    "room-llm-brain":                 M,   # the brain itself defaults to MAGNIFY
    "agentic-comms-router":           S,   # route messages efficiently
    "bot-room-registry":              S,
    "rosetta-combined-view":          S,
    "optimal-routing-wiring":         S,
    "multicursor-commissioning":      M,
}


def role_for_room(room_key: str) -> CognitiveRole:
    """Return the cognitive role for *room_key*, defaulting to MAGNIFY."""
    return ROOM_COGNITIVE_ROLES.get(room_key, CognitiveRole.MAGNIFY)


def rooms_by_role(role: CognitiveRole) -> list[str]:
    """Return all room keys assigned to *role*, sorted."""
    return sorted(k for k, v in ROOM_COGNITIVE_ROLES.items() if v is role)


def role_summary() -> dict[str, int]:
    """Return ``{role_value: count}`` for all assigned rooms."""
    counts: dict[str, int] = {}
    for r in ROOM_COGNITIVE_ROLES.values():
        counts[r.value] = counts.get(r.value, 0) + 1
    return counts


__all__ = [
    "ROOM_COGNITIVE_ROLES",
    "role_for_room",
    "rooms_by_role",
    "role_summary",
]
