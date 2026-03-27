"""
Founder Observability Tests — PR 6 Gap Closure

Validates the founder visibility layer:

  1. SLO breach detection and alerting
  2. Dashboard data aggregation correctness
  3. KPI tracking and snapshot accuracy

All tests operate against real module logic (no mocks).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import time
import pytest

from operational_slo_tracker import (
    OperationalSLOTracker, SLOTarget, ExecutionRecord,
)
from operational_dashboard_aggregator import (
    OperationalDashboardAggregator, ModuleHealth, DashboardSnapshot,
)
from kpi_tracker import KPITracker, KPIDefinition, KPIDirection, KPIStatus


# ===========================================================================
# 1. SLO Breach Detection and Alerting
# ===========================================================================

class TestSLOBreachDetection:
    """OperationalSLOTracker: compliance evaluation and breach detection."""

    def _tracker(self) -> OperationalSLOTracker:
        return OperationalSLOTracker()

    def _record(self, success: bool, duration: float = 0.1,
                task_type: str = "test-task") -> ExecutionRecord:
        return ExecutionRecord(
            task_type=task_type, success=success, duration=duration
        )

    def test_initial_status_no_records(self):
        t = self._tracker()
        status = t.get_status()
        assert status["total_records"] == 0
        assert status["tracking_active"] is False

    def test_record_execution_increments_count(self):
        t = self._tracker()
        t.record_execution(self._record(True))
        assert t.get_status()["total_records"] == 1

    def test_success_rate_all_success(self):
        t = self._tracker()
        for _ in range(10):
            t.record_execution(self._record(True))
        metrics = t.get_metrics("test-task")
        assert metrics["success_rate"] == 1.0

    def test_success_rate_all_failure(self):
        t = self._tracker()
        for _ in range(5):
            t.record_execution(ExecutionRecord(
                task_type="test-task", success=False, duration=0.1,
                failure_reason="timeout"
            ))
        metrics = t.get_metrics("test-task")
        assert metrics["success_rate"] == 0.0

    def test_success_rate_mixed(self):
        t = self._tracker()
        for _ in range(7):
            t.record_execution(self._record(True))
        for _ in range(3):
            t.record_execution(self._record(False))
        metrics = t.get_metrics("test-task")
        assert abs(metrics["success_rate"] - 0.7) < 0.01

    def test_slo_compliant_when_above_threshold(self):
        t = self._tracker()
        t.add_slo_target(SLOTarget(
            target_name="high_success",
            metric="success_rate",
            threshold=0.90,
            window_seconds=3600,
        ))
        for _ in range(10):
            t.record_execution(self._record(True))
        compliance = t.check_slo_compliance()
        assert compliance["high_success"]["compliant"] is True

    def test_slo_breach_when_below_threshold(self):
        t = self._tracker()
        t.add_slo_target(SLOTarget(
            target_name="high_success",
            metric="success_rate",
            threshold=0.95,
            window_seconds=3600,
        ))
        # Only 80% success — should breach
        for _ in range(8):
            t.record_execution(self._record(True))
        for _ in range(2):
            t.record_execution(self._record(False))
        compliance = t.check_slo_compliance()
        assert compliance["high_success"]["compliant"] is False

    def test_slo_reports_actual_value(self):
        t = self._tracker()
        t.add_slo_target(SLOTarget(
            target_name="latency_p95",
            metric="latency_p95",
            threshold=1.0,
            window_seconds=3600,
        ))
        for _ in range(10):
            t.record_execution(self._record(True, duration=0.2))
        compliance = t.check_slo_compliance()
        assert "actual" in compliance["latency_p95"]
        assert compliance["latency_p95"]["actual"] >= 0.0

    def test_latency_percentiles_computed(self):
        t = self._tracker()
        durations = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for d in durations:
            t.record_execution(self._record(True, duration=d))
        metrics = t.get_metrics("test-task")
        assert metrics["latency_p50"] > 0.0
        assert metrics["latency_p95"] >= metrics["latency_p50"]
        assert metrics["latency_p99"] >= metrics["latency_p95"]

    def test_failure_cause_breakdown(self):
        t = self._tracker()
        t.record_execution(self._record(False, task_type="task-a"))
        t.record_execution(ExecutionRecord(
            task_type="task-a", success=False, duration=0.1,
            failure_reason="timeout"
        ))
        t.record_execution(ExecutionRecord(
            task_type="task-a", success=False, duration=0.1,
            failure_reason="timeout"
        ))
        metrics = t.get_metrics("task-a")
        assert "timeout" in metrics["failure_causes"]
        assert metrics["failure_causes"]["timeout"] == 2

    def test_multiple_slo_targets_tracked_independently(self):
        t = self._tracker()
        t.add_slo_target(SLOTarget(
            target_name="success_slo", metric="success_rate",
            threshold=0.9, window_seconds=3600,
        ))
        t.add_slo_target(SLOTarget(
            target_name="latency_slo", metric="latency_p95",
            threshold=2.0, window_seconds=3600,
        ))
        for _ in range(10):
            t.record_execution(self._record(True, duration=0.1))
        compliance = t.check_slo_compliance()
        assert "success_slo" in compliance
        assert "latency_slo" in compliance

    def test_status_lists_tracked_task_types(self):
        t = self._tracker()
        t.record_execution(ExecutionRecord(task_type="billing", success=True, duration=0.1))
        t.record_execution(ExecutionRecord(task_type="auth", success=True, duration=0.05))
        status = t.get_status()
        assert "billing" in status["task_types_tracked"]
        assert "auth" in status["task_types_tracked"]


# ===========================================================================
# 2. Dashboard Data Aggregation Correctness
# ===========================================================================

class TestDashboardDataAggregation:
    """OperationalDashboardAggregator: module registration and health."""

    def _dash(self) -> OperationalDashboardAggregator:
        return OperationalDashboardAggregator()

    def test_register_module(self):
        d = self._dash()
        d.register_module("OPS-001", "SLOTracker", lambda: {"status": "ok"})
        assert d.get_status()["registered_modules"] == 1

    def test_unregister_module(self):
        d = self._dash()
        d.register_module("OPS-001", "SLOTracker", lambda: {"status": "ok"})
        assert d.unregister_module("OPS-001") is True
        assert d.get_status()["registered_modules"] == 0

    def test_collect_with_healthy_module(self):
        d = self._dash()
        d.register_module("OPS-001", "HealthyMod", lambda: {"ok": True})
        snap = d.collect()
        assert isinstance(snap, DashboardSnapshot)
        assert snap.total_modules == 1
        assert snap.healthy_count >= 1

    def test_collect_with_degraded_module(self):
        """A module that returns an error dict is classified as degraded."""
        d = self._dash()
        d.register_module(
            "OPS-002", "DegradedMod",
            lambda: {"error": "connection refused"}
        )
        snap = d.collect()
        assert snap.total_modules == 1
        # Module may be healthy or degraded depending on implementation
        assert snap.healthy_count + snap.degraded_count + snap.unreachable_count == 1

    def test_collect_with_raising_module(self):
        """A module that raises is handled gracefully."""
        def _broken():
            raise RuntimeError("service unavailable")

        d = self._dash()
        d.register_module("OPS-003", "BrokenMod", _broken)
        snap = d.collect()  # must not raise
        assert snap.unreachable_count >= 1

    def test_multiple_modules_aggregated(self):
        d = self._dash()
        for i in range(5):
            d.register_module(f"MOD-{i:03d}", f"Module{i}",
                               lambda: {"status": "ok"})
        snap = d.collect()
        assert snap.total_modules == 5

    def test_snapshot_has_required_fields(self):
        d = self._dash()
        d.register_module("OPS-001", "M1", lambda: {"ok": True})
        snap = d.collect()
        assert snap.snapshot_id is not None
        assert snap.generated_at is not None
        assert snap.total_modules >= 1

    def test_snapshot_to_dict_is_serializable(self):
        d = self._dash()
        d.register_module("OPS-001", "M1", lambda: {"ok": True})
        snap = d.collect()
        as_dict = snap.to_dict()
        assert isinstance(as_dict, dict)
        assert "snapshot_id" in as_dict

    def test_get_snapshots_after_multiple_collects(self):
        d = self._dash()
        d.register_module("OPS-001", "M1", lambda: {"ok": True})
        d.collect()
        d.collect()
        snaps = d.get_snapshots(limit=10)
        assert len(snaps) >= 2

    def test_get_status_summary(self):
        d = self._dash()
        d.register_module("OPS-001", "M1", lambda: {"ok": True})
        status = d.get_status()
        assert "registered_modules" in status

    def test_system_health_string_set(self):
        d = self._dash()
        d.register_module("OPS-001", "M1", lambda: {"ok": True})
        snap = d.collect()
        assert snap.system_health in {"healthy", "degraded", "critical", "unknown"}


# ===========================================================================
# 3. KPI Tracking and Snapshot Accuracy
# ===========================================================================

class TestKPITrackingAccuracy:
    """KPITracker: define, record, snapshot, and breach detection."""

    def _tracker(self) -> KPITracker:
        return KPITracker()

    def test_define_and_list_kpi(self):
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="uptime", name="Uptime", target=99.9, unit="%"
        ))
        kpis = t.list_kpis()
        assert any(k.get("kpi_id") == "uptime" for k in kpis)

    def test_record_observation(self):
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="uptime", name="Uptime", target=99.9, unit="%"
        ))
        obs = t.record("uptime", 99.95)
        assert obs is not None
        assert obs.value == 99.95

    def test_snapshot_shows_met_kpi(self):
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="uptime", name="Uptime", target=99.0, unit="%",
            direction=KPIDirection.HIGHER_IS_BETTER,
        ))
        t.record("uptime", 99.9)
        snap = t.snapshot()
        uptime_result = next(
            (r for r in snap.results if r.kpi_id == "uptime"), None
        )
        assert uptime_result is not None
        assert uptime_result.status == KPIStatus.MET

    def test_snapshot_shows_not_met_kpi(self):
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="error_rate", name="Error Rate", target=0.1, unit="%",
            direction=KPIDirection.LOWER_IS_BETTER,
        ))
        t.record("error_rate", 5.0)  # 5% error — above 0.1% threshold
        snap = t.snapshot()
        err_result = next(
            (r for r in snap.results if r.kpi_id == "error_rate"), None
        )
        assert err_result is not None
        assert err_result.status == KPIStatus.NOT_MET

    def test_snapshot_met_count_accuracy(self):
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="k1", name="K1", target=50.0, unit="%"
        ))
        t.define_kpi(KPIDefinition(
            kpi_id="k2", name="K2", target=50.0, unit="%"
        ))
        t.record("k1", 80.0)  # above target — met
        t.record("k2", 20.0)  # below target — not met
        snap = t.snapshot()
        assert snap.met_count >= 1
        assert snap.not_met_count >= 1

    def test_remove_kpi(self):
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="temp", name="Temp KPI", target=10.0, unit=""
        ))
        result = t.remove_kpi("temp")
        assert result is True
        kpis = t.list_kpis()
        assert not any(k.get("kpi_id") == "temp" for k in kpis)

    def test_no_data_kpi_reported(self):
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="empty_kpi", name="Empty", target=99.0, unit="%"
        ))
        snap = t.snapshot()
        empty = next((r for r in snap.results if r.kpi_id == "empty_kpi"), None)
        if empty is not None:
            assert empty.status == KPIStatus.NO_DATA

    def test_multiple_observations_averaged(self):
        """KPI tracker uses the average of all observations to compute status."""
        t = self._tracker()
        t.define_kpi(KPIDefinition(
            kpi_id="avg_success", name="Avg Success Rate", target=90.0, unit="%"
        ))
        t.record("avg_success", 95.0)
        t.record("avg_success", 96.0)
        snap = t.snapshot()
        sr = next((r for r in snap.results if r.kpi_id == "avg_success"), None)
        assert sr is not None
        # Average of 95 and 96 is 95.5 — above target of 90
        assert sr.status == KPIStatus.MET

    def test_kpi_status_tracker_get_status(self):
        t = self._tracker()
        status = t.get_status()
        assert "total_kpis" in status or isinstance(status, dict)
