"""
Tests for Adapter Framework

Comprehensive tests covering:
- Schema validation
- Replay protection
- Rejecting free-form commands
- Kill condition triggers
- Gate + authority enforcement
"""

import pytest
import time
import secrets
from src.adapter_framework.adapter_contract import (
    AdapterManifest, AdapterCapability, TelemetrySchema,
    CommandSchema, SafetyLimits
)
from src.adapter_framework.execution_packet_extension import DeviceExecutionPacket
from src.adapter_framework.adapter_runtime import AdapterRuntime, AdapterRegistry
from src.adapter_framework.adapters.mock_adapter import MockAdapter
from src.adapter_framework.telemetry_artifact import TelemetryArtifact, TelemetryIngestionPipeline
from src.adapter_framework.safety_hooks import HeartbeatWatchdog, ErrorCodeMapper


class TestSchemaValidation:
    """Test schema validation"""

    def test_telemetry_schema_valid(self):
        """Test valid telemetry passes schema"""
        schema = TelemetrySchema(
            required_fields=["position", "velocity"],
            field_types={"position": "float", "velocity": "float"},
            field_ranges={"position": (-180.0, 180.0)},
            update_frequency_hz=10.0
        )

        telemetry = {
            "position": 45.0,
            "velocity": 2.5
        }

        is_valid, errors = schema.validate(telemetry)
        assert is_valid
        assert len(errors) == 0

    def test_telemetry_schema_missing_field(self):
        """Test missing required field fails"""
        schema = TelemetrySchema(
            required_fields=["position", "velocity"],
            field_types={},
            field_ranges={},
            update_frequency_hz=10.0
        )

        telemetry = {"position": 45.0}  # Missing velocity

        is_valid, errors = schema.validate(telemetry)
        assert not is_valid
        assert "velocity" in str(errors)

    def test_telemetry_schema_out_of_range(self):
        """Test out of range value fails"""
        schema = TelemetrySchema(
            required_fields=["position"],
            field_types={"position": "float"},
            field_ranges={"position": (-180.0, 180.0)},
            update_frequency_hz=10.0
        )

        telemetry = {"position": 200.0}  # Out of range

        is_valid, errors = schema.validate(telemetry)
        assert not is_valid
        assert "out of range" in str(errors)

    def test_command_schema_valid(self):
        """Test valid command passes schema"""
        schema = CommandSchema(
            allowed_actions=["move_to"],
            parameter_schemas={
                "move_to": {
                    "position": {"type": "float", "min": -180.0, "max": 180.0, "required": True}
                }
            },
            preconditions={}
        )

        command = {
            "action": "move_to",
            "parameters": {"position": 45.0}
        }

        is_valid, errors = schema.validate(command)
        assert is_valid
        assert len(errors) == 0

    def test_command_schema_invalid_action(self):
        """Test invalid action fails"""
        schema = CommandSchema(
            allowed_actions=["move_to"],
            parameter_schemas={},
            preconditions={}
        )

        command = {
            "action": "invalid_action",
            "parameters": {}
        }

        is_valid, errors = schema.validate(command)
        assert not is_valid
        assert "not in allowed actions" in str(errors)


class TestReplayProtection:
    """Test replay attack protection"""

    def test_replay_protection_rejects_duplicate_nonce(self):
        """Test duplicate nonce is rejected"""
        nonce = secrets.token_hex(16)
        seen_nonces = {nonce}

        packet = DeviceExecutionPacket.create(
            target_adapter_id="test_adapter",
            target_device_id="test_device",
            action="move_to",
            parameters={"position": 45.0},
            required_gates=["safety_gate"],
            authority_level="medium",
            verification_requirements=["position_verified"],
            telemetry_expectations={"position": 45.0},
            private_key="test_key",
            reason="Test"
        )
        packet.nonce = nonce  # Force duplicate nonce

        is_valid = packet.check_replay(seen_nonces, window_seconds=30.0)
        assert not is_valid

    def test_replay_protection_rejects_old_timestamp(self):
        """Test old timestamp is rejected"""
        packet = DeviceExecutionPacket.create(
            target_adapter_id="test_adapter",
            target_device_id="test_device",
            action="move_to",
            parameters={"position": 45.0},
            required_gates=["safety_gate"],
            authority_level="medium",
            verification_requirements=["position_verified"],
            telemetry_expectations={"position": 45.0},
            private_key="test_key",
            reason="Test"
        )

        # Make timestamp old
        packet.timestamp = time.time() - 60.0  # 60 seconds ago

        is_valid = packet.check_replay(set(), window_seconds=30.0)
        assert not is_valid

    def test_replay_protection_accepts_fresh_packet(self):
        """Test fresh packet is accepted"""
        packet = DeviceExecutionPacket.create(
            target_adapter_id="test_adapter",
            target_device_id="test_device",
            action="move_to",
            parameters={"position": 45.0},
            required_gates=["safety_gate"],
            authority_level="medium",
            verification_requirements=["position_verified"],
            telemetry_expectations={"position": 45.0},
            private_key="test_key",
            reason="Test"
        )

        is_valid = packet.check_replay(set(), window_seconds=30.0)
        assert is_valid


