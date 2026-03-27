# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Room Registry — maps every Murphy subsystem to a dedicated Matrix room.

Room naming convention: ``#murphy-{subsystem}:{homeserver_domain}``
e.g. ``#murphy-security-plane:example.com``

On startup :meth:`RoomRegistry.ensure_all_rooms` creates any missing rooms
idempotently (safe to call on every restart).

Configuration
-------------
MATRIX_HOMESERVER_DOMAIN   domain part used in room aliases (default ``localhost``)
MATRIX_AUTO_CREATE_ROOMS   ``true`` to auto-create rooms (default ``true``)
MATRIX_ADMIN_USERS         comma-separated list of Matrix user IDs to invite as admins
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .matrix_client import MatrixClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Complete subsystem → (category, encrypted) mapping
# Every Murphy module listed in the problem spec is represented here.
# ---------------------------------------------------------------------------

#: (category_label, encrypted)
_RoomSpec = Tuple[str, bool]

SUBSYSTEM_ROOMS: Dict[str, _RoomSpec] = {
    # ── Core Engines ────────────────────────────────────────────────────────
    "confidence-engine":                ("core-engines", False),
    "execution-engine":                 ("core-engines", False),
    "execution-orchestrator":           ("core-engines", False),
    "gate-synthesis":                   ("core-engines", False),
    "learning-engine":                  ("core-engines", False),
    "integration-engine":               ("core-engines", False),
    "form-intake":                      ("core-engines", False),
    "librarian":                        ("core-engines", False),
    "security-plane":                   ("security", True),
    "control-plane":                    ("core-engines", False),
    "compute-plane":                    ("core-engines", False),

    # ── Governance & Compliance ──────────────────────────────────────────────
    "governance-framework":             ("governance", True),
    "base-governance-runtime":          ("governance", True),
    "compliance-engine":                ("governance", True),
    "compliance-as-code-engine":        ("governance", True),
    "compliance-monitoring":            ("governance", True),
    "rbac-governance":                  ("governance", True),
    "authority-gate":                   ("governance", True),
    "gate-bypass-controller":           ("governance", True),
    "governance-kernel":                ("governance", True),
    "governance-toggle":                ("governance", True),
    "outreach-compliance-integration":  ("governance", True),

    # ── Safety & HITL ────────────────────────────────────────────────────────
    "hitl-autonomy-controller":         ("safety-hitl", False),
    "hitl-graduation-engine":           ("safety-hitl", False),
    "safety-orchestrator":              ("safety-hitl", False),
    "safety-validation-pipeline":       ("safety-hitl", False),
    "safety-gateway-integrator":        ("safety-hitl", False),
    "emergency-stop-controller":        ("safety-hitl", False),
    "freelancer-validator":             ("safety-hitl", False),

    # ── Automation & Execution ───────────────────────────────────────────────
    "automation-scheduler":             ("automation", False),
    "automation-scaler":                ("automation", False),
    "automation-marketplace":           ("automation", False),
    "automation-mode-controller":       ("automation", False),
    "full-automation-controller":       ("automation", False),
    "self-automation-orchestrator":     ("automation", False),
    "murphy-native-automation":         ("automation", False),
    "automation-integration-hub":       ("automation", False),
    "automation-loop-connector":        ("automation", False),
    "automation-rbac-controller":       ("automation", False),
    "automation-readiness-evaluator":   ("automation", False),
    "automation-type-registry":         ("automation", False),

    # ── LLM & AI ────────────────────────────────────────────────────────────
    "llm-integration-layer":            ("llm-ai", False),
    "llm-controller":                   ("llm-ai", False),
    "llm-output-validator":             ("llm-ai", False),
    "llm-routing-completeness":         ("llm-ai", False),
    "llm-swarm-integration":            ("llm-ai", False),
    "enhanced-local-llm":               ("llm-ai", False),
    "local-inference-engine":           ("llm-ai", False),
    "local-llm-fallback":               ("llm-ai", False),
    "local-model-layer":                ("llm-ai", False),
    "safe-llm-wrapper":                 ("llm-ai", False),
    "openai-compatible-provider":       ("llm-ai", False),
    "deepinfra-key-rotator":                 ("llm-ai", True),
    "inference-gate-engine":            ("llm-ai", False),

    # ── Swarm & Agent Systems ────────────────────────────────────────────────
    "advanced-swarm-system":            ("swarm-agents", False),
    "domain-swarms":                    ("swarm-agents", False),
    "durable-swarm-orchestrator":       ("swarm-agents", False),
    "murphy-crew-system":               ("swarm-agents", False),
    "swarm-proposal-generator":         ("swarm-agents", False),
    "agent-persona-library":            ("swarm-agents", False),
    "agent-monitor-dashboard":          ("swarm-agents", False),
    "agent-run-recorder":               ("swarm-agents", False),
    "agentic-api-provisioner":          ("swarm-agents", False),
    "agentic-onboarding-engine":        ("swarm-agents", False),
    "declarative-fleet-manager":        ("swarm-agents", False),

    # ── Business & Finance ───────────────────────────────────────────────────
    "niche-business-generator":         ("business-finance", False),
    "niche-viability-gate":             ("business-finance", False),
    "business-scaling-engine":          ("business-finance", False),
    "invoice-processing-pipeline":      ("business-finance", True),
    "financial-reporting-engine":       ("business-finance", True),
    "sales-automation":                 ("business-finance", False),
    "trading-bot-engine":               ("business-finance", True),
    "trading-strategy-engine":          ("business-finance", True),
    "trading-bot-lifecycle":            ("business-finance", True),
    "trading-hitl-gateway":             ("business-finance", True),
    "trading-shadow-learner":           ("business-finance", True),
    "crypto-exchange-connector":        ("business-finance", True),
    "crypto-portfolio-tracker":         ("business-finance", True),
    "crypto-risk-manager":              ("business-finance", True),
    "crypto-wallet-manager":            ("business-finance", True),
    "coinbase-connector":               ("business-finance", True),
    "budget-aware-processor":           ("business-finance", False),
    "cost-optimization-advisor":        ("business-finance", False),
    "cost-explosion-gate":              ("business-finance", False),
    "market-data-feed":                 ("business-finance", False),
    "rosetta-selling-bridge":           ("business-finance", False),

    # ── Communication & Notifications ───────────────────────────────────────
    "email-integration":                ("comms-notifications", False),
    "notification-system":              ("comms-notifications", False),
    "customer-communication-manager":   ("comms-notifications", False),
    "social-media-scheduler":           ("comms-notifications", False),
    "social-media-moderation":          ("comms-notifications", False),
    "announcer-voice-engine":           ("comms-notifications", False),
    "content-pipeline-engine":          ("comms-notifications", False),
    "content-creator-platform-modulator": ("comms-notifications", False),
    "campaign-orchestrator":            ("comms-notifications", False),
    "adaptive-campaign-engine":         ("comms-notifications", False),
    "self-marketing-orchestrator":      ("comms-notifications", False),
    "contact-compliance-governor":      ("comms-notifications", False),

    # ── Infrastructure & DevOps ──────────────────────────────────────────────
    "docker-containerization":          ("infrastructure", False),
    "kubernetes-deployment":            ("infrastructure", False),
    "hetzner-deploy":                   ("infrastructure", False),
    "cloudflare-deploy":                ("infrastructure", False),
    "ci-cd-pipeline-manager":           ("infrastructure", False),
    "multi-cloud-orchestrator":         ("infrastructure", False),
    "geographic-load-balancer":         ("infrastructure", False),
    "resource-scaling-controller":      ("infrastructure", False),
    "capacity-planning-engine":         ("infrastructure", False),
    "backup-disaster-recovery":         ("infrastructure", False),

    # ── Security ─────────────────────────────────────────────────────────────
    "security-plane-adapter":           ("security", True),
    "security-audit-scanner":           ("security", True),
    "security-hardening-config":        ("security", True),
    "fastapi-security":                 ("security", True),
    "flask-security":                   ("security", True),
    "oauth-oidc-provider":              ("security", True),
    "secure-key-manager":               ("security", True),
    "murphy-credential-gate":           ("security", True),
    "key-harvester":                    ("security", True),

    # ── Data & Knowledge ─────────────────────────────────────────────────────
    "knowledge-graph-builder":          ("data-knowledge", False),
    "knowledge-base-manager":           ("data-knowledge", False),
    "knowledge-gap-system":             ("data-knowledge", False),
    "rag-vector-integration":           ("data-knowledge", False),
    "generative-knowledge-builder":     ("data-knowledge", False),
    "concept-graph-engine":             ("data-knowledge", False),
    "concept-translation":              ("data-knowledge", False),
    "data-pipeline-orchestrator":       ("data-knowledge", False),
    "data-archive-manager":             ("data-knowledge", False),
    "cross-platform-data-sync":         ("data-knowledge", False),

    # ── Monitoring & Observability ───────────────────────────────────────────
    "health-monitor":                   ("monitoring", False),
    "heartbeat-liveness-protocol":      ("monitoring", False),
    "activated-heartbeat-runner":       ("monitoring", False),
    "prometheus-metrics-exporter":      ("monitoring", False),
    "observability-counters":           ("monitoring", False),
    "murphy-trace":                     ("monitoring", False),
    "bot-telemetry-normalizer":         ("monitoring", False),
    "telemetry-adapter":                ("monitoring", False),
    "telemetry-system":                 ("monitoring", False),
    "telemetry-learning":               ("monitoring", False),
    "operational-slo-tracker":          ("monitoring", False),
    "slo-remediation-bridge":           ("monitoring", False),
    "log-analysis-engine":              ("monitoring", False),
    "alert-rules-engine":               ("monitoring", False),
    "causal-spike-analyzer":            ("monitoring", False),

    # ── Self-Healing & Resilience ────────────────────────────────────────────
    "autonomous-repair-system":         ("self-healing", False),
    "self-fix-loop":                    ("self-healing", False),
    "self-healing-coordinator":         ("self-healing", False),
    "self-improvement-engine":          ("self-healing", False),
    "self-optimisation-engine":         ("self-healing", False),
    "murphy-code-healer":               ("self-healing", False),
    "code-repair-engine":               ("self-healing", False),
    "chaos-resilience-loop":            ("self-healing", False),
    "murphy-immune-engine":             ("self-healing", False),
    "immune-memory":                    ("self-healing", False),
    "predictive-failure-engine":        ("self-healing", False),
    "predictive-maintenance-engine":    ("self-healing", False),
    "blackstart-controller":            ("self-healing", False),
    "system-update-recommendation-engine": ("self-healing", False),

    # ── Domain & Expert Systems ──────────────────────────────────────────────
    "domain-engine":                    ("domain-expert", False),
    "domain-expert-system":             ("domain-expert", False),
    "domain-expert-integration":        ("domain-expert", False),
    "domain-gate-generator":            ("domain-expert", False),
    "dynamic-expert-generator":         ("domain-expert", False),
    "murphy-engineering-toolbox":       ("domain-expert", False),
    "simulation-engine":                ("domain-expert", False),
    "digital-twin-engine":              ("domain-expert", False),
    "computer-vision-pipeline":         ("domain-expert", False),
    "murphy-sensor-fusion":             ("domain-expert", False),
    "murphy-autonomous-perception":     ("domain-expert", False),

    # ── Org & Workflow ───────────────────────────────────────────────────────
    "org-compiler":                     ("org-workflow", False),
    "org-chart-enforcement":            ("org-workflow", False),
    "organization-chart-system":        ("org-workflow", False),
    "organizational-context-system":    ("org-workflow", False),
    "onboarding-flow":                  ("org-workflow", False),
    "onboarding-automation-engine":     ("org-workflow", False),
    "onboarding-team-pipeline":         ("org-workflow", False),

    # ── Module System ────────────────────────────────────────────────────────
    "module-compiler":                  ("module-system", False),
    "module-compiler-adapter":          ("module-system", False),
    "module-manager":                   ("module-system", False),
    "module-registry":                  ("module-system", False),
    "modular-runtime":                  ("module-system", False),
    "shim-compiler":                    ("module-system", False),
    "plugin-extension-sdk":             ("module-system", False),
    "capability-map":                   ("module-system", False),

    # ── Misc Systems ─────────────────────────────────────────────────────────
    "murphy-state-graph":               ("misc-systems", False),
    "murphy-template-hub":              ("misc-systems", False),
    "murphy-drawing-engine":            ("misc-systems", False),
    "murphy-repl":                      ("misc-systems", False),
    "murphy-shadow-trainer":            ("misc-systems", False),
    "murphy-osmosis-engine":            ("misc-systems", False),
    "murphy-wingman-evolution":         ("misc-systems", False),
    "murphy-action-engine":             ("misc-systems", False),
    "nocode-workflow-terminal":         ("misc-systems", False),
    "ai-workflow-generator":            ("misc-systems", False),
    "rpa-recorder-engine":              ("misc-systems", False),
    "playwright-task-definitions":      ("misc-systems", False),
    "image-generation-engine":          ("misc-systems", False),
    "digital-asset-generator":          ("misc-systems", False),
    "innovation-farmer":                ("misc-systems", False),
    "knostalgia-engine":                ("misc-systems", False),
    "knostalgia-category-engine":       ("misc-systems", False),
    "research-engine":                  ("misc-systems", False),
    "advanced-research":                ("misc-systems", False),
    "multi-source-research":            ("misc-systems", False),
    "competitive-intelligence-engine":  ("misc-systems", False),
    "self-introspection":               ("misc-systems", False),
    "self-codebase-swarm":              ("misc-systems", False),
    "cutsheet-engine":                  ("misc-systems", False),
    "visual-swarm-builder":             ("misc-systems", False),
    "ceo-branch":                       ("misc-systems", False),
    "production-assistant-engine":      ("misc-systems", False),
    "founder-updates":                  ("misc-systems", False),

    # ── Runtime & State ──────────────────────────────────────────────────────
    "runtime":                          ("runtime-state", False),
    "recursive-stability-controller":   ("runtime-state", False),
    "supervision-tree":                 ("runtime-state", False),
    "supervisor-system":                ("runtime-state", False),
    "persistence-manager":              ("runtime-state", False),
    "persistence-wal":                  ("runtime-state", False),
    "persistence-replay-completeness":  ("runtime-state", False),
    "state-machine":                    ("runtime-state", False),
    "state-schema":                     ("runtime-state", False),
    "environment-state-manager":        ("runtime-state", False),
    "session-context":                  ("runtime-state", False),
    "closure-engine":                   ("runtime-state", False),
    "event-backbone":                   ("runtime-state", False),

    # ── Integration & Adapters ───────────────────────────────────────────────
    "integration-bus":                  ("integrations-adapters", False),
    "integrations":                     ("integrations-adapters", False),
    "system-integrator":                ("integrations-adapters", False),
    "enterprise-integrations":          ("integrations-adapters", False),
    "platform-connector-framework":     ("integrations-adapters", False),
    "delivery-adapters":                ("integrations-adapters", False),
    "delivery-channel-completeness":    ("integrations-adapters", False),
    "ticketing-adapter":                ("integrations-adapters", False),
    "mfgc-core":                        ("integrations-adapters", False),
    "mfgc-adapter":                     ("integrations-adapters", False),
    "mfgc-metrics":                     ("integrations-adapters", False),
    "remote-access-connector":          ("integrations-adapters", False),

    # ── IoT & Industrial ─────────────────────────────────────────────────────
    "building-automation-connectors":   ("iot-industrial", False),
    "energy-management-connectors":     ("iot-industrial", False),
    "additive-manufacturing-connectors": ("iot-industrial", False),
    "manufacturing-automation-standards": ("iot-industrial", False),
    "sensor-reader":                    ("iot-industrial", False),
    "robotics":                         ("iot-industrial", False),

    # ── CRM & Account ────────────────────────────────────────────────────────
    "crm":                              ("crm-account", False),
    "account-management":               ("crm-account", False),
    "credential-profile-system":        ("crm-account", True),

    # ── Board & Portfolio ────────────────────────────────────────────────────
    "board-system":                     ("board-portfolio", False),
    "portfolio":                        ("board-portfolio", False),
    "time-tracking":                    ("board-portfolio", False),

    # ── Communication Subsystems ─────────────────────────────────────────────
    "comms":                            ("comms-subsystems", False),
    "communication-system":             ("comms-subsystems", False),
    "collaboration":                    ("comms-subsystems", False),
    "guest-collab":                     ("comms-subsystems", False),

    # ── Additional ───────────────────────────────────────────────────────────
    "bridge-layer":                     ("additional", False),
    "protocols":                        ("additional", False),
    "dashboards":                       ("additional", False),
    "dev-module":                       ("additional", False),
    "eq":                               ("additional", False),
    "aionmind":                         ("additional", False),
    "auar":                             ("additional", False),
    "avatar":                           ("additional", False),
    "neuro-symbolic-models":            ("additional", False),
    "rosetta":                          ("additional", False),
    "self-selling-engine":              ("additional", False),
    "schema-registry":                  ("additional", False),
    "deterministic-compute-plane":      ("additional", False),
    "control-theory":                   ("additional", False),
    "synthetic-failure-generator":      ("additional", False),
    "autonomous-systems":               ("additional", False),
    "murphy-foundation-model":          ("additional", False),
    "execution-packet-compiler":        ("additional", False),
    "execution":                        ("additional", False),

    # ── Well-known system rooms ───────────────────────────────────────────────
    "system-status":                    ("system", False),
    "security-alerts":                  ("system", True),
    "hitl-approvals":                   ("system", False),
    "ci-cd":                            ("system", False),
    "finance":                          ("system", True),
    "monitoring":                       ("system", False),
    "admin":                            ("system", True),

    # ── Additional rooms for previously unregistered packages ────────────
    "document-export":                  ("additional", False),
    "game-creation-pipeline":           ("misc-systems", False),
    "management-systems":               ("misc-systems", False),
    "matrix-bridge":                    ("misc-systems", False),
    "multiverse-game-framework":        ("misc-systems", False),
    "org-build-plan":                   ("org-workflow", False),
    "platform-onboarding":              ("org-workflow", False),
    "service-module":                   ("misc-systems", False),
    "strategy-templates":               ("misc-systems", False),
    "workdocs":                         ("additional", False),
}


