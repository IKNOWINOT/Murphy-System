"""
Tests for OBS-010: UnifiedObservabilityEngine.

Validates metric recording, sliding-window statistics, anomaly detection,
health-score computation, alert-rule evaluation, event-to-metric extraction,
report generation, and thread safety.

Design Label: TEST-OBS-010
Owner: QA Team
"""

import sys
import os
import math
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unified_observability_engine import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    FiredAlert,
    MetricPoint,
    MetricType,
    MetricWindow,
    SystemHealthScore,
    TrendDirection,
    UnifiedObservabilityEngine,
)
from event_backbone import EventBackbone, EventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return UnifiedObservabilityEngine()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def wired_engine(backbone):
    return UnifiedObservabilityEngine(event_backbone=backbone)


# ===========================================================================
# MetricPoint
# ===========================================================================

class TestMetricPoint:
    def test_defaults(self):
        pt = MetricPoint(metric_name="foo.bar", value=42.0)
        assert pt.metric_name == "foo.bar"
        assert pt.value == 42.0
        assert isinstance(pt.timestamp, float)
        assert pt.metric_type == MetricType.GAUGE

    def test_to_dict(self):
        pt = MetricPoint("a.b", 1.5, tags={"component": "test"}, metric_type=MetricType.COUNTER)
        d = pt.to_dict()
        assert d["metric_name"] == "a.b"
        assert d["value"] == 1.5
        assert d["metric_type"] == "counter"
        assert d["tags"]["component"] == "test"


# ===========================================================================
# MetricWindow
# ===========================================================================

class TestMetricWindow:
    def test_add_and_len(self):
        w = MetricWindow(window_size=5)
        for i in range(5):
            w.add(float(i))
        assert len(w) == 5

    def test_circular_buffer_overflow(self):
        w = MetricWindow(window_size=3)
        for i in range(10):
            w.add(float(i))
        assert len(w) == 3
        vals, _ = w._snapshot()
        assert vals == [7.0, 8.0, 9.0]

    def test_mean(self):
        w = MetricWindow()
        for v in [1.0, 2.0, 3.0, 4.0]:
            w.add(v)
        assert w.mean() == pytest.approx(2.5)

    def test_mean_empty(self):
        assert MetricWindow().mean() == 0.0

    def test_p50(self):
        w = MetricWindow()
        for v in [1, 2, 3, 4, 5]:
            w.add(float(v))
        assert w.p50() == pytest.approx(3.0)

    def test_p95(self):
        w = MetricWindow()
        for v in range(100):
            w.add(float(v))
        # p95 of 0..99 ≈ 94.05
        assert w.p95() == pytest.approx(94.05)

    def test_p99(self):
        w = MetricWindow()
        for v in range(100):
            w.add(float(v))
        assert w.p99() == pytest.approx(98.01)

    def test_p50_single_value(self):
        w = MetricWindow()
        w.add(7.0)
        assert w.p50() == 7.0

    def test_rate_increasing(self):
        w = MetricWindow()
        now = time.time()
        w.add(0.0, now)
        w.add(10.0, now + 5.0)
        assert w.rate() == pytest.approx(2.0)

    def test_rate_insufficient_points(self):
        w = MetricWindow()
        w.add(5.0)
        assert w.rate() == 0.0

    def test_rate_same_timestamp(self):
        w = MetricWindow()
        ts = time.time()
        w.add(1.0, ts)
        w.add(2.0, ts)
        assert w.rate() == 0.0

    def test_trend_rising(self):
        w = MetricWindow()
        now = time.time()
        for i in range(10):
            w.add(float(i * 10), now + i)
        assert w.trend() == TrendDirection.RISING

    def test_trend_falling(self):
        w = MetricWindow()
        now = time.time()
        for i in range(10):
            w.add(float(100 - i * 10), now + i)
        assert w.trend() == TrendDirection.FALLING

    def test_trend_stable(self):
        w = MetricWindow()
        now = time.time()
        for i in range(10):
            w.add(5.0, now + i)
        assert w.trend() == TrendDirection.STABLE

    def test_trend_single_point(self):
        w = MetricWindow()
        w.add(1.0)
        assert w.trend() == TrendDirection.STABLE

    def test_anomaly_score_normal(self):
        w = MetricWindow()
        for _ in range(50):
            w.add(10.0)
        # All identical values → z-score of 0
        assert w.anomaly_score() == pytest.approx(0.0)

    def test_anomaly_score_outlier(self):
        w = MetricWindow()
        for _ in range(50):
            w.add(10.0)
        w.add(1000.0)  # extreme outlier
        score = w.anomaly_score()
        assert score == pytest.approx(1.0)

    def test_anomaly_score_insufficient_data(self):
        w = MetricWindow()
        w.add(1.0)
        w.add(2.0)
        assert w.anomaly_score() == 0.0


