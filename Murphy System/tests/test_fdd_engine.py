# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for Murphy FDD Engine (Layer 5) — fault injection per rule."""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fdd.rule_engine import (
    RuleBasedFDD,
    FaultSeverity,
    FaultStatus,
    FaultRule,
    Fault,
    BUILTIN_RULES,
)
from fdd.statistical_fdd import CUSUMDetector, RegressionBaseline
from fdd.alarm_manager import AlarmManager, AlarmPriority


# ── Rule-based FDD tests ─────────────────────────────────────────

class TestRuleBasedFDD(unittest.TestCase):

    def setUp(self):
        self.fdd = RuleBasedFDD()

    def test_builtin_rules_loaded(self):
        rules = self.fdd.list_rules()
        self.assertGreaterEqual(len(rules), 5)

    def test_simultaneous_heat_cool_detected(self):
        faults = self.fdd.evaluate("AHU-1", {
            "heating_active": True, "cooling_active": True,
        })
        self.assertTrue(any(f.rule_id == "FDD-AHU-001" for f in faults))

    def test_simultaneous_heat_cool_not_triggered(self):
        faults = self.fdd.evaluate("AHU-2", {
            "heating_active": True, "cooling_active": False,
        })
        self.assertFalse(any(f.rule_id == "FDD-AHU-001" for f in faults))

    def test_stuck_damper_detected(self):
        faults = self.fdd.evaluate("AHU-3", {
            "damper_command": 80, "damper_position": 20,
        })
        self.assertTrue(any(f.rule_id == "FDD-AHU-002" for f in faults))

    def test_stuck_damper_normal(self):
        faults = self.fdd.evaluate("AHU-4", {
            "damper_command": 50, "damper_position": 48,
        })
        self.assertFalse(any(f.rule_id == "FDD-AHU-002" for f in faults))

    def test_sensor_freeze_detected(self):
        faults = self.fdd.evaluate("SENSOR-1", {
            "recent_values": [72.0, 72.0, 72.0, 72.0, 72.0],
            "value": 72.0,
        })
        self.assertTrue(any(f.rule_id == "FDD-SENSOR-001" for f in faults))

    def test_sensor_freeze_not_triggered(self):
        faults = self.fdd.evaluate("SENSOR-2", {
            "recent_values": [72.0, 72.1, 71.9, 72.2, 71.8],
            "value": 72.0,
        })
        self.assertFalse(any(f.rule_id == "FDD-SENSOR-001" for f in faults))

    def test_sensor_drift_detected(self):
        faults = self.fdd.evaluate("SENSOR-3", {
            "value": -50.0, "plausible_low": 0, "plausible_high": 120,
        })
        self.assertTrue(any(f.rule_id == "FDD-SENSOR-002" for f in faults))

    def test_sensor_drift_normal(self):
        faults = self.fdd.evaluate("SENSOR-4", {
            "value": 72.0, "plausible_low": 0, "plausible_high": 120,
        })
        self.assertFalse(any(f.rule_id == "FDD-SENSOR-002" for f in faults))

    def test_chiller_degradation_detected(self):
        faults = self.fdd.evaluate("CHILLER-1", {
            "cop": 2.1, "cop_threshold": 3.0,
        })
        self.assertTrue(any(f.rule_id == "FDD-CHILLER-001" for f in faults))

    def test_chiller_normal(self):
        faults = self.fdd.evaluate("CHILLER-2", {
            "cop": 4.5, "cop_threshold": 3.0,
        })
        self.assertFalse(any(f.rule_id == "FDD-CHILLER-001" for f in faults))

    def test_deduplication(self):
        """Same fault should not be raised twice."""
        self.fdd.evaluate("AHU-DUP", {"heating_active": True, "cooling_active": True})
        faults2 = self.fdd.evaluate("AHU-DUP", {"heating_active": True, "cooling_active": True})
        self.assertEqual(len(faults2), 0)

    def test_auto_resolve(self):
        """Fault auto-resolves when condition clears."""
        self.fdd.evaluate("AHU-AR", {"heating_active": True, "cooling_active": True})
        active = self.fdd.get_active_faults(equipment_id="AHU-AR")
        self.assertGreater(len(active), 0)
        self.fdd.evaluate("AHU-AR", {"heating_active": True, "cooling_active": False})
        active_after = self.fdd.get_active_faults(equipment_id="AHU-AR")
        self.assertEqual(len(active_after), 0)

    def test_acknowledge_fault(self):
        faults = self.fdd.evaluate("AHU-ACK", {"heating_active": True, "cooling_active": True})
        self.assertTrue(len(faults) > 0)
        result = self.fdd.acknowledge_fault(faults[0].fault_id)
        self.assertTrue(result)

    def test_custom_rule(self):
        custom = FaultRule(
            rule_id="CUSTOM-001", name="Custom Test",
            description="Test custom rule", severity=FaultSeverity.LOW,
            condition=lambda d: d.get("custom_flag", False),
        )
        self.fdd.register_rule(custom)
        faults = self.fdd.evaluate("EQ-CUSTOM", {"custom_flag": True})
        self.assertTrue(any(f.rule_id == "CUSTOM-001" for f in faults))

    def test_fault_history(self):
        self.fdd.evaluate("AHU-HIST", {"heating_active": True, "cooling_active": True})
        history = self.fdd.get_fault_history()
        self.assertGreater(len(history), 0)


# ── CUSUM tests ──────────────────────────────────────────────────

