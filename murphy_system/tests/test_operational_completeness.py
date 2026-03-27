"""Tests for the operational_completeness module."""

import os
import unittest
import threading

# Ensure the src package is importable

from operational_completeness import (
    CapacityPlanner,
    ResourceManager,
    AutomatedScheduler,
    HealthMonitor,
    RunbookExecutor,
    ComponentStatus,
    RunbookStatus,
    ResourceType,
    _linear_regression,
)


# -----------------------------------------------------------------------
# Capacity Planner Tests
# -----------------------------------------------------------------------

class TestCapacityPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = CapacityPlanner()

    def test_record_usage(self):
        result = self.planner.record_usage("cpu", 0.75)
        self.assertEqual(result["resource_type"], "cpu")
        self.assertEqual(result["value"], 0.75)
        self.assertIn("timestamp", result)

    def test_get_usage_history_empty(self):
        result = self.planner.get_usage_history("cpu")
        self.assertEqual(result["sample_count"], 0)
        self.assertEqual(result["values"], [])

    def test_get_usage_history_with_data(self):
        self.planner.record_usage("cpu", 0.5)
        self.planner.record_usage("cpu", 0.6)
        result = self.planner.get_usage_history("cpu")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["values"], [0.5, 0.6])

    def test_forecast_insufficient_data(self):
        self.planner.record_usage("cpu", 0.5)
        result = self.planner.forecast("cpu")
        self.assertEqual(result["error"], "insufficient_data")

    def test_forecast_with_data(self):
        for v in [10, 20, 30, 40]:
            self.planner.record_usage("mem", v)
        result = self.planner.forecast("mem", periods_ahead=2)
        self.assertEqual(len(result["forecasted_values"]), 2)
        self.assertGreater(result["forecasted_values"][0], 40)

    def test_recommend_scaling_up(self):
        for v in [80, 85, 90, 95]:
            self.planner.record_usage("cpu", v)
        result = self.planner.recommend_scaling("cpu", current_capacity=100)
        self.assertEqual(result["recommendation"], "scale_up")

    def test_recommend_scaling_down(self):
        for v in [10, 8, 6, 5]:
            self.planner.record_usage("cpu", v)
        result = self.planner.recommend_scaling("cpu", current_capacity=100)
        self.assertEqual(result["recommendation"], "scale_down")

    def test_recommend_hold_insufficient_data(self):
        result = self.planner.recommend_scaling("cpu", current_capacity=100)
        self.assertEqual(result["recommendation"], "hold")
        self.assertEqual(result["reason"], "insufficient_data")


# -----------------------------------------------------------------------
# Resource Manager Tests
# -----------------------------------------------------------------------

class TestResourceManager(unittest.TestCase):

    def setUp(self):
        self.mgr = ResourceManager()

    def test_register_pool(self):
        result = self.mgr.register_pool("cpu", 100, unit="cores")
        self.assertEqual(result["resource_type"], "cpu")
        self.assertEqual(result["total_capacity"], 100)

    def test_get_pool_status(self):
        self.mgr.register_pool("cpu", 100)
        status = self.mgr.get_pool_status("cpu")
        self.assertEqual(status["available"], 100)
        self.assertEqual(status["utilisation"], 0.0)

    def test_get_pool_status_not_found(self):
        result = self.mgr.get_pool_status("gpu")
        self.assertIn("error", result)

    def test_allocate_success(self):
        self.mgr.register_pool("cpu", 100)
        result = self.mgr.allocate("cpu", 30, requester="svc-a")
        self.assertTrue(result["success"])
        self.assertIn("allocation_id", result)

    def test_allocate_insufficient_capacity(self):
        self.mgr.register_pool("cpu", 10)
        result = self.mgr.allocate("cpu", 20)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "insufficient_capacity")

    def test_allocate_pool_not_found(self):
        result = self.mgr.allocate("gpu", 10)
        self.assertFalse(result["success"])

    def test_release_allocation(self):
        self.mgr.register_pool("mem", 64)
        alloc = self.mgr.allocate("mem", 32)
        release = self.mgr.release(alloc["allocation_id"])
        self.assertTrue(release["success"])
        status = self.mgr.get_pool_status("mem")
        self.assertEqual(status["available"], 64)

    def test_release_not_found(self):
        result = self.mgr.release("nonexistent")
        self.assertFalse(result["success"])

    def test_list_allocations(self):
        self.mgr.register_pool("cpu", 100)
        self.mgr.allocate("cpu", 10)
        self.mgr.allocate("cpu", 20)
        result = self.mgr.list_allocations()
        self.assertEqual(result["count"], 2)

    def test_list_allocations_filtered(self):
        self.mgr.register_pool("cpu", 100)
        self.mgr.register_pool("mem", 100)
        self.mgr.allocate("cpu", 10)
        self.mgr.allocate("mem", 20)
        result = self.mgr.list_allocations(resource_type="cpu")
        self.assertEqual(result["count"], 1)


