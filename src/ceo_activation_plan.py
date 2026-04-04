# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
CEO Branch Activation & Org Chart Automation Plan — Murphy System.

Design Label: CEO-001 — CEO Branch Activation Plan
Owner: Executive / Platform Engineering
Dependencies:
  - inoni_org_bootstrap.InoniOrgBootstrap — existing org chart bootstrap
  - thread_safe_operations.capped_append — bounded collections

This module defines Murphy's self-executing operational plan to activate its
CEO branch, populate the org chart, and run itself.

Key classes:
  - OrgChartPosition     — single position in the org chart (human or agent)
  - OrgWorkflow          — automated workflow for a role with dependency graph
  - DeploymentReadinessReport — self-check: does Murphy have what it needs?
  - CEOActivationPlan    — top-level self-operating plan
  - MurphyOrgChartManager — manages the org chart, validates dependencies,
                             generates readiness reports
  - WorkflowOrchestrator — resolves workflow dependencies, runs workflows in
                           dependency order

Role-to-subsystem mapping:
  CEO       → self_selling_engine + campaign_orchestrator + inoni_org_bootstrap
  CTO       → autonomous_repair_system + murphy_code_healer + deployment_readiness
  COO       → onboarding_flow + production_assistant + agentic_onboarding_engine
  CMO       → self_marketing_orchestrator + outreach_campaign_planner +
               marketing_analytics_aggregator + adaptive_campaign_engine
  CFO       → billing/api + unit_economics_analyzer + subscription_manager
  VP_Sales  → sales_automation + self_selling_engine + contact_compliance_governor
  VP_Engineering → code_healer + autonomous_repair + test_runner
  Head_Compliance → compliance_engine + compliance_as_code_engine +
                     contact_compliance_governor

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock (CWE-362)
  - Non-destructive: org chart positions transition forward only; no deletion
  - Bounded collections via capped_append (CWE-770)
  - Input validated before processing (CWE-20)
  - Collection hard caps prevent memory exhaustion (CWE-400)
  - Error messages sanitised before logging (CWE-209)
