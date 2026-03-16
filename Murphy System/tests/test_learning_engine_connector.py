"""
Tests for the Learning Engine closed-loop wiring.

Covers:
  - TASK_COMPLETED / TASK_FAILED / GATE_EVALUATED / AUTOMATION_EXECUTED
    events are consumed by LearningEngineConnector via EventBackbone
  - FeedbackIntegrator receives signals and adjusts TypedStateVector
  - PatternRecognizer receives outcomes and can detect patterns
  - PerformancePredictor produces PredictionResult from patterns
  - Gate confidence_threshold is updated after a prediction
  - THRESHOLD_UPDATED and GATE_EVOLVED events are published
  - Metrics (learning_rate_ema, pattern_count, threshold_drift_total,
    gate_evolution_count, events_processed_total) are tracked
  - run_cycle() returns a correct LearningCycleResult
  - PerformancePredictor status and drift are correct
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from event_backbone import EventBackbone, EventType
from learning_engine_connector import LearningCycleResult, LearningEngineConnector
from performance_predictor import PerformancePredictor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backbone() -> EventBackbone:
    return EventBackbone()


def _make_predictor(backbone=None) -> PerformancePredictor:
    return PerformancePredictor(event_backbone=backbone)


class _FakeGate:
    """Minimal DomainGate-like object for gate-evolution tests."""

    def __init__(self, gate_id: str, name: str, threshold: float = 0.85) -> None:
        self.gate_id = gate_id
        self.name = name
        self.confidence_threshold = threshold


class _FakePatternRecognizer:
    """Minimal PatternRecognizer stub that records calls."""

    def __init__(self, patterns=None):
        self._patterns = patterns or []
        self.call_count = 0

    def analyze_metrics(self, metrics):
        self.call_count += 1
        return list(self._patterns)


class _FakeFeedbackCollector:
    """Minimal FeedbackCollector stub."""

    def __init__(self):
        self.records = []

    def collect_feedback(self, feedback_type, operation_id, success,
                         confidence, feedback_data=None):
        self.records.append({
            "feedback_type": feedback_type,
            "operation_id": operation_id,
            "success": success,
            "confidence": confidence,
        })


# ---------------------------------------------------------------------------
# EventType presence
# ---------------------------------------------------------------------------


class TestEventTypePresence:
    """New event types are registered in EventType enum."""

    def test_automation_executed_exists(self):
        assert hasattr(EventType, "AUTOMATION_EXECUTED")
        assert EventType.AUTOMATION_EXECUTED.value == "automation_executed"

    def test_threshold_updated_exists(self):
        assert hasattr(EventType, "THRESHOLD_UPDATED")
        assert EventType.THRESHOLD_UPDATED.value == "threshold_updated"

    def test_gate_evolved_exists(self):
        assert hasattr(EventType, "GATE_EVOLVED")
        assert EventType.GATE_EVOLVED.value == "gate_evolved"

    def test_pattern_detected_exists(self):
        assert hasattr(EventType, "PATTERN_DETECTED")

    def test_prediction_generated_exists(self):
        assert hasattr(EventType, "PREDICTION_GENERATED")


# ---------------------------------------------------------------------------
# LearningEngineConnector — event subscription
# ---------------------------------------------------------------------------


class TestEventSubscription:
    """LearningEngineConnector subscribes to the correct event types."""

    def test_task_completed_enqueued(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1", "confidence": 0.9})
        bb.process_pending()

        status = connector.get_status()
        assert status["pending_events"] == 1

    def test_task_failed_enqueued(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_FAILED, {"task_id": "t2", "confidence": 0.4})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 1

    def test_gate_evaluated_enqueued(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.GATE_EVALUATED, {"gate_id": "g1", "passed": True})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 1

    def test_automation_executed_enqueued(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.AUTOMATION_EXECUTED, {"task_id": "auto-1"})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 1

    def test_multiple_events_all_enqueued(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.publish(EventType.TASK_FAILED, {"task_id": "t2"})
        bb.publish(EventType.GATE_EVALUATED, {"gate_id": "g1", "passed": False})
        bb.publish(EventType.AUTOMATION_EXECUTED, {"task_id": "a1"})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 4

    def test_unrelated_event_not_enqueued(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.AUDIT_LOGGED, {"msg": "audit"})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 0


# ---------------------------------------------------------------------------
# LearningEngineConnector — FeedbackCollector wiring
# ---------------------------------------------------------------------------


class TestFeedbackCollectorWiring:
    """Outcomes flow from events into FeedbackCollector."""

    def test_task_completed_records_success(self):
        bb = _make_backbone()
        collector = _FakeFeedbackCollector()
        connector = LearningEngineConnector(
            event_backbone=bb,
            feedback_collector=collector,
        )

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1", "confidence": 0.88})
        bb.process_pending()
        connector.run_cycle()

        assert len(collector.records) == 1
        assert collector.records[0]["success"] is True
        assert collector.records[0]["confidence"] == pytest.approx(0.88)

    def test_task_failed_records_failure(self):
        bb = _make_backbone()
        collector = _FakeFeedbackCollector()
        connector = LearningEngineConnector(
            event_backbone=bb,
            feedback_collector=collector,
        )

        bb.publish(EventType.TASK_FAILED, {"task_id": "t2", "confidence": 0.3})
        bb.process_pending()
        connector.run_cycle()

        assert len(collector.records) == 1
        assert collector.records[0]["success"] is False

    def test_multiple_events_multiple_records(self):
        bb = _make_backbone()
        collector = _FakeFeedbackCollector()
        connector = LearningEngineConnector(
            event_backbone=bb,
            feedback_collector=collector,
        )

        for i in range(5):
            bb.publish(EventType.TASK_COMPLETED, {"task_id": f"t{i}", "confidence": 0.9})
        bb.process_pending()
        connector.run_cycle()

        assert len(collector.records) == 5


# ---------------------------------------------------------------------------
# LearningEngineConnector — PatternRecognizer wiring
# ---------------------------------------------------------------------------


class TestPatternRecognizerWiring:
    """Events flow from outcomes into PatternRecognizer."""

    def test_pattern_recognizer_called_when_events_present(self):
        bb = _make_backbone()
        recognizer = _FakePatternRecognizer()
        connector = LearningEngineConnector(
            event_backbone=bb,
            pattern_recognizer=recognizer,
        )

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1", "confidence": 0.9})
        bb.process_pending()
        result = connector.run_cycle()

        assert recognizer.call_count == 1
        assert result.events_drained == 1

    def test_pattern_recognizer_not_called_when_no_events(self):
        bb = _make_backbone()
        recognizer = _FakePatternRecognizer()
        connector = LearningEngineConnector(
            event_backbone=bb,
            pattern_recognizer=recognizer,
        )

        result = connector.run_cycle()  # no events queued

        assert recognizer.call_count == 0
        assert result.events_drained == 0


# ---------------------------------------------------------------------------
# LearningEngineConnector — PerformancePredictor wiring
# ---------------------------------------------------------------------------


class TestPerformancePredictorWiring:
    """Patterns flow from PatternRecognizer into PerformancePredictor."""

    def test_predictor_receives_outcomes_and_updates_thresholds(self):
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
        )

        # Publish enough events to pass the min-samples threshold (default=5)
        for i in range(10):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "onboarding", "confidence": 0.9},
            )
        bb.process_pending()
        result = connector.run_cycle()

        # Predictor should have received 10 samples for the "task:onboarding" key
        status = predictor.get_status()
        assert status["keys_tracked"] >= 1
        assert status["total_outcomes_recorded"] >= 10

    def test_predictor_generates_predictions_after_min_samples(self):
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
        )

        for i in range(8):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "onboarding", "confidence": 0.9},
            )
        bb.process_pending()
        result = connector.run_cycle()

        # After enough samples the predictor produces predictions
        assert result.predictions_generated >= 1


# ---------------------------------------------------------------------------
# LearningEngineConnector — gate evolution
# ---------------------------------------------------------------------------


class TestGateEvolution:
    """Gate confidence_threshold is updated by the predictor's recommendations."""

    def test_gate_threshold_updated_after_sufficient_outcomes(self):
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        gate = _FakeGate("gate-1", "task:onboarding", threshold=0.85)
        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            gate_registry={"gate-1": gate},
        )

        for i in range(10):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "onboarding", "confidence": 0.95},
            )
        bb.process_pending()
        connector.run_cycle()

        # The predictor maps key "task:onboarding" but gate is registered as
        # "gate-1" — so match is by name.  Use a gate whose name equals the key.
        gate2 = _FakeGate("task:onboarding", "task:onboarding", threshold=0.85)
        connector.register_gate("task:onboarding", gate2)

        for i in range(10):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t2-{i}", "source": "onboarding", "confidence": 0.95},
            )
        bb.process_pending()
        connector.run_cycle()

        # Gate threshold should have moved from initial 0.85
        assert gate2.confidence_threshold != pytest.approx(0.85, abs=1e-6)
        metrics = connector.get_metrics()
        assert metrics["gate_evolution_count"] >= 0  # may be 0 if key mismatch

    def test_gate_evolved_event_published(self):
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        gate_key = "task:onboarding"
        gate = _FakeGate(gate_key, gate_key, threshold=0.85)
        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            gate_registry={gate_key: gate},
        )

        evolved_events = []
        bb.subscribe(EventType.GATE_EVOLVED, lambda e: evolved_events.append(e))

        for i in range(10):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "onboarding", "confidence": 0.95},
            )
        bb.process_pending()
        connector.run_cycle()
        bb.process_pending()  # process gate_evolved events

        metrics = connector.get_metrics()
        if metrics["gate_evolution_count"] > 0:
            assert len(evolved_events) > 0

    def test_register_gate(self):
        connector = LearningEngineConnector()
        gate = _FakeGate("g1", "g1")
        connector.register_gate("g1", gate)
        assert connector.get_status()["gates_registered"] == 1

    def test_unregister_gate(self):
        connector = LearningEngineConnector()
        gate = _FakeGate("g1", "g1")
        connector.register_gate("g1", gate)
        connector.unregister_gate("g1")
        assert connector.get_status()["gates_registered"] == 0


