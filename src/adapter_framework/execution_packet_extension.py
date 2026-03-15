"""
Execution Packet Extension for Device Commands

Extends ExecutionPacket to support device actuation with strict validation.

CRITICAL: This is the ONLY way to send commands to devices.
"""

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceExecutionPacket:
    """
    Execution packet for device commands.

    CRITICAL CONSTRAINTS:
    - ONLY way to actuate devices
    - MUST be validated by Control Plane
    - MUST pass all gates
    - MUST have appropriate authority
    """

    # Packet identity
    packet_id: str
    timestamp: float

    # Target
    target_adapter_id: str
    target_device_id: str

    # Command (validated against adapter's command schema)
    command: Dict  # {action, parameters, timestamp, nonce}

    # Control Plane authorization
    required_gates: List[str]  # Gates that MUST pass
    authority_level: str  # "none", "low", "medium", "high", "full"

    # Verification
    verification_requirements: List[str]  # What must be verified
    telemetry_expectations: Dict  # Expected postconditions

    # Security
    signature: str  # Cryptographic signature
    nonce: str  # Unique nonce for replay protection

    # Execution
    timeout_seconds: float = 30.0
    max_retries: int = 0

    # Audit
    issued_by: str = "control_plane"
    reason: str = ""

    def __post_init__(self):
        """Validate packet"""
        # Validate authority level
        valid_authority = ["none", "low", "medium", "high", "full"]
        if self.authority_level not in valid_authority:
            raise ValueError(f"Invalid authority level: {self.authority_level}")

        # Validate command has required fields
        required_command_fields = ['action', 'parameters', 'timestamp', 'nonce']
        for field in required_command_fields:
            if field not in self.command:
                raise ValueError(f"Command missing required field: {field}")

        # Validate nonce matches
        if self.command['nonce'] != self.nonce:
            raise ValueError("Command nonce does not match packet nonce")

    def verify_signature(self, public_key: str) -> bool:
        """
        Verify packet signature.

        Args:
            public_key: Public key for verification

        Returns:
            True if signature valid
        """
        # Compute packet hash
        packet_data = {
            "packet_id": self.packet_id,
            "timestamp": self.timestamp,
            "target_adapter_id": self.target_adapter_id,
            "target_device_id": self.target_device_id,
            "command": self.command,
            "authority_level": self.authority_level,
            "nonce": self.nonce
        }

        import json
        serialized = json.dumps(packet_data, sort_keys=True)
        packet_hash = hashlib.sha256(serialized.encode()).hexdigest()

        # In production, use proper cryptographic signature verification
        # For now, simple hash comparison
        expected_signature = hashlib.sha256(f"{packet_hash}{public_key}".encode()).hexdigest()

        return self.signature == expected_signature

    def check_replay(self, seen_nonces: set, window_seconds: float = 30.0) -> bool:
        """
        Check for replay attack.

        Args:
            seen_nonces: Set of recently seen nonces
            window_seconds: Replay protection window

        Returns:
            True if not a replay
        """
        # Check if nonce already seen
        if self.nonce in seen_nonces:
            return False

        # Check timestamp freshness
        current_time = time.time()
        if abs(current_time - self.timestamp) > window_seconds:
            return False

        return True

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "packet_id": self.packet_id,
            "timestamp": self.timestamp,
            "target_adapter_id": self.target_adapter_id,
            "target_device_id": self.target_device_id,
            "command": self.command,
            "required_gates": self.required_gates,
            "authority_level": self.authority_level,
            "verification_requirements": self.verification_requirements,
            "telemetry_expectations": self.telemetry_expectations,
            "signature": self.signature,
            "nonce": self.nonce,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "issued_by": self.issued_by,
            "reason": self.reason
        }

    @staticmethod
    def create(
        target_adapter_id: str,
        target_device_id: str,
        action: str,
        parameters: Dict,
        required_gates: List[str],
        authority_level: str,
        verification_requirements: List[str],
        telemetry_expectations: Dict,
        private_key: str,
        reason: str = ""
    ) -> 'DeviceExecutionPacket':
        """
        Create a new DeviceExecutionPacket.

        Args:
            target_adapter_id: Target adapter ID
            target_device_id: Target device ID
            action: Action to execute
            parameters: Action parameters
            required_gates: Required gates
            authority_level: Authority level
            verification_requirements: Verification requirements
            telemetry_expectations: Expected postconditions
            private_key: Private key for signing
            reason: Reason for command

        Returns:
            DeviceExecutionPacket
        """
        # Generate unique identifiers
        packet_id = f"packet_{int(time.time() * 1000)}_{secrets.token_hex(8)}"
        nonce = secrets.token_hex(16)
        timestamp = time.time()

        # Create command
        command = {
            "action": action,
            "parameters": parameters,
            "timestamp": timestamp,
            "nonce": nonce
        }

        # Compute signature
        packet_data = {
            "packet_id": packet_id,
            "timestamp": timestamp,
            "target_adapter_id": target_adapter_id,
            "target_device_id": target_device_id,
            "command": command,
            "authority_level": authority_level,
            "nonce": nonce
        }

        import json
        serialized = json.dumps(packet_data, sort_keys=True)
        packet_hash = hashlib.sha256(serialized.encode()).hexdigest()
        signature = hashlib.sha256(f"{packet_hash}{private_key}".encode()).hexdigest()

        return DeviceExecutionPacket(
            packet_id=packet_id,
            timestamp=timestamp,
            target_adapter_id=target_adapter_id,
            target_device_id=target_device_id,
            command=command,
            required_gates=required_gates,
            authority_level=authority_level,
            verification_requirements=verification_requirements,
            telemetry_expectations=telemetry_expectations,
            signature=signature,
            nonce=nonce,
            issued_by="control_plane",
            reason=reason
        )