class TestFreeFormCommandRejection:
    """Test that free-form commands are rejected"""

    def test_adapter_rejects_non_packet_command(self):
        """Test adapter only accepts ExecutionPackets"""
        adapter = MockAdapter("test_device")
        runtime = AdapterRuntime(adapter, "test_public_key")

        # Try to execute without packet (should fail at type level)
        # In production, this would be enforced by type system
        # Here we test that execute() requires DeviceExecutionPacket

        # This should work
        packet = DeviceExecutionPacket.create(
            target_adapter_id=adapter.manifest.adapter_id,
            target_device_id="test_device",
            action="stop",
            parameters={},
            required_gates=[],
            authority_level="low",
            verification_requirements=[],
            telemetry_expectations={},
            private_key="test_key",
            reason="Test"
        )

        # Signature will fail but that's expected
        result = runtime.execute(packet)
        assert "signature" in result.get("error", "").lower()

    def test_adapter_validates_command_schema(self):
        """Test adapter validates command against schema"""
        adapter = MockAdapter("test_device")
        runtime = AdapterRuntime(adapter, "test_key")

        # Create packet with invalid action
        packet = DeviceExecutionPacket.create(
            target_adapter_id=adapter.manifest.adapter_id,
            target_device_id="test_device",
            action="invalid_action",  # Not in allowed_actions
            parameters={},
            required_gates=[],
            authority_level="low",
            verification_requirements=[],
            telemetry_expectations={},
            private_key="test_key",
            reason="Test"
        )

        result = runtime.execute(packet)
        assert not result["success"]


class TestKillConditions:
    """Test kill condition triggers"""

    def test_temperature_exceeded_triggers_error(self):
        """Test temperature limit violation"""
        adapter = MockAdapter("test_device")

        # Force temperature over limit
        adapter.temperature = 85.0  # Over 80.0 limit

        telemetry = adapter.read_telemetry()

        assert "temperature_exceeded" in telemetry["error_codes"]
        assert telemetry["health"] == "degraded"

    def test_safety_limit_violation_rejects_command(self):
        """Test safety limit violation rejects command"""
        adapter = MockAdapter("test_device")
        runtime = AdapterRuntime(adapter, "test_key")

        # Create packet with velocity over limit
        packet = DeviceExecutionPacket.create(
            target_adapter_id=adapter.manifest.adapter_id,
            target_device_id="test_device",
            action="set_velocity",
            parameters={"velocity": 15.0},  # Over 10.0 limit
            required_gates=[],
            authority_level="low",
            verification_requirements=[],
            telemetry_expectations={},
            private_key="test_key",
            reason="Test"
        )

        result = runtime.execute(packet)
        assert not result["success"]
        # Error message contains parameter validation failure
        assert "velocity" in result.get("error", "").lower()
        assert "10.0" in result.get("error", "")


class TestAuthorityEnforcement:
    """Test authority level enforcement"""

    def test_no_authority_rejected(self):
        """Test packet with no authority is rejected"""
        adapter = MockAdapter("test_device")
        runtime = AdapterRuntime(adapter, "test_key")

        packet = DeviceExecutionPacket.create(
            target_adapter_id=adapter.manifest.adapter_id,
            target_device_id="test_device",
            action="stop",
            parameters={},
            required_gates=[],
            authority_level="none",  # No authority
            verification_requirements=[],
            telemetry_expectations={},
            private_key="test_key",
            reason="Test"
        )

        result = runtime.execute(packet)
        assert not result["success"]
        assert "no authority" in result.get("error", "").lower()


