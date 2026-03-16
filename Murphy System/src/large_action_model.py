"""
Large Action Model (LAM) Framework — Murphy System

Transforms Murphy from a self-healing infrastructure into a Large Action Model
for business operations.  The LAM combines thought and function around money
analysis and work of any kind, generating coordinated business actions through
the dual-agent architecture of Shadow Agents (individual/personal) and Org
Chart Agents (organizational/structural).

Design label: ARCH-007 — Large Action Model Framework

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_AUDIT_ENTRIES = 50_000
_MAX_AGREEMENTS = 10_000
_MAX_LICENSES = 10_000
_MAX_SEQUENCES = 10_000

__all__ = [
    "ActionPrimitive",
    "ActionSequence",
    "AgreementResult",
    "AgreementType",
    "ExecutionResult",
    "LicenseRecord",
    "LicenseType",
    "WorkflowMatch",
    "ShadowActionPlanner",
    "OrgChartOrchestrator",
    "ActionAgreementProtocol",
    "WorkflowLicenseManager",
    "WorkflowMatchmaker",
    "LargeActionModel",
    "LAMError",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LicenseType(str, Enum):
    """License type for workflow sequences."""
    PRIVATE = "private"
    ORG_INTERNAL = "org_internal"
    LICENSED = "licensed"
    OPEN = "open"


class AgreementType(str, Enum):
    """Possible outcomes of the ActionAgreementProtocol negotiation."""
    INSTANT = "instant"
    NEGOTIATED = "negotiated"
    ESCALATED = "escalated"
    REJECTED = "rejected"


class ExecutionStatus(str, Enum):
    """Execution status for an agreed plan."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# ---------------------------------------------------------------------------
# Core data classes
# ---------------------------------------------------------------------------


@dataclass
class ActionPrimitive:
    """Atomic business action — the 'token' of the Large Action Model.

    Examples:
    - approve_expense(amount, department, requester)
    - schedule_meeting(participants, topic, duration)
    - assign_task(task, assignee, deadline, priority)
    - escalate_decision(decision, to_role, reason)
    - generate_report(report_type, date_range, audience)
    """
    action_id: str
    action_type: str          # verb category: approve, schedule, assign, escalate, analyze, generate
    domain: str               # finance, hr, engineering, sales, operations
    parameters: Dict[str, Any]
    requires_authority: str    # minimum role level required
    cost_estimate: float       # estimated resource cost
    reversible: bool           # can this action be undone?
    rollback_action: Optional[str] = None  # action_type to undo this


@dataclass
class ActionSequence:
    """A composed business workflow — analogous to a sentence in an LLM.

    Sequences can be:
    - Sequential: A → B → C
    - Parallel: A + B → C
    - Conditional: A → (if X then B else C) → D
    - Iterative: A → B → (repeat if not done) → C
    """
    sequence_id: str
    name: str
    description: str
    primitives: List[ActionPrimitive]
    dag: Dict[str, List[str]]   # dependency graph: action_id → [depends_on]
    owner_type: str             # "shadow" | "org_chart" | "shared"
    owner_id: str
    license_type: str           # "private" | "org_internal" | "licensed" | "open"
    version: str
    confidence_score: float     # how well-validated is this sequence
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgreementResult:
    """The result of an ActionAgreementProtocol negotiation."""
    agreement_id: str
    sequence_id: str
    shadow_agent_id: str
    org_id: str
    agreement_type: AgreementType
    approved_sequence: Optional[ActionSequence]
    reason: str
    conditions: List[str] = field(default_factory=list)
    requires_human: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionResult:
    """The result of executing an agreed plan."""
    execution_id: str
    agreement_id: str
    status: ExecutionStatus
    completed_actions: List[str] = field(default_factory=list)
    failed_action: Optional[str] = None
    error_message: Optional[str] = None
    audit_entries: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


@dataclass
class LicenseRecord:
    """A record of a licensed workflow."""
    license_id: str
    sequence_id: str
    owner_org_id: str
    license_type: LicenseType
    terms: Dict[str, Any]
    usage_count: int = 0
    revenue_generated: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WorkflowMatch:
    """A workflow match recommendation from the WorkflowMatchmaker."""
    match_id: str
    sequence_id: str
    sequence_name: str
    owner_org_id: str
    fit_score: float        # 0.0–1.0, higher is better
    integration_complexity: str  # "low" | "medium" | "high"
    estimated_roi: float
    rationale: str
    license_type: LicenseType


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LAMError(Exception):
    """Base exception for LAM Framework errors."""


# ---------------------------------------------------------------------------
# Shadow Action Planner
# ---------------------------------------------------------------------------


