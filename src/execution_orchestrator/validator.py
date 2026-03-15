"""
Pre-Execution Validator
========================

Validates execution packets before execution begins.

Validation Steps:
1. Packet signature verification
2. Interface existence checking
3. Permission validation
4. Resource health checking

Design Principle: Fail fast - catch issues before execution starts
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .models import InterfaceHealth, InterfaceStatus

logger = logging.getLogger(__name__)


class PreExecutionValidator:
    """
    Validates execution packets before execution

    Ensures:
    - Packet integrity (signature valid)
    - Interface availability (all interfaces exist and healthy)
    - Permission validity (execution authorized)
    - Resource health (sufficient resources available)
    """

    def __init__(self):
        self.interface_registry: Dict[str, InterfaceHealth] = {}

    def validate_packet(
        self,
        packet: Dict,
        expected_signature: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate packet integrity

        Args:
            packet: Execution packet to validate
            expected_signature: Expected cryptographic signature

        Returns:
            (is_valid, error_message)
        """
        # Check packet structure
        if not self._validate_packet_structure(packet):
            return False, "Invalid packet structure"

        # Verify signature
        if not self._verify_signature(packet, expected_signature):
            return False, "Signature verification failed - packet may have been tampered with"

        # Check packet is sealed
        if not packet.get('is_sealed', False):
            return False, "Packet is not sealed - cannot execute unsealed packets"

        # Check packet has not expired
        if self._is_packet_expired(packet):
            return False, "Packet has expired"

        return True, None

    def validate_interfaces(
        self,
        required_interfaces: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate all required interfaces exist and are healthy

        Args:
            required_interfaces: List of interface IDs required for execution

        Returns:
            (all_valid, error_message)
        """
        missing_interfaces = []
        unhealthy_interfaces = []

        for interface_id in required_interfaces:
            # Check interface exists
            if interface_id not in self.interface_registry:
                missing_interfaces.append(interface_id)
                continue

            # Check interface health
            health = self.interface_registry[interface_id]
            if not health.is_healthy():
                unhealthy_interfaces.append(interface_id)

        # Report missing interfaces
        if missing_interfaces:
            return False, f"Missing interfaces: {', '.join(missing_interfaces)}"

        # Report unhealthy interfaces
        if unhealthy_interfaces:
            return False, f"Unhealthy interfaces: {', '.join(unhealthy_interfaces)}"

        return True, None

    def validate_permissions(
        self,
        packet: Dict,
        authority_level: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate execution permissions

        Args:
            packet: Execution packet
            authority_level: Current authority level

        Returns:
            (is_authorized, error_message)
        """
        required_authority = packet.get('required_authority', 'none')

        # Authority hierarchy: none < read_only < limited < standard < elevated
        authority_hierarchy = {
            'none': 0,
            'read_only': 1,
            'limited': 2,
            'standard': 3,
            'elevated': 4
        }

        current_level = authority_hierarchy.get(authority_level, 0)
        required_level = authority_hierarchy.get(required_authority, 0)

        if current_level < required_level:
            return False, f"Insufficient authority: have '{authority_level}', need '{required_authority}'"

        return True, None

    def validate_resources(
        self,
        packet: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate resource availability

        Args:
            packet: Execution packet

        Returns:
            (resources_available, error_message)
        """
        # Check estimated resource requirements
        estimated_memory_mb = packet.get('estimated_memory_mb', 0)
        estimated_disk_mb = packet.get('estimated_disk_mb', 0)
        estimated_duration_sec = packet.get('estimated_duration_sec', 0)

        # Simple resource checks (in production, would check actual system resources)
        if estimated_memory_mb > 1000:  # 1GB limit
            return False, f"Estimated memory usage ({estimated_memory_mb}MB) exceeds limit"

        if estimated_disk_mb > 10000:  # 10GB limit
            return False, f"Estimated disk usage ({estimated_disk_mb}MB) exceeds limit"

        if estimated_duration_sec > 3600:  # 1 hour limit
            return False, f"Estimated duration ({estimated_duration_sec}s) exceeds limit"

        return True, None

    def register_interface(self, health: InterfaceHealth):
        """Register an interface with its health status"""
        self.interface_registry[health.interface_id] = health

    def update_interface_health(self, interface_id: str, health: InterfaceHealth):
        """Update health status of an interface"""
        self.interface_registry[interface_id] = health

    def get_interface_status(self) -> InterfaceStatus:
        """Get overall interface status"""
        status = InterfaceStatus()
        for health in self.interface_registry.values():
            status.add_interface(health)
        return status

    def _validate_packet_structure(self, packet: Dict) -> bool:
        """Validate packet has required fields"""
        required_fields = [
            'packet_id',
            'scope_hash',
            'execution_graph',
            'is_sealed',
            'signature'
        ]

        for field in required_fields:
            if field not in packet:
                return False

        return True

    def _verify_signature(self, packet: Dict, expected_signature: str) -> bool:
        """Verify packet signature"""
        # Get packet signature
        packet_signature = packet.get('signature', '')

        # Compare signatures
        return packet_signature == expected_signature

    def _is_packet_expired(self, packet: Dict) -> bool:
        """Check if packet has expired"""
        # Check if packet has expiration time
        expiration_time = packet.get('expiration_time')
        if not expiration_time:
            return False

        # Parse expiration time
        try:
            expiration_dt = datetime.fromisoformat(expiration_time)
            return datetime.now(timezone.utc) > expiration_dt
        except (ValueError, TypeError):
            return False

    def validate_all(
        self,
        packet: Dict,
        expected_signature: str,
        authority_level: str
    ) -> Tuple[bool, List[str]]:
        """
        Run all validation checks

        Args:
            packet: Execution packet
            expected_signature: Expected signature
            authority_level: Current authority level

        Returns:
            (all_valid, list_of_errors)
        """
        errors = []

        # Validate packet
        valid, error = self.validate_packet(packet, expected_signature)
        if not valid:
            errors.append(f"Packet validation: {error}")

        # Validate interfaces
        required_interfaces = packet.get('required_interfaces', [])
        valid, error = self.validate_interfaces(required_interfaces)
        if not valid:
            errors.append(f"Interface validation: {error}")

        # Validate permissions
        valid, error = self.validate_permissions(packet, authority_level)
        if not valid:
            errors.append(f"Permission validation: {error}")

        # Validate resources
        valid, error = self.validate_resources(packet)
        if not valid:
            errors.append(f"Resource validation: {error}")

        return len(errors) == 0, errors