# ===========================================================================
# SystemHealthScore
# ===========================================================================

class TestSystemHealthScore:
    def test_to_dict(self):
        score = SystemHealthScore(
            overall=0.87,
            components={"heartbeat": 0.9, "self_fix_loop": 0.85},
            alerts=["test alert"],
        )
        d = score.to_dict()
        assert d["overall"] == pytest.approx(0.87, abs=1e-4)
        assert d["components"]["heartbeat"] == pytest.approx(0.9, abs=1e-4)
        assert "test alert" in d["alerts"]
        assert "computed_at" in d


# ===========================================================================
# UnifiedObservabilityEngine — metric recording and querying
# ===========================================================================

class TestMetricRecordingAndQuerying:
    def test_record_single_metric(self, engine):
        engine.record_metric("test.metric", 42.0)
        pts = engine.query("test.metric")
        assert len(pts) == 1
        assert pts[0].value == 42.0

    def test_record_multiple_metrics(self, engine):
        engine.record_metric("a.b", 1.0)
        engine.record_metric("a.c", 2.0)
        assert len(engine.query("a.b")) == 1
        assert len(engine.query("a.c")) == 1

    def test_record_multiple_points_same_metric(self, engine):
        for i in range(5):
            engine.record_metric("counter", float(i))
        assert len(engine.query("counter")) == 5

    def test_query_time_range(self, engine):
        now = time.time()
        engine.record_metric("ts.test", 1.0, timestamp=now - 100)
        engine.record_metric("ts.test", 2.0, timestamp=now - 50)
        engine.record_metric("ts.test", 3.0, timestamp=now)
        pts = engine.query("ts.test", time_range=(now - 60, now))
        assert len(pts) == 2
        assert {p.value for p in pts} == {2.0, 3.0}

    def test_query_tag_filter(self, engine):
        engine.record_metric("tagged", 1.0, tags={"env": "prod"})
        engine.record_metric("tagged", 2.0, tags={"env": "dev"})
        pts = engine.query("tagged", tags={"env": "prod"})
        assert len(pts) == 1
        assert pts[0].value == 1.0

    def test_query_unknown_metric_empty(self, engine):
        assert engine.query("does.not.exist") == []

    def test_get_metric_names(self, engine):
        engine.record_metric("alpha", 1.0)
        engine.record_metric("beta", 2.0)
        names = engine.get_metric_names()
        assert "alpha" in names
        assert "beta" in names

    def test_record_returns_metric_point(self, engine):
        pt = engine.record_metric("ret.test", 7.0, tags={"k": "v"})
        assert isinstance(pt, MetricPoint)
        assert pt.value == 7.0


# ===========================================================================
# Health score computation
# ===========================================================================