@dataclass
class RoomInfo:
    """Metadata about a registered Murphy Matrix room."""

    subsystem: str
    alias: str                            # local alias without server domain
    full_alias: str                       # ``#murphy-{subsystem}:{domain}``
    category: str
    encrypted: bool
    room_id: Optional[str] = field(default=None)


class RoomRegistry:
    """Maps every Murphy subsystem to a dedicated Matrix room.

    Parameters
    ----------
    client:
        :class:`~murphy.matrix_bridge.MatrixClient` instance used for room
        creation.
    homeserver_domain:
        Domain part used when building room aliases, e.g. ``example.com``.
        Defaults to ``MATRIX_HOMESERVER_DOMAIN`` env var or ``localhost``.
    auto_create:
        Whether to auto-create rooms on :meth:`ensure_all_rooms`.  Defaults
        to the ``MATRIX_AUTO_CREATE_ROOMS`` env var (``true``).
    admin_users:
        List of Matrix user IDs to invite on room creation.  Defaults to
        ``MATRIX_ADMIN_USERS`` env var (comma-separated).
    """

    def __init__(
        self,
        client: MatrixClient,
        homeserver_domain: Optional[str] = None,
        auto_create: Optional[bool] = None,
        admin_users: Optional[List[str]] = None,
    ) -> None:
        self._client = client
        self.domain: str = (
            homeserver_domain
            or os.environ.get("MATRIX_HOMESERVER_DOMAIN", "localhost")
        )
        self.auto_create: bool = (
            auto_create
            if auto_create is not None
            else os.environ.get("MATRIX_AUTO_CREATE_ROOMS", "true").lower()
            not in ("0", "false", "no")
        )
        raw_admins = os.environ.get("MATRIX_ADMIN_USERS", "")
        self.admin_users: List[str] = admin_users or [
            u.strip() for u in raw_admins.split(",") if u.strip()
        ]
        self._rooms: Dict[str, RoomInfo] = self._build_registry()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_registry(self) -> Dict[str, RoomInfo]:
        rooms: Dict[str, RoomInfo] = {}
        for subsystem, (category, encrypted) in SUBSYSTEM_ROOMS.items():
            alias = f"murphy-{subsystem}"
            full_alias = f"#{alias}:{self.domain}"
            rooms[subsystem] = RoomInfo(
                subsystem=subsystem,
                alias=alias,
                full_alias=full_alias,
                category=category,
                encrypted=encrypted,
            )
        return rooms

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_room(self, subsystem: str) -> Optional[RoomInfo]:
        """Return :class:`RoomInfo` for *subsystem*, or ``None``."""
        return self._rooms.get(subsystem)

    def get_room_id(self, subsystem: str) -> Optional[str]:
        """Return the Matrix room ID for *subsystem*, or ``None``."""
        info = self._rooms.get(subsystem)
        return info.room_id if info else None

    def all_subsystems(self) -> List[str]:
        """Return all registered subsystem names."""
        return list(self._rooms.keys())

    def subsystems_by_category(self, category: str) -> List[str]:
        """Return subsystem names belonging to *category*."""
        return [s for s, info in self._rooms.items() if info.category == category]

    def categories(self) -> List[str]:
        """Return all unique category names in insertion order."""
        seen: Dict[str, None] = {}
        for info in self._rooms.values():
            seen[info.category] = None
        return list(seen)

    # ------------------------------------------------------------------
    # Room creation
    # ------------------------------------------------------------------

    async def ensure_all_rooms(self) -> Dict[str, Optional[str]]:
        """Ensure every registered room exists on the homeserver.

        Returns a mapping of ``subsystem → room_id`` (``None`` if creation
        failed or was skipped).
        """
        if not self.auto_create:
            logger.info("MATRIX_AUTO_CREATE_ROOMS is disabled — skipping room creation")
            return {s: info.room_id for s, info in self._rooms.items()}

        results: Dict[str, Optional[str]] = {}
        for subsystem, info in self._rooms.items():
            room_id = await self._client.create_room(
                alias=info.alias,
                name=f"Murphy • {subsystem.replace('-', ' ').title()}",
                topic=f"Murphy System — {subsystem} subsystem",
                is_public=False,
                invite=self.admin_users,
                encrypted=info.encrypted,
            )
            info.room_id = room_id
            results[subsystem] = room_id
            if room_id:
                logger.debug("Room ready: %s → %s", info.full_alias, room_id)
        logger.info("ensure_all_rooms complete: %d/%d rooms ready",
                    sum(1 for v in results.values() if v), len(results))
        return results

    async def ensure_room(self, subsystem: str) -> Optional[str]:
        """Ensure a single room exists and return its room ID."""
        info = self._rooms.get(subsystem)
        if info is None:
            logger.warning("Unknown subsystem: %s", subsystem)
            return None
        if info.room_id:
            return info.room_id
        room_id = await self._client.create_room(
            alias=info.alias,
            name=f"Murphy • {subsystem.replace('-', ' ').title()}",
            topic=f"Murphy System — {subsystem} subsystem",
            is_public=False,
            invite=self.admin_users,
            encrypted=info.encrypted,
        )
        info.room_id = room_id
        return room_id

    def set_room_id(self, subsystem: str, room_id: str) -> None:
        """Manually set the room ID for an already-existing room."""
        if subsystem in self._rooms:
            self._rooms[subsystem].room_id = room_id

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Dict[str, object]]:
        """Return a dict summary of all registered rooms."""
        return {
            s: {
                "alias": info.full_alias,
                "category": info.category,
                "encrypted": info.encrypted,
                "room_id": info.room_id,
            }
            for s, info in self._rooms.items()
        }


__all__ = ["RoomRegistry", "RoomInfo", "SUBSYSTEM_ROOMS", "ROOM_COGNITIVE_ROLES"]

# Re-export ROOM_COGNITIVE_ROLES so callers can do:
#   from src.matrix_bridge.room_registry import ROOM_COGNITIVE_ROLES
try:
    from .room_cognitive_roles import ROOM_COGNITIVE_ROLES
except ImportError:
    ROOM_COGNITIVE_ROLES = {}  # type: ignore[assignment]
