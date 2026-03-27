"""
Bridge Layer Data Models

Defines all data structures for System A → System B bridging:
- HypothesisArtifact: System A sandbox output (zero execution rights)
- VerificationArtifact: Verification results with provenance
- CompilationResult: System B packet compilation output
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """Verification status for hypotheses"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    REQUIRES_HUMAN = "requires_human"


class BlockingReason(str, Enum):
    """Reasons why hypothesis cannot be compiled to ExecutionPacket"""
    CONFIDENCE_TOO_LOW = "confidence_too_low"
    CONTRADICTIONS_TOO_HIGH = "contradictions_too_high"
    GATES_NOT_SATISFIED = "gates_not_satisfied"
    VERIFICATION_INCOMPLETE = "verification_incomplete"
    ASSUMPTIONS_UNVERIFIED = "assumptions_unverified"
    MISSING_DEPENDENCIES = "missing_dependencies"
    RISK_FLAGS_PRESENT = "risk_flags_present"
    AUTHORITY_INSUFFICIENT = "authority_insufficient"


@dataclass
class HypothesisArtifact:
    """
    System A sandbox output with ZERO execution rights.

    This is a pure hypothesis/plan that CANNOT execute anything.
    It must be evaluated, verified, and gated by System B before
    any ExecutionPacket can be compiled.

    CRITICAL CONSTRAINTS:
    - status: MUST be "sandbox"
    - confidence: MUST be null (computed by System B)
    - execution_rights: MUST be false
    """
    hypothesis_id: str
    plan_summary: str
    assumptions: List[str]  # Explicit assumptions
    dependencies: List[str]  # Data sources, external APIs, etc.
    risk_flags: List[str]  # Self-reported risks
    proposed_actions: List[Dict[str, Any]]  # High-level, NOT executable

    # MANDATORY SANDBOX CONSTRAINTS
    status: Literal["sandbox"] = "sandbox"
    confidence: None = None  # Computed by System B only
    execution_rights: Literal[False] = False

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_system: str = "system_a"
    provenance: Dict[str, Any] = field(default_factory=dict)
    integrity_hash: str = ""

    def __post_init__(self):
        """Enforce sandbox constraints"""
        # CRITICAL: Enforce sandbox status
        if self.status != "sandbox":
            raise ValueError("HypothesisArtifact status MUST be 'sandbox'")

        # CRITICAL: Enforce null confidence
        if self.confidence is not None:
            raise ValueError("HypothesisArtifact confidence MUST be null")

        # CRITICAL: Enforce zero execution rights
        if self.execution_rights is not False:
            raise ValueError("HypothesisArtifact execution_rights MUST be false")

        # Compute integrity hash
        if not self.integrity_hash:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 integrity hash"""
        canonical = json.dumps({
            "hypothesis_id": self.hypothesis_id,
            "plan_summary": self.plan_summary,
            "assumptions": self.assumptions,
            "dependencies": self.dependencies,
            "risk_flags": self.risk_flags,
            "proposed_actions": self.proposed_actions,
            "created_at": self.created_at.isoformat(),
        }, sort_keys=True)

        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify integrity hash matches current state"""
        expected_hash = self._compute_hash()
        return expected_hash == self.integrity_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "plan_summary": self.plan_summary,
            "assumptions": self.assumptions,
            "dependencies": self.dependencies,
            "risk_flags": self.risk_flags,
            "proposed_actions": self.proposed_actions,
            "status": self.status,
            "confidence": self.confidence,
            "execution_rights": self.execution_rights,
            "created_at": self.created_at.isoformat(),
            "source_system": self.source_system,
            "provenance": self.provenance,
            "integrity_hash": self.integrity_hash,
        }


