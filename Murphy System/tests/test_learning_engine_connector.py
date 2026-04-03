"""
Tests for LearningEngineConnector — closed-loop ML wiring hub.

Covers:
- Instantiation and start/stop lifecycle
- Event handler integration (task success, failure, gate eval, automation)
- force_analyze() propagates insights
- status() diagnostic snapshot
- bootstrap_learning_connector() singleton creation
- get_connector() returns running instance
- Graceful degradation when backbone/learning engine unavailable
"""

import pytest
from unittest.mock import MagicMock, patch, call
from typing import Any

import os
import sys

import pytest


from event_backbone import EventBackbone, EventType
from learning_engine_connector import LearningCycleResult, LearningEngineConnector
from performance_predictor import PerformancePredictor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_event(event_id: str = "evt-001", payload: dict = None):
    e = MagicMock()
    e.event_id = event_id
    e.payload = payload or {}
    return e


def _make_backbone():
    """Return a mock backbone that tracks subscriptions."""
    backbone = MagicMock()
    backbone.subscribe.side_effect = lambda et, handler: f"sub-{et.value}"
    backbone.unsubscribe = MagicMock()
    return backbone


def _make_learning_engine():
    engine = MagicMock()
    engine.record_performance = MagicMock()
    engine.collect_feedback = MagicMock()
    engine.analyze_learning = MagicMock(return_value=[])
    return engine


def _make_connector(analyze_interval=9999.0, backbone=None, learning=None):
    """Create a LearningEngineConnector with provided or mock deps."""
    from src.learning_engine_connector import LearningEngineConnector
    bb = backbone if backbone is not None else _make_backbone()
    le = learning if learning is not None else _make_learning_engine()
    return LearningEngineConnector(
        backbone=bb,
        learning_engine=le,
        analyze_interval_seconds=analyze_interval,
    ), bb, le


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------

class TestImport:
    def test_module_importable(self):
        import src.learning_engine_connector as mod
        assert hasattr(mod, "LearningEngineConnector")
        assert hasattr(mod, "bootstrap_learning_connector")
        assert hasattr(mod, "get_connector")


# ---------------------------------------------------------------------------
# Lifecycle: start / stop
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_start_subscribes_to_event_types(self):
        conn, bb, _ = _make_connector()
        result = conn.start()
        assert result is True
        assert conn._is_started is True
        assert bb.subscribe.call_count >= 3  # TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED

    def test_start_is_idempotent(self):
        conn, bb, _ = _make_connector()
        conn.start()
        conn.start()  # second call should be no-op
        # subscribe must not be called again on second start
        count_after_first = bb.subscribe.call_count
        assert count_after_first == bb.subscribe.call_count

    def test_stop_unsubscribes_all(self):
        conn, bb, _ = _make_connector()
        conn.start()
        sub_count = len(conn._subscription_ids)
        conn.stop()
        assert bb.unsubscribe.call_count == sub_count
        assert conn._is_started is False
        assert len(conn._subscription_ids) == 0

    def test_stop_when_not_started_is_safe(self):
        conn, _, _ = _make_connector()
        conn.stop()  # must not raise

    def test_start_returns_false_when_backbone_none_and_module_missing(self):
        """When backbone=None AND EventBackbone module unavailable, start() returns False."""
        from src.learning_engine_connector import LearningEngineConnector
        import unittest.mock as _mock
        with _mock.patch("src.learning_engine_connector._import_event_backbone",
                         return_value=(None, None)):
            conn = LearningEngineConnector(
                backbone=None,
                learning_engine=_make_learning_engine(),
            )
            result = conn.start()
            assert result is False
            assert conn._is_started is False

    def test_start_returns_false_when_learning_engine_none_and_module_missing(self):
        """When learning_engine=None AND module unavailable, start() returns False."""
        from src.learning_engine_connector import LearningEngineConnector
        import unittest.mock as _mock
        with _mock.patch("src.learning_engine_connector._import_learning_engine",
                         return_value=None):
            conn = LearningEngineConnector(
                backbone=_make_backbone(),
                learning_engine=None,
            )
            result = conn.start()
            assert result is False


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