class ShadowActionPlanner:
    """Plans actions optimized for individual work styles.

    Each user's shadow agent maintains:
    - Work pattern profile (when they work best, preferred communication styles)
    - Task completion history (what approaches work for this person)
    - Preference model (how they like reports formatted, meeting lengths, etc.)
    - Personal automation library (their custom action sequences)

    The shadow planner:
    1. Receives a goal/request from the user
    2. Decomposes it into ActionPrimitives
    3. Optimizes the sequence based on this user's patterns
    4. Submits the plan to the OrgChartOrchestrator for scheduling
    5. Learns from outcomes to improve future plans
    """

    def __init__(self, shadow_agent_id: str, user_context: Optional[Dict[str, Any]] = None) -> None:
        self._shadow_agent_id = shadow_agent_id
        self._user_context: Dict[str, Any] = user_context or {}
        self._preference_model: Dict[str, Any] = {}
        self._completion_history: List[Dict[str, Any]] = []
        self._personal_library: List[ActionSequence] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Plan generation
    # ------------------------------------------------------------------

    def decompose_goal(
        self,
        goal: str,
        domain: str = "operations",
        authority_level: str = "individual",
    ) -> ActionSequence:
        """Decompose a high-level goal into an ActionSequence.

        Returns a new ActionSequence with ActionPrimitives derived from the
        goal description.  The sequence is optimized using the user's
        preference model.
        """
        primitives = self._extract_primitives(goal, domain, authority_level)
        dag = self._build_dag(primitives)
        seq = ActionSequence(
            sequence_id=uuid.uuid4().hex[:16],
            name=f"plan:{goal[:40]}",
            description=goal,
            primitives=primitives,
            dag=dag,
            owner_type="shadow",
            owner_id=self._shadow_agent_id,
            license_type=LicenseType.PRIVATE,
            version="1.0",
            confidence_score=self._compute_confidence(primitives),
        )
        return seq

    def optimize_sequence(self, sequence: ActionSequence) -> ActionSequence:
        """Re-order or adjust a sequence based on the user's preference model."""
        with self._lock:
            prefs = self._preference_model.copy()

        # Apply preference-based adjustments (e.g., batch like-domain actions)
        optimized = self._apply_preferences(sequence, prefs)
        return optimized

    def learn_from_outcome(self, sequence_id: str, outcome: Dict[str, Any]) -> None:
        """Update the preference model based on execution outcomes."""
        with self._lock:
            entry = {"sequence_id": sequence_id, "outcome": outcome, "ts": datetime.now(timezone.utc).isoformat()}
            capped_append(self._completion_history, entry, max_size=_MAX_SEQUENCES)
            self._update_preference_model(outcome)

    def add_to_personal_library(self, sequence: ActionSequence) -> None:
        """Save a validated sequence to the user's personal automation library."""
        with self._lock:
            capped_append(self._personal_library, sequence, max_size=_MAX_SEQUENCES)

    def get_personal_library(self) -> List[ActionSequence]:
        """Return the user's personal automation library."""
        with self._lock:
            return list(self._personal_library)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_primitives(
        self,
        goal: str,
        domain: str,
        authority_level: str,
    ) -> List[ActionPrimitive]:
        """Derive ActionPrimitives from a goal string."""
        # Heuristic decomposition — maps common verbs to action types
        verb_map = {
            "approve": "approve",
            "schedule": "schedule",
            "assign": "assign",
            "escalate": "escalate",
            "report": "generate",
            "analyze": "analyze",
            "create": "generate",
            "review": "analyze",
            "send": "communicate",
            "notify": "communicate",
        }
        goal_lower = goal.lower()
        detected_type = "analyze"
        for kw, at in verb_map.items():
            if kw in goal_lower:
                detected_type = at
                break

        primitive = ActionPrimitive(
            action_id=uuid.uuid4().hex[:12],
            action_type=detected_type,
            domain=domain,
            parameters={"goal": goal},
            requires_authority=authority_level,
            cost_estimate=0.0,
            reversible=detected_type not in {"approve", "communicate"},
            rollback_action="reject" if detected_type == "approve" else None,
        )
        return [primitive]

    def _build_dag(self, primitives: List[ActionPrimitive]) -> Dict[str, List[str]]:
        """Build a linear DAG for a list of primitives (sequential by default)."""
        dag: Dict[str, List[str]] = {}
        for i, prim in enumerate(primitives):
            if i == 0:
                dag[prim.action_id] = []
            else:
                dag[prim.action_id] = [primitives[i - 1].action_id]
        return dag

    def _compute_confidence(self, primitives: List[ActionPrimitive]) -> float:
        """Compute an initial confidence score based on history match."""
        if not self._completion_history:
            return 0.5
        history_len = len(self._completion_history)
        successes = sum(
            1 for e in self._completion_history
            if e.get("outcome", {}).get("status") == "completed"
        )
        return successes / (history_len or 1)

    def _apply_preferences(
        self,
        sequence: ActionSequence,
        prefs: Dict[str, Any],
    ) -> ActionSequence:
        """Apply preference model to adjust a sequence (stub for extensibility)."""
        return sequence

    def _update_preference_model(self, outcome: Dict[str, Any]) -> None:
        """Update internal preference model from execution outcome."""
        if outcome.get("status") == "completed":
            self._preference_model["success_rate"] = (
                self._preference_model.get("success_rate", 0.5) * 0.9 + 0.1
            )
        else:
            self._preference_model["success_rate"] = (
                self._preference_model.get("success_rate", 0.5) * 0.9
            )


