"""
Tests for ARCH-006: ChaosResilienceLoop.

Validates hypothesis definition, experiment execution, scoring logic,
scorecard aggregation, gap feeding to SelfFixLoop, built-in hypothesis
library coverage, and thread safety.

Design Label: TEST-ARCH-006
Owner: QA Team
"""

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


from thread_safe_operations import capped_append

from chaos_resilience_loop import (
    ChaosResilienceLoop,
    ResilienceHypothesis,
    ResilienceExperiment,
    ResilienceScorecard,
    _compute_experiment_score,
    _BUILTIN_HYPOTHESES,
)
from event_backbone import EventBackbone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def minimal_loop():
    """Loop with no external dependencies."""
    return ChaosResilienceLoop()


@pytest.fixture
def loop_with_backbone(backbone):
    return ChaosResilienceLoop(event_backbone=backbone)


def _make_hypothesis(
    hid: str = "hyp-test-001",
    failure_type: str = "skipped_gate",
    target: str = "confidence_engine",
    max_time: float = 30.0,
    max_drop: float = 0.2,
) -> ResilienceHypothesis:
    return ResilienceHypothesis(
        hypothesis_id=hid,
        description="Test hypothesis",
        target_component=target,
        failure_type=failure_type,
        expected_behavior="Gate should fire and recovery should complete",
        max_acceptable_recovery_time_sec=max_time,
        max_acceptable_confidence_drop=max_drop,
    )


def _make_experiment(
    hypothesis_id: str = "hyp-test-001",
    score: float = 0.8,
    recovery: bool = True,
    regression: bool = False,
) -> ResilienceExperiment:
    return ResilienceExperiment(
        experiment_id=f"exp-{hypothesis_id}",
        hypothesis_id=hypothesis_id,
        injected_failure=None,
        recovery_observed=recovery,
        recovery_time_sec=5.0,
        confidence_drop=0.05,
        gates_that_fired=["gate-confidence-check"],
        gates_that_missed=[],
        regression_detected=regression,
        score=score,
    )


# ---------------------------------------------------------------------------
# Hypothesis definition and validation tests
# ---------------------------------------------------------------------------

class TestHypothesisDefinition:
    def test_define_hypothesis_returns_object(self, minimal_loop):
        h = minimal_loop.define_hypothesis(
            hypothesis_id="hyp-001",
            description="Test",
            target_component="confidence_engine",
            failure_type="skipped_gate",
            expected_behavior="Gate catches skip",
        )
        assert isinstance(h, ResilienceHypothesis)
        assert h.hypothesis_id == "hyp-001"
        assert h.target_component == "confidence_engine"
        assert h.failure_type == "skipped_gate"

    def test_define_hypothesis_registered_internally(self, minimal_loop):
        minimal_loop.define_hypothesis(
            hypothesis_id="hyp-reg",
            description="Registration test",
            target_component="recovery_coordinator",
            failure_type="missing_rollback",
            expected_behavior="Recovery registered",
        )
        assert "hyp-reg" in minimal_loop._hypotheses

    def test_define_hypothesis_custom_thresholds(self, minimal_loop):
        h = minimal_loop.define_hypothesis(
            hypothesis_id="hyp-thresholds",
            description="Custom thresholds",
            target_component="threshold_tuning",
            failure_type="delayed_verification",
            expected_behavior="Tuning within 90s",
            max_acceptable_recovery_time_sec=90.0,
            max_acceptable_confidence_drop=0.4,
        )
        assert h.max_acceptable_recovery_time_sec == 90.0
        assert h.max_acceptable_confidence_drop == 0.4

    def test_hypothesis_dataclass_defaults(self):
        h = ResilienceHypothesis(
            hypothesis_id="h1",
            description="d",
            target_component="c",
            failure_type="skipped_gate",
            expected_behavior="e",
        )
        assert h.max_acceptable_recovery_time_sec == 60.0
        assert h.max_acceptable_confidence_drop == 0.3


