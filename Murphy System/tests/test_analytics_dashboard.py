"""Tests for analytics_dashboard module."""

import os
import threading
import time
import unittest

# Ensure src is importable

from analytics_dashboard import (
    AlertRulesEngine,
    AlertSeverity,
    AlertState,
    AnalyticsDashboard,
    BusinessIntelligence,
    ComplianceAnalytics,
    ComplianceRecord,
    DashboardWidget,
    ExecutionAnalytics,
    MetricType,
    PerformanceMetrics,
    PerformanceSample,
    RealTimeDashboard,
    TaskExecution,
    WidgetType,
)


# ---------------------------------------------------------------------------
# Execution Analytics Tests
# ---------------------------------------------------------------------------

class TestExecutionAnalytics(unittest.TestCase):

    def setUp(self):
        self.ea = ExecutionAnalytics()

    def test_record_execution_success(self):
        result = self.ea.record_execution("deploy", 100.0, 101.5, True)
        self.assertEqual(result["task_type"], "deploy")
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["latency"], 1.5)

    def test_record_execution_failure(self):
        result = self.ea.record_execution("build", 0, 1, False, error_message="fail")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_message"], "fail")

    def test_record_execution_invalid_times(self):
        with self.assertRaises(ValueError):
            self.ea.record_execution("x", 10, 5, True)

    def test_success_rate_overall(self):
        self.ea.record_execution("a", 0, 1, True)
        self.ea.record_execution("a", 0, 1, False)
        rate = self.ea.get_success_rate()
        self.assertAlmostEqual(rate["success_rate"], 0.5)
        self.assertEqual(rate["total"], 2)

    def test_success_rate_by_type(self):
        self.ea.record_execution("a", 0, 1, True)
        self.ea.record_execution("b", 0, 1, False)
        rate = self.ea.get_success_rate("a")
        self.assertAlmostEqual(rate["success_rate"], 1.0)

    def test_success_rate_empty(self):
        rate = self.ea.get_success_rate()
        self.assertEqual(rate["success_rate"], 0.0)

    def test_latency_distribution(self):
        for i in range(10):
            self.ea.record_execution("t", 0, float(i + 1), True)
        dist = self.ea.get_latency_distribution()
        self.assertEqual(dist["count"], 10)
        self.assertAlmostEqual(dist["min"], 1.0)
        self.assertAlmostEqual(dist["max"], 10.0)
        self.assertGreater(dist["p95"], 0)
        self.assertGreater(dist["p99"], 0)

    def test_latency_distribution_empty(self):
        dist = self.ea.get_latency_distribution()
        self.assertEqual(dist["count"], 0)
        self.assertEqual(dist["mean"], 0)

    def test_throughput(self):
        now = time.time()
        self.ea.record_execution("t", now - 1, now, True)
        tp = self.ea.get_throughput(window_seconds=10.0)
        self.assertEqual(tp["task_count"], 1)
        self.assertGreater(tp["throughput_per_second"], 0)

    def test_counts_by_type(self):
        self.ea.record_execution("a", 0, 1, True)
        self.ea.record_execution("a", 0, 1, False)
        self.ea.record_execution("b", 0, 1, True)
        counts = self.ea.get_counts_by_type()
        self.assertEqual(counts["counts"]["a"], 2)
        self.assertEqual(counts["counts"]["b"], 1)
        self.assertEqual(counts["total"], 3)

    def test_get_summary(self):
        self.ea.record_execution("x", 0, 1, True)
        summary = self.ea.get_summary()
        self.assertIn("counts", summary)
        self.assertIn("latency", summary)
        self.assertIn("throughput", summary)


# ---------------------------------------------------------------------------
# Compliance Analytics Tests
# ---------------------------------------------------------------------------