@dataclass
class VerificationRequest:
    """
    Request for verification of hypothesis claims/assumptions.

    Types:
    - deterministic: Mathematical/logical verification
    - external_api: Query external data source
    - human_confirmation: Requires human review
    """
    request_id: str
    hypothesis_id: str
    verification_type: Literal["deterministic", "external_api", "human_confirmation"]
    claim: str
    context: Dict[str, Any]
    priority: Literal["low", "medium", "high", "critical"]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "hypothesis_id": self.hypothesis_id,
            "verification_type": self.verification_type,
            "claim": self.claim,
            "context": self.context,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class VerificationArtifact:
    """
    Verification result with full provenance.

    All verification results become artifacts in the artifact graph
    with complete provenance chain.
    """
    verification_id: str
    request_id: str
    hypothesis_id: str
    status: VerificationStatus
    result: Optional[bool]  # True=verified, False=failed, None=pending
    evidence: Dict[str, Any]  # Supporting evidence
    method: str  # How verification was performed
    verified_by: str  # System or user that performed verification
    timestamp: datetime
    provenance: Dict[str, Any]
    integrity_hash: str

    @staticmethod
    def create(
        request_id: str,
        hypothesis_id: str,
        status: VerificationStatus,
        result: Optional[bool],
        evidence: Dict[str, Any],
        method: str,
        verified_by: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> "VerificationArtifact":
        """Create a new verification artifact"""
        timestamp = datetime.now(timezone.utc)
        verification_id = f"verification_{hypothesis_id}_{timestamp.timestamp()}"

        if provenance is None:
            provenance = {}

        # Compute integrity hash
        canonical = json.dumps({
            "verification_id": verification_id,
            "request_id": request_id,
            "hypothesis_id": hypothesis_id,
            "status": status.value,
            "result": result,
            "evidence": evidence,
            "method": method,
            "verified_by": verified_by,
            "timestamp": timestamp.isoformat(),
            "provenance": provenance,
        }, sort_keys=True)

        integrity_hash = hashlib.sha256(canonical.encode()).hexdigest()

        return VerificationArtifact(
            verification_id=verification_id,
            request_id=request_id,
            hypothesis_id=hypothesis_id,
            status=status,
            result=result,
            evidence=evidence,
            method=method,
            verified_by=verified_by,
            timestamp=timestamp,
            provenance=provenance,
            integrity_hash=integrity_hash,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "request_id": self.request_id,
            "hypothesis_id": self.hypothesis_id,
            "status": self.status.value,
            "result": self.result,
            "evidence": self.evidence,
            "method": self.method,
            "verified_by": self.verified_by,
            "timestamp": self.timestamp.isoformat(),
            "provenance": self.provenance,
            "integrity_hash": self.integrity_hash,
        }


@dataclass
class CompilationResult:
    """
    Result of ExecutionPacket compilation attempt.

    Success: Contains compiled ExecutionPacket
    Failure: Contains blocking reasons and required evidence
    """
    hypothesis_id: str
    success: bool
    execution_packet: Optional[Dict[str, Any]]  # Compiled packet if success
    blocking_reasons: List[BlockingReason]
    confidence: float
    authority_level: str
    gates_satisfied: List[str]
    gates_blocking: List[str]
    verifications_complete: List[str]
    verifications_pending: List[str]
    required_evidence: List[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "success": self.success,
            "execution_packet": self.execution_packet,
            "blocking_reasons": [br.value for br in self.blocking_reasons],
            "confidence": self.confidence,
            "authority_level": self.authority_level,
            "gates_satisfied": self.gates_satisfied,
            "gates_blocking": self.gates_blocking,
            "verifications_complete": self.verifications_complete,
            "verifications_pending": self.verifications_pending,
            "required_evidence": self.required_evidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class IntakeResult:
    """
    Result of hypothesis intake by System B.

    Contains:
    - Extracted claims and assumptions
    - Generated verification requests
    - Gate synthesis proposals
    - Admissible scope decision
    """
    hypothesis_id: str
    admitted: bool
    extracted_claims: List[str]
    extracted_assumptions: List[str]
    verification_requests: List[VerificationRequest]
    gate_proposals: List[str]  # Gate IDs proposed
    confidence_impact: Optional[float]  # Estimated impact on confidence
    admissible_scope: str  # Description of what can be done
    rejection_reasons: List[str]  # If not admitted
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "admitted": self.admitted,
            "extracted_claims": self.extracted_claims,
            "extracted_assumptions": self.extracted_assumptions,
            "verification_requests": [vr.to_dict() for vr in self.verification_requests],
            "gate_proposals": self.gate_proposals,
            "confidence_impact": self.confidence_impact,
            "admissible_scope": self.admissible_scope,
            "rejection_reasons": self.rejection_reasons,
            "timestamp": self.timestamp.isoformat(),
        }
