"""
Tests for delivery_channel_completeness module.

Covers all 5 capabilities:
  1. Delivery confirmation tracking
  2. Retry with exponential backoff
  3. Template rendering engine
  4. Delivery analytics
  5. Channel health monitor
"""

import sys
import os
import threading
import unittest

# Ensure the src package is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "src"),
)

from delivery_channel_completeness import (
    ChannelHealthMonitor,
    DeliveryAnalytics,
    DeliveryConfirmationTracker,
    RetryConfig,
    RetryManager,
    TemplateRenderingEngine,
    TrackingStatus,
)


# ===================================================================
# 1. Delivery Confirmation Tracking
# ===================================================================

class TestDeliveryConfirmationTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = DeliveryConfirmationTracker()

    def test_create_delivery(self):
        rec = self.tracker.create_delivery("email", "user@example.com")
        self.assertEqual(rec["status"], "queued")
        self.assertEqual(rec["channel"], "email")
        self.assertIn("delivery_id", rec)

    def test_update_status(self):
        rec = self.tracker.create_delivery("chat", "bob")
        updated = self.tracker.update_status(rec["delivery_id"], "sent")
        self.assertEqual(updated["status"], "sent")

    def test_update_status_full_lifecycle(self):
        rec = self.tracker.create_delivery("email", "a@b.com")
        did = rec["delivery_id"]
        for status in ("sent", "delivered", "read"):
            self.tracker.update_status(did, status)
        final = self.tracker.get_delivery(did)
        self.assertEqual(final["status"], "read")
        self.assertEqual(len(final["history"]), 4)

    def test_update_status_invalid(self):
        rec = self.tracker.create_delivery("email", "a@b.com")
        with self.assertRaises(ValueError):
            self.tracker.update_status(rec["delivery_id"], "invalid_state")

    def test_update_status_unknown_id(self):
        with self.assertRaises(KeyError):
            self.tracker.update_status("nonexistent", "sent")

    def test_increment_retry(self):
        rec = self.tracker.create_delivery("voice", "phone:123")
        did = rec["delivery_id"]
        self.tracker.increment_retry(did)
        self.tracker.increment_retry(did)
        updated = self.tracker.get_delivery(did)
        self.assertEqual(updated["retry_count"], 2)

    def test_get_confirmations_by_channel(self):
        self.tracker.create_delivery("email", "a@b.com")
        rec2 = self.tracker.create_delivery("email", "c@d.com")
        self.tracker.update_status(rec2["delivery_id"], "delivered")
        result = self.tracker.get_confirmations_by_channel("email")
        self.assertEqual(result["channel"], "email")
        self.assertIn("queued", result["confirmations"])

    def test_get_all_deliveries(self):
        self.tracker.create_delivery("email", "a@b.com")
        self.tracker.create_delivery("chat", "bob")
        all_d = self.tracker.get_all_deliveries()
        self.assertEqual(len(all_d), 2)

    def test_thread_safety(self):
        errors = []

        def _create(n):
            try:
                for _ in range(n):
                    self.tracker.create_delivery("email", "t@t.com")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_create, args=(20,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(self.tracker.get_all_deliveries()), 80)


# ===================================================================
# 2. Retry with Exponential Backoff
# ===================================================================

