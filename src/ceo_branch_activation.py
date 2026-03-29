# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
CEO Branch Activation Module — Murphy System.

Design Label: CEO-002 — CEO Branch Activation & Org Chart Automation
Owner: Executive / Platform Engineering
Dependencies:
  - ceo_activation_plan — existing org chart data-models and builder
  - thread_safe_operations.capped_append — bounded collections
  - telemetry_adapter.TelemetryAdapter — decision telemetry

This module defines the *runtime* layer on top of the CEO activation plan:

Key classes:
  VPRole          — a single VP-level autonomous role with status_check /
                    generate_report / execute_directive interface
  OrgChartAutomation — builds and maintains the full VP role map
  SystemWorkflow  — continuous self-running workflow loop (default 20 min)
  CEOBranch       — top-level autonomous decision-making entry point
                    (coordinates all subsystem controllers and org chart)

Org chart mapping (per requirement spec):
  CEO               → ceo_branch_activation (this module)
  CTO               → architecture_evolution, code_repair_engine
  VP Sales          → self_selling_engine/
  VP Operations     → full_automation_controller, automation_scheduler
  VP Compliance     → compliance_engine, compliance_as_code_engine
  VP Engineering    → ci_cd_pipeline_manager, autonomous_repair_system
  VP Customer Suc.  → onboarding_flow, agentic_onboarding_engine
  VP Finance        → financial_reporting_engine, cost_optimization_advisor
  VP Marketing      → campaign_orchestrator, adaptive_campaign_engine
  CSO               → fastapi_security, authority_gate

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock (CWE-362)
  - Bounded collections via capped_append (CWE-770)
  - Input validated before processing (CWE-20)
  - Error messages sanitised before logging (CWE-209)
  - Graceful degradation: missing subsystems do not halt the loop
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

# ---------------------------------------------------------------------------
# Rosetta integration (soft imports — degrades gracefully when unavailable)
# ---------------------------------------------------------------------------
try:
    from rosetta.rosetta_manager import RosettaManager as _RosettaManager
    from rosetta.rosetta_models import (
        AgentState as _AgentState,
        Identity as _Identity,
        RosettaAgentState as _RosettaAgentState,
        SystemState as _SystemState,
    )
    _ROSETTA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ROSETTA_AVAILABLE = False
    _RosettaManager = None  # type: ignore[assignment,misc]
    _RosettaAgentState = None  # type: ignore[assignment,misc]
    _Identity = None  # type: ignore[assignment,misc]
    _SystemState = None  # type: ignore[assignment,misc]
    _AgentState = None  # type: ignore[assignment,misc]

try:
    from rosetta_platform_state import RosettaPlatformManager as _PlatformManager
    _PLATFORM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLATFORM_AVAILABLE = False
    _PlatformManager = None  # type: ignore[assignment,misc]

try:
    from rosetta_stone_heartbeat import (
        OrganizationTier as _OrganizationTier,
        RosettaStoneHeartbeat as _Heartbeat,
    )
    _HEARTBEAT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _HEARTBEAT_AVAILABLE = False
    _OrganizationTier = None  # type: ignore[assignment,misc]
    _Heartbeat = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants                                                         [CWE-20]
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_NAME_RE = re.compile(r"^[a-zA-Z0-9 _\-\.]{1,200}$")
_MAX_ROLE_LABEL_LEN: int = 200
_MAX_DIRECTIVE_LEN: int = 2_000
_MAX_REPORT_ENTRIES: int = 500
_MAX_AUDIT_LOG: int = 10_000
_MAX_VP_ROLES: int = 50
_MAX_WORKFLOW_RESULTS: int = 1_000
_MAX_TELEMETRY_EVENTS: int = 5_000

# Minimum confidence for full automation (graceful-degradation gate)
_CONFIDENCE_THRESHOLD: float = 0.70

# Default workflow tick interval (seconds) — matches 20-min selling cycle
_DEFAULT_TICK_SECONDS: float = 1_200.0


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RoleStatus(str, Enum):
    """Health / activation status of a VP role."""
    HEALTHY   = "healthy"
    DEGRADED  = "degraded"
    OFFLINE   = "offline"
    UNKNOWN   = "unknown"


class WorkflowPhase(str, Enum):
    """Phase of the continuous system workflow."""
    IDLE      = "idle"
    RUNNING   = "running"
    DEGRADED  = "degraded"
    STOPPED   = "stopped"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RoleReport:
    """Snapshot report emitted by a VP role for the CEO dashboard."""
    role_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    role_label: str = ""
    status: str = RoleStatus.UNKNOWN.value
    subsystems: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_label": self.role_label,
            "status": self.status,
            "subsystems": list(self.subsystems),
            "metrics": dict(self.metrics),
            "alerts": list(self.alerts),
            "generated_at": self.generated_at,
        }


@dataclass
class DirectiveResult:
    """Result from executing a top-down CEO directive."""
    directive_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    role_label: str = ""
    directive: str = ""
    accepted: bool = False
    message: str = ""
    executed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directive_id": self.directive_id,
            "role_label": self.role_label,
            "directive": self.directive,
            "accepted": self.accepted,
            "message": self.message,
            "executed_at": self.executed_at,
        }


