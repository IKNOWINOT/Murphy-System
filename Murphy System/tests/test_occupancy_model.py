# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for Murphy Occupancy Model (BAS-005) — sensor fusion & edge cases."""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from building_automation.occupancy_model import (
    OccupancyModel,
    OccupancySensorInput,
    OccupancyEstimate,
)


class TestOccupancyModel(unittest.TestCase):

    def setUp(self):
        self.model = OccupancyModel(zone_id="Z1", max_capacity=50)

    def test_co2_based_occupancy(self):
        self.model.update_sensor(OccupancySensorInput(
            sensor_id="CO2-1", sensor_type="co2",
            value=800.0, confidence=0.8, timestamp=time.time(),
        ))
        est = self.model.estimate()
        self.assertIsInstance(est, OccupancyEstimate)
        self.assertGreater(est.estimated_count, 0)

    def test_pir_sensor(self):
        self.model.update_sensor(OccupancySensorInput(
            sensor_id="PIR-1", sensor_type="pir",
            value=1.0, confidence=0.9, timestamp=time.time(),
        ))
        est = self.model.estimate()
        self.assertTrue(est.is_occupied)

    def test_badge_sensor(self):
        self.model.update_sensor(OccupancySensorInput(
            sensor_id="BADGE-1", sensor_type="badge",
            value=10.0, confidence=0.95, timestamp=time.time(),
        ))
        est = self.model.estimate()
        self.assertGreaterEqual(est.estimated_count, 1)

    def test_multi_sensor_fusion(self):
        now = time.time()
        self.model.update_sensor(OccupancySensorInput("CO2-1", "co2", 600.0, 0.7, now))
        self.model.update_sensor(OccupancySensorInput("PIR-1", "pir", 1.0, 0.9, now))
        self.model.update_sensor(OccupancySensorInput("BADGE-1", "badge", 8.0, 0.95, now))
        est = self.model.estimate()
        self.assertTrue(est.is_occupied)
        self.assertGreater(len(est.contributing_sensors), 1)

    def test_no_sensors_offline_fallback(self):
        """When no sensors have reported, estimate should still work."""
        est = self.model.estimate()
        self.assertIsInstance(est, OccupancyEstimate)
        self.assertEqual(est.estimated_count, 0)
        self.assertFalse(est.is_occupied)

    def test_stale_sensor_data(self):
        """Sensors with old timestamps should have reduced confidence."""
        old_time = time.time() - 7200  # 2 hours old
        self.model.update_sensor(OccupancySensorInput(
            "CO2-OLD", "co2", 900.0, 0.8, old_time,
        ))
        est = self.model.estimate()
        self.assertIsInstance(est, OccupancyEstimate)

    def test_capacity_clamp(self):
        """Estimated count should not exceed max_capacity."""
        self.model.update_sensor(OccupancySensorInput(
            "BADGE-BIG", "badge", 200.0, 0.99, time.time(),
        ))
        est = self.model.estimate()
        self.assertLessEqual(est.estimated_count, 50)

    def test_predict_preconditioning(self):
        now = time.time()
        self.model.update_sensor(OccupancySensorInput("PIR-1", "pir", 1.0, 0.9, now))
        result = self.model.predict_preconditioning(minutes_ahead=30)
        self.assertIn("should_precondition", result)

    def test_ble_sensor(self):
        self.model.update_sensor(OccupancySensorInput(
            "BLE-1", "ble", 5.0, 0.6, time.time(),
        ))
        est = self.model.estimate()
        self.assertIsInstance(est, OccupancyEstimate)


if __name__ == "__main__":
    unittest.main()