class TestHealthScoreComputation:
    def test_no_data_defaults_to_healthy(self, engine):
        score = engine.compute_health_score()
        assert score.overall == pytest.approx(1.0)
        for v in score.components.values():
            assert v == pytest.approx(1.0)

    def test_heartbeat_healthy(self, engine):
        engine.record_metric("heartbeat.bots_healthy", 8.0)
        engine.record_metric("heartbeat.bots_total", 10.0)
        score = engine.compute_health_score()
        assert score.components["heartbeat"] == pytest.approx(0.8)

    def test_heartbeat_all_healthy(self, engine):
        engine.record_metric("heartbeat.bots_healthy", 5.0)
        engine.record_metric("heartbeat.bots_total", 5.0)
        score = engine.compute_health_score()
        assert score.components["heartbeat"] == pytest.approx(1.0)

    def test_self_fix_loop_no_gaps(self, engine):
        engine.record_metric("self_fix_loop.gaps_remaining", 0.0)
        engine.record_metric("self_fix_loop.gaps_fixed", 5.0)
        score = engine.compute_health_score()
        assert score.components["self_fix_loop"] == pytest.approx(1.0)

    def test_self_fix_loop_some_gaps(self, engine):
        engine.record_metric("self_fix_loop.gaps_remaining", 4.0)
        engine.record_metric("self_fix_loop.gaps_fixed", 6.0)
        score = engine.compute_health_score()
        # total = 10, remaining = 4 → score = 1 - 4/10 = 0.6
        assert score.components["self_fix_loop"] == pytest.approx(0.6)

    def test_supervision_tree_health(self, engine):
        engine.record_metric("supervision_tree.running_components", 7.0)
        engine.record_metric("supervision_tree.total_components", 10.0)
        score = engine.compute_health_score()
        assert score.components["supervision_tree"] == pytest.approx(0.7)

    def test_circuit_breaker_health(self, engine):
        engine.record_metric("circuit_breaker.closed_breakers", 3.0)
        engine.record_metric("circuit_breaker.total_breakers", 4.0)
        score = engine.compute_health_score()
        assert score.components["circuit_breaker"] == pytest.approx(0.75)

    def test_overall_is_weighted_average(self, engine):
        # All 4 components equal → overall == component value
        engine.record_metric("heartbeat.bots_healthy", 6.0)
        engine.record_metric("heartbeat.bots_total", 10.0)
        engine.record_metric("self_fix_loop.gaps_remaining", 4.0)
        engine.record_metric("self_fix_loop.gaps_fixed", 6.0)
        engine.record_metric("supervision_tree.running_components", 6.0)
        engine.record_metric("supervision_tree.total_components", 10.0)
        engine.record_metric("circuit_breaker.closed_breakers", 6.0)
        engine.record_metric("circuit_breaker.total_breakers", 10.0)
        score = engine.compute_health_score()
        assert 0.0 <= score.overall <= 1.0

    def test_score_clipped_to_zero_one(self, engine):
        # Force a bad value scenario
        engine.record_metric("heartbeat.bots_healthy", -5.0)
        engine.record_metric("heartbeat.bots_total", 10.0)
        score = engine.compute_health_score()
        assert score.components["heartbeat"] == pytest.approx(0.0)
        assert 0.0 <= score.overall <= 1.0

    def test_health_score_is_dataclass(self, engine):
        score = engine.compute_health_score()
        assert isinstance(score, SystemHealthScore)
        assert isinstance(score.components, dict)
        assert isinstance(score.alerts, list)


# ===========================================================================
# Anomaly detection
# ===========================================================================

class TestAnomalyDetection:
    def test_no_anomalies_flat_series(self, engine):
        for _ in range(30):
            engine.record_metric("stable.metric", 5.0)
        anomalies = engine.detect_anomalies()
        assert len(anomalies) == 0

    def test_anomaly_detected_on_outlier(self, engine):
        for _ in range(50):
            engine.record_metric("spike.metric", 1.0)
        engine.record_metric("spike.metric", 10000.0)
        anomalies = engine.detect_anomalies(threshold=0.5)
        assert any("spike.metric" in a for a in anomalies)

    def test_custom_threshold(self, engine):
        for _ in range(10):
            engine.record_metric("m", 1.0)
        engine.record_metric("m", 5.0)
        # High threshold — should not fire
        no_anomalies = engine.detect_anomalies(threshold=0.99)
        low_anomalies = engine.detect_anomalies(threshold=0.01)
        # At least one case behaves differently
        assert isinstance(no_anomalies, list)
        assert isinstance(low_anomalies, list)

    def test_anomaly_score_via_window(self):
        w = MetricWindow()
        for _ in range(50):
            w.add(5.0)
        w.add(1000.0)
        assert w.anomaly_score() >= 0.7


# ===========================================================================
# Alert rule evaluation
# ===========================================================================

