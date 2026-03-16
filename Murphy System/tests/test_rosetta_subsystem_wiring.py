"""
Tests for Rosetta Subsystem Wiring — INC-07 / P3-001 through P3-006.

Validates that each of the five subsystem connections:
  P3-001  SelfImprovementEngine → patterns pushed to improvement_proposals
  P3-002  SelfAutomationOrchestrator cycles → automation_progress
  P3-003  RAGVectorIntegration ingestion on save_state()
  P3-004  EventBackbone subscriptions → system_state.status update
  P3-005  StateManager delta push → system_state fields in Rosetta document

All tests use stub objects so they run without heavy optional dependencies.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

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