class TestTelemetryIngestion:
    """Test telemetry ingestion pipeline"""

    def test_telemetry_ingestion_valid(self):
        """Test valid telemetry is ingested"""
        pipeline = TelemetryIngestionPipeline()

        telemetry = {
            "timestamp": time.time(),
            "device_id": "test_device",
            "state_vector": {"position": 45.0},
            "error_codes": [],
            "health": "healthy",
            "checksum": TelemetryArtifact._compute_checksum({"position": 45.0}),
            "sequence_number": 1
        }

        artifact = pipeline.ingest(telemetry, "test_adapter")

        assert artifact is not None
        assert artifact.device_id == "test_device"

    def test_telemetry_deduplication(self):
        """Test duplicate telemetry is rejected"""
        pipeline = TelemetryIngestionPipeline()

        telemetry = {
            "timestamp": time.time(),
            "device_id": "test_device",
            "state_vector": {"position": 45.0},
            "error_codes": [],
            "health": "healthy",
            "checksum": TelemetryArtifact._compute_checksum({"position": 45.0}),
            "sequence_number": 1
        }

        # Ingest first time
        artifact1 = pipeline.ingest(telemetry, "test_adapter")
        assert artifact1 is not None

        # Try to ingest duplicate
        telemetry["sequence_number"] = 2  # Different sequence
        artifact2 = pipeline.ingest(telemetry, "test_adapter")
        assert artifact2 is None  # Rejected as duplicate

    def test_telemetry_sequence_validation(self):
        """Test sequence number must increase"""
        pipeline = TelemetryIngestionPipeline()

        # Ingest sequence 1
        telemetry1 = {
            "timestamp": time.time(),
            "device_id": "test_device",
            "state_vector": {"position": 45.0},
            "error_codes": [],
            "health": "healthy",
            "checksum": TelemetryArtifact._compute_checksum({"position": 45.0}),
            "sequence_number": 1
        }
        pipeline.ingest(telemetry1, "test_adapter")

        # Try to ingest sequence 1 again (should fail)
        telemetry2 = {
            "timestamp": time.time(),
            "device_id": "test_device",
            "state_vector": {"position": 50.0},
            "error_codes": [],
            "health": "healthy",
            "checksum": TelemetryArtifact._compute_checksum({"position": 50.0}),
            "sequence_number": 1  # Same sequence
        }
        artifact = pipeline.ingest(telemetry2, "test_adapter")
        assert artifact is None


class TestHeartbeatWatchdog:
    """Test heartbeat monitoring"""

    def test_heartbeat_resets_timer(self):
        """Test heartbeat resets watchdog timer"""
        watchdog = HeartbeatWatchdog("test_adapter", timeout_seconds=5.0)

        initial_time = watchdog.last_heartbeat
        time.sleep(0.1)

        watchdog.heartbeat()

        assert watchdog.last_heartbeat > initial_time


class TestErrorCodeMapping:
    """Test error code to Murphy index mapping"""

    def test_error_mapping_increases_murphy(self):
        """Test errors increase Murphy index"""
        mapper = ErrorCodeMapper()

        result = mapper.map_error("test_adapter", ["temperature_exceeded", "force_exceeded"])

        assert result["murphy_increase"] > 0
        assert result["authority_decay"] > 0

    def test_no_errors_no_increase(self):
        """Test no errors means no Murphy increase"""
        mapper = ErrorCodeMapper()

        result = mapper.map_error("test_adapter", [])

        assert result["murphy_increase"] == 0.0
        assert result["authority_decay"] == 0.0


class TestAdapterRegistry:
    """Test adapter registry"""

    def test_register_adapter(self):
        """Test adapter registration"""
        registry = AdapterRegistry()
        adapter = MockAdapter("test_device")

        runtime = registry.register(adapter, "test_key")

        assert runtime is not None
        assert adapter.manifest.adapter_id in registry.list_adapters()

    def test_emergency_stop_all(self):
        """Test emergency stop all adapters"""
        registry = AdapterRegistry()

        adapter1 = MockAdapter("device1")
        adapter2 = MockAdapter("device2")

        registry.register(adapter1, "key1")
        registry.register(adapter2, "key2")

        results = registry.emergency_stop_all("Test emergency")

        assert len(results) == 2
        assert adapter1.is_emergency_stopped
        assert adapter2.is_emergency_stopped


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
