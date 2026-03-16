"""
Production Assistant Engine for Murphy System.

Design Label: PROD-001 — Production Assistant
Owner: Platform Engineering / Operations
Dependencies:
  - ProductionOutputCalibrator (CAL-001) — QC / dimension scoring
  - strategic.murphy_confidence.gates.SafetyGate — blocking confidence gates
  - compliance_engine.ComplianceEngine — regulatory checks
  - compliance_as_code_engine.ComplianceAsCodeEngine — compliance-as-code
  - thread_safe_operations.capped_append — bounded collections

Mirrors the onboarding assistant pattern (AgenticOnboardingEngine /
OnboardingAutomationEngine) but focused on production work.

Flow:
  1. Submit a ProductionProposal with regulatory_location, regulatory_industry,
     regulatory_functions, deliverable_spec, hitl_requirements, required_gates.
  2. validate_proposal() checks regulatory completeness AND confidence ≥ 0.99.
  3. Create a ProductionWorkOrder linked to an approved proposal.
  4. validate_work_order() matches the actual deliverable against the proposal
     at ≥ 0.99 confidence, runs dimension scoring via ProductionOutputCalibrator.
  5. Manage profile lifecycle: created → in_review → approved →
     in_progress → delivered → verified.

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock.
  - Non-destructive: profiles transition forward only; no deletion.
  - Bounded collections via capped_append (CWE-770).
  - Input validated before processing (CWE-20).
  - Collection hard caps prevent memory exhaustion (CWE-400).
  - Raw emails / PII never written to log records.
  - Error messages sanitised before logging (CWE-209).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

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
# Confidence threshold                                                PROD-001
# ---------------------------------------------------------------------------

PRODUCTION_CONFIDENCE_THRESHOLD: float = 0.99

# ---------------------------------------------------------------------------
# Input-validation constants                                         [CWE-20]
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_LOCATION_RE = re.compile(r"^[a-zA-Z0-9 ,.\-_/]{1,300}$")
_INDUSTRY_RE = re.compile(r"^[a-zA-Z0-9 ,.\-_/]{1,200}$")
_MAX_FUNCTIONS = 50
_MAX_FUNCTION_LEN = 200
_MAX_SPEC_LEN = 10_000
_MAX_GATES = 20
_MAX_GATE_LEN = 100
_MAX_CERTIFICATION_LEN = 300
_MAX_CERTS_PER_REQ = 20
_MAX_EXPERIENCE_LEN = 500
_MAX_ACCOUNTABILITY_LEN = 500
_MAX_DELIVERABLE_LEN = 50_000
_MAX_NOTES_LEN = 2_000

# Collection hard caps                                               [CWE-400]
_MAX_PROFILES = 10_000
_MAX_PROPOSALS = 10_000
_MAX_WORK_ORDERS = 10_000
_MAX_AUDIT_LOG = 50_000

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ProductionLifecycle(str, Enum):
    """Lifecycle states for a ProductionProfile."""
    CREATED     = "created"
    IN_REVIEW   = "in_review"
    APPROVED    = "approved"
    IN_PROGRESS = "in_progress"
    DELIVERED   = "delivered"
    VERIFIED    = "verified"
    REJECTED    = "rejected"

class ProposalStatus(str, Enum):
    """Validation status of a ProductionProposal."""
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class WorkOrderStatus(str, Enum):
    """Validation status of a ProductionWorkOrder."""
    PENDING   = "pending"
    VALIDATED = "validated"
    FAILED    = "failed"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class HITLGateRequirement:
    """Human-in-the-loop gate requirement attached to a proposal.

    All fields are optional; omit fields that are not applicable.
    """
    requirement_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    # One or more professional certifications required for the workers
    certifications_required: List[str] = field(default_factory=list)
    # Business or professional licences required
    licenses_required: List[str] = field(default_factory=list)
    # Minimum / type of experience (free text, e.g. "5+ years structural eng.")
    experience_criteria: str = ""
    # Discipline (trade / profession, e.g. "Civil Engineering")
    discipline: str = ""
    # Accountability framework for the discipline
    accountability_framework: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "certifications_required": list(self.certifications_required),
            "licenses_required": list(self.licenses_required),
            "experience_criteria": self.experience_criteria,
            "discipline": self.discipline,
            "accountability_framework": self.accountability_framework,
        }


@dataclass
class ProductionProposal:
    """A production proposal that must pass 99% confidence gating.

    Regulatory fields (location, industry, functions) are mandatory.
    The deliverable_spec describes the expected output to be matched.
    """
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    # Regulatory fields — all three are required for a valid proposal
    regulatory_location: str = ""      # e.g. "US/California", "EU/Germany"
    regulatory_industry: str = ""      # e.g. "construction", "healthcare"
    regulatory_functions: List[str] = field(default_factory=list)  # regulatory activities
    # Deliverable specification — describes the expected output
    deliverable_spec: str = ""
    # HITL gate requirements
    hitl_requirements: List[HITLGateRequirement] = field(default_factory=list)
    # Gate IDs that must pass (from murphy_confidence.gates or compliance_engine)
    required_gates: List[str] = field(default_factory=list)
    # Metadata
    title: str = ""
    notes: str = ""
    submitted_by: str = ""
    status: ProposalStatus = ProposalStatus.PENDING
    confidence_score: float = 0.0
    rejection_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "regulatory_location": self.regulatory_location,
            "regulatory_industry": self.regulatory_industry,
            "regulatory_functions": list(self.regulatory_functions),
            "deliverable_spec": self.deliverable_spec,
            "hitl_requirements": [h.to_dict() for h in self.hitl_requirements],
            "required_gates": list(self.required_gates),
            "title": self.title,
            "notes": self.notes,
            "submitted_by": self.submitted_by,
            "status": self.status.value,
            "confidence_score": self.confidence_score,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ProductionWorkOrder:
    """Links an approved proposal to actual deliverable content.

    The deliverable content is matched against the proposal's deliverable_spec
    at ≥ PRODUCTION_CONFIDENCE_THRESHOLD.
    """
    work_order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    proposal_id: str = ""
    # Actual deliverable content to be validated
    actual_deliverable: str = ""
    # Metadata
    assigned_to: str = ""
    status: WorkOrderStatus = WorkOrderStatus.PENDING
    confidence_score: float = 0.0
    failure_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "proposal_id": self.proposal_id,
            "assigned_to": self.assigned_to,
            "status": self.status.value,
            "confidence_score": self.confidence_score,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at,
            "validated_at": self.validated_at,
        }


@dataclass
class DeliverableMatch:
    """Result of matching a deliverable against a proposal's spec at 99%."""
    match_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    proposal_id: str = ""
    work_order_id: str = ""
    confidence_score: float = 0.0
    passed: bool = False
    # Dimension scores from ProductionOutputCalibrator
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    matched_elements: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)
    notes: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_id": self.match_id,
            "proposal_id": self.proposal_id,
            "work_order_id": self.work_order_id,
            "confidence_score": self.confidence_score,
            "passed": self.passed,
            "dimension_scores": dict(self.dimension_scores),
            "matched_elements": list(self.matched_elements),
            "missing_elements": list(self.missing_elements),
            "notes": self.notes,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class ProductionProfile:
    """Full lifecycle state for a single production engagement."""
    profile_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    proposal_id: str = ""
    work_order_id: str = ""
    lifecycle: ProductionLifecycle = ProductionLifecycle.CREATED
    deliverable_match: Optional[DeliverableMatch] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "proposal_id": self.proposal_id,
            "work_order_id": self.work_order_id,
            "lifecycle": self.lifecycle.value,
            "deliverable_match": (
                self.deliverable_match.to_dict() if self.deliverable_match else None
            ),
            "history": list(self.history),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of a proposal or work-order validation pass."""
    passed: bool = False
    confidence_score: float = 0.0
    gate_results: Dict[str, bool] = field(default_factory=dict)
    regulatory_ok: bool = False
    deliverable_ok: bool = False
    hitl_ok: bool = False
    failure_reasons: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "confidence_score": self.confidence_score,
            "gate_results": dict(self.gate_results),
            "regulatory_ok": self.regulatory_ok,
            "deliverable_ok": self.deliverable_ok,
            "hitl_ok": self.hitl_ok,
            "failure_reasons": list(self.failure_reasons),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    """Return a safe, opaque error token; never leak raw exception text."""
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Core Engine                                                        PROD-001
# ---------------------------------------------------------------------------

class ProductionAssistantEngine:
    """
    Production Assistant Engine (PROD-001).

    Mirrors the onboarding assistant lifecycle pattern but is focused
    on validated production work:

      - Every proposal must pass regulatory completeness and 99% confidence.
      - Every work order must match the proposal's deliverable_spec at 99%.
      - HITL gate requirements on proposals are validated before approval.
      - Dimension scoring is delegated to ProductionOutputCalibrator.
      - Compliance checks are delegated to ComplianceEngine.
      - Safety gates use SafetyGate from strategic.murphy_confidence.gates.

    Thread-safety: all mutable state is guarded by a single threading.Lock.
    """

    def __init__(
        self,
        calibrator: Any = None,
        compliance_engine: Any = None,
        compliance_as_code_engine: Any = None,
    ) -> None:
        self._lock = threading.Lock()

        # Inject dependencies or use lazy stubs
        self._calibrator = calibrator
        self._compliance = compliance_engine
        self._cce = compliance_as_code_engine

        # In-memory registries
        self._proposals: Dict[str, ProductionProposal] = {}
        self._work_orders: Dict[str, ProductionWorkOrder] = {}
        self._profiles: Dict[str, ProductionProfile] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Input validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_id(value: str, name: str) -> str:
        """Validate an ID field; raises ValueError on bad input."""
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        clean = value.strip()
        if not _ID_RE.match(clean):
            raise ValueError(f"{name} contains invalid characters or exceeds length limit")
        return clean

    @staticmethod
    def _validate_location(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("regulatory_location must be a string")
        clean = value.strip()
        if not clean:
            raise ValueError("regulatory_location must not be empty")
        if not _LOCATION_RE.match(clean):
            raise ValueError("regulatory_location contains invalid characters")
        return clean

    @staticmethod
    def _validate_industry(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("regulatory_industry must be a string")
        clean = value.strip()
        if not clean:
            raise ValueError("regulatory_industry must not be empty")
        if not _INDUSTRY_RE.match(clean):
            raise ValueError("regulatory_industry contains invalid characters")
        return clean

    @staticmethod
    def _validate_functions(funcs: List[str]) -> List[str]:
        if not isinstance(funcs, list):
            raise ValueError("regulatory_functions must be a list")
        if len(funcs) == 0:
            raise ValueError("regulatory_functions must not be empty")
        if len(funcs) > _MAX_FUNCTIONS:
            raise ValueError(
                f"regulatory_functions exceeds maximum of {_MAX_FUNCTIONS} entries"
            )
        cleaned: List[str] = []
        for f in funcs:
            if not isinstance(f, str):
                raise ValueError("each regulatory_function must be a string")
            c = f.strip()
            if len(c) > _MAX_FUNCTION_LEN:
                raise ValueError(
                    f"regulatory_function entry exceeds {_MAX_FUNCTION_LEN} chars"
                )
            cleaned.append(c)
        return cleaned

    @staticmethod
    def _validate_gates(gates: List[str]) -> List[str]:
        if not isinstance(gates, list):
            raise ValueError("required_gates must be a list")
        if len(gates) > _MAX_GATES:
            raise ValueError(f"required_gates exceeds maximum of {_MAX_GATES} entries")
        cleaned: List[str] = []
        for g in gates:
            if not isinstance(g, str):
                raise ValueError("each gate must be a string")
            c = g.strip()
            if len(c) > _MAX_GATE_LEN:
                raise ValueError(f"gate ID exceeds {_MAX_GATE_LEN} chars")
            cleaned.append(c)
        return cleaned

    @staticmethod
    def _validate_hitl(hitl_list: List[HITLGateRequirement]) -> List[HITLGateRequirement]:
        if not isinstance(hitl_list, list):
            raise ValueError("hitl_requirements must be a list")
        for h in hitl_list:
            if not isinstance(h, HITLGateRequirement):
                raise ValueError("each HITL requirement must be HITLGateRequirement")
            if len(h.certifications_required) > _MAX_CERTS_PER_REQ:
                raise ValueError(
                    f"certifications_required exceeds {_MAX_CERTS_PER_REQ} entries"
                )
            for cert in h.certifications_required:
                if len(cert) > _MAX_CERTIFICATION_LEN:
                    raise ValueError(
                        f"certification entry exceeds {_MAX_CERTIFICATION_LEN} chars"
                    )
            if len(h.experience_criteria) > _MAX_EXPERIENCE_LEN:
                raise ValueError(
                    f"experience_criteria exceeds {_MAX_EXPERIENCE_LEN} chars"
                )
            if len(h.accountability_framework) > _MAX_ACCOUNTABILITY_LEN:
                raise ValueError(
                    f"accountability_framework exceeds {_MAX_ACCOUNTABILITY_LEN} chars"
                )
        return hitl_list

    # ------------------------------------------------------------------
    # Proposal management
    # ------------------------------------------------------------------

    def submit_proposal(self, proposal: ProductionProposal) -> str:
        """Register a new proposal and return its proposal_id.

        Validates inputs; does NOT run confidence gating yet (call
        validate_proposal() for full gating).
        """
        try:
            proposal.regulatory_location = self._validate_location(
                proposal.regulatory_location
            )
            proposal.regulatory_industry = self._validate_industry(
                proposal.regulatory_industry
            )
            proposal.regulatory_functions = self._validate_functions(
                proposal.regulatory_functions
            )
            proposal.required_gates = self._validate_gates(proposal.required_gates)
            self._validate_hitl(proposal.hitl_requirements)

            if not isinstance(proposal.deliverable_spec, str):
                raise ValueError("deliverable_spec must be a string")
            if len(proposal.deliverable_spec) > _MAX_SPEC_LEN:
                raise ValueError(
                    f"deliverable_spec exceeds {_MAX_SPEC_LEN} chars"
                )
            if len(proposal.notes) > _MAX_NOTES_LEN:
                raise ValueError(f"notes exceeds {_MAX_NOTES_LEN} chars")

        except ValueError as exc:
            logger.warning("submit_proposal validation failed: %s", exc)
            raise

        with self._lock:
            if len(self._proposals) >= _MAX_PROPOSALS:
                raise RuntimeError("Proposal registry is at capacity")
            pid = proposal.proposal_id
            self._proposals[pid] = proposal
            self._record_audit("submit_proposal", {"proposal_id": pid})

        logger.info("Proposal submitted: id=%s", pid)
        return pid

    def validate_proposal(self, proposal_id: str) -> ValidationResult:
        """Run full 99%-confidence gating on the proposal.

        Checks (in order):
          1. Regulatory completeness (location + industry + functions)
          2. Deliverable spec completeness
          3. HITL gate requirements integrity
          4. Compliance engine checks
          5. SafetyGate evaluation at PRODUCTION_CONFIDENCE_THRESHOLD

        Returns a ValidationResult; updates proposal.status.
        """
        pid = self._validate_id(proposal_id, "proposal_id")
        result = ValidationResult()

        with self._lock:
            proposal = self._proposals.get(pid)
        if proposal is None:
            result.failure_reasons.append(f"Proposal {pid} not found")
            return result

        # 1. Regulatory completeness
        reg_ok = bool(
            proposal.regulatory_location
            and proposal.regulatory_industry
            and proposal.regulatory_functions
        )
        result.regulatory_ok = reg_ok
        if not reg_ok:
            result.failure_reasons.append(
                "Missing regulatory fields (location, industry, or functions)"
            )

        # 2. Deliverable spec
        spec_ok = bool(proposal.deliverable_spec.strip())
        result.deliverable_ok = spec_ok
        if not spec_ok:
            result.failure_reasons.append("deliverable_spec is empty")

        # 3. HITL integrity — each requirement must have at least discipline
        #    OR certifications
        hitl_ok = True
        for h in proposal.hitl_requirements:
            if not h.discipline and not h.certifications_required:
                hitl_ok = False
                result.failure_reasons.append(
                    f"HITL requirement {h.requirement_id} has no discipline or certifications"
                )
        result.hitl_ok = hitl_ok

        # 4. Compliance checks (best-effort; non-blocking if engine unavailable)
        compliance_ok = True
        if self._compliance is not None:
            try:
                comp_result = self._compliance.check(
                    location=proposal.regulatory_location,
                    industry=proposal.regulatory_industry,
                    functions=proposal.regulatory_functions,
                )
                if not comp_result.get("compliant", True):
                    compliance_ok = False
                    result.failure_reasons.append(
                        "Compliance engine: " + comp_result.get("reason", "non-compliant")
                    )
            except Exception as exc:
                logger.warning("ComplianceEngine check failed: %s", _sanitize_error(exc))

        # 5. Confidence score calculation
        #    Score is a weighted average of sub-checks; all must clear 0.99
        score_components: List[float] = []
        score_components.append(1.0 if reg_ok else 0.0)
        score_components.append(1.0 if spec_ok else 0.0)
        score_components.append(1.0 if hitl_ok else 0.0)
        score_components.append(1.0 if compliance_ok else 0.0)

        # Calibrator dimension scoring on deliverable spec (if calibrator available)
        calibrator_score = 0.0
        if self._calibrator is not None and spec_ok:
            try:
                calibrator_score = self._get_calibrator_spec_score(proposal)
            except Exception as exc:
                logger.warning(
                    "Calibrator scoring failed: %s", _sanitize_error(exc)
                )
                calibrator_score = 0.0
        else:
            # Without calibrator, apply a conservative heuristic
            calibrator_score = self._heuristic_spec_score(proposal.deliverable_spec)
        score_components.append(calibrator_score)

        confidence = sum(score_components) / len(score_components) if score_components else 0.0
        result.confidence_score = round(confidence, 6)

        # 6. SafetyGate evaluation
        gate_results: Dict[str, bool] = {}
        try:
            from strategic.murphy_confidence.gates import SafetyGate
            from strategic.murphy_confidence.types import (
                ConfidenceResult as ConfRes,
            )
            from strategic.murphy_confidence.types import (
                GateAction,
                GateType,
                Phase,
            )
            conf_result = ConfRes(
                score=confidence,
                phase=Phase.EXECUTE,
                action=(
                    GateAction.PROCEED_AUTOMATICALLY
                    if confidence >= PRODUCTION_CONFIDENCE_THRESHOLD
                    else GateAction.BLOCK_EXECUTION
                ),
                allowed=confidence >= PRODUCTION_CONFIDENCE_THRESHOLD,
                rationale="production_assistant.validate_proposal",
                weights={},
            )
            for gate_id in (proposal.required_gates or ["compliance_gate", "hitl_gate"]):
                g_type = (
                    GateType.HITL if "hitl" in gate_id.lower()
                    else GateType.COMPLIANCE
                )
                gate = SafetyGate(
                    gate_id=gate_id,
                    gate_type=g_type,
                    threshold=PRODUCTION_CONFIDENCE_THRESHOLD,
                )
                g_result = gate.evaluate(conf_result)
                gate_results[gate_id] = g_result.passed
                if not g_result.passed:
                    result.failure_reasons.append(g_result.message)
        except ImportError:
            # SafetyGate not available in this deployment path; fall back
            for gate_id in (proposal.required_gates or []):
                gate_results[gate_id] = confidence >= PRODUCTION_CONFIDENCE_THRESHOLD

        result.gate_results = gate_results

        # Final pass/fail
        all_gates_passed = all(gate_results.values()) if gate_results else True
        result.passed = (
            reg_ok
            and spec_ok
            and hitl_ok
            and compliance_ok
            and confidence >= PRODUCTION_CONFIDENCE_THRESHOLD
            and all_gates_passed
        )

        # Persist decision
        with self._lock:
            proposal.status = (
                ProposalStatus.APPROVED if result.passed else ProposalStatus.REJECTED
            )
            proposal.confidence_score = result.confidence_score
            if not result.passed:
                proposal.rejection_reason = "; ".join(result.failure_reasons[:5])
            proposal.updated_at = _ts()
            self._record_audit(
                "validate_proposal",
                {
                    "proposal_id": pid,
                    "passed": result.passed,
                    "confidence": result.confidence_score,
                },
            )

        logger.info(
            "Proposal %s validation: passed=%s confidence=%.4f",
            pid,
            result.passed,
            result.confidence_score,
        )
        return result

    # ------------------------------------------------------------------
    # Work order management
    # ------------------------------------------------------------------

    def submit_work_order(self, work_order: ProductionWorkOrder) -> str:
        """Register a new work order linked to an approved proposal.

        Raises ValueError if the proposal does not exist or is not approved.
        """
        pid = self._validate_id(work_order.proposal_id, "proposal_id")

        if not isinstance(work_order.actual_deliverable, str):
            raise ValueError("actual_deliverable must be a string")
        if len(work_order.actual_deliverable) > _MAX_DELIVERABLE_LEN:
            raise ValueError(
                f"actual_deliverable exceeds {_MAX_DELIVERABLE_LEN} chars"
            )

        with self._lock:
            proposal = self._proposals.get(pid)
            if proposal is None:
                raise ValueError(f"Proposal {pid} not found")
            if proposal.status != ProposalStatus.APPROVED:
                raise ValueError(
                    f"Proposal {pid} is not approved (status={proposal.status.value})"
                )
            if len(self._work_orders) >= _MAX_WORK_ORDERS:
                raise RuntimeError("Work order registry is at capacity")
            wid = work_order.work_order_id
            self._work_orders[wid] = work_order
            self._record_audit("submit_work_order", {"work_order_id": wid, "proposal_id": pid})

        logger.info("Work order submitted: id=%s proposal=%s", wid, pid)
        return wid

    def validate_work_order(self, work_order_id: str) -> DeliverableMatch:
        """Match the work order's actual_deliverable against the proposal spec at 99%.

        Returns a DeliverableMatch with confidence_score and passed flag.
        Updates work_order.status and creates/updates the linked ProductionProfile.
        """
        wid = self._validate_id(work_order_id, "work_order_id")

        with self._lock:
            work_order = self._work_orders.get(wid)
        if work_order is None:
            return DeliverableMatch(
                work_order_id=wid,
                notes=f"Work order {wid} not found",
            )

        with self._lock:
            proposal = self._proposals.get(work_order.proposal_id)
        if proposal is None:
            return DeliverableMatch(
                work_order_id=wid,
                proposal_id=work_order.proposal_id,
                notes="Linked proposal not found",
            )

        # Perform deliverable matching
        match = self._match_deliverable(proposal, work_order)

        # Update work order status
        with self._lock:
            work_order.status = (
                WorkOrderStatus.VALIDATED if match.passed else WorkOrderStatus.FAILED
            )
            work_order.confidence_score = match.confidence_score
            work_order.failure_reason = (
                "; ".join(match.missing_elements[:5]) if not match.passed else ""
            )
            work_order.validated_at = _ts()

        # Update or create production profile
        self._update_profile_for_work_order(work_order, match)

        with self._lock:
            self._record_audit(
                "validate_work_order",
                {
                    "work_order_id": wid,
                    "passed": match.passed,
                    "confidence": match.confidence_score,
                },
            )

        logger.info(
            "Work order %s validation: passed=%s confidence=%.4f",
            wid,
            match.passed,
            match.confidence_score,
        )
        return match

    # ------------------------------------------------------------------
    # Profile lifecycle
    # ------------------------------------------------------------------

    def get_profile(self, profile_id: str) -> Optional[ProductionProfile]:
        """Return a ProductionProfile by ID, or None if not found."""
        pid = self._validate_id(profile_id, "profile_id")
        with self._lock:
            return self._profiles.get(pid)

    def advance_lifecycle(
        self,
        profile_id: str,
        new_state: ProductionLifecycle,
        notes: str = "",
    ) -> bool:
        """Advance a profile's lifecycle state.

        Only forward transitions are permitted (except REJECTED).
        Returns True on success, False if the transition is not permitted.
        """
        pid = self._validate_id(profile_id, "profile_id")
        if len(notes) > _MAX_NOTES_LEN:
            notes = notes[:_MAX_NOTES_LEN]

        _FORWARD_ORDER = [
            ProductionLifecycle.CREATED,
            ProductionLifecycle.IN_REVIEW,
            ProductionLifecycle.APPROVED,
            ProductionLifecycle.IN_PROGRESS,
            ProductionLifecycle.DELIVERED,
            ProductionLifecycle.VERIFIED,
        ]

        with self._lock:
            profile = self._profiles.get(pid)
            if profile is None:
                return False

            current = profile.lifecycle
            if new_state == ProductionLifecycle.REJECTED:
                profile.lifecycle = new_state
                profile.updated_at = _ts()
                capped_append(
                    profile.history,
                    {"from": current.value, "to": new_state.value, "notes": notes, "at": _ts()},
                    max_size=200,
                )
                self._record_audit(
                    "advance_lifecycle",
                    {"profile_id": pid, "from": current.value, "to": new_state.value},
                )
                return True

            if current == ProductionLifecycle.VERIFIED:
                return False

            try:
                cur_idx = _FORWARD_ORDER.index(current)
                new_idx = _FORWARD_ORDER.index(new_state)
            except ValueError:
                return False

            if new_idx <= cur_idx:
                return False

            profile.lifecycle = new_state
            profile.updated_at = _ts()
            capped_append(
                profile.history,
                {"from": current.value, "to": new_state.value, "notes": notes, "at": _ts()},
                max_size=200,
            )
            self._record_audit(
                "advance_lifecycle",
                {"profile_id": pid, "from": current.value, "to": new_state.value},
            )
            return True

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Return a summary list of all production profiles."""
        with self._lock:
            return [p.to_dict() for p in self._profiles.values()]

    def list_proposals(self) -> List[Dict[str, Any]]:
        """Return a summary list of all proposals."""
        with self._lock:
            return [p.to_dict() for p in self._proposals.values()]

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent audit log entries."""
        limit = min(max(1, limit), 1000)
        with self._lock:
            return list(self._audit_log[-limit:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_deliverable(
        self,
        proposal: ProductionProposal,
        work_order: ProductionWorkOrder,
    ) -> DeliverableMatch:
        """Compare actual_deliverable against proposal.deliverable_spec at 99%."""
        match = DeliverableMatch(
            proposal_id=proposal.proposal_id,
            work_order_id=work_order.work_order_id,
        )

        spec = proposal.deliverable_spec.lower()
        actual = work_order.actual_deliverable.lower()

        if not spec or not actual:
            match.notes = "Empty spec or deliverable"
            return match

        # Extract significant terms from the spec (simple token approach)
        spec_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", spec))
        actual_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", actual))

        # Filter out very common stop words
        _STOP = {
            "the", "and", "for", "are", "that", "this", "with",
            "has", "its", "not", "from", "also", "will", "been",
        }
        spec_terms = spec_tokens - _STOP
        actual_terms = actual_tokens - _STOP

        matched: List[str] = sorted(spec_terms & actual_terms)
        missing: List[str] = sorted(spec_terms - actual_terms)

        # Dimension scoring via calibrator (if available)
        dimension_scores: Dict[str, float] = {}
        if self._calibrator is not None:
            try:
                dim_scores = self._calibrator.score_output()
                for ds in dim_scores:
                    dimension_scores[ds.dimension.value] = ds.score
            except Exception as exc:
                logger.debug("Calibrator dimension scoring: %s", _sanitize_error(exc))

        if not dimension_scores:
            dimension_scores = self._heuristic_dimension_scores(actual)

        dim_avg = (
            sum(dimension_scores.values()) / len(dimension_scores)
            if dimension_scores
            else 0.0
        )

        # Coverage ratio: fraction of spec terms present in actual
        coverage = len(matched) / len(spec_terms) if spec_terms else 1.0

        # Regulatory function coverage
        reg_func_coverage = self._check_regulatory_functions(
            proposal.regulatory_functions, actual
        )

        # Composite confidence = weighted average
        confidence = (
            0.50 * coverage
            + 0.30 * reg_func_coverage
            + 0.20 * dim_avg
        )
        confidence = round(min(1.0, max(0.0, confidence)), 6)

        match.confidence_score = confidence
        match.passed = confidence >= PRODUCTION_CONFIDENCE_THRESHOLD
        match.dimension_scores = dimension_scores
        match.matched_elements = matched[:100]
        match.missing_elements = missing[:100]
        match.notes = (
            f"Coverage={coverage:.3f} reg_func={reg_func_coverage:.3f} "
            f"dim_avg={dim_avg:.3f}"
        )

        return match

    @staticmethod
    def _check_regulatory_functions(functions: List[str], actual_lower: str) -> float:
        """Check what fraction of required regulatory functions appear in the deliverable."""
        if not functions:
            return 1.0
        hits = sum(
            1 for f in functions if f.lower() in actual_lower
        )
        return hits / len(functions)

    @staticmethod
    def _heuristic_spec_score(spec: str) -> float:
        """Simple heuristic: score spec completeness by length and structure."""
        if not spec or not spec.strip():
            return 0.0
        words = len(spec.split())
        # Consider 50+ word specs well-formed for heuristic purposes
        raw = min(1.0, words / 50.0)
        # Has structure markers (numbered list, colons, headers)?
        structure_bonus = 0.1 if any(c in spec for c in [":", "\n", "1.", "-"]) else 0.0
        return min(1.0, raw + structure_bonus)

    @staticmethod
    def _heuristic_dimension_scores(content: str) -> Dict[str, float]:
        """Return heuristic dimension scores when calibrator is unavailable."""
        if not content:
            return {dim: 0.0 for dim in [
                "clarity", "completeness", "structure", "accuracy",
                "consistency", "professionalism", "efficiency",
                "maintainability", "security", "usability",
            ]}
        words = len(content.split())
        base = min(1.0, words / 200.0)
        has_structure = 0.15 if any(c in content for c in ["\n", ":", "•", "-", "1."]) else 0.0
        return {
            "clarity":        min(1.0, base + has_structure),
            "completeness":   min(1.0, base),
            "structure":      min(1.0, base + has_structure),
            "accuracy":       min(1.0, base),
            "consistency":    min(1.0, base),
            "professionalism": min(1.0, base + has_structure),
            "efficiency":     min(1.0, base),
            "maintainability": min(1.0, base),
            "security":       min(1.0, base * 0.8),
            "usability":      min(1.0, base + has_structure),
        }

    def _get_calibrator_spec_score(self, proposal: ProductionProposal) -> float:
        """Use the calibrator to score the deliverable spec content."""
        try:
            from production_output_calibrator import (
                ProductionOutput,
                ProposalRequirement,
            )
            output = ProductionOutput(content=proposal.deliverable_spec)
            self._calibrator.register_output(output)
            reqs = [
                ProposalRequirement(description=f)
                for f in proposal.regulatory_functions[:10]
            ]
            self._calibrator.register_proposal_request(reqs)
            dim_scores = self._calibrator.score_output()
            if not dim_scores:
                return 0.0
            return sum(ds.score for ds in dim_scores) / len(dim_scores)
        except Exception as exc:
            logger.debug("_get_calibrator_spec_score: %s", _sanitize_error(exc))
            return 0.0

    def _update_profile_for_work_order(
        self,
        work_order: ProductionWorkOrder,
        match: DeliverableMatch,
    ) -> None:
        """Create or update the ProductionProfile for this work order."""
        with self._lock:
            # Find existing profile for this proposal
            existing: Optional[ProductionProfile] = None
            for p in self._profiles.values():
                if p.proposal_id == work_order.proposal_id:
                    existing = p
                    break

            if existing is None:
                # Create new profile
                profile = ProductionProfile(
                    proposal_id=work_order.proposal_id,
                    work_order_id=work_order.work_order_id,
                    lifecycle=(
                        ProductionLifecycle.IN_PROGRESS
                        if not match.passed
                        else ProductionLifecycle.DELIVERED
                    ),
                    deliverable_match=match,
                )
                if len(self._profiles) < _MAX_PROFILES:
                    self._profiles[profile.profile_id] = profile
            else:
                existing.work_order_id = work_order.work_order_id
                existing.deliverable_match = match
                if match.passed and existing.lifecycle not in (
                    ProductionLifecycle.VERIFIED,
                    ProductionLifecycle.DELIVERED,
                ):
                    existing.lifecycle = ProductionLifecycle.DELIVERED
                existing.updated_at = _ts()

    def _record_audit(self, action: str, context: Dict[str, Any]) -> None:
        """Append a bounded audit record (must be called while lock is held)."""
        capped_append(
            self._audit_log,
            {"action": action, "context": context, "at": _ts()},
            max_size=_MAX_AUDIT_LOG,
        )