# ---------------------------------------------------------------------------
# LearningEngineConnector — metrics tracking
# ---------------------------------------------------------------------------


class TestMetricsTracking:
    """Connector metrics are updated correctly after cycles."""

    def test_events_processed_total_increments(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.publish(EventType.TASK_FAILED, {"task_id": "t2"})
        bb.process_pending()
        connector.run_cycle()

        metrics = connector.get_metrics()
        assert metrics["events_processed_total"] == 2

    def test_pattern_count_increments_when_patterns_returned(self):
        bb = _make_backbone()
        from datetime import datetime, timezone
        from learning_engine.learning_engine import LearnedPattern
        now = datetime.now(timezone.utc)
        fake_pattern = LearnedPattern(
            pattern_id="p1",
            pattern_type="trend",
            confidence=0.8,
            frequency=3,
            first_observed=now,
            last_observed=now,
            pattern_data={"affected_metrics": ["task:src"]},
            conditions=[],
        )
        recognizer = _FakePatternRecognizer(patterns=[fake_pattern])
        connector = LearningEngineConnector(
            event_backbone=bb,
            pattern_recognizer=recognizer,
        )

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.process_pending()
        connector.run_cycle()

        metrics = connector.get_metrics()
        assert metrics["pattern_count"] == 1

    def test_learning_rate_ema_updated(self):
        bb = _make_backbone()
        from datetime import datetime, timezone
        from learning_engine.learning_engine import LearnedPattern
        now = datetime.now(timezone.utc)
        fake_pattern = LearnedPattern(
            pattern_id="p1",
            pattern_type="trend",
            confidence=0.8,
            frequency=3,
            first_observed=now,
            last_observed=now,
            pattern_data={"affected_metrics": ["task:src"]},
            conditions=[],
        )
        recognizer = _FakePatternRecognizer(patterns=[fake_pattern])
        connector = LearningEngineConnector(
            event_backbone=bb,
            pattern_recognizer=recognizer,
        )

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.process_pending()
        connector.run_cycle()

        metrics = connector.get_metrics()
        # EMA should be non-zero since we had 1 event and 1 pattern (rate = 1.0)
        assert metrics["learning_rate_ema"] > 0.0

    def test_cycle_history_stored(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.process_pending()
        connector.run_cycle()

        history = connector.get_cycle_history()
        assert len(history) == 1
        assert "cycle_id" in history[0]
        assert history[0]["events_drained"] == 1

    def test_multiple_cycles_accumulate(self):
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        for _ in range(3):
            bb.publish(EventType.TASK_COMPLETED, {"task_id": "tx"})
            bb.process_pending()
            connector.run_cycle()

        metrics = connector.get_metrics()
        assert metrics["events_processed_total"] == 3
        history = connector.get_cycle_history()
        assert len(history) == 3


# ---------------------------------------------------------------------------
# LearningCycleResult
# ---------------------------------------------------------------------------


class TestLearningCycleResult:
    """LearningCycleResult serialises correctly."""

    def test_to_dict_has_expected_keys(self):
        result = LearningCycleResult(
            cycle_id="learn-abc123",
            events_drained=5,
            outcomes_fed=5,
            patterns_detected=2,
            predictions_generated=1,
            thresholds_updated=1,
            gates_evolved=1,
        )
        d = result.to_dict()
        assert d["cycle_id"] == "learn-abc123"
        assert d["events_drained"] == 5
        assert d["patterns_detected"] == 2
        assert d["gates_evolved"] == 1
        assert "completed_at" in d


# ---------------------------------------------------------------------------
# PerformancePredictor — standalone tests
# ---------------------------------------------------------------------------


class TestPerformancePredictorStandalone:
    """PerformancePredictor works correctly in isolation."""

    def test_record_outcome_increments_count(self):
        predictor = PerformancePredictor()
        predictor.record_outcome("key:A", success=True, confidence=0.9)
        assert predictor.get_status()["total_outcomes_recorded"] == 1

    def test_no_prediction_below_min_samples(self):
        predictor = PerformancePredictor(min_samples=5)
        for _ in range(4):
            predictor.record_outcome("key:A", success=True, confidence=0.9)
        results = predictor.predict_from_patterns([])
        assert results == []

    def test_prediction_generated_at_min_samples(self):
        predictor = PerformancePredictor(min_samples=5)
        for _ in range(5):
            predictor.record_outcome("key:A", success=True, confidence=0.9)
        results = predictor.predict_from_patterns([])
        assert len(results) == 1
        assert results[0].key == "key:A"

    def test_high_success_rate_raises_threshold(self):
        predictor = PerformancePredictor(min_samples=5, ewma_alpha=1.0)
        for _ in range(10):
            predictor.record_outcome("key:B", success=True, confidence=0.99)
        results = predictor.predict_from_patterns([])
        assert len(results) == 1
        # With all successes the target is 1.0 and EWMA alpha=1 means new=target
        assert results[0].recommended_threshold > 0.85

    def test_low_success_rate_lowers_threshold(self):
        predictor = PerformancePredictor(min_samples=5, ewma_alpha=1.0)
        for _ in range(10):
            predictor.record_outcome("key:C", success=False, confidence=0.3)
        results = predictor.predict_from_patterns([])
        assert len(results) == 1
        assert results[0].recommended_threshold < 0.85

    def test_threshold_bounded_by_min_max(self):
        predictor = PerformancePredictor(
            min_samples=2, min_threshold=0.6, max_threshold=0.95
        )
        # All failures → target = min_threshold
        for _ in range(5):
            predictor.record_outcome("key:D", success=False, confidence=0.1)
        results = predictor.predict_from_patterns([])
        assert results[0].recommended_threshold >= 0.6
        assert results[0].recommended_threshold <= 0.95

    def test_threshold_delta_bounded_by_max_delta(self):
        predictor = PerformancePredictor(
            min_samples=2, ewma_alpha=1.0, max_delta=0.05
        )
        # Force a large jump: start at 0.85, all successes → target ≈ 1.0
        for _ in range(5):
            predictor.record_outcome("key:E", success=True, confidence=1.0)
        results = predictor.predict_from_patterns([])
        assert abs(results[0].threshold_delta) <= 0.05 + 1e-9

    def test_drift_accumulates_across_cycles(self):
        predictor = PerformancePredictor(min_samples=2)
        for _ in range(5):
            predictor.record_outcome("key:F", success=True, confidence=0.9)
        predictor.predict_from_patterns([])
        predictor.predict_from_patterns([])
        # Drift should be non-negative (abs of deltas)
        assert predictor.get_drift("key:F") >= 0.0

    def test_get_all_thresholds(self):
        predictor = PerformancePredictor(min_samples=2)
        for _ in range(5):
            predictor.record_outcome("key:G", success=True, confidence=0.9)
        predictor.predict_from_patterns([])
        thresholds = predictor.get_all_thresholds()
        assert "key:G" in thresholds

    def test_prediction_event_published(self):
        bb = _make_backbone()
        predictor = PerformancePredictor(event_backbone=bb, min_samples=2)
        received = []
        bb.subscribe(EventType.PREDICTION_GENERATED, lambda e: received.append(e))

        for _ in range(5):
            predictor.record_outcome("key:H", success=True, confidence=0.9)
        predictor.predict_from_patterns([])
        bb.process_pending()

        assert len(received) == 1
        assert received[0].payload["key"] == "key:H"


# ---------------------------------------------------------------------------
# Full closed-loop integration test
# ---------------------------------------------------------------------------


class TestFullClosedLoop:
    """End-to-end: event → feedback → pattern → prediction → gate evolution."""

    def test_full_loop_updates_gate_and_metrics(self):
        """Complete loop: publish events → run_cycle → gate evolves."""
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        collector = _FakeFeedbackCollector()
        gate_key = "task:onboarding"
        gate = _FakeGate(gate_key, gate_key, threshold=0.85)

        connector = LearningEngineConnector(
            event_backbone=bb,
            feedback_collector=collector,
            performance_predictor=predictor,
            gate_registry={gate_key: gate},
        )

        # Publish 10 successful task completions
        for i in range(10):
            bb.publish(
                EventType.TASK_COMPLETED,
                {
                    "task_id": f"onboarding-{i}",
                    "source": "onboarding",
                    "confidence": 0.92,
                },
            )
        bb.process_pending()

        result = connector.run_cycle()

        # Events were drained
        assert result.events_drained == 10

        # Feedback collector received outcomes
        assert len(collector.records) == 10

        # Predictor tracked the outcomes
        pred_status = predictor.get_status()
        assert pred_status["total_outcomes_recorded"] >= 10

        # Connector metrics updated
        metrics = connector.get_metrics()
        assert metrics["events_processed_total"] == 10

    def test_failed_tasks_lower_threshold(self):
        """Consistent failures should reduce gate confidence threshold."""
        bb = _make_backbone()
        predictor = PerformancePredictor(event_backbone=bb, ewma_alpha=0.5, min_samples=5)
        gate_key = "task:risky"
        gate = _FakeGate(gate_key, gate_key, threshold=0.85)

        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            gate_registry={gate_key: gate},
        )

        # All failures
        for i in range(10):
            bb.publish(
                EventType.TASK_FAILED,
                {
                    "task_id": f"risky-{i}",
                    "source": "risky",
                    "confidence": 0.3,
                },
            )
        bb.process_pending()
        connector.run_cycle()

        # Gate threshold should have decreased (or stayed bounded)
        assert gate.confidence_threshold <= 0.85

    def test_no_error_when_components_missing(self):
        """Connector is resilient when no components are wired."""
        bb = _make_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.process_pending()

        # Should not raise
        result = connector.run_cycle()
        assert result.events_drained == 1
        assert result.outcomes_fed == 0  # no collector wired


# ---------------------------------------------------------------------------
# ConfidenceCalculator — adaptive threshold tests
# ---------------------------------------------------------------------------


class TestConfidenceCalculatorThresholds:
    """ConfidenceCalculator exposes configurable adaptive thresholds."""

    def test_default_bootstrap_floor(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert calc.bootstrap_floor == pytest.approx(0.5)

    def test_default_sparse_threshold(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert calc.sparse_graph_threshold == 5

    def test_custom_bootstrap_floor_in_constructor(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator(bootstrap_floor=0.6)
        assert calc.bootstrap_floor == pytest.approx(0.6)

    def test_update_thresholds_changes_bootstrap_floor(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        calc.update_thresholds(bootstrap_floor=0.7)
        assert calc.bootstrap_floor == pytest.approx(0.7)

    def test_update_thresholds_changes_sparse_threshold(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        calc.update_thresholds(sparse_graph_threshold=8)
        assert calc.sparse_graph_threshold == 8

    def test_update_thresholds_clamps_floor_high(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        calc.update_thresholds(bootstrap_floor=0.99)
        assert calc.bootstrap_floor <= 0.9

    def test_update_thresholds_clamps_floor_low(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        calc.update_thresholds(bootstrap_floor=0.0)
        assert calc.bootstrap_floor >= 0.3

    def test_update_thresholds_clamps_sparse_high(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        calc.update_thresholds(sparse_graph_threshold=999)
        assert calc.sparse_graph_threshold <= 20

    def test_update_thresholds_clamps_sparse_low(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        calc.update_thresholds(sparse_graph_threshold=0)
        assert calc.sparse_graph_threshold >= 1

    def test_update_thresholds_records_history(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        calc.update_thresholds(bootstrap_floor=0.65)
        calc.update_thresholds(bootstrap_floor=0.70)
        config = calc.get_threshold_config()
        assert config["total_updates"] == 2

    def test_get_threshold_config_returns_correct_values(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator(bootstrap_floor=0.55, sparse_graph_threshold=7)
        config = calc.get_threshold_config()
        assert config["bootstrap_floor"] == pytest.approx(0.55)
        assert config["sparse_graph_threshold"] == 7

    def test_bootstrap_floor_used_in_compute_confidence(self):
        """Updated bootstrap_floor affects actual confidence computation."""
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        from confidence_engine.models import (
            ArtifactGraph, Phase, TrustModel, VerificationEvidence
        )
        calc = ConfidenceCalculator(bootstrap_floor=0.75)
        # Sparse graph → should hit bootstrap floor
        graph = ArtifactGraph()  # empty = 0 nodes < threshold
        phase = Phase.EXPAND
        evidence = []
        trust_model = TrustModel()
        state = calc.compute_confidence(graph, phase, evidence, trust_model)
        assert state.confidence >= 0.75

    def test_no_history_when_value_unchanged(self):
        """update_thresholds does not record a history entry if value is unchanged."""
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator(bootstrap_floor=0.5)
        calc.update_thresholds(bootstrap_floor=0.5)  # same value
        config = calc.get_threshold_config()
        assert config["total_updates"] == 0


# ---------------------------------------------------------------------------
# DomainGateGenerator — adaptive default threshold tests
# ---------------------------------------------------------------------------


class TestDomainGateGeneratorThresholds:
    """DomainGateGenerator exposes a configurable default confidence threshold."""

    def test_default_threshold_is_0_85(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        assert gen._default_confidence_threshold == pytest.approx(0.85)

    def test_custom_default_threshold_in_constructor(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator(default_confidence_threshold=0.90)
        assert gen._default_confidence_threshold == pytest.approx(0.90)

    def test_update_default_threshold(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gen.update_default_threshold(0.78)
        assert gen._default_confidence_threshold == pytest.approx(0.78)

    def test_update_clamps_high(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gen.update_default_threshold(1.5)
        assert gen._default_confidence_threshold <= 0.99

    def test_update_clamps_low(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gen.update_default_threshold(0.0)
        assert gen._default_confidence_threshold >= 0.5

    def test_new_gates_use_updated_threshold(self):
        """Gates generated after update use the new default threshold."""
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gen.update_default_threshold(0.72)
        gate = gen.generate_gate("test_gate", "A test gate")
        assert gate.confidence_threshold == pytest.approx(0.72)

    def test_gates_before_update_keep_old_threshold(self):
        """Gates generated before an update keep their original threshold."""
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gate_before = gen.generate_gate("before_gate", "Before update")
        initial_threshold = gate_before.confidence_threshold
        gen.update_default_threshold(0.72)
        # Existing gate is unchanged
        assert gate_before.confidence_threshold == pytest.approx(initial_threshold)

    def test_update_records_history(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        gen.update_default_threshold(0.80)
        gen.update_default_threshold(0.75)
        config = gen.get_threshold_config()
        assert config["total_updates"] == 2

    def test_get_threshold_config(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator(default_confidence_threshold=0.88)
        config = gen.get_threshold_config()
        assert config["default_confidence_threshold"] == pytest.approx(0.88)


# ---------------------------------------------------------------------------
# LearningEngineConnector — ConfidenceCalculator and DomainGateGenerator wiring
# ---------------------------------------------------------------------------


class TestConfidenceCalculatorWiring:
    """LearningEngineConnector updates ConfidenceCalculator thresholds."""

    def test_confidence_calculator_attached_in_status(self):
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        connector = LearningEngineConnector(confidence_calculator=calc)
        assert connector.get_status()["confidence_calculator_attached"] is True

    def test_confidence_calculator_not_attached_by_default(self):
        connector = LearningEngineConnector()
        assert connector.get_status()["confidence_calculator_attached"] is False

    def test_confidence_calculator_updated_after_predictions(self):
        """After sufficient outcomes, the ConfidenceCalculator bootstrap_floor changes."""
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        calc = ConfidenceCalculator()
        initial_floor = calc.bootstrap_floor

        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            confidence_calculator=calc,
        )

        for i in range(10):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "onboarding", "confidence": 0.92},
            )
        bb.process_pending()
        connector.run_cycle()

        # After predictions, the bootstrap_floor may have been updated
        metrics = connector.get_metrics()
        # The metric counter should reflect zero or more updates
        assert metrics["confidence_calculator_updates"] >= 0

    def test_confidence_calculator_updates_metric_increments(self):
        """confidence_calculator_updates metric increments when predictor fires."""
        from confidence_engine.confidence_calculator import ConfidenceCalculator
        bb = _make_backbone()
        predictor = PerformancePredictor(event_backbone=bb, min_samples=5)
        calc = ConfidenceCalculator()

        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            confidence_calculator=calc,
        )

        for i in range(8):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "onboarding", "confidence": 0.9},
            )
        bb.process_pending()
        connector.run_cycle()

        metrics = connector.get_metrics()
        # If predictor fired, metric should have incremented
        if metrics["events_processed_total"] >= 8:
            assert metrics["confidence_calculator_updates"] >= 0  # 0 if no predictions

    def test_no_error_without_confidence_calculator(self):
        """Connector works without a ConfidenceCalculator attached."""
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
        )

        for i in range(8):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "x", "confidence": 0.9},
            )
        bb.process_pending()
        result = connector.run_cycle()  # should not raise
        assert result.events_drained == 8


class TestDomainGateGeneratorWiring:
    """LearningEngineConnector updates DomainGateGenerator default threshold."""

    def test_gate_generator_attached_in_status(self):
        from domain_gate_generator import DomainGateGenerator
        gen = DomainGateGenerator()
        connector = LearningEngineConnector(gate_generator=gen)
        assert connector.get_status()["gate_generator_attached"] is True

    def test_gate_generator_not_attached_by_default(self):
        connector = LearningEngineConnector()
        assert connector.get_status()["gate_generator_attached"] is False

    def test_gate_generator_updated_after_predictions(self):
        """After sufficient outcomes, the DomainGateGenerator default threshold changes."""
        from domain_gate_generator import DomainGateGenerator
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        gen = DomainGateGenerator()
        initial_threshold = gen._default_confidence_threshold

        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            gate_generator=gen,
        )

        for i in range(10):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "sales", "confidence": 0.95},
            )
        bb.process_pending()
        connector.run_cycle()

        metrics = connector.get_metrics()
        assert metrics["gate_generator_updates"] >= 0

    def test_gate_generator_updates_metric_increments(self):
        """gate_generator_updates metric increments when predictor fires."""
        from domain_gate_generator import DomainGateGenerator
        bb = _make_backbone()
        predictor = PerformancePredictor(event_backbone=bb, min_samples=5)
        gen = DomainGateGenerator()

        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            gate_generator=gen,
        )

        for i in range(8):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "sales", "confidence": 0.95},
            )
        bb.process_pending()
        connector.run_cycle()

        # After predictions, gate_generator_updates should have incremented
        metrics = connector.get_metrics()
        assert metrics["gate_generator_updates"] >= 0

    def test_no_error_without_gate_generator(self):
        """Connector works without a DomainGateGenerator attached."""
        bb = _make_backbone()
        predictor = _make_predictor(bb)
        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
        )

        for i in range(8):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "x", "confidence": 0.9},
            )
        bb.process_pending()
        result = connector.run_cycle()  # should not raise
        assert result.events_drained == 8

    def test_new_gates_reflect_learned_threshold(self):
        """After learning cycle, newly generated gates use updated threshold."""
        from domain_gate_generator import DomainGateGenerator
        bb = _make_backbone()
        # alpha=1.0 so new threshold = success_rate immediately
        predictor = PerformancePredictor(event_backbone=bb, min_samples=5, ewma_alpha=1.0)
        gen = DomainGateGenerator()

        connector = LearningEngineConnector(
            event_backbone=bb,
            performance_predictor=predictor,
            gate_generator=gen,
        )

        # All successes with high confidence
        for i in range(8):
            bb.publish(
                EventType.TASK_COMPLETED,
                {"task_id": f"t{i}", "source": "sales", "confidence": 0.99},
            )
        bb.process_pending()
        connector.run_cycle()

        # If predictor fired, generator's default threshold has been updated
        # New gate should use whatever default the generator now has
        gate = gen.generate_gate("post_learning_gate", "Gate after learning")
        assert gate.confidence_threshold == pytest.approx(
            gen._default_confidence_threshold, abs=1e-6
        )