class TestComplianceAnalytics(unittest.TestCase):

    def setUp(self):
        self.ca = ComplianceAnalytics()

    def test_record_assessment(self):
        r = self.ca.record_assessment("gdpr", 85.0, violations=["v1"])
        self.assertEqual(r["category"], "gdpr")
        self.assertAlmostEqual(r["score"], 85.0)
        self.assertEqual(r["violations"], ["v1"])

    def test_score_out_of_range(self):
        with self.assertRaises(ValueError):
            self.ca.record_assessment("x", 150.0)
        with self.assertRaises(ValueError):
            self.ca.record_assessment("x", -1.0)

    def test_scores_over_time(self):
        self.ca.record_assessment("gdpr", 80.0)
        self.ca.record_assessment("gdpr", 90.0)
        data = self.ca.get_scores_over_time("gdpr")
        self.assertEqual(data["count"], 2)
        self.assertAlmostEqual(data["average_score"], 85.0)

    def test_violation_trends(self):
        self.ca.record_assessment("gdpr", 70.0, violations=["a", "b"])
        self.ca.record_assessment("hipaa", 60.0, violations=["c"])
        trends = self.ca.get_violation_trends()
        self.assertEqual(trends["total_violations"], 3)
        self.assertEqual(trends["by_category"]["gdpr"], 2)

    def test_remediation_effectiveness(self):
        self.ca.record_assessment("gdpr", 70, violations=["a"],
                                  remediated=True, remediation_time=30.0)
        self.ca.record_assessment("gdpr", 60, violations=["b"],
                                  remediated=False)
        eff = self.ca.get_remediation_effectiveness()
        self.assertEqual(eff["total_with_violations"], 2)
        self.assertEqual(eff["remediated_count"], 1)
        self.assertAlmostEqual(eff["remediation_rate"], 0.5)
        self.assertAlmostEqual(eff["avg_remediation_time"], 30.0)

    def test_remediation_effectiveness_empty(self):
        eff = self.ca.get_remediation_effectiveness()
        self.assertEqual(eff["remediation_rate"], 0.0)

    def test_compliance_summary(self):
        self.ca.record_assessment("x", 90.0)
        s = self.ca.get_summary()
        self.assertIn("scores", s)
        self.assertIn("violations", s)
        self.assertIn("remediation", s)


# ---------------------------------------------------------------------------
# Performance Metrics Tests
# ---------------------------------------------------------------------------

class TestPerformanceMetrics(unittest.TestCase):

    def setUp(self):
        self.pm = PerformanceMetrics(max_samples=50)

    def test_record_sample(self):
        r = self.pm.record_sample(55.0, 60.0, 120.5, 10)
        self.assertAlmostEqual(r["cpu_percent"], 55.0)
        self.assertEqual(r["queue_depth"], 10)

    def test_cpu_trends(self):
        self.pm.record_sample(10.0, 20.0, 50.0, 1)
        self.pm.record_sample(30.0, 40.0, 60.0, 2)
        t = self.pm.get_cpu_trends()
        self.assertEqual(t["count"], 2)
        self.assertAlmostEqual(t["min"], 10.0)
        self.assertAlmostEqual(t["max"], 30.0)

    def test_memory_trends(self):
        self.pm.record_sample(10.0, 50.0, 1.0, 0)
        t = self.pm.get_memory_trends()
        self.assertAlmostEqual(t["latest"], 50.0)

    def test_api_response_trends(self):
        self.pm.record_sample(10.0, 20.0, 200.0, 0)
        t = self.pm.get_api_response_trends()
        self.assertAlmostEqual(t["latest"], 200.0)

    def test_queue_depth_trends(self):
        self.pm.record_sample(10.0, 20.0, 50.0, 42)
        t = self.pm.get_queue_depth_trends()
        self.assertAlmostEqual(t["latest"], 42.0)

    def test_max_samples_eviction(self):
        for i in range(60):
            self.pm.record_sample(float(i), 0.0, 0.0, 0)
        s = self.pm.get_summary()
        self.assertEqual(s["total_samples"], 50)

    def test_empty_trends(self):
        t = self.pm.get_cpu_trends()
        self.assertEqual(t["count"], 0)

    def test_summary(self):
        self.pm.record_sample(10, 20, 30, 40)
        s = self.pm.get_summary()
        self.assertIn("cpu", s)
        self.assertIn("memory", s)
        self.assertIn("api_response", s)
        self.assertIn("queue_depth", s)