# ---------------------------------------------------------------------------
# Scoring logic tests
# ---------------------------------------------------------------------------

class TestScoringLogic:
    def _hyp(self, max_time: float = 30.0, max_drop: float = 0.2) -> ResilienceHypothesis:
        return _make_hypothesis(max_time=max_time, max_drop=max_drop)

    def test_perfect_recovery_scores_one(self):
        score = _compute_experiment_score(
            hypothesis=self._hyp(),
            recovery_observed=True,
            recovery_time_sec=5.0,
            confidence_drop=0.05,
            gates_that_fired=["gate-a"],
            gates_that_missed=[],
            regression_detected=False,
        )
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_total_failure_scores_zero(self):
        score = _compute_experiment_score(
            hypothesis=self._hyp(),
            recovery_observed=False,
            recovery_time_sec=999.0,
            confidence_drop=0.9,
            gates_that_fired=[],
            gates_that_missed=["gate-a", "gate-b"],
            regression_detected=True,
        )
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_partial_recovery_time_exceeded(self):
        score = _compute_experiment_score(
            hypothesis=self._hyp(max_time=10.0),
            recovery_observed=True,
            recovery_time_sec=20.0,   # 2× the limit
            confidence_drop=0.05,
            gates_that_fired=["gate-a"],
            gates_that_missed=[],
            regression_detected=False,
        )
        assert 0.0 < score < 1.0

    def test_partial_confidence_drop_exceeded(self):
        score = _compute_experiment_score(
            hypothesis=self._hyp(max_drop=0.1),
            recovery_observed=True,
            recovery_time_sec=5.0,
            confidence_drop=0.5,      # 5× the limit
            gates_that_fired=["gate-a"],
            gates_that_missed=[],
            regression_detected=False,
        )
        assert 0.0 < score < 1.0

    def test_regression_penalty(self):
        score_no_regression = _compute_experiment_score(
            hypothesis=self._hyp(),
            recovery_observed=True,
            recovery_time_sec=5.0,
            confidence_drop=0.05,
            gates_that_fired=["gate-a"],
            gates_that_missed=[],
            regression_detected=False,
        )
        score_with_regression = _compute_experiment_score(
            hypothesis=self._hyp(),
            recovery_observed=True,
            recovery_time_sec=5.0,
            confidence_drop=0.05,
            gates_that_fired=["gate-a"],
            gates_that_missed=[],
            regression_detected=True,
        )
        assert score_no_regression > score_with_regression

    def test_missed_gate_reduces_score(self):
        score_no_miss = _compute_experiment_score(
            hypothesis=self._hyp(),
            recovery_observed=True,
            recovery_time_sec=5.0,
            confidence_drop=0.05,
            gates_that_fired=["gate-a", "gate-b"],
            gates_that_missed=[],
            regression_detected=False,
        )
        score_with_miss = _compute_experiment_score(
            hypothesis=self._hyp(),
            recovery_observed=True,
            recovery_time_sec=5.0,
            confidence_drop=0.05,
            gates_that_fired=["gate-a"],
            gates_that_missed=["gate-b"],
            regression_detected=False,
        )
        assert score_no_miss > score_with_miss

    def test_score_bounded_zero_to_one(self):
        for recovery in [True, False]:
            score = _compute_experiment_score(
                hypothesis=self._hyp(),
                recovery_observed=recovery,
                recovery_time_sec=1000.0,
                confidence_drop=1.0,
                gates_that_fired=[],
                gates_that_missed=["a", "b", "c"],
                regression_detected=True,
            )
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Experiment execution tests
# ---------------------------------------------------------------------------

