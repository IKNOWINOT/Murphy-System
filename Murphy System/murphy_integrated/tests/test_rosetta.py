"""
Tests for the Rosetta State Management System.

Covers models, manager CRUD, archive classifier, recalibration scheduler,
global aggregator, thread safety, and integration with EventType / PromptStep.
"""

import json
import threading
from datetime import datetime, timedelta, timezone

import pytest

from rosetta.rosetta_models import (
    AgentState,
    ArchiveEntry,
    ArchiveLog,
    AutomationProgress,
    Goal,
    GoalStatus,
    Identity,
    ImprovementProposal,
    Metadata,
    Recalibration,
    RecalibrationStatus,
    RosettaAgentState,
    SystemState,
    Task,
    TaskStatus,
    WorkflowPattern,
)
from rosetta.rosetta_manager import RosettaManager
from rosetta.archive_classifier import ArchiveClassifier
from rosetta.recalibration_scheduler import RecalibrationScheduler
from rosetta.global_aggregator import GlobalAggregator


# ==================== Helpers ====================

def _make_identity(agent_id: str = "agent-1", name: str = "TestAgent") -> Identity:
    return Identity(agent_id=agent_id, name=name, role="worker", version="1.0.0")


def _make_state(agent_id: str = "agent-1", **kwargs) -> RosettaAgentState:
    return RosettaAgentState(identity=_make_identity(agent_id), **kwargs)


def _make_goal(goal_id: str = "g1", **kwargs) -> Goal:
    defaults = {"goal_id": goal_id, "title": f"Goal {goal_id}"}
    defaults.update(kwargs)
    return Goal(**defaults)


def _make_task(task_id: str = "t1", goal_id: str = "g1", **kwargs) -> Task:
    defaults = {"task_id": task_id, "goal_id": goal_id, "title": f"Task {task_id}"}
    defaults.update(kwargs)
    return Task(**defaults)


# ==================== Model Tests ====================

class TestRosettaModels:
    def test_identity_creation(self):
        ident = Identity(agent_id="a1", name="Alice", role="lead")
        assert ident.agent_id == "a1"
        assert ident.name == "Alice"

    def test_system_state_defaults(self):
        ss = SystemState()
        assert ss.status == "idle"
        assert ss.uptime_seconds == 0.0

    def test_goal_validation(self):
        g = Goal(goal_id="g1", title="Test", priority=1, progress_percent=50.0)
        assert g.priority == 1
        assert g.progress_percent == 50.0

    def test_goal_priority_bounds(self):
        with pytest.raises(Exception):
            Goal(goal_id="g1", title="T", priority=0)
        with pytest.raises(Exception):
            Goal(goal_id="g1", title="T", priority=6)

    def test_task_status_enum(self):
        t = Task(task_id="t1", goal_id="g1", title="T", status=TaskStatus.RUNNING)
        assert t.status == "running" or t.status == TaskStatus.RUNNING

    def test_agent_state_defaults(self):
        a = AgentState()
        assert a.current_phase == "idle"
        assert a.active_goals == []
        assert a.task_queue == []

    def test_full_rosetta_state_creation(self):
        state = _make_state(
            agent_state=AgentState(
                current_phase="active",
                active_goals=[_make_goal()],
                task_queue=[_make_task()],
            ),
        )
        assert state.identity.agent_id == "agent-1"
        assert len(state.agent_state.active_goals) == 1
        assert len(state.agent_state.task_queue) == 1

    def test_rosetta_state_serialization(self):
        state = _make_state()
        data = state.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["identity"]["agent_id"] == "agent-1"

        restored = RosettaAgentState.model_validate(data)
        assert restored.identity.agent_id == "agent-1"

    def test_automation_progress(self):
        ap = AutomationProgress(category="testing", total_items=100, completed_items=75, coverage_percent=75.0)
        assert ap.coverage_percent == 75.0

    def test_recalibration_defaults(self):
        r = Recalibration()
        assert r.status == "idle" or r.status == RecalibrationStatus.IDLE
        assert r.cycle_count == 0

    def test_archive_entry(self):
        e = ArchiveEntry(entry_id="e1", reason="done", category="completed_goal", data={"x": 1})
        assert e.data == {"x": 1}

    def test_improvement_proposal(self):
        p = ImprovementProposal(proposal_id="p1", title="Better caching", priority=2)
        assert p.priority == 2

    def test_workflow_pattern(self):
        wp = WorkflowPattern(pattern_id="w1", name="deploy", steps=["build", "test", "ship"], success_rate=0.95)
        assert wp.success_rate == 0.95

    def test_metadata_defaults(self):
        m = Metadata()
        assert m.schema_version == "1.0"


