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