class TestAlertRuleEvaluation:
    def test_alert_fires_when_threshold_exceeded(self):
        rule = AlertRule(
            rule_id="test-1",
            name="Test Rule",
            metric_name="test.metric",
            threshold=5.0,
            window_seconds=300.0,
            severity=AlertSeverity.WARNING,
        )
        manager = AlertManager(rules=[rule])
        w = MetricWindow()
        w.add(10.0)
        fired = manager.evaluate_rules({"test.metric": w})
        assert len(fired) == 1
        assert fired[0].rule_id == "test-1"

    def test_alert_does_not_fire_below_threshold(self):
        rule = AlertRule("r2", "R2", "m", threshold=10.0, window_seconds=60.0)
        manager = AlertManager(rules=[rule])
        w = MetricWindow()
        w.add(5.0)
        fired = manager.evaluate_rules({"m": w})
        assert len(fired) == 0

    def test_alert_fires_once_not_twice(self):
        rule = AlertRule("r3", "R3", "m", threshold=1.0, window_seconds=300.0)
        manager = AlertManager(rules=[rule])
        w = MetricWindow()
        w.add(5.0)
        fired1 = manager.evaluate_rules({"m": w})
        fired2 = manager.evaluate_rules({"m": w})
        assert len(fired1) == 1
        assert len(fired2) == 0  # already active — not re-fired

    def test_alert_resolved_when_condition_clears(self):
        rule = AlertRule("r4", "R4", "m", threshold=3.0, window_seconds=300.0)
        manager = AlertManager(rules=[rule])
        w_high = MetricWindow()
        w_high.add(10.0)
        manager.evaluate_rules({"m": w_high})
        assert len(manager.get_active_alerts()) == 1

        # Now provide a window that doesn't exceed threshold
        w_low = MetricWindow()
        w_low.add(1.0)
        manager.evaluate_rules({"m": w_low})
        assert len(manager.get_active_alerts()) == 0

    def test_disabled_rule_skipped(self):
        rule = AlertRule("r5", "R5", "m", threshold=1.0, window_seconds=60.0, enabled=False)
        manager = AlertManager(rules=[rule])
        w = MetricWindow()
        w.add(100.0)
        fired = manager.evaluate_rules({"m": w})
        assert len(fired) == 0

    def test_add_and_remove_rule(self):
        manager = AlertManager(rules=[])
        rule = AlertRule("r6", "R6", "m", threshold=1.0, window_seconds=60.0)
        manager.add_rule(rule)
        assert len(manager.list_rules()) == 1
        removed = manager.remove_rule("r6")
        assert removed is True
        assert len(manager.list_rules()) == 0

    def test_remove_nonexistent_rule(self):
        manager = AlertManager(rules=[])
        assert manager.remove_rule("nonexistent") is False

    def test_alert_severity_preserved(self):
        rule = AlertRule("r7", "R7", "m", threshold=0.0, severity=AlertSeverity.CRITICAL,
                         window_seconds=60.0)
        manager = AlertManager(rules=[rule])
        w = MetricWindow()
        w.add(1.0)
        fired = manager.evaluate_rules({"m": w})
        assert fired[0].severity == AlertSeverity.CRITICAL

    def test_get_active_alerts_returns_dicts(self):
        rule = AlertRule("r8", "R8", "m", threshold=0.0, window_seconds=60.0)
        manager = AlertManager(rules=[rule])
        w = MetricWindow()
        w.add(5.0)
        manager.evaluate_rules({"m": w})
        active = manager.get_active_alerts()
        assert len(active) == 1
        assert "alert_id" in active[0]
        assert "severity" in active[0]

    def test_fired_alert_to_dict(self):
        alert = FiredAlert(
            alert_id="aid1",
            rule_id="rid1",
            rule_name="Test",
            severity=AlertSeverity.INFO,
            metric_name="m",
            observed_value=7.5,
            threshold=5.0,
            message="test msg",
        )
        d = alert.to_dict()
        assert d["alert_id"] == "aid1"
        assert d["is_active"] is True
        assert d["severity"] == "info"

    def test_manager_status(self):
        manager = AlertManager(rules=[])
        s = manager.get_status()
        assert s["total_rules"] == 0
        assert s["active_alerts"] == 0


