"""
Adapter Contract

Defines the interface that all sensor/robot adapters MUST implement.

CRITICAL: Adapters are EXECUTION TARGETS only. They:
- CANNOT decide
- CANNOT gate
- CANNOT authorize
- MUST only execute validated ExecutionPackets
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .execution_packet_extension import DeviceExecutionPacket

import logging

logger = logging.getLogger(__name__)


class AdapterCapability(Enum):
    """Adapter capability types"""
    READ_ONLY = "read_only"  # Sensors only
    ACTUATION = "actuation"  # Actuators only
    MIXED = "mixed"  # Both sensors and actuators


@dataclass
class SafetyLimits:
    """Safety limits for adapter"""

    # Physical limits
    max_velocity: Optional[float] = None  # m/s or rad/s
    max_force: Optional[float] = None  # N
    max_torque: Optional[float] = None  # Nm
    max_acceleration: Optional[float] = None  # m/s²

    # Operational limits
    max_temperature: Optional[float] = None  # °C
    max_current: Optional[float] = None  # A
    max_voltage: Optional[float] = None  # V

    # Rate limits
    max_commands_per_second: float = 10.0
    min_command_interval_ms: float = 100.0

    # Kill conditions (any trigger emergency stop)
    kill_conditions: List[str] = None

    def __post_init__(self):
        if self.kill_conditions is None:
            self.kill_conditions = [
                "temperature_exceeded",
                "force_exceeded",
                "communication_lost",
                "checksum_failed",
                "unauthorized_command"
            ]

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "max_velocity": self.max_velocity,
            "max_force": self.max_force,
            "max_torque": self.max_torque,
            "max_acceleration": self.max_acceleration,
            "max_temperature": self.max_temperature,
            "max_current": self.max_current,
            "max_voltage": self.max_voltage,
            "max_commands_per_second": self.max_commands_per_second,
            "min_command_interval_ms": self.min_command_interval_ms,
            "kill_conditions": self.kill_conditions
        }


@dataclass
class TelemetrySchema:
    """Schema for telemetry data"""

    # Required fields
    required_fields: List[str]

    # Field types
    field_types: Dict[str, str]

    # Field ranges (for validation)
    field_ranges: Dict[str, tuple]

    # Update frequency
    update_frequency_hz: float

    def validate(self, telemetry: Dict) -> tuple[bool, List[str]]:
        """
        Validate telemetry data against schema.

        Returns:
            (is_valid, errors)
        """
        errors = []

        # Check required fields
        for field in self.required_fields:
            if field not in telemetry:
                errors.append(f"Missing required field: {field}")

        # Check field types
        for field, expected_type in self.field_types.items():
            if field in telemetry:
                actual_type = type(telemetry[field]).__name__
                if actual_type != expected_type:
                    errors.append(f"Field {field}: expected {expected_type}, got {actual_type}")

        # Check field ranges
        for field, (min_val, max_val) in self.field_ranges.items():
            if field in telemetry:
                value = telemetry[field]
                if not (min_val <= value <= max_val):
                    errors.append(f"Field {field}: value {value} out of range [{min_val}, {max_val}]")

        return len(errors) == 0, errors


@dataclass
class CommandSchema:
    """Schema for command data"""

    # Allowed actions
    allowed_actions: List[str]

    # Parameter schemas per action
    parameter_schemas: Dict[str, Dict[str, Any]]

    # Preconditions per action
    preconditions: Dict[str, List[str]]

    def validate(self, command: Dict) -> tuple[bool, List[str]]:
        """
        Validate command against schema.

        Returns:
            (is_valid, errors)
        """
        errors = []

        # Check action
        action = command.get('action')
        if not action:
            errors.append("Missing action field")
            return False, errors

        if action not in self.allowed_actions:
            errors.append(f"Action {action} not in allowed actions: {self.allowed_actions}")
            return False, errors

        # Check parameters
        if action in self.parameter_schemas:
            param_schema = self.parameter_schemas[action]
            params = command.get('parameters', {})

            for param_name, param_spec in param_schema.items():
                if param_spec.get('required', False) and param_name not in params:
                    errors.append(f"Missing required parameter: {param_name}")

                if param_name in params:
                    value = params[param_name]

                    # Type check
                    expected_type = param_spec.get('type')
                    if expected_type and type(value).__name__ != expected_type:
                        errors.append(f"Parameter {param_name}: expected {expected_type}, got {type(value).__name__}")

                    # Range check
                    if 'min' in param_spec and value < param_spec['min']:
                        errors.append(f"Parameter {param_name}: {value} < min {param_spec['min']}")
                    if 'max' in param_spec and value > param_spec['max']:
                        errors.append(f"Parameter {param_name}: {value} > max {param_spec['max']}")

        return len(errors) == 0, errors


@dataclass
class AdapterManifest:
    """Adapter manifest describing capabilities and constraints"""

    # Identity
    adapter_id: str
    adapter_type: str  # e.g., "robot_arm", "camera", "gripper"
    version: str

    # Capabilities
    capability: AdapterCapability

    # Schemas
    telemetry_schema: TelemetrySchema
    command_schema: Optional[CommandSchema]  # None for read-only

    # Safety
    safety_limits: SafetyLimits

    # Security
    requires_signature: bool = True
    requires_nonce: bool = True
    replay_window_seconds: float = 30.0

    # Metadata
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "adapter_id": self.adapter_id,
            "adapter_type": self.adapter_type,
            "version": self.version,
            "capability": self.capability.value,
            "telemetry_schema": {
                "required_fields": self.telemetry_schema.required_fields,
                "field_types": self.telemetry_schema.field_types,
                "field_ranges": self.telemetry_schema.field_ranges,
                "update_frequency_hz": self.telemetry_schema.update_frequency_hz
            },
            "command_schema": {
                "allowed_actions": self.command_schema.allowed_actions,
                "parameter_schemas": self.command_schema.parameter_schemas,
                "preconditions": self.command_schema.preconditions
            } if self.command_schema else None,
            "safety_limits": self.safety_limits.to_dict(),
            "requires_signature": self.requires_signature,
            "requires_nonce": self.requires_nonce,
            "replay_window_seconds": self.replay_window_seconds,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number
        }


class AdapterAPI(ABC):
    """
    Abstract base class for all adapters.

    CRITICAL CONSTRAINTS:
    - Adapters are EXECUTION TARGETS only
    - NO free-form natural language
    - NO tool calls
    - ONLY validated ExecutionPackets
    """

    def __init__(self, manifest: AdapterManifest):
        """
        Initialize adapter.

        Args:
            manifest: Adapter manifest
        """
        self.manifest = manifest
        self.last_command_time = 0.0
        self.command_count = 0
        self.is_emergency_stopped = False

    @abstractmethod
    def get_manifest(self) -> AdapterManifest:
        """
        Get adapter manifest.

        Returns:
            AdapterManifest
        """
        pass

    @abstractmethod
    def read_telemetry(self) -> Dict:
        """
        Read current telemetry from device.

        Returns:
            Telemetry dictionary with:
            - timestamp: float (Unix timestamp)
            - device_id: str
            - state_vector: Dict (device-specific state)
            - error_codes: List[str]
            - health: str ("healthy", "degraded", "failed")
            - checksum: str (SHA-256 of state_vector)

        MUST NOT:
        - Accept any parameters
        - Modify device state
        - Execute commands
        """
        pass

    @abstractmethod
    def execute_command(self, execution_packet: 'DeviceExecutionPacket') -> Dict:
        """
        Execute command from validated ExecutionPacket.

        Args:
            execution_packet: Validated DeviceExecutionPacket

        Returns:
            Execution result with:
            - success: bool
            - telemetry: Dict (post-execution telemetry)
            - error: Optional[str]

        MUST:
        - Validate packet signature
        - Validate authority + gates
        - Validate command against schema
        - Check rate limits
        - Check safety limits
        - Emit audit log

        MUST NOT:
        - Accept free-form commands
        - Accept natural language
        - Bypass validation
        """
        pass

    @abstractmethod
    def emergency_stop(self) -> bool:
        """
        Execute emergency stop.

        Returns:
            True if successful

        MUST:
        - Immediately halt all motion
        - Set emergency_stopped flag
        - Emit emergency stop event
        - Return to safe state
        """
        pass

    @abstractmethod
    def heartbeat(self) -> Dict:
        """
        Send heartbeat and get status.

        Returns:
            Status dictionary with:
            - alive: bool
            - uptime_seconds: float
            - last_command_time: float
            - command_count: int
            - is_emergency_stopped: bool
        """
        pass

    def check_rate_limit(self) -> tuple[bool, str]:
        """
        Check if command rate limit is satisfied.

        Returns:
            (allowed, reason)
        """
        current_time = time.time()
        time_since_last = (current_time - self.last_command_time) * 1000  # ms

        if time_since_last < self.manifest.safety_limits.min_command_interval_ms:
            return False, f"Rate limit: {time_since_last:.1f}ms < {self.manifest.safety_limits.min_command_interval_ms}ms"

        return True, "OK"

    def validate_safety_limits(self, command: Dict) -> tuple[bool, List[str]]:
        """
        Validate command against safety limits.

        Returns:
            (is_safe, violations)
        """
        violations = []

        params = command.get('parameters', {})
        limits = self.manifest.safety_limits

        # Check velocity
        if 'velocity' in params and limits.max_velocity:
            if abs(params['velocity']) > limits.max_velocity:
                violations.append(f"Velocity {params['velocity']} exceeds limit {limits.max_velocity}")

        # Check force
        if 'force' in params and limits.max_force:
            if abs(params['force']) > limits.max_force:
                violations.append(f"Force {params['force']} exceeds limit {limits.max_force}")

        # Check torque
        if 'torque' in params and limits.max_torque:
            if abs(params['torque']) > limits.max_torque:
                violations.append(f"Torque {params['torque']} exceeds limit {limits.max_torque}")

        # Check acceleration
        if 'acceleration' in params and limits.max_acceleration:
            if abs(params['acceleration']) > limits.max_acceleration:
                violations.append(f"Acceleration {params['acceleration']} exceeds limit {limits.max_acceleration}")

        return len(violations) == 0, violations
