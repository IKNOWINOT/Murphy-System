"""
Core data models for Org Compiler & Shadow Learning System

All schemas enforce strict safety constraints:
- Proposals are sandbox-only (no execution rights)
- Human authority is immutable
- Escalation paths cannot be removed by agents
- All substitutions require explicit gate satisfaction
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


class AuthorityLevel(Enum):
    """Authority levels for decision-making"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXECUTIVE = "executive"


class ArtifactType(Enum):
    """Types of work artifacts"""
    DOCUMENT = "document"
    CODE = "code"
    DESIGN = "design"
    APPROVAL = "approval"
    REPORT = "report"
    TICKET = "ticket"
    EMAIL = "email"
    MEETING_NOTES = "meeting_notes"


class ProposalStatus(Enum):
    """Status of template proposals"""
    SANDBOX = "sandbox"  # Observation only, no execution
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYED = "deployed"


class GateStatus(Enum):
    """Status of substitution gates"""
    NOT_MET = "not_met"
    PENDING = "pending"
    SATISFIED = "satisfied"
    FAILED = "failed"


@dataclass
class EscalationPath:
    """
    Escalation path definition

    CRITICAL: Escalation paths are IMMUTABLE by agents.
    Only humans can modify escalation paths.
    """
    path_id: str
    from_role: str
    to_role: str
    trigger_conditions: List[str]
    sla_hours: float
    requires_human: bool = True  # Always true by default
    immutable: bool = True  # Cannot be changed by agents

    def __post_init__(self):
        """Enforce immutability"""
        if not self.immutable:
            raise ValueError("EscalationPath.immutable must be True")
        if not self.requires_human:
            raise ValueError("EscalationPath.requires_human must be True")


@dataclass
class ComplianceConstraint:
    """
    Compliance/regulatory constraint

    These constraints are MANDATORY and cannot be bypassed by automation.
    """
    constraint_id: str
    regulation: str  # e.g., "SOX", "HIPAA", "GDPR"
    description: str
    verification_required: bool
    human_signoff_required: bool
    audit_trail_required: bool
    immutable: bool = True

    def __post_init__(self):
        """Enforce compliance immutability"""
        if not self.immutable:
            raise ValueError("ComplianceConstraint.immutable must be True")


@dataclass
class RoleMetrics:
    """Performance metrics and SLA targets for a role"""
    sla_targets: Dict[str, float]  # e.g., {"response_time_hours": 24, "quality_score": 0.95}
    quality_gates: List[str]
    throughput_target: Optional[float] = None
    error_rate_max: Optional[float] = None


@dataclass
class RoleTemplate:
    """
    Role template defining responsibilities, authority, and constraints

    This is the compiled output from org charts, SOPs, and process flows.
    It defines what a role does, what authority it has, and what constraints apply.
    """
    role_id: str
    role_name: str
    responsibilities: List[str]
    decision_authority: AuthorityLevel
    input_artifacts: List[ArtifactType]
    output_artifacts: List[ArtifactType]
    escalation_paths: List[EscalationPath]
    compliance_constraints: List[ComplianceConstraint]
    requires_human_signoff: List[str]  # List of actions requiring human approval
    metrics: RoleMetrics

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"
    source_documents: List[str] = field(default_factory=list)

    # Integrity
    integrity_hash: Optional[str] = None

    def __post_init__(self):
        """Validate and compute integrity hash"""
        # Validate authority is bounded
        if self.decision_authority not in AuthorityLevel:
            raise ValueError(f"Invalid authority level: {self.decision_authority}")

        # Ensure at least one responsibility
        if not self.responsibilities:
            raise ValueError("RoleTemplate must have at least one responsibility")

        # Ensure escalation paths are immutable
        for path in self.escalation_paths:
            if not path.immutable:
                raise ValueError("All escalation paths must be immutable")

        # Ensure compliance constraints are immutable
        for constraint in self.compliance_constraints:
            if not constraint.immutable:
                raise ValueError("All compliance constraints must be immutable")

        # Compute integrity hash
        if self.integrity_hash is None:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of role template"""
        data = {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "responsibilities": sorted(self.responsibilities),
            "decision_authority": self.decision_authority.value,
            "escalation_paths": [p.path_id for p in self.escalation_paths],
            "compliance_constraints": [c.constraint_id for c in self.compliance_constraints],
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify integrity hash matches current state"""
        return self.integrity_hash == self._compute_hash()


