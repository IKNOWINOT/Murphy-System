"""
Tests for ARCH-002: SelfAutomationOrchestrator persistence wiring.

Validates that the SelfAutomationOrchestrator can save and restore state
via PersistenceManager, surviving simulated restarts.

Design Label: TEST-001 / ARCH-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from self_automation_orchestrator import (
    SelfAutomationOrchestrator,
    TaskCategory,
    TaskStatus,
    PromptStep,
)
from persistence_manager import PersistenceManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def orch(pm):
    return SelfAutomationOrchestrator(persistence_manager=pm)


# ------------------------------------------------------------------
# Backward compatibility: no persistence_manager
# ------------------------------------------------------------------

class TestNoPersistence:
    def test_orchestrator_works_without_persistence(self):
        orch = SelfAutomationOrchestrator()
        task = orch.create_task("Fix bug", TaskCategory.BUG_FIX)
        assert task.task_id.startswith("task-")

    def test_save_state_returns_false_without_pm(self):
        orch = SelfAutomationOrchestrator()
        assert orch.save_state() is False

    def test_load_state_returns_false_without_pm(self):
        orch = SelfAutomationOrchestrator()
        assert orch.load_state() is False


# ------------------------------------------------------------------
# Persistence round-trip
# ------------------------------------------------------------------

class TestPersistenceRoundTrip:
    def test_save_and_load_tasks(self, pm):
        orch1 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch1.create_task("Task A", TaskCategory.BUG_FIX, priority=1)
        orch1.create_task("Task B", TaskCategory.FEATURE_REQUEST, priority=3)
        assert orch1.save_state() is True

        orch2 = SelfAutomationOrchestrator(persistence_manager=pm)
        assert orch2.get_status()["total_tasks"] == 0
        assert orch2.load_state() is True
        assert orch2.get_status()["total_tasks"] == 2

    def test_task_status_preserved(self, pm):
        orch1 = SelfAutomationOrchestrator(persistence_manager=pm)
        task = orch1.create_task("Task C", TaskCategory.COVERAGE_GAP)
        orch1.start_task(task.task_id)
        orch1.save_state()

        orch2 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch2.load_state()
        restored = orch2.get_task(task.task_id)
        assert restored is not None
        assert restored.status == TaskStatus.IN_PROGRESS

    def test_completed_tasks_preserved(self, pm):
        orch1 = SelfAutomationOrchestrator(persistence_manager=pm)
        task = orch1.create_task("Done", TaskCategory.BUG_FIX)
        orch1.start_task(task.task_id)
        orch1.complete_task(task.task_id, result={"ok": True})
        orch1.save_state()

        orch2 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch2.load_state()
        assert orch2.get_status()["completed_count"] == 1

    def test_gap_registry_preserved(self, pm):
        orch1 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch1.register_gap("gap-1", TaskCategory.COVERAGE_GAP, "Missing tests", severity=2)
        orch1.save_state()

        orch2 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch2.load_state()
        gaps = orch2.get_open_gaps()
        assert len(gaps) == 1
        assert gaps[0]["gap_id"] == "gap-1"

    def test_cycle_history_preserved(self, pm):
        orch1 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch1.start_cycle(gap_analysis={"total_gaps": 5})
        orch1.complete_cycle()
        orch1.save_state()

        orch2 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch2.load_state()
        assert orch2.get_status()["completed_cycles"] == 1

    def test_load_state_returns_false_when_empty(self, pm):
        orch = SelfAutomationOrchestrator(persistence_manager=pm)
        assert orch.load_state() is False

    def test_queue_order_preserved(self, pm):
        orch1 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch1.create_task("Low", TaskCategory.BUG_FIX, priority=5)
        orch1.create_task("High", TaskCategory.BUG_FIX, priority=1)
        orch1.save_state()

        orch2 = SelfAutomationOrchestrator(persistence_manager=pm)
        orch2.load_state()
        next_task = orch2.get_next_task()
        assert next_task is not None
        assert next_task.title == "High"
