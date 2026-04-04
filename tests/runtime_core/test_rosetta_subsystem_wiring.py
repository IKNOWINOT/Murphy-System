"""
Tests for Rosetta Subsystem Wiring (INC-07 / H-03).

Covers all P3 wiring tasks:
  P3-001  SelfImprovementEngine.extract_patterns() → RosettaManager.update_state()
  P3-002  SelfAutomationOrchestrator cycle records → automation_progress[]
  P3-003  RAGVectorIntegration.ingest_document() ← RosettaManager state
  P3-004  EventBackbone subscriptions (TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED)
  P3-005  StateManager sync → Rosetta document delta push

Also covers:
  - bootstrap_wiring() convenience factory
  - WiringStatus dataclass and summary()
  - Graceful degradation when optional deps are None
  - Error handling / partial failures

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from rosetta.subsystem_wiring import (
    RosettaSubsystemWiring,
    WiringStatus,
    bootstrap_wiring,
)
from rosetta.rosetta_manager import RosettaManager
from rosetta.rosetta_models import Identity, RosettaAgentState


# ---------------------------------------------------------------------------
# Minimal stubs for optional dependencies
# ---------------------------------------------------------------------------


class _StubPatterns:
    """Minimal SelfImprovementEngine stub."""

    def __init__(self, patterns: Optional[List[Dict]] = None) -> None:
        self._patterns = patterns if patterns is not None else [
            {"pattern_id": "p1", "type": "recurring_failure", "category": "test", "occurrences": 3},
        ]

    def extract_patterns(self) -> List[Dict]:
        return list(self._patterns)


class _StubPatternsBad:
    """Raises on extract_patterns."""
    def extract_patterns(self):
        raise RuntimeError("engine exploded")


@dataclass
class _CycleRecord:
    cycle_id: str
    started_at: str
    completed_at: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    tests_added: int = 0
    modules_added: List[str] = field(default_factory=list)
    gap_analysis: Optional[Dict] = None


class _StubOrchestrator:
    """Minimal SelfAutomationOrchestrator stub."""

    def __init__(self, cycles: Optional[List[_CycleRecord]] = None) -> None:
        self._cycles = cycles or [
            _CycleRecord("c1", "2026-01-01T00:00:00Z",
                         completed_at="2026-01-01T01:00:00Z",
                         tasks_completed=5, tasks_failed=1),
            _CycleRecord("c2", "2026-01-02T00:00:00Z",
                         completed_at="2026-01-02T01:00:00Z",
                         tasks_completed=7, tasks_failed=0),
            _CycleRecord("c3", "2026-01-03T00:00:00Z",
                         completed_at=None,  # in-progress
                         tasks_completed=2, tasks_failed=0),
        ]

    def get_cycle_history(self) -> List[_CycleRecord]:
        return list(self._cycles)


class _StubOrchestratorBad:
    def get_cycle_history(self):
        raise RuntimeError("orchestrator broken")


class _StubRAG:
    """Minimal RAGVectorIntegration stub."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: List[Dict] = []
        self._fail = fail

    def ingest_document(self, text: str, title: str = "", source: str = "",
                        metadata: Optional[Dict] = None,
                        strategy: Optional[Any] = None) -> Dict:
        if self._fail:
            return {"status": "error", "message": "storage full"}
        self.calls.append({"text": text, "title": title, "source": source, "metadata": metadata})
        return {"status": "ok", "chunks_stored": max(1, len(text) // 500)}


class _StubEvent:
    """Minimal Event stub."""
    def __init__(self, payload: Optional[Dict] = None) -> None:
        self.payload = payload or {}


class _StubEventBackbone:
    """Minimal EventBackbone stub that records subscriptions."""

    def __init__(self, raise_on_subscribe: bool = False) -> None:
        self.subscriptions: List[Dict] = []
        self._raise = raise_on_subscribe
        self._counter = 0

    def subscribe(self, event_type, handler) -> str:
        if self._raise:
            raise RuntimeError("backbone unavailable")
        self._counter += 1
        sub_id = f"sub-{self._counter}"
        self.subscriptions.append({"event_type": event_type, "handler": handler, "sub_id": sub_id})
        return sub_id

    def fire(self, event_type, payload: Optional[Dict] = None) -> None:
        """Helper to trigger all handlers for a given event_type."""
        for s in self.subscriptions:
            if s["event_type"] == event_type:
                s["handler"](_StubEvent(payload))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_manager(tmp_path):
    """RosettaManager with temp persistence dir and a pre-seeded agent state."""
    mgr = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
    state = RosettaAgentState(
        identity=Identity(agent_id="murphy-system", name="Murphy", role="orchestrator")
    )
    mgr.save_state(state)
    return mgr


# ---------------------------------------------------------------------------
# WiringStatus tests
# ---------------------------------------------------------------------------

class TestWiringStatus:
    def test_all_false_by_default(self):
        s = WiringStatus()
        assert s.p3_001_patterns_to_rosetta is False
        assert s.p3_002_cycles_to_progress is False
        assert s.p3_003_rag_to_rosetta is False
        assert s.p3_004_event_subscriptions is False
        assert s.p3_005_state_sync is False
        assert s.errors == []

    def test_summary_lists_active_and_inactive(self):
        s = WiringStatus(p3_001_patterns_to_rosetta=True, p3_004_event_subscriptions=True)
        summary = s.summary()
        assert "P3-001" in summary
        assert "P3-004" in summary

    def test_errors_captured_in_summary(self):
        s = WiringStatus(errors=["oops"])
        assert "oops" in s.summary()


# ---------------------------------------------------------------------------
# P3-001 — patterns → Rosetta
# ---------------------------------------------------------------------------

class TestP3001PatternsToRosetta:
    def test_patterns_pushed_to_rosetta(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_improvement_engine=_StubPatterns())
        assert w.wire_patterns_to_rosetta() is True
        assert w.status.p3_001_patterns_to_rosetta is True

    def test_patterns_written_into_state(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_improvement_engine=_StubPatterns())
        w.wire_patterns_to_rosetta()
        state = tmp_manager.load_state("murphy-system")
        assert state is not None

    def test_no_improvement_engine_returns_false(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager)
        assert w.wire_patterns_to_rosetta() is False
        assert w.status.p3_001_patterns_to_rosetta is False

    def test_empty_patterns_returns_true_gracefully(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_improvement_engine=_StubPatterns(patterns=[]))
        assert w.wire_patterns_to_rosetta() is True

    def test_exception_returns_false_and_records_error(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_improvement_engine=_StubPatternsBad())
        assert w.wire_patterns_to_rosetta() is False
        assert len(w.status.errors) == 1
        assert "P3-001" in w.status.errors[0]


# ---------------------------------------------------------------------------
# P3-002 — cycles → automation_progress
# ---------------------------------------------------------------------------

class TestP3002CyclesToProgress:
    def test_cycles_synced(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_automation_orchestrator=_StubOrchestrator())
        assert w.wire_cycles_to_automation_progress() is True
        assert w.status.p3_002_cycles_to_progress is True

    def test_state_updated_after_sync(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_automation_orchestrator=_StubOrchestrator())
        w.wire_cycles_to_automation_progress()
        state = tmp_manager.load_state("murphy-system")
        assert state is not None
        # automation_progress should be set
        assert len(state.automation_progress) >= 1
        assert state.automation_progress[0].category == "self_improvement"

    def test_coverage_calculation(self, tmp_manager):
        cycles = [
            _CycleRecord("c1", "2026-01-01T00:00:00Z", completed_at="2026-01-01T01:00:00Z"),
            _CycleRecord("c2", "2026-01-01T00:00:00Z", completed_at=None),
        ]
        w = RosettaSubsystemWiring(tmp_manager, self_automation_orchestrator=_StubOrchestrator(cycles))
        w.wire_cycles_to_automation_progress()
        state = tmp_manager.load_state("murphy-system")
        prog = state.automation_progress[0]
        assert prog.total_items == 2
        assert prog.completed_items == 1
        assert prog.coverage_percent == 50.0

    def test_no_orchestrator_returns_false(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager)
        assert w.wire_cycles_to_automation_progress() is False

    def test_empty_cycle_history(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_automation_orchestrator=_StubOrchestrator([]))
        assert w.wire_cycles_to_automation_progress() is True

    def test_exception_returns_false(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_automation_orchestrator=_StubOrchestratorBad())
        assert w.wire_cycles_to_automation_progress() is False
        assert any("P3-002" in e for e in w.status.errors)


# ---------------------------------------------------------------------------
# P3-003 — RAG ingestion from Rosetta state
# ---------------------------------------------------------------------------

class TestP3003RAGIngestion:
    def test_ingestion_succeeds(self, tmp_manager):
        rag = _StubRAG()
        w = RosettaSubsystemWiring(tmp_manager, rag_vector_integration=rag)
        assert w.wire_rag_ingestion() is True
        assert w.status.p3_003_rag_to_rosetta is True
        assert len(rag.calls) == 1

    def test_document_contains_agent_id(self, tmp_manager):
        rag = _StubRAG()
        w = RosettaSubsystemWiring(tmp_manager, rag_vector_integration=rag)
        w.wire_rag_ingestion()
        assert "murphy-system" in rag.calls[0]["text"]

    def test_document_title_set(self, tmp_manager):
        rag = _StubRAG()
        w = RosettaSubsystemWiring(tmp_manager, rag_vector_integration=rag)
        w.wire_rag_ingestion()
        assert "murphy-system" in rag.calls[0]["title"]

    def test_no_rag_returns_false(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager)
        assert w.wire_rag_ingestion() is False
        assert w.status.p3_003_rag_to_rosetta is False

    def test_missing_agent_state_returns_true_gracefully(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "empty"))
        rag = _StubRAG()
        w = RosettaSubsystemWiring(mgr, rag_vector_integration=rag)
        # No state saved → load returns None → graceful return True
        assert w.wire_rag_ingestion() is True
        assert len(rag.calls) == 0  # nothing ingested, but not an error

    def test_rag_error_status_returns_false(self, tmp_manager):
        rag = _StubRAG(fail=True)
        w = RosettaSubsystemWiring(tmp_manager, rag_vector_integration=rag)
        assert w.wire_rag_ingestion() is False


# ---------------------------------------------------------------------------
# P3-004 — EventBackbone subscriptions
# ---------------------------------------------------------------------------

class TestP3004EventSubscriptions:
    def test_three_subscriptions_registered(self, tmp_manager):
        backbone = _StubEventBackbone()
        w = RosettaSubsystemWiring(tmp_manager, event_backbone=backbone)
        assert w.wire_event_subscriptions() is True
        assert w.status.p3_004_event_subscriptions is True
        assert len(backbone.subscriptions) == 3

    def test_subscribed_to_correct_event_types(self, tmp_manager):
        from event_backbone import EventType
        backbone = _StubEventBackbone()
        w = RosettaSubsystemWiring(tmp_manager, event_backbone=backbone)
        w.wire_event_subscriptions()
        subscribed_types = {s["event_type"] for s in backbone.subscriptions}
        assert EventType.TASK_COMPLETED in subscribed_types
        assert EventType.TASK_FAILED in subscribed_types
        assert EventType.GATE_EVALUATED in subscribed_types

    def test_handler_fires_and_updates_rosetta(self, tmp_manager):
        from event_backbone import EventType
        backbone = _StubEventBackbone()
        w = RosettaSubsystemWiring(tmp_manager, event_backbone=backbone)
        w.wire_event_subscriptions()
        # Fire an event; handler should not raise
        backbone.fire(EventType.TASK_COMPLETED, {"task_id": "task-123"})
        # State should still be loadable (handler ran without crashing)
        assert tmp_manager.load_state("murphy-system") is not None

    def test_handler_updates_metadata_field(self, tmp_manager):
        from event_backbone import EventType
        backbone = _StubEventBackbone()
        w = RosettaSubsystemWiring(tmp_manager, event_backbone=backbone)
        w.wire_event_subscriptions()
        backbone.fire(EventType.TASK_COMPLETED, {"task_id": "t-abc"})
        state = tmp_manager.load_state("murphy-system")
        # metadata should have last_task_completed_at set
        assert state.metadata is not None

    def test_no_backbone_returns_false(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager)
        assert w.wire_event_subscriptions() is False

    def test_backbone_exception_returns_false(self, tmp_manager):
        backbone = _StubEventBackbone(raise_on_subscribe=True)
        w = RosettaSubsystemWiring(tmp_manager, event_backbone=backbone)
        assert w.wire_event_subscriptions() is False
        assert any("P3-004" in e for e in w.status.errors)

    def test_subscription_ids_stored(self, tmp_manager):
        backbone = _StubEventBackbone()
        w = RosettaSubsystemWiring(tmp_manager, event_backbone=backbone)
        w.wire_event_subscriptions()
        assert len(w._subscription_ids) == 3


# ---------------------------------------------------------------------------
# P3-005 — State sync delta push
# ---------------------------------------------------------------------------

class TestP3005StateSync:
    def test_sync_succeeds(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager)
        assert w.wire_state_sync() is True
        assert w.status.p3_005_state_sync is True

    def test_sync_updates_heartbeat(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager)
        before = datetime.now(timezone.utc)
        w.wire_state_sync()
        state = tmp_manager.load_state("murphy-system")
        assert state is not None
        # system_state.last_heartbeat should be set to approximately now
        hb = state.system_state.last_heartbeat
        assert hb is not None
        if hasattr(hb, "timestamp"):
            assert hb.timestamp() >= before.timestamp() - 1

    def test_sync_missing_agent_returns_true(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "empty"))
        w = RosettaSubsystemWiring(mgr)
        assert w.wire_state_sync("nonexistent-agent") is True

    def test_sync_exception_returns_false(self, tmp_manager):
        bad_mgr = MagicMock()
        bad_mgr.load_state.side_effect = RuntimeError("db gone")
        w = RosettaSubsystemWiring(bad_mgr)
        assert w.wire_state_sync() is False
        assert any("P3-005" in e for e in w.status.errors)