class TestExperimentExecution:
    def test_run_experiment_returns_experiment(self, minimal_loop):
        h = _make_hypothesis()
        exp = minimal_loop.run_experiment(h)
        assert isinstance(exp, ResilienceExperiment)
        assert exp.hypothesis_id == h.hypothesis_id
        assert 0.0 <= exp.score <= 1.0

    def test_run_experiment_stores_result(self, minimal_loop):
        h = _make_hypothesis()
        exp = minimal_loop.run_experiment(h)
        stored = minimal_loop.get_experiments()
        assert any(e["experiment_id"] == exp.experiment_id for e in stored)

    def test_run_experiment_publishes_events(self, loop_with_backbone):
        events_seen = []
        from event_backbone import EventType

        def capture(evt):
            events_seen.append(evt.event_type)

        loop_with_backbone._backbone.subscribe(EventType.CHAOS_EXPERIMENT_STARTED, capture)
        loop_with_backbone._backbone.subscribe(EventType.CHAOS_EXPERIMENT_COMPLETED, capture)

        h = _make_hypothesis()
        loop_with_backbone.run_experiment(h)
        loop_with_backbone._backbone.process_pending()

        assert EventType.CHAOS_EXPERIMENT_STARTED in events_seen
        assert EventType.CHAOS_EXPERIMENT_COMPLETED in events_seen

    def test_run_experiment_with_mock_failure_generator(self, minimal_loop):
        """Experiment executes cleanly with a mock pipeline."""
        mock_pipeline = MagicMock()
        mock_base = MagicMock()
        mock_operator = MagicMock()
        mock_failure = MagicMock()
        mock_failure.missed_gates = []
        mock_failure.to_dict.return_value = {}

        mock_sim = MagicMock()
        mock_sim.execution_halted = True
        mock_sim.final_confidence = 0.75
        mock_sim.final_risk = 0.2
        mock_sim.gates_triggered = ["gate-confidence-check"]
        mock_sim.gates_missed = []
        mock_telemetry = MagicMock()
        mock_telemetry.detection_latency = 5.0
        mock_sim.telemetry_outcome = mock_telemetry

        mock_pipeline.create_base_scenario.return_value = mock_base
        mock_pipeline.create_perturbation_operator.return_value = mock_operator
        mock_pipeline.apply_perturbation.return_value = mock_failure
        mock_pipeline.run_pipeline.return_value = mock_sim

        loop = ChaosResilienceLoop(failure_generator=mock_pipeline)
        h = _make_hypothesis(failure_type="skipped_gate")
        exp = loop.run_experiment(h)

        assert exp.recovery_observed is True
        assert exp.confidence_drop == pytest.approx(0.05, abs=0.01)
        assert "gate-confidence-check" in exp.gates_that_fired
        assert exp.score > 0.0

    def test_run_experiment_no_generator_does_not_crash(self, minimal_loop):
        """Even with no external failure generator, run_experiment returns a valid result."""
        h = _make_hypothesis()
        exp = minimal_loop.run_experiment(h)
        assert isinstance(exp, ResilienceExperiment)
        assert 0.0 <= exp.score <= 1.0


# ---------------------------------------------------------------------------
# run_suite tests
# ---------------------------------------------------------------------------

class TestRunSuite:
    def test_run_suite_all_hypotheses(self, minimal_loop):
        hypotheses = [_make_hypothesis(hid=f"hyp-{i}") for i in range(5)]
        results = minimal_loop.run_suite(hypotheses)
        assert len(results) == 5

    def test_run_suite_bounded_by_max_experiments(self, minimal_loop):
        hypotheses = [_make_hypothesis(hid=f"hyp-{i}") for i in range(10)]
        results = minimal_loop.run_suite(hypotheses, max_experiments=3)
        assert len(results) == 3

    def test_run_suite_returns_experiment_list(self, minimal_loop):
        hypotheses = [_make_hypothesis(hid="hyp-suite")]
        results = minimal_loop.run_suite(hypotheses)
        assert all(isinstance(r, ResilienceExperiment) for r in results)