class TestRetryManager(unittest.TestCase):

    def test_default_config(self):
        mgr = RetryManager()
        cfg = mgr.get_config()
        self.assertEqual(cfg["max_retries"], 3)
        self.assertEqual(cfg["initial_delay"], 1.0)

    def test_compute_delay_increases(self):
        mgr = RetryManager(RetryConfig(jitter=False))
        d0 = mgr.compute_delay(0)
        d1 = mgr.compute_delay(1)
        d2 = mgr.compute_delay(2)
        self.assertLess(d0, d1)
        self.assertLess(d1, d2)

    def test_compute_delay_capped(self):
        mgr = RetryManager(RetryConfig(max_delay=5.0, jitter=False))
        d10 = mgr.compute_delay(10)
        self.assertLessEqual(d10, 5.0)

    def test_compute_delay_jitter(self):
        mgr = RetryManager(RetryConfig(jitter=True))
        delays = {mgr.compute_delay(1) for _ in range(20)}
        self.assertGreater(len(delays), 1, "Jitter should vary delays")

    def test_execute_success_first_try(self):
        mgr = RetryManager(RetryConfig(initial_delay=0.01, max_retries=2))
        result = mgr.execute_with_retry("d1", lambda: {"success": True})
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts"], 1)

    def test_execute_eventual_success(self):
        counter = {"n": 0}

        def flaky():
            counter["n"] += 1
            if counter["n"] < 3:
                raise RuntimeError("temporary error")
            return {"success": True}

        mgr = RetryManager(RetryConfig(initial_delay=0.01, max_retries=3, jitter=False))
        result = mgr.execute_with_retry("d2", flaky)
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts"], 3)

    def test_execute_all_fail(self):
        mgr = RetryManager(RetryConfig(initial_delay=0.01, max_retries=1, jitter=False))
        result = mgr.execute_with_retry(
            "d3", lambda: (_ for _ in ()).throw(RuntimeError("fail"))
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"], 2)

    def test_get_attempts(self):
        mgr = RetryManager(RetryConfig(initial_delay=0.01, max_retries=0))
        mgr.execute_with_retry("d4", lambda: {"success": True})
        info = mgr.get_attempts("d4")
        self.assertEqual(len(info["attempts"]), 1)


# ===================================================================
# 3. Template Rendering Engine
# ===================================================================

class TestTemplateRenderingEngine(unittest.TestCase):

    def setUp(self):
        self.engine = TemplateRenderingEngine()

    def test_variable_substitution(self):
        result = self.engine.render("Hello {{name}}!", {"name": "World"})
        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "Hello World!")

    def test_missing_variable_empty(self):
        result = self.engine.render("Hello {{missing}}!")
        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "Hello !")

    def test_conditional_true(self):
        tpl = "{% if show %}visible{% endif %}"
        result = self.engine.render(tpl, {"show": True})
        self.assertEqual(result["output"], "visible")

    def test_conditional_false(self):
        tpl = "{% if show %}visible{% endif %}"
        result = self.engine.render(tpl, {"show": False})
        self.assertEqual(result["output"], "")

    def test_iteration(self):
        tpl = "{% for item in items %}[{{item}}]{% endfor %}"
        result = self.engine.render(tpl, {"items": ["a", "b", "c"]})
        self.assertEqual(result["output"], "[a][b][c]")

    def test_partial_include(self):
        self.engine.register_partial("sig", "-- Murphy Bot")
        result = self.engine.render("Body. {% include sig %}")
        self.assertEqual(result["output"], "Body. -- Murphy Bot")

    def test_nested_vars_in_loop(self):
        tpl = "{% for u in users %}{{u}},{% endfor %}"
        result = self.engine.render(tpl, {"users": ["Alice", "Bob"]})
        self.assertEqual(result["output"], "Alice,Bob,")

    def test_get_stats(self):
        self.engine.render("hi", {})
        stats = self.engine.get_stats()
        self.assertEqual(stats["render_count"], 1)

    def test_dotted_variable(self):
        result = self.engine.render("{{user.name}}", {"user": {"name": "Ada"}})
        self.assertEqual(result["output"], "Ada")


# ===================================================================
# 4. Delivery Analytics
# ===================================================================

class TestDeliveryAnalytics(unittest.TestCase):

    def setUp(self):
        self.analytics = DeliveryAnalytics()

    def test_record_event(self):
        ev = self.analytics.record_event("email", True, 120.0)
        self.assertEqual(ev["channel"], "email")
        self.assertTrue(ev["success"])

    def test_delivery_rates(self):
        self.analytics.record_event("email", True, 100)
        self.analytics.record_event("email", True, 110)
        self.analytics.record_event("email", False, 0, failure_reason="timeout")
        rates = self.analytics.get_delivery_rates()
        email = rates["delivery_rates"]["email"]
        self.assertEqual(email["total"], 3)
        self.assertEqual(email["success"], 2)
        self.assertAlmostEqual(email["success_rate"], 0.6667, places=3)

    def test_latency_percentiles(self):
        for lat in range(1, 101):
            self.analytics.record_event("chat", True, float(lat))
        pct = self.analytics.get_latency_percentiles("chat")
        self.assertGreater(pct["percentiles"]["p50"], 0)
        self.assertGreater(pct["percentiles"]["p99"], pct["percentiles"]["p50"])
        self.assertEqual(pct["sample_count"], 100)

    def test_latency_percentiles_empty(self):
        pct = self.analytics.get_latency_percentiles("voice")
        self.assertEqual(pct["sample_count"], 0)

    def test_channel_performance(self):
        self.analytics.record_event("email", True, 50, cost=0.01)
        self.analytics.record_event("email", True, 60, cost=0.02)
        perf = self.analytics.get_channel_performance()
        self.assertIn("email", perf["channel_performance"])
        self.assertAlmostEqual(
            perf["channel_performance"]["email"]["avg_latency_ms"], 55.0
        )

    def test_failure_reasons(self):
        self.analytics.record_event("email", False, 0, failure_reason="timeout")
        self.analytics.record_event("email", False, 0, failure_reason="timeout")
        self.analytics.record_event("email", False, 0, failure_reason="bounce")
        reasons = self.analytics.get_failure_reasons("email")
        self.assertEqual(reasons["failure_reasons"]["timeout"], 2)
        self.assertEqual(reasons["failure_reasons"]["bounce"], 1)

    def test_cost_report(self):
        self.analytics.set_channel_cost("email", 0.01)
        self.analytics.record_event("email", True, 50, cost=0.01)
        self.analytics.record_event("email", True, 50, cost=0.01)
        report = self.analytics.get_cost_report()
        self.assertAlmostEqual(report["cost_report"]["email"]["total_cost"], 0.02)
        self.assertEqual(report["cost_report"]["email"]["configured_unit_cost"], 0.01)


