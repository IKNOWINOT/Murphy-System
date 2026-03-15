"""
Packet Sealer
Seals execution packets with cryptographic signatures
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .models import (
    ExecutionGraph,
    ExecutionPacket,
    ExecutionScope,
    InterfaceMap,
    PacketState,
    RollbackPlan,
    TelemetryPlan,
)

logger = logging.getLogger(__name__)


class PacketSealer:
    """
    Seals execution packets with cryptographic signatures

    Signature binds:
    - Artifacts
    - Constraints
    - Authority state

    Any mutation invalidates packet
    """

    def __init__(self):
        self.sealed_packets: Dict[str, ExecutionPacket] = {}

    def create_packet(
        self,
        packet_id: str,
        scope: ExecutionScope,
        execution_graph: ExecutionGraph,
        interfaces: InterfaceMap,
        rollback_plan: RollbackPlan,
        telemetry_plan: TelemetryPlan
    ) -> ExecutionPacket:
        """
        Create execution packet

        Args:
            packet_id: Unique packet identifier
            scope: Frozen execution scope
            execution_graph: Execution DAG
            interfaces: Interface map
            rollback_plan: Rollback plan
            telemetry_plan: Telemetry plan

        Returns:
            Execution packet in COMPILING state
        """
        packet = ExecutionPacket(
            packet_id=packet_id,
            scope=scope,
            execution_graph=execution_graph,
            interfaces=interfaces,
            rollback_plan=rollback_plan,
            telemetry_plan=telemetry_plan,
            state=PacketState.COMPILING
        )

        return packet

    def seal_packet(
        self,
        packet: ExecutionPacket,
        confidence: float,
        authority_band: str,
        phase: str
    ) -> Tuple[bool, str, List[str]]:
        """
        Seal packet with cryptographic signature

        Args:
            packet: Packet to seal
            confidence: Current confidence
            authority_band: Current authority band
            phase: Current phase

        Returns:
            (success, signature, errors)
        """
        errors = []

        # Validate packet before sealing
        is_valid, validation_errors = self._validate_packet(packet)
        if not is_valid:
            errors.extend(validation_errors)
            return False, "", errors

        # Seal packet
        try:
            signature = packet.seal(confidence, authority_band, phase)

            # Store sealed packet
            self.sealed_packets[packet.packet_id] = packet

            return True, signature, []

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            errors.append(f"Failed to seal packet: {str(exc)}")
            return False, "", errors

    def verify_packet(
        self,
        packet: ExecutionPacket
    ) -> Tuple[bool, List[str]]:
        """
        Verify packet signature and integrity

        Args:
            packet: Packet to verify

        Returns:
            (is_valid, violations)
        """
        violations = []

        # Check if packet is sealed
        if packet.state != PacketState.SEALED:
            violations.append(f"Packet not sealed (state: {packet.state.value})")

        # Verify signature
        if not packet.verify_signature():
            violations.append("Signature verification failed")

        # Verify scope is frozen
        if not packet.scope.frozen:
            violations.append("Scope not frozen")

        # Verify scope hash
        expected_hash = packet.scope.calculate_hash()
        if packet.signature:
            # Signature should contain scope hash
            pass  # Already verified in verify_signature

        return len(violations) == 0, violations

    def detect_mutation(
        self,
        packet: ExecutionPacket,
        current_scope_hash: str
    ) -> Tuple[bool, List[str]]:
        """
        Detect if packet has been mutated

        Args:
            packet: Sealed packet
            current_scope_hash: Current scope hash

        Returns:
            (is_mutated, mutations)
        """
        mutations = []

        # Check scope hash
        original_hash = packet.scope.calculate_hash()
        if original_hash != current_scope_hash:
            mutations.append("Scope hash mismatch - scope has been mutated")

        # Verify signature
        if not packet.verify_signature():
            mutations.append("Signature verification failed - packet mutated")

        return len(mutations) > 0, mutations

    def invalidate_packet(
        self,
        packet: ExecutionPacket,
        reason: str
    ) -> None:
        """
        Invalidate packet

        Args:
            packet: Packet to invalidate
            reason: Reason for invalidation
        """
        packet.invalidate(reason)

        # Remove from sealed packets
        if packet.packet_id in self.sealed_packets:
            del self.sealed_packets[packet.packet_id]

    def _validate_packet(
        self,
        packet: ExecutionPacket
    ) -> Tuple[bool, List[str]]:
        """
        Validate packet before sealing

        Checks:
        - Scope is frozen
        - Execution graph is valid DAG
        - All steps are deterministic
        - Rollback plan exists
        - Telemetry plan exists
        """
        errors = []

        # Check scope
        if not packet.scope.frozen:
            errors.append("Scope not frozen")

        scope_valid, scope_errors = packet.scope.validate()
        if not scope_valid:
            errors.extend(scope_errors)

        # Check execution graph
        if not packet.execution_graph.is_dag():
            errors.append("Execution graph is not a DAG")

        is_det, det_errors = packet.execution_graph.validate_determinism()
        if not is_det:
            errors.extend(det_errors)

        # Check rollback plan
        if not packet.rollback_plan.steps:
            errors.append("Rollback plan is empty")

        # Check telemetry plan
        if not packet.telemetry_plan.configs:
            errors.append("Telemetry plan is empty")

        return len(errors) == 0, errors

    def get_sealed_packet(self, packet_id: str) -> ExecutionPacket:
        """Get sealed packet by ID"""
        return self.sealed_packets.get(packet_id)

    def list_sealed_packets(self) -> List[str]:
        """List all sealed packet IDs"""
        return list(self.sealed_packets.keys())

    def generate_completion_certificate(
        self,
        packet: ExecutionPacket,
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate completion certificate for successful execution

        Args:
            packet: Executed packet
            execution_result: Execution result

        Returns:
            Completion certificate
        """
        certificate = {
            'packet_id': packet.packet_id,
            'signature': packet.signature,
            'scope_hash': packet.scope.calculate_hash(),
            'execution_result': execution_result,
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'certificate_hash': None
        }

        # Generate certificate hash
        cert_str = json.dumps(certificate, sort_keys=True)
        certificate['certificate_hash'] = hashlib.sha256(cert_str.encode()).hexdigest()

        return certificate
