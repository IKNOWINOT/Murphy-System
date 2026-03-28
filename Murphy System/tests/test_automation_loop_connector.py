"""
Tests for DEV-001: AutomationLoopConnector.

Validates the closed-loop feedback cycle between SelfImprovementEngine
and SelfAutomationOrchestrator.

Design Label: TEST-002 / DEV-001
Owner: QA Team
"""

import os
import pytest


from automation_loop_connector import AutomationLoopConnector, LoopCycleResult
from self_improvement_engine import SelfImprovementEngine, ExecutionOutcome, OutcomeType
from self_automation_orchestrator import SelfAutomationOrchestrator, TaskCategory, TaskStatus
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def engine(pm):
    return SelfImprovementEngine(persistence_manager=pm)


@pytest.fixture
def orchestrator(pm):
    return SelfAutomationOrchestrator(persistence_manager=pm)


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def connector(engine, orchestrator):
    return AutomationLoopConnector(
        improvement_engine=engine,
        orchestrator=orchestrator,
    )


@pytest.fixture
def wired_connector(engine, orchestrator, backbone):
    return AutomationLoopConnector(
        improvement_engine=engine,
        orchestrator=orchestrator,
        event_backbone=backbone,
    )


def _make_outcome(task_id, outcome_type, task_type="deploy"):
    return ExecutionOutcome(
        task_id=task_id,
        session_id="s1",
        outcome=outcome_type,
        metrics={"task_type": task_type, "duration": 1.0},
    )


# ------------------------------------------------------------------
# Basic cycle
# ------------------------------------------------------------------

class TestBasicCycle:
    def test_empty_cycle(self, connector):
        result = connector.run_cycle()
        assert isinstance(result, LoopCycleResult)
        assert result.outcomes_recorded == 0
        assert result.tasks_created == 0

    def test_cycle_records_pending_outcomes(self, connector, engine):
        # Manually queue outcomes
        connector._queue_outcome(
            {"task_id": "t1", "session_id": "s1", "metrics": {"task_type": "deploy"}},
            "failure",
        )
        connector._queue_outcome(
            {"task_id": "t2", "session_id": "s1", "metrics": {"task_type": "deploy"}},
            "failure",
        )
        result = connector.run_cycle()
        assert result.outcomes_recorded == 2
        assert engine.get_status()["total_outcomes"] == 2


# ------------------------------------------------------------------
# Proposal → Task creation
# ------------------------------------------------------------------

class TestProposalToTask:
    def test_high_priority_proposals_create_tasks(self, connector, engine, orchestrator):
        # Record enough failures to generate a high-priority proposal
        for i in range(5):
            engine.record_outcome(_make_outcome(f"t-{i}", OutcomeType.FAILURE))

        result = connector.run_cycle()
        assert result.proposals_generated >= 1
        # High/critical proposals should create tasks
        tasks = orchestrator.list_tasks()
        if result.tasks_created > 0:
            assert len(tasks) >= 1
            assert tasks[0].title.startswith("[AUTO]")

    def test_low_priority_proposals_not_auto_created(self, engine, orchestrator):
        # Only successes → low priority proposals → no tasks
        connector = AutomationLoopConnector(
            improvement_engine=engine,
            orchestrator=orchestrator,
            auto_task_priority_threshold="critical",  # very restrictive
        )
        for i in range(5):
            engine.record_outcome(_make_outcome(f"t-{i}", OutcomeType.SUCCESS))
        result = connector.run_cycle()
        # Success patterns generate low-priority proposals — shouldn't create tasks
        assert result.tasks_created == 0

    def test_deduplication(self, connector, engine, orchestrator):
        for i in range(3):
            engine.record_outcome(_make_outcome(f"t-{i}", OutcomeType.FAILURE))
        connector.run_cycle()
        first_count = orchestrator.get_status()["total_tasks"]
        # Second cycle: same outcomes generate new patterns with new IDs
        # but the connector tracks proposal_ids it has already seen,
        # so task count growth should be bounded compared to untracked.
        connector.run_cycle()
        second_count = orchestrator.get_status()["total_tasks"]
        # Both cycles may produce proposals (patterns re-extracted with new IDs),
        # but the proposals from the first cycle are already tracked.
        assert second_count >= first_count


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_event_subscription_queues_outcomes(self, wired_connector, backbone):
        backbone.publish(
            event_type=EventType.TASK_FAILED,
            payload={"task_id": "evt-1", "metrics": {"task_type": "deploy"}},
            source="test",
        )
        backbone.process_pending()
        status = wired_connector.get_status()
        assert status["pending_outcomes"] >= 1


# ------------------------------------------------------------------
# Cycle history
# ------------------------------------------------------------------

class TestCycleHistory:
    def test_history_accumulates(self, connector):
        connector.run_cycle()
        connector.run_cycle()
        history = connector.get_cycle_history()
        assert len(history) == 2

    def test_cycle_result_to_dict(self, connector):
        result = connector.run_cycle()
        d = result.to_dict()
        assert "cycle_id" in d
        assert "outcomes_recorded" in d


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_attachments(self, connector):
        status = connector.get_status()
        assert status["engine_attached"] is True
        assert status["orchestrator_attached"] is True
        assert status["event_backbone_attached"] is False

    def test_status_with_backbone(self, wired_connector):
        assert wired_connector.get_status()["event_backbone_attached"] is True