# ---------------------------------------------------------------------------
# Business Intelligence Tests
# ---------------------------------------------------------------------------

class TestBusinessIntelligence(unittest.TestCase):

    def setUp(self):
        self.bi = BusinessIntelligence()

    def test_record_task_cost(self):
        r = self.bi.record_task_cost("deploy", 5.0, 120.0)
        self.assertEqual(r["task_type"], "deploy")
        self.assertAlmostEqual(r["cost"], 5.0)

    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError):
            self.bi.record_task_cost("x", -1.0, 10.0)

    def test_cost_per_task(self):
        self.bi.record_task_cost("deploy", 5.0, 60)
        self.bi.record_task_cost("deploy", 7.0, 80)
        cpt = self.bi.get_cost_per_task("deploy")
        self.assertEqual(cpt["count"], 2)
        self.assertAlmostEqual(cpt["avg_cost"], 6.0)

    def test_cost_per_task_empty(self):
        cpt = self.bi.get_cost_per_task("nonexistent")
        self.assertEqual(cpt["count"], 0)

    def test_set_manual_baseline(self):
        r = self.bi.set_manual_baseline("deploy", 20.0)
        self.assertAlmostEqual(r["manual_cost_per_task"], 20.0)

    def test_roi_calculation(self):
        self.bi.set_manual_baseline("deploy", 20.0)
        self.bi.record_task_cost("deploy", 5.0, 60, automated=True)
        self.bi.record_task_cost("deploy", 5.0, 60, automated=True)
        roi = self.bi.get_roi("deploy")
        self.assertAlmostEqual(roi["savings_per_task"], 15.0)
        self.assertAlmostEqual(roi["total_savings"], 30.0)
        self.assertGreater(roi["roi_percent"], 0)

    def test_roi_no_baseline(self):
        self.bi.record_task_cost("deploy", 5.0, 60)
        roi = self.bi.get_roi("deploy")
        self.assertAlmostEqual(roi["roi_percent"], 0.0)
        self.assertFalse(roi["baseline_set"])

    def test_automation_savings(self):
        self.bi.set_manual_baseline("deploy", 20.0)
        self.bi.record_task_cost("deploy", 5.0, 60, automated=True)
        savings = self.bi.get_automation_savings()
        self.assertGreater(savings["total_savings"], 0)

    def test_productivity_gains(self):
        self.bi.record_task_cost("x", 5.0, 10.0, automated=True)
        self.bi.record_task_cost("x", 15.0, 100.0, automated=False)
        pg = self.bi.get_productivity_gains()
        self.assertGreater(pg["speedup_factor"], 1.0)
        self.assertGreater(pg["time_saved_per_task"], 0)

    def test_productivity_empty(self):
        pg = self.bi.get_productivity_gains()
        self.assertEqual(pg["speedup_factor"], 0.0)

    def test_business_summary(self):
        s = self.bi.get_summary()
        self.assertIn("cost_per_task", s)
        self.assertIn("automation_savings", s)
        self.assertIn("productivity", s)


# ---------------------------------------------------------------------------
# Real-time Dashboard Tests
# ---------------------------------------------------------------------------

