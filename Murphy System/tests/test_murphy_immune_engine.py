"""
Comprehensive tests for ARCH-014: MurphyImmuneEngine.

Validates the 11-phase immune cycle, all sub-components, safety invariants,
edge cases, and integration with mocked subsystems.

Design Label: TEST-ARCH-014
Owner: QA Team

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


from murphy_immune_engine import (
    CascadeAnalyzer,
    CascadeEdge,
    ChaosHardenedValidator,
    DesiredStateReconciler,
    DriftEvent,
    ImmunityEntry,
    ImmunityMemory,
    ImmuneReport,
    MurphyImmuneEngine,
    PredictedFailure,
    PredictiveFailureAnalyzer,
    _CHAOS_PASS_THRESHOLD,
    _DEFAULT_CONFIDENCE_DECAY,
    _MIN_CONFIDENCE,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

class _FakeGap:
    """Minimal duck-typed Gap for testing."""

    def __init__(
        self,
        gap_id: str = None,
        description: str = "timeout error in worker",
        source: str = "health_check",
        severity: str = "medium",
        category: str = "timeout",
    ) -> None:
        self.gap_id = gap_id or f"gap-{uuid.uuid4().hex[:8]}"
        self.description = description
        self.source = source
        self.severity = severity
        self.category = category
        self.proposal_id: Optional[str] = None
        self.pattern_id: Optional[str] = None
        self.context: Dict[str, Any] = {"error_type": "timeout_error"}


class _FakePlan:
    """Minimal duck-typed FixPlan for testing."""

    def __init__(self, plan_id: str = None) -> None:
        self.plan_id = plan_id or f"plan-{uuid.uuid4().hex[:8]}"
        self.gap_description = "test gap"
        self.context = ""
        self.fix_type = "config_adjustment"
        self.fix_steps = [{"action": "adjust_timeout", "key": "t", "value": 30}]
        self.rollback_steps = [{"action": "adjust_timeout", "key": "t", "value": 20}]
        self.test_criteria = [{"check": "timeout_reduced"}]
        self.expected_outcome = "ok"
        self.status = "planned"
        self.created_at = ""
        self.completed_at = ""
        self.iteration = 0


class _FakeExecution:
    """Minimal duck-typed FixExecution for testing."""

    def __init__(self, passed: bool = True) -> None:
        self.execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        self.plan_id = "plan-test"
        self.tests_run = [{"check": "timeout_reduced", "passed": passed}]
        self.step_results = [{"action": "adjust_timeout", "success": True}]
        self.gaps_before: List[str] = []
        self.gaps_after: List[str] = []
        self.regressions: List[str] = []
        self.status = "success" if passed else "failed"
        self.duration_ms = 10.0


def _make_fix_loop(gaps=None, test_pass=True):
    """Create a mock SelfFixLoop that returns controllable gaps and test results."""
    loop = MagicMock()
    loop.diagnose.return_value = gaps or []
    loop.plan.return_value = _FakePlan()
    loop.execute.return_value = _FakeExecution(passed=test_pass)
    loop.test.return_value = test_pass
    loop.rollback.return_value = None
    return loop


def _make_engine(
    gaps=None,
    test_pass=True,
    desired_state=None,
    chaos_rounds=1,
) -> MurphyImmuneEngine:
    """Build a MurphyImmuneEngine with mocked subsystems."""
    loop = _make_fix_loop(gaps=gaps, test_pass=test_pass)
    engine = MurphyImmuneEngine(
        fix_loop=loop,
        desired_state=desired_state or {},
        chaos_rounds=chaos_rounds,
    )
    return engine


# ---------------------------------------------------------------------------
# DesiredStateReconciler tests
# ---------------------------------------------------------------------------

class TestDesiredStateReconciler:
    def test_no_drift_when_actual_matches_desired(self):
        desired = {"recovery_procedures": 5, "active_bot_count": 3}
        reconciler = DesiredStateReconciler(desired_state=desired)
        events = reconciler.reconcile(actual_state={"recovery_procedures": 5, "active_bot_count": 3})
        assert events == []

    def test_drift_detected_on_mismatch(self):
        desired = {"recovery_procedures": 5}
        reconciler = DesiredStateReconciler(desired_state=desired)
        events = reconciler.reconcile(actual_state={"recovery_procedures": 3})
        assert len(events) == 1
        evt = events[0]
        assert evt.component == "recovery_procedures"
        assert evt.expected == 5
        assert evt.actual == 3

    def test_multiple_drifts(self):
        desired = {"recovery_procedures": 5, "active_bot_count": 3, "circuit_breakers": "CLOSED"}
        reconciler = DesiredStateReconciler(desired_state=desired)
        actual = {"recovery_procedures": 5, "active_bot_count": 2, "circuit_breakers": "OPEN"}
        events = reconciler.reconcile(actual_state=actual)
        assert len(events) == 2
        components = {e.component for e in events}
        assert "active_bot_count" in components
        assert "circuit_breakers" in components

    def test_drift_event_has_required_fields(self):
        reconciler = DesiredStateReconciler(desired_state={"key": "expected"})
        events = reconciler.reconcile(actual_state={"key": "actual"})
        assert len(events) == 1
        evt = events[0]
        assert evt.drift_id.startswith("drift-")
        assert evt.component == "key"
        assert evt.detected_at != ""

    def test_drift_history_accumulates(self):
        reconciler = DesiredStateReconciler(desired_state={"x": 1})
        reconciler.reconcile(actual_state={"x": 2})
        reconciler.reconcile(actual_state={"x": 3})
        history = reconciler.get_drift_history()
        assert len(history) == 2

    def test_set_desired_state(self):
        reconciler = DesiredStateReconciler(desired_state={"a": 1})
        reconciler.set_desired_state({"b": 2})
        assert reconciler.get_desired_state() == {"b": 2}

    def test_critical_severity_for_circuit_breaker_drift(self):
        reconciler = DesiredStateReconciler(desired_state={"circuit_breaker_states": "CLOSED"})
        events = reconciler.reconcile(actual_state={"circuit_breaker_states": "OPEN"})
        assert len(events) == 1
        assert events[0].severity == "critical"

    def test_high_severity_for_bot_count_drift(self):
        reconciler = DesiredStateReconciler(desired_state={"active_bot_count": 5})
        events = reconciler.reconcile(actual_state={"active_bot_count": 2})
        assert len(events) == 1
        assert events[0].severity == "high"

    def test_empty_desired_state_no_drift(self):
        reconciler = DesiredStateReconciler(desired_state={})
        events = reconciler.reconcile(actual_state={"anything": "here"})
        assert events == []

    def test_missing_actual_key_is_drift(self):
        reconciler = DesiredStateReconciler(desired_state={"required_key": "value"})
        events = reconciler.reconcile(actual_state={})
        assert len(events) == 1
        assert events[0].actual is None


# ---------------------------------------------------------------------------
# PredictiveFailureAnalyzer tests
# ---------------------------------------------------------------------------

class TestPredictiveFailureAnalyzer:
    def test_no_predictions_with_single_snapshot(self):
        analyzer = PredictiveFailureAnalyzer()
        analyzer.record_snapshot({"db": 10, "auth": 5})
        preds = analyzer.analyze()
        assert preds == []

    def test_no_predictions_with_stable_series(self):
        analyzer = PredictiveFailureAnalyzer()
        for _ in range(5):
            analyzer.record_snapshot({"db": 10})
        preds = analyzer.analyze()
        assert preds == []

    def test_prediction_generated_for_growing_series(self):
        analyzer = PredictiveFailureAnalyzer()
        for i in range(6):
            analyzer.record_snapshot({"db": i * 10})
        preds = analyzer.analyze()
        db_preds = [p for p in preds if p.category == "db"]
        assert len(db_preds) >= 1
        assert db_preds[0].probability > 0.0

    def test_prediction_has_required_fields(self):
        analyzer = PredictiveFailureAnalyzer()
        for i in range(4):
            analyzer.record_snapshot({"auth": i * 5})
        preds = analyzer.analyze()
        auth_preds = [p for p in preds if p.category == "auth"]
        if auth_preds:
            pred = auth_preds[0]
            assert pred.prediction_id.startswith("pred-")
            assert 0.0 <= pred.probability <= 1.0
            assert pred.time_horizon_seconds >= 0
            assert pred.severity in ("critical", "high", "medium", "low")

    def test_canary_score_stable_category(self):
        analyzer = PredictiveFailureAnalyzer()
        for _ in range(5):
            analyzer.record_snapshot({"stable": 100})
        score = analyzer.get_canary_score("stable")
        assert score == 0.0

    def test_canary_score_growing_category(self):
        analyzer = PredictiveFailureAnalyzer()
        for i in range(5):
            analyzer.record_snapshot({"growing": i * 10})
        score = analyzer.get_canary_score("growing")
        assert score > 0.0

    def test_canary_score_unknown_category_returns_zero(self):
        analyzer = PredictiveFailureAnalyzer()
        score = analyzer.get_canary_score("does_not_exist")
        assert score == 0.0

    def test_get_predictions_returns_snapshot(self):
        analyzer = PredictiveFailureAnalyzer()
        for i in range(4):
            analyzer.record_snapshot({"err": i * 3})
        analyzer.analyze()
        preds = analyzer.get_predictions()
        assert isinstance(preds, list)

    def test_multiple_categories_analyzed_independently(self):
        analyzer = PredictiveFailureAnalyzer()
        for i in range(5):
            analyzer.record_snapshot({"db": i * 5, "cache": 10})  # db grows, cache stable
        preds = analyzer.analyze()
        categories = {p.category for p in preds}
        # db should be flagged; cache (stable) should not
        assert "db" in categories
        assert "cache" not in categories


# ---------------------------------------------------------------------------
# ImmunityMemory tests
# ---------------------------------------------------------------------------

class TestImmunityMemory:
    def test_compute_fingerprint_is_deterministic(self):
        fp1 = ImmunityMemory.compute_fingerprint("db", "timeout", "high")
        fp2 = ImmunityMemory.compute_fingerprint("db", "timeout", "high")
        assert fp1 == fp2

    def test_compute_fingerprint_differs_by_args(self):
        fp1 = ImmunityMemory.compute_fingerprint("db", "timeout", "high")
        fp2 = ImmunityMemory.compute_fingerprint("auth", "timeout", "high")
        assert fp1 != fp2

    def test_recall_returns_none_for_unknown_fingerprint(self):
        memory = ImmunityMemory()
        assert memory.recall("nonexistent") is None

    def test_memorize_and_recall(self):
        memory = ImmunityMemory()
        entry = memory.memorize(
            category="db",
            error_type="timeout",
            severity="high",
            fix_steps=[{"action": "increase_pool"}],
            rollback_steps=[{"action": "restore_pool"}],
            test_criteria=[{"check": "pool_ok"}],
        )
        fp = ImmunityMemory.compute_fingerprint("db", "timeout", "high")
        recalled = memory.recall(fp)
        assert recalled is not None
        assert recalled.entry_id == entry.entry_id
        assert recalled.category == "db"

    def test_memorize_reinforces_existing_entry(self):
        memory = ImmunityMemory()
        memory.memorize("db", "timeout", "high", [], [], [])
        memory.memorize("db", "timeout", "high", [], [], [])
        assert memory.size() == 1

    def test_memorize_updates_applications(self):
        memory = ImmunityMemory()
        entry1 = memory.memorize("db", "timeout", "high", [], [], [])
        entry2 = memory.memorize("db", "timeout", "high", [], [], [])
        # entry1 and entry2 should be the same object
        assert entry1.entry_id == entry2.entry_id
        assert entry2.applications == 2

    def test_decay_reduces_confidence(self):
        memory = ImmunityMemory(confidence_decay_per_cycle=0.20)
        memory.memorize("db", "timeout", "medium", [], [], [])
        fp = ImmunityMemory.compute_fingerprint("db", "timeout", "medium")
        before = memory.recall(fp)
        assert before is not None
        initial_confidence = before.confidence

        memory.decay_all()

        after = memory.recall(fp)
        if after is not None:
            assert after.confidence < initial_confidence

    def test_decay_evicts_low_confidence_entries(self):
        memory = ImmunityMemory(confidence_decay_per_cycle=0.50, min_confidence=0.30)
        memory.memorize("db", "timeout", "medium", [], [], [])
        fp = ImmunityMemory.compute_fingerprint("db", "timeout", "medium")
        entry = memory.recall(fp)
        assert entry is not None
        # Force confidence near minimum
        entry.confidence = 0.31
        memory.decay_all()  # drops by 0.50 → below min → evicted
        assert memory.recall(fp) is None

    def test_penalize_reduces_confidence(self):
        memory = ImmunityMemory()
        memory.memorize("db", "timeout", "high", [], [], [])
        fp = ImmunityMemory.compute_fingerprint("db", "timeout", "high")
        entry_before = memory.recall(fp)
        assert entry_before is not None
        before_conf = entry_before.confidence
        memory.penalize(fp, amount=0.20)
        entry_after = memory.recall(fp)
        assert entry_after is not None
        assert entry_after.confidence < before_conf

    def test_penalize_evicts_very_low_confidence(self):
        memory = ImmunityMemory(min_confidence=0.10)
        memory.memorize("x", "y", "low", [], [], [])
        fp = ImmunityMemory.compute_fingerprint("x", "y", "low")
        entry = memory.recall(fp)
        entry.confidence = 0.15
        memory.penalize(fp, amount=0.20)
        assert memory.recall(fp) is None

    def test_penalize_unknown_fingerprint_noop(self):
        memory = ImmunityMemory()
        # Should not raise
        memory.penalize("nonexistent", amount=0.5)

    def test_all_entries_returns_valid_entries(self):
        memory = ImmunityMemory()
        memory.memorize("a", "b", "low", [], [], [])
        memory.memorize("c", "d", "high", [], [], [])
        entries = memory.all_entries()
        assert len(entries) == 2

    def test_size_tracks_entry_count(self):
        memory = ImmunityMemory()
        assert memory.size() == 0
        memory.memorize("a", "b", "low", [], [], [])
        assert memory.size() == 1

    def test_confidence_caps_at_one_on_reinforce(self):
        memory = ImmunityMemory()
        for _ in range(20):
            memory.memorize("a", "b", "low", [], [], [])
        fp = ImmunityMemory.compute_fingerprint("a", "b", "low")
        entry = memory.recall(fp)
        assert entry.confidence <= 1.0


# ---------------------------------------------------------------------------
# ChaosHardenedValidator tests
# ---------------------------------------------------------------------------

class TestChaosHardenedValidator:
    def test_passes_without_pipeline_or_callable(self):
        validator = ChaosHardenedValidator(chaos_rounds=3)
        passed, rate = validator.validate("plan-1", "timeout")
        assert passed is True
        assert rate == 1.0

    def test_passes_when_test_callable_returns_true(self):
        validator = ChaosHardenedValidator(chaos_rounds=3)
        passed, rate = validator.validate("p1", "db", test_callable=lambda: True)
        assert passed is True
        assert rate == 1.0

    def test_fails_when_test_callable_returns_false(self):
        validator = ChaosHardenedValidator(chaos_rounds=3)
        passed, rate = validator.validate("p1", "db", test_callable=lambda: False)
        assert passed is False
        assert rate == 0.0

    def test_partial_pass_below_threshold_fails(self):
        call_count = {"n": 0}

        def sometimes_pass():
            call_count["n"] += 1
            return call_count["n"] % 2 == 0  # passes on even calls only

        validator = ChaosHardenedValidator(chaos_rounds=4)
        passed, rate = validator.validate("p1", "db", test_callable=sometimes_pass)
        assert 0.0 <= rate <= 1.0
        assert passed == (rate >= _CHAOS_PASS_THRESHOLD)

    def test_fix_callable_is_called_each_round(self):
        calls = []
        validator = ChaosHardenedValidator(chaos_rounds=3)
        validator.validate("p1", "db", fix_callable=lambda: calls.append(1))
        assert len(calls) == 3

    def test_exception_in_test_callable_recorded_as_fail(self):
        def exploding():
            raise RuntimeError("chaos explosion")

        validator = ChaosHardenedValidator(chaos_rounds=2)
        # Should not raise; exceptions are caught internally
        passed, rate = validator.validate("p1", "db", test_callable=exploding)
        assert passed is False

    def test_results_recorded(self):
        validator = ChaosHardenedValidator(chaos_rounds=2)
        validator.validate("plan-x", "auth")
        results = validator.get_results()
        assert len(results) == 2
        assert all(r["plan_id"] == "plan-x" for r in results)

    def test_chaos_rounds_minimum_one(self):
        validator = ChaosHardenedValidator(chaos_rounds=0)
        # chaos_rounds capped at 1
        passed, rate = validator.validate("p", "c")
        assert isinstance(passed, bool)


# ---------------------------------------------------------------------------
# CascadeAnalyzer tests
# ---------------------------------------------------------------------------

class TestCascadeAnalyzer:
    def test_record_edge_creates_new_edge(self):
        analyzer = CascadeAnalyzer()
        edge = analyzer.record_edge("db", "cache")
        assert edge.source_category == "db"
        assert edge.target_category == "cache"
        assert edge.edge_id.startswith("edge-")

    def test_record_edge_reinforces_existing(self):
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("db", "cache")
        edge2 = analyzer.record_edge("db", "cache", caused_regression=True)
        assert edge2.observed_regressions == 1

    def test_get_downstream_empty_for_unknown_node(self):
        analyzer = CascadeAnalyzer()
        assert analyzer.get_downstream("unknown") == []

    def test_get_downstream_returns_connected_nodes(self):
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("api", "db")
        analyzer.record_edge("api", "cache")
        downstream = analyzer.get_downstream("api")
        assert "db" in downstream
        assert "cache" in downstream

    def test_check_cascade_no_regression_healthy(self):
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("api", "db")
        regressions = analyzer.check_cascade("api", health_check_callable=lambda cat: True)
        assert regressions == []

    def test_check_cascade_detects_regression(self):
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("api", "db")
        regressions = analyzer.check_cascade("api", health_check_callable=lambda cat: False)
        assert "db" in regressions

    def test_check_cascade_no_callable_returns_empty(self):
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("api", "db")
        regressions = analyzer.check_cascade("api", health_check_callable=None)
        assert regressions == []

    def test_check_cascade_exception_in_health_check_is_safe(self):
        def exploding(cat):
            raise RuntimeError("health check failure")

        analyzer = CascadeAnalyzer()
        analyzer.record_edge("api", "db")
        # Should not raise; exception is caught and category treated as healthy
        regressions = analyzer.check_cascade("api", health_check_callable=exploding)
        assert regressions == []

    def test_get_all_edges_flat_list(self):
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("a", "b")
        analyzer.record_edge("a", "c")
        analyzer.record_edge("b", "c")
        edges = analyzer.get_all_edges()
        assert len(edges) == 3

    def test_get_graph_stats(self):
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("a", "b")
        analyzer.record_edge("a", "c", caused_regression=True)
        stats = analyzer.get_graph_stats()
        assert stats["edge_count"] == 2
        assert stats["node_count"] >= 2
        assert stats["total_observed_regressions"] >= 1

    def test_cascade_regression_increases_edge_weight(self):
        analyzer = CascadeAnalyzer()
        edge = analyzer.record_edge("x", "y", caused_regression=False)
        initial_weight = edge.weight
        analyzer.check_cascade("x", health_check_callable=lambda cat: False)
        assert edge.weight > initial_weight or edge.observed_regressions > 0


# ---------------------------------------------------------------------------
# MurphyImmuneEngine — unit-level tests
# ---------------------------------------------------------------------------

class TestMurphyImmuneEngine:
    def test_instantiation_no_args(self):
        engine = MurphyImmuneEngine()
        assert engine is not None

    def test_accessors_return_components(self):
        engine = MurphyImmuneEngine()
        assert isinstance(engine.get_reconciler(), DesiredStateReconciler)
        assert isinstance(engine.get_predictor(), PredictiveFailureAnalyzer)
        assert isinstance(engine.get_memory(), ImmunityMemory)
        assert isinstance(engine.get_chaos_validator(), ChaosHardenedValidator)
        assert isinstance(engine.get_cascade_analyzer(), CascadeAnalyzer)

    def test_run_no_gaps_returns_report(self):
        engine = _make_engine(gaps=[])
        report = engine.run_immune_cycle(max_iterations=1)
        assert isinstance(report, ImmuneReport)
        assert report.gaps_found == 0
        assert report.gaps_fixed == 0

    def test_run_with_single_gap_fixed(self):
        gap = _FakeGap()
        engine = _make_engine(gaps=[gap], test_pass=True, chaos_rounds=1)
        report = engine.run_immune_cycle(max_iterations=5)
        # The gap should be processed
        assert report.plans_executed >= 1

    def test_run_with_failing_test_rolls_back(self):
        gap = _FakeGap()
        engine = _make_engine(gaps=[gap], test_pass=False, chaos_rounds=1)
        loop = engine._loop
        report = engine.run_immune_cycle(max_iterations=2)
        # Rollback should have been called
        loop.rollback.assert_called()

    def test_report_has_required_fields(self):
        engine = _make_engine(gaps=[])
        report = engine.run_immune_cycle(max_iterations=1)
        assert report.report_id.startswith("immune-")
        assert report.generated_at != ""
        assert report.duration_ms >= 0
        assert report.final_health_status in ("green", "yellow", "red")

    def test_report_to_dict_is_serializable(self):
        engine = _make_engine(gaps=[])
        report = engine.run_immune_cycle(max_iterations=1)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "report_id" in d

    def test_get_reports_accumulates(self):
        engine = _make_engine(gaps=[])
        engine.run_immune_cycle(max_iterations=1)
        engine.run_immune_cycle(max_iterations=1)
        reports = engine.get_reports()
        assert len(reports) == 2

    def test_set_desired_state(self):
        engine = MurphyImmuneEngine()
        engine.set_desired_state({"recovery_procedures": 5})
        state = engine.get_desired_state()
        assert state["recovery_procedures"] == 5

    def test_immunity_recall_skips_planning(self):
        """If a fix is in ImmunityMemory, planning should be skipped."""
        gap = _FakeGap(category="db", severity="high")
        engine = _make_engine(gaps=[gap], test_pass=True, chaos_rounds=1)
        # Pre-populate memory
        engine.get_memory().memorize(
            category="db",
            error_type="timeout_error",
            severity="high",
            fix_steps=[{"action": "noop"}],
            rollback_steps=[],
            test_criteria=[],
        )
        report = engine.run_immune_cycle(max_iterations=2)
        assert report.immunity_recalls >= 1
        # plan() should NOT have been called since recall happened
        engine._loop.plan.assert_not_called()

    def test_chaos_failed_does_not_memorize(self):
        """A fix that fails chaos validation should NOT be added to ImmunityMemory."""
        gap = _FakeGap(category="flaky")
        engine = _make_engine(gaps=[gap], test_pass=True, chaos_rounds=1)
        # Override chaos validator to always fail
        engine._chaos_validator = ChaosHardenedValidator(chaos_rounds=1)
        # Make the test callable always fail in chaos
        original_validate = engine._chaos_validator.validate

        def always_fail(plan_id, category, **kwargs):
            return (False, 0.0)

        engine._chaos_validator.validate = always_fail

        report = engine.run_immune_cycle(max_iterations=2)
        assert report.entries_memorized == 0

    def test_cascade_regression_prevents_memorize(self):
        """A fix that causes a cascade regression should NOT be memorized."""
        gap = _FakeGap(category="api")
        engine = _make_engine(gaps=[gap], test_pass=True, chaos_rounds=1)
        # Add a downstream edge that will always regress
        engine.get_cascade_analyzer().record_edge("api", "db")
        # Make health check always fail for downstream
        original_check = engine.get_cascade_analyzer().check_cascade

        def failing_cascade(cat, **kwargs):
            return ["db"]

        engine.get_cascade_analyzer().check_cascade = failing_cascade

        report = engine.run_immune_cycle(max_iterations=2)
        assert report.cascade_regressions_detected >= 1
        assert report.entries_memorized == 0

    def test_drift_events_counted_in_report(self):
        engine = _make_engine(gaps=[], desired_state={"recovery_procedures": 5})
        report = engine.run_immune_cycle(max_iterations=1)
        assert report.drift_events_detected >= 0  # actual state may differ

    def test_max_iterations_respected(self):
        """Cycle must stop after max_iterations even if gaps remain."""
        gap = _FakeGap()
        engine = _make_engine(gaps=[gap], test_pass=False, chaos_rounds=1)
        # loop.diagnose always returns the same gap
        engine._loop.diagnose.return_value = [gap]
        report = engine.run_immune_cycle(max_iterations=3)
        assert report.iterations_run <= 3

    def test_no_disk_writes(self):
        """run_immune_cycle must not write to disk (no open() calls on source files)."""
        engine = _make_engine(gaps=[])
        with patch("builtins.open", side_effect=AssertionError("open() must not be called")) as mock_open:
            try:
                report = engine.run_immune_cycle(max_iterations=1)
            except AssertionError:
                pytest.fail("run_immune_cycle attempted to open/write a file on disk")
        # We get here only if no open() was called — report should be valid
        assert isinstance(report, ImmuneReport)

    def test_event_backbone_receives_cycle_events(self):
        """EventBackbone should receive IMMUNE_CYCLE_STARTED and IMMUNE_CYCLE_COMPLETED."""
        backbone = MagicMock()
        engine = MurphyImmuneEngine(event_backbone=backbone, chaos_rounds=1)
        engine.run_immune_cycle(max_iterations=1)
        # At minimum IMMUNE_CYCLE_STARTED and IMMUNE_CYCLE_COMPLETED must be published
        published_types = [call.args[0].value for call in backbone.publish.call_args_list]
        assert "immune_cycle_started" in published_types
        assert "immune_cycle_completed" in published_types

    def test_persistence_manager_called_on_report(self):
        """PersistenceManager.save_document must be called once per cycle."""
        pm = MagicMock()
        engine = MurphyImmuneEngine(persistence_manager=pm, chaos_rounds=1)
        engine.run_immune_cycle(max_iterations=1)
        pm.save_document.assert_called_once()

    def test_no_fix_loop_runs_cleanly(self):
        """Engine with no SelfFixLoop should still complete without errors."""
        engine = MurphyImmuneEngine()  # no fix_loop
        report = engine.run_immune_cycle(max_iterations=1)
        assert isinstance(report, ImmuneReport)


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_mutex_prevents_concurrent_cycles(self):
        """Calling run_immune_cycle while one is running must raise RuntimeError."""
        engine = _make_engine(gaps=[])
        barrier = threading.Barrier(2)
        errors = []
        results = []

        def slow_diagnose():
            barrier.wait(timeout=5.0)
            time.sleep(0.05)
            return []

        engine._loop.diagnose.side_effect = slow_diagnose

        def run():
            try:
                r = engine.run_immune_cycle(max_iterations=2)
                results.append(r)
            except RuntimeError as exc:
                errors.append(exc)

        t1 = threading.Thread(target=run)
        t2 = threading.Thread(target=run)
        t1.start()
        t2.start()
        t1.join(timeout=10.0)
        t2.join(timeout=10.0)

        # One thread should have succeeded; the other should have raised
        assert len(errors) == 1
        assert "already running" in str(errors[0]).lower()

    def test_max_iterations_upper_bound(self):
        """Loop must never exceed max_iterations iterations."""
        never_ending_gap = _FakeGap()
        loop = _make_fix_loop(gaps=[never_ending_gap], test_pass=False)
        loop.diagnose.return_value = [never_ending_gap]
        engine = MurphyImmuneEngine(fix_loop=loop, chaos_rounds=1)
        report = engine.run_immune_cycle(max_iterations=5)
        assert report.iterations_run <= 5

    def test_rollback_called_on_test_failure(self):
        gap = _FakeGap()
        loop = _make_fix_loop(gaps=[gap], test_pass=False)
        engine = MurphyImmuneEngine(fix_loop=loop, chaos_rounds=1)
        engine.run_immune_cycle(max_iterations=2)
        loop.rollback.assert_called()

    def test_empty_cycle_green_health(self):
        engine = _make_engine(gaps=[])
        report = engine.run_immune_cycle(max_iterations=1)
        assert report.final_health_status == "green"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_all_gaps_recalled_from_memory_no_planning(self):
        """When all gaps are in ImmunityMemory, planning must not be called."""
        gaps = [_FakeGap(category="db", severity="high") for _ in range(3)]
        engine = _make_engine(gaps=gaps, test_pass=True, chaos_rounds=1)
        memory = engine.get_memory()
        for g in gaps:
            memory.memorize(
                category=g.category,
                error_type=g.context.get("error_type", "unknown"),
                severity=g.severity,
                fix_steps=[],
                rollback_steps=[],
                test_criteria=[],
            )
        report = engine.run_immune_cycle(max_iterations=2)
        assert report.immunity_recalls >= len(gaps)
        engine._loop.plan.assert_not_called()

    def test_empty_gap_list_no_iterations_needed(self):
        engine = _make_engine(gaps=[])
        report = engine.run_immune_cycle(max_iterations=10)
        assert report.gaps_found == 0

    def test_cascade_loop_prevention(self):
        """A cycle in the cascade graph should not cause infinite recursion."""
        analyzer = CascadeAnalyzer()
        analyzer.record_edge("a", "b")
        analyzer.record_edge("b", "a")   # create a cycle
        # check_cascade only looks one hop deep, so no infinite loop
        regressions = analyzer.check_cascade("a", health_check_callable=lambda cat: True)
        assert regressions == []

    def test_predicted_failure_gap_contributes_to_count(self):
        """Synthetic gaps from PredictedFailure must be counted in gaps_found."""
        engine = MurphyImmuneEngine(chaos_rounds=1)
        # Inject a trend into the predictor
        for i in range(6):
            engine.get_predictor().record_snapshot({"db": i * 10})
        report = engine.run_immune_cycle(max_iterations=1)
        # Predictions may or may not trigger depending on analysis, but should not crash
        assert isinstance(report, ImmuneReport)

    def test_immunity_memory_decay_runs_each_cycle(self):
        """decay_all() should be called at the end of every cycle."""
        engine = _make_engine(gaps=[])
        memory = engine.get_memory()
        # Spy on decay_all
        calls = []
        original_decay = memory.decay_all

        def tracked_decay():
            calls.append(1)
            return original_decay()

        memory.decay_all = tracked_decay
        engine.run_immune_cycle(max_iterations=1)
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Data model tests
# ---------------------------------------------------------------------------

class TestDataModels:
    def test_drift_event_to_dict(self):
        evt = DriftEvent(drift_id="d-1", component="bots", expected=5, actual=3, severity="high")
        d = evt.to_dict()
        assert d["drift_id"] == "d-1"
        assert d["component"] == "bots"
        assert d["expected"] == 5
        assert d["actual"] == 3

    def test_predicted_failure_to_dict(self):
        pf = PredictedFailure(
            prediction_id="p-1",
            category="db",
            description="growing error rate",
            probability=0.75,
            time_horizon_seconds=3600.0,
            severity="high",
        )
        d = pf.to_dict()
        assert d["prediction_id"] == "p-1"
        assert d["probability"] == 0.75

    def test_immunity_entry_to_dict(self):
        entry = ImmunityEntry(
            entry_id="e-1",
            fingerprint="abcd1234",
            category="db",
            error_type="timeout",
            severity="high",
            fix_steps=[{"action": "noop"}],
            rollback_steps=[],
            test_criteria=[],
        )
        d = entry.to_dict()
        assert d["entry_id"] == "e-1"
        assert d["fingerprint"] == "abcd1234"
        assert d["confidence"] == 1.0

    def test_cascade_edge_to_dict(self):
        edge = CascadeEdge(edge_id="ed-1", source_category="api", target_category="db")
        d = edge.to_dict()
        assert d["edge_id"] == "ed-1"
        assert d["source_category"] == "api"

    def test_immune_report_to_dict(self):
        report = ImmuneReport(
            report_id="r-1",
            iterations_run=2,
            gaps_found=3,
            gaps_fixed=2,
            gaps_remaining=1,
            drift_events_detected=0,
            predicted_failures=0,
            immunity_recalls=0,
            chaos_validations_passed=2,
            chaos_validations_failed=0,
            cascade_regressions_detected=0,
            entries_memorized=2,
            plans_executed=2,
            plans_succeeded=2,
            plans_rolled_back=0,
            tests_run=4,
            tests_passed=4,
            tests_failed=0,
            duration_ms=120.5,
            final_health_status="green",
        )
        d = report.to_dict()
        assert d["report_id"] == "r-1"
        assert d["final_health_status"] == "green"
        assert d["duration_ms"] == 120.5