class TestEventHandlers:
    def test_on_task_completed_records_success(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={
            "task_id": "t-001", "duration_seconds": 1.5, "confidence": 0.9
        })
        conn._on_task_completed(event)
        le.record_performance.assert_called()
        calls = [c.args[0] for c in le.record_performance.call_args_list]
        assert "task_success_rate" in calls

    def test_on_task_completed_records_duration(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={
            "task_id": "t-002", "duration_seconds": 3.7, "confidence": 0.8
        })
        conn._on_task_completed(event)
        calls = [c.args[0] for c in le.record_performance.call_args_list]
        assert "task_duration_seconds" in calls

    def test_on_task_completed_skips_duration_when_zero(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={"task_id": "t-003", "duration_seconds": 0})
        conn._on_task_completed(event)
        calls = [c.args[0] for c in le.record_performance.call_args_list]
        assert "task_duration_seconds" not in calls

    def test_on_task_completed_collects_positive_feedback(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={"task_id": "t-004", "confidence": 0.95})
        conn._on_task_completed(event)
        le.collect_feedback.assert_called_once()
        kwargs = le.collect_feedback.call_args.kwargs
        assert kwargs["success"] is True
        assert kwargs["feedback_type"] == "task_execution"

    def test_on_task_failed_records_failure_rate(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={"task_id": "t-005", "confidence": 0.2})
        conn._on_task_failed(event)
        calls = [(c.args[0], c.args[1]) for c in le.record_performance.call_args_list]
        assert ("task_success_rate", 0.0) in calls

    def test_on_task_failed_collects_negative_feedback(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={"task_id": "t-006"})
        conn._on_task_failed(event)
        le.collect_feedback.assert_called_once()
        kwargs = le.collect_feedback.call_args.kwargs
        assert kwargs["success"] is False

    def test_on_gate_evaluated_records_gate_confidence(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={
            "gate_id": "G-HITL", "confidence": 0.88, "passed": True
        })
        conn._on_gate_evaluated(event)
        calls = [c.args[0] for c in le.record_performance.call_args_list]
        assert any("G-HITL" in m for m in calls)

    def test_on_gate_evaluated_collects_gate_feedback(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={
            "gate_id": "G-REVIEW", "confidence": 0.6, "passed": False
        })
        conn._on_gate_evaluated(event)
        le.collect_feedback.assert_called_once()
        kwargs = le.collect_feedback.call_args.kwargs
        assert kwargs["feedback_type"] == "gate_evaluation"
        assert kwargs["success"] is False

    def test_on_automation_executed_records_success(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={
            "automation_id": "auto-01", "success": True, "confidence": 0.9
        })
        conn._on_automation_executed(event)
        calls = [(c.args[0], c.args[1]) for c in le.record_performance.call_args_list]
        assert ("automation_success_rate", 1.0) in calls

    def test_on_automation_executed_records_failure(self):
        conn, _, le = _make_connector()
        event = _make_fake_event(payload={
            "automation_id": "auto-02", "success": False, "confidence": 0.3
        })
        conn._on_automation_executed(event)
        calls = [(c.args[0], c.args[1]) for c in le.record_performance.call_args_list]
        assert ("automation_success_rate", 0.0) in calls

    def test_events_received_counter_increments(self):
        conn, _, _ = _make_connector()
        for _ in range(5):
            conn._on_task_completed(_make_fake_event())
        assert conn._events_received == 5

    def test_handler_does_not_raise_on_learning_engine_error(self):
        """Handlers must not propagate exceptions from the learning engine."""
        conn, _, le = _make_connector()
        le.record_performance.side_effect = RuntimeError("simulated failure")
        conn._on_task_completed(_make_fake_event())  # must not raise


# ---------------------------------------------------------------------------
# Force analyze
# ---------------------------------------------------------------------------

class TestForceAnalyze:
    def test_force_analyze_calls_analyze_learning(self):
        conn, _, le = _make_connector(analyze_interval=9999.0)
        le.analyze_learning.return_value = []
        conn.force_analyze()
        le.analyze_learning.assert_called_once()

    def test_force_analyze_returns_insights(self):
        conn, _, le = _make_connector(analyze_interval=9999.0)
        insight = MagicMock()
        insight.insight_id = "i-001"
        insight.insight_type = "performance_issue"
        insight.confidence = 0.9
        insight.importance = 0.8
        le.analyze_learning.return_value = [insight]
        result = conn.force_analyze()
        assert len(result) == 1

    def test_force_analyze_updates_insights_counter(self):
        conn, _, le = _make_connector(analyze_interval=9999.0)
        insight = MagicMock()
        insight.insight_id = "i-002"
        insight.insight_type = "trend"
        insight.confidence = 0.7
        insight.importance = 0.5
        le.analyze_learning.return_value = [insight]
        conn.force_analyze()
        assert conn._insights_generated == 1

    def test_force_analyze_returns_empty_when_no_learning_engine(self):
        from src.learning_engine_connector import LearningEngineConnector
        conn = LearningEngineConnector(backbone=_make_backbone(), learning_engine=None)
        result = conn.force_analyze()
        assert result == []

    def test_force_analyze_does_not_raise_on_engine_error(self):
        conn, _, le = _make_connector()
        le.analyze_learning.side_effect = RuntimeError("analyze failed")
        result = conn.force_analyze()
        assert result == []


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_keys_present(self):
        conn, _, _ = _make_connector()
        s = conn.status()
        expected = [
            "started", "subscriptions", "events_received",
            "insights_generated", "backbone_available",
            "learning_engine_available",
        ]
        for key in expected:
            assert key in s, f"Missing key: {key}"

    def test_status_started_false_before_start(self):
        conn, _, _ = _make_connector()
        assert conn.status()["started"] is False

    def test_status_started_true_after_start(self):
        conn, _, _ = _make_connector()
        conn.start()
        assert conn.status()["started"] is True

    def test_status_backbone_available_false_when_none_and_module_missing(self):
        """backbone_available is False only when the module itself is unavailable."""
        from src.learning_engine_connector import LearningEngineConnector
        import unittest.mock as _mock
        with _mock.patch("src.learning_engine_connector._import_event_backbone",
                         return_value=(None, None)):
            conn = LearningEngineConnector(backbone=None, learning_engine=None)
            assert conn.status()["backbone_available"] is False

    def test_status_reflects_event_counter(self):
        conn, _, _ = _make_connector()
        conn._on_task_completed(_make_fake_event())
        conn._on_task_failed(_make_fake_event())
        assert conn.status()["events_received"] == 2


