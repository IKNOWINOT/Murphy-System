"""
Core data models for Gate Synthesis Engine
Defines gates, risk vectors, exposure signals, and lifecycle management
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class GateType(Enum):
    """Types of gates that can be synthesized"""
    CONSTRAINT = "constraint"           # Restricts what can be done
    VERIFICATION = "verification"       # Requires evidence before proceeding
    AUTHORITY = "authority"             # Limits authority level
    ISOLATION = "isolation"             # Enforces sandboxing


class GateCategory(Enum):
    """Categories of gates based on what they protect against"""
    SEMANTIC_STABILITY = "semantic_stability"     # Prevents interpretation drift
    VERIFICATION_REQUIRED = "verification_required"  # Forces deterministic checks
    AUTHORITY_DECAY = "authority_decay"           # Downgrades authority
    ISOLATION_REQUIRED = "isolation_required"     # Enforces sandboxing


class GateState(Enum):
    """Lifecycle states of a gate"""
    PROPOSED = "proposed"       # Gate has been generated but not activated
    ACTIVE = "active"           # Gate is currently enforcing
    SATISFIED = "satisfied"     # Gate conditions met, can be retired
    EXPIRED = "expired"         # Gate expired without being satisfied
    RETIRED = "retired"         # Gate permanently retired


class FailureModeType(Enum):
    """Types of failure modes"""
    SEMANTIC_DRIFT = "semantic_drift"
    CONSTRAINT_VIOLATION = "constraint_violation"
    AUTHORITY_MISUSE = "authority_misuse"
    VERIFICATION_INSUFFICIENT = "verification_insufficient"
    IRREVERSIBLE_ACTION = "irreversible_action"
    BLAST_RADIUS_EXCEEDED = "blast_radius_exceeded"


@dataclass
class RiskVector:
    """
    Risk vector for a candidate future step

    Components:
    - H: Epistemic instability
    - (1-D): Lack of deterministic grounding
    - Exposure: External side effects
    - AuthorityRisk: Risk from authority level
    """
    H: float  # Epistemic instability [0, 1]
    one_minus_D: float  # Lack of grounding [0, 1]
    exposure: float  # External exposure [0, 1]
    authority_risk: float  # Authority risk [0, 1]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'H': self.H,
            'one_minus_D': self.one_minus_D,
            'exposure': self.exposure,
            'authority_risk': self.authority_risk,
            'magnitude': self.magnitude()
        }

    def magnitude(self) -> float:
        """Calculate overall risk magnitude"""
        return (self.H + self.one_minus_D + self.exposure + self.authority_risk) / 4.0


@dataclass
class FailureMode:
    """
    Identified failure mode for a future step
    """
    id: str
    type: FailureModeType
    probability: float  # [0, 1]
    impact: float  # [0, 1]
    risk_vector: RiskVector
    description: str
    affected_artifacts: List[str] = field(default_factory=list)
    mitigation_required: bool = True
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def risk_score(self) -> float:
        """Calculate risk score (probability × impact)"""
        return self.probability * self.impact

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'probability': self.probability,
            'impact': self.impact,
            'risk_score': self.risk_score,
            'risk_vector': self.risk_vector.to_dict(),
            'description': self.description,
            'affected_artifacts': self.affected_artifacts,
            'mitigation_required': self.mitigation_required,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class RiskPath:
    """
    Projected risk path showing how risk evolves
    """
    path_id: str
    steps: List[str]  # Sequence of artifact IDs
    failure_modes: List[FailureMode]
    cumulative_risk: float
    likelihood: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'path_id': self.path_id,
            'steps': self.steps,
            'failure_modes': [fm.to_dict() for fm in self.failure_modes],
            'cumulative_risk': self.cumulative_risk,
            'likelihood': self.likelihood,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ExposureSignal:
    """
    Signal indicating exposure to external systems
    """
    signal_id: str
    external_side_effects: bool
    reversibility: float  # [0, 1] - 0 = irreversible, 1 = fully reversible
    blast_radius_estimate: float  # [0, 1] - scope of potential damage
    affected_systems: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def risk_level(self) -> str:
        """Calculate risk level"""
        if self.blast_radius_estimate > 0.7 or not self.external_side_effects:
            return "high"
        elif self.blast_radius_estimate > 0.4:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'signal_id': self.signal_id,
            'external_side_effects': self.external_side_effects,
            'reversibility': self.reversibility,
            'blast_radius_estimate': self.blast_radius_estimate,
            'risk_level': self.risk_level,
            'affected_systems': self.affected_systems,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class BlastRadius:
    """
    Estimated blast radius of an action
    """
    scope: float  # [0, 1] - how much can be affected
    severity: float  # [0, 1] - how bad the damage could be
    affected_domains: List[str] = field(default_factory=list)

    @property
    def total_risk(self) -> float:
        """Calculate total risk (scope × severity)"""
        return self.scope * self.severity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'scope': self.scope,
            'severity': self.severity,
            'total_risk': self.total_risk,
            'affected_domains': self.affected_domains
        }


@dataclass
class RetirementCondition:
    """
    Conditions under which a gate can be retired
    """
    condition_type: str  # "confidence_recovery", "verification_success", "risk_reduction"
    threshold: float
    current_value: float = 0.0
    satisfied: bool = False

    def check(self, current_value: float) -> bool:
        """Check if condition is satisfied"""
        self.current_value = current_value

        if self.condition_type == "confidence_recovery":
            self.satisfied = current_value >= self.threshold
        elif self.condition_type == "verification_success":
            self.satisfied = current_value >= self.threshold
        elif self.condition_type == "risk_reduction":
            self.satisfied = current_value <= self.threshold

        return self.satisfied

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'condition_type': self.condition_type,
            'threshold': self.threshold,
            'current_value': self.current_value,
            'satisfied': self.satisfied
        }


@dataclass
class Gate:
    """
    Control gate that restricts or requires actions

    DESIGN LAW: No gate may authorize action.
    Gates may only restrict or require more evidence.
    """
    id: str
    type: GateType
    category: GateCategory
    target: str  # What this gate applies to (artifact, phase, action, interface)
    trigger_condition: Dict[str, Any]
    enforcement_effect: Dict[str, Any]
    state: GateState = GateState.PROPOSED

    # Lifecycle
    created_at: datetime = field(default_factory=datetime.now)
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    retired_at: Optional[datetime] = None

    # Retirement conditions
    retirement_conditions: List[RetirementCondition] = field(default_factory=list)

    # Metadata
    reason: str = ""
    failure_modes_addressed: List[str] = field(default_factory=list)
    priority: int = 5  # 1-10, higher = more critical
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate ID if not provided"""
        if not self.id:
            content_str = f"{self.type.value}_{self.category.value}_{self.target}"
            self.id = hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def activate(self) -> None:
        """Activate the gate"""
        if self.state == GateState.PROPOSED:
            self.state = GateState.ACTIVE
            self.activated_at = datetime.now(timezone.utc)

    def check_expiry(self) -> bool:
        """Check if gate has expired"""
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            self.state = GateState.EXPIRED
            return True
        return False

    def check_retirement_conditions(self) -> bool:
        """Check if all retirement conditions are satisfied"""
        if not self.retirement_conditions:
            return False

        all_satisfied = all(cond.satisfied for cond in self.retirement_conditions)

        if all_satisfied:
            self.state = GateState.SATISFIED
            return True

        return False

    def retire(self, reason: str = "") -> None:
        """Retire the gate"""
        self.state = GateState.RETIRED
        self.retired_at = datetime.now(timezone.utc)
        if reason:
            self.metadata['retirement_reason'] = reason

    def is_active(self) -> bool:
        """Check if gate is currently active"""
        return self.state == GateState.ACTIVE

    def can_retire(self) -> bool:
        """Check if gate can be retired"""
        return self.state in [GateState.SATISFIED, GateState.EXPIRED]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'category': self.category.value,
            'target': self.target,
            'trigger_condition': self.trigger_condition,
            'enforcement_effect': self.enforcement_effect,
            'state': self.state.value,
            'created_at': self.created_at.isoformat(),
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'retired_at': self.retired_at.isoformat() if self.retired_at else None,
            'retirement_conditions': [rc.to_dict() for rc in self.retirement_conditions],
            'reason': self.reason,
            'failure_modes_addressed': self.failure_modes_addressed,
            'priority': self.priority,
            'metadata': self.metadata,
            'is_active': self.is_active(),
            'can_retire': self.can_retire()
        }


