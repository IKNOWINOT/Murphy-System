"""
Execution Packet - Immutable, Signed Instruction Bundle
Part 4 of MFGC-AI Specification

An Execution Packet is a sealed contract between control plane and execution plane.
Once compiled, it cannot be modified. All actions are bounded, time-limited, and auditable.
"""

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions that can be executed"""
    READ_SENSOR = "read_sensor"
    WRITE_ACTUATOR = "write_actuator"
    QUERY_DATABASE = "query_database"
    CALL_API = "call_api"
    GENERATE_CONTENT = "generate_content"
    EXECUTE_COMMAND = "execute_command"


class ConstraintType(Enum):
    """Types of safety constraints"""
    ABSOLUTE_BOUND = "absolute_bound"
    RATE_LIMIT = "rate_limit"
    REDUNDANCY_CHECK = "redundancy_check"
    HUMAN_APPROVAL = "human_approval"
    TIMEOUT = "timeout"


@dataclass
class Action:
    """Single executable action"""
    action_id: str
    action_type: ActionType
    description: str
    parameters: Dict[str, Any]
    preconditions: List[str]
    postconditions: List[str]
    bound_artifacts: List[str]  # Hashes of artifacts this action depends on
    max_retries: int = 3
    timeout_seconds: int = 30


@dataclass
class SafetyConstraint:
    """Safety constraint that must be enforced"""
    constraint_id: str
    constraint_type: ConstraintType
    description: str
    predicate: str  # Executable predicate (Python expression)
    violation_action: str  # What to do if violated: "halt", "rollback", "alert"
    severity: str  # "critical", "high", "medium", "low"


@dataclass
class Gate:
    """Gate predicate that must be satisfied"""
    gate_id: str
    description: str
    predicate: str  # Executable predicate
    is_satisfied: bool
    evidence: List[str]  # Links to evidence artifacts
    required_for_execution: bool = True


@dataclass
class TimeWindow:
    """Time bounds for execution"""
    valid_from: datetime
    valid_until: datetime
    heartbeat_interval_seconds: int = 60

    def is_valid(self) -> bool:
        """Check if current time is within window"""
        now = datetime.now(timezone.utc)
        return self.valid_from <= now <= self.valid_until

    def time_remaining(self) -> float:
        """Seconds remaining in window"""
        return (self.valid_until - datetime.now(timezone.utc)).total_seconds()


@dataclass
class RollbackPlan:
    """Plan for safely stopping or reversing execution"""
    description: str
    rollback_actions: List[Action]
    safe_state_description: str
    human_handoff_required: bool = False
    human_handoff_contact: Optional[str] = None


@dataclass
class AuthorityEnvelope:
    """Bounds on what actions are allowed"""
    max_authority_level: float  # 0.0 to 1.0
    allowed_action_types: List[ActionType]
    forbidden_actions: List[str]
    requires_human_approval: bool
    approval_threshold: float = 0.85


@dataclass
class ExecutionPacket:
    """
    Immutable Execution Packet

    This is the sealed contract between control plane and execution plane.
    Once compiled and signed, it cannot be modified.
    """

    # Identity
    packet_id: str
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)

    # Scope Freezing
    scope_hash: str = ""  # Hash of entire artifact graph
    artifact_hashes: Dict[str, str] = field(default_factory=dict)  # Individual artifact hashes

    # Execution Plan
    task_graph: List[Action] = field(default_factory=list)  # DAG of actions
    dependencies: Dict[str, List[str]] = field(default_factory=dict)  # Action dependencies

    # Safety
    safety_constraints: List[SafetyConstraint] = field(default_factory=list)
    active_gates: List[Gate] = field(default_factory=list)
    authority_envelope: Optional[AuthorityEnvelope] = None

    # Time Bounds
    time_window: Optional[TimeWindow] = None

    # Rollback
    rollback_plan: Optional[RollbackPlan] = None

    # Compilation Metadata
    confidence_at_compile: float = 0.0
    murphy_index_at_compile: float = 0.0
    phase_at_compile: str = ""
    gates_satisfied_count: int = 0
    gates_total_count: int = 0

    # Evidence & Audit
    evidence_links: List[str] = field(default_factory=list)
    compilation_log: List[str] = field(default_factory=list)

    # Signatures (optional for MVP, critical for production)
    signatures: Dict[str, str] = field(default_factory=dict)

    # Status
    is_compiled: bool = False
    is_signed: bool = False
    is_executed: bool = False
    execution_started_at: Optional[datetime] = None
    execution_completed_at: Optional[datetime] = None

    def compute_scope_hash(self) -> str:
        """
        Compute cryptographic hash of the entire scope.
        This freezes the semantic space - no new interpretations allowed.
        """
        scope_data = {
            'packet_id': self.packet_id,
            'task_graph': [asdict(action) for action in self.task_graph],
            'dependencies': self.dependencies,
            'safety_constraints': [asdict(c) for c in self.safety_constraints],
            'active_gates': [asdict(g) for g in self.active_gates],
            'artifact_hashes': self.artifact_hashes,
        }

        scope_json = json.dumps(scope_data, sort_keys=True, default=str)
        return hashlib.sha256(scope_json.encode()).hexdigest()

    def verify_scope_hash(self) -> bool:
        """Verify that scope hasn't been tampered with"""
        computed = self.compute_scope_hash()
        return computed == self.scope_hash

    def add_signature(self, signer: str, signature: str):
        """Add a signature from a control plane service"""
        self.signatures[signer] = signature
        if len(self.signatures) >= 3:  # Require quorum
            self.is_signed = True

    def verify_signatures(self) -> bool:
        """Verify all signatures (simplified for MVP)"""
        # In production, this would use actual cryptographic verification
        return len(self.signatures) >= 3 and self.is_signed

    def can_execute(self) -> tuple[bool, List[str]]:
        """
        Check if packet can be executed.
        Returns (can_execute, reasons)
        """
        reasons = []

        if not self.is_compiled:
            reasons.append("Packet not compiled")

        if not self.is_signed:
            reasons.append("Packet not signed")

        if not self.verify_scope_hash():
            reasons.append("Scope hash verification failed - packet may be tampered")

        if self.time_window and not self.time_window.is_valid():
            reasons.append("Time window expired or not yet valid")

        if self.is_executed:
            reasons.append("Packet already executed")

        # Check all critical gates are satisfied
        unsatisfied_gates = [
            g.gate_id for g in self.active_gates
            if g.required_for_execution and not g.is_satisfied
        ]
        if unsatisfied_gates:
            reasons.append(f"Critical gates not satisfied: {', '.join(unsatisfied_gates)}")

        return (len(reasons) == 0, reasons)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'packet_id': self.packet_id,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'scope_hash': self.scope_hash,
            'task_graph': [asdict(action) for action in self.task_graph],
            'safety_constraints': [asdict(c) for c in self.safety_constraints],
            'active_gates': [asdict(g) for g in self.active_gates],
            'authority_envelope': asdict(self.authority_envelope) if self.authority_envelope else None,
            'time_window': {
                'valid_from': self.time_window.valid_from.isoformat(),
                'valid_until': self.time_window.valid_until.isoformat(),
                'heartbeat_interval_seconds': self.time_window.heartbeat_interval_seconds,
            } if self.time_window else None,
            'rollback_plan': asdict(self.rollback_plan) if self.rollback_plan else None,
            'confidence_at_compile': self.confidence_at_compile,
            'murphy_index_at_compile': self.murphy_index_at_compile,
            'phase_at_compile': self.phase_at_compile,
            'gates_satisfied': f"{self.gates_satisfied_count}/{self.gates_total_count}",
            'is_compiled': self.is_compiled,
            'is_signed': self.is_signed,
            'is_executed': self.is_executed,
            'can_execute': self.can_execute()[0],
            'execution_blockers': self.can_execute()[1],
        }

    def get_status_summary(self) -> str:
        """Get human-readable status"""
        can_exec, reasons = self.can_execute()

        if self.is_executed:
            return "✅ EXECUTED"
        elif can_exec:
            return "🟢 READY FOR EXECUTION"
        elif not self.is_compiled:
            return "🔴 NOT COMPILED"
        elif not self.is_signed:
            return "🟡 AWAITING SIGNATURES"
        else:
            return f"🔴 BLOCKED: {', '.join(reasons)}"


