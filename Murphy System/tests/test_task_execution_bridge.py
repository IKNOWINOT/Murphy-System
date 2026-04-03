"""
Tests for WIRE-003: TaskExecutionBridge.

Validates risk-gated task execution cycle, HITL workflow, and stats.

Design Label: TEST-WIRE-003
Owner: QA Team
"""

import sys
import os
import threading
import pytest


from task_execution_bridge import TaskExecutionBridge, TaskExecutionPlan, CycleExecutionSummary
from self_automation_orchestrator import SelfAutomationOrchestrator, TaskCategory
from gate_bypass_controller import GateBypassController, TaskRiskLevel
from event_backbone import EventBackbone, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orchestrator():
    return SelfAutomationOrchestrator()


@pytest.fixture
def gate_ctrl():
    return GateBypassController()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def bridge(orchestrator, gate_ctrl, backbone):
    return TaskExecutionBridge(
        orchestrator=orchestrator,
        event_backbone=backbone,
        gate_bypass_controller=gate_ctrl,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_task(orchestrator, task_type="text_generation", priority=3):
    """Add a minimal task to the orchestrator and return its task_id."""
    task = orchestrator.create_task(
        title=f"Test task for {task_type}",
        category=TaskCategory.SELF_IMPROVEMENT,
        priority=priority,
        description="Auto-generated test task",
    )
    # Override category string so gate controller picks the right risk
    if hasattr(task, "category"):
        task.category = task_type
    return task.task_id


# ---------------------------------------------------------------------------
# Test: risk gating
# ---------------------------------------------------------------------------

class TestRiskGating:
    def test_critical_risk_held_for_review(self, bridge, orchestrator, gate_ctrl):
        """CRITICAL risk tasks must never auto-execute."""
        task = orchestrator.create_task(
            title="Critical task",
            category=TaskCategory.SELF_IMPROVEMENT,
            priority=1,
            description="A critical task",
        )
        # Force a high-risk type by patching category
        task.category = "code_modification"  # not in minimal/low risk sets

        summary = bridge.run_execution_cycle()
        assert summary.tasks_held_for_review >= 1
        assert summary.tasks_auto_approved == 0

    def test_minimal_risk_task_auto_approved(self, gate_ctrl, backbone):
        """MINIMAL risk tasks may auto-proceed (no successes required for MINIMAL)."""
        orch = SelfAutomationOrchestrator()
        task_type = "text_generation"

        task = orch.create_task(
            title="Minimal risk task",
            category=TaskCategory.SELF_IMPROVEMENT,
            priority=3,
            description="Low risk text task",
        )
        task.category = task_type

        bridge = TaskExecutionBridge(
            orchestrator=orch,
            event_backbone=backbone,
            gate_bypass_controller=gate_ctrl,
        )
        summary = bridge.run_execution_cycle()
        assert summary.tasks_auto_approved >= 1

    def test_no_gate_controller_all_held(self, orchestrator, backbone):
        """Without a gate controller every task must be held for review."""
        bridge_no_gate = TaskExecutionBridge(
            orchestrator=orchestrator,
            event_backbone=backbone,
            gate_bypass_controller=None,
        )
        orchestrator.create_task(
            title="Task without gate",
            category=TaskCategory.SELF_IMPROVEMENT,
            priority=3,
            description="Should be held",
        )
        summary = bridge_no_gate.run_execution_cycle()
        assert summary.tasks_held_for_review >= 1
        assert summary.tasks_auto_approved == 0


# ---------------------------------------------------------------------------
# Test: max_tasks_per_cycle
# ---------------------------------------------------------------------------

class TestMaxTasksPerCycle:
    def test_max_tasks_respected(self, gate_ctrl, backbone):
        """Bridge must not process more than max_tasks_per_cycle tasks."""
        orch = SelfAutomationOrchestrator()
        for i in range(10):
            orch.create_task(
                title=f"Task {i}",
                category=TaskCategory.SELF_IMPROVEMENT,
                priority=3,
                description=f"Task number {i}",
            )

        bridge = TaskExecutionBridge(
            orchestrator=orch,
            event_backbone=backbone,
            gate_bypass_controller=gate_ctrl,
            max_tasks_per_cycle=3,
        )
        summary = bridge.run_execution_cycle()
        assert summary.tasks_evaluated <= 3

    def test_max_tasks_default(self, orchestrator, gate_ctrl, backbone):
        bridge = TaskExecutionBridge(
            orchestrator=orchestrator,
            gate_bypass_controller=gate_ctrl,
            max_tasks_per_cycle=5,
        )
        assert bridge._max_tasks_per_cycle == 5


# ---------------------------------------------------------------------------
# Test: get_pending_reviews
# ---------------------------------------------------------------------------

class TestPendingReviews:
    def test_held_task_appears_in_pending_reviews(self, bridge, orchestrator):
        orchestrator.create_task(
            title="Needs review",
            category=TaskCategory.SELF_IMPROVEMENT,
            priority=1,
            description="High risk task",
        )
        bridge.run_execution_cycle()
        pending = bridge.get_pending_reviews()
        assert len(pending) >= 1
        item = pending[0]
        assert "task_id" in item
        assert item["require_human_review"] is True
        assert item["status"] == "pending"


# ---------------------------------------------------------------------------
# Test: approve_task / reject_task
# ---------------------------------------------------------------------------

class TestHITLWorkflow:
    def _held_task_id(self, bridge, orchestrator):
        orchestrator.create_task(
            title="HITL task",
            category=TaskCategory.SELF_IMPROVEMENT,
            priority=1,
            description="Held for HITL",
        )
        bridge.run_execution_cycle()
        pending = bridge.get_pending_reviews()
        assert pending, "Expected at least one pending review"
        return pending[0]["task_id"]

    def test_approve_task(self, bridge, orchestrator):
        task_id = self._held_task_id(bridge, orchestrator)
        result = bridge.approve_task(task_id)
        assert result is True
        # Task should no longer be pending
        pending_ids = [p["task_id"] for p in bridge.get_pending_reviews()]
        assert task_id not in pending_ids

    def test_reject_task(self, bridge, orchestrator):
        task_id = self._held_task_id(bridge, orchestrator)
        result = bridge.reject_task(task_id, reason="test rejection")
        assert result is True
        pending_ids = [p["task_id"] for p in bridge.get_pending_reviews()]
        assert task_id not in pending_ids

    def test_approve_nonexistent_task(self, bridge):
        assert bridge.approve_task("nonexistent-id") is False

    def test_reject_nonexistent_task(self, bridge):
        assert bridge.reject_task("nonexistent-id") is False

    def test_double_approve_returns_false(self, bridge, orchestrator):
        task_id = self._held_task_id(bridge, orchestrator)
        assert bridge.approve_task(task_id) is True
        assert bridge.approve_task(task_id) is False


# ---------------------------------------------------------------------------
# Test: get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_status_structure(self, bridge):
        status = bridge.get_status()
        assert "total_evaluated" in status
        assert "total_auto_approved" in status
        assert "total_held_for_review" in status
        assert "total_failed" in status
        assert "pending_review_count" in status
        assert "cycles_completed" in status
        assert "max_tasks_per_cycle" in status
        assert "orchestrator_attached" in status
        assert "gate_controller_attached" in status
        assert "event_backbone_attached" in status

    def test_status_counts_update(self, bridge, orchestrator):
        orchestrator.create_task(
            title="Status test",
            category=TaskCategory.SELF_IMPROVEMENT,
            priority=3,
            description="Status check",
        )
        bridge.run_execution_cycle()
        status = bridge.get_status()
        assert status["total_evaluated"] >= 1
        assert status["cycles_completed"] >= 1

    def test_no_orchestrator(self, backbone, gate_ctrl):
        bridge = TaskExecutionBridge(
            orchestrator=None,
            event_backbone=backbone,
            gate_bypass_controller=gate_ctrl,
        )
        summary = bridge.run_execution_cycle()
        assert summary.tasks_evaluated == 0


# ---------------------------------------------------------------------------
# Test: Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_cycles(self, gate_ctrl, backbone):
        orch = SelfAutomationOrchestrator()
        for i in range(10):
            orch.create_task(
                title=f"Concurrent task {i}",
                category=TaskCategory.SELF_IMPROVEMENT,
                priority=3,
                description=f"Task {i}",
            )

        bridge = TaskExecutionBridge(
            orchestrator=orch,
            event_backbone=backbone,
            gate_bypass_controller=gate_ctrl,
            max_tasks_per_cycle=2,
        )

        errors = []

        def _worker():
            try:
                bridge.run_execution_cycle()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_approve_reject(self, bridge, orchestrator):
        """Concurrent approve/reject should not raise exceptions."""
        orchestrator.create_task(
            title="Concurrent HITL",
            category=TaskCategory.SELF_IMPROVEMENT,
            priority=1,
            description="Concurrency test",
        )
        bridge.run_execution_cycle()
        pending = bridge.get_pending_reviews()
        if not pending:
            return  # Nothing to test

        task_id = pending[0]["task_id"]
        errors = []

        def _approve():
            try:
                bridge.approve_task(task_id)
            except Exception as exc:
                errors.append(exc)

        def _reject():
            try:
                bridge.reject_task(task_id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_approve), threading.Thread(target=_reject)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