@dataclass
class GateRegistry:
    """
    Registry of all gates
    """
    gates: Dict[str, Gate] = field(default_factory=dict)

    def add_gate(self, gate: Gate) -> None:
        """Add gate to registry"""
        self.gates[gate.id] = gate

    def get_gate(self, gate_id: str) -> Optional[Gate]:
        """Get gate by ID"""
        return self.gates.get(gate_id)

    def get_active_gates(self) -> List[Gate]:
        """Get all active gates"""
        return [gate for gate in self.gates.values() if gate.is_active()]

    def get_gates_by_category(self, category: GateCategory) -> List[Gate]:
        """Get gates by category"""
        return [gate for gate in self.gates.values() if gate.category == category]

    def get_gates_by_target(self, target: str) -> List[Gate]:
        """Get gates affecting a specific target"""
        return [gate for gate in self.gates.values() if gate.target == target]

    def retire_expired_gates(self) -> List[str]:
        """Retire all expired gates"""
        expired = []
        for gate in self.gates.values():
            if gate.check_expiry():
                gate.retire("Expired")
                expired.append(gate.id)
        return expired

    def check_all_retirement_conditions(self) -> List[str]:
        """Check retirement conditions for all gates"""
        retired = []
        for gate in self.gates.values():
            if gate.is_active() and gate.check_retirement_conditions():
                gate.retire("Conditions satisfied")
                retired.append(gate.id)
        return retired

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'gates': {gate_id: gate.to_dict() for gate_id, gate in self.gates.items()},
            'total_gates': len(self.gates),
            'active_gates': len(self.get_active_gates()),
            'by_category': {
                category.value: len(self.get_gates_by_category(category))
                for category in GateCategory
            }
        }