def create_simple_packet(
    packet_id: str,
    actions: List[Action],
    confidence: float,
    murphy_index: float,
    phase: str,
    gates: List[Gate],
    validity_hours: int = 24
) -> ExecutionPacket:
    """
    Helper function to create a simple execution packet.
    For MVP - production would have more sophisticated compilation.
    """

    # Create time window
    now = datetime.now(timezone.utc)
    time_window = TimeWindow(
        valid_from=now,
        valid_until=now + timedelta(hours=validity_hours),
        heartbeat_interval_seconds=60
    )

    # Create authority envelope based on confidence
    authority_envelope = AuthorityEnvelope(
        max_authority_level=min(confidence, 0.95),
        allowed_action_types=[ActionType.READ_SENSOR, ActionType.QUERY_DATABASE, ActionType.GENERATE_CONTENT],
        forbidden_actions=["override_human", "irreversible_action"],
        requires_human_approval=confidence < 0.85
    )

    # Create basic rollback plan
    rollback_plan = RollbackPlan(
        description="Safe stop and state preservation",
        rollback_actions=[],
        safe_state_description="All operations halted, state logged",
        human_handoff_required=True,
        human_handoff_contact="system_admin"
    )

    # Create packet
    packet = ExecutionPacket(
        packet_id=packet_id,
        task_graph=actions,
        active_gates=gates,
        authority_envelope=authority_envelope,
        time_window=time_window,
        rollback_plan=rollback_plan,
        confidence_at_compile=confidence,
        murphy_index_at_compile=murphy_index,
        phase_at_compile=phase,
        gates_satisfied_count=sum(1 for g in gates if g.is_satisfied),
        gates_total_count=len(gates),
    )

    # Compute scope hash
    packet.scope_hash = packet.compute_scope_hash()
    packet.is_compiled = True

    return packet