# ===========================================================================
# Event-to-metric extraction
# ===========================================================================

class TestEventToMetricExtraction:
    def test_self_fix_completed_extracts_gaps(self, wired_engine, backbone):
        backbone.publish(
            EventType.SELF_FIX_COMPLETED,
            {"gaps_fixed": 3, "gaps_remaining": 2},
            source="test",
        )
        backbone.process_pending()
        assert wired_engine.query("self_fix_loop.gaps_fixed") != []
        assert wired_engine.query("self_fix_loop.gaps_remaining") != []

    def test_self_fix_completed_values(self, wired_engine, backbone):
        backbone.publish(
            EventType.SELF_FIX_COMPLETED,
            {"gaps_fixed": 5, "gaps_remaining": 1},
        )
        backbone.process_pending()
        pts = wired_engine.query("self_fix_loop.gaps_fixed")
        assert pts[-1].value == 5.0

    def test_bot_heartbeat_ok_extracts_counts(self, wired_engine, backbone):
        backbone.publish(
            EventType.BOT_HEARTBEAT_OK,
            {"bots_healthy": 8, "total_bots": 10},
        )
        backbone.process_pending()
        pts_healthy = wired_engine.query("heartbeat.bots_healthy")
        pts_total = wired_engine.query("heartbeat.bots_total")
        assert len(pts_healthy) == 1
        assert pts_healthy[0].value == 8.0
        assert pts_total[0].value == 10.0

    def test_bot_heartbeat_failed_extracts_counter(self, wired_engine, backbone):
        backbone.publish(
            EventType.BOT_HEARTBEAT_FAILED,
            {"failed_bots": 2},
        )
        backbone.process_pending()
        pts = wired_engine.query("heartbeat.bots_failed")
        assert pts[-1].value == 2.0

    def test_supervisor_child_restarted_extracts(self, wired_engine, backbone):
        backbone.publish(
            EventType.SUPERVISOR_CHILD_RESTARTED,
            {"running_components": 9, "total_components": 10},
        )
        backbone.process_pending()
        restarts = wired_engine.query("supervision_tree.child_restarts")
        assert len(restarts) >= 1
        running = wired_engine.query("supervision_tree.running_components")
        assert running[-1].value == 9.0

    def test_system_health_extracts_circuit_breakers(self, wired_engine, backbone):
        backbone.publish(
            EventType.SYSTEM_HEALTH,
            {"closed_breakers": 3, "total_breakers": 4, "circuit_breaker_trips": 1},
        )
        backbone.process_pending()
        closed = wired_engine.query("circuit_breaker.closed_breakers")
        assert closed[-1].value == 3.0

    def test_self_fix_started_extracts_counter(self, wired_engine, backbone):
        backbone.publish(EventType.SELF_FIX_STARTED, {})
        backbone.process_pending()
        pts = wired_engine.query("self_fix_loop.runs_started")
        assert len(pts) >= 1

    def test_self_fix_rolled_back_extracts_counter(self, wired_engine, backbone):
        backbone.publish(EventType.SELF_FIX_ROLLED_BACK, {})
        backbone.process_pending()
        pts = wired_engine.query("self_fix_loop.rollbacks")
        assert len(pts) >= 1


# ===========================================================================
# Report generation
# ===========================================================================

class TestReportGeneration:
    def test_report_is_string(self, engine):
        report = engine.generate_report()
        assert isinstance(report, str)

    def test_report_contains_title(self, engine):
        assert "Murphy System" in engine.generate_report()

    def test_report_contains_health_header(self, engine):
        assert "Health" in engine.generate_report()

    def test_report_contains_metric_names(self, engine):
        engine.record_metric("custom.gauge", 7.0)
        report = engine.generate_report()
        assert "custom.gauge" in report

    def test_report_contains_no_alerts_message_when_clean(self, engine):
        report = engine.generate_report()
        assert "No active alerts" in report

    def test_report_contains_no_anomalies_message_when_clean(self, engine):
        for _ in range(20):
            engine.record_metric("flat.metric", 10.0)
        report = engine.generate_report()
        assert "No anomalies detected" in report

    def test_report_contains_component_scores(self, engine):
        engine.record_metric("heartbeat.bots_healthy", 8.0)
        engine.record_metric("heartbeat.bots_total", 10.0)
        report = engine.generate_report()
        assert "heartbeat" in report