class TestRealTimeDashboard(unittest.TestCase):

    def setUp(self):
        self.db = RealTimeDashboard()

    def test_add_widget(self):
        w = self.db.add_widget("Test", WidgetType.COUNTER, "src")
        self.assertEqual(w["title"], "Test")
        self.assertEqual(w["widget_type"], "counter")

    def test_remove_widget(self):
        w = self.db.add_widget("Test", WidgetType.COUNTER, "src")
        r = self.db.remove_widget(w["widget_id"])
        self.assertTrue(r["removed"])

    def test_remove_nonexistent_widget(self):
        r = self.db.remove_widget("fake-id")
        self.assertFalse(r["removed"])

    def test_register_data_provider(self):
        r = self.db.register_data_provider("src", lambda: {"value": 42})
        self.assertTrue(r["registered"])

    def test_dashboard_data_with_provider(self):
        w = self.db.add_widget("Count", WidgetType.COUNTER, "my_src")
        self.db.register_data_provider("my_src", lambda: {"v": 1})
        data = self.db.get_dashboard_data()
        self.assertEqual(data["widget_count"], 1)
        self.assertEqual(data["widgets"][0]["data"]["v"], 1)

    def test_create_layout(self):
        w1 = self.db.add_widget("A", WidgetType.COUNTER, "s")
        w2 = self.db.add_widget("B", WidgetType.TABLE, "s")
        layout = self.db.create_layout("main", [w1["widget_id"], w2["widget_id"]])
        self.assertTrue(layout["created"])
        self.assertEqual(layout["widget_count"], 2)

    def test_create_layout_unknown_widget(self):
        r = self.db.create_layout("bad", ["nonexistent"])
        self.assertFalse(r["created"])

    def test_dashboard_data_by_layout(self):
        w = self.db.add_widget("X", WidgetType.GAUGE, "s")
        self.db.create_layout("my_layout", [w["widget_id"]])
        data = self.db.get_dashboard_data("my_layout")
        self.assertEqual(data["layout"], "my_layout")
        self.assertEqual(data["widget_count"], 1)

    def test_list_widgets(self):
        self.db.add_widget("A", WidgetType.COUNTER, "s")
        listed = self.db.list_widgets()
        self.assertEqual(listed["count"], 1)

    def test_list_layouts(self):
        w = self.db.add_widget("A", WidgetType.COUNTER, "s")
        self.db.create_layout("L", [w["widget_id"]])
        listed = self.db.list_layouts()
        self.assertEqual(listed["count"], 1)
        self.assertIn("L", listed["layouts"])


# ---------------------------------------------------------------------------
# Alert Rules Engine Tests
# ---------------------------------------------------------------------------

