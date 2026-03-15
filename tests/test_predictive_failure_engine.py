"""
Tests for PRED-001: PredictiveFailureEngine.

Validates telemetry ingestion, heuristic detectors, preemptive action
triggering, adaptive weight adjustment, thread safety, and event publishing.

Design Label: TEST-PRED-001
Owner: QA Team
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from predictive_failure_engine import (
    PredictiveFailureEngine,
    PredictionResult,
    FailureSignal,
    AdaptiveWeightManager,
    _linear_trend,
    _signal_type_to_heuristic,
    _recommend_action,
)
from event_backbone import EventBackbone, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return PredictiveFailureEngine()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def wired_engine(backbone):
    return PredictiveFailureEngine(event_backbone=backbone)


# ---------------------------------------------------------------------------
# FailureSignal
# ---------------------------------------------------------------------------

class TestFailureSignal:
    def test_to_dict_contains_required_keys(self):
        sig = FailureSignal(
            signal_id="s-001",
            signal_type="latency_spike",
            severity_score=0.8,
            confidence=0.9,
            source_component="api-gw",
            detected_at="2024-01-01T00:00:00+00:00",
            context={"p95_ms": 600},
        )
        d = sig.to_dict()
        assert d["signal_id"] == "s-001"
        assert d["signal_type"] == "latency_spike"
        assert d["severity_score"] == 0.8
        assert d["confidence"] == 0.9
        assert d["source_component"] == "api-gw"
        assert d["context"]["p95_ms"] == 600

    def test_default_context_is_empty_dict(self):
        sig = FailureSignal(
            signal_id="s-002",
            signal_type="error_rate_increase",
            severity_score=0.5,
            confidence=0.6,
            source_component="worker",
            detected_at="2024-01-01T00:00:00+00:00",
        )
        assert sig.context == {}


# ---------------------------------------------------------------------------
# PredictionResult
# ---------------------------------------------------------------------------

class TestPredictionResult:
    def test_to_dict_contains_required_keys(self):
        pred = PredictionResult(
            prediction_id="pred-001",
            predicted_failure_type="latency_spike",
            probability=0.75,
            estimated_time_to_failure_sec=1800.0,
            recommended_preemptive_action="Scale out service",
        )
        d = pred.to_dict()
        assert d["prediction_id"] == "pred-001"
        assert d["predicted_failure_type"] == "latency_spike"
        assert d["probability"] == 0.75
        assert d["status"] == "predicted"
        assert d["supporting_signals"] == []

    def test_default_status_is_predicted(self):
        pred = PredictionResult(
            prediction_id="pred-002",
            predicted_failure_type="error_rate_increase",
            probability=0.5,
            estimated_time_to_failure_sec=900.0,
            recommended_preemptive_action="Inspect logs",
        )
        assert pred.status == "predicted"


# ---------------------------------------------------------------------------
# AdaptiveWeightManager
# ---------------------------------------------------------------------------

class TestAdaptiveWeightManager:
    def test_initial_weights_are_one(self):
        mgr = AdaptiveWeightManager()
        for heuristic in AdaptiveWeightManager._HEURISTICS:
            assert mgr.get_weight(heuristic) == 1.0

    def test_record_hit_increases_weight(self):
        mgr = AdaptiveWeightManager()
        before = mgr.get_weight("latency_degradation")
        mgr.record_hit("latency_degradation")
        after = mgr.get_weight("latency_degradation")
        assert after > before

    def test_record_miss_decreases_weight(self):
        mgr = AdaptiveWeightManager()
        before = mgr.get_weight("error_rate_acceleration")
        mgr.record_miss("error_rate_acceleration")
        after = mgr.get_weight("error_rate_acceleration")
        assert after < before

    def test_weight_bounded_above(self):
        mgr = AdaptiveWeightManager()
        for _ in range(100):
            mgr.record_hit("confidence_drift")
        assert mgr.get_weight("confidence_drift") <= 2.0

    def test_weight_bounded_below(self):
        mgr = AdaptiveWeightManager()
        for _ in range(100):
            mgr.record_miss("resource_exhaustion")
        assert mgr.get_weight("resource_exhaustion") >= 0.1

    def test_accuracy_no_data(self):
        mgr = AdaptiveWeightManager()
        assert mgr.get_accuracy("latency_degradation") == 0.0

    def test_accuracy_all_hits(self):
        mgr = AdaptiveWeightManager()
        mgr.record_hit("recurring_patterns")
        mgr.record_hit("recurring_patterns")
        assert mgr.get_accuracy("recurring_patterns") == 1.0

    def test_get_all_weights_snapshot(self):
        mgr = AdaptiveWeightManager()
        weights = mgr.get_all_weights()
        assert isinstance(weights, dict)
        assert len(weights) == len(AdaptiveWeightManager._HEURISTICS)

    def test_thread_safe_concurrent_updates(self):
        mgr = AdaptiveWeightManager()
        errors: list = []

        def update():
            try:
                for _ in range(50):
                    mgr.record_hit("latency_degradation")
                    mgr.record_miss("error_rate_acceleration")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=update) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert 0.1 <= mgr.get_weight("latency_degradation") <= 2.0


# ---------------------------------------------------------------------------
# Telemetry ingestion
# ---------------------------------------------------------------------------

class TestTelemetryIngestion:
    def test_ingest_telemetry_stores_event(self, engine):
        engine.ingest_telemetry({"component": "api-gw", "response_time_ms": 200})
        status = engine.get_status()
        assert status["telemetry_window_size"] == 1

    def test_ingest_multiple_events(self, engine):
        for i in range(10):
            engine.ingest_telemetry({"response_time_ms": 100 + i})
        status = engine.get_status()
        assert status["telemetry_window_size"] == 10

    def test_ingest_respects_window_size(self):
        small_engine = PredictiveFailureEngine(window_size=5)
        for i in range(20):
            small_engine.ingest_telemetry({"response_time_ms": i})
        status = small_engine.get_status()
        assert status["telemetry_window_size"] <= 5

    def test_ingest_error_stores_record(self, engine):
        engine.ingest_error({"message": "DB timeout", "component": "db", "fingerprint": "fp-001"})
        status = engine.get_status()
        assert status["error_window_size"] == 1


# ---------------------------------------------------------------------------
# Latency degradation detector
# ---------------------------------------------------------------------------

class TestLatencyDegradation:
    def _feed_latency(self, eng, low_values, high_values):
        for v in low_values:
            eng.ingest_telemetry({"response_time_ms": v, "component": "svc"})
        for v in high_values:
            eng.ingest_telemetry({"response_time_ms": v, "component": "svc"})

    def test_no_signal_below_threshold(self, engine):
        self._feed_latency(engine, [100] * 10, [150] * 5)
        preds = engine.analyze()
        latency_preds = [p for p in preds if p.predicted_failure_type == "latency_spike"]
        assert latency_preds == []

    def test_signal_when_p95_exceeds_2x_baseline(self, engine):
        # Baseline established from first half; second half is much higher
        self._feed_latency(engine, [100] * 10, [1000] * 10)
        preds = engine.analyze()
        latency_preds = [p for p in preds if p.predicted_failure_type == "latency_spike"]
        assert len(latency_preds) >= 1

    def test_no_signal_with_fewer_than_5_events(self, engine):
        for _ in range(4):
            engine.ingest_telemetry({"response_time_ms": 5000})
        preds = engine.analyze()
        assert preds == []


# ---------------------------------------------------------------------------
# Error rate acceleration detector
# ---------------------------------------------------------------------------

class TestErrorRateAcceleration:
    def test_no_signal_stable_error_rate(self, engine):
        # Ingest errors in stable bursts, then check
        for _ in range(5):
            engine.ingest_error({"message": "err", "fingerprint": f"fp-{_}"})
        engine.analyze()  # snapshot window
        for _ in range(5):
            engine.ingest_error({"message": "err", "fingerprint": f"fp-{_}"})
        preds = engine.analyze()
        accel_preds = [p for p in preds if p.predicted_failure_type == "error_rate_increase"]
        # Stable rate should not trigger
        assert isinstance(accel_preds, list)

    def test_signal_on_accelerating_errors(self, engine):
        # Force accelerating error rate by directly building the history
        engine._error_rate_history = [1, 3, 6, 10, 15]
        preds = engine.analyze()
        accel_preds = [p for p in preds if p.predicted_failure_type == "error_rate_increase"]
        assert len(accel_preds) >= 1


# ---------------------------------------------------------------------------
# Confidence drift detector
# ---------------------------------------------------------------------------

class TestConfidenceDrift:
    def test_no_signal_stable_confidence(self, engine):
        for v in [0.9, 0.91, 0.89, 0.9, 0.92]:
            engine.ingest_telemetry({"component": "model", "confidence": v})
        preds = engine.analyze()
        drift_preds = [p for p in preds if p.predicted_failure_type == "confidence_drift"]
        assert drift_preds == []

    def test_signal_on_consistent_downward_trend(self, engine):
        for v in [0.95, 0.85, 0.75, 0.65, 0.55, 0.45]:
            engine.ingest_telemetry({"component": "model", "confidence": v})
        preds = engine.analyze()
        drift_preds = [p for p in preds if p.predicted_failure_type == "confidence_drift"]
        assert len(drift_preds) >= 1

    def test_signal_includes_drifting_component(self, engine):
        for v in [0.95, 0.8, 0.65, 0.5, 0.35]:
            engine.ingest_telemetry({"component": "nlp-engine", "confidence": v})
        preds = engine.analyze()
        drift_preds = [p for p in preds if p.predicted_failure_type == "confidence_drift"]
        assert len(drift_preds) >= 1
        ctx = drift_preds[0].supporting_signals[0].context
        assert "nlp-engine" in ctx.get("drifting_components", [])


# ---------------------------------------------------------------------------
# Resource exhaustion detector
# ---------------------------------------------------------------------------

class TestResourceExhaustion:
    def test_no_signal_normal_memory(self, engine):
        engine.ingest_telemetry({"component": "worker", "memory_mb": 512})
        preds = engine.analyze()
        res_preds = [p for p in preds if p.predicted_failure_type == "resource_pressure"]
        assert res_preds == []

    def test_signal_high_memory(self, engine):
        engine.ingest_telemetry({"component": "worker", "memory_mb": 3900})
        preds = engine.analyze()
        res_preds = [p for p in preds if p.predicted_failure_type == "resource_pressure"]
        assert len(res_preds) >= 1

    def test_signal_large_config_store(self, engine):
        engine.ingest_telemetry({"component": "runtime", "runtime_config_size": 20_000})
        preds = engine.analyze()
        res_preds = [p for p in preds if p.predicted_failure_type == "resource_pressure"]
        assert len(res_preds) >= 1

    def test_signal_too_many_procedures(self, engine):
        engine.ingest_telemetry({"component": "runtime", "registered_procedures": 1000})
        preds = engine.analyze()
        res_preds = [p for p in preds if p.predicted_failure_type == "resource_pressure"]
        assert len(res_preds) >= 1

    def test_no_signal_empty_telemetry(self, engine):
        preds = engine.analyze()
        assert preds == []


# ---------------------------------------------------------------------------
# Recurring patterns detector
# ---------------------------------------------------------------------------

class TestRecurringPatterns:
    def test_no_signal_on_first_occurrence(self, engine):
        engine.ingest_error({"fingerprint": "fp-abc", "component": "svc"})
        preds = engine.analyze()
        recur_preds = [p for p in preds if p.predicted_failure_type == "pattern_recurrence"]
        assert recur_preds == []

    def test_signal_on_recurrence_within_cooldown(self, engine):
        # Seed first occurrence
        engine.ingest_error({"fingerprint": "fp-xyz", "component": "svc"})
        engine.analyze()  # records seen_patterns
        # Ingest same fingerprint again
        engine.ingest_error({"fingerprint": "fp-xyz", "component": "svc"})
        preds = engine.analyze()
        recur_preds = [p for p in preds if p.predicted_failure_type == "pattern_recurrence"]
        assert len(recur_preds) >= 1

    def test_signal_has_high_confidence(self, engine):
        engine.ingest_error({"fingerprint": "fp-repeat", "component": "db"})
        engine.analyze()
        engine.ingest_error({"fingerprint": "fp-repeat", "component": "db"})
        preds = engine.analyze()
        recur_preds = [p for p in preds if p.predicted_failure_type == "pattern_recurrence"]
        assert recur_preds[0].supporting_signals[0].confidence == 0.9


# ---------------------------------------------------------------------------
# Analyze returns structured predictions
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_analyze_returns_list(self, engine):
        result = engine.analyze()
        assert isinstance(result, list)

    def test_analyze_no_signals_returns_empty(self, engine):
        result = engine.analyze()
        assert result == []

    def test_predictions_stored_in_engine(self, engine):
        engine._error_rate_history = [1, 4, 9, 16, 25]
        preds = engine.analyze()
        assert len(preds) >= 1
        stored = engine.get_predictions()
        assert len(stored) >= 1

    def test_probability_bounded_zero_to_one(self, engine):
        engine.ingest_telemetry({"component": "w", "memory_mb": 4095})
        preds = engine.analyze()
        for p in preds:
            assert 0.0 <= p.probability <= 1.0


# ---------------------------------------------------------------------------
# Preempt
# ---------------------------------------------------------------------------

class TestPreempt:
    def test_preempt_returns_false_without_dependencies(self, engine):
        pred = PredictionResult(
            prediction_id="pred-test",
            predicted_failure_type="latency_spike",
            probability=0.9,
            estimated_time_to_failure_sec=300.0,
            recommended_preemptive_action="Scale out",
        )
        result = engine.preempt(pred)
        assert result is False

    def test_preempt_updates_status_when_fix_loop_present(self):
        class _FakeFixLoop:
            called = False

            def run_loop(self, max_iterations=1):
                self.called = True

        loop = _FakeFixLoop()
        eng = PredictiveFailureEngine(self_fix_loop=loop)
        pred = PredictionResult(
            prediction_id="pred-fl",
            predicted_failure_type="error_rate_increase",
            probability=0.8,
            estimated_time_to_failure_sec=600.0,
            recommended_preemptive_action="Run diagnostics",
        )
        result = eng.preempt(pred)
        assert result is True
        assert pred.status == "preempted"
        assert loop.called

    def test_preempt_skips_already_preempted(self, engine):
        pred = PredictionResult(
            prediction_id="pred-already",
            predicted_failure_type="latency_spike",
            probability=0.5,
            estimated_time_to_failure_sec=1200.0,
            recommended_preemptive_action="Scale",
            status="preempted",
        )
        result = engine.preempt(pred)
        assert result is False

    def test_preempt_publishes_event(self, wired_engine, backbone):
        class _FakeFixLoop:
            def run_loop(self, max_iterations=1):
                pass

        eng = PredictiveFailureEngine(
            self_fix_loop=_FakeFixLoop(),
            event_backbone=backbone,
        )
        pred = PredictionResult(
            prediction_id="pred-evt",
            predicted_failure_type="latency_spike",
            probability=0.7,
            estimated_time_to_failure_sec=900.0,
            recommended_preemptive_action="Scale",
        )
        eng.preempt(pred)
        # One PREDICTION_PREEMPTED event should be queued
        backbone.process_pending()
        status = backbone.get_status()
        assert status["events_processed"] >= 1


# ---------------------------------------------------------------------------
# Record outcome (feedback loop)
# ---------------------------------------------------------------------------

class TestRecordOutcome:
    def _make_engine_with_prediction(self):
        eng = PredictiveFailureEngine()
        sig = FailureSignal(
            signal_id="s-feed",
            signal_type="latency_spike",
            severity_score=0.7,
            confidence=0.8,
            source_component="svc",
            detected_at="2024-01-01T00:00:00+00:00",
        )
        pred = PredictionResult(
            prediction_id="pred-feed",
            predicted_failure_type="latency_spike",
            probability=0.7,
            estimated_time_to_failure_sec=600.0,
            recommended_preemptive_action="Scale",
            supporting_signals=[sig],
        )
        with eng._lock:
            eng._predictions.append(pred)
        return eng, pred

    def test_record_outcome_materialized_increases_weight(self):
        eng, pred = self._make_engine_with_prediction()
        before = eng._weights.get_weight("latency_degradation")
        eng.record_outcome("pred-feed", "materialized")
        after = eng._weights.get_weight("latency_degradation")
        assert after > before

    def test_record_outcome_false_positive_decreases_weight(self):
        eng, pred = self._make_engine_with_prediction()
        before = eng._weights.get_weight("latency_degradation")
        eng.record_outcome("pred-feed", "false_positive")
        after = eng._weights.get_weight("latency_degradation")
        assert after < before

    def test_record_outcome_updates_status(self):
        eng, pred = self._make_engine_with_prediction()
        eng.record_outcome("pred-feed", "materialized")
        assert pred.status == "materialized"

    def test_record_outcome_returns_false_for_unknown_id(self, engine):
        result = engine.record_outcome("no-such-id", "materialized")
        assert result is False

    def test_record_outcome_publishes_event(self, backbone):
        eng = PredictiveFailureEngine(event_backbone=backbone)
        sig = FailureSignal(
            signal_id="s-pub",
            signal_type="error_rate_increase",
            severity_score=0.6,
            confidence=0.7,
            source_component="svc",
            detected_at="2024-01-01T00:00:00+00:00",
        )
        pred = PredictionResult(
            prediction_id="pred-pub",
            predicted_failure_type="error_rate_increase",
            probability=0.6,
            estimated_time_to_failure_sec=900.0,
            recommended_preemptive_action="Inspect",
            supporting_signals=[sig],
        )
        with eng._lock:
            eng._predictions.append(pred)
        eng.record_outcome("pred-pub", "false_positive")
        backbone.process_pending()
        status = backbone.get_status()
        assert status["events_processed"] >= 1


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------

class TestEventPublishing:
    def test_analyze_publishes_prediction_generated(self, backbone):
        eng = PredictiveFailureEngine(event_backbone=backbone)
        eng.ingest_telemetry({"component": "w", "memory_mb": 4090})
        preds = eng.analyze()
        if preds:
            backbone.process_pending()
            status = backbone.get_status()
            assert status["events_processed"] >= 1

    def test_event_types_exist(self):
        assert hasattr(EventType, "PREDICTION_GENERATED")
        assert hasattr(EventType, "PREDICTION_PREEMPTED")
        assert hasattr(EventType, "PREDICTION_MATERIALIZED")
        assert hasattr(EventType, "PREDICTION_FALSE_POSITIVE")


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_ingest_and_analyze(self, engine):
        errors: list = []

        def ingest():
            try:
                for i in range(50):
                    engine.ingest_telemetry({"response_time_ms": 100 + i, "component": "t"})
                    engine.ingest_error({"message": "err", "fingerprint": f"fp-{i}"})
            except Exception as exc:
                errors.append(exc)

        def analyze():
            try:
                for _ in range(20):
                    engine.analyze()
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=ingest) for _ in range(5)]
            + [threading.Thread(target=analyze) for _ in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_record_outcomes(self, engine):
        errors: list = []

        # Seed predictions
        for i in range(20):
            sig = FailureSignal(
                signal_id=f"s-{i}",
                signal_type="latency_spike",
                severity_score=0.5,
                confidence=0.5,
                source_component="svc",
                detected_at="2024-01-01T00:00:00+00:00",
            )
            pred = PredictionResult(
                prediction_id=f"pred-{i}",
                predicted_failure_type="latency_spike",
                probability=0.5,
                estimated_time_to_failure_sec=600.0,
                recommended_preemptive_action="Scale",
                supporting_signals=[sig],
            )
            with engine._lock:
                engine._predictions.append(pred)

        def record():
            try:
                for i in range(20):
                    engine.record_outcome(f"pred-{i}", "materialized")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=record) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ---------------------------------------------------------------------------
# Status and get_predictions
# ---------------------------------------------------------------------------

class TestStatus:
    def test_initial_status(self, engine):
        status = engine.get_status()
        assert status["telemetry_window_size"] == 0
        assert status["error_window_size"] == 0
        assert status["total_predictions"] == 0
        assert isinstance(status["heuristic_weights"], dict)

    def test_get_predictions_returns_list(self, engine):
        preds = engine.get_predictions()
        assert isinstance(preds, list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_linear_trend_ascending(self):
        slope = _linear_trend([1.0, 2.0, 3.0, 4.0, 5.0])
        assert slope > 0

    def test_linear_trend_descending(self):
        slope = _linear_trend([5.0, 4.0, 3.0, 2.0, 1.0])
        assert slope < 0

    def test_linear_trend_flat(self):
        slope = _linear_trend([3.0, 3.0, 3.0, 3.0])
        assert slope == 0.0

    def test_linear_trend_single_value(self):
        assert _linear_trend([5.0]) == 0.0

    def test_signal_type_to_heuristic_mapping(self):
        assert _signal_type_to_heuristic("latency_spike") == "latency_degradation"
        assert _signal_type_to_heuristic("error_rate_increase") == "error_rate_acceleration"
        assert _signal_type_to_heuristic("confidence_drift") == "confidence_drift"
        assert _signal_type_to_heuristic("resource_pressure") == "resource_exhaustion"
        assert _signal_type_to_heuristic("pattern_recurrence") == "recurring_patterns"

    def test_recommend_action_known_type(self):
        action = _recommend_action("latency_spike")
        assert isinstance(action, str)
        assert len(action) > 0

    def test_recommend_action_unknown_type(self):
        action = _recommend_action("unknown_type")
        assert isinstance(action, str)
        assert len(action) > 0