# -----------------------------------------------------------------------
# Automated Scheduler Tests
# -----------------------------------------------------------------------

class TestAutomatedScheduler(unittest.TestCase):

    def setUp(self):
        self.sched = AutomatedScheduler()

    def test_register_job(self):
        result = self.sched.register_job("backup", "0 2 * * *")
        self.assertIn("job_id", result)
        self.assertEqual(result["name"], "backup")

    def test_disable_enable_job(self):
        job = self.sched.register_job("test", "* * * * *")
        self.assertTrue(self.sched.disable_job(job["job_id"])["success"])
        self.assertTrue(self.sched.enable_job(job["job_id"])["success"])

    def test_disable_job_not_found(self):
        result = self.sched.disable_job("nope")
        self.assertFalse(result["success"])

    def test_enable_job_not_found(self):
        result = self.sched.enable_job("nope")
        self.assertFalse(result["success"])

    def test_add_maintenance_window(self):
        result = self.sched.add_maintenance_window(
            "deploy", "2025-01-01T00:00:00Z", "2025-01-01T04:00:00Z")
        self.assertIn("window_id", result)

    def test_is_in_blackout_true(self):
        self.sched.add_maintenance_window(
            "mw", "2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z")
        result = self.sched.is_in_blackout("2025-06-15T12:00:00Z")
        self.assertTrue(result["in_blackout"])

    def test_is_in_blackout_false(self):
        self.sched.add_maintenance_window(
            "mw", "2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z")
        result = self.sched.is_in_blackout("2025-06-15T12:00:00Z")
        self.assertFalse(result["in_blackout"])

    def test_can_execute_disabled(self):
        job = self.sched.register_job("j", "* * * * *")
        self.sched.disable_job(job["job_id"])
        result = self.sched.can_execute(job["job_id"])
        self.assertFalse(result["can_execute"])
        self.assertEqual(result["reason"], "job_disabled")

    def test_can_execute_dependency_not_met(self):
        dep = self.sched.register_job("dep", "* * * * *")
        job = self.sched.register_job("j", "* * * * *",
                                      depends_on=[dep["job_id"]])
        result = self.sched.can_execute(job["job_id"])
        self.assertFalse(result["can_execute"])
        self.assertEqual(result["reason"], "dependency_not_met")

    def test_can_execute_success(self):
        dep = self.sched.register_job("dep", "* * * * *")
        self.sched.record_execution(dep["job_id"], True)
        job = self.sched.register_job("j", "* * * * *",
                                      depends_on=[dep["job_id"]])
        result = self.sched.can_execute(job["job_id"])
        self.assertTrue(result["can_execute"])

    def test_record_execution(self):
        job = self.sched.register_job("j", "* * * * *")
        result = self.sched.record_execution(job["job_id"], True)
        self.assertTrue(result["success"])

    def test_get_schedule_status(self):
        self.sched.register_job("a", "* * * * *")
        self.sched.add_maintenance_window(
            "mw", "2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z")
        status = self.sched.get_schedule_status()
        self.assertEqual(status["total_jobs"], 1)
        self.assertEqual(status["total_windows"], 1)


# -----------------------------------------------------------------------
# Health Monitor Tests
# -----------------------------------------------------------------------

class TestHealthMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = HealthMonitor()

    def test_register_component(self):
        result = self.monitor.register_component("api")
        self.assertEqual(result["status"], ComponentStatus.UNKNOWN)

    def test_update_status_healthy(self):
        self.monitor.register_component("api")
        result = self.monitor.update_status("api", ComponentStatus.HEALTHY)
        self.assertTrue(result["success"])

    def test_update_status_not_registered(self):
        result = self.monitor.update_status("ghost", ComponentStatus.HEALTHY)
        self.assertFalse(result["success"])

    def test_anomaly_detection(self):
        self.monitor.register_component("db")
        self.monitor.update_status("db", ComponentStatus.UNHEALTHY, "timeout")
        anomalies = self.monitor.get_anomalies()
        self.assertEqual(anomalies["count"], 1)

    def test_auto_healing_trigger(self):
        self.monitor.register_component("cache")
        self.monitor.register_healing_rule(
            "cache", "restart",
            trigger_statuses=[ComponentStatus.UNHEALTHY])
        result = self.monitor.update_status(
            "cache", ComponentStatus.UNHEALTHY, "OOM")
        self.assertTrue(result.get("auto_heal_triggered"))
        history = self.monitor.get_healing_history()
        self.assertEqual(history["count"], 1)

    def test_get_component_status(self):
        self.monitor.register_component("web")
        self.monitor.update_status("web", ComponentStatus.HEALTHY)
        result = self.monitor.get_component_status("web")
        self.assertEqual(result["status"], ComponentStatus.HEALTHY)

    def test_get_component_status_not_registered(self):
        result = self.monitor.get_component_status("x")
        self.assertIn("error", result)

    def test_system_health_all_healthy(self):
        self.monitor.register_component("a")
        self.monitor.register_component("b")
        self.monitor.update_status("a", ComponentStatus.HEALTHY)
        self.monitor.update_status("b", ComponentStatus.HEALTHY)
        result = self.monitor.get_system_health()
        self.assertEqual(result["overall_status"], ComponentStatus.HEALTHY)

    def test_system_health_degraded(self):
        self.monitor.register_component("a")
        self.monitor.update_status("a", ComponentStatus.DEGRADED)
        result = self.monitor.get_system_health()
        self.assertEqual(result["overall_status"], ComponentStatus.DEGRADED)

    def test_system_health_empty(self):
        result = self.monitor.get_system_health()
        self.assertEqual(result["overall_status"], ComponentStatus.UNKNOWN)