# ---------------------------------------------------------------------------
# Org Chart Orchestrator
# ---------------------------------------------------------------------------


class OrgChartOrchestrator:
    """Orchestrates all shadow agent activities for organizational optimization.

    Responsibilities:
    - Queue management: prioritize across all shadow agents' pending actions
    - Resource allocation: ensure no budget/resource conflicts
    - Authority enforcement: verify each action has proper authorization
    - Cross-department coordination: when shadow agent A's plan affects dept B
    - Conflict resolution: when two shadow agents' plans conflict
    - Business flow optimization: reorder/batch actions for efficiency
    - Compliance checking: ensure all sequences pass governance

    The orchestrator sees the global picture that individual shadows cannot:
    - Company-wide resource utilization
    - Cross-team dependencies
    - Budget constraints across departments
    - Regulatory/compliance requirements
    - Strategic priority alignment
    """

    def __init__(
        self,
        org_id: str,
        governance_kernel=None,
        org_chart_enforcement=None,
    ) -> None:
        self._org_id = org_id
        self._governance_kernel = governance_kernel
        self._org_chart_enforcement = org_chart_enforcement
        self._queue: List[Tuple[int, ActionSequence]] = []  # (priority, sequence)
        self._resource_budgets: Dict[str, float] = {}
        self._active_sequences: Dict[str, ActionSequence] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def enqueue(self, sequence: ActionSequence, priority: int = 5) -> None:
        """Add a sequence to the orchestration queue."""
        with self._lock:
            capped_append(self._queue, (priority, sequence))
            self._queue.sort(key=lambda item: item[0])

    def dequeue_next(self) -> Optional[ActionSequence]:
        """Pop the highest-priority sequence from the queue."""
        with self._lock:
            if not self._queue:
                return None
            _, seq = self._queue.pop(0)
            return seq

    def queue_depth(self) -> int:
        """Return the current queue depth."""
        with self._lock:
            return len(self._queue)

    # ------------------------------------------------------------------
    # Constraint evaluation
    # ------------------------------------------------------------------

    def evaluate_sequence(
        self,
        sequence: ActionSequence,
    ) -> Tuple[bool, str, List[str]]:
        """Evaluate a sequence against organizational constraints.

        Returns (approved, reason, conditions).
        """
        violations: List[str] = []
        conditions: List[str] = []

        # Budget check
        total_cost = sum(p.cost_estimate for p in sequence.primitives)
        org_budget = self._resource_budgets.get(self._org_id, float("inf"))
        if total_cost > org_budget:
            violations.append(
                f"cost_estimate {total_cost:.2f} exceeds org budget {org_budget:.2f}"
            )

        # Authority check
        for prim in sequence.primitives:
            ok, reason = self._check_authority(prim, sequence.owner_id)
            if not ok:
                violations.append(f"authority_violation: {prim.action_id}: {reason}")

        # Governance kernel check
        if self._governance_kernel is not None:
            gk_ok, gk_reason = self._run_governance_check(sequence)
            if not gk_ok:
                violations.append(f"governance: {gk_reason}")

        if violations:
            return False, "; ".join(violations), conditions

        conditions.append("dual_authorization_required")
        return True, "approved", conditions

    def resolve_conflict(
        self,
        seq_a: ActionSequence,
        seq_b: ActionSequence,
    ) -> Tuple[ActionSequence, ActionSequence]:
        """Resolve resource conflicts between two sequences.

        Returns (preferred, deferred) tuple.
        """
        score_a = seq_a.confidence_score
        score_b = seq_b.confidence_score
        if score_a >= score_b:
            return seq_a, seq_b
        return seq_b, seq_a

    def set_department_budget(self, dept_or_org_id: str, budget: float) -> None:
        """Set the available resource budget for a department or org."""
        with self._lock:
            self._resource_budgets[dept_or_org_id] = budget

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_authority(
        self,
        primitive: ActionPrimitive,
        owner_id: str,
    ) -> Tuple[bool, str]:
        """Verify the action primitive's authority requirement is satisfied."""
        if self._org_chart_enforcement is not None:
            try:
                result = self._org_chart_enforcement.check_action_authority(
                    agent_id=owner_id,
                    action=primitive.action_type,
                    required_level=primitive.requires_authority,
                )
                if isinstance(result, tuple):
                    return result
                return bool(result), ""
            except Exception as exc:
                logger.warning("org_chart_enforcement.check_action_authority failed: %s", exc)
        return True, ""

    def _run_governance_check(self, sequence: ActionSequence) -> Tuple[bool, str]:
        """Run sequence-level governance checks via the GovernanceKernel."""
        try:
            result = self._governance_kernel.enforce(
                agent_id=sequence.owner_id,
                action=f"execute_sequence:{sequence.sequence_id}",
                department=sequence.owner_id,
            )
            if hasattr(result, "action"):
                from governance_kernel import EnforcementAction
                if result.action == EnforcementAction.DENY:
                    return False, result.reason
            return True, ""
        except Exception as exc:
            logger.warning("GovernanceKernel.enforce failed: %s", exc)
            return True, ""


