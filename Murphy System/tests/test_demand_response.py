# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for Demand Response Engine (EMS-003) — DR event, shed, restore."""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from energy_management.demand_response import (
    DemandResponseEngine,
    LoadDefinition,
    LoadPriority,
    ShedStatus,
)


class TestDemandResponseEngine(unittest.TestCase):

    def setUp(self):
        self.dr = DemandResponseEngine()
        # register test loads
        self.dr.register_load(LoadDefinition("L1", "Lobby Lights", "Z1", LoadPriority.DISCRETIONARY, 5.0))
        self.dr.register_load(LoadDefinition("L2", "Plug Loads", "Z2", LoadPriority.LOW, 15.0))
        self.dr.register_load(LoadDefinition("L3", "AHU-2 Fan", "Z3", LoadPriority.MEDIUM, 30.0))
        self.dr.register_load(LoadDefinition("L4", "AHU-1 Fan", "Z1", LoadPriority.HIGH, 50.0))
        self.dr.register_load(LoadDefinition("L5", "Fire Panel", "Z1", LoadPriority.CRITICAL, 2.0, is_sheddable=False))

    def test_register_load(self):
        loads = self.dr.list_loads()
        self.assertEqual(len(loads), 5)

    def test_receive_dr_event(self):
        result = self.dr.receive_dr_event({
            "signal_level": "HIGH",
            "target_reduction_kw": 20,
            "duration_minutes": 60,
        })
        self.assertEqual(result["status"], "pending")
        self.assertIn("event_id", result)

    def test_get_active_events(self):
        self.dr.receive_dr_event({"signal_level": "MODERATE", "target_reduction_kw": 10})
        events = self.dr.get_active_events()
        self.assertGreater(len(events), 0)

    def test_compute_shed_plan_priority_order(self):
        plan = self.dr.compute_shed_plan(target_reduction_kw=25)
        # should shed discretionary and low first
        priorities = [p["priority"] for p in plan]
        self.assertEqual(priorities[0], "discretionary")

    def test_compute_shed_plan_excludes_critical(self):
        plan = self.dr.compute_shed_plan(target_reduction_kw=200)
        load_ids = [p["load_id"] for p in plan]
        self.assertNotIn("L5", load_ids)  # Fire Panel is critical

    def test_execute_shed(self):
        plan = self.dr.compute_shed_plan(20)
        evt = self.dr.receive_dr_event({"target_reduction_kw": 20})
        result = self.dr.execute_shed(plan, event_id=evt["event_id"])
        self.assertGreater(result["total_shed_kw"], 0)
        self.assertGreater(result["loads_shed"], 0)

    def test_shed_status(self):
        plan = self.dr.compute_shed_plan(10)
        self.dr.execute_shed(plan)
        status = self.dr.get_shed_status()
        self.assertEqual(status["overall"], "shedding")

    def test_restore_loads(self):
        evt = self.dr.receive_dr_event({"target_reduction_kw": 20})
        plan = self.dr.compute_shed_plan(20)
        self.dr.execute_shed(plan, event_id=evt["event_id"])
        result = self.dr.restore_loads(evt["event_id"])
        self.assertGreater(result["restored_count"], 0)

    def test_restore_nonexistent_event(self):
        result = self.dr.restore_loads("fake-event")
        self.assertIn("error", result)

    def test_verify_reduction_pass(self):
        result = self.dr.verify_reduction(100, 75, 20)
        self.assertTrue(result["verified"])
        self.assertEqual(result["actual_reduction_kw"], 25)

    def test_verify_reduction_fail(self):
        result = self.dr.verify_reduction(100, 95, 20)
        self.assertFalse(result["verified"])

    def test_audit_log(self):
        self.dr.receive_dr_event({"target_reduction_kw": 10})
        log = self.dr.get_audit_log()
        self.assertGreater(len(log), 0)

    def test_full_dr_cycle(self):
        """End-to-end: receive → plan → shed → verify → restore."""
        evt = self.dr.receive_dr_event({
            "signal_level": "HIGH",
            "target_reduction_kw": 20,
            "duration_minutes": 30,
        })
        plan = self.dr.compute_shed_plan(20)
        self.dr.execute_shed(plan, evt["event_id"])
        verify = self.dr.verify_reduction(100, 78, 20)
        self.assertTrue(verify["verified"])
        restore = self.dr.restore_loads(evt["event_id"])
        self.assertGreater(restore["restored_count"], 0)
        status = self.dr.get_shed_status()
        self.assertEqual(status["overall"], "normal")


if __name__ == "__main__":
    unittest.main()