# ==================== Manager CRUD Tests ====================

class TestRosettaManager:
    def test_save_and_load(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        state = _make_state("a1")
        mgr.save_state(state)
        loaded = mgr.load_state("a1")
        assert loaded is not None
        assert loaded.identity.agent_id == "a1"

    def test_load_nonexistent(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        assert mgr.load_state("nope") is None

    def test_update_state(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("a1"))
        updated = mgr.update_state("a1", {"system_state": {"status": "active"}})
        assert updated is not None
        assert updated.system_state.status == "active"

    def test_update_nonexistent(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        assert mgr.update_state("nope", {"system_state": {"status": "x"}}) is None

    def test_list_agents(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("a1"))
        mgr.save_state(_make_state("a2"))
        agents = mgr.list_agents()
        assert "a1" in agents
        assert "a2" in agents

    def test_delete_state(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("a1"))
        assert mgr.delete_state("a1") is True
        assert mgr.load_state("a1") is None
        assert mgr.delete_state("a1") is False

    def test_aggregate(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(
            _make_state(
                "a1",
                agent_state=AgentState(active_goals=[_make_goal()]),
                system_state=SystemState(status="active"),
            )
        )
        mgr.save_state(
            _make_state(
                "a2",
                agent_state=AgentState(
                    active_goals=[_make_goal("g2")],
                    task_queue=[_make_task()],
                ),
            )
        )
        agg = mgr.aggregate()
        assert agg["total_agents"] == 2
        assert agg["total_goals"] == 2
        assert agg["total_tasks"] == 1

    def test_get_status(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        status = mgr.get_status()
        assert "persistence_dir" in status
        assert "agents_in_memory" in status

    def test_persistence_on_disk(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("disk1"))

        # Create a fresh manager pointing at same dir
        mgr2 = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        loaded = mgr2.load_state("disk1")
        assert loaded is not None
        assert loaded.identity.agent_id == "disk1"

    def test_json_file_written(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("j1"))
        fp = tmp_path / "rosetta" / "j1.json"
        assert fp.exists()
        data = json.loads(fp.read_text())
        assert data["identity"]["agent_id"] == "j1"


# ==================== Archive Classifier Tests ====================

class TestArchiveClassifier:
    def test_classify_completed(self):
        ac = ArchiveClassifier()
        assert ac.classify({"status": "completed"}) == "completed_goal"

    def test_classify_failed(self):
        ac = ArchiveClassifier()
        assert ac.classify({"status": "failed"}) == "failed_task"

    def test_classify_stale(self):
        ac = ArchiveClassifier()
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        assert ac.classify({"status": "pending", "updated_at": old}) == "stale_data"

    def test_classify_manual_default(self):
        ac = ArchiveClassifier()
        assert ac.classify({"status": "running"}) == "manual"

    def test_should_archive_completed(self):
        ac = ArchiveClassifier()
        assert ac.should_archive({"status": "completed"}) is True

    def test_should_archive_failed(self):
        ac = ArchiveClassifier()
        assert ac.should_archive({"status": "failed"}) is True

    def test_should_archive_stale(self):
        ac = ArchiveClassifier()
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        assert ac.should_archive({"status": "pending", "updated_at": old}) is True

    def test_should_not_archive_recent(self):
        ac = ArchiveClassifier()
        recent = datetime.now(timezone.utc).isoformat()
        assert ac.should_archive({"status": "pending", "updated_at": recent}) is False

    def test_archive_item(self):
        ac = ArchiveClassifier()
        state = _make_state("a1")
        assert len(state.archive_log.entries) == 0

        state = ac.archive_item(state, {"status": "completed", "title": "done"}, "finished")
        assert len(state.archive_log.entries) == 1
        assert state.archive_log.total_archived == 1
        assert state.archive_log.entries[0].category == "completed_goal"

    def test_categories_constant(self):
        assert "completed_goal" in ArchiveClassifier.CATEGORIES
        assert "manual" in ArchiveClassifier.CATEGORIES


# ==================== Recalibration Scheduler Tests ====================

class TestRecalibrationScheduler:
    def test_run_recalibration_not_found(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        sched = RecalibrationScheduler(mgr)
        result = sched.run_recalibration("missing")
        assert result["status"] == "not_found"

    def test_run_recalibration_basic(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("a1"))
        sched = RecalibrationScheduler(mgr)
        result = sched.run_recalibration("a1")
        assert result["status"] == "completed"
        assert result["cycle_count"] == 1

    def test_run_recalibration_findings(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        state = _make_state(
            "a1",
            agent_state=AgentState(
                active_goals=[
                    _make_goal("g1", status=GoalStatus.IN_PROGRESS, progress_percent=5.0),
                    _make_goal("g2", status=GoalStatus.PENDING),
                ],
                task_queue=[
                    _make_task("t1", status=TaskStatus.BLOCKED),
                    _make_task("t2", status=TaskStatus.FAILED),
                ],
            ),
            automation_progress=[
                AutomationProgress(category="tests", total_items=100, completed_items=20, coverage_percent=20.0),
            ],
        )
        mgr.save_state(state)
        sched = RecalibrationScheduler(mgr)
        result = sched.run_recalibration("a1")
        assert len(result["findings"]) >= 5  # low progress, pending, blocked, failed, low coverage

    def test_run_all(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("a1"))
        mgr.save_state(_make_state("a2"))
        sched = RecalibrationScheduler(mgr)
        result = sched.run_all()
        assert result["agents_processed"] == 2

    def test_recalibration_increments_cycle(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("a1"))
        sched = RecalibrationScheduler(mgr)
        sched.run_recalibration("a1")
        sched.run_recalibration("a1")
        loaded = mgr.load_state("a1")
        assert loaded.recalibration.cycle_count == 2

    def test_get_status(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        sched = RecalibrationScheduler(mgr, interval_seconds=3600)
        status = sched.get_status()
        assert status["running"] is False
        assert status["interval_seconds"] == 3600


# ==================== Global Aggregator Tests ====================

class TestGlobalAggregator:
    def test_aggregate_system_health(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(
            _make_state("a1", system_state=SystemState(status="active", memory_usage_mb=100, cpu_usage_percent=50))
        )
        mgr.save_state(
            _make_state("a2", system_state=SystemState(status="idle", memory_usage_mb=200, cpu_usage_percent=30))
        )
        agg = GlobalAggregator(mgr)
        health = agg.aggregate_system_health()
        assert health["agent_count"] == 2
        assert health["avg_memory_mb"] == 150.0
        assert health["status_counts"]["active"] == 1

    def test_aggregate_goal_progress(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(
            _make_state(
                "a1",
                agent_state=AgentState(active_goals=[
                    _make_goal("g1", status=GoalStatus.COMPLETED, progress_percent=100),
                    _make_goal("g2", status=GoalStatus.IN_PROGRESS, progress_percent=50),
                ]),
            )
        )
        agg = GlobalAggregator(mgr)
        gp = agg.aggregate_goal_progress()
        assert gp["total_goals"] == 2
        assert gp["avg_progress_percent"] == 75.0

    def test_aggregate_automation_coverage(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(
            _make_state(
                "a1",
                automation_progress=[
                    AutomationProgress(category="tests", total_items=100, completed_items=80),
                ],
            )
        )
        mgr.save_state(
            _make_state(
                "a2",
                automation_progress=[
                    AutomationProgress(category="tests", total_items=50, completed_items=20),
                ],
            )
        )
        agg = GlobalAggregator(mgr)
        ac = agg.aggregate_automation_coverage()
        assert ac["by_category"]["tests"]["total_items"] == 150
        assert ac["by_category"]["tests"]["completed_items"] == 100

    def test_get_global_view(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("a1"))
        agg = GlobalAggregator(mgr)
        view = agg.get_global_view()
        assert "system_health" in view
        assert "goal_progress" in view
        assert "automation_coverage" in view

    def test_empty_aggregation(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        agg = GlobalAggregator(mgr)
        health = agg.aggregate_system_health()
        assert health["agent_count"] == 0
        assert health["avg_memory_mb"] == 0


# ==================== Thread Safety Tests ====================

class TestThreadSafety:
    def test_concurrent_saves(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        errors = []

        def save_agent(idx):
            try:
                mgr.save_state(_make_state(f"agent-{idx}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=save_agent, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(mgr.list_agents()) == 10

    def test_concurrent_read_write(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        mgr.save_state(_make_state("shared"))
        errors = []

        def reader():
            try:
                for _ in range(5):
                    mgr.load_state("shared")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for _ in range(5):
                    mgr.update_state("shared", {"system_state": {"active_tasks": 1}})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads += [threading.Thread(target=writer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ==================== Integration Tests ====================

class TestEventTypeIntegration:
    def test_recalibration_start_event(self):
        from event_backbone import EventType
        assert EventType.RECALIBRATION_START.value == "recalibration_start"

    def test_rosetta_updated_event(self):
        from event_backbone import EventType
        assert EventType.ROSETTA_UPDATED.value == "rosetta_updated"

    def test_event_backbone_still_works(self):
        from event_backbone import EventBackbone, EventType
        bb = EventBackbone()
        eid = bb.publish(EventType.ROSETTA_UPDATED, {"agent_id": "a1"})
        assert eid is not None


class TestPromptStepIntegration:
    def test_transition_step_exists(self):
        from self_automation_orchestrator import PromptStep
        assert PromptStep.TRANSITION.value == "transition"

    def test_transition_template(self):
        from self_automation_orchestrator import SelfAutomationOrchestrator, PromptStep
        orch = SelfAutomationOrchestrator()
        assert PromptStep.TRANSITION in orch.PROMPT_TEMPLATES

    def test_generate_prompt_transition(self):
        from self_automation_orchestrator import SelfAutomationOrchestrator, TaskCategory
        orch = SelfAutomationOrchestrator()
        task = orch.create_task(
            title="Transition test",
            category=TaskCategory.SELF_IMPROVEMENT,
            module_name="rosetta",
        )
        from self_automation_orchestrator import PromptStep
        prompt = orch.generate_prompt(task, PromptStep.TRANSITION)
        assert "rosetta" in prompt


class TestPersistenceManagerIntegration:
    def test_save_and_load_rosetta_state(self, tmp_path):
        from persistence_manager import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path / "murphy"))
        state_data = {"identity": {"agent_id": "a1", "name": "Test"}}
        pm.save_rosetta_state("a1", state_data)
        loaded = pm.load_rosetta_state("a1")
        assert loaded is not None
        assert loaded["identity"]["agent_id"] == "a1"

    def test_load_rosetta_state_missing(self, tmp_path):
        from persistence_manager import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path / "murphy"))
        assert pm.load_rosetta_state("nope") is None

    def test_list_rosetta_agents(self, tmp_path):
        from persistence_manager import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path / "murphy"))
        pm.save_rosetta_state("a1", {"id": "a1"})
        pm.save_rosetta_state("a2", {"id": "a2"})
        agents = pm.list_rosetta_agents()
        assert "a1" in agents
        assert "a2" in agents

    def test_rosetta_dir_created(self, tmp_path):
        from persistence_manager import PersistenceManager
        pm = PersistenceManager(persistence_dir=str(tmp_path / "murphy"))
        rosetta_dir = tmp_path / "murphy" / "rosetta"
        assert rosetta_dir.is_dir()