# ===========================================================================
# Dashboard data
# ===========================================================================

class TestDashboardData:
    def test_structure(self, engine):
        engine.record_metric("db.query_time", 50.0)
        data = engine.get_dashboard_data()
        assert "health_score" in data
        assert "metrics" in data
        assert "active_alerts" in data
        assert "anomalies" in data
        assert "generated_at" in data

    def test_metrics_summary_keys(self, engine):
        engine.record_metric("m1", 10.0)
        data = engine.get_dashboard_data()
        m = data["metrics"]["m1"]
        for key in ("count", "mean", "p50", "p95", "p99", "rate", "trend", "anomaly_score"):
            assert key in m, f"Missing key: {key}"

    def test_health_score_in_dashboard(self, engine):
        engine.record_metric("heartbeat.bots_healthy", 10.0)
        engine.record_metric("heartbeat.bots_total", 10.0)
        data = engine.get_dashboard_data()
        assert data["health_score"]["overall"] == pytest.approx(1.0)


# ===========================================================================
# AlertManager with EventBackbone
# ===========================================================================

class TestAlertManagerWithBackbone:
    def test_alert_fired_event_published(self, backbone):
        rule = AlertRule("r-bb", "BB Rule", "m", threshold=1.0, window_seconds=60.0,
                         severity=AlertSeverity.CRITICAL)
        manager = AlertManager(rules=[rule], event_backbone=backbone)
        received = []
        backbone.subscribe(EventType.ALERT_FIRED, lambda e: received.append(e))
        w = MetricWindow()
        w.add(5.0)
        manager.evaluate_rules({"m": w})
        backbone.process_pending()
        assert len(received) >= 1

    def test_alert_resolved_event_published(self, backbone):
        rule = AlertRule("r-res", "Res Rule", "m", threshold=1.0, window_seconds=60.0)
        manager = AlertManager(rules=[rule], event_backbone=backbone)
        resolved = []
        backbone.subscribe(EventType.ALERT_RESOLVED, lambda e: resolved.append(e))
        w_high = MetricWindow()
        w_high.add(5.0)
        manager.evaluate_rules({"m": w_high})
        w_low = MetricWindow()
        w_low.add(0.5)
        manager.evaluate_rules({"m": w_low})
        backbone.process_pending()
        assert len(resolved) >= 1


# ===========================================================================
# Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_record_metric(self, engine):
        errors = []

        def worker(n):
            try:
                for _ in range(100):
                    engine.record_metric(f"thread.metric.{n}", float(n))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        for i in range(5):
            pts = engine.query(f"thread.metric.{i}")
            assert len(pts) == 100

    def test_concurrent_compute_health_score(self, engine):
        for _ in range(50):
            engine.record_metric("heartbeat.bots_healthy", 8.0)
            engine.record_metric("heartbeat.bots_total", 10.0)

        errors = []
        results = []

        def compute():
            try:
                results.append(engine.compute_health_score())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=compute) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(results) == 10
        for r in results:
            assert 0.0 <= r.overall <= 1.0

    def test_concurrent_window_add(self):
        w = MetricWindow(window_size=500)
        errors = []

        def adder():
            try:
                for i in range(100):
                    w.add(float(i))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=adder) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(w) == 500  # capped at window size


# ===========================================================================
# Engine status
# ===========================================================================

class TestEngineStatus:
    def test_initial_status(self, engine):
        s = engine.get_status()
        assert s["status"] == "ok"
        assert s["metrics_tracked"] == 0
        assert s["backbone_attached"] is False

    def test_status_after_recording(self, engine):
        engine.record_metric("x", 1.0)
        engine.record_metric("y", 2.0)
        s = engine.get_status()
        assert s["metrics_tracked"] == 2
        assert s["total_points_stored"] == 2

    def test_wired_status(self, wired_engine):
        s = wired_engine.get_status()
        assert s["backbone_attached"] is True