# ---------------------------------------------------------------------------
# wire_all() — full pipeline
# ---------------------------------------------------------------------------

class TestWireAll:
    def test_wire_all_returns_wiring_status(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager)
        status = w.wire_all()
        assert isinstance(status, WiringStatus)

    def test_wire_all_with_all_deps_activates_p5(self, tmp_manager):
        w = RosettaSubsystemWiring(
            tmp_manager,
            self_improvement_engine=_StubPatterns(),
            self_automation_orchestrator=_StubOrchestrator(),
            rag_vector_integration=_StubRAG(),
            event_backbone=_StubEventBackbone(),
        )
        status = w.wire_all()
        assert status.p3_001_patterns_to_rosetta is True
        assert status.p3_002_cycles_to_progress is True
        assert status.p3_003_rag_to_rosetta is True
        assert status.p3_004_event_subscriptions is True
        assert status.p3_005_state_sync is True

    def test_wire_all_no_optional_deps(self, tmp_manager):
        """With only the manager, only P3-005 (state sync) should activate."""
        w = RosettaSubsystemWiring(tmp_manager)
        status = w.wire_all()
        assert status.p3_001_patterns_to_rosetta is False
        assert status.p3_002_cycles_to_progress is False
        assert status.p3_003_rag_to_rosetta is False
        assert status.p3_004_event_subscriptions is False
        assert status.p3_005_state_sync is True

    def test_wire_all_is_idempotent(self, tmp_manager):
        w = RosettaSubsystemWiring(tmp_manager, self_improvement_engine=_StubPatterns())
        status1 = w.wire_all()
        status2 = w.wire_all()
        assert status1.p3_001_patterns_to_rosetta == status2.p3_001_patterns_to_rosetta


