"""
Tests for Correction Loop

Tests:
- InvalidationDetector detection
- ConfidenceDecayer decay logic
- AuthorityDecayer decay logic
- ExecutionFreezer freezing logic
- ReExpansionTrigger re-expansion criteria
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.supervisor_system.schemas import (
    AssumptionArtifact,
    AssumptionStatus,
    InvalidationSignal,
    InvalidationSource
)
from src.supervisor_system.assumption_management import (
    AssumptionRegistry,
    AssumptionBindingManager,
    AssumptionLifecycleManager
)
from src.supervisor_system.correction_loop import (
    InvalidationDetector,
    ConfidenceDecayer,
    AuthorityDecayer,
    ExecutionFreezer,
    ReExpansionTrigger
)


class TestInvalidationDetector:
    """Test InvalidationDetector detection."""

    def test_detect_telemetry_invalidation(self):
        """Test detecting invalidation from telemetry."""
        registry = AssumptionRegistry()
        lifecycle = AssumptionLifecycleManager(registry)
        detector = InvalidationDetector(registry, lifecycle)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-001",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)

        # Detect invalidation
        telemetry = {"reason": "Contradictory data observed"}
        signal = detector.detect_telemetry_invalidation("test-001", telemetry, 0.85)

        assert signal is not None
        assert signal.source == InvalidationSource.TELEMETRY
        assert signal.confidence == 0.85

    def test_detect_deterministic_invalidation(self):
        """Test detecting invalidation from deterministic verification."""
        registry = AssumptionRegistry()
        lifecycle = AssumptionLifecycleManager(registry)
        detector = InvalidationDetector(registry, lifecycle)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-002",
            description="Test assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)

        # Detect invalidation
        verification = {"valid": False, "reason": "Mathematical proof failed"}
        signal = detector.detect_deterministic_invalidation("test-002", verification)

        assert signal is not None
        assert signal.source == InvalidationSource.DETERMINISTIC
        assert signal.confidence == 1.0
        assert signal.severity == "critical"

    def test_detect_timeout_invalidation(self):
        """Test detecting invalidation from timeout."""
        registry = AssumptionRegistry()
        lifecycle = AssumptionLifecycleManager(registry)
        detector = InvalidationDetector(registry, lifecycle)

        # Create stale assumption
        assumption = AssumptionArtifact(
            assumption_id="test-003",
            description="Stale assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            next_review_date=datetime.now(timezone.utc) - timedelta(days=1),  # Past
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)

        # Detect timeout invalidation
        signals = detector.detect_timeout_invalidation()

        assert len(signals) == 1
        assert signals[0].source == InvalidationSource.TIMEOUT

    def test_track_confidence_trend(self):
        """Test tracking confidence trend."""
        registry = AssumptionRegistry()
        lifecycle = AssumptionLifecycleManager(registry)
        detector = InvalidationDetector(registry, lifecycle)

        # Track decreasing confidence
        detector.track_confidence_trend("artifact-001", 0.9)
        detector.track_confidence_trend("artifact-001", 0.8)
        detector.track_confidence_trend("artifact-001", 0.7)
        detector.track_confidence_trend("artifact-001", 0.6)
        detector.track_confidence_trend("artifact-001", 0.5)

        is_problematic = detector.track_confidence_trend("artifact-001", 0.4)
        assert is_problematic is True


class TestConfidenceDecayer:
    """Test ConfidenceDecayer decay logic."""

    def test_decay_confidence_critical(self):
        """Test confidence decay for critical severity."""
        registry = AssumptionRegistry()
        decayer = ConfidenceDecayer(registry)

        signal = InvalidationSignal(
            signal_id="sig-001",
            assumption_id="test-004",
            source=InvalidationSource.DETERMINISTIC,
            reason="Critical failure",
            confidence=1.0,
            severity="critical",
            timestamp=datetime.now(timezone.utc)
        )

        action = decayer.decay_confidence("test-004", signal, 0.9)

        assert action.confidence_before == 0.9
        assert abs(action.confidence_after - 0.09) < 0.001  # 0.9 * 0.1 (with floating point tolerance)

    def test_decay_confidence_high(self):
        """Test confidence decay for high severity."""
        registry = AssumptionRegistry()
        decayer = ConfidenceDecayer(registry)

        signal = InvalidationSignal(
            signal_id="sig-002",
            assumption_id="test-005",
            source=InvalidationSource.TELEMETRY,
            reason="High severity issue",
            confidence=0.9,
            severity="high",
            timestamp=datetime.now(timezone.utc)
        )

        action = decayer.decay_confidence("test-005", signal, 0.8)

        assert action.confidence_before == 0.8
        assert action.confidence_after == 0.24  # 0.8 * 0.3


class TestAuthorityDecayer:
    """Test AuthorityDecayer decay logic."""

    def test_decay_authority_critical(self):
        """Test authority decay for critical severity."""
        registry = AssumptionRegistry()
        decayer = AuthorityDecayer(registry)

        signal = InvalidationSignal(
            signal_id="sig-003",
            assumption_id="test-006",
            source=InvalidationSource.DETERMINISTIC,
            reason="Critical failure",
            confidence=1.0,
            severity="critical",
            timestamp=datetime.now(timezone.utc)
        )

        action = decayer.decay_authority("test-006", signal, "high")

        assert action.authority_before == "high"
        assert action.authority_after == "none"

    def test_decay_authority_high(self):
        """Test authority decay for high severity."""
        registry = AssumptionRegistry()
        decayer = AuthorityDecayer(registry)

        signal = InvalidationSignal(
            signal_id="sig-004",
            assumption_id="test-007",
            source=InvalidationSource.TELEMETRY,
            reason="High severity issue",
            confidence=0.9,
            severity="high",
            timestamp=datetime.now(timezone.utc)
        )

        action = decayer.decay_authority("test-007", signal, "medium")

        assert action.authority_before == "medium"
        assert action.authority_after == "low"


class TestExecutionFreezer:
    """Test ExecutionFreezer freezing logic."""

    def test_freeze_execution(self):
        """Test freezing execution for critical assumption."""
        registry = AssumptionRegistry()
        binding_manager = AssumptionBindingManager(registry)
        freezer = ExecutionFreezer(registry, binding_manager)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-008",
            description="Critical assumption",
            source_artifact_id="hyp-001",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)

        # Bind to artifact as critical
        binding_manager.bind_to_hypothesis("test-008", "hyp-001", is_critical=True)

        # Freeze execution
        signal = InvalidationSignal(
            signal_id="sig-005",
            assumption_id="test-008",
            source=InvalidationSource.SUPERVISOR,
            reason="Supervisor invalidated",
            confidence=1.0,
            severity="critical",
            timestamp=datetime.now(timezone.utc)
        )

        action = freezer.freeze_execution("test-008", signal)

        assert action.execution_frozen is True
        assert "hyp-001" in action.affected_artifacts

    def test_can_execute_frozen(self):
        """Test checking if frozen artifact can execute."""
        registry = AssumptionRegistry()
        binding_manager = AssumptionBindingManager(registry)
        freezer = ExecutionFreezer(registry, binding_manager)

        # Create and freeze
        assumption = AssumptionArtifact(
            assumption_id="test-009",
            description="Critical assumption",
            source_artifact_id="hyp-002",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)
        binding_manager.bind_to_hypothesis("test-009", "hyp-002", is_critical=True)

        signal = InvalidationSignal(
            signal_id="sig-006",
            assumption_id="test-009",
            source=InvalidationSource.SUPERVISOR,
            reason="Invalidated",
            confidence=1.0,
            severity="critical",
            timestamp=datetime.now(timezone.utc)
        )

        freezer.freeze_execution("test-009", signal)

        # Check if can execute
        can_execute, blocking = freezer.can_execute("hyp-002")

        assert can_execute is False
        assert "test-009" in blocking

    def test_unfreeze_artifact(self):
        """Test unfreezing artifact."""
        registry = AssumptionRegistry()
        binding_manager = AssumptionBindingManager(registry)
        freezer = ExecutionFreezer(registry, binding_manager)

        # Create and freeze
        assumption = AssumptionArtifact(
            assumption_id="test-010",
            description="Critical assumption",
            source_artifact_id="hyp-003",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)
        binding_manager.bind_to_hypothesis("test-010", "hyp-003", is_critical=True)

        signal = InvalidationSignal(
            signal_id="sig-007",
            assumption_id="test-010",
            source=InvalidationSource.SUPERVISOR,
            reason="Invalidated",
            confidence=1.0,
            severity="critical",
            timestamp=datetime.now(timezone.utc)
        )

        freezer.freeze_execution("test-010", signal)

        # Unfreeze
        fully_unfrozen = freezer.unfreeze_artifact("hyp-003", "test-010")

        assert fully_unfrozen is True

        # Check can execute now
        can_execute, _ = freezer.can_execute("hyp-003")
        assert can_execute is True


class TestReExpansionTrigger:
    """Test ReExpansionTrigger re-expansion criteria."""

    def test_can_reexpand_success(self):
        """Test successful re-expansion check."""
        registry = AssumptionRegistry()
        binding_manager = AssumptionBindingManager(registry)
        freezer = ExecutionFreezer(registry, binding_manager)
        trigger = ReExpansionTrigger(registry, binding_manager, freezer)

        # Create validated assumption
        assumption = AssumptionArtifact(
            assumption_id="test-011",
            description="Validated assumption",
            source_artifact_id="hyp-004",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.VALIDATED,
            created_at=datetime.now(timezone.utc),
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)
        binding_manager.bind_to_hypothesis("test-011", "hyp-004", is_critical=True)

        # Check can re-expand
        can_reexpand, reasons = trigger.can_reexpand("hyp-004", 0.85)

        assert can_reexpand is True
        assert len(reasons) == 0

    def test_cannot_reexpand_low_confidence(self):
        """Test re-expansion blocked by low confidence."""
        registry = AssumptionRegistry()
        binding_manager = AssumptionBindingManager(registry)
        freezer = ExecutionFreezer(registry, binding_manager)
        trigger = ReExpansionTrigger(registry, binding_manager, freezer)

        # Check with low confidence
        can_reexpand, reasons = trigger.can_reexpand("hyp-005", 0.5)

        assert can_reexpand is False
        assert any("Confidence" in r for r in reasons)

    def test_trigger_reexpansion(self):
        """Test triggering re-expansion."""
        registry = AssumptionRegistry()
        binding_manager = AssumptionBindingManager(registry)
        freezer = ExecutionFreezer(registry, binding_manager)
        trigger = ReExpansionTrigger(registry, binding_manager, freezer)

        # Create validated assumption
        assumption = AssumptionArtifact(
            assumption_id="test-012",
            description="Validated assumption",
            source_artifact_id="hyp-006",
            confidence_if_true=0.9,
            confidence_if_false=0.3,
            status=AssumptionStatus.VALIDATED,
            created_at=datetime.now(timezone.utc),
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            validated_by_self=False,
            requires_external_validation=True
        )
        registry.register(assumption)
        binding_manager.bind_to_hypothesis("test-012", "hyp-006", is_critical=True)

        # Trigger re-expansion
        action = trigger.trigger_reexpansion("hyp-006", 0.85)

        assert action is not None
        assert "hyp-006" in action.affected_artifacts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