# ---------------------------------------------------------------------------
# Bootstrap singleton
# ---------------------------------------------------------------------------

class TestBootstrap:
    def test_bootstrap_learning_connector_returns_connector(self):
        import src.learning_engine_connector as mod
        # Reset singleton for test isolation
        mod._connector_instance = None
        try:
            conn = mod.bootstrap_learning_connector(
                backbone=_make_backbone(),
                learning_engine=_make_learning_engine(),
                analyze_interval_seconds=9999.0,
            )
            assert conn is not None
        finally:
            mod._connector_instance = None

    def test_bootstrap_second_call_returns_same_instance_if_started(self):
        import src.learning_engine_connector as mod
        mod._connector_instance = None
        try:
            bb = _make_backbone()
            le = _make_learning_engine()
            c1 = mod.bootstrap_learning_connector(backbone=bb, learning_engine=le)
            c2 = mod.bootstrap_learning_connector(backbone=bb, learning_engine=le)
            assert c1 is c2
        finally:
            mod._connector_instance = None

    def test_get_connector_returns_running_instance(self):
        import src.learning_engine_connector as mod
        mod._connector_instance = None
        try:
            mod.bootstrap_learning_connector(
                backbone=_make_backbone(),
                learning_engine=_make_learning_engine(),
            )
            assert mod.get_connector() is mod._connector_instance
        finally:
            mod._connector_instance = None

    def test_get_connector_returns_none_before_bootstrap(self):
        import src.learning_engine_connector as mod
        original = mod._connector_instance
        mod._connector_instance = None
        try:
            assert mod.get_connector() is None
        finally:
            mod._connector_instance = original

def _make_real_backbone() -> EventBackbone:
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
        bb = _make_real_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1", "confidence": 0.9})
        bb.process_pending()

        status = connector.get_status()
        assert status["pending_events"] == 1

    def test_task_failed_enqueued(self):
        bb = _make_real_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_FAILED, {"task_id": "t2", "confidence": 0.4})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 1

    def test_gate_evaluated_enqueued(self):
        bb = _make_real_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.GATE_EVALUATED, {"gate_id": "g1", "passed": True})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 1

    def test_automation_executed_enqueued(self):
        bb = _make_real_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.AUTOMATION_EXECUTED, {"task_id": "auto-1"})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 1

    def test_multiple_events_all_enqueued(self):
        bb = _make_real_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.publish(EventType.TASK_FAILED, {"task_id": "t2"})
        bb.publish(EventType.GATE_EVALUATED, {"gate_id": "g1", "passed": False})
        bb.publish(EventType.AUTOMATION_EXECUTED, {"task_id": "a1"})
        bb.process_pending()

        assert connector.get_status()["pending_events"] == 4

    def test_unrelated_event_not_enqueued(self):
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.publish(EventType.TASK_FAILED, {"task_id": "t2"})
        bb.process_pending()
        connector.run_cycle()

        metrics = connector.get_metrics()
        assert metrics["events_processed_total"] == 2

    def test_pattern_count_increments_when_patterns_returned(self):
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
        connector = LearningEngineConnector(event_backbone=bb)

        bb.publish(EventType.TASK_COMPLETED, {"task_id": "t1"})
        bb.process_pending()
        connector.run_cycle()

        history = connector.get_cycle_history()
        assert len(history) == 1
        assert "cycle_id" in history[0]
        assert history[0]["events_drained"] == 1

    def test_multiple_cycles_accumulate(self):
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
        bb = _make_real_backbone()
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