# ---------------------------------------------------------------------------
# Scorecard aggregation tests
# ---------------------------------------------------------------------------

class TestScorecard:
    def test_generate_scorecard_empty_returns_zero(self, minimal_loop):
        sc = minimal_loop.generate_scorecard()
        assert isinstance(sc, ResilienceScorecard)
        assert sc.overall_score == 0.0
        assert sc.experiments_run == 0

    def test_generate_scorecard_aggregates_scores(self):
        loop = ChaosResilienceLoop()
        h1 = loop.define_hypothesis(
            "h1", "desc", "confidence_engine", "skipped_gate", "expected", 30.0, 0.2
        )
        h2 = loop.define_hypothesis(
            "h2", "desc", "recovery_coordinator", "missing_rollback", "expected", 30.0, 0.2
        )
        # Manually inject experiments
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=1.0))
            loop._experiments.append(_make_experiment("h2", score=0.0))

        sc = loop.generate_scorecard()
        assert sc.experiments_run == 2
        assert 0.0 <= sc.overall_score <= 1.0

    def test_generate_scorecard_identifies_weak_components(self):
        loop = ChaosResilienceLoop()
        loop.define_hypothesis(
            "h1", "d", "weak_component", "skipped_gate", "e", 30.0, 0.2
        )
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=0.3))

        sc = loop.generate_scorecard()
        assert "weak_component" in sc.weakest_components

    def test_generate_scorecard_passes_for_high_score(self):
        loop = ChaosResilienceLoop()
        loop.define_hypothesis(
            "h1", "d", "strong_component", "skipped_gate", "e", 30.0, 0.2
        )
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=0.9))

        sc = loop.generate_scorecard()
        assert "strong_component" not in sc.weakest_components

    def test_scorecard_passed_count(self):
        loop = ChaosResilienceLoop()
        loop.define_hypothesis("h1", "d", "c", "false_confidence", "e")
        loop.define_hypothesis("h2", "d", "c", "skipped_gate", "e")
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=0.8))
            loop._experiments.append(_make_experiment("h2", score=0.4))

        sc = loop.generate_scorecard()
        assert sc.experiments_passed == 1
        assert sc.experiments_run == 2

    def test_scorecard_publishes_event(self, loop_with_backbone):
        events_seen = []
        from event_backbone import EventType
        loop_with_backbone._backbone.subscribe(
            EventType.CHAOS_SCORECARD_GENERATED,
            lambda evt: events_seen.append(evt),
        )
        loop_with_backbone.generate_scorecard()
        loop_with_backbone._backbone.process_pending()
        assert len(events_seen) == 1

    def test_scorecard_stored_in_loop(self, minimal_loop):
        minimal_loop.generate_scorecard()
        scorecards = minimal_loop.get_scorecards()
        assert len(scorecards) >= 1


# ---------------------------------------------------------------------------
# Gap feeding to SelfFixLoop
# ---------------------------------------------------------------------------