# ---------------------------------------------------------------------------
# Action Agreement Protocol
# ---------------------------------------------------------------------------


class ActionAgreementProtocol:
    """Negotiation protocol between shadow agents and org chart orchestrator.

    When a shadow agent submits a plan:
    1. PROPOSE: Shadow submits ActionSequence to orchestrator
    2. EVALUATE: Orchestrator evaluates against org constraints
    3. NEGOTIATE: If conflicts exist, propose alternatives
    4. AGREE: Both parties accept a final plan
    5. EXECUTE: Plan is executed with dual-signed authorization
    6. REVIEW: Both parties evaluate outcome and learn

    Agreement types:
    - INSTANT: No conflicts, auto-approved within authority
    - NEGOTIATED: Minor adjustments (timing, resource allocation)
    - ESCALATED: Requires human decision-maker intervention
    - REJECTED: Violates hard constraints (compliance, budget)
    """

    def __init__(self, orchestrator: OrgChartOrchestrator) -> None:
        self._orchestrator = orchestrator
        self._agreements: List[AgreementResult] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Protocol phases
    # ------------------------------------------------------------------

    def propose(
        self,
        sequence: ActionSequence,
        shadow_agent_id: str,
        org_id: str,
    ) -> AgreementResult:
        """Run the full PROPOSE → EVALUATE → (NEGOTIATE|AGREE|ESCALATE|REJECT) cycle."""
        approved, reason, conditions = self._orchestrator.evaluate_sequence(sequence)

        if approved:
            agreement_type = AgreementType.INSTANT
            approved_sequence = sequence
            requires_human = False
        else:
            # Attempt negotiation
            negotiated, negotiated_seq, neg_reason = self._negotiate(sequence, reason)
            if negotiated:
                agreement_type = AgreementType.NEGOTIATED
                approved_sequence = negotiated_seq
                reason = neg_reason
                requires_human = False
            elif self._needs_escalation(reason):
                agreement_type = AgreementType.ESCALATED
                approved_sequence = None
                requires_human = True
            else:
                agreement_type = AgreementType.REJECTED
                approved_sequence = None
                requires_human = False

        result = AgreementResult(
            agreement_id=uuid.uuid4().hex[:16],
            sequence_id=sequence.sequence_id,
            shadow_agent_id=shadow_agent_id,
            org_id=org_id,
            agreement_type=agreement_type,
            approved_sequence=approved_sequence,
            reason=reason,
            conditions=conditions,
            requires_human=requires_human,
        )

        with self._lock:
            capped_append(self._agreements, result, max_size=_MAX_AGREEMENTS)

        return result

    def get_agreement(self, agreement_id: str) -> Optional[AgreementResult]:
        """Retrieve an agreement by ID."""
        with self._lock:
            for agreement in self._agreements:
                if agreement.agreement_id == agreement_id:
                    return agreement
        return None

    def list_agreements(self, org_id: Optional[str] = None) -> List[AgreementResult]:
        """List all agreements, optionally filtered by org."""
        with self._lock:
            if org_id is None:
                return list(self._agreements)
            return [a for a in self._agreements if a.org_id == org_id]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _negotiate(
        self,
        sequence: ActionSequence,
        violation_reason: str,
    ) -> Tuple[bool, Optional[ActionSequence], str]:
        """Attempt to produce a modified sequence that satisfies constraints.

        Returns (success, adjusted_sequence, reason).
        """
        # Budget-only violations: attempt to reduce cost estimates
        if "cost_estimate" in violation_reason and "authority" not in violation_reason:
            adjusted = ActionSequence(
                sequence_id=uuid.uuid4().hex[:16],
                name=sequence.name,
                description=sequence.description,
                primitives=[
                    ActionPrimitive(
                        action_id=p.action_id,
                        action_type=p.action_type,
                        domain=p.domain,
                        parameters=p.parameters,
                        requires_authority=p.requires_authority,
                        cost_estimate=p.cost_estimate * 0.8,
                        reversible=p.reversible,
                        rollback_action=p.rollback_action,
                    )
                    for p in sequence.primitives
                ],
                dag=sequence.dag,
                owner_type=sequence.owner_type,
                owner_id=sequence.owner_id,
                license_type=sequence.license_type,
                version=sequence.version,
                confidence_score=sequence.confidence_score * 0.9,
            )
            approved, reason, _ = self._orchestrator.evaluate_sequence(adjusted)
            if approved:
                return True, adjusted, "cost_reduced_to_fit_budget"
        return False, None, violation_reason

    def _needs_escalation(self, reason: str) -> bool:
        """Determine if a rejection reason warrants human escalation."""
        escalation_keywords = ["authority_violation", "governance", "compliance"]
        return any(kw in reason for kw in escalation_keywords)