"""

from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input-validation constants                                        [CWE-20]
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_NAME_RE = re.compile(r"^[a-zA-Z0-9 _\-\.]{1,200}$")
_MAX_TITLE_LEN = 200
_MAX_NOTES_LEN = 2_000
_MAX_SUBSYSTEMS_PER_ROLE = 20

# Collection hard caps                                             [CWE-400]
_MAX_POSITIONS = 500
_MAX_WORKFLOWS = 500
_MAX_AUDIT_LOG = 10_000
_MAX_WORKFLOW_STEPS = 100

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PositionType(str, Enum):
    HUMAN         = "human"
    SHADOW_AGENT  = "shadow_agent"
    HYBRID        = "hybrid"


class PositionStatus(str, Enum):
    VACANT     = "vacant"
    ACTIVE     = "active"
    ONBOARDING = "onboarding"
    SUSPENDED  = "suspended"


class WorkflowStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    BLOCKED   = "blocked"


class ReadinessLevel(str, Enum):
    READY          = "ready"
    PARTIALLY_READY = "partially_ready"
    NOT_READY      = "not_ready"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class OrgChartPosition:
    """A single position in the Murphy org chart."""
    position_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    department: str = ""
    position_type: str = PositionType.SHADOW_AGENT.value
    holder_name: str = ""
    reports_to: str = ""           # position_id of the manager
    subsystems: List[str] = field(default_factory=list)   # Murphy modules mapped to this role
    permissions: List[str] = field(default_factory=list)
    status: str = PositionStatus.VACANT.value
    agent_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "title": self.title,
            "department": self.department,
            "position_type": self.position_type,
            "holder_name": self.holder_name,
            "reports_to": self.reports_to,
            "subsystems": list(self.subsystems),
            "permissions": list(self.permissions),
            "status": self.status,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "notes": self.notes,
        }


@dataclass
class WorkflowStep:
    """A single step in an OrgWorkflow."""
    step_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    module: str = ""     # Murphy module that executes this step
    method: str = ""     # Method / action to call
    depends_on: List[str] = field(default_factory=list)  # step_ids this step depends on
    status: str = WorkflowStatus.PENDING.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "module": self.module,
            "method": self.method,
            "depends_on": list(self.depends_on),
            "status": self.status,
        }


@dataclass
class OrgWorkflow:
    """Automated workflow for a Murphy org role with a dependency graph."""
    workflow_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str = ""                     # role name, e.g. "CMO"
    position_id: str = ""
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    status: str = WorkflowStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "role": self.role,
            "position_id": self.position_id,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "notes": self.notes,
        }


@dataclass
class DeploymentReadinessReport:
    """Self-check report: does Murphy have everything needed to self-operate?"""
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    overall_readiness: str = ReadinessLevel.NOT_READY.value
    total_positions: int = 0
    filled_positions: int = 0
    missing_positions: List[str] = field(default_factory=list)
    subsystem_coverage: Dict[str, bool] = field(default_factory=dict)
    missing_subsystems: List[str] = field(default_factory=list)
    workflow_readiness: Dict[str, str] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "overall_readiness": self.overall_readiness,
            "total_positions": self.total_positions,
            "filled_positions": self.filled_positions,
            "missing_positions": self.missing_positions,
            "subsystem_coverage": dict(self.subsystem_coverage),
            "missing_subsystems": list(self.missing_subsystems),
            "workflow_readiness": dict(self.workflow_readiness),
            "gaps": list(self.gaps),
            "recommendations": list(self.recommendations),
        }


@dataclass
class CEOActivationPlan:
    """Top-level self-executing plan for Murphy to activate its CEO branch."""
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Murphy CEO Branch Activation"
    description: str = (
        "Murphy activates its CEO branch, populates the org chart, "
        "and runs itself autonomously."
    )
    org_chart: List[OrgChartPosition] = field(default_factory=list)
    workflows: List[OrgWorkflow] = field(default_factory=list)
    readiness_report: Optional[DeploymentReadinessReport] = None
    status: str = WorkflowStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    activated_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "org_chart": [p.to_dict() for p in self.org_chart],
            "workflow_count": len(self.workflows),
            "readiness_report": self.readiness_report.to_dict() if self.readiness_report else None,
            "status": self.status,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Required subsystems — all modules Murphy needs for full self-operation
# ---------------------------------------------------------------------------

REQUIRED_SUBSYSTEMS: List[str] = [
    # Self-selling / marketing
    "self_selling_engine",
    "campaign_orchestrator",
    "outreach_campaign_planner",
    "contact_compliance_governor",
    "self_marketing_orchestrator",
    "adaptive_campaign_engine",
    # Onboarding / delivery
    "agentic_onboarding_engine",
    "onboarding_flow",
    "production_assistant",
    # Confidence / gating
    "murphy_confidence_gates",
    "murphy_gate",
    # Compliance
    "compliance_engine",
    "compliance_as_code_engine",
    # Revenue / billing
    "billing_api",
    "subscription_manager",
    "unit_economics_analyzer",
    # Infrastructure
    "autonomous_repair_system",
    "murphy_code_healer",
    "deployment_readiness",
    "inoni_org_bootstrap",
]


# ---------------------------------------------------------------------------
# Default org chart definition
# ---------------------------------------------------------------------------

def _build_default_org_chart() -> List[OrgChartPosition]:
    """Return the default org chart structure for Murphy self-operation."""
    positions = [
        OrgChartPosition(
            position_id="pos-founder",
            title="Founder / Admin",
            department="executive",
            position_type=PositionType.HUMAN.value,
            holder_name=os.environ.get("MURPHY_FOUNDER_NAME", ""),
            reports_to="",
            subsystems=[],
            permissions=["all"],
            status=PositionStatus.ACTIVE.value,
            notes="Sole human employee. All agents report to Founder.",
        ),
        OrgChartPosition(
            position_id="pos-ceo",
            title="CEO (Autonomous Operations)",
            department="executive",
            position_type=PositionType.SHADOW_AGENT.value,
            holder_name="Murphy (AI)",
            reports_to="pos-founder",
            subsystems=[
                "self_selling_engine",
                "campaign_orchestrator",
                "inoni_org_bootstrap",
                "murphy_confidence_gates",
            ],
            permissions=[
                "strategic_direction",
                "org_chart_management",
                "revenue_oversight",
                "approve_campaigns",
            ],
            status=PositionStatus.VACANT.value,
            notes="Activated when all dependencies are verified ready.",
        ),
        OrgChartPosition(
            position_id="pos-cto",
            title="CTO (Platform Engineering)",
            department="engineering",
            position_type=PositionType.SHADOW_AGENT.value,
            holder_name="Murphy Engineering Agent",
            reports_to="pos-founder",
            subsystems=[
                "autonomous_repair_system",
                "murphy_code_healer",
                "deployment_readiness",
                "murphy_gate",
            ],
            permissions=[
                "system_monitoring",
                "deployment",
                "code_review",
                "incident_response",
            ],
            status=PositionStatus.VACANT.value,
        ),
        OrgChartPosition(
            position_id="pos-coo",
            title="COO (Operations)",
            department="operations",
            position_type=PositionType.SHADOW_AGENT.value,
            holder_name="Murphy Operations Agent",
            reports_to="pos-founder",
            subsystems=[
                "agentic_onboarding_engine",
                "onboarding_flow",
                "production_assistant",
            ],
            permissions=[
                "onboarding_management",
                "production_oversight",
                "client_relations",
            ],
            status=PositionStatus.VACANT.value,
        ),
        OrgChartPosition(
            position_id="pos-cmo",
            title="CMO (Marketing)",
            department="marketing",
            position_type=PositionType.SHADOW_AGENT.value,
            holder_name="Murphy Marketing Agent",
            reports_to="pos-ceo",
            subsystems=[
                "self_marketing_orchestrator",
                "outreach_campaign_planner",
                "adaptive_campaign_engine",
                "contact_compliance_governor",
            ],
            permissions=[
                "campaigns",
                "content_calendar",
                "analytics",
                "brand",
                "outreach",
            ],
            status=PositionStatus.VACANT.value,
        ),
        OrgChartPosition(
            position_id="pos-cfo",
            title="CFO (Finance)",
            department="finance",
            position_type=PositionType.SHADOW_AGENT.value,
            holder_name="Murphy Finance Agent",
            reports_to="pos-founder",
            subsystems=[
                "billing_api",
                "subscription_manager",
                "unit_economics_analyzer",
            ],
            permissions=[
                "billing",
                "pricing",
                "revenue_reporting",
                "budget",
            ],
            status=PositionStatus.VACANT.value,
        ),
        OrgChartPosition(
            position_id="pos-vp-sales",
            title="VP Sales",
            department="sales",
            position_type=PositionType.SHADOW_AGENT.value,
            holder_name="Murphy Sales Agent",
            reports_to="pos-ceo",
            subsystems=[
                "self_selling_engine",
                "contact_compliance_governor",
                "outreach_campaign_planner",
            ],
            permissions=[
                "lead_management",
                "outreach",
                "pipeline",
                "close_deals",
            ],
            status=PositionStatus.VACANT.value,
        ),
        OrgChartPosition(
            position_id="pos-head-compliance",
            title="Head of Compliance",
            department="legal",
            position_type=PositionType.SHADOW_AGENT.value,
            holder_name="Murphy Compliance Agent",
            reports_to="pos-ceo",
            subsystems=[
                "compliance_engine",
                "compliance_as_code_engine",
                "contact_compliance_governor",
            ],
            permissions=[
                "compliance_policy",
                "audit_trail",
                "regulatory_review",
            ],
            status=PositionStatus.VACANT.value,
        ),
    ]
    return positions


# ---------------------------------------------------------------------------
# Default workflow definitions
# ---------------------------------------------------------------------------

def _build_default_workflows(positions: List[OrgChartPosition]) -> List[OrgWorkflow]:
    """Return the default automated workflows for each org role."""
    pos_by_title: Dict[str, str] = {p.title: p.position_id for p in positions}

    workflows = [
        OrgWorkflow(
            workflow_id="wf-ceo-activate",
            role="CEO",
            position_id=pos_by_title.get("CEO (Autonomous Operations)", "pos-ceo"),
            description="Activate CEO branch: validate subsystems, populate org chart, start all cycles.",
            steps=[
                WorkflowStep(
                    step_id="step-verify-deps",
                    name="Verify all dependencies",
                    description="Run deployment readiness check across all required subsystems.",
                    module="deployment_readiness",
                    method="run_full_check",
                    depends_on=[],
                ),
                WorkflowStep(
                    step_id="step-bootstrap-org",
                    name="Bootstrap org chart",
                    description="Instantiate InoniOrgBootstrap and populate shadow agents.",
                    module="inoni_org_bootstrap",
                    method="bootstrap",
                    depends_on=["step-verify-deps"],
                ),
                WorkflowStep(
                    step_id="step-start-selling",
                    name="Start self-selling engine",
                    description="Begin 20-minute outreach cycles via MurphySelfSellingEngine.",
                    module="self_selling_engine",
                    method="run_selling_cycle",
                    depends_on=["step-bootstrap-org"],
                ),
                WorkflowStep(
                    step_id="step-start-marketing",
                    name="Start marketing orchestrator",
                    description="Begin content, social, outreach, and developer cycles.",
                    module="self_marketing_orchestrator",
                    method="run_all_cycles",
                    depends_on=["step-bootstrap-org"],
                ),
            ],
        ),
        OrgWorkflow(
            workflow_id="wf-cmo-marketing",
            role="CMO",
            position_id=pos_by_title.get("CMO (Marketing)", "pos-cmo"),
            description="CMO workflow: content, outreach, compliance, analytics.",
            steps=[
                WorkflowStep(
                    step_id="step-compliance-check",
                    name="Run compliance health check",
                    description="Verify ContactComplianceGovernor and OutreachComplianceGate.",
                    module="contact_compliance_governor",
                    method="get_status",
                    depends_on=[],
                ),
                WorkflowStep(
                    step_id="step-run-campaigns",
                    name="Run campaign orchestrator",
                    description="Execute active campaign plans respecting compliance rules.",
                    module="campaign_orchestrator",
                    method="run_active_campaigns",
                    depends_on=["step-compliance-check"],
                ),
                WorkflowStep(
                    step_id="step-outreach-schedule",
                    name="Build daily outreach schedule",
                    description="Generate compliant outreach schedules via OutreachCampaignPlanner.",
                    module="outreach_campaign_planner",
                    method="build_daily_outreach_schedule",
                    depends_on=["step-compliance-check"],
                ),
                WorkflowStep(
                    step_id="step-analytics-report",
                    name="Generate analytics report",
                    description="Aggregate marketing metrics via adaptive campaign engine.",
                    module="adaptive_campaign_engine",
                    method="get_status",
                    depends_on=["step-run-campaigns", "step-outreach-schedule"],
                ),
            ],
        ),
        OrgWorkflow(
            workflow_id="wf-cto-platform",
            role="CTO",
            position_id=pos_by_title.get("CTO (Platform Engineering)", "pos-cto"),
            description="CTO workflow: monitor, repair, deploy.",
            steps=[
                WorkflowStep(
                    step_id="step-monitor",
                    name="Monitor system health",
                    description="Run autonomous repair system health check.",
                    module="autonomous_repair_system",
                    method="run_health_check",
                    depends_on=[],
                ),
                WorkflowStep(
                    step_id="step-heal",
                    name="Heal detected issues",
                    description="Execute code healer proposals for detected gaps.",
                    module="murphy_code_healer",
                    method="run_healing_cycle",
                    depends_on=["step-monitor"],
                ),
                WorkflowStep(
                    step_id="step-deploy-check",
                    name="Deployment readiness check",
                    description="Validate all environment variables, DB, Redis, modules.",
                    module="deployment_readiness",
                    method="run_full_check",
                    depends_on=["step-heal"],
                ),
            ],
        ),
        OrgWorkflow(
            workflow_id="wf-coo-operations",
            role="COO",
            position_id=pos_by_title.get("COO (Operations)", "pos-coo"),
            description="COO workflow: onboarding, production, client success.",
            steps=[
                WorkflowStep(
                    step_id="step-onboarding-queue",
                    name="Process onboarding queue",
                    description="Run agentic onboarding for queued prospects.",
                    module="agentic_onboarding_engine",
                    method="run_onboarding_cycle",
                    depends_on=[],
                ),
                WorkflowStep(
                    step_id="step-production-validate",
                    name="Validate production work orders",
                    description="Run 99% confidence validation on pending work orders.",
                    module="production_assistant",
                    method="validate_pending_work_orders",
                    depends_on=["step-onboarding-queue"],
                ),
            ],
        ),
        OrgWorkflow(
            workflow_id="wf-cfo-finance",
            role="CFO",
            position_id=pos_by_title.get("CFO (Finance)", "pos-cfo"),
            description="CFO workflow: billing, subscriptions, unit economics.",
            steps=[
                WorkflowStep(
                    step_id="step-billing-health",
                    name="Billing health check",
                    description="Verify PayPal + Coinbase webhook endpoints and subscription state.",
                    module="billing_api",
                    method="health_check",
                    depends_on=[],
                ),
                WorkflowStep(
                    step_id="step-subscription-report",
                    name="Subscription status report",
                    description="Generate subscription count by tier and MRR.",
                    module="subscription_manager",
                    method="get_status",
                    depends_on=["step-billing-health"],
                ),
                WorkflowStep(
                    step_id="step-unit-economics",
                    name="Unit economics report",
                    description="Generate LTV, CAC, and margin analysis.",
                    module="unit_economics_analyzer",
                    method="run_analysis",
                    depends_on=["step-subscription-report"],
                ),
            ],
        ),
    ]
    return workflows


# ---------------------------------------------------------------------------
# MurphyOrgChartManager
# ---------------------------------------------------------------------------


class MurphyOrgChartManager:
    """Manages the Murphy org chart: positions, workflows, and readiness.

    Thread-safe via an internal Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._positions: Dict[str, OrgChartPosition] = {}
        self._workflows: Dict[str, OrgWorkflow] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_id(value: str, label: str = "id") -> str:
        value = str(value or "").strip().replace("\x00", "")
        if not _ID_RE.match(value):
            raise ValueError(f"Invalid {label}: must match {_ID_RE.pattern}")
        return value

    # ------------------------------------------------------------------
    # Org chart management
    # ------------------------------------------------------------------

    def add_position(self, position: OrgChartPosition) -> OrgChartPosition:
        """Add a position to the org chart.

        Raises:
            ValueError: if position_id is invalid or org chart is at capacity.
        """
        self._validate_id(position.position_id, "position_id")
        with self._lock:
            if len(self._positions) >= _MAX_POSITIONS:
                raise ValueError(f"Org chart at capacity ({_MAX_POSITIONS}).")
            self._positions[position.position_id] = position
            capped_append(
                self._audit_log,
                {
                    "action": "add_position",
                    "position_id": position.position_id,
                    "title": position.title,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
                max_size=_MAX_AUDIT_LOG,
            )
        logger.info("Org chart: added position %s (%s)", position.position_id, position.title)
        return position

    def activate_position(self, position_id: str, agent_id: Optional[str] = None) -> bool:
        """Transition a position from VACANT to ACTIVE.

        Returns True if activated, False if not found.
        """
        position_id = self._validate_id(position_id, "position_id")
        with self._lock:
            pos = self._positions.get(position_id)
            if pos is None:
                return False
            pos.status = PositionStatus.ACTIVE.value
            if agent_id:
                pos.agent_id = str(agent_id)[:200]
            capped_append(
                self._audit_log,
                {
                    "action": "activate_position",
                    "position_id": position_id,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
                max_size=_MAX_AUDIT_LOG,
            )
        return True

    def get_position(self, position_id: str) -> Optional[OrgChartPosition]:
        """Return a position by ID, or None if not found."""
        position_id = self._validate_id(position_id, "position_id")
        with self._lock:
            return self._positions.get(position_id)

    def get_org_chart(self) -> List[Dict[str, Any]]:
        """Return the full org chart as a list of position dicts."""
        with self._lock:
            return [p.to_dict() for p in self._positions.values()]

    # ------------------------------------------------------------------
    # Workflow management
    # ------------------------------------------------------------------

    def add_workflow(self, workflow: OrgWorkflow) -> OrgWorkflow:
        """Register an automated workflow."""
        self._validate_id(workflow.workflow_id, "workflow_id")
        with self._lock:
            if len(self._workflows) >= _MAX_WORKFLOWS:
                raise ValueError(f"Workflow registry at capacity ({_MAX_WORKFLOWS}).")
            self._workflows[workflow.workflow_id] = workflow
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[OrgWorkflow]:
        """Return a workflow by ID, or None if not found."""
        workflow_id = self._validate_id(workflow_id, "workflow_id")
        with self._lock:
            return self._workflows.get(workflow_id)

    # ------------------------------------------------------------------
    # Readiness assessment
    # ------------------------------------------------------------------

    def generate_readiness_report(self) -> DeploymentReadinessReport:
        """Self-check: does Murphy have everything needed to self-operate?

        Checks:
          1. Are all required positions filled?
          2. Are all required subsystems represented in at least one position?
          3. Are all workflows defined for critical roles?
        """
        with self._lock:
            positions = dict(self._positions)
            workflows = dict(self._workflows)

        total = len(positions)
        filled = sum(
            1 for p in positions.values()
            if p.status == PositionStatus.ACTIVE.value
        )
        missing_positions = [
            p.title
            for p in positions.values()
            if p.status == PositionStatus.VACANT.value
            and p.position_type == PositionType.SHADOW_AGENT.value
        ]

        # Check subsystem coverage
        covered: Set[str] = set()
        for pos in positions.values():
            covered.update(pos.subsystems)

        subsystem_coverage: Dict[str, bool] = {
            s: (s in covered) for s in REQUIRED_SUBSYSTEMS
        }
        missing_subsystems = [s for s, present in subsystem_coverage.items() if not present]

        # Check workflow coverage for key roles
        workflow_roles = {wf.role for wf in workflows.values()}
        critical_roles = {"CEO", "CMO", "CTO", "COO", "CFO"}
        workflow_readiness: Dict[str, str] = {
            role: ("ready" if role in workflow_roles else "missing")
            for role in critical_roles
        }

        gaps: List[str] = []
        recommendations: List[str] = []

        if missing_positions:
            gaps.append(f"Unfilled positions: {missing_positions}")
            recommendations.append(
                "Activate shadow agents for all VACANT positions via MurphyOrgChartManager."
            )
        if missing_subsystems:
            gaps.append(f"Uncovered subsystems: {missing_subsystems}")
            recommendations.append(
                "Map missing subsystems to an org chart position or provision them."
            )
        for role, status in workflow_readiness.items():
            if status == "missing":
                gaps.append(f"No workflow defined for role: {role}")
                recommendations.append(
                    f"Add an OrgWorkflow for the {role} role via WorkflowOrchestrator."
                )

        if not gaps:
            overall = ReadinessLevel.READY.value
        elif len(gaps) <= 2:
            overall = ReadinessLevel.PARTIALLY_READY.value
        else:
            overall = ReadinessLevel.NOT_READY.value

        report = DeploymentReadinessReport(
            overall_readiness=overall,
            total_positions=total,
            filled_positions=filled,
            missing_positions=missing_positions,
            subsystem_coverage=subsystem_coverage,
            missing_subsystems=missing_subsystems,
            workflow_readiness=workflow_readiness,
            gaps=gaps,
            recommendations=recommendations,
        )
        with self._lock:
            capped_append(
                self._audit_log,
                {
                    "action": "readiness_report",
                    "overall": overall,
                    "gaps": len(gaps),
                    "at": report.generated_at,
                },
                max_size=_MAX_AUDIT_LOG,
            )
        return report

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "positions": len(self._positions),
                "workflows": len(self._workflows),
                "audit_log_size": len(self._audit_log),
            }


# ---------------------------------------------------------------------------
# WorkflowOrchestrator
# ---------------------------------------------------------------------------


class WorkflowOrchestrator:
    """Resolves workflow dependencies and returns an execution-ordered step list.

    Uses topological sort (Kahn's algorithm) on the step dependency graph.
    Detects cycles and raises ValueError if found.

    Thread-safe via an internal Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._execution_log: List[Dict[str, Any]] = []

    def resolve_execution_order(self, workflow: OrgWorkflow) -> List[WorkflowStep]:
        """Return workflow steps in dependency-safe execution order.

        Raises:
            ValueError: if the dependency graph contains a cycle.
        """
        steps_by_id: Dict[str, WorkflowStep] = {s.step_id: s for s in workflow.steps}

        # Build adjacency / in-degree
        in_degree: Dict[str, int] = {sid: 0 for sid in steps_by_id}
        dependents: Dict[str, List[str]] = {sid: [] for sid in steps_by_id}

        for step in workflow.steps:
            for dep_id in step.depends_on:
                if dep_id not in steps_by_id:
                    raise ValueError(
                        f"Step '{step.step_id}' depends on unknown step '{dep_id}'."
                    )
                in_degree[step.step_id] += 1
                dependents[dep_id].append(step.step_id)

        # Kahn's algorithm
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        ordered: List[WorkflowStep] = []

        while queue:
            sid = queue.pop(0)
            ordered.append(steps_by_id[sid])
            for dep_sid in dependents[sid]:
                in_degree[dep_sid] -= 1
                if in_degree[dep_sid] == 0:
                    queue.append(dep_sid)

        if len(ordered) != len(steps_by_id):
            raise ValueError(
                f"Workflow '{workflow.workflow_id}' contains a circular dependency."
            )

        with self._lock:
            capped_append(
                self._execution_log,
                {
                    "action": "resolve_execution_order",
                    "workflow_id": workflow.workflow_id,
                    "step_count": len(ordered),
                    "at": datetime.now(timezone.utc).isoformat(),
                },
                max_size=_MAX_AUDIT_LOG,
            )
        return ordered

    def get_execution_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._execution_log)


# ---------------------------------------------------------------------------
# CEOActivationPlanBuilder
# ---------------------------------------------------------------------------


class CEOActivationPlanBuilder:
    """Builds and manages the full CEO activation plan.

    Combines MurphyOrgChartManager and WorkflowOrchestrator to produce a
    CEOActivationPlan that can be inspected, validated, and executed.

    Thread-safe via an internal Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._org_manager = MurphyOrgChartManager()
        self._workflow_orchestrator = WorkflowOrchestrator()
        self._plan: Optional[CEOActivationPlan] = None

    def build(self) -> CEOActivationPlan:
        """Build the default CEO activation plan.

        Populates the org chart with default positions, adds default workflows,
        and generates an initial readiness report.
        """
        positions = _build_default_org_chart()
        for pos in positions:
            self._org_manager.add_position(pos)

        # Activate the Founder position (already human)
        self._org_manager.activate_position("pos-founder")

        workflows = _build_default_workflows(positions)
        for wf in workflows:
            self._org_manager.add_workflow(wf)

        readiness = self._org_manager.generate_readiness_report()

        plan = CEOActivationPlan(
            org_chart=positions,
            workflows=workflows,
            readiness_report=readiness,
        )
        with self._lock:
            self._plan = plan
        return plan

    def activate_ceo_branch(self) -> Dict[str, Any]:
        """Transition the CEO position to ACTIVE and return activation result."""
        success = self._org_manager.activate_position("pos-ceo")
        result = {
            "activated": success,
            "position_id": "pos-ceo",
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if success:
            with self._lock:
                if self._plan:
                    self._plan.status = WorkflowStatus.RUNNING.value
                    self._plan.activated_at = result["at"]
            logger.info("CEO branch activated.")
        return result

    def get_execution_plan(self, role: str) -> Optional[List[Dict[str, Any]]]:
        """Return the dependency-ordered step list for a role's workflow, or None."""
        role = str(role or "").strip().upper().replace("\x00", "")
        with self._lock:
            workflows = self._org_manager._workflows  # noqa: SLF001

        for wf in workflows.values():
            if wf.role.upper() == role:
                try:
                    steps = self._workflow_orchestrator.resolve_execution_order(wf)
                    return [s.to_dict() for s in steps]
                except ValueError as exc:
                    logger.error("Dependency error for role %s: %s", role, str(exc)[:200])
                    return None
        return None

    def get_readiness_report(self) -> DeploymentReadinessReport:
        """Generate a fresh readiness report against the current org chart state."""
        return self._org_manager.generate_readiness_report()

    def get_status(self) -> Dict[str, Any]:
        org_status = self._org_manager.get_status()
        with self._lock:
            plan_status = self._plan.status if self._plan else "not_built"
        return {
            "plan_status": plan_status,
            **org_status,
        }