class TestCUSUMDetector(unittest.TestCase):

    def test_no_drift(self):
        cusum = CUSUMDetector(target_mean=72.0, threshold=5.0)
        for _ in range(10):
            result = cusum.add_observation(72.0)
        self.assertIsNone(result["alarm"])

    def test_upward_drift(self):
        cusum = CUSUMDetector(target_mean=72.0, threshold=5.0, allowance=0.5)
        alarm = None
        for i in range(20):
            result = cusum.add_observation(74.0)
            if result["alarm"]:
                alarm = result["alarm"]
        self.assertEqual(alarm, "upward_drift")

    def test_downward_drift(self):
        cusum = CUSUMDetector(target_mean=72.0, threshold=5.0, allowance=0.5)
        alarm = None
        for i in range(20):
            result = cusum.add_observation(70.0)
            if result["alarm"]:
                alarm = result["alarm"]
        self.assertEqual(alarm, "downward_drift")

    def test_reset(self):
        cusum = CUSUMDetector(target_mean=72.0, threshold=5.0)
        cusum.add_observation(80.0)
        cusum.reset()
        result = cusum.add_observation(72.0)
        self.assertEqual(result["cusum_pos"], 0)

    def test_get_alarms(self):
        cusum = CUSUMDetector(target_mean=72.0, threshold=3.0, allowance=0.1)
        for _ in range(10):
            cusum.add_observation(75.0)
        alarms = cusum.get_alarms()
        self.assertGreater(len(alarms), 0)


# ── Regression baseline tests ───────────────────────────────────

class TestRegressionBaseline(unittest.TestCase):

    def test_linear_fit(self):
        reg = RegressionBaseline(deviation_threshold_pct=15.0)
        for x in range(10):
            reg.add_training_point(float(x), float(x * 2 + 1))
        coeffs = reg.get_coefficients()
        self.assertAlmostEqual(coeffs["slope"], 2.0, places=1)
        self.assertAlmostEqual(coeffs["intercept"], 1.0, places=1)

    def test_predict(self):
        reg = RegressionBaseline()
        for x in range(10):
            reg.add_training_point(float(x), float(x * 3))
        pred = reg.predict(5.0)
        self.assertIsNotNone(pred)
        self.assertAlmostEqual(pred, 15.0, places=0)

    def test_deviation_ok(self):
        reg = RegressionBaseline(deviation_threshold_pct=20.0)
        for x in range(10):
            reg.add_training_point(float(x), float(x * 100))
        result = reg.check_deviation(5.0, 510.0)
        self.assertFalse(result["fault"])

    def test_deviation_fault(self):
        reg = RegressionBaseline(deviation_threshold_pct=10.0)
        for x in range(10):
            reg.add_training_point(float(x), float(x * 100))
        result = reg.check_deviation(5.0, 700.0)
        self.assertTrue(result["fault"])

    def test_insufficient_data(self):
        reg = RegressionBaseline()
        pred = reg.predict(5.0)
        self.assertIsNone(pred)


# ── Alarm Manager tests ─────────────────────────────────────────

class TestAlarmManager(unittest.TestCase):

    def setUp(self):
        self.mgr = AlarmManager()

    def test_raise_alarm(self):
        result = self.mgr.raise_alarm("A1", "EQ-1", "Test alarm")
        self.assertEqual(result["status"], "raised")

    def test_deduplication(self):
        self.mgr.raise_alarm("A-DUP", "EQ-1", "First")
        result = self.mgr.raise_alarm("A-DUP", "EQ-1", "Second")
        self.assertEqual(result["status"], "deduplicated")
        self.assertEqual(result["count"], 2)

    def test_clear_alarm(self):
        self.mgr.raise_alarm("A-CLR", "EQ-1", "To clear")
        self.assertTrue(self.mgr.clear_alarm("A-CLR"))

    def test_priority_sorting(self):
        self.mgr.raise_alarm("A-LOW", "EQ-1", "Low", AlarmPriority.LOW)
        self.mgr.raise_alarm("A-CRIT", "EQ-1", "Critical", AlarmPriority.CRITICAL)
        alarms = self.mgr.get_active_alarms()
        self.assertEqual(alarms[0]["priority_name"], "CRITICAL")

    def test_maintenance_suppression(self):
        now = time.time()
        self.mgr.set_maintenance_window("EQ-MAINT", now - 60, now + 3600)
        result = self.mgr.raise_alarm("A-MAINT", "EQ-MAINT", "During maint")
        self.assertEqual(result["status"], "suppressed_maintenance")

    def test_manual_suppression(self):
        self.mgr.suppress_equipment("EQ-SUP")
        result = self.mgr.raise_alarm("A-SUP", "EQ-SUP", "Suppressed")
        self.assertEqual(result["status"], "suppressed")

    def test_unsuppress(self):
        self.mgr.suppress_equipment("EQ-UNSUP")
        self.mgr.unsuppress_equipment("EQ-UNSUP")
        result = self.mgr.raise_alarm("A-UNSUP", "EQ-UNSUP", "After unsuppress")
        self.assertEqual(result["status"], "raised")

    def test_alarm_history(self):
        self.mgr.raise_alarm("A-H1", "EQ-1", "History")
        history = self.mgr.get_alarm_history()
        self.assertGreater(len(history), 0)

    def test_filter_by_equipment(self):
        self.mgr.raise_alarm("A-F1", "EQ-A", "For A")
        self.mgr.raise_alarm("A-F2", "EQ-B", "For B")
        alarms = self.mgr.get_active_alarms(equipment_id="EQ-A")
        self.assertTrue(all(a["equipment_id"] == "EQ-A" for a in alarms))


if __name__ == "__main__":
    unittest.main()
