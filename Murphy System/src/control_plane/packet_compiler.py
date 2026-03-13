"""
Execution Packet Compiler
Part 4 of MFGC-AI Specification

This is the critical boundary where reasoning becomes action.
Converts verified, gated, high-confidence plans into immutable execution packets.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .execution_packet import (
    Action,
    ActionType,
    AuthorityEnvelope,
    ConstraintType,
    ExecutionPacket,
    Gate,
    RollbackPlan,
    SafetyConstraint,
    TimeWindow,
    create_simple_packet,
)

logger = logging.getLogger(__name__)


class PacketCompilationError(Exception):
    """Raised when packet compilation fails"""
    pass


class PacketCompiler:
    """
    Compiles execution packets from system state.

    This is the ONLY place where plans become executable actions.
    Enforces all MFGC-AI safety conditions.
    """

    def __init__(self):
        self.confidence_threshold = 0.85
        self.murphy_threshold = 0.5
        self.gate_satisfaction_threshold = 0.7
        self.max_unknowns = 2

        self.compiled_packets: Dict[str, ExecutionPacket] = {}
        self.compilation_log: List[Dict[str, Any]] = []

    def can_compile(
        self,
        confidence: float,
        murphy_index: float,
        phase: str,
        gates: List[Gate],
        unknowns: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Check if execution packet can be compiled.

        Formal Compilation Preconditions:
        1. Phase = Execute
        2. Confidence >= threshold
        3. Murphy Index <= threshold
        4. All gates satisfied
        5. Unknowns <= max

        Returns (can_compile, reasons)
        """
        reasons = []

        # Phase condition
        if phase.lower() != "execute":
            reasons.append(f"Phase must be 'execute', currently '{phase}'")

        # Confidence condition
        if confidence < self.confidence_threshold:
            reasons.append(
                f"Confidence {confidence:.2f} below threshold {self.confidence_threshold}"
            )

        # Murphy index condition
        if murphy_index > self.murphy_threshold:
            reasons.append(
                f"Murphy index {murphy_index:.2f} above threshold {self.murphy_threshold}"
            )

        # Gate satisfaction
        satisfied_gates = sum(1 for g in gates if g.is_satisfied)
        total_gates = len(gates)
        satisfaction_rate = satisfied_gates / total_gates if total_gates > 0 else 0

        if satisfaction_rate < self.gate_satisfaction_threshold:
            reasons.append(
                f"Gate satisfaction {satisfaction_rate:.1%} below threshold "
                f"{self.gate_satisfaction_threshold:.0%} ({satisfied_gates}/{total_gates})"
            )

        # Unknowns condition
        if len(unknowns) > self.max_unknowns:
            reasons.append(
                f"Too many unknowns: {len(unknowns)} > {self.max_unknowns}"
            )

        return (len(reasons) == 0, reasons)

    def compile_packet(
        self,
        task_description: str,
        confidence: float,
        murphy_index: float,
        phase: str,
        gates: List[Dict[str, Any]],
        unknowns: List[str],
        artifact_graph: Optional[Dict[str, Any]] = None
    ) -> ExecutionPacket:
        """
        Compile an execution packet from system state.

        This is the main compilation entry point.
        """

        # Convert gate dicts to Gate objects
        gate_objects = [
            Gate(
                gate_id=g.get('id', str(uuid.uuid4())),
                description=g.get('description', ''),
                predicate=g.get('predicate', 'True'),
                is_satisfied=g.get('is_satisfied', False),
                evidence=g.get('evidence', []),
                required_for_execution=g.get('required', True)
            )
            for g in gates
        ]

        # Check compilation preconditions
        can_compile, reasons = self.can_compile(
            confidence, murphy_index, phase, gate_objects, unknowns
        )

        if not can_compile:
            error_msg = f"Cannot compile execution packet: {'; '.join(reasons)}"
            self._log_compilation_attempt(
                success=False,
                confidence=confidence,
                murphy_index=murphy_index,
                phase=phase,
                error=error_msg
            )
            raise PacketCompilationError(error_msg)

        # Generate packet ID
        packet_id = f"EP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

        # Extract actions from task description (simplified for MVP)
        actions = self._extract_actions(task_description, confidence)

        # Create safety constraints
        safety_constraints = self._generate_safety_constraints(
            confidence, murphy_index, gate_objects
        )

        # Create packet
        packet = create_simple_packet(
            packet_id=packet_id,
            actions=actions,
            confidence=confidence,
            murphy_index=murphy_index,
            phase=phase,
            gates=gate_objects,
            validity_hours=24
        )

        # Add safety constraints
        packet.safety_constraints = safety_constraints

        # Add compilation log
        packet.compilation_log.append(
            f"Compiled at {datetime.now(timezone.utc).isoformat()} with confidence {confidence:.2f}"
        )
        packet.compilation_log.append(
            f"Murphy index: {murphy_index:.2f}"
        )
        packet.compilation_log.append(
            f"Gates satisfied: {packet.gates_satisfied_count}/{packet.gates_total_count}"
        )

        # Sign packet (simplified for MVP)
        self._sign_packet(packet)

        # Store packet
        self.compiled_packets[packet_id] = packet

        # Log successful compilation
        self._log_compilation_attempt(
            success=True,
            confidence=confidence,
            murphy_index=murphy_index,
            phase=phase,
            packet_id=packet_id
        )

        return packet

    def _extract_actions(
        self,
        task_description: str,
        confidence: float
    ) -> List[Action]:
        """
        Extract executable actions from task description.
        Simplified for MVP - production would use more sophisticated parsing.
        """
        actions = []

        # Create a simple action for the task
        action = Action(
            action_id=f"action-{uuid.uuid4().hex[:8]}",
            action_type=ActionType.GENERATE_CONTENT,
            description=task_description,
            parameters={'task': task_description, 'confidence': confidence},
            preconditions=['confidence >= 0.85', 'gates_satisfied'],
            postconditions=['task_completed', 'results_logged'],
            bound_artifacts=[],
            max_retries=3,
            timeout_seconds=300
        )

        actions.append(action)
        return actions

    def _generate_safety_constraints(
        self,
        confidence: float,
        murphy_index: float,
        gates: List[Gate]
    ) -> List[SafetyConstraint]:
        """Generate safety constraints based on system state"""
        constraints = []

        # Confidence monitoring constraint
        constraints.append(SafetyConstraint(
            constraint_id=f"conf-monitor-{uuid.uuid4().hex[:8]}",
            constraint_type=ConstraintType.ABSOLUTE_BOUND,
            description="Confidence must remain above threshold during execution",
            predicate=f"confidence >= {self.confidence_threshold}",
            violation_action="halt",
            severity="critical"
        ))

        # Murphy index constraint
        constraints.append(SafetyConstraint(
            constraint_id=f"murphy-monitor-{uuid.uuid4().hex[:8]}",
            constraint_type=ConstraintType.ABSOLUTE_BOUND,
            description="Murphy index must remain below threshold",
            predicate=f"murphy_index <= {self.murphy_threshold}",
            violation_action="halt",
            severity="critical"
        ))

        # Timeout constraint
        constraints.append(SafetyConstraint(
            constraint_id=f"timeout-{uuid.uuid4().hex[:8]}",
            constraint_type=ConstraintType.TIMEOUT,
            description="Execution must complete within time window",
            predicate="execution_time < time_window.valid_until",
            violation_action="halt",
            severity="high"
        ))

        # Gate monitoring constraint
        if gates:
            constraints.append(SafetyConstraint(
                constraint_id=f"gate-monitor-{uuid.uuid4().hex[:8]}",
                constraint_type=ConstraintType.REDUNDANCY_CHECK,
                description="All critical gates must remain satisfied",
                predicate="all(g.is_satisfied for g in critical_gates)",
                violation_action="halt",
                severity="critical"
            ))

        return constraints

    def _sign_packet(self, packet: ExecutionPacket):
        """
        Sign packet with control plane signatures.
        Simplified for MVP - production would use actual cryptography.
        """
        # In production, these would be cryptographic signatures
        # For MVP, we just add placeholder signatures

        packet.add_signature("gate_compiler", f"sig-gc-{uuid.uuid4().hex[:16]}")
        packet.add_signature("confidence_engine", f"sig-ce-{uuid.uuid4().hex[:16]}")
        packet.add_signature("authority_controller", f"sig-ac-{uuid.uuid4().hex[:16]}")

        packet.is_signed = True

    def _log_compilation_attempt(
        self,
        success: bool,
        confidence: float,
        murphy_index: float,
        phase: str,
        packet_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log compilation attempt for audit trail"""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'success': success,
            'confidence': confidence,
            'murphy_index': murphy_index,
            'phase': phase,
            'packet_id': packet_id,
            'error': error
        }
        self.compilation_log.append(log_entry)

    def get_packet(self, packet_id: str) -> Optional[ExecutionPacket]:
        """Retrieve a compiled packet by ID"""
        return self.compiled_packets.get(packet_id)

    def list_packets(self) -> List[Dict[str, Any]]:
        """List all compiled packets"""
        return [
            {
                'packet_id': pid,
                'status': packet.get_status_summary(),
                'created_at': packet.created_at.isoformat(),
                'confidence': packet.confidence_at_compile,
                'murphy_index': packet.murphy_index_at_compile,
                'can_execute': packet.can_execute()[0]
            }
            for pid, packet in self.compiled_packets.items()
        ]

    def get_compilation_log(self) -> List[Dict[str, Any]]:
        """Get compilation attempt log for audit"""
        return self.compilation_log
