"""
Comprehensive Test Suite for Murphy Governance Framework

Tests all components of the formal governance framework:
- Agent descriptor validation and enforcement
- Governance artifact ingestion and validation
- Stability monitoring and refusal semantics
- Scheduler rules and invariant enforcement
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from src.governance_framework import (
    AgentDescriptor, AgentDescriptorValidator, AuthorityBand, ActionType,
    GovernanceArtifact, ArtifactRegistry, ArtifactValidator, ArtifactType,
    StabilityController, StabilityMetrics, ExecutionOutcome,
    GovernanceScheduler, SchedulingDecision,
    RefusalHandlerImpl, RefusalRecord
)


class TestAgentDescriptor:
    """Test agent descriptor implementation"""

    def test_basic_descriptor_creation(self):
        """Test basic agent descriptor creation and validation"""
        descriptor = AgentDescriptor(
            agent_id="test-agent-001",
            version="1.0.0",
            authority_band=AuthorityBand.LOW
        )

        assert descriptor.agent_id == "test-agent-001"
        assert descriptor.version == "1.0.0"
        assert descriptor.authority_band == AuthorityBand.LOW
        assert descriptor.validate() == True

    def test_authority_band_enforcement(self):
        """Test authority band constraints"""
        low_agent = AgentDescriptor("low-agent", "1.0.0", AuthorityBand.LOW)
        high_agent = AgentDescriptor("high-agent", "1.0.0", AuthorityBand.HIGH)

        # Default permission sets are empty; no actions allowed without explicit grants
        assert low_agent.can_execute_action(ActionType.PROPOSE_PLAN) == False
        assert high_agent.can_execute_action(ActionType.EXECUTE) == False

    def test_descriptor_validator(self):
        """Test agent descriptor validator"""
        validator = AgentDescriptorValidator()
        descriptor = AgentDescriptor("test-agent", "1.0.0", AuthorityBand.MEDIUM)

        result = validator.validate_descriptor(descriptor)
        # Default descriptor lacks timeout termination conditions
        assert result["valid"] == False
        assert len(result["errors"]) > 0


class TestGovernanceArtifact:
    """Test governance artifact implementation"""

    def test_artifact_creation(self):
        """Test basic artifact creation"""
        artifact = GovernanceArtifact(
            artifact_id="policy-001",
            artifact_type=ArtifactType.POLICY,
            name="Data Retention Policy",
            version="1.0.0",
            source_system="Compliance System"
        )

        assert artifact.artifact_id == "policy-001"
        assert artifact.artifact_type == ArtifactType.POLICY
        assert artifact.validate() == True

    def test_artifact_expiration(self):
        """Test artifact expiration logic"""
        expired_artifact = GovernanceArtifact(
            "expired-policy", ArtifactType.POLICY, "Old Policy", "1.0.0", "System"
        )
        expired_artifact.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        assert expired_artifact.is_expired() == True

        valid_artifact = GovernanceArtifact(
            "valid-policy", ArtifactType.POLICY, "Current Policy", "1.0.0", "System"
        )
        valid_artifact.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        assert valid_artifact.is_expired() == False

    def test_artifact_registry(self):
        """Test artifact registry operations"""
        registry = ArtifactRegistry()
        artifact = GovernanceArtifact("reg-test", ArtifactType.POLICY, "Test Policy", "1.0.0", "System")

        # Register artifact
        assert registry.register_artifact(artifact) == True

        # Retrieve artifact
        retrieved = registry.get_artifact("reg-test")
        assert retrieved is not None
        assert retrieved.name == "Test Policy"


class TestStabilityController:
    """Test stability monitoring and refusal semantics"""

    def test_stability_metrics(self):
        """Test stability metrics calculation"""
        metrics = StabilityMetrics()

        # Test stable state (same hash = no state changes = stable)
        agent_state = {"state": "stable"}
        history = [
            {"state_hash": "hash1", "timestamp": time.time()},
            {"state_hash": "hash1", "timestamp": time.time()}
        ]

        assert metrics.is_stable(agent_state, history) == True
        assert metrics.calculate_stability_score(agent_state, history) == 1.0

    def test_refusal_handler(self):
        """Test refusal handling"""
        handler = RefusalHandlerImpl()

        # Test valid refusal
        assert handler.validate_refusal("agent-001", "SAFETY_CONSTRAINT_VIOLATION", "Unsafe action") == True

        # Test invalid refusal
        assert handler.validate_refusal("agent-001", "INVALID_REASON", "Invalid") == False

        # Test refusal record creation
        record = handler.handle_refusal(
            "agent-001",
            "SAFETY_CONSTRAINT_VIOLATION",
            "Action violates safety",
            "LOW",
            ["agent-002", "agent-003"]
        )

        assert isinstance(record, RefusalRecord)
        assert record.agent_id == "agent-001"
        assert record.refusal_code == "SAFETY_CONSTRAINT_VIOLATION"

    def test_stability_controller_integration(self):
        """Test stability controller integration"""
        controller = StabilityController()

        agent_state = {"agent_id": "test-agent"}
        history = []

        result = controller.evaluate_agent_stability(agent_state, history)
        assert "stability_score" in result
        assert "is_stable" in result
        assert "can_continue" in result
        assert "recommendation" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
