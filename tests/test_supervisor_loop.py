"""
Tests for Supervisor Loop

Tests:
- SupervisorInterface functionality
- FeedbackProcessor actions
- FeedbackRouter routing
- SupervisorAuditLogger tracking
"""

import pytest
from datetime import datetime, timedelta

from src.supervisor_system.schemas import (
    AssumptionArtifact,
    AssumptionStatus,
    FeedbackType
)
from src.supervisor_system.assumption_management import (
    AssumptionRegistry,
    AssumptionValidator,
    AssumptionLifecycleManager
)
from src.supervisor_system.supervisor_loop import (
    SupervisorInterface,
    FeedbackProcessor,
    FeedbackRouter,
    SupervisorAuditLogger
)


class TestSupervisorAuditLogger:
    """Test SupervisorAuditLogger tracking."""

    def test_log_feedback(self):
        """Test logging supervisor feedback."""
        from src.supervisor_system.schemas import SupervisorFeedbackArtifact

        logger = SupervisorAuditLogger()

        feedback = SupervisorFeedbackArtifact(
            feedback_id="fb-001",
            assumption_id="test-001",
            feedback_type=FeedbackType.APPROVE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            timestamp=datetime.now(),
            rationale="Looks good"
        )

        log = logger.log_feedback(feedback, "APPROVE", {"status": "approved"})

        assert log.feedback_id == "fb-001"
        assert log.supervisor_id == "sup-001"
        assert log.action == "APPROVE"

    def test_get_logs_for_assumption(self):
        """Test retrieving logs for specific assumption."""
        from src.supervisor_system.schemas import SupervisorFeedbackArtifact

        logger = SupervisorAuditLogger()

        feedback1 = SupervisorFeedbackArtifact(
            feedback_id="fb-001",
            assumption_id="test-001",
            feedback_type=FeedbackType.APPROVE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            timestamp=datetime.now(),
            rationale="Approved"
        )

        feedback2 = SupervisorFeedbackArtifact(
            feedback_id="fb-002",
            assumption_id="test-002",
            feedback_type=FeedbackType.DENY,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            timestamp=datetime.now(),
            rationale="Denied"
        )

        logger.log_feedback(feedback1, "APPROVE", {})
        logger.log_feedback(feedback2, "DENY", {})

        logs = logger.get_logs_for_assumption("test-001")
        assert len(logs) == 1
        assert logs[0].assumption_id == "test-001"


class TestFeedbackProcessor:
    """Test FeedbackProcessor actions."""

    def test_process_approve(self):
        """Test processing APPROVE feedback."""
        from src.supervisor_system.schemas import SupervisorFeedbackArtifact

        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle = AssumptionLifecycleManager(registry)
        audit_logger = SupervisorAuditLogger()
        processor = FeedbackProcessor(registry, validator, lifecycle, audit_logger)

        # Create assumption
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

        # Create feedback
        feedback = SupervisorFeedbackArtifact(
            feedback_id="fb-001",
            assumption_id="test-001",
            feedback_type=FeedbackType.APPROVE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            timestamp=datetime.now(),
            rationale="Approved"
        )

        result = processor.process_approve(feedback)
        assert result is True

        # Check status changed to under review
        updated = registry.get("test-001")
        assert updated.status == AssumptionStatus.UNDER_REVIEW

    def test_process_deny(self):
        """Test processing DENY feedback."""
        from src.supervisor_system.schemas import SupervisorFeedbackArtifact

        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle = AssumptionLifecycleManager(registry)
        audit_logger = SupervisorAuditLogger()
        processor = FeedbackProcessor(registry, validator, lifecycle, audit_logger)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-002",
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

        # Create feedback
        feedback = SupervisorFeedbackArtifact(
            feedback_id="fb-002",
            assumption_id="test-002",
            feedback_type=FeedbackType.DENY,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            timestamp=datetime.now(),
            rationale="Incorrect assumption"
        )

        result = processor.process_deny(feedback)
        assert result is True

        # Check status changed to invalidated
        updated = registry.get("test-002")
        assert updated.status == AssumptionStatus.INVALIDATED
        assert len(updated.invalidation_signals) == 1

    def test_process_validate(self):
        """Test processing VALIDATE feedback."""
        from src.supervisor_system.schemas import SupervisorFeedbackArtifact

        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle = AssumptionLifecycleManager(registry)
        audit_logger = SupervisorAuditLogger()
        processor = FeedbackProcessor(registry, validator, lifecycle, audit_logger)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-003",
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

        # Create feedback
        feedback = SupervisorFeedbackArtifact(
            feedback_id="fb-003",
            assumption_id="test-003",
            feedback_type=FeedbackType.VALIDATE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            timestamp=datetime.now(),
            rationale="Validated by supervisor"
        )

        result = processor.process_validate(feedback)
        assert result is True

        # Check status changed to validated
        updated = registry.get("test-003")
        assert updated.status == AssumptionStatus.VALIDATED
        assert len(updated.validation_evidence) == 1


class TestFeedbackRouter:
    """Test FeedbackRouter routing."""

    def test_route_approve(self):
        """Test routing APPROVE feedback."""
        from src.supervisor_system.schemas import SupervisorFeedbackArtifact

        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle = AssumptionLifecycleManager(registry)
        audit_logger = SupervisorAuditLogger()
        processor = FeedbackProcessor(registry, validator, lifecycle, audit_logger)
        router = FeedbackRouter(processor)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-004",
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

        # Create feedback
        feedback = SupervisorFeedbackArtifact(
            feedback_id="fb-004",
            assumption_id="test-004",
            feedback_type=FeedbackType.APPROVE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            timestamp=datetime.now(),
            rationale="Approved"
        )

        result = router.route(feedback)
        assert result is True


class TestSupervisorInterface:
    """Test SupervisorInterface functionality."""

    def test_submit_feedback(self):
        """Test submitting supervisor feedback."""
        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle = AssumptionLifecycleManager(registry)
        interface = SupervisorInterface(registry, validator, lifecycle)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-005",
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

        # Submit feedback
        success, feedback_id = interface.submit_feedback(
            assumption_id="test-005",
            feedback_type=FeedbackType.APPROVE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            rationale="Looks good"
        )

        assert success is True
        assert feedback_id != ""

    def test_get_feedback_for_assumption(self):
        """Test retrieving feedback for assumption."""
        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle = AssumptionLifecycleManager(registry)
        interface = SupervisorInterface(registry, validator, lifecycle)

        # Create assumption
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

        # Submit feedback
        interface.submit_feedback(
            assumption_id="test-006",
            feedback_type=FeedbackType.APPROVE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            rationale="Approved"
        )

        # Get feedback
        logs = interface.get_feedback_for_assumption("test-006")
        assert len(logs) == 1
        assert logs[0].assumption_id == "test-006"

    def test_get_statistics(self):
        """Test getting interface statistics."""
        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle = AssumptionLifecycleManager(registry)
        interface = SupervisorInterface(registry, validator, lifecycle)

        # Create assumption
        assumption = AssumptionArtifact(
            assumption_id="test-007",
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

        # Submit feedback
        interface.submit_feedback(
            assumption_id="test-007",
            feedback_type=FeedbackType.APPROVE,
            supervisor_id="sup-001",
            supervisor_role="senior_engineer",
            rationale="Approved"
        )

        stats = interface.get_statistics()
        assert stats["total_feedback"] == 1
        assert stats["audit_logs"]["total_logs"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
