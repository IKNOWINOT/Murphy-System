"""
Tests for OBS-004: SelfHealingCoordinator.

Validates procedure registration, failure handling, cooldown logic,
max-attempts enforcement, and EventBackbone integration.

Design Label: TEST-002 / OBS-004
Owner: QA Team
"""

import os
import time
import pytest


from self_healing_coordinator import (
    SelfHealingCoordinator,
    RecoveryProcedure,
    RecoveryAttempt,
    RecoveryStatus,
)
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def coordinator():
    return SelfHealingCoordinator()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def wired_coordinator(backbone):
    return SelfHealingCoordinator(event_backbone=backbone)


def _success_handler(ctx):
    return True


def _failure_handler(ctx):
    return False


def _crashing_handler(ctx):
    raise RuntimeError("handler exploded")


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestRegistration:
    def test_register_procedure(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="restart-db",
            category="database_failure",
            description="Restart DB pool",
            handler=_success_handler,
        )
        result = coordinator.register_procedure(proc)
        assert result == "restart-db"
        assert "database_failure" in coordinator.get_status()["categories"]

    def test_unregister_procedure(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="cat1",
            description="test", handler=_success_handler,
        )
        coordinator.register_procedure(proc)
        assert coordinator.unregister_procedure("p1") is True
        assert "cat1" not in coordinator.get_status()["categories"]

    def test_unregister_missing_returns_false(self, coordinator):
        assert coordinator.unregister_procedure("nope") is False


# ------------------------------------------------------------------
# Failure handling
# ------------------------------------------------------------------

class TestFailureHandling:
    def test_successful_recovery(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="test_fail",
            description="test", handler=_success_handler,
        )
        coordinator.register_procedure(proc)
        attempt = coordinator.handle_failure("test_fail", trigger="manual")
        assert attempt.status == RecoveryStatus.SUCCESS
        assert attempt.duration_ms >= 0

    def test_failed_recovery(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="test_fail",
            description="test", handler=_failure_handler,
        )
        coordinator.register_procedure(proc)
        attempt = coordinator.handle_failure("test_fail")
        assert attempt.status == RecoveryStatus.FAILED

    def test_crashing_handler(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="crash",
            description="test", handler=_crashing_handler,
        )
        coordinator.register_procedure(proc)
        attempt = coordinator.handle_failure("crash")
        assert attempt.status == RecoveryStatus.FAILED
        assert "exploded" in attempt.message

    def test_unregistered_category_skipped(self, coordinator):
        attempt = coordinator.handle_failure("unknown_category")
        assert attempt.status == RecoveryStatus.SKIPPED
        assert "No recovery procedure" in attempt.message

    def test_max_attempts_enforced(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="fail_cat",
            description="test", handler=_failure_handler,
            max_attempts=2, cooldown_seconds=0,
        )
        coordinator.register_procedure(proc)
        coordinator.handle_failure("fail_cat")
        coordinator.handle_failure("fail_cat")
        # Third attempt should be skipped
        attempt = coordinator.handle_failure("fail_cat")
        assert attempt.status == RecoveryStatus.SKIPPED
        assert "Max recovery attempts" in attempt.message

    def test_cooldown_enforced(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="cool_cat",
            description="test", handler=_success_handler,
            cooldown_seconds=999,
        )
        coordinator.register_procedure(proc)
        coordinator.handle_failure("cool_cat")
        attempt = coordinator.handle_failure("cool_cat")
        assert attempt.status == RecoveryStatus.COOLDOWN

    def test_reset_failure_counter(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="reset_cat",
            description="test", handler=_failure_handler,
            max_attempts=1, cooldown_seconds=0,
        )
        coordinator.register_procedure(proc)
        coordinator.handle_failure("reset_cat")  # fails
        assert coordinator.reset_failure_counter("reset_cat") is True
        # Should be allowed again
        attempt = coordinator.handle_failure("reset_cat")
        assert attempt.status == RecoveryStatus.FAILED  # handler still fails but attempt is made

    def test_reset_unknown_returns_false(self, coordinator):
        assert coordinator.reset_failure_counter("nope") is False


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

class TestHistory:
    def test_history_accumulates(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="cat1",
            description="test", handler=_success_handler,
            cooldown_seconds=0,
        )
        coordinator.register_procedure(proc)
        coordinator.handle_failure("cat1")
        coordinator.handle_failure("cat1")
        history = coordinator.get_history()
        assert len(history) == 2


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_recovery_publishes_learning_feedback(self, wired_coordinator, backbone):
        recorder = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: recorder.append(e))
        proc = RecoveryProcedure(
            procedure_id="p1", category="event_test",
            description="test", handler=_success_handler,
        )
        wired_coordinator.register_procedure(proc)
        wired_coordinator.handle_failure("event_test")
        backbone.process_pending()
        assert len(recorder) >= 1
        assert recorder[0].payload["source"] == "self_healing_coordinator"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, coordinator):
        proc = RecoveryProcedure(
            procedure_id="p1", category="s_cat",
            description="test", handler=_success_handler,
        )
        coordinator.register_procedure(proc)
        status = coordinator.get_status()
        assert status["registered_procedures"] == 1
        assert "s_cat" in status["categories"]
        assert status["event_backbone_attached"] is False
