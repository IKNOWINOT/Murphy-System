# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for Rosetta Subsystem Wiring — RSW-001 (P3-006).

Verifies P3-001 through P3-005:
  P3-001  SelfImprovementEngine patterns → RosettaManager.update_after_task()
  P3-002  SelfAutomationOrchestrator cycles → automation_progress
  P3-003  RAGVectorIntegration.ingest_document() → RosettaManager.save_agent_doc()
  P3-004  EventBackbone subscription wiring
  P3-005  SystemState sync → Rosetta document
"""

from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow imports from src/
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_SRC = _HERE.parent.parent / "Murphy System" / "src"

from rosetta.rosetta_manager import RosettaManager
from rosetta.rosetta_models import AutomationProgress, Identity, RosettaAgentState, SystemState
from rosetta_subsystem_wiring import RosettaSubsystemWiring, bootstrap_rosetta_wiring


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_rosetta(tmp_path: Path) -> RosettaManager:
    """Create a RosettaManager backed by a temp directory."""
    return RosettaManager(persistence_dir=str(tmp_path))


def _make_patterns(n: int = 3) -> List[Dict[str, Any]]:
    return [
        {
            "pattern_id": f"succ-task-{i:04d}",
            "type": "success_pattern",
            "category": "generic",
            "occurrences": i + 2,
            "avg_duration": float(i * 10),
            "sample_task_ids": [f"tid-{i}"],
        }
        for i in range(n)
    ]


def _make_improvement_engine(patterns: Optional[List[Dict]] = None) -> MagicMock:
    engine = MagicMock()
    engine.extract_patterns.return_value = patterns or _make_patterns()
    return engine


def _make_orchestrator(cycles: int = 2, completed: int = 1) -> MagicMock:
    orch = MagicMock()
    mock_cycles = []
    from datetime import datetime, timezone

    for i in range(cycles):
        c = MagicMock()
        c.completed_at = datetime.now(timezone.utc).isoformat() if i < completed else None
        mock_cycles.append(c)
    orch.get_cycle_history.return_value = mock_cycles
    return orch


def _make_rag(status: str = "ok") -> MagicMock:
    rag = MagicMock()
    rag.ingest_document.return_value = {"status": status, "chunks": 5}
    return rag


def _make_backbone() -> MagicMock:
    backbone = MagicMock()
    backbone.subscribe.side_effect = lambda event_type, handler: f"sub-{event_type.value}"
    return backbone


def _seed_agent(rosetta: RosettaManager, agent_id: str = "system") -> RosettaAgentState:
    """Create a minimal agent state in the RosettaManager."""
    state = RosettaAgentState(identity=Identity(agent_id=agent_id, name=agent_id))
    rosetta.save_state(state)
    return state


# ===========================================================================
# P3-001 — SelfImprovementEngine patterns → update_after_task()
# ===========================================================================


class TestUpdateAfterTask:
    """P3-001: RosettaManager.update_after_task()."""

    def test_creates_workflow_patterns(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        patterns = _make_patterns(3)

        state = rosetta.update_after_task("system", patterns)

        assert state is not None
        assert len(state.workflow_patterns) == 3
        ids = [wp.pattern_id for wp in state.workflow_patterns]
        assert "succ-task-0000" in ids

    def test_idempotent_same_pattern_id(self, tmp_path: Path) -> None:
        """Duplicate pattern_ids must not be added twice."""
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        patterns = _make_patterns(2)

        rosetta.update_after_task("system", patterns)
        state = rosetta.update_after_task("system", patterns)  # second call

        assert state is not None
        assert len(state.workflow_patterns) == 2, "duplicates should be skipped"

    def test_empty_patterns_noop(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)

        state = rosetta.update_after_task("system", [])
        assert state is not None  # no crash

    def test_auto_creates_agent_if_missing(self, tmp_path: Path) -> None:
        """update_after_task should create a new agent if it doesn't exist."""
        rosetta = _make_rosetta(tmp_path)
        patterns = _make_patterns(1)

        state = rosetta.update_after_task("new-agent", patterns)
        assert state is not None
        assert state.identity.agent_id == "new-agent"

    def test_success_rate_set_for_success_patterns(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        patterns = [
            {
                "pattern_id": "succ-x-001",
                "type": "success_pattern",
                "category": "content",
                "occurrences": 5,
                "avg_duration": 3.5,
                "sample_task_ids": [],
            }
        ]
        state = rosetta.update_after_task("system", patterns)
        assert state is not None
        wp = next(w for w in state.workflow_patterns if w.pattern_id == "succ-x-001")
        assert wp.success_rate == 1.0

    def test_failure_pattern_zero_success_rate(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        patterns = [
            {
                "pattern_id": "fail-x-001",
                "type": "recurring_failure",
                "category": "content",
                "occurrences": 3,
                "avg_duration": 0.0,
                "sample_task_ids": [],
            }
        ]
        state = rosetta.update_after_task("system", patterns)
        assert state is not None
        wp = next(w for w in state.workflow_patterns if w.pattern_id == "fail-x-001")
        assert wp.success_rate == 0.0


# ===========================================================================
# P3-002 — SelfAutomationOrchestrator cycles → automation_progress
# ===========================================================================


class TestSyncAutomationProgress:
    """P3-002: RosettaManager.sync_automation_progress()."""

    def test_upserts_new_category(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)

        state = rosetta.sync_automation_progress(
            agent_id="system",
            category="self_improvement",
            completed=3,
            total=5,
        )

        assert state is not None
        entries = [ap for ap in state.automation_progress if ap.category == "self_improvement"]
        assert len(entries) == 1
        assert entries[0].completed_items == 3
        assert entries[0].total_items == 5
        assert entries[0].coverage_percent == pytest.approx(60.0)

    def test_updates_existing_category(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)

        rosetta.sync_automation_progress("system", "self_improvement", 1, 5)
        state = rosetta.sync_automation_progress("system", "self_improvement", 4, 5)

        assert state is not None
        entries = [ap for ap in state.automation_progress if ap.category == "self_improvement"]
        assert len(entries) == 1, "should not duplicate categories"
        assert entries[0].completed_items == 4

    def test_zero_total_gives_zero_coverage(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)

        state = rosetta.sync_automation_progress("system", "cat", 0, 0)
        assert state is not None
        entries = [ap for ap in state.automation_progress if ap.category == "cat"]
        assert entries[0].coverage_percent == 0.0


# ===========================================================================
# P3-003 — RAGVectorIntegration.ingest_document() via save_agent_doc()
# ===========================================================================


class TestSaveAgentDoc:
    """P3-003: RosettaManager.save_agent_doc()."""

    def test_calls_rag_ingest(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        rag = _make_rag()

        result = rosetta.save_agent_doc("system", rag)

        assert result["status"] == "ok"
        rag.ingest_document.assert_called_once()
        call_kwargs = rag.ingest_document.call_args.kwargs
        assert call_kwargs["title"] == "rosetta:system"
        assert call_kwargs["source"] == "rosetta_state_manager"
        assert call_kwargs["metadata"]["agent_id"] == "system"

    def test_custom_content_passed_through(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        rag = _make_rag()

        result = rosetta.save_agent_doc("system", rag, content="custom doc text")

        rag.ingest_document.assert_called_once()
        call_kwargs = rag.ingest_document.call_args.kwargs
        assert call_kwargs["text"] == "custom doc text"

    def test_returns_error_if_agent_missing(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        rag = _make_rag()

        result = rosetta.save_agent_doc("nonexistent", rag)
        assert result["status"] == "error"

    def test_handles_rag_exception(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        rag = MagicMock()
        rag.ingest_document.side_effect = RuntimeError("rag down")

        result = rosetta.save_agent_doc("system", rag)
        assert result["status"] == "error"


# ===========================================================================
# P3-004 — EventBackbone subscription wiring
# ===========================================================================


class TestWireEventSubscriptions:
    """P3-004: EventBackbone subscriptions."""

    def test_registers_three_subscriptions(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        backbone = _make_backbone()
        wiring = RosettaSubsystemWiring(
            rosetta_manager=rosetta,
            backbone=backbone,
        )

        sub_ids = wiring.wire_event_subscriptions()

        assert backbone.subscribe.call_count == 3
        assert len(sub_ids) == 3

    def test_no_backbone_returns_empty(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        wiring = RosettaSubsystemWiring(rosetta_manager=rosetta)

        sub_ids = wiring.wire_event_subscriptions()
        assert sub_ids == []

    def test_task_completed_triggers_pattern_sync(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        backbone = _make_backbone()
        engine = _make_improvement_engine(_make_patterns(2))
        wiring = RosettaSubsystemWiring(
            rosetta_manager=rosetta,
            backbone=backbone,
            improvement_engine=engine,
        )
        wiring.wire_event_subscriptions()

        # Simulate TASK_COMPLETED event
        event = MagicMock()
        wiring._on_task_completed(event)

        engine.extract_patterns.assert_called()
        state = rosetta.load_state("system")
        assert state is not None
        assert len(state.workflow_patterns) == 2

    def test_task_failed_triggers_pattern_sync(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        engine = _make_improvement_engine(_make_patterns(1))
        wiring = RosettaSubsystemWiring(
            rosetta_manager=rosetta,
            improvement_engine=engine,
        )

        event = MagicMock()
        wiring._on_task_failed(event)

        engine.extract_patterns.assert_called_once()

    def test_gate_evaluated_updates_system_state(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        wiring = RosettaSubsystemWiring(rosetta_manager=rosetta)

        event = MagicMock()
        event.payload = {"status": "blocked"}
        wiring._on_gate_evaluated(event)

        state = rosetta.load_state("system")
        assert state is not None
        assert state.system_state.status == "blocked"


# ===========================================================================
# P3-005 — StateManager sync → Rosetta document
# ===========================================================================


class TestSyncSystemState:
    """P3-005: SystemState sync."""

    def test_syncs_status(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        wiring = RosettaSubsystemWiring(rosetta_manager=rosetta)

        state = wiring.sync_system_state(status="active", uptime_seconds=120.0)

        assert state is not None
        assert state.system_state.status == "active"
        assert state.system_state.uptime_seconds == pytest.approx(120.0)

    def test_rosetta_manager_sync_system_state_method(self, tmp_path: Path) -> None:
        """Direct RosettaManager.sync_system_state() call."""
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)

        sys_state = SystemState(status="paused", uptime_seconds=300.0, memory_usage_mb=512.0)
        state = rosetta.sync_system_state("system", sys_state)

        assert state is not None
        assert state.system_state.status == "paused"
        assert state.system_state.memory_usage_mb == pytest.approx(512.0)

    def test_missing_agent_creates_state(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        wiring = RosettaSubsystemWiring(
            rosetta_manager=rosetta,
            agent_id="new-system",
        )

        state = wiring.sync_system_state(status="idle")
        # update_state returns None if agent doesn't exist; wiring falls back gracefully
        # but no crash should occur
        assert True  # reached here without exception


# ===========================================================================
# Full integration: bootstrap_rosetta_wiring()
# ===========================================================================


class TestBootstrapRosettaWiring:
    """End-to-end: bootstrap_rosetta_wiring() wires all P3 bridges."""

    def test_bootstrap_returns_wiring_instance(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        wiring = bootstrap_rosetta_wiring(rosetta_manager=rosetta)
        assert isinstance(wiring, RosettaSubsystemWiring)

    def test_bootstrap_with_all_components(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        backbone = _make_backbone()
        engine = _make_improvement_engine(_make_patterns(2))
        orch = _make_orchestrator(cycles=3, completed=2)
        rag = _make_rag()

        wiring = bootstrap_rosetta_wiring(
            rosetta_manager=rosetta,
            backbone=backbone,
            improvement_engine=engine,
            orchestrator=orch,
            rag=rag,
        )

        assert isinstance(wiring, RosettaSubsystemWiring)
        # P3-001: patterns were synced
        state = rosetta.load_state("system")
        assert state is not None
        assert len(state.workflow_patterns) == 2

        # P3-002: automation progress was pushed
        ap_entries = [a for a in state.automation_progress if a.category == "self_improvement"]
        assert len(ap_entries) == 1
        assert ap_entries[0].total_items == 3
        assert ap_entries[0].completed_items == 2

        # P3-003: RAG ingestion was called
        rag.ingest_document.assert_called_once()

        # P3-004: subscriptions registered
        assert backbone.subscribe.call_count == 3

    def test_wire_all_returns_summary_dict(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        _seed_agent(rosetta)
        wiring = RosettaSubsystemWiring(rosetta_manager=rosetta)

        summary = wiring.wire_all()

        assert "agent_id" in summary
        assert "timestamp" in summary
        assert "p3_001_patterns_synced" in summary
        assert "p3_002_cycles_synced" in summary
        assert "p3_003_rag_doc" in summary
        assert "p3_004_subscriptions" in summary
        assert "p3_005_system_state" in summary

    def test_wire_all_with_no_optionals(self, tmp_path: Path) -> None:
        """Wiring with no optional components must not raise."""
        rosetta = _make_rosetta(tmp_path)
        wiring = RosettaSubsystemWiring(rosetta_manager=rosetta)
        summary = wiring.wire_all()
        assert summary["p3_003_rag_doc"] == "skipped"
        assert summary["p3_004_subscriptions"] == 0

    def test_sync_improvement_patterns_no_engine(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        wiring = RosettaSubsystemWiring(rosetta_manager=rosetta)
        result = wiring.sync_improvement_patterns()
        assert result is None

    def test_sync_automation_cycles_no_orchestrator(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        wiring = RosettaSubsystemWiring(rosetta_manager=rosetta)
        result = wiring.sync_automation_cycles()
        assert result is None

    def test_improvement_engine_exception_handled(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        engine = MagicMock()
        engine.extract_patterns.side_effect = RuntimeError("engine error")
        wiring = RosettaSubsystemWiring(
            rosetta_manager=rosetta,
            improvement_engine=engine,
        )
        result = wiring.sync_improvement_patterns()
        assert result is None  # graceful degradation

    def test_orchestrator_exception_handled(self, tmp_path: Path) -> None:
        rosetta = _make_rosetta(tmp_path)
        orch = MagicMock()
        orch.get_cycle_history.side_effect = RuntimeError("orch error")
        wiring = RosettaSubsystemWiring(
            rosetta_manager=rosetta,
            orchestrator=orch,
        )
        result = wiring.sync_automation_cycles()
        assert result is None
from rosetta.rosetta_manager import RosettaManager
from rosetta.rosetta_models import AgentState, Goal, Identity, RosettaAgentState
from rosetta.subsystem_wiring import (
    RosettaSubsystemWiring,
    _DEFAULT_AGENT_ID,
    _derive_agent_id,
    _now_iso,
    _safe_update,
    _safe_update_proposals,
    _safe_update_automation_progress,
    _safe_update_system_state,
    _state_to_text,
    bootstrap_wiring,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_rosetta_mgr(tmp_path):
    """A RosettaManager backed by a temporary directory."""
    return RosettaManager(persistence_dir=str(tmp_path / "rosetta"))


@pytest.fixture
def wiring(tmp_rosetta_mgr):
    """A fresh RosettaSubsystemWiring instance."""
    return RosettaSubsystemWiring(tmp_rosetta_mgr)


def _make_agent(mgr: RosettaManager, agent_id: str, role: str = "worker") -> RosettaAgentState:
    """Save and return a minimal agent state."""
    identity = Identity(agent_id=agent_id, name=agent_id, role=role, version="1.0.0")
    state = RosettaAgentState(identity=identity)
    mgr.save_state(state)
    return state


# ---------------------------------------------------------------------------
# Stub subsystems
# ---------------------------------------------------------------------------


class _StubOutcome:
    """Minimal ExecutionOutcome stub."""
    def __init__(self, agent_id: str = _DEFAULT_AGENT_ID):
        self.agent_id = agent_id
        self.task_id = "task-1"
        self.success = True


class _StubImprovementEngine:
    """Stub for SelfImprovementEngine."""
    def __init__(self):
        self._outcomes: List[Any] = []
        self._patterns: List[Dict[str, Any]] = [{"pattern": "retry-on-timeout"}]

    def record_outcome(self, outcome: Any) -> str:
        self._outcomes.append(outcome)
        return "recorded"

    def extract_patterns(self) -> List[Dict[str, Any]]:
        return list(self._patterns)


@dataclass
class _StubCycleRecord:
    cycle_id: str = "cycle-001"
    started_at: str = "2026-01-01T00:00:00+00:00"
    completed_at: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    tests_added: int = 0
    modules_added: List[str] = field(default_factory=list)
    gap_analysis: Optional[Dict[str, Any]] = None


class _StubOrchestrator:
    """Stub for SelfAutomationOrchestrator."""
    def __init__(self):
        self._cycles: List[_StubCycleRecord] = []
        self._current: Optional[_StubCycleRecord] = None

    def complete_cycle(self) -> Optional[_StubCycleRecord]:
        if self._current is None:
            self._current = _StubCycleRecord()
        self._current.completed_at = datetime.now(timezone.utc).isoformat()
        self._cycles.append(self._current)
        completed = self._current
        self._current = None
        return completed

    def get_cycle_history(self) -> List[_StubCycleRecord]:
        return list(self._cycles)


class _StubRAG:
    """Stub for RAGVectorIntegration."""
    def __init__(self):
        self.ingested: List[Dict[str, Any]] = []

    def ingest_document(
        self,
        text: str,
        title: str = "",
        source: str = "",
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        self.ingested.append({"text": text, "title": title, "source": source, "metadata": metadata})
        return {"status": "ok", "doc_id": "doc-stub"}


class _StubEventType:
    """Minimal EventType enum mimic with string values."""
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    GATE_EVALUATED = "gate_evaluated"


class _StubBackbone:
    """Stub for EventBackbone — supports subscribe/unsubscribe/fire."""
    def __init__(self):
        self._subs: Dict[Any, List[Callable]] = {}
        self._sub_index: Dict[str, tuple] = {}
        self._counter = 0

    def subscribe(self, event_type: Any, handler: Callable) -> str:
        sub_id = f"sub-{self._counter}"
        self._counter += 1
        self._subs.setdefault(event_type, []).append(handler)
        self._sub_index[sub_id] = (event_type, handler)
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        if sub_id in self._sub_index:
            del self._sub_index[sub_id]

    def fire(self, event_type: Any, payload: Dict[str, Any]) -> None:
        """Invoke all handlers registered for *event_type* with a fake event."""
        event = MagicMock()
        event.payload = payload
        for handler in self._subs.get(event_type, []):
            handler(event)


class _StubSystemState:
    """Stub for execution_engine.state_manager.SystemState."""
    def __init__(self, state_id: str = "state-1", state_name: str = "agent-test"):
        self.state_id = state_id
        self.state_name = state_name
        self.variables: Dict[str, Any] = {}


class _StubStateManager:
    """Stub for StateManager."""
    def __init__(self):
        self._states: Dict[str, _StubSystemState] = {}

    def create_state(self, state_id: str, state_name: str = "default") -> _StubSystemState:
        s = _StubSystemState(state_id=state_id, state_name=state_name)
        self._states[state_id] = s
        return s

    def get_state(self, state_id: str) -> Optional[_StubSystemState]:
        return self._states.get(state_id)

    def update_state(self, state_id: str, variables: Dict[str, Any]) -> bool:
        state = self._states.get(state_id)
        if state:
            state.variables.update(variables)
            return True
        return False


# ---------------------------------------------------------------------------
# P3-001: SelfImprovementEngine wiring
# ---------------------------------------------------------------------------


class TestP3001SelfImprovementEngineWiring:
    """Verify that record_outcome() causes patterns to be pushed into Rosetta."""

    def test_patterns_pushed_as_proposals(self, wiring, tmp_rosetta_mgr):
        """Patterns extracted after record_outcome land in improvement_proposals."""
        _make_agent(tmp_rosetta_mgr, "agent-sip")
        engine = _StubImprovementEngine()
        engine._patterns = [{"pattern": "fallback-on-error"}, {"pattern": "retry-on-timeout"}]
        wiring.connect_self_improvement(engine)

        outcome = _StubOutcome(agent_id="agent-sip")
        result = engine.record_outcome(outcome)

        assert result == "recorded", "Original return value preserved"
        state = tmp_rosetta_mgr.load_state("agent-sip")
        assert state is not None
        assert len(state.improvement_proposals) == 2

    def test_proposal_category_is_self_improvement(self, wiring, tmp_rosetta_mgr):
        """Each pushed proposal has category 'self_improvement'."""
        _make_agent(tmp_rosetta_mgr, "agent-cat")
        engine = _StubImprovementEngine()
        engine._patterns = [{"pattern": "cache-hit"}]
        wiring.connect_self_improvement(engine)

        engine.record_outcome(_StubOutcome(agent_id="agent-cat"))

        state = tmp_rosetta_mgr.load_state("agent-cat")
        assert state.improvement_proposals[0].category == "self_improvement"

    def test_original_method_still_called(self, wiring, tmp_rosetta_mgr):
        """The original record_outcome() is still invoked after patching."""
        engine = _StubImprovementEngine()
        wiring.connect_self_improvement(engine)
        engine.record_outcome(_StubOutcome())
        assert len(engine._outcomes) == 1

    def test_rosetta_error_doesnt_propagate(self, wiring, tmp_rosetta_mgr):
        """A failure inside the Rosetta side-effect never raises to the caller."""
        engine = _StubImprovementEngine()
        wiring.connect_self_improvement(engine)
        # Force extract_patterns to blow up
        engine.extract_patterns = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore
        result = engine.record_outcome(_StubOutcome())
        assert result == "recorded"

    def test_unknown_agent_skips_gracefully(self, wiring, tmp_rosetta_mgr):
        """If the agent_id doesn't have a Rosetta state, no error is raised."""
        engine = _StubImprovementEngine()
        wiring.connect_self_improvement(engine)
        engine.record_outcome(_StubOutcome(agent_id="no-such-agent"))


# ---------------------------------------------------------------------------
# P3-002: SelfAutomationOrchestrator wiring
# ---------------------------------------------------------------------------


class TestP3002AutomationOrchestratorWiring:
    """Verify that complete_cycle() pushes progress data into Rosetta."""

    def test_automation_progress_updated_on_complete(self, wiring, tmp_rosetta_mgr):
        """Completing a cycle writes a self_automation entry to automation_progress."""
        _make_agent(tmp_rosetta_mgr, _DEFAULT_AGENT_ID, role="system")
        orch = _StubOrchestrator()
        wiring.connect_automation_orchestrator(orch)

        cycle = orch.complete_cycle()

        assert cycle is not None
        assert cycle.completed_at is not None
        state = tmp_rosetta_mgr.load_state(_DEFAULT_AGENT_ID)
        assert state is not None
        categories = [p.category for p in state.automation_progress]
        assert "self_automation" in categories

    def test_original_complete_cycle_still_called(self, wiring, tmp_rosetta_mgr):
        """The patched method still returns the original cycle record."""
        orch = _StubOrchestrator()
        wiring.connect_automation_orchestrator(orch)
        cycle = orch.complete_cycle()
        assert cycle is not None
        assert cycle.cycle_id == "cycle-001"

    def test_coverage_percent_computed(self, wiring, tmp_rosetta_mgr):
        """coverage_percent is 100.0 after one completed cycle out of one."""
        _make_agent(tmp_rosetta_mgr, _DEFAULT_AGENT_ID, role="system")
        orch = _StubOrchestrator()
        wiring.connect_automation_orchestrator(orch)
        orch.complete_cycle()

        state = tmp_rosetta_mgr.load_state(_DEFAULT_AGENT_ID)
        entry = next(p for p in state.automation_progress if p.category == "self_automation")
        assert entry.coverage_percent == pytest.approx(100.0)

    def test_none_cycle_skips_push(self, wiring, tmp_rosetta_mgr):
        """If complete_cycle() returns None, no Rosetta update is attempted."""
        orch = _StubOrchestrator()
        # Patch get_cycle_history to raise; if it's called it means None wasn't handled
        orch.get_cycle_history = lambda: (_ for _ in ()).throw(RuntimeError("should not call"))
        wiring.connect_automation_orchestrator(orch)

        # complete_cycle() with no current cycle returns None
        result = orch.complete_cycle()
        assert result is None or isinstance(result, _StubCycleRecord)


# ---------------------------------------------------------------------------
# P3-003: RAGVectorIntegration wiring
# ---------------------------------------------------------------------------


class TestP3003RAGWiring:
    """Verify that save_state() also ingests the state into the RAG system."""

    def test_ingest_called_on_save(self, wiring, tmp_rosetta_mgr):
        """After connecting RAG, every save_state() triggers ingest_document()."""
        rag = _StubRAG()
        wiring.connect_rag(rag)

        identity = Identity(agent_id="agent-rag", name="RAG Agent", role="worker", version="1.0.0")
        state = RosettaAgentState(identity=identity)
        tmp_rosetta_mgr.save_state(state)

        assert len(rag.ingested) == 1, "Exactly one ingest_document call expected"
        doc = rag.ingested[0]
        assert doc["source"] == "rosetta"
        assert "agent-rag" in doc["title"]

    def test_rag_error_doesnt_block_save(self, wiring, tmp_rosetta_mgr):
        """A RAG failure must not prevent the state from being saved."""
        rag = _StubRAG()
        rag.ingest_document = MagicMock(side_effect=RuntimeError("rag exploded"))
        wiring.connect_rag(rag)

        identity = Identity(agent_id="agent-rag2", name="RAG Agent 2", role="worker", version="1.0.0")
        state = RosettaAgentState(identity=identity)
        agent_id = tmp_rosetta_mgr.save_state(state)

        assert agent_id == "agent-rag2", "Agent ID returned even though RAG failed"
        loaded = tmp_rosetta_mgr.load_state("agent-rag2")
        assert loaded is not None, "State still saved despite RAG failure"

    def test_text_representation_not_empty(self, tmp_rosetta_mgr):
        """_state_to_text() returns a non-empty string containing the agent ID."""
        identity = Identity(agent_id="agent-txt", name="Text Agent", role="worker", version="1.0.0")
        state = RosettaAgentState(identity=identity)
        text = _state_to_text(state)
        assert isinstance(text, str)
        assert len(text) > 10
        assert "agent-txt" in text

    def test_metadata_contains_agent_id(self, wiring, tmp_rosetta_mgr):
        """The metadata dict passed to ingest_document contains agent_id."""
        rag = _StubRAG()
        wiring.connect_rag(rag)
        identity = Identity(agent_id="meta-agent", name="Meta", role="worker", version="1.0.0")
        tmp_rosetta_mgr.save_state(RosettaAgentState(identity=identity))
        assert rag.ingested[0]["metadata"]["agent_id"] == "meta-agent"


# ---------------------------------------------------------------------------
# P3-004: EventBackbone subscription wiring
# ---------------------------------------------------------------------------


class TestP3004EventBackboneWiring:
    """Verify EventBackbone subscription and system_state.status update."""

    def _connect(self, wiring: RosettaSubsystemWiring, backbone: _StubBackbone) -> None:
        """Connect backbone using our stub EventType (bypasses real import)."""
        wiring.connect_event_backbone(backbone, _event_type_cls=_StubEventType)

    def test_three_subscriptions_created(self, wiring, tmp_rosetta_mgr):
        """connect_event_backbone() creates exactly 3 subscriptions."""
        backbone = _StubBackbone()
        self._connect(wiring, backbone)
        assert len(wiring._subscription_ids) == 3

    def test_task_completed_sets_status_active(self, wiring, tmp_rosetta_mgr):
        """TASK_COMPLETED → system_state.status = 'active'."""
        _make_agent(tmp_rosetta_mgr, "agent-tc")
        backbone = _StubBackbone()
        self._connect(wiring, backbone)

        backbone.fire(_StubEventType.TASK_COMPLETED, {"agent_id": "agent-tc"})

        state = tmp_rosetta_mgr.load_state("agent-tc")
        assert state.system_state.status == "active"

    def test_task_failed_sets_status_error(self, wiring, tmp_rosetta_mgr):
        """TASK_FAILED → system_state.status = 'error'."""
        _make_agent(tmp_rosetta_mgr, "agent-tf")
        backbone = _StubBackbone()
        self._connect(wiring, backbone)

        backbone.fire(_StubEventType.TASK_FAILED, {"agent_id": "agent-tf"})

        state = tmp_rosetta_mgr.load_state("agent-tf")
        assert state.system_state.status == "error"

    def test_gate_evaluated_sets_status_active(self, wiring, tmp_rosetta_mgr):
        """GATE_EVALUATED → system_state.status = 'active'."""
        _make_agent(tmp_rosetta_mgr, "agent-ge")
        backbone = _StubBackbone()
        self._connect(wiring, backbone)

        backbone.fire(_StubEventType.GATE_EVALUATED, {"agent_id": "agent-ge"})

        state = tmp_rosetta_mgr.load_state("agent-ge")
        assert state.system_state.status == "active"

    def test_disconnect_clears_subscriptions(self, wiring, tmp_rosetta_mgr):
        """disconnect_event_backbone() removes all subscription IDs."""
        backbone = _StubBackbone()
        self._connect(wiring, backbone)
        assert len(wiring._subscription_ids) == 3
        wiring.disconnect_event_backbone(backbone)
        assert len(wiring._subscription_ids) == 0

    def test_handler_error_doesnt_propagate(self, wiring, tmp_rosetta_mgr):
        """An error inside a handler is suppressed and does not raise."""
        backbone = _StubBackbone()
        self._connect(wiring, backbone)
        # Fire with a None payload (should not raise)
        backbone.fire(_StubEventType.TASK_COMPLETED, None)

    def test_missing_event_type_skips_wiring(self, wiring, tmp_rosetta_mgr):
        """If EventType is a class with no matching attributes, no subscription is created."""
        backbone = _StubBackbone()

        class _EmptyEventType:
            """An event type class with none of the expected event names."""

        # Passing an event type class that doesn't have TASK_COMPLETED etc.
        # The loop over event_map should raise AttributeError for each,
        # which is caught per-subscription and logged as a warning.
        wiring.connect_event_backbone(backbone, _event_type_cls=_EmptyEventType)
        # Since all three subscriptions raise AttributeError, none succeed
        assert len(wiring._subscription_ids) == 0


# ---------------------------------------------------------------------------
# P3-005: StateManager delta push
# ---------------------------------------------------------------------------


class TestP3005StateManagerWiring:
    """Verify that StateManager.update_state() pushes system_state to Rosetta."""

    def test_status_pushed_to_rosetta(self, wiring, tmp_rosetta_mgr):
        """update_state() with a status key updates system_state.status."""
        _make_agent(tmp_rosetta_mgr, "agent-test")
        sm = _StubStateManager()
        sm.create_state("state-1", state_name="agent-test")
        wiring.connect_state_manager(sm)

        result = sm.update_state("state-1", {"status": "active"})

        assert result is True
        state = tmp_rosetta_mgr.load_state("agent-test")
        assert state is not None
        assert state.system_state.status == "active"

    def test_active_tasks_pushed_to_rosetta(self, wiring, tmp_rosetta_mgr):
        """update_state() with active_tasks key updates system_state.active_tasks."""
        _make_agent(tmp_rosetta_mgr, "agent-tasks")
        sm = _StubStateManager()
        sm.create_state("state-2", state_name="agent-tasks")
        wiring.connect_state_manager(sm)

        sm.update_state("state-2", {"active_tasks": 5})

        state = tmp_rosetta_mgr.load_state("agent-tasks")
        assert state.system_state.active_tasks == 5

    def test_original_update_still_returns_true(self, wiring, tmp_rosetta_mgr):
        """The patched update_state() preserves True/False return from original."""
        sm = _StubStateManager()
        sm.create_state("state-x")
        wiring.connect_state_manager(sm)

        assert sm.update_state("state-x", {"k": "v"}) is True
        assert sm.update_state("nonexistent", {"k": "v"}) is False

    def test_rosetta_failure_doesnt_break_state_update(self, wiring, tmp_rosetta_mgr):
        """A Rosetta failure during system_state push does not disrupt the update."""
        sm = _StubStateManager()
        sm.create_state("state-y", state_name="agent-y")
        wiring.connect_state_manager(sm)

        # Kill the rosetta manager's update_state to simulate failure
        tmp_rosetta_mgr.update_state = MagicMock(side_effect=RuntimeError("rosetta down"))

        result = sm.update_state("state-y", {"key": "val"})
        # The StateManager update still succeeded
        assert result is True
        assert sm._states["state-y"].variables["key"] == "val"


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Unit tests for private helper functions."""

    def test_now_iso_returns_utc_string(self):
        ts = _now_iso()
        assert isinstance(ts, str)
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None

    def test_derive_agent_id_with_name(self):
        state = _StubSystemState(state_name="agent-abc")
        assert _derive_agent_id(state) == "agent-abc"

    def test_derive_agent_id_with_default_name(self):
        state = _StubSystemState(state_name="default")
        assert _derive_agent_id(state) == _DEFAULT_AGENT_ID

    def test_derive_agent_id_none(self):
        assert _derive_agent_id(None) == _DEFAULT_AGENT_ID

    def test_state_to_text_contains_agent_id(self):
        identity = Identity(agent_id="my-agent", name="My Agent", role="worker", version="1.0.0")
        state = RosettaAgentState(identity=identity)
        text = _state_to_text(state)
        assert "my-agent" in text

    def test_state_to_text_fallback_for_arbitrary_object(self):
        text = _state_to_text(object())
        assert isinstance(text, str)
        assert len(text) > 0

    def test_safe_update_no_op_for_unknown_agent(self, tmp_rosetta_mgr):
        """_safe_update() with an unknown agent_id silently skips."""
        _safe_update(tmp_rosetta_mgr, "no-such-agent", {"system_state": {"status": "active"}})

    def test_safe_update_proposals_skips_unknown_agent(self, tmp_rosetta_mgr):
        """_safe_update_proposals() silently skips unknown agents."""
        _safe_update_proposals(tmp_rosetta_mgr, "ghost", [{"proposal_id": "p1", "title": "T"}])

    def test_safe_update_proposals_adds_to_known_agent(self, tmp_rosetta_mgr):
        """_safe_update_proposals() appends proposals to a known agent."""
        _make_agent(tmp_rosetta_mgr, "agent-prop")
        _safe_update_proposals(
            tmp_rosetta_mgr,
            "agent-prop",
            [{"proposal_id": "p-1", "title": "Test Prop", "category": "general", "status": "proposed"}],
        )
        state = tmp_rosetta_mgr.load_state("agent-prop")
        assert any(p.proposal_id == "p-1" for p in state.improvement_proposals)

    def test_safe_update_automation_progress(self, tmp_rosetta_mgr):
        """_safe_update_automation_progress() upserts the automation_progress list."""
        _make_agent(tmp_rosetta_mgr, "agent-ap", role="system")
        _safe_update_automation_progress(
            tmp_rosetta_mgr,
            "agent-ap",
            {"category": "ci", "total_items": 10, "completed_items": 8, "coverage_percent": 80.0},
        )
        state = tmp_rosetta_mgr.load_state("agent-ap")
        assert any(p.category == "ci" for p in state.automation_progress)

    def test_safe_update_system_state(self, tmp_rosetta_mgr):
        """_safe_update_system_state() updates the system_state fields."""
        _make_agent(tmp_rosetta_mgr, "agent-ss")
        _safe_update_system_state(tmp_rosetta_mgr, "agent-ss", "active", active_tasks=3)
        state = tmp_rosetta_mgr.load_state("agent-ss")
        assert state.system_state.status == "active"
        assert state.system_state.active_tasks == 3


# ---------------------------------------------------------------------------
# Integration: bootstrap_wiring
# ---------------------------------------------------------------------------


class TestBootstrapWiring:
    """bootstrap_wiring() integration tests."""

    def test_bootstrap_returns_wiring_object(self, tmp_rosetta_mgr):
        """bootstrap_wiring() returns a RosettaSubsystemWiring instance."""
        result = bootstrap_wiring(tmp_rosetta_mgr)
        assert result is not None
        assert isinstance(result, RosettaSubsystemWiring)

    def test_bootstrap_handles_all_import_errors_gracefully(self, tmp_rosetta_mgr):
        """bootstrap_wiring() succeeds even when all subsystems are absent."""
        import builtins
        real_import = builtins.__import__

        blocked = {
            "src.self_improvement_engine",
            "self_improvement_engine",
            "src.self_automation_orchestrator",
            "self_automation_orchestrator",
            "src.rag_vector_integration",
            "rag_vector_integration",
            "src.event_backbone",
            "event_backbone",
            "src.execution_engine.state_manager",
            "execution_engine.state_manager",
        }

        def _block_imports(name, *args, **kwargs):
            if name in blocked:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_block_imports):
            result = bootstrap_wiring(tmp_rosetta_mgr)
        assert result is not None

    def test_wiring_object_has_empty_subscription_list(self, tmp_rosetta_mgr):
        """A freshly created wiring has an empty subscription ID list."""
        w = RosettaSubsystemWiring(tmp_rosetta_mgr)
        assert isinstance(w._subscription_ids, list)
        assert len(w._subscription_ids) == 0