# -----------------------------------------------------------------------
# Runbook Executor Tests
# -----------------------------------------------------------------------

class TestRunbookExecutor(unittest.TestCase):

    def setUp(self):
        self.executor = RunbookExecutor()

    def test_create_runbook(self):
        result = self.executor.create_runbook(
            "deploy", [{"action": "backup"}, {"action": "restart"}])
        self.assertIn("runbook_id", result)
        self.assertEqual(result["total_steps"], 2)

    def test_execute_runbook_success(self):
        rb = self.executor.create_runbook(
            "ops", [{"action": "restart"}, {"action": "health_check"}])
        result = self.executor.execute_runbook(rb["runbook_id"])
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], RunbookStatus.COMPLETED)

    def test_execute_runbook_with_unsupported_action(self):
        rb = self.executor.create_runbook(
            "bad", [{"action": "fly_to_moon"}])
        result = self.executor.execute_runbook(rb["runbook_id"])
        self.assertFalse(result["success"])

    def test_execute_runbook_not_found(self):
        result = self.executor.execute_runbook("nope")
        self.assertFalse(result["success"])

    def test_register_template(self):
        result = self.executor.register_template(
            "standard_deploy", [{"action": "backup"}, {"action": "restart"}])
        self.assertIn("template_id", result)

    def test_create_from_template(self):
        tmpl = self.executor.register_template(
            "tmpl", [{"action": "scale"}])
        result = self.executor.create_from_template(tmpl["template_id"])
        self.assertIn("runbook_id", result)

    def test_create_from_template_not_found(self):
        result = self.executor.create_from_template("nope")
        self.assertFalse(result["success"])

    def test_get_runbook_status(self):
        rb = self.executor.create_runbook("x", [{"action": "notify"}])
        result = self.executor.get_runbook_status(rb["runbook_id"])
        self.assertEqual(result["status"], RunbookStatus.PENDING)

    def test_get_runbook_status_not_found(self):
        result = self.executor.get_runbook_status("nope")
        self.assertIn("error", result)

    def test_list_runbooks(self):
        self.executor.create_runbook("a", [{"action": "restart"}])
        self.executor.create_runbook("b", [{"action": "backup"}])
        result = self.executor.list_runbooks()
        self.assertEqual(result["count"], 2)

    def test_list_templates(self):
        self.executor.register_template("t1", [{"action": "scale"}])
        result = self.executor.list_templates()
        self.assertEqual(result["count"], 1)


# -----------------------------------------------------------------------
# Helper Tests
# -----------------------------------------------------------------------

class TestHelpers(unittest.TestCase):

    def test_linear_regression_flat(self):
        slope, intercept = _linear_regression([5, 5, 5, 5])
        self.assertAlmostEqual(slope, 0.0)
        self.assertAlmostEqual(intercept, 5.0)

    def test_linear_regression_ascending(self):
        slope, intercept = _linear_regression([0, 1, 2, 3])
        self.assertAlmostEqual(slope, 1.0)
        self.assertAlmostEqual(intercept, 0.0)


# -----------------------------------------------------------------------
# Thread-Safety Tests
# -----------------------------------------------------------------------

class TestThreadSafety(unittest.TestCase):

    def test_concurrent_capacity_recording(self):
        planner = CapacityPlanner()
        errors = []

        def record(tid):
            try:
                for i in range(50):
                    planner.record_usage("cpu", float(i + tid))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)
        history = planner.get_usage_history("cpu")
        self.assertEqual(history["sample_count"], 200)

    def test_concurrent_resource_allocation(self):
        mgr = ResourceManager()
        mgr.register_pool("cpu", 1000)
        results = []

        def allocate(tid):
            for _ in range(10):
                r = mgr.allocate("cpu", 1, requester=f"t-{tid}")
                results.append(r["success"])

        threads = [threading.Thread(target=allocate, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 40)
        self.assertTrue(all(results))


if __name__ == "__main__":
    unittest.main()