class TestAlertRulesEngine(unittest.TestCase):

    def setUp(self):
        self.engine = AlertRulesEngine()

    def test_add_rule(self):
        r = self.engine.add_rule("High CPU", "cpu", "gt", 90.0,
                                 severity=AlertSeverity.CRITICAL)
        self.assertEqual(r["name"], "High CPU")
        self.assertEqual(r["condition"], "gt")
        self.assertEqual(r["severity"], "critical")

    def test_add_rule_invalid_condition(self):
        with self.assertRaises(ValueError):
            self.engine.add_rule("X", "m", "invalid", 1.0)

    def test_remove_rule(self):
        r = self.engine.add_rule("X", "m", "gt", 1.0)
        removed = self.engine.remove_rule(r["rule_id"])
        self.assertTrue(removed["removed"])

    def test_remove_nonexistent_rule(self):
        r = self.engine.remove_rule("fake")
        self.assertFalse(r["removed"])

    def test_alert_fires_on_breach(self):
        self.engine.add_rule("High CPU", "cpu", "gt", 90.0,
                             cooldown_seconds=0)
        result = self.engine.update_metric("cpu", 95.0)
        self.assertEqual(len(result["fired"]), 1)
        self.assertEqual(result["fired"][0]["event"], "alert_fired")

    def test_alert_does_not_fire_when_ok(self):
        self.engine.add_rule("High CPU", "cpu", "gt", 90.0)
        result = self.engine.update_metric("cpu", 50.0)
        self.assertEqual(len(result["fired"]), 0)

    def test_alert_resolves(self):
        self.engine.add_rule("High CPU", "cpu", "gt", 90.0,
                             cooldown_seconds=0)
        self.engine.update_metric("cpu", 95.0)
        result = self.engine.update_metric("cpu", 50.0)
        self.assertEqual(len(result["resolved"]), 1)
        self.assertEqual(result["resolved"][0]["event"], "alert_resolved")

    def test_cooldown_prevents_refire(self):
        self.engine.add_rule("X", "m", "gt", 5.0, cooldown_seconds=9999)
        self.engine.update_metric("m", 10.0)  # fires
        self.engine.update_metric("m", 3.0)   # resolves
        result = self.engine.update_metric("m", 10.0)  # should not re-fire (cooldown)
        self.assertEqual(len(result["fired"]), 0)

    def test_notification_callback(self):
        received = []
        self.engine.register_notification_callback(lambda a: received.append(a))
        self.engine.add_rule("X", "m", "gt", 5.0, cooldown_seconds=0)
        self.engine.update_metric("m", 10.0)
        self.assertEqual(len(received), 1)

    def test_get_active_alerts(self):
        self.engine.add_rule("X", "m", "gt", 5.0, cooldown_seconds=0)
        self.engine.update_metric("m", 10.0)
        active = self.engine.get_active_alerts()
        self.assertEqual(active["count"], 1)

    def test_get_alert_history(self):
        self.engine.add_rule("X", "m", "gt", 5.0, cooldown_seconds=0)
        self.engine.update_metric("m", 10.0)
        history = self.engine.get_alert_history()
        self.assertGreaterEqual(history["count"], 1)

    def test_get_rules(self):
        self.engine.add_rule("A", "m", "gt", 1.0)
        self.engine.add_rule("B", "m", "lt", 0.5)
        rules = self.engine.get_rules()
        self.assertEqual(rules["count"], 2)

    def test_get_metric_values(self):
        self.engine.update_metric("cpu", 42.0)
        mv = self.engine.get_metric_values()
        self.assertAlmostEqual(mv["metrics"]["cpu"], 42.0)

    def test_lt_condition(self):
        self.engine.add_rule("Low disk", "disk", "lt", 10.0,
                             cooldown_seconds=0)
        result = self.engine.update_metric("disk", 5.0)
        self.assertEqual(len(result["fired"]), 1)


# ---------------------------------------------------------------------------
# Unified Analytics Dashboard Tests
# ---------------------------------------------------------------------------

class TestAnalyticsDashboard(unittest.TestCase):

    def setUp(self):
        self.ad = AnalyticsDashboard()

    def test_full_report(self):
        report = self.ad.get_full_report()
        self.assertIn("execution", report)
        self.assertIn("compliance", report)
        self.assertIn("performance", report)
        self.assertIn("business", report)
        self.assertIn("alerts", report)
        self.assertIn("generated_at", report)

    def test_setup_default_dashboard(self):
        result = self.ad.setup_default_dashboard()
        self.assertEqual(result["widgets_created"], 5)
        self.assertTrue(result["layout"]["created"])

    def test_end_to_end_flow(self):
        self.ad.execution.record_execution("deploy", 0, 1, True)
        self.ad.compliance.record_assessment("gdpr", 95.0)
        self.ad.performance.record_sample(30.0, 40.0, 100.0, 5)
        self.ad.business.record_task_cost("deploy", 5.0, 60)
        self.ad.alerts.add_rule("High CPU", "cpu", "gt", 90.0, cooldown_seconds=0)
        self.ad.alerts.update_metric("cpu", 95.0)
        report = self.ad.get_full_report()
        self.assertEqual(report["execution"]["counts"]["total"], 1)
        self.assertEqual(report["alerts"]["count"], 1)


# ---------------------------------------------------------------------------
# Thread-safety Test
# ---------------------------------------------------------------------------

class TestThreadSafety(unittest.TestCase):

    def test_concurrent_execution_recording(self):
        ea = ExecutionAnalytics()
        errors = []

        def worker(n):
            try:
                for i in range(50):
                    ea.record_execution(f"type_{n}", 0, float(i + 1), i % 2 == 0)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        counts = ea.get_counts_by_type()
        self.assertEqual(counts["total"], 200)


if __name__ == "__main__":
    unittest.main()