class TestFeedGapsToSelfFix:
    def test_feed_gaps_no_self_fix_loop_returns_empty(self, minimal_loop):
        result = minimal_loop.feed_gaps_to_self_fix()
        assert result == []

    def test_feed_gaps_no_weak_components_returns_empty(self):
        mock_fix = MagicMock()
        loop = ChaosResilienceLoop(self_fix_loop=mock_fix)
        loop.define_hypothesis("h1", "d", "strong_c", "skipped_gate", "e")
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=0.9))
        result = loop.feed_gaps_to_self_fix()
        assert result == []

    def test_feed_gaps_calls_self_fix_plan_and_execute(self):
        mock_fix = MagicMock()
        mock_plan = MagicMock()
        mock_fix.plan.return_value = mock_plan

        loop = ChaosResilienceLoop(self_fix_loop=mock_fix)
        loop.define_hypothesis("h1", "d", "weak_c", "skipped_gate", "e")
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=0.3))

        result = loop.feed_gaps_to_self_fix()

        assert len(result) > 0
        mock_fix.plan.assert_called()
        mock_fix.execute.assert_called()

    def test_feed_gaps_publishes_event(self, backbone):
        events_seen = []
        from event_backbone import EventType
        backbone.subscribe(
            EventType.CHAOS_GAPS_SUBMITTED,
            lambda evt: events_seen.append(evt),
        )

        mock_fix = MagicMock()
        mock_fix.plan.return_value = MagicMock()

        loop = ChaosResilienceLoop(self_fix_loop=mock_fix, event_backbone=backbone)
        loop.define_hypothesis("h1", "d", "comp", "skipped_gate", "e")
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=0.3))

        loop.feed_gaps_to_self_fix()
        backbone.process_pending()

        assert len(events_seen) == 1

    def test_feed_gaps_with_real_self_fix_loop(self):
        """Integration: feed gaps into an actual SelfFixLoop instance."""
        from self_fix_loop import SelfFixLoop, Gap

        fix_loop = SelfFixLoop()
        loop = ChaosResilienceLoop(self_fix_loop=fix_loop)
        loop.define_hypothesis("h1", "d", "threshold_tuning", "delayed_verification", "e")
        with loop._lock:
            loop._experiments.append(_make_experiment("h1", score=0.2))

        result = loop.feed_gaps_to_self_fix()
        # May return gap_ids or empty list depending on plan/execute outcome
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Built-in hypothesis library tests
# ---------------------------------------------------------------------------

class TestBuiltinHypothesisLibrary:
    def test_builtin_hypotheses_returns_list(self):
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        assert isinstance(hyps, list)
        assert len(hyps) == 4

    def test_builtin_hypotheses_are_resilience_hypothesis_instances(self):
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        assert all(isinstance(h, ResilienceHypothesis) for h in hyps)

    def test_builtin_hypothesis_ids_unique(self):
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        ids = [h.hypothesis_id for h in hyps]
        assert len(ids) == len(set(ids))

    def test_builtin_timeout_cluster_hypothesis(self):
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        timeout_hyp = next((h for h in hyps if h.hypothesis_id == "hyp-builtin-001"), None)
        assert timeout_hyp is not None
        assert timeout_hyp.failure_type == "delayed_verification"
        assert timeout_hyp.max_acceptable_recovery_time_sec == 60.0
        assert timeout_hyp.target_component == "threshold_tuning"

    def test_builtin_skipped_gate_hypothesis(self):
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        hyp = next((h for h in hyps if h.hypothesis_id == "hyp-builtin-002"), None)
        assert hyp is not None
        assert hyp.failure_type == "skipped_gate"
        assert hyp.target_component == "confidence_engine"

    def test_builtin_false_confidence_hypothesis(self):
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        hyp = next((h for h in hyps if h.hypothesis_id == "hyp-builtin-003"), None)
        assert hyp is not None
        assert hyp.failure_type == "false_confidence"

    def test_builtin_missing_rollback_hypothesis(self):
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        hyp = next((h for h in hyps if h.hypothesis_id == "hyp-builtin-004"), None)
        assert hyp is not None
        assert hyp.failure_type == "missing_rollback"
        assert hyp.target_component == "recovery_coordinator"

    def test_builtin_library_run_suite(self, minimal_loop):
        """Built-in library can be fed directly into run_suite."""
        hyps = ChaosResilienceLoop.builtin_hypotheses()
        results = minimal_loop.run_suite(hyps)
        assert len(results) == 4