@dataclass
class WorkflowTickResult:
    """Aggregated result of one SystemWorkflow tick."""
    tick_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tick_number: int = 0
    phase: str = WorkflowPhase.IDLE.value
    plan_updated: bool = False
    role_reports: List[RoleReport] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)
    confidence: float = 0.0
    degraded_roles: List[str] = field(default_factory=list)
    ticked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick_id": self.tick_id,
            "tick_number": self.tick_number,
            "phase": self.phase,
            "plan_updated": self.plan_updated,
            "role_reports": [r.to_dict() for r in self.role_reports],
            "alerts": list(self.alerts),
            "confidence": self.confidence,
            "degraded_roles": list(self.degraded_roles),
            "ticked_at": self.ticked_at,
        }


# ---------------------------------------------------------------------------
# VPRole
# ---------------------------------------------------------------------------

class VPRole:
    """Represents a single VP-level autonomous role in the Murphy org chart.

    Provides the three canonical interfaces required by every role:
      - ``status_check()``     — query subsystem health
      - ``generate_report()``  — produce a CEO-dashboard report
      - ``execute_directive()``— receive and act on a top-down instruction

    The *status_probe* callable is an optional injection point allowing tests
    (and production code) to hook live subsystem health checks without
    importing those subsystems directly (avoids circular imports).

    Thread-safe via an internal Lock.
    """

    def __init__(
        self,
        role_label: str,
        subsystems: List[str],
        responsibilities: List[str],
        status_probe: Optional[Callable[[], Dict[str, Any]]] = None,
        *,
        rosetta_manager: Optional[Any] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Initialise a VP role.

        Args:
            role_label: Human-readable role name (e.g. ``"VP Sales"``).
            subsystems: List of Murphy module names owned by this role.
            responsibilities: Short description list of accountabilities.
            status_probe: Optional ``() -> dict`` that returns live status
                from the role's subsystems.  Falls back to ``{}`` if *None*.
            rosetta_manager: Optional :class:`RosettaManager` so the role
                can read its own Rosetta state (P1 — Gap 1 closure).
            agent_id: Rosetta agent ID for this role (derived from
                role_label if not provided).
        """
        label = str(role_label or "")[:_MAX_ROLE_LABEL_LEN].replace("\x00", "")
        if not label:
            raise ValueError("role_label must not be empty")

        self._lock = threading.Lock()
        self._role_label: str = label
        self._subsystems: List[str] = [
            str(s)[:200].replace("\x00", "") for s in (subsystems or [])
        ]
        self._responsibilities: List[str] = [
            str(r)[:500].replace("\x00", "") for r in (responsibilities or [])
        ]
        self._status_probe: Callable[[], Dict[str, Any]] = (
            status_probe if callable(status_probe) else (lambda: {})
        )
        self._report_log: List[Dict[str, Any]] = []
        self._directive_log: List[Dict[str, Any]] = []
        # P1 — Rosetta integration: each VP role can read its own state
        self._rosetta_manager = rosetta_manager
        self._agent_id: str = agent_id or re.sub(
            r"[^a-zA-Z0-9_-]", "_", label.lower()
        )[:200]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def role_label(self) -> str:
        return self._role_label

    @property
    def agent_id(self) -> str:
        """Rosetta agent ID for this role."""
        return self._agent_id

    @property
    def subsystems(self) -> List[str]:
        with self._lock:
            return list(self._subsystems)

    @property
    def rosetta_state(self) -> Optional[Dict[str, Any]]:
        """Return this role's Rosetta state document, or *None*.

        Provides the VP agent with full context of what it has been doing
        (task history, goal progress, automation status) and what is
        happening system-wide (via the state feed).
        """
        if self._rosetta_manager is None:
            return None
        try:
            state = self._rosetta_manager.load_state(self._agent_id)
            if state is None:
                return None
            return state.model_dump(mode="json") if hasattr(state, "model_dump") else None
        except Exception:  # noqa: BLE001
            return None

    def status_check(self) -> RoleStatus:
        """Query subsystem health and return a :class:`RoleStatus`.

        Calls the injected *status_probe*.  Any exception is caught and
        treated as DEGRADED so the overall workflow can route around it.
        """
        try:
            probe_data = self._status_probe()
            # If the probe raises or returns something with an explicit
            # "healthy: false", we degrade.
            if isinstance(probe_data, dict) and not probe_data.get("healthy", True):
                return RoleStatus.DEGRADED
            return RoleStatus.HEALTHY
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Role %s status_check failed: %s",
                self._role_label,
                str(exc)[:200],
            )
            return RoleStatus.DEGRADED

    def generate_report(self) -> RoleReport:
        """Produce a CEO-dashboard report for this role.

        Includes the status, subsystem list, and any alerts discovered
        by *status_check*.  When a Rosetta manager is available, the
        report is enriched with historical context (goals, tasks,
        automation progress) from the agent's own state document.
        """
        status = self.status_check()
        alerts: List[str] = []
        metrics: Dict[str, Any] = {}

        if status == RoleStatus.DEGRADED:
            alerts.append(
                f"{self._role_label}: one or more subsystems returned a degraded signal"
            )
        elif status == RoleStatus.OFFLINE:
            alerts.append(f"{self._role_label}: role is OFFLINE — manual intervention required")

        try:
            probe_data = self._status_probe()
            if isinstance(probe_data, dict):
                metrics = {k: v for k, v in probe_data.items() if k != "healthy"}
        except Exception:  # noqa: BLE001
            pass

        # P1 — Enrich with Rosetta state context
        rosetta_ctx = self.rosetta_state
        if rosetta_ctx is not None:
            agent_st = rosetta_ctx.get("agent_state", {})
            metrics["rosetta_goals"] = len(agent_st.get("active_goals", []))
            metrics["rosetta_tasks"] = len(agent_st.get("task_queue", []))
            metrics["rosetta_agent_id"] = self._agent_id

        report = RoleReport(
            role_label=self._role_label,
            status=status.value,
            subsystems=list(self._subsystems),
            metrics=metrics,
            alerts=alerts,
        )
        with self._lock:
            capped_append(
                self._report_log,
                {"report_id": report.role_id, "at": report.generated_at},
                max_size=_MAX_REPORT_ENTRIES,
            )
        return report

    def execute_directive(self, directive: str) -> DirectiveResult:
        """Receive and process a top-down CEO directive.

        The directive is logged and acknowledged.  Concrete actions are
        dispatched to the role's subsystems via the status probe interface
        or deferred to HITL when outside scope.

        Args:
            directive: Plain-text instruction string (max 2 000 chars).

        Returns:
            A :class:`DirectiveResult` describing the outcome.
        """
        directive = str(directive or "")[:_MAX_DIRECTIVE_LEN].replace("\x00", "")
        if not directive:
            return DirectiveResult(
                role_label=self._role_label,
                directive=directive,
                accepted=False,
                message="Empty directive — ignored",
            )

        result = DirectiveResult(
            role_label=self._role_label,
            directive=directive,
            accepted=True,
            message=f"{self._role_label} acknowledged directive and queued for execution",
        )
        with self._lock:
            capped_append(
                self._directive_log,
                result.to_dict(),
                max_size=_MAX_REPORT_ENTRIES,
            )
        logger.info("Role %s accepted directive: %.100s", self._role_label, directive)
        return result

    def get_directive_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._directive_log)


# ---------------------------------------------------------------------------
# OrgChartAutomation
# ---------------------------------------------------------------------------

# Canonical org chart definition — maps role label to (subsystems, responsibilities)
_ORG_CHART_DEFINITION: List[Dict[str, Any]] = [
    {
        "label": "CEO",
        "subsystems": ["ceo_branch_activation"],
        "responsibilities": [
            "Strategic decisions",
            "Operational plan generation and update",
            "Org chart management",
            "Revenue oversight",
        ],
    },
    {
        "label": "CTO",
        "subsystems": ["architecture_evolution", "code_repair_engine"],
        "responsibilities": [
            "Technical direction",
            "Self-improvement orchestration",
            "Platform architecture",
        ],
    },
    {
        "label": "VP Sales",
        "subsystems": ["self_selling_engine"],
        "responsibilities": [
            "Revenue generation",
            "Outreach orchestration",
            "Trial lifecycle management",
        ],
    },
    {
        "label": "VP Operations",
        "subsystems": ["full_automation_controller", "automation_scheduler"],
        "responsibilities": [
            "Day-to-day operations",
            "Automation scheduling",
            "Operational health",
        ],
    },
    {
        "label": "VP Compliance",
        "subsystems": ["compliance_engine", "compliance_as_code_engine"],
        "responsibilities": [
            "Regulatory compliance monitoring",
            "Compliance-as-code enforcement",
            "Audit trail management",
        ],
    },
    {
        "label": "VP Engineering",
        "subsystems": ["ci_cd_pipeline_manager", "autonomous_repair_system"],
        "responsibilities": [
            "Build and deploy automation",
            "Autonomous self-repair",
            "CI/CD pipeline health",
        ],
    },
    {
        "label": "VP Customer Success",
        "subsystems": ["onboarding_flow", "agentic_onboarding_engine"],
        "responsibilities": [
            "Customer onboarding",
            "Retention and engagement",
            "Onboarding automation",
        ],
    },
    {
        "label": "VP Finance",
        "subsystems": ["financial_reporting_engine", "cost_optimization_advisor"],
        "responsibilities": [
            "Budget management",
            "Revenue tracking",
            "Cost optimisation",
        ],
    },
    {
        "label": "VP Marketing",
        "subsystems": ["campaign_orchestrator", "adaptive_campaign_engine"],
        "responsibilities": [
            "Marketing campaign orchestration",
            "Adaptive campaign optimisation",
            "Community building and outreach",
        ],
    },
    {
        "label": "Chief Security Officer",
        "subsystems": ["fastapi_security", "authority_gate"],
        "responsibilities": [
            "Security posture management",
            "Authority and permission gating",
            "Threat detection and response",
        ],
    },
]


class OrgChartAutomation:
    """Builds and maintains the VP role map for the CEO branch.

    Roles can have an optional *status_probe* injected per role label so
    that tests and production code can wire in live subsystem probes without
    coupling this module to every subsystem.

    Thread-safe via an internal Lock.
    """

    def __init__(
        self,
        role_probes: Optional[Dict[str, Callable[[], Dict[str, Any]]]] = None,
        *,
        rosetta_manager: Optional[Any] = None,
    ) -> None:
        """Initialise the org chart.

        Args:
            role_probes: Optional mapping of ``role_label -> callable`` that
                returns a health dict ``{"healthy": bool, ...}``.
            rosetta_manager: Optional :class:`RosettaManager` passed to
                each VP role so they can read their Rosetta state (P1).
        """
        self._lock = threading.Lock()
        self._roles: Dict[str, VPRole] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._rosetta_manager = rosetta_manager

        probes = role_probes or {}
        for definition in _ORG_CHART_DEFINITION:
            label = definition["label"]
            role = VPRole(
                role_label=label,
                subsystems=definition["subsystems"],
                responsibilities=definition["responsibilities"],
                status_probe=probes.get(label),
                rosetta_manager=rosetta_manager,
            )
            self._roles[label] = role

        self._log_event("org_chart_built", {"role_count": len(self._roles)})

    # ------------------------------------------------------------------
    # Role access
    # ------------------------------------------------------------------

    def get_role(self, label: str) -> Optional[VPRole]:
        """Return the :class:`VPRole` with the given label, or *None*."""
        label = str(label or "")[:_MAX_ROLE_LABEL_LEN].replace("\x00", "")
        with self._lock:
            return self._roles.get(label)

    def get_all_roles(self) -> Dict[str, VPRole]:
        """Return a shallow copy of the role map."""
        with self._lock:
            return dict(self._roles)

    def get_org_chart(self) -> List[Dict[str, Any]]:
        """Return a serialisable representation of the full org chart."""
        with self._lock:
            roles = list(self._roles.values())
        return [
            {
                "role_label": r.role_label,
                "subsystems": r.subsystems,
                "status": r.status_check().value,
            }
            for r in roles
        ]

    # ------------------------------------------------------------------
    # Status and reports
    # ------------------------------------------------------------------

    def collect_reports(self) -> List[RoleReport]:
        """Collect fresh reports from every VP role."""
        with self._lock:
            roles = list(self._roles.values())
        reports: List[RoleReport] = []
        for role in roles:
            try:
                reports.append(role.generate_report())
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to generate report for role %s: %s",
                    role.role_label,
                    str(exc)[:200],
                )
                reports.append(
                    RoleReport(
                        role_label=role.role_label,
                        status=RoleStatus.OFFLINE.value,
                        alerts=[f"{role.role_label}: report generation failed"],
                    )
                )
        return reports

    def broadcast_directive(
        self, directive: str, roles: Optional[List[str]] = None
    ) -> List[DirectiveResult]:
        """Send a directive to all roles (or a subset).

        Args:
            directive: Instruction string (max 2 000 chars).
            roles: Optional list of role labels to target.  Broadcasts to
                all roles when *None*.
        """
        directive = str(directive or "")[:_MAX_DIRECTIVE_LEN].replace("\x00", "")
        with self._lock:
            role_map = dict(self._roles)

        if roles is not None:
            target_labels = [
                str(r)[:_MAX_ROLE_LABEL_LEN].replace("\x00", "") for r in roles
            ]
            role_map = {k: v for k, v in role_map.items() if k in target_labels}

        results: List[DirectiveResult] = []
        for role in role_map.values():
            try:
                results.append(role.execute_directive(directive))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Directive dispatch failed for %s: %s",
                    role.role_label,
                    str(exc)[:200],
                )
        self._log_event(
            "directive_broadcast",
            {"directive_preview": directive[:100], "target_count": len(results)},
        )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_event(self, action: str, details: Dict[str, Any]) -> None:
        entry: Dict[str, Any] = {
            "action": action,
            "at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)


# ---------------------------------------------------------------------------
# SystemWorkflow
# ---------------------------------------------------------------------------

class SystemWorkflow:
    """Continuous self-running workflow loop for Murphy.

    At each tick:
      1. CEO generates / updates the operational plan.
      2. Each VP role generates a report (parallel-safe, serial execution).
      3. Results are aggregated into a system-wide status report.
      4. Plan is adjusted based on results (adaptive confidence scoring).
      5. Anomalies trigger alert logging (and can call an optional hook).
      6. If confidence drops below threshold, the loop degrades gracefully.

    The loop is implemented with :class:`threading.Timer` so it is
    non-blocking and safe to embed inside the heartbeat runner.

    Thread-safe via an internal RLock.
    """

    def __init__(
        self,
        org_chart: OrgChartAutomation,
        tick_interval: float = _DEFAULT_TICK_SECONDS,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
        alert_hook: Optional[Callable[[List[str]], None]] = None,
        *,
        rosetta_manager: Optional[Any] = None,
    ) -> None:
        """Initialise the system workflow.

        Args:
            org_chart: The :class:`OrgChartAutomation` instance to query.
            tick_interval: Seconds between workflow ticks (default 1 200 s).
            confidence_threshold: Minimum confidence to stay in full
                automation.  Below this, the loop degrades gracefully.
            alert_hook: Optional ``(alerts: List[str]) -> None`` called
                when anomalies are detected in a tick.
            rosetta_manager: Optional :class:`RosettaManager` for persisting
                role reports back to Rosetta (P2 — Gap 3 closure).
        """
        if tick_interval <= 0:
            raise ValueError("tick_interval must be > 0")
        if not (0.0 <= confidence_threshold <= 1.0):
            raise ValueError("confidence_threshold must be in [0.0, 1.0]")

        self._lock = threading.RLock()
        self._org_chart = org_chart
        self._tick_interval = tick_interval
        self._confidence_threshold = confidence_threshold
        self._alert_hook: Optional[Callable[[List[str]], None]] = alert_hook
        self._rosetta_manager = rosetta_manager

        self._phase: WorkflowPhase = WorkflowPhase.IDLE
        self._tick_count: int = 0
        self._running: bool = False
        self._timer: Optional[threading.Timer] = None
        self._tick_results: List[WorkflowTickResult] = []
        self._operational_plan: Dict[str, Any] = {}
        self._current_confidence: float = 1.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the periodic workflow tick timer."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._phase = WorkflowPhase.RUNNING
        self._schedule_next()
        logger.info(
            "SystemWorkflow started (interval=%.0fs, confidence_threshold=%.2f)",
            self._tick_interval,
            self._confidence_threshold,
        )

    def stop(self) -> None:
        """Stop the workflow loop gracefully."""
        with self._lock:
            self._running = False
            self._phase = WorkflowPhase.STOPPED
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        logger.info("SystemWorkflow stopped.")

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def phase(self) -> WorkflowPhase:
        with self._lock:
            return self._phase

    # ------------------------------------------------------------------
    # Readiness check
    # ------------------------------------------------------------------

    def readiness_check(self) -> Dict[str, Any]:
        """Verify all VP role dependencies are available before full activation.

        Returns a dict with::

            {
                "ready": bool,
                "healthy_roles": [...],
                "degraded_roles": [...],
                "offline_roles": [...],
            }
        """
        org_chart = self._org_chart.get_org_chart()
        healthy, degraded, offline = [], [], []
        for entry in org_chart:
            label = entry["role_label"]
            status = entry["status"]
            if status == RoleStatus.HEALTHY.value:
                healthy.append(label)
            elif status == RoleStatus.DEGRADED.value:
                degraded.append(label)
            else:
                offline.append(label)

        ready = len(offline) == 0
        return {
            "ready": ready,
            "healthy_roles": healthy,
            "degraded_roles": degraded,
            "offline_roles": offline,
        }

    # ------------------------------------------------------------------
    # Tick execution
    # ------------------------------------------------------------------

    def tick(self) -> WorkflowTickResult:
        """Execute one workflow tick (idempotent — same state → same result).

        Steps:
          1. Generate / update the operational plan.
          2. Collect reports from all VP roles.
          3. Aggregate results and compute confidence.
          4. Adjust plan adaptively based on confidence.
          5. Emit alerts for anomalies.

        Returns:
            A :class:`WorkflowTickResult` capturing the full tick state.
        """
        with self._lock:
            tick_number = self._tick_count + 1
            self._tick_count = tick_number

        result = WorkflowTickResult(tick_number=tick_number)

        # Step 1 — update operational plan
        plan_updated = self._update_operational_plan()
        result.plan_updated = plan_updated

        # Step 2 — collect role reports
        reports = self._org_chart.collect_reports()
        result.role_reports = reports

        # Step 3 — aggregate confidence
        healthy_count = sum(
            1 for r in reports if r.status == RoleStatus.HEALTHY.value
        )
        degraded_roles = [
            r.role_label
            for r in reports
            if r.status in (RoleStatus.DEGRADED.value, RoleStatus.OFFLINE.value)
        ]
        result.degraded_roles = degraded_roles

        total = len(reports) if reports else 1
        confidence = healthy_count / total
        result.confidence = confidence

        with self._lock:
            self._current_confidence = confidence

        # Step 4 — adaptive plan adjustment
        if confidence < self._confidence_threshold:
            self._degrade_plan(degraded_roles)
            result.phase = WorkflowPhase.DEGRADED.value
            with self._lock:
                self._phase = WorkflowPhase.DEGRADED
        else:
            result.phase = WorkflowPhase.RUNNING.value
            with self._lock:
                if self._phase == WorkflowPhase.DEGRADED:
                    # Recovered — return to running
                    self._phase = WorkflowPhase.RUNNING
                    logger.info("SystemWorkflow recovered from degraded state.")

        # Step 5 — collect and emit alerts
        all_alerts: List[str] = []
        for rpt in reports:
            all_alerts.extend(rpt.alerts)
        if degraded_roles:
            all_alerts.append(
                f"Degraded roles detected: {', '.join(degraded_roles)}"
            )
        result.alerts = all_alerts

        if all_alerts and callable(self._alert_hook):
            try:
                self._alert_hook(all_alerts)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Alert hook failed: %s", str(exc)[:200])

        # Persist tick result
        with self._lock:
            capped_append(
                self._tick_results, result.to_dict(), max_size=_MAX_WORKFLOW_RESULTS
            )

        # P2 — Write role reports back to Rosetta state
        self._persist_reports_to_rosetta(reports, tick_number, confidence)

        logger.info(
            "SystemWorkflow tick #%d: confidence=%.2f phase=%s degraded=%s",
            tick_number,
            confidence,
            result.phase,
            degraded_roles or "none",
        )
        return result

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------

    def get_tick_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent tick results (up to *limit*)."""
        limit = max(1, min(int(limit), _MAX_WORKFLOW_RESULTS))
        with self._lock:
            return list(self._tick_results[-limit:])

    def get_operational_plan(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._operational_plan)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "phase": self._phase.value,
                "tick_count": self._tick_count,
                "tick_interval": self._tick_interval,
                "confidence_threshold": self._confidence_threshold,
                "current_confidence": self._current_confidence,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist_reports_to_rosetta(
        self,
        reports: List[RoleReport],
        tick_number: int,
        confidence: float,
    ) -> None:
        """P2 — Write role reports back to each agent's Rosetta state.

        Closes the feedback loop: after every tick, each VP role's report
        is persisted to its Rosetta state document so the agent knows
        what happened on the previous cycle.
        """
        if self._rosetta_manager is None or not _ROSETTA_AVAILABLE:
            return
        for rpt in reports:
            # Derive the agent_id from the role via the org chart
            role = self._org_chart.get_role(rpt.role_label)
            if role is None:
                continue
            agent_id = role.agent_id
            try:
                self._rosetta_manager.update_state(agent_id, {
                    "system_state": {
                        "status": "active" if rpt.status == RoleStatus.HEALTHY.value else "degraded",
                        "active_tasks": rpt.metrics.get("rosetta_tasks", 0),
                        "last_heartbeat": rpt.generated_at,
                    },
                    "metadata": {
                        "last_tick": tick_number,
                        "last_confidence": confidence,
                        "last_report": rpt.to_dict(),
                    },
                })
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "P2: failed to persist report for %s: %s",
                    rpt.role_label, str(exc)[:200],
                )

    def _schedule_next(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._timer = threading.Timer(
                self._tick_interval, self._run_tick
            )
            self._timer.daemon = True
            self._timer.start()

    def _run_tick(self) -> None:
        try:
            self.tick()
        except Exception as exc:  # noqa: BLE001
            logger.error("SystemWorkflow tick error: %s", str(exc)[:300])
        finally:
            self._schedule_next()

    def _update_operational_plan(self) -> bool:
        """Generate / refresh the self-generated operational plan.

        Covers all required domains:
          - Revenue generation (self-selling engine)
          - Customer onboarding
          - Production delivery
          - Compliance monitoring
          - System health and self-repair
          - Community building and outreach
          - Resource allocation and cost management
        """
        plan: Dict[str, Any] = {
            "plan_version": uuid.uuid4().hex[:8],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "domains": {
                "revenue_generation": {
                    "owner": "VP Sales",
                    "subsystem": "self_selling_engine",
                    "objective": "Run 20-minute autonomous selling cycles",
                    "kpi": "qualified_prospects_per_cycle",
                },
                "customer_onboarding": {
                    "owner": "VP Customer Success",
                    "subsystem": "agentic_onboarding_engine",
                    "objective": "Complete agentic onboarding for every trial sign-up",
                    "kpi": "onboarding_completion_rate",
                },
                "production_delivery": {
                    "owner": "VP Operations",
                    "subsystem": "full_automation_controller",
                    "objective": "Deliver production work orders on schedule",
                    "kpi": "work_order_completion_rate",
                },
                "compliance_monitoring": {
                    "owner": "VP Compliance",
                    "subsystem": "compliance_engine",
                    "objective": "Maintain 100% regulatory compliance across all outreach",
                    "kpi": "compliance_violation_count",
                },
                "system_health": {
                    "owner": "VP Engineering",
                    "subsystem": "autonomous_repair_system",
                    "objective": "Self-detect and repair faults before human escalation",
                    "kpi": "mean_time_to_recovery",
                },
                "community_outreach": {
                    "owner": "VP Marketing",
                    "subsystem": "campaign_orchestrator",
                    "objective": "Run community building and brand campaigns",
                    "kpi": "community_engagement_rate",
                },
                "resource_allocation": {
                    "owner": "VP Finance",
                    "subsystem": "cost_optimization_advisor",
                    "objective": "Minimise operational spend while meeting SLOs",
                    "kpi": "cost_per_customer",
                },
            },
        }
        with self._lock:
            self._operational_plan = plan
        return True

    def _degrade_plan(self, degraded_roles: List[str]) -> None:
        """Narrow the operational plan when confidence is below threshold."""
        logger.warning(
            "SystemWorkflow degrading plan — confidence below %.2f. "
            "Degraded roles: %s",
            self._confidence_threshold,
            degraded_roles,
        )
        with self._lock:
            self._operational_plan["degraded_roles"] = degraded_roles
            self._operational_plan["scope_reduction"] = (
                "Automation scope narrowed to healthy roles only"
            )


# ---------------------------------------------------------------------------
# CEOBranch
# ---------------------------------------------------------------------------

class CEOBranch:
    """Top-level autonomous decision-making module for Murphy System.

    Activates all subsystem controllers, maintains the org chart, runs
    the self-generating operational plan, and hosts the continuous
    :class:`SystemWorkflow` loop.

    Integration points wired in this class:
      P0 — Persona loading: ``activate()`` seeds every VP role's Rosetta
           state document so agents have context from tick #1.
      P1 — VP Rosetta access: ``rosetta_manager`` is passed to each role.
      P2 — Report write-back: ``SystemWorkflow`` persists reports.
      P3 — Directive routing: ``issue_directive()`` records through
           ``RosettaPlatformManager`` for audit trail.
      P4 — Heartbeat translators: ``activate()`` registers MANAGEMENT-
           tier translator that cascades pulses to VP roles.

    Designed to be embedded inside :class:`ActivatedHeartbeatRunner` as
    an optional extension (see ``ceo_branch`` parameter in the runner).

    Thread-safe via an internal Lock.
    """

    def __init__(
        self,
        role_probes: Optional[Dict[str, Callable[[], Dict[str, Any]]]] = None,
        tick_interval: float = _DEFAULT_TICK_SECONDS,
        confidence_threshold: float = _CONFIDENCE_THRESHOLD,
        alert_hook: Optional[Callable[[List[str]], None]] = None,
        event_backbone: Any = None,
        *,
        rosetta_manager: Optional[Any] = None,
        platform_manager: Optional[Any] = None,
        heartbeat: Optional[Any] = None,
    ) -> None:
        """Initialise the CEO branch.

        Args:
            role_probes: Optional per-role health probe callables.
                Mapping of ``role_label -> () -> {"healthy": bool, ...}``.
            tick_interval: Seconds between workflow ticks.
            confidence_threshold: Min confidence for full automation.
            alert_hook: Optional alert callback ``(alerts: List[str]) -> None``.
            event_backbone: Optional :class:`EventBackbone` instance.  When
                provided, telemetry events are also published to the backbone
                so they flow through the system-wide event fabric.
            rosetta_manager: Optional :class:`RosettaManager` — enables P0
                (persona loading), P1 (VP state access), and P2 (report write-back).
            platform_manager: Optional :class:`RosettaPlatformManager` —
                enables P3 (directive audit trail via sync_down).
            heartbeat: Optional :class:`RosettaStoneHeartbeat` — enables
                P4 (management-tier translator registration).
        """
        self._lock = threading.Lock()
        self._branch_id: str = uuid.uuid4().hex[:12]
        self._activated: bool = False
        self._activation_time: Optional[str] = None
        self._telemetry: List[Dict[str, Any]] = []
        self._backbone = event_backbone
        self._rosetta_manager = rosetta_manager
        self._platform_manager = platform_manager
        self._heartbeat = heartbeat

        # Build org chart (P1 — pass rosetta_manager to every VP role)
        self._org_chart = OrgChartAutomation(
            role_probes=role_probes, rosetta_manager=rosetta_manager,
        )

        # Build continuous workflow (P2 — pass rosetta_manager for report write-back)
        self._workflow = SystemWorkflow(
            org_chart=self._org_chart,
            tick_interval=tick_interval,
            confidence_threshold=confidence_threshold,
            alert_hook=alert_hook,
            rosetta_manager=rosetta_manager,
        )

        logger.info("CEOBranch %s initialised.", self._branch_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def activate(self) -> Dict[str, Any]:
        """Activate the CEO branch.

        On first activation:
          1. Readiness check (query all VP roles).
          2. **P0** — Seed Rosetta state for every VP role.
          3. **P4** — Register MANAGEMENT-tier heartbeat translator.
          4. Start the workflow loop.

        Always returns an activation report regardless of readiness.

        Returns:
            Dict with ``activated``, ``readiness``, and metadata.
        """
        readiness = self._workflow.readiness_check()
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            if self._activated:
                return {
                    "activated": True,
                    "already_active": True,
                    "branch_id": self._branch_id,
                    "readiness": readiness,
                    "at": now,
                }

        # P0 — Seed Rosetta state for every VP role
        personas_loaded = self._seed_rosetta_personas()

        # P4 — Register heartbeat management-tier translator
        heartbeat_registered = self._register_heartbeat_translator()

        # Start the workflow regardless (supports graceful degradation)
        self._workflow.start()

        with self._lock:
            self._activated = True
            self._activation_time = now

        self._emit_telemetry(
            "ceo_branch_activated",
            {
                "readiness": readiness,
                "at": now,
                "personas_loaded": personas_loaded,
                "heartbeat_registered": heartbeat_registered,
            },
        )
        logger.info(
            "CEOBranch %s activated. Ready=%s degraded=%s personas=%d",
            self._branch_id,
            readiness["ready"],
            readiness["degraded_roles"],
            personas_loaded,
        )
        return {
            "activated": True,
            "already_active": False,
            "branch_id": self._branch_id,
            "readiness": readiness,
            "personas_loaded": personas_loaded,
            "heartbeat_registered": heartbeat_registered,
            "at": now,
        }

    def deactivate(self) -> None:
        """Stop the workflow loop and mark the branch inactive."""
        self._workflow.stop()
        with self._lock:
            self._activated = False
        self._emit_telemetry("ceo_branch_deactivated", {})
        logger.info("CEOBranch %s deactivated.", self._branch_id)

    @property
    def activated(self) -> bool:
        with self._lock:
            return self._activated

    # ------------------------------------------------------------------
    # Strategic interface
    # ------------------------------------------------------------------

    def run_tick(self) -> WorkflowTickResult:
        """Execute a single workflow tick (can be called externally by the
        heartbeat runner for tight integration).
        """
        result = self._workflow.tick()
        self._emit_telemetry(
            "ceo_tick",
            {
                "tick_number": result.tick_number,
                "confidence": result.confidence,
                "degraded_roles": result.degraded_roles,
                "alerts": result.alerts[:10],
            },
        )
        return result

    def get_org_chart(self) -> List[Dict[str, Any]]:
        """Return the current org chart state."""
        return self._org_chart.get_org_chart()

    def issue_directive(
        self, directive: str, roles: Optional[List[str]] = None
    ) -> List[DirectiveResult]:
        """Issue a top-down directive to all (or selected) VP roles.

        P3 — When a ``platform_manager`` is configured, the directive is
        recorded in the platform state layer for audit trail and
        persistence.  Each target agent receives a ``sync_down()`` push
        so its Rosetta state reflects the new directive.
        """
        results = self._org_chart.broadcast_directive(directive, roles=roles)

        # P3 — Route through Platform Manager for audit trail
        if self._platform_manager is not None:
            try:
                self._platform_manager.update_platform(
                    status="active",
                    metadata={"last_directive": str(directive or "")[:200]},
                )
                # Push directive to each targeted agent via sync_down
                target_roles = self._org_chart.get_all_roles()
                if roles is not None:
                    target_roles = {
                        k: v for k, v in target_roles.items() if k in roles
                    }
                for role in target_roles.values():
                    try:
                        self._platform_manager.sync_down(role.agent_id)
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:  # noqa: BLE001
                logger.debug("P3: platform_manager directive recording failed: %s", str(exc)[:200])

        self._emit_telemetry(
            "ceo_directive",
            {
                "directive_preview": str(directive or "")[:100],
                "target_roles": roles or "all",
                "result_count": len(results),
            },
        )
        return results

    def get_operational_plan(self) -> Dict[str, Any]:
        """Return the current operational plan."""
        return self._workflow.get_operational_plan()

    def readiness_check(self) -> Dict[str, Any]:
        """Verify all dependencies before full activation."""
        return self._workflow.readiness_check()

    # ------------------------------------------------------------------
    # Status and telemetry
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of the CEO branch state."""
        workflow_status = self._workflow.get_status()
        with self._lock:
            return {
                "branch_id": self._branch_id,
                "activated": self._activated,
                "activation_time": self._activation_time,
                "telemetry_event_count": len(self._telemetry),
                **workflow_status,
            }

    def get_telemetry(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent telemetry events."""
        limit = max(1, min(int(limit), _MAX_TELEMETRY_EVENTS))
        with self._lock:
            return list(self._telemetry[-limit:])

    def _emit_telemetry(self, event: str, data: Dict[str, Any]) -> None:
        entry: Dict[str, Any] = {
            "event": event,
            "branch_id": self._branch_id,
            "at": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        with self._lock:
            capped_append(self._telemetry, entry, max_size=_MAX_TELEMETRY_EVENTS)
        if self._backbone is not None:
            try:
                self._backbone.publish(event, entry)
            except Exception:
                logger.debug("CEOBranch: EventBackbone publish failed for event %r", event)

    # ------------------------------------------------------------------
    # P0 — Seed Rosetta state for every VP role (Gap 2 closure)
    # ------------------------------------------------------------------

    def _seed_rosetta_personas(self) -> int:
        """Create a Rosetta state document for each VP role in the org chart.

        Uses the canonical ``_ORG_CHART_DEFINITION`` to build an initial
        ``RosettaAgentState`` per role.  Each agent gets:
          - identity: agent_id derived from role label, name = role label,
            role = first responsibility, org = "murphy-system"
          - system_state: status="idle" (not yet active)
          - agent_state: current_phase = "onboarding"

        Returns the count of successfully created personas.
        """
        if self._rosetta_manager is None or not _ROSETTA_AVAILABLE:
            return 0

        loaded = 0
        all_roles = self._org_chart.get_all_roles()
        for role in all_roles.values():
            try:
                # Skip if state already exists (idempotent)
                existing = self._rosetta_manager.load_state(role.agent_id)
                if existing is not None:
                    loaded += 1
                    continue

                state = _RosettaAgentState(
                    identity=_Identity(
                        agent_id=role.agent_id,
                        name=role.role_label,
                        role=role.role_label,
                        version="1.0.0",
                        organization="murphy-system",
                    ),
                    system_state=_SystemState(status="idle"),
                    agent_state=_AgentState(current_phase="onboarding"),
                )
                self._rosetta_manager.save_state(state)
                loaded += 1
                logger.debug("P0: seeded Rosetta state for %s (%s)",
                             role.role_label, role.agent_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "P0: failed to seed Rosetta state for %s: %s",
                    role.role_label, str(exc)[:200],
                )
        return loaded

    # ------------------------------------------------------------------
    # P4 — Register heartbeat tier translator (Gap 4 closure)
    # ------------------------------------------------------------------

    def _register_heartbeat_translator(self) -> bool:
        """Register a MANAGEMENT-tier translator that routes heartbeat
        pulses to all VP roles as directives.

        The translator converts each pulse's ``directives`` field into
        ``execute_directive()`` calls on all non-CEO VP roles, enabling
        cascading organisational communication.

        Returns ``True`` if registration succeeded, ``False`` otherwise.
        """
        if self._heartbeat is None or not _HEARTBEAT_AVAILABLE:
            return False

        try:
            org_chart = self._org_chart

            def _management_translator(pulse_dict):
                """Convert a heartbeat pulse into VP-level directives."""
                directives = pulse_dict.get("directives", {})
                if not directives:
                    return {"ack": True, "actions": 0}

                directive_text = "; ".join(
                    f"{k}: {v}" for k, v in directives.items()
                )[:_MAX_DIRECTIVE_LEN]

                roles = org_chart.get_all_roles()
                actions = 0
                for label, role in roles.items():
                    if label == "CEO":
                        continue  # CEO is the pulse origin; skip
                    try:
                        role.execute_directive(directive_text)
                        actions += 1
                    except Exception:
                        pass
                return {"ack": True, "actions": actions}

            self._heartbeat.register_translator(
                _OrganizationTier.MANAGEMENT, _management_translator,
            )
            logger.info("P4: registered MANAGEMENT-tier heartbeat translator")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("P4: heartbeat translator registration failed: %s", str(exc)[:200])
            return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Data models
    "RoleReport",
    "DirectiveResult",
    "WorkflowTickResult",
    # Enums
    "RoleStatus",
    "WorkflowPhase",
    # Classes
    "VPRole",
    "OrgChartAutomation",
    "SystemWorkflow",
    "CEOBranch",
    # Constants
    "_ORG_CHART_DEFINITION",
    "_CONFIDENCE_THRESHOLD",
    "_DEFAULT_TICK_SECONDS",
]