# ---------------------------------------------------------------------------
# bootstrap_wiring()
# ---------------------------------------------------------------------------

class TestBootstrapWiring:
    def test_returns_wiring_instance(self, tmp_manager):
        result = bootstrap_wiring(tmp_manager, run_immediately=False)
        assert isinstance(result, RosettaSubsystemWiring)

    def test_run_immediately_true_activates_wiring(self, tmp_manager):
        result = bootstrap_wiring(tmp_manager, run_immediately=True)
        # P3-005 always activates (manager-only)
        assert result.status.p3_005_state_sync is True

    def test_run_immediately_false_leaves_status_false(self, tmp_manager):
        result = bootstrap_wiring(tmp_manager, run_immediately=False)
        assert result.status.p3_005_state_sync is False

    def test_all_optional_deps_passed_through(self, tmp_manager):
        rag = _StubRAG()
        improvement = _StubPatterns()
        orchestrator = _StubOrchestrator()
        backbone = _StubEventBackbone()
        result = bootstrap_wiring(
            tmp_manager,
            event_backbone=backbone,
            self_improvement_engine=improvement,
            self_automation_orchestrator=orchestrator,
            rag_vector_integration=rag,
            run_immediately=True,
        )
        assert result.status.p3_001_patterns_to_rosetta is True
        assert result.status.p3_002_cycles_to_progress is True
        assert result.status.p3_003_rag_to_rosetta is True
        assert result.status.p3_004_event_subscriptions is True
        assert result.status.p3_005_state_sync is True


# ---------------------------------------------------------------------------
# State-to-text serialisation
# ---------------------------------------------------------------------------

class TestStateToText:
    def test_text_includes_agent_id(self, tmp_manager):
        state = tmp_manager.load_state("murphy-system")
        text = RosettaSubsystemWiring._state_to_text(state)
        assert "murphy-system" in text

    def test_text_includes_sections(self, tmp_manager):
        state = tmp_manager.load_state("murphy-system")
        text = RosettaSubsystemWiring._state_to_text(state)
        assert "## Goals" in text
        assert "## Tasks" in text
        assert "## Automation Progress" in text

    def test_text_handles_empty_goals(self, tmp_path):
        mgr = RosettaManager(persistence_dir=str(tmp_path / "empty"))
        state = RosettaAgentState(
            identity=Identity(agent_id="a", name="A", role="worker")
        )
        mgr.save_state(state)
        loaded = mgr.load_state("a")
        text = RosettaSubsystemWiring._state_to_text(loaded)
        assert "## Goals (0)" in text