@dataclass
class WorkArtifact:
    """
    A work artifact produced or consumed by a role
    """
    artifact_id: str
    artifact_type: ArtifactType
    producer_role: str
    consumer_roles: List[str]
    content_hash: str
    metadata: Dict[str, any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class HandoffEvent:
    """
    A handoff event between roles

    Shadow learning agents observe these to learn workflow patterns.
    """
    event_id: str
    from_role: str
    to_role: str
    artifact: WorkArtifact
    timestamp: datetime
    duration_hours: Optional[float] = None
    approval_required: bool = False
    approval_granted: Optional[bool] = None
    notes: Optional[str] = None


@dataclass
class TemplateProposalArtifact:
    """
    A proposal for automating part of a role

    CRITICAL SAFETY CONSTRAINTS:
    - status MUST be "sandbox" (no execution rights)
    - Cannot modify escalation paths
    - Cannot bypass compliance constraints
    - Requires explicit gate satisfaction for deployment
    """
    proposal_id: str
    shadowed_role: str  # e.g., "Designer 1", "Designer 2"
    proposed_automation_steps: List[str]
    evidence_references: List[str]  # References to observed telemetry
    risk_analysis: Dict[str, any]
    required_gates: List[str]  # Gates that must be satisfied

    # What would remain human
    human_retained_responsibilities: List[str]
    human_signoff_points: List[str]

    # Performance evidence
    observation_window_days: int
    success_rate: float
    error_patterns: List[str]

    # Safety constraints (IMMUTABLE)
    status: ProposalStatus = ProposalStatus.SANDBOX
    execution_rights: bool = False
    can_modify_escalation: bool = False
    can_bypass_compliance: bool = False

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "shadow_learning_agent"
    integrity_hash: Optional[str] = None

    def __post_init__(self):
        """Enforce safety constraints"""
        # CRITICAL: Proposals are ALWAYS sandbox-only
        if self.status != ProposalStatus.SANDBOX:
            raise ValueError("TemplateProposalArtifact.status MUST be 'sandbox'")

        if self.execution_rights:
            raise ValueError("TemplateProposalArtifact.execution_rights MUST be False")

        if self.can_modify_escalation:
            raise ValueError("TemplateProposalArtifact.can_modify_escalation MUST be False")

        if self.can_bypass_compliance:
            raise ValueError("TemplateProposalArtifact.can_bypass_compliance MUST be False")

        # Ensure evidence exists
        if not self.evidence_references:
            raise ValueError("TemplateProposalArtifact must have evidence references")

        # Ensure risk analysis exists
        if not self.risk_analysis:
            raise ValueError("TemplateProposalArtifact must have risk analysis")

        # Compute integrity hash
        if self.integrity_hash is None:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of proposal"""
        data = {
            "proposal_id": self.proposal_id,
            "shadowed_role": self.shadowed_role,
            "automation_steps": sorted(self.proposed_automation_steps),
            "evidence": sorted(self.evidence_references),
            "status": self.status.value,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class SubstitutionGate:
    """
    A gate that must be satisfied before automation can substitute for a human role

    ALL gates must be satisfied for substitution to occur.
    """
    gate_id: str
    gate_type: Literal[
        "performance_evidence",
        "deterministic_verification",
        "compliance_check",
        "human_signoff"
    ]
    description: str
    status: GateStatus = GateStatus.NOT_MET

    # Evidence
    evidence_window_days: Optional[int] = None
    required_success_rate: Optional[float] = None
    actual_success_rate: Optional[float] = None

    # Verification
    verification_method: Optional[str] = None
    verification_passed: Optional[bool] = None

    # Compliance
    regulation: Optional[str] = None
    compliance_verified: Optional[bool] = None

    # Human signoff
    signoff_required_from: Optional[str] = None
    signoff_granted: Optional[bool] = None
    signoff_timestamp: Optional[datetime] = None

    # Metadata
    evaluated_at: Optional[datetime] = None

    def evaluate(self) -> GateStatus:
        """Evaluate gate status based on type"""
        if self.gate_type == "performance_evidence":
            if (self.actual_success_rate is not None and
                self.required_success_rate is not None and
                self.actual_success_rate >= self.required_success_rate):
                self.status = GateStatus.SATISFIED
            else:
                self.status = GateStatus.NOT_MET

        elif self.gate_type == "deterministic_verification":
            if self.verification_passed:
                self.status = GateStatus.SATISFIED
            else:
                self.status = GateStatus.NOT_MET

        elif self.gate_type == "compliance_check":
            if self.compliance_verified:
                self.status = GateStatus.SATISFIED
            else:
                self.status = GateStatus.NOT_MET

        elif self.gate_type == "human_signoff":
            if self.signoff_granted:
                self.status = GateStatus.SATISFIED
            else:
                self.status = GateStatus.PENDING

        self.evaluated_at = datetime.now(timezone.utc)
        return self.status


@dataclass
class OrgChartNode:
    """
    A node in the organizational chart
    """
    node_id: str
    role_name: str
    reports_to: Optional[str]  # node_id of manager
    team: str
    department: str
    authority_level: AuthorityLevel
    direct_reports: List[str] = field(default_factory=list)
    metadata: Dict[str, any] = field(default_factory=dict)


@dataclass
class ProcessFlow:
    """
    A process flow diagram representation
    """
    flow_id: str
    flow_name: str
    steps: List[Dict[str, any]]  # Each step has: step_id, role, action, inputs, outputs
    decision_points: List[Dict[str, any]]  # Decision points with conditions
    handoffs: List[Dict[str, any]]  # Handoff points between roles
    sla_targets: Dict[str, float]
    compliance_checkpoints: List[str]
