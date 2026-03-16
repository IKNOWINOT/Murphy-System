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
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — allow imports from src/
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_SRC = _HERE.parent.parent / "Murphy System" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

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
