"""Tests for the Operational SLO Tracker module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import threading
import pytest
from src.operational_slo_tracker import (
    ExecutionRecord,
    SLOTarget,
    OperationalSLOTracker,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def tracker():
    return OperationalSLOTracker()


def _make_record(
    task_type="deploy",
    success=True,
    duration=1.0,
    failure_reason=None,
    required_approval=False,
    approved=None,
    timestamp=None,
):
    return ExecutionRecord(
        task_type=task_type,
        success=success,
        duration=duration,
        failure_reason=failure_reason,
        required_approval=required_approval,
        approved=approved,
        timestamp=timestamp,
    )


# ------------------------------------------------------------------
# Execution recording
# ------------------------------------------------------------------

class TestExecutionRecording:
    def test_record_single_execution(self, tracker):
        record = _make_record(task_type="build")
        rid = tracker.record_execution(record)
        assert isinstance(rid, str) and len(rid) == 12
        assert tracker.get_status()["total_records"] == 1

    def test_record_multiple_executions(self, tracker):
        for i in range(5):
            tracker.record_execution(_make_record(task_type=f"type-{i}"))
        assert tracker.get_status()["total_records"] == 5

    def test_record_default_timestamp(self):
        record = ExecutionRecord(task_type="a", success=True, duration=0.5)
        assert record.timestamp is not None

    def test_record_custom_timestamp(self):
        record = ExecutionRecord(
            task_type="a", success=True, duration=0.5,
            timestamp="2024-01-01T00:00:00+00:00",
        )
        assert record.timestamp == "2024-01-01T00:00:00+00:00"


# ------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------

class TestMetrics:
    def test_empty_metrics(self, tracker):
        m = tracker.get_metrics()
        assert m["sample_size"] == 0
        assert m["success_rate"] == 0.0

    def test_success_rate(self, tracker):
        for _ in range(8):
            tracker.record_execution(_make_record(success=True))
        for _ in range(2):
            tracker.record_execution(_make_record(success=False, failure_reason="timeout"))
        m = tracker.get_metrics()
        assert m["success_rate"] == pytest.approx(0.8)
        assert m["sample_size"] == 10

    def test_failure_causes(self, tracker):
        tracker.record_execution(_make_record(success=False, failure_reason="timeout"))
        tracker.record_execution(_make_record(success=False, failure_reason="timeout"))
        tracker.record_execution(_make_record(success=False, failure_reason="auth_error"))
        m = tracker.get_metrics()
        assert m["failure_causes"]["timeout"] == 2
        assert m["failure_causes"]["auth_error"] == 1

    def test_filter_by_task_type(self, tracker):
        tracker.record_execution(_make_record(task_type="build", success=True, duration=1.0))
        tracker.record_execution(_make_record(task_type="build", success=False, duration=2.0,
                                               failure_reason="compile_error"))
        tracker.record_execution(_make_record(task_type="test", success=True, duration=0.5))
        m_build = tracker.get_metrics(task_type="build")
        m_test = tracker.get_metrics(task_type="test")
        assert m_build["sample_size"] == 2
        assert m_build["success_rate"] == pytest.approx(0.5)
        assert m_test["sample_size"] == 1
        assert m_test["success_rate"] == pytest.approx(1.0)

    def test_approval_ratio(self, tracker):
        tracker.record_execution(_make_record(required_approval=True, approved=True))
        tracker.record_execution(_make_record(required_approval=True, approved=True))
        tracker.record_execution(_make_record(required_approval=True, approved=False))
        tracker.record_execution(_make_record(required_approval=False))
        m = tracker.get_metrics()
        assert m["approval_ratio"] == pytest.approx(2.0 / 3.0, rel=1e-3)

    def test_nonexistent_task_type(self, tracker):
        tracker.record_execution(_make_record(task_type="build"))
        m = tracker.get_metrics(task_type="nonexistent")
        assert m["sample_size"] == 0


# ------------------------------------------------------------------
# Latency percentiles
# ------------------------------------------------------------------

class TestLatencyPercentiles:
    def test_single_value(self, tracker):
        tracker.record_execution(_make_record(duration=5.0))
        m = tracker.get_metrics()
        assert m["latency_p50"] == pytest.approx(5.0)
        assert m["latency_p95"] == pytest.approx(5.0)
        assert m["latency_p99"] == pytest.approx(5.0)

    def test_known_distribution(self, tracker):
        # 1..100 uniform
        for i in range(1, 101):
            tracker.record_execution(_make_record(duration=float(i)))
        m = tracker.get_metrics()
        assert m["latency_p50"] == pytest.approx(50.5, abs=1.0)
        assert m["latency_p95"] == pytest.approx(95.05, abs=1.0)
        assert m["latency_p99"] == pytest.approx(99.01, abs=1.0)

    def test_two_values(self, tracker):
        tracker.record_execution(_make_record(duration=1.0))
        tracker.record_execution(_make_record(duration=3.0))
        m = tracker.get_metrics()
        assert m["latency_p50"] == pytest.approx(2.0)


# ------------------------------------------------------------------
# SLO target compliance
# ------------------------------------------------------------------

class TestSLOCompliance:
    def test_no_targets(self, tracker):
        result = tracker.check_slo_compliance()
        assert result == {}

    def test_success_rate_compliant(self, tracker):
        tracker.add_slo_target(SLOTarget(
            target_name="deploy-success",
            metric="success_rate",
            threshold=0.8,
            window_seconds=3600,
        ))
        for _ in range(9):
            tracker.record_execution(_make_record(success=True))
        tracker.record_execution(_make_record(success=False, failure_reason="err"))
        result = tracker.check_slo_compliance()
        assert result["deploy-success"]["compliant"] is True
        assert result["deploy-success"]["actual"] == pytest.approx(0.9)

    def test_success_rate_non_compliant(self, tracker):
        tracker.add_slo_target(SLOTarget(
            target_name="deploy-success",
            metric="success_rate",
            threshold=0.95,
            window_seconds=3600,
        ))
        for _ in range(7):
            tracker.record_execution(_make_record(success=True))
        for _ in range(3):
            tracker.record_execution(_make_record(success=False, failure_reason="err"))
        result = tracker.check_slo_compliance()
        assert result["deploy-success"]["compliant"] is False

    def test_latency_p95_compliant(self, tracker):
        tracker.add_slo_target(SLOTarget(
            target_name="latency-slo",
            metric="latency_p95",
            threshold=5.0,
            window_seconds=3600,
        ))
        for i in range(20):
            tracker.record_execution(_make_record(duration=float(i % 4 + 1)))
        result = tracker.check_slo_compliance()
        assert result["latency-slo"]["compliant"] is True

    def test_latency_p95_non_compliant(self, tracker):
        tracker.add_slo_target(SLOTarget(
            target_name="latency-slo",
            metric="latency_p95",
            threshold=2.0,
            window_seconds=3600,
        ))
        for i in range(20):
            tracker.record_execution(_make_record(duration=float(i + 1)))
        result = tracker.check_slo_compliance()
        assert result["latency-slo"]["compliant"] is False

    def test_compliance_result_structure(self, tracker):
        tracker.add_slo_target(SLOTarget(
            target_name="my-slo",
            metric="success_rate",
            threshold=0.5,
            window_seconds=3600,
        ))
        tracker.record_execution(_make_record(success=True))
        result = tracker.check_slo_compliance()
        entry = result["my-slo"]
        assert "target_name" in entry
        assert "metric" in entry
        assert "threshold" in entry
        assert "actual" in entry
        assert "compliant" in entry
        assert "window_seconds" in entry
        assert "sample_size" in entry


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_empty_status(self, tracker):
        status = tracker.get_status()
        assert status["total_records"] == 0
        assert status["total_slo_targets"] == 0
        assert status["tracking_active"] is False

    def test_status_after_activity(self, tracker):
        tracker.record_execution(_make_record(task_type="build"))
        tracker.record_execution(_make_record(task_type="test"))
        tracker.add_slo_target(SLOTarget(
            target_name="slo-1", metric="success_rate",
            threshold=0.9, window_seconds=3600,
        ))
        status = tracker.get_status()
        assert status["total_records"] == 2
        assert status["total_slo_targets"] == 1
        assert status["tracking_active"] is True
        assert sorted(status["task_types_tracked"]) == ["build", "test"]


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_recording(self, tracker):
        errors: list = []

        def _record_batch(start: int):
            try:
                for i in range(50):
                    tracker.record_execution(_make_record(
                        task_type="concurrent",
                        duration=float(start + i),
                    ))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_record_batch, args=(i * 50,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert tracker.get_status()["total_records"] == 200

    def test_concurrent_metrics_and_recording(self, tracker):
        # Pre-populate some data
        for i in range(20):
            tracker.record_execution(_make_record(duration=float(i)))

        errors: list = []

        def _read_metrics():
            try:
                for _ in range(50):
                    tracker.get_metrics()
            except Exception as exc:
                errors.append(exc)

        def _write_records():
            try:
                for i in range(50):
                    tracker.record_execution(_make_record(duration=float(i)))
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=_read_metrics)
        t2 = threading.Thread(target=_write_records)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == []


# ------------------------------------------------------------------
# Alert Rules Engine wiring (ARCH-007)
# ------------------------------------------------------------------

class TestAlertRulesEngineWiring:
    def test_init_without_alert_engine(self):
        t = OperationalSLOTracker()
        s = t.get_status()
        assert s["alert_rules_engine_attached"] is False

    def test_init_with_alert_engine(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from alert_rules_engine import AlertRulesEngine
        engine = AlertRulesEngine()
        t = OperationalSLOTracker(alert_rules_engine=engine)
        s = t.get_status()
        assert s["alert_rules_engine_attached"] is True

    def test_get_fired_alerts_empty(self):
        t = OperationalSLOTracker()
        assert t.get_fired_alerts() == []

    def test_slo_breach_fires_alert(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from alert_rules_engine import AlertRulesEngine, AlertRule, AlertSeverity, Comparator
        engine = AlertRulesEngine()
        engine.add_rule(AlertRule(
            "rule-test-success", "Test SLO Breach", AlertSeverity.CRITICAL,
            "success_rate", Comparator.LT, 0.95, 0.0, "SLO breach test"
        ))
        t = OperationalSLOTracker(alert_rules_engine=engine)
        t.add_slo_target(SLOTarget("slo-success", "success_rate", 0.95, 3600.0))
        # Record 3 successes and 7 failures → success_rate=0.3 < 0.95
        for _ in range(3):
            t.record_execution(_make_record(success=True))
        for _ in range(7):
            t.record_execution(_make_record(success=False))
        compliance = t.check_slo_compliance()
        assert compliance["slo-success"]["compliant"] is False
        alerts = t.get_fired_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["rule_name"] == "Test SLO Breach"

    def test_compliant_slo_no_alert(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from alert_rules_engine import AlertRulesEngine, AlertRule, AlertSeverity, Comparator
        engine = AlertRulesEngine()
        engine.add_rule(AlertRule(
            "rule-test-success2", "Test SLO Breach2", AlertSeverity.WARNING,
            "success_rate", Comparator.LT, 0.95, 0.0
        ))
        t = OperationalSLOTracker(alert_rules_engine=engine)
        t.add_slo_target(SLOTarget("slo-ok", "success_rate", 0.95, 3600.0))
        # Record 10 successes → success_rate=1.0 >= 0.95
        for _ in range(10):
            t.record_execution(_make_record(success=True))
        compliance = t.check_slo_compliance()
        assert compliance["slo-ok"]["compliant"] is True
        assert t.get_fired_alerts() == []

    def test_get_fired_alerts_limit(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from alert_rules_engine import AlertRulesEngine, AlertRule, AlertSeverity, Comparator
        engine = AlertRulesEngine()
        engine.add_rule(AlertRule(
            "rule-limit", "Limit Test", AlertSeverity.WARNING,
            "success_rate", Comparator.LT, 0.99, 0.0
        ))
        t = OperationalSLOTracker(alert_rules_engine=engine)
        t.add_slo_target(SLOTarget("slo-limit", "success_rate", 0.99, 3600.0))
        for _ in range(3):
            t.record_execution(_make_record(success=False))
        t.check_slo_compliance()
        assert len(t.get_fired_alerts(limit=1)) == 1