# ---------------------------------------------------------------------------
# Thread safety and bounded execution tests
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_run_experiment_no_data_race(self):
        """Multiple threads run experiments concurrently without data corruption."""
        loop = ChaosResilienceLoop()
        errors = []

        def run_exp(hid):
            try:
                h = _make_hypothesis(hid=hid)
                loop.run_experiment(h)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run_exp, args=(f"hyp-{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"
        assert len(loop.get_experiments()) == 10

    def test_concurrent_scorecard_generation_is_safe(self):
        """Scorecard generation under concurrent experiment writes is safe."""
        loop = ChaosResilienceLoop()
        loop.define_hypothesis("h1", "d", "c", "skipped_gate", "e")

        errors = []
        scorecards = []

        def generate():
            try:
                sc = loop.generate_scorecard()
                scorecards.append(sc)
            except Exception as exc:
                errors.append(exc)

        def add_exp():
            try:
                with loop._lock:
                    capped_append(
                        loop._experiments,
                        _make_experiment("h1", score=0.8),
                    )
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=generate) for _ in range(5)]
            + [threading.Thread(target=add_exp) for _ in range(5)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"

    def test_run_suite_bounded_prevents_overflow(self):
        """run_suite never exceeds max_experiments even with large input."""
        loop = ChaosResilienceLoop()
        hypotheses = [_make_hypothesis(hid=f"h-{i}") for i in range(100)]
        results = loop.run_suite(hypotheses, max_experiments=5)
        assert len(results) <= 5


# ---------------------------------------------------------------------------
# Serialisation and data integrity tests
# ---------------------------------------------------------------------------

class TestSerialisation:
    def test_experiment_to_dict(self):
        exp = _make_experiment()
        d = exp.to_dict()
        assert "experiment_id" in d
        assert "score" in d
        assert "recovery_observed" in d
        assert "gates_that_fired" in d

    def test_scorecard_to_dict(self):
        sc = ResilienceScorecard(
            overall_score=0.75,
            component_scores={"confidence_engine": 0.75},
            weakest_components=[],
            recommendations=["All good"],
            experiments_run=4,
            experiments_passed=3,
        )
        d = sc.to_dict()
        assert d["overall_score"] == pytest.approx(0.75)
        assert "component_scores" in d
        assert "recommendations" in d

    def test_experiment_with_failure_case_serialises(self):
        mock_failure = MagicMock()
        mock_failure.to_dict.return_value = {"failure_id": "f1"}
        exp = ResilienceExperiment(
            experiment_id="e1",
            hypothesis_id="h1",
            injected_failure=mock_failure,
            recovery_observed=True,
            recovery_time_sec=5.0,
            confidence_drop=0.05,
            gates_that_fired=["g1"],
            gates_that_missed=[],
            regression_detected=False,
            score=1.0,
        )
        d = exp.to_dict()
        assert d["injected_failure"] == {"failure_id": "f1"}


# ---------------------------------------------------------------------------
# Event backbone integration tests
# ---------------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_chaos_event_types_exist_in_backbone(self):
        from event_backbone import EventType
        assert hasattr(EventType, "CHAOS_EXPERIMENT_STARTED")
        assert hasattr(EventType, "CHAOS_EXPERIMENT_COMPLETED")
        assert hasattr(EventType, "CHAOS_SCORECARD_GENERATED")
        assert hasattr(EventType, "CHAOS_GAPS_SUBMITTED")

    def test_events_published_during_full_suite(self, backbone):
        from event_backbone import EventType

        events_seen = []
        for et in [
            EventType.CHAOS_EXPERIMENT_STARTED,
            EventType.CHAOS_EXPERIMENT_COMPLETED,
            EventType.CHAOS_SCORECARD_GENERATED,
        ]:
            backbone.subscribe(et, lambda evt: events_seen.append(evt.event_type))

        loop = ChaosResilienceLoop(event_backbone=backbone)
        h = _make_hypothesis()
        loop.run_suite([h])
        loop.generate_scorecard()
        backbone.process_pending()

        assert EventType.CHAOS_EXPERIMENT_STARTED in events_seen
        assert EventType.CHAOS_EXPERIMENT_COMPLETED in events_seen
        assert EventType.CHAOS_SCORECARD_GENERATED in events_seen