# ===================================================================
# 5. Channel Health Monitor
# ===================================================================

class TestChannelHealthMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = ChannelHealthMonitor()

    def test_register_channel(self):
        result = self.monitor.register_channel("email", backup_channel="chat")
        self.assertTrue(result["registered"])
        self.assertEqual(result["backup"], "chat")

    def test_record_healthy_check(self):
        self.monitor.register_channel("email")
        status = self.monitor.record_health_check("email", True, 50.0)
        self.assertEqual(status["status"], "healthy")
        self.assertEqual(status["total_checks"], 1)

    def test_channel_degrades(self):
        self.monitor.register_channel("email")
        self.monitor.record_health_check("email", True, 50)
        self.monitor.record_health_check("email", False, 0, error="down")
        status = self.monitor.get_channel_status("email")
        self.assertEqual(status["status"], "degraded")

    def test_channel_unhealthy(self):
        self.monitor.register_channel("email")
        for _ in range(5):
            self.monitor.record_health_check("email", False, 0, error="down")
        status = self.monitor.get_channel_status("email")
        self.assertEqual(status["status"], "unhealthy")

    def test_failover_to_backup(self):
        self.monitor.register_channel("email", backup_channel="chat")
        self.monitor.register_channel("chat")
        for _ in range(5):
            self.monitor.record_health_check("email", False, 0, error="down")
        resolved = self.monitor.resolve_channel("email")
        self.assertTrue(resolved["failover"])
        self.assertEqual(resolved["resolved"], "chat")

    def test_no_failover_when_healthy(self):
        self.monitor.register_channel("email", backup_channel="chat")
        self.monitor.register_channel("chat")
        self.monitor.record_health_check("email", True, 30)
        resolved = self.monitor.resolve_channel("email")
        self.assertFalse(resolved["failover"])
        self.assertEqual(resolved["resolved"], "email")

    def test_get_all_channels_status(self):
        self.monitor.register_channel("email")
        self.monitor.register_channel("chat")
        all_s = self.monitor.get_all_channels_status()
        self.assertIn("email", all_s["channels"])
        self.assertIn("chat", all_s["channels"])

    def test_get_error_rates(self):
        self.monitor.register_channel("email")
        self.monitor.record_health_check("email", True, 50)
        self.monitor.record_health_check("email", False, 0)
        rates = self.monitor.get_error_rates()
        self.assertAlmostEqual(rates["error_rates"]["email"], 0.5)

    def test_health_history(self):
        self.monitor.register_channel("voice")
        for i in range(15):
            self.monitor.record_health_check("voice", True, float(i))
        hist = self.monitor.get_health_history("voice", limit=5)
        self.assertEqual(len(hist["history"]), 5)

    def test_unregistered_channel_check_raises(self):
        with self.assertRaises(KeyError):
            self.monitor.record_health_check("missing", True, 10)

    def test_resolve_unregistered_channel(self):
        resolved = self.monitor.resolve_channel("unknown")
        self.assertFalse(resolved["failover"])
        self.assertEqual(resolved["reason"], "unregistered")


if __name__ == "__main__":
    unittest.main()
