"""
Safety Enforcer
===============

Ensures synthetic failure generator never touches production.

Safety Rules:
1. Never touch production interfaces
2. Never emit real execution packets
3. Only produce training artifacts
4. Maintain complete isolation
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SafetyEnforcer:
    """
    Enforces safety rules for synthetic failure generator

    Ensures complete isolation from production systems
    """

    def __init__(self):
        self.production_interfaces: List[str] = []
        self.blocked_operations: List[str] = []
        self.safety_violations: List[Dict[str, Any]] = []
        self.is_production_mode = False
        self.training_mode = True  # Always in training mode by default

    def register_production_interface(self, interface_id: str):
        """Register production interface to block"""
        self.production_interfaces.append(interface_id)

    def validate_packet(self, packet: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate packet is synthetic only

        Returns:
            (is_valid, error_message)
        """
        # Check if packet is marked as synthetic
        if not packet.get('is_synthetic', False):
            error = "Packet not marked as synthetic"
            self._log_violation('packet_validation', error, packet)
            return False, error

        # Check for production interface references
        interfaces = packet.get('interface_definitions', {})
        for interface_id in interfaces:
            if interface_id in self.production_interfaces:
                error = f"Packet references production interface: {interface_id}"
                self._log_violation('production_interface', error, packet)
                return False, error

        # Check packet has training marker
        if 'training_artifact' not in packet and 'is_synthetic' not in packet:
            error = "Packet missing training/synthetic markers"
            self._log_violation('missing_markers', error, packet)
            return False, error

        return True, None

    def validate_execution(
        self,
        execution_plan: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate execution is simulation only

        Returns:
            (is_valid, error_message)
        """
        # Check for real execution markers
        if execution_plan.get('is_real_execution', False):
            error = "Execution plan marked as real execution"
            self._log_violation('real_execution', error, execution_plan)
            return False, error

        # Check for production operations
        steps = execution_plan.get('execution_graph', {}).get('steps', [])
        for step in steps:
            step_type = step.get('type', '')

            # Block dangerous operations
            dangerous_ops = [
                'database_write',
                'file_system_write',
                'api_call_production',
                'actuator_command_real'
            ]

            if step_type in dangerous_ops:
                error = f"Execution contains dangerous operation: {step_type}"
                self._log_violation('dangerous_operation', error, execution_plan)
                return False, error

        return True, None

    def validate_interface_access(
        self,
        interface_id: str,
        operation: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate interface access is safe

        Returns:
            (is_valid, error_message)
        """
        # Block production interface access
        if interface_id in self.production_interfaces:
            error = f"Attempted access to production interface: {interface_id}"
            self._log_violation('interface_access', error, {
                'interface_id': interface_id,
                'operation': operation
            })
            return False, error

        # Block write operations
        write_operations = ['write', 'update', 'delete', 'execute']
        if operation in write_operations:
            error = f"Attempted write operation: {operation}"
            self._log_violation('write_operation', error, {
                'interface_id': interface_id,
                'operation': operation
            })
            return False, error

        return True, None

    def enforce_training_only_mode(self, artifact: Dict[str, Any]) -> bool:
        """
        Enforce that only training artifacts are produced

        Returns:
            True if artifact is valid training artifact
        """
        # Check artifact type
        artifact_type = artifact.get('artifact_type', '')

        valid_types = [
            'confidence_training',
            'gate_policy',
            'risk_prediction',
            'reward_signal',
            'simulation_result'
        ]

        if artifact_type not in valid_types:
            error = f"Invalid artifact type: {artifact_type}"
            self._log_violation('invalid_artifact_type', error, artifact)
            return False

        # Check artifact has training markers
        if not artifact.get('is_training_data', True):
            error = "Artifact not marked as training data"
            self._log_violation('missing_training_marker', error, artifact)
            return False

        return True

    def block_production_emission(
        self,
        packet: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Block emission of real execution packets

        Returns:
            (is_blocked, reason)
        """
        # Always block if not synthetic
        if not packet.get('is_synthetic', False):
            return True, "Packet not marked as synthetic"

        # Block if has production markers
        if packet.get('is_production', False):
            return True, "Packet marked as production"

        # Block if references production interfaces
        interfaces = packet.get('required_interfaces', [])
        for interface_id in interfaces:
            if interface_id in self.production_interfaces:
                return True, f"References production interface: {interface_id}"

        return False, None

    def get_safety_report(self) -> Dict[str, Any]:
        """Get safety enforcement report"""
        return {
            'total_violations': len(self.safety_violations),
            'production_interfaces_protected': len(self.production_interfaces),
            'blocked_operations': len(self.blocked_operations),
            'violations_by_type': self._count_violations_by_type(),
            'recent_violations': self.safety_violations[-10:],
            'is_production_mode': self.is_production_mode,
            'safety_status': 'SAFE' if len(self.safety_violations) == 0 else 'VIOLATIONS_DETECTED'
        }

    def clear_violations(self):
        """Clear violation history"""
        self.safety_violations = []

    def allow_production_access(self) -> bool:
        """Check if production access is allowed (should always be False)"""
        return False

    def is_training_mode(self) -> bool:
        """Check if in training mode (should always be True)"""
        return self.training_mode

    def allow_packet_emission(self, packet: Dict[str, Any]) -> bool:
        """Check if packet emission is allowed (should block production packets)"""
        # Block any packet that looks like production
        if packet.get('target') == 'production_system':
            return False
        if packet.get('is_real_execution', False):
            return False
        return False  # Block all emissions by default for safety

    def validate_safety(self, artifact: Any) -> bool:
        """Validate safety of artifact or packet"""
        if isinstance(artifact, dict):
            # Training artifacts pass
            if artifact.get('type') == 'training':
                return True
            # Production packets fail
            if artifact.get('type') == 'production':
                return False
            if artifact.get('target') == 'production_system':
                return False
        return True  # Default to safe for training artifacts

    def enable_production_mode(self, enable: bool):
        """
        Enable/disable production mode

        WARNING: Should never be enabled in synthetic failure generator
        """
        if enable:
            self._log_violation(
                'production_mode_enabled',
                'CRITICAL: Production mode enabled in synthetic failure generator',
                {}
            )

        self.is_production_mode = enable

    def _log_violation(
        self,
        violation_type: str,
        message: str,
        context: Dict[str, Any]
    ):
        """Log safety violation"""
        violation = {
            'violation_type': violation_type,
            'message': message,
            'context': context,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        self.safety_violations.append(violation)
        self.blocked_operations.append(violation_type)

        # In production, would also:
        # - Send alert
        # - Log to security system
        # - Trigger incident response

    def _count_violations_by_type(self) -> Dict[str, int]:
        """Count violations by type"""
        counts = {}
        for violation in self.safety_violations:
            violation_type = violation['violation_type']
            counts[violation_type] = counts.get(violation_type, 0) + 1
        return counts
