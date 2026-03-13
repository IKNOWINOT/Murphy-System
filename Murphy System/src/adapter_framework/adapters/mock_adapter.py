"""
Mock Adapter

Simulated device adapter for testing.

Simulates:
- Telemetry generation
- Command execution
- Error conditions
- Safety limits
"""

import hashlib
import json
import logging
import time
from typing import Dict

from ..adapter_contract import (
    AdapterAPI,
    AdapterCapability,
    AdapterManifest,
    CommandSchema,
    SafetyLimits,
    TelemetrySchema,
)
from ..execution_packet_extension import DeviceExecutionPacket

logger = logging.getLogger("adapter_framework.adapters.mock_adapter")


class MockAdapter(AdapterAPI):
    """
    Mock adapter for testing.

    Simulates a simple robot arm with:
    - Position control
    - Velocity limits
    - Force limits
    - Temperature monitoring
    """

    def __init__(self, device_id: str = "mock_device_001"):
        """
        Initialize mock adapter.

        Args:
            device_id: Device ID
        """
        # Create manifest
        manifest = AdapterManifest(
            adapter_id=f"mock_adapter_{device_id}",
            adapter_type="robot_arm",
            version="1.0.0",
            capability=AdapterCapability.MIXED,
            telemetry_schema=TelemetrySchema(
                required_fields=["position", "velocity", "temperature"],
                field_types={
                    "position": "float",
                    "velocity": "float",
                    "temperature": "float"
                },
                field_ranges={
                    "position": (-180.0, 180.0),
                    "velocity": (-10.0, 10.0),
                    "temperature": (0.0, 100.0)
                },
                update_frequency_hz=10.0
            ),
            command_schema=CommandSchema(
                allowed_actions=["move_to", "set_velocity", "stop", "reset"],
                parameter_schemas={
                    "move_to": {
                        "position": {"type": "float", "min": -180.0, "max": 180.0, "required": True},
                        "velocity": {"type": "float", "min": 0.1, "max": 10.0, "required": False}
                    },
                    "set_velocity": {
                        "velocity": {"type": "float", "min": -10.0, "max": 10.0, "required": True}
                    },
                    "stop": {},
                    "reset": {}
                },
                preconditions={
                    "move_to": ["device_ready", "no_errors"],
                    "set_velocity": ["device_ready"],
                    "stop": [],
                    "reset": []
                }
            ),
            safety_limits=SafetyLimits(
                max_velocity=10.0,
                max_force=100.0,
                max_acceleration=5.0,
                max_temperature=80.0,
                max_commands_per_second=10.0,
                min_command_interval_ms=100.0
            ),
            manufacturer="InonI LLC",
            model="MockArm-1000",
            serial_number="MOCK-001"
        )

        super().__init__(manifest)

        # Device state
        self.device_id = device_id
        self.position = 0.0
        self.velocity = 0.0
        self.temperature = 25.0
        self.error_codes = []
        self.health = "healthy"
        self.sequence_number = 0
        self.start_time = time.time()

    def get_manifest(self) -> AdapterManifest:
        """Get adapter manifest"""
        return self.manifest

    def read_telemetry(self) -> Dict:
        """Read current telemetry"""
        # Update state (simulate physics)
        self._update_state()

        # Create state vector
        state_vector = {
            "position": self.position,
            "velocity": self.velocity,
            "temperature": self.temperature
        }

        # Compute checksum
        serialized = json.dumps(state_vector, sort_keys=True)
        checksum = hashlib.sha256(serialized.encode()).hexdigest()

        # Increment sequence
        self.sequence_number += 1

        return {
            "timestamp": time.time(),
            "device_id": self.device_id,
            "state_vector": state_vector,
            "error_codes": self.error_codes.copy(),
            "health": self.health,
            "checksum": checksum,
            "sequence_number": self.sequence_number,
            "metadata": {
                "firmware_version": "1.0.0",
                "uptime_seconds": time.time() - self.start_time,
                "temperature_celsius": self.temperature
            }
        }

    def execute_command(self, execution_packet: DeviceExecutionPacket) -> Dict:
        """Execute command from packet"""
        # Check rate limit
        allowed, reason = self.check_rate_limit()
        if not allowed:
            return {
                "success": False,
                "error": reason
            }

        # Check safety limits
        is_safe, violations = self.validate_safety_limits(execution_packet.command)
        if not is_safe:
            return {
                "success": False,
                "error": f"Safety violation: {violations}"
            }

        # Extract command
        action = execution_packet.command['action']
        parameters = execution_packet.command.get('parameters', {})

        # Execute action
        try:
            if action == "move_to":
                self._move_to(parameters)
            elif action == "set_velocity":
                self._set_velocity(parameters)
            elif action == "stop":
                self._stop()
            elif action == "reset":
                self._reset()
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}"
                }

            # Update command tracking
            self.last_command_time = time.time()
            self.command_count += 1

            # Read post-execution telemetry
            telemetry = self.read_telemetry()

            return {
                "success": True,
                "telemetry": telemetry,
                "error": None
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                "success": False,
                "error": str(exc)
            }

    def emergency_stop(self) -> bool:
        """Execute emergency stop"""
        logger.info(f"[EMERGENCY STOP] {self.device_id}")

        # Stop all motion
        self.velocity = 0.0
        self.is_emergency_stopped = True
        self.error_codes.append("emergency_stop")
        self.health = "degraded"

        return True

    def heartbeat(self) -> Dict:
        """Send heartbeat"""
        return {
            "alive": True,
            "uptime_seconds": time.time() - self.start_time,
            "last_command_time": self.last_command_time,
            "command_count": self.command_count,
            "is_emergency_stopped": self.is_emergency_stopped
        }

    def _update_state(self):
        """Update device state (simulate physics)"""
        # Update position based on velocity
        dt = 0.1  # 100ms
        self.position += self.velocity * dt

        # Clamp position
        self.position = max(-180.0, min(180.0, self.position))

        # Update temperature (increases with motion)
        if abs(self.velocity) > 0.1:
            self.temperature += 0.1
        else:
            self.temperature = max(25.0, self.temperature - 0.05)

        # Check for errors
        self.error_codes = []

        if self.temperature > self.manifest.safety_limits.max_temperature:
            self.error_codes.append("temperature_exceeded")
            self.health = "degraded"
        else:
            self.health = "healthy"

    def _move_to(self, parameters: Dict):
        """Move to position"""
        target_position = parameters['position']
        velocity = parameters.get('velocity', 1.0)

        # Set velocity towards target
        if target_position > self.position:
            self.velocity = velocity
        elif target_position < self.position:
            self.velocity = -velocity
        else:
            self.velocity = 0.0

    def _set_velocity(self, parameters: Dict):
        """Set velocity"""
        self.velocity = parameters['velocity']

    def _stop(self):
        """Stop motion"""
        self.velocity = 0.0

    def _reset(self):
        """Reset to initial state"""
        self.position = 0.0
        self.velocity = 0.0
        self.temperature = 25.0
        self.error_codes = []
        self.health = "healthy"
        self.is_emergency_stopped = False