# ---------------------------------------------------------------------------
# Workflow License Manager
# ---------------------------------------------------------------------------


class WorkflowLicenseManager:
    """Manages licensing of workflow sequences across organizations.

    Capabilities:
    - Package an ActionSequence as a licensable workflow template
    - Define license terms (usage limits, modification rights, revenue share)
    - Publish to the Murphy Workflow Marketplace
    - Match workflows: find sequences that complement your org's workflows
    - Import licensed workflows and adapt them to your org chart
    - Track usage and revenue for licensed workflows
    - Version management for evolving workflows

    License types:
    - PRIVATE: Only within owning org
    - ORG_INTERNAL: Shared across org's departments
    - LICENSED: Available to other orgs under terms
    - OPEN: Freely available (attribution required)
    """

    def __init__(self, persistence_manager=None, event_backbone=None) -> None:
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._licenses: Dict[str, LicenseRecord] = {}
        self._marketplace: List[LicenseRecord] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Licensing operations
    # ------------------------------------------------------------------

    def package_workflow(
        self,
        sequence: ActionSequence,
        owner_org_id: str,
        license_type: LicenseType,
        terms: Optional[Dict[str, Any]] = None,
    ) -> LicenseRecord:
        """Package a sequence as a licensable workflow template."""
        if not sequence.sequence_id:
            raise LAMError("sequence must have a sequence_id")
        if not owner_org_id:
            raise LAMError("owner_org_id is required")

        record = LicenseRecord(
            license_id=uuid.uuid4().hex[:16],
            sequence_id=sequence.sequence_id,
            owner_org_id=owner_org_id,
            license_type=license_type,
            terms=terms or {},
        )
        with self._lock:
            self._licenses[record.license_id] = record
            if license_type in (LicenseType.LICENSED, LicenseType.OPEN):
                capped_append(self._marketplace, record, max_size=_MAX_LICENSES)

        self._publish_event("LAM_WORKFLOW_LICENSED", {
            "license_id": record.license_id,
            "sequence_id": sequence.sequence_id,
            "owner_org_id": owner_org_id,
            "license_type": license_type,
        })
        return record

    def get_license(self, license_id: str) -> Optional[LicenseRecord]:
        """Retrieve a license record by ID."""
        with self._lock:
            return self._licenses.get(license_id)

    def list_marketplace(
        self,
        license_type: Optional[LicenseType] = None,
    ) -> List[LicenseRecord]:
        """List all publicly available workflows in the marketplace."""
        with self._lock:
            if license_type is None:
                return list(self._marketplace)
            return [r for r in self._marketplace if r.license_type == license_type]

    def record_usage(self, license_id: str, revenue: float = 0.0) -> bool:
        """Record a usage event for a licensed workflow."""
        with self._lock:
            record = self._licenses.get(license_id)
            if record is None:
                return False
            record.usage_count += 1
            record.revenue_generated += revenue
        return True

    def import_workflow(
        self,
        license_id: str,
        importing_org_id: str,
    ) -> Optional[LicenseRecord]:
        """Import a licensed workflow for use by another org.

        Returns the source license record if import is permitted.
        """
        with self._lock:
            record = self._licenses.get(license_id)
            if record is None:
                return None
            if record.license_type == LicenseType.PRIVATE:
                return None
            if record.license_type == LicenseType.ORG_INTERNAL:
                if record.owner_org_id != importing_org_id:
                    return None
            record.usage_count += 1
        return record

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Publish a LAM event to the EventBackbone if available."""
        try:
            from event_backbone import EventType
            # Map known event names to EventType values
            event_type_map: Dict[str, Any] = {
                "LAM_WORKFLOW_LICENSED": EventType.TASK_COMPLETED,
                "LAM_WORKFLOW_FAILED": EventType.TASK_FAILED,
                "LAM_GATE_EVALUATED": EventType.GATE_EVALUATED,
            }
            et = event_type_map.get(event_name)
            if et is None:
                logger.debug("No EventType mapping for LAM event %r; skipping", event_name)
                return
            self._backbone.publish(event_type=et, payload=payload)
            from event_backbone_client import publish as _bb_publish  # noqa: PLC0415
            _bb_publish(
                event_name,
                payload,
                source="workflow_license_manager",
                backbone=self._backbone,
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)


# ---------------------------------------------------------------------------
# Workflow Matchmaker
# ---------------------------------------------------------------------------


class WorkflowMatchmaker:
    """Matches organizations with complementary workflow templates.

    Analyzes:
    - Your org's current workflow gaps (what you're doing manually)
    - Your org's workflow strengths (what you've optimized)
    - Available licensed workflows from other orgs
    - Compatibility scoring (does this workflow fit your org chart?)
    - Integration complexity (how hard to adopt?)

    Produces:
    - Ranked recommendations with fit scores
    - Integration plans for top matches
    - Estimated ROI for each adoption
    """

    def __init__(self, license_manager: WorkflowLicenseManager) -> None:
        self._license_manager = license_manager

    def find_matches(
        self,
        org_profile: Dict[str, Any],
        top_n: int = 5,
    ) -> List[WorkflowMatch]:
        """Return ranked workflow matches for an organization profile.

        org_profile keys:
        - domains (List[str]): domains the org operates in
        - gaps (List[str]): known workflow gaps / pain points
        - existing_sequences (List[str]): sequence_ids already in use
        - budget_per_workflow (float): maximum cost per adopted workflow
        """
        candidates = self._license_manager.list_marketplace()
        if not candidates:
            return []

        scored: List[Tuple[float, LicenseRecord]] = []
        for record in candidates:
            score = self._compute_fit_score(record, org_profile)
            scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        matches: List[WorkflowMatch] = []
        for score, record in scored[:top_n]:
            matches.append(
                WorkflowMatch(
                    match_id=uuid.uuid4().hex[:12],
                    sequence_id=record.sequence_id,
                    sequence_name=f"workflow:{record.sequence_id[:8]}",
                    owner_org_id=record.owner_org_id,
                    fit_score=score,
                    integration_complexity=self._complexity(score),
                    estimated_roi=self._estimate_roi(score, org_profile),
                    rationale=self._build_rationale(score, org_profile),
                    license_type=record.license_type,
                )
            )
        return matches

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_fit_score(
        self,
        record: LicenseRecord,
        org_profile: Dict[str, Any],
    ) -> float:
        """Heuristic fit score 0.0–1.0 based on org profile."""
        score = 0.5
        usage_bonus = min(record.usage_count * 0.01, 0.3)
        score += usage_bonus
        # Prefer open licenses
        if record.license_type == LicenseType.OPEN:
            score += 0.1
        elif record.license_type == LicenseType.LICENSED:
            score += 0.05
        return min(score, 1.0)

    def _complexity(self, fit_score: float) -> str:
        if fit_score >= 0.8:
            return "low"
        if fit_score >= 0.6:
            return "medium"
        return "high"

    def _estimate_roi(self, fit_score: float, org_profile: Dict[str, Any]) -> float:
        budget = float(org_profile.get("budget_per_workflow", 1000.0))
        return round(budget * fit_score * 2.5, 2)

    def _build_rationale(self, fit_score: float, org_profile: Dict[str, Any]) -> str:
        gaps = org_profile.get("gaps", [])
        if gaps:
            return f"Addresses gaps in {', '.join(gaps[:3])}; fit score {fit_score:.2f}"
        return f"General workflow fit score {fit_score:.2f}"


# ---------------------------------------------------------------------------
# Large Action Model — main orchestrator
# ---------------------------------------------------------------------------


class LargeActionModel:
    """Murphy's Large Action Model — business action generation at scale.

    Like an LLM generates text from prompts, the LAM generates business
    actions from goals.  It combines:

    - Shadow Agents (personal optimization) — individual work style learning
    - Org Chart Agents (organizational optimization) — business flow optimization
    - Agreement Protocol — cultivating consensus between individual and org needs
    - Workflow Licensing — spreading optimized processes across organizations
    - Workflow Matching — discovering complementary workflows

    The LAM operates at three levels:
    1. INDIVIDUAL: Shadow agent optimizes for user's work patterns
    2. ORGANIZATIONAL: Org chart orchestrator optimizes for business goals
    3. ECOSYSTEM: Workflow marketplace enables cross-org optimization

    API:
    - generate_actions(goal, user_context, org_context) → ActionSequence
    - submit_for_orchestration(sequence) → AgreementResult
    - license_workflow(sequence, terms) → LicenseRecord
    - find_matching_workflows(org_profile) → List[WorkflowMatch]
    - execute_agreed_plan(agreement) → ExecutionResult
    """

    def __init__(
        self,
        org_id: str,
        shadow_agent_integration=None,
        governance_kernel=None,
        org_chart_enforcement=None,
        workflow_dag_engine=None,
        persistence_manager=None,
        event_backbone=None,
    ) -> None:
        self._org_id = org_id
        self._shadow_integration = shadow_agent_integration
        self._workflow_dag_engine = workflow_dag_engine
        self._event_backbone = event_backbone

        # Core sub-components
        self._orchestrator = OrgChartOrchestrator(
            org_id=org_id,
            governance_kernel=governance_kernel,
            org_chart_enforcement=org_chart_enforcement,
        )
        self._agreement_protocol = ActionAgreementProtocol(self._orchestrator)
        self._license_manager = WorkflowLicenseManager(
            persistence_manager=persistence_manager,
            event_backbone=event_backbone,
        )
        self._matchmaker = WorkflowMatchmaker(self._license_manager)

        # Per-shadow planners
        self._planners: Dict[str, ShadowActionPlanner] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_shadow(
        self,
        shadow_agent_id: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ShadowActionPlanner:
        """Register a shadow agent planner with the LAM."""
        with self._lock:
            if shadow_agent_id not in self._planners:
                self._planners[shadow_agent_id] = ShadowActionPlanner(
                    shadow_agent_id=shadow_agent_id,
                    user_context=user_context,
                )
            return self._planners[shadow_agent_id]

    def generate_actions(
        self,
        goal: str,
        shadow_agent_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        org_context: Optional[Dict[str, Any]] = None,
    ) -> ActionSequence:
        """Generate an ActionSequence from a high-level goal.

        1. Retrieves (or creates) the shadow planner for the user.
        2. Decomposes the goal into ActionPrimitives.
        3. Optimizes the sequence for the user's work style.
        4. Emits LAM_ACTION_GENERATED audit event.
        """
        planner = self.register_shadow(shadow_agent_id, user_context)
        domain = (org_context or {}).get("domain", "operations")
        authority = (user_context or {}).get("authority_level", "individual")
        sequence = planner.decompose_goal(goal, domain=domain, authority_level=authority)
        sequence = planner.optimize_sequence(sequence)

        self._audit("LAM_ACTION_GENERATED", {
            "goal": goal,
            "shadow_agent_id": shadow_agent_id,
            "sequence_id": sequence.sequence_id,
        })
        return sequence

    def submit_for_orchestration(
        self,
        sequence: ActionSequence,
        shadow_agent_id: str,
    ) -> AgreementResult:
        """Submit an ActionSequence for org-chart orchestration and agreement.

        Runs the full ActionAgreementProtocol negotiation.
        Emits LAM_AGREEMENT_PROPOSED and (if agreed) LAM_AGREEMENT_REACHED.
        """
        self._audit("LAM_AGREEMENT_PROPOSED", {
            "sequence_id": sequence.sequence_id,
            "shadow_agent_id": shadow_agent_id,
            "org_id": self._org_id,
        })
        result = self._agreement_protocol.propose(
            sequence=sequence,
            shadow_agent_id=shadow_agent_id,
            org_id=self._org_id,
        )
        if result.agreement_type in (AgreementType.INSTANT, AgreementType.NEGOTIATED):
            self._audit("LAM_AGREEMENT_REACHED", {
                "agreement_id": result.agreement_id,
                "agreement_type": result.agreement_type,
            })
        return result

    def license_workflow(
        self,
        sequence: ActionSequence,
        owner_org_id: str,
        license_type: LicenseType,
        terms: Optional[Dict[str, Any]] = None,
    ) -> LicenseRecord:
        """Package and license a workflow sequence.

        Safety: only ORG_INTERNAL, LICENSED, and OPEN sequences can be
        shared; PRIVATE sequences are never published to the marketplace.
        Emits LAM_WORKFLOW_LICENSED.
        """
        record = self._license_manager.package_workflow(
            sequence=sequence,
            owner_org_id=owner_org_id,
            license_type=license_type,
            terms=terms,
        )
        self._audit("LAM_WORKFLOW_LICENSED", {
            "license_id": record.license_id,
            "sequence_id": sequence.sequence_id,
            "owner_org_id": owner_org_id,
        })
        return record

    def find_matching_workflows(
        self,
        org_profile: Dict[str, Any],
        top_n: int = 5,
    ) -> List[WorkflowMatch]:
        """Discover complementary workflows from the marketplace.

        Emits LAM_WORKFLOW_MATCHED for each recommendation batch.
        """
        matches = self._matchmaker.find_matches(org_profile, top_n=top_n)
        self._audit("LAM_WORKFLOW_MATCHED", {
            "org_id": self._org_id,
            "match_count": len(matches),
        })
        return matches

    def execute_agreed_plan(
        self,
        agreement: AgreementResult,
    ) -> ExecutionResult:
        """Execute the approved plan from an agreement.

        Safety invariants enforced:
        - Only INSTANT or NEGOTIATED agreements are executed.
        - ESCALATED agreements require human sign-off (returns PENDING).
        - REJECTED agreements are never executed.
        - Full audit trail recorded.

        Emits LAM_EXECUTION_COMPLETED.
        """
        execution_id = uuid.uuid4().hex[:16]

        if agreement.agreement_type == AgreementType.REJECTED:
            return ExecutionResult(
                execution_id=execution_id,
                agreement_id=agreement.agreement_id,
                status=ExecutionStatus.FAILED,
                error_message="agreement was rejected; execution not permitted",
            )

        if agreement.agreement_type == AgreementType.ESCALATED:
            return ExecutionResult(
                execution_id=execution_id,
                agreement_id=agreement.agreement_id,
                status=ExecutionStatus.PENDING,
                error_message="awaiting human escalation sign-off",
            )

        if agreement.approved_sequence is None:
            return ExecutionResult(
                execution_id=execution_id,
                agreement_id=agreement.agreement_id,
                status=ExecutionStatus.FAILED,
                error_message="no approved sequence attached to agreement",
            )

        # Execute via WorkflowDAGEngine if available
        result = self._run_sequence(execution_id, agreement)
        self._audit("LAM_EXECUTION_COMPLETED", {
            "execution_id": execution_id,
            "agreement_id": agreement.agreement_id,
            "status": result.status,
        })
        return result

    # ------------------------------------------------------------------
    # Orchestrator access
    # ------------------------------------------------------------------

    def set_org_budget(self, budget: float) -> None:
        """Set the overall org budget for the orchestrator."""
        self._orchestrator.set_department_budget(self._org_id, budget)

    def get_orchestrator(self) -> OrgChartOrchestrator:
        """Return the underlying OrgChartOrchestrator."""
        return self._orchestrator

    def get_agreement_protocol(self) -> ActionAgreementProtocol:
        """Return the underlying ActionAgreementProtocol."""
        return self._agreement_protocol

    def get_license_manager(self) -> WorkflowLicenseManager:
        """Return the underlying WorkflowLicenseManager."""
        return self._license_manager

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a copy of the internal audit log."""
        with self._lock:
            return list(self._audit_log)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_sequence(
        self,
        execution_id: str,
        agreement: AgreementResult,
    ) -> ExecutionResult:
        """Execute each primitive in the approved sequence in DAG order."""
        sequence = agreement.approved_sequence
        if sequence is None:
            raise ValueError("approved_sequence must not be None")

        completed: List[str] = []
        audit_entries: List[Dict[str, Any]] = []

        try:
            ordered = self._topological_order(sequence)
        except Exception as exc:
            logger.error("DAG topological sort failed: %s", exc)
            return ExecutionResult(
                execution_id=execution_id,
                agreement_id=agreement.agreement_id,
                status=ExecutionStatus.FAILED,
                error_message=f"DAG sort failed: {exc}",
            )

        for action_id in ordered:
            primitive = self._find_primitive(sequence, action_id)
            if primitive is None:
                continue
            entry = self._execute_primitive(primitive, agreement)
            audit_entries.append(entry)
            if entry.get("status") == "failed":
                return ExecutionResult(
                    execution_id=execution_id,
                    agreement_id=agreement.agreement_id,
                    status=ExecutionStatus.FAILED,
                    completed_actions=completed,
                    failed_action=action_id,
                    error_message=entry.get("error"),
                    audit_entries=audit_entries,
                    completed_at=datetime.now(timezone.utc),
                )
            completed.append(action_id)

        return ExecutionResult(
            execution_id=execution_id,
            agreement_id=agreement.agreement_id,
            status=ExecutionStatus.COMPLETED,
            completed_actions=completed,
            audit_entries=audit_entries,
            completed_at=datetime.now(timezone.utc),
        )

    def _topological_order(self, sequence: ActionSequence) -> List[str]:
        """Return action_ids in topological execution order."""
        dag = sequence.dag
        in_degree: Dict[str, int] = {aid: 0 for aid in dag}
        for deps in dag.values():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0)

        # Kahn's algorithm
        queue = [aid for aid, deg in in_degree.items() if deg == 0]
        result: List[str] = []
        visited: set = set()

        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            result.append(node)
            for aid, deps in dag.items():
                if node in deps and aid not in visited:
                    remaining = [d for d in deps if d not in visited]
                    if not remaining:
                        queue.append(aid)

        return result

    def _find_primitive(
        self,
        sequence: ActionSequence,
        action_id: str,
    ) -> Optional[ActionPrimitive]:
        """Find a primitive by action_id within a sequence."""
        for p in sequence.primitives:
            if p.action_id == action_id:
                return p
        return None

    def _execute_primitive(
        self,
        primitive: ActionPrimitive,
        agreement: AgreementResult,
    ) -> Dict[str, Any]:
        """Execute a single primitive, delegating to WorkflowDAGEngine if set."""
        entry: Dict[str, Any] = {
            "action_id": primitive.action_id,
            "action_type": primitive.action_type,
            "domain": primitive.domain,
            "agreement_id": agreement.agreement_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }

        if self._workflow_dag_engine is not None:
            try:
                self._workflow_dag_engine.execute_step(
                    step_id=primitive.action_id,
                    action=primitive.action_type,
                    parameters=primitive.parameters,
                )
            except Exception as exc:
                logger.error("WorkflowDAGEngine step failed: %s", exc)
                entry["status"] = "failed"
                entry["error"] = str(exc)

        return entry

    def _audit(self, event: str, payload: Dict[str, Any]) -> None:
        """Append an event to the internal audit log."""
        entry = {
            "event": event,
            "payload": payload,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_ENTRIES)
