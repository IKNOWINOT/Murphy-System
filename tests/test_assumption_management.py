"""
Tests for Assumption Management System

Tests:
- AssumptionRegistry functionality
- AssumptionValidator enforcement
- AssumptionBindingManager logic
- AssumptionLifecycleManager transitions
"""

import pytest
from datetime import datetime, timedelta

from src.supervisor_system.schemas import (
    AssumptionArtifact,
    AssumptionStatus,
    InvalidationSignal,
    InvalidationSource,
    ValidationEvidence,
    AssumptionBinding
)
from src.supervisor_system.assumption_management import (
    AssumptionRegistry,
    AssumptionValidator,
    AssumptionBindingManager,
    AssumptionLifecycleManager
)


class TestAssumptionRegistry:
    """Test AssumptionRegistry functionality."""

    def test_register_assumption(self):
        """Test registering a new assumption."""
        registry = AssumptionRegistry()

        assumption = AssumptionArtifact(
            assumption_id="test-001",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        retrieved = registry.get("test-001")
        assert retrieved is not None
        assert retrieved.assumption_id == "test-001"
        assert retrieved.description == "Test assumption"

    def test_cannot_register_self_validated(self):
        """Test that self-validated assumptions cannot be created."""
        registry = AssumptionRegistry()

        # Should raise ValueError during object creation
        with pytest.raises(ValueError, match="validated_by_self=True"):
            assumption = AssumptionArtifact(
                assumption_id="test-002",
                description="Self-validated assumption",
                source_artifact_id="hyp-001",
                confidence_if_true=0.9,
                confidence_if_false=0.3,
                status=AssumptionStatus.ACTIVE,
                created_at=datetime.now(),
                next_review_date=datetime.now() + timedelta(days=30),
                validated_by_self=True,  # INVALID
                requires_external_validation=True
            )

    def test_cannot_register_without_external_validation(self):
        """Test that assumptions without external validation cannot be created."""
        registry = AssumptionRegistry()

        # Should raise ValueError during object creation
        with pytest.raises(ValueError, match="requires_external_validation=True"):
            assumption = AssumptionArtifact(
                assumption_id="test-003",
                description="No external validation",
                source_artifact_id="hyp-001",
                confidence_if_true=0.9,
                confidence_if_false=0.3,
                status=AssumptionStatus.ACTIVE,
                created_at=datetime.now(),
                next_review_date=datetime.now() + timedelta(days=30),
                validated_by_self=False,
                requires_external_validation=False  # INVALID
            )

    def test_get_stale_assumptions(self):
        """Test retrieving stale assumptions."""
        registry = AssumptionRegistry()

        # Active assumption with past review date
        stale_assumption = AssumptionArtifact(
            assumption_id="test-004",
            description="Stale assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now() - timedelta(days=60),
            next_review_date=datetime.now() - timedelta(days=1),  # Past
            validated_by_self=False,
            requires_external_validation=True
        )

        # Active assumption with future review date
        fresh_assumption = AssumptionArtifact(
            assumption_id="test-005",
            description="Fresh assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),  # Future
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(stale_assumption)
        registry.register(fresh_assumption)

        stale = registry.get_stale()
        assert len(stale) == 1
        assert stale[0].assumption_id == "test-004"

    def test_add_binding(self):
        """Test adding bindings between assumptions and artifacts."""
        registry = AssumptionRegistry()

        assumption = AssumptionArtifact(
            assumption_id="test-006",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        binding = AssumptionBinding(
            assumption_id="test-006",
            hypothesis_id="hyp-001",
            execution_packet_id=None,
            is_critical=True,
            bound_at=datetime.now()
        )

        registry.add_binding(binding)

        assumptions = registry.get_by_artifact("hyp-001")
        assert len(assumptions) == 1
        assert assumptions[0].assumption_id == "test-006"

    def test_get_critical_assumptions(self):
        """Test retrieving critical assumptions for an artifact."""
        registry = AssumptionRegistry()

        assumption1 = AssumptionArtifact(
            assumption_id="test-007",
            description="Critical assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        assumption2 = AssumptionArtifact(
            assumption_id="test-008",
            description="Non-critical assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption1)
        registry.register(assumption2)

        binding1 = AssumptionBinding(
            assumption_id="test-007",
            hypothesis_id="hyp-001",
            execution_packet_id=None,
            is_critical=True,
            bound_at=datetime.now()
        )

        binding2 = AssumptionBinding(
            assumption_id="test-008",
            hypothesis_id="hyp-001",
            execution_packet_id=None,
            is_critical=False,
            bound_at=datetime.now()
        )

        registry.add_binding(binding1)
        registry.add_binding(binding2)

        critical = registry.get_critical_by_artifact("hyp-001")
        assert len(critical) == 1
        assert critical[0].assumption_id == "test-007"

    def test_get_statistics(self):
        """Test registry statistics."""
        registry = AssumptionRegistry()

        assumption1 = AssumptionArtifact(
            assumption_id="test-009",
            description="Active assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        assumption2 = AssumptionArtifact(
            assumption_id="test-010",
            description="Invalidated assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.INVALIDATED,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption1)
        registry.register(assumption2)

        stats = registry.get_statistics()
        assert stats["total_assumptions"] == 2
        assert stats["active"] == 1
        assert stats["invalidated"] == 1


class TestAssumptionValidator:
    """Test AssumptionValidator enforcement."""

    def test_reject_self_generated_evidence(self):
        """Test that self-generated evidence cannot be created."""
        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-011",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        # Self-generated evidence should raise ValueError during creation
        with pytest.raises(ValueError, match="must be external"):
            evidence = ValidationEvidence(
                evidence_id="ev-001",
                assumption_id="test-011",
                evidence_type="deterministic",
                description="Self-generated proof",
                confidence=0.95,
                source="internal",
                timestamp=datetime.now(),
                is_external=False  # INVALID
            )

    def test_accept_external_evidence(self):
        """Test that external evidence is accepted."""
        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-012",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        # External evidence
        evidence = ValidationEvidence(
            evidence_id="ev-002",
            assumption_id="test-012",
            evidence_type="supervisor",
            description="Supervisor confirmed",
            confidence=0.95,
            source="supervisor-001",
            timestamp=datetime.now(),
            is_external=True  # VALID
        )

        result = validator.validate_evidence("test-012", evidence)
        assert result is True

    def test_reject_low_confidence_evidence(self):
        """Test that low confidence evidence is rejected."""
        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-013",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        # Low confidence evidence
        evidence = ValidationEvidence(
            evidence_id="ev-003",
            assumption_id="test-013",
            evidence_type="api",
            description="API response",
            confidence=0.5,  # Below threshold
            source="external-api",
            timestamp=datetime.now(),
            is_external=True
        )

        result = validator.validate_evidence("test-013", evidence)
        assert result is False


class TestAssumptionBindingManager:
    """Test AssumptionBindingManager logic."""

    def test_bind_to_hypothesis(self):
        """Test binding assumption to hypothesis."""
        registry = AssumptionRegistry()
        manager = AssumptionBindingManager(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-014",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        binding = manager.bind_to_hypothesis("test-014", "hyp-001", is_critical=True)

        assert binding.assumption_id == "test-014"
        assert binding.hypothesis_id == "hyp-001"
        assert binding.is_critical is True

    def test_cannot_execute_with_invalidated_critical_assumption(self):
        """Test that artifacts cannot execute with invalidated critical assumptions."""
        registry = AssumptionRegistry()
        manager = AssumptionBindingManager(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-015",
            description="Critical assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.INVALIDATED,  # INVALIDATED
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)
        manager.bind_to_hypothesis("test-015", "hyp-001", is_critical=True)

        can_execute, reasons = manager.can_artifact_execute("hyp-001")

        assert can_execute is False
        assert len(reasons) > 0
        assert "INVALIDATED" in reasons[0]

    def test_can_execute_with_validated_assumptions(self):
        """Test that artifacts can execute with validated assumptions."""
        registry = AssumptionRegistry()
        manager = AssumptionBindingManager(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-016",
            description="Validated assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.VALIDATED,  # VALIDATED
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)
        manager.bind_to_hypothesis("test-016", "hyp-001", is_critical=True)

        can_execute, reasons = manager.can_artifact_execute("hyp-001")

        assert can_execute is True
        assert len(reasons) == 0


class TestAssumptionLifecycleManager:
    """Test AssumptionLifecycleManager transitions."""

    def test_mark_stale(self):
        """Test marking assumption as stale."""
        registry = AssumptionRegistry()
        manager = AssumptionLifecycleManager(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-017",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)
        manager.mark_stale("test-017")

        retrieved = registry.get("test-017")
        assert retrieved.status == AssumptionStatus.STALE

    def test_mark_invalidated(self):
        """Test marking assumption as invalidated."""
        registry = AssumptionRegistry()
        manager = AssumptionLifecycleManager(registry)

        assumption = AssumptionArtifact(
            assumption_id="test-018",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(),
            next_review_date=datetime.now() + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        signal = InvalidationSignal(
            signal_id="sig-001",
            assumption_id="test-018",
            source=InvalidationSource.TELEMETRY,
            reason="Telemetry contradicts assumption",
            confidence=0.9,
            severity="high",
            timestamp=datetime.now()
        )

        manager.mark_invalidated("test-018", signal)

        retrieved = registry.get("test-018")
        assert retrieved.status == AssumptionStatus.INVALIDATED
        assert len(retrieved.invalidation_signals) == 1

    def test_check_stale_assumptions(self):
        """Test automatic stale detection."""
        registry = AssumptionRegistry()
        manager = AssumptionLifecycleManager(registry)

        # Past review date
        assumption = AssumptionArtifact(
            assumption_id="test-019",
            description="Overdue assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now() - timedelta(days=60),
            next_review_date=datetime.now() - timedelta(days=1),  # Past
            validated_by_self=False,
            requires_external_validation=True
        )

        registry.register(assumption)

        stale_ids = manager.check_stale_assumptions()

        assert len(stale_ids) == 1
        assert "test-019" in stale_ids

        retrieved = registry.get("test-019")
        assert retrieved.status == AssumptionStatus.STALE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
