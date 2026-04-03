"""
Tests for Virtual Controller module
"""
import sys
import unittest
from pathlib import Path
import pytest

# Add src to path

from virtual_controller import (
    VirtualController,
    WiringVerificationEngine,
    WiringIssue,
    VerificationReport,
    MINIMUM_POINT_REQUIREMENTS,
    VALID_UNITS_PER_TYPE
)
from bas_equipment_ingestion import (
    EquipmentSpec,
    ControllerPoint,
    EquipmentPointType,
    EquipmentProtocol,
    EquipmentCategory
)

pytestmark = [pytest.mark.timeout(15)]


class TestControllerPopulation(unittest.TestCase):
    def test_populate_from_spec_loads_all_points(self):
        """Test that populate_from_spec loads all points"""
        points = [
            ControllerPoint("1", "Temp", EquipmentPointType.AI, "ai", 0, "Temp", "degF", 0, 100, 70),
            ControllerPoint("2", "Fan", EquipmentPointType.DO, "do", 0, "Fan", "binary", 0, 1, 0),
        ]
        spec = self._create_spec(points)
        
        controller = VirtualController(spec)
        
        self.assertEqual(len(controller.points), 2)
        self.assertEqual(controller.equipment_name, "Test Equipment")
    
    def test_point_count_matches(self):
        """Test point count matches spec"""
        points = [
            ControllerPoint(f"p{i}", f"Point{i}", EquipmentPointType.AI, "ai", i, "", "degF", 0, 100, 50)
            for i in range(10)
        ]
        spec = self._create_spec(points)
        
        controller = VirtualController()
        count = controller.populate_from_spec(spec)
        
        self.assertEqual(count, 10)
        self.assertEqual(len(controller.points), 10)
    
    def _create_spec(self, points):
        return EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="Test Equipment",
            equipment_type="Test",
            category=EquipmentCategory.HVAC,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.1",
            port=47808,
            device_id=1,
            points=points,
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )


class TestPointReadWrite(unittest.TestCase):
    def test_read_ai_returns_float_in_range(self):
        """Test reading AI returns float within limits"""
        point = ControllerPoint("1", "Temp", EquipmentPointType.AI, "ai", 0, "", "degF", 50, 90, 70)
        spec = self._create_spec([point])
        
        controller = VirtualController(spec)
        value = controller.read_point("1")
        
        self.assertIsInstance(value, float)
        self.assertGreaterEqual(value, 50)
        self.assertLessEqual(value, 90)
    
    def test_write_ao_updates_value(self):
        """Test writing to AO updates value"""
        point = ControllerPoint("1", "Valve", EquipmentPointType.AO, "ao", 0, "", "percent", 0, 100, 0, is_commandable=True)
        spec = self._create_spec([point])
        
        controller = VirtualController(spec)
        success = controller.write_point("1", 75.0)
        
        self.assertTrue(success)
        self.assertEqual(controller.points["1"].current_value, 75.0)
    
    def test_write_to_non_commandable_di_returns_false(self):
        """Test writing to non-commandable DI returns False"""
        point = ControllerPoint("1", "Status", EquipmentPointType.DI, "di", 0, "", "binary", 0, 1, 0, is_commandable=False)
        spec = self._create_spec([point])
        
        controller = VirtualController(spec)
        success = controller.write_point("1", 1.0)
        
        self.assertFalse(success)
    
    def _create_spec(self, points):
        return EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="Test",
            equipment_type="Test",
            category=EquipmentCategory.HVAC,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.1",
            port=47808,
            device_id=1,
            points=points,
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )


class TestSimulatedReadings(unittest.TestCase):
    def test_simulated_values_within_limits(self):
        """Test simulated values are within low/high limits"""
        point = ControllerPoint("1", "Test", EquipmentPointType.AI, "ai", 0, "", "degF", 40, 60, 50)
        spec = self._create_spec([point])
        
        controller = VirtualController(spec)
        
        # Test multiple simulations
        for _ in range(10):
            value = controller.simulate_reading(point)
            self.assertGreaterEqual(value, 40)
            self.assertLessEqual(value, 60)
    
    def test_temp_readings_in_valid_range(self):
        """Test temperature readings are reasonable"""
        point = ControllerPoint("1", "Temp", EquipmentPointType.AI, "ai", 0, "", "degF", 50, 90, 70)
        spec = self._create_spec([point])
        
        controller = VirtualController(spec)
        value = controller.simulate_reading(point)
        
        self.assertGreaterEqual(value, 50)
        self.assertLessEqual(value, 90)
    
    def _create_spec(self, points):
        return EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="Test",
            equipment_type="Test",
            category=EquipmentCategory.HVAC,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.1",
            port=47808,
            device_id=1,
            points=points,
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )


class TestWiringVerification(unittest.TestCase):
    def test_valid_ahu_spec_passes(self):
        """Test valid AHU spec passes verification"""
        points = [
            ControllerPoint("1", "Supply Air Temp", EquipmentPointType.AI, "ai", 0, "", "degF", 50, 90, 55),
            ControllerPoint("2", "Fan Enable", EquipmentPointType.DO, "do", 0, "", "binary", 0, 1, 0, is_commandable=True),
        ]
        spec = self._create_spec(points, EquipmentCategory.HVAC)
        
        controller = VirtualController(spec)
        report = controller.verify_wiring(spec)
        
        self.assertEqual(report.error_count, 0)
    
    def test_missing_supply_temp_error(self):
        """Test missing supply temp generates error"""
        points = [
            ControllerPoint("1", "Return Air Temp", EquipmentPointType.AI, "ai", 0, "", "degF", 50, 90, 70),
        ]
        spec = self._create_spec(points, EquipmentCategory.HVAC)
        
        engine = WiringVerificationEngine()
        report = engine.verify(spec)
        
        # HVAC requires at least 1 DO, so this should have warnings/errors
        self.assertGreater(len(report.issues), 0)
    
    def test_reversed_limits_error(self):
        """Test reversed limits generate error"""
        points = [
            ControllerPoint("1", "Bad Point", EquipmentPointType.AI, "ai", 0, "", "degF", 100, 0, 50),  # reversed
        ]
        spec = self._create_spec(points, EquipmentCategory.ELECTRICAL)
        
        engine = WiringVerificationEngine()
        report = engine.verify(spec)
        
        self.assertGreater(report.error_count, 0)
        self.assertFalse(report.passed)
    
    def test_duplicate_bacnet_instances_warning(self):
        """Test duplicate BACnet instances generate warning"""
        points = [
            ControllerPoint("1", "Point1", EquipmentPointType.AI, "analog-input", 0, "", "degF", 0, 100, 50),
            ControllerPoint("2", "Point2", EquipmentPointType.AI, "analog-input", 0, "", "degF", 0, 100, 50),  # duplicate instance
        ]
        spec = self._create_spec(points, EquipmentCategory.HVAC)
        
        engine = WiringVerificationEngine()
        report = engine.verify(spec)
        
        # Should have duplicate instance errors
        self.assertGreater(len(report.issues), 0)
        duplicate_issues = [i for i in report.issues if i.issue_type == "duplicate_instance"]
        self.assertGreater(len(duplicate_issues), 0)
    
    def _create_spec(self, points, category=EquipmentCategory.HVAC):
        return EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="Test Equipment",
            equipment_type="Test",
            category=category,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.1",
            port=47808,
            device_id=1,
            points=points,
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )


class TestVerificationReport(unittest.TestCase):
    def test_to_dict_serializable(self):
        """Test report to_dict is serializable"""
        points = [
            ControllerPoint("1", "Temp", EquipmentPointType.AI, "ai", 0, "", "degF", 0, 100, 50),
        ]
        spec = self._create_spec(points)
        
        engine = WiringVerificationEngine()
        report = engine.verify(spec)
        report_dict = report.to_dict()
        
        self.assertIn("report_id", report_dict)
        self.assertIn("issues", report_dict)
        self.assertIsInstance(report_dict["issues"], list)
    
    def test_summary_returns_non_empty_string(self):
        """Test summary returns non-empty string"""
        points = [
            ControllerPoint("1", "Temp", EquipmentPointType.AI, "ai", 0, "", "degF", 0, 100, 50),
        ]
        spec = self._create_spec(points)
        
        engine = WiringVerificationEngine()
        report = engine.verify(spec)
        summary = report.summary()
        
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 0)
    
    def test_passed_true_only_when_zero_errors(self):
        """Test passed=True only when error_count=0"""
        # Valid spec
        points = [
            ControllerPoint("1", "Voltage", EquipmentPointType.AI, "ai", 0, "", "V", 0, 500, 277),
        ]
        spec = self._create_spec(points, EquipmentCategory.ELECTRICAL)
        
        engine = WiringVerificationEngine()
        report = engine.verify(spec)
        
        if report.error_count == 0:
            self.assertTrue(report.passed)
        else:
            self.assertFalse(report.passed)
    
    def _create_spec(self, points, category=EquipmentCategory.HVAC):
        return EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="Test Equipment",
            equipment_type="Test",
            category=category,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.1",
            port=47808,
            device_id=1,
            points=points,
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )


class TestControllerStatus(unittest.TestCase):
    def test_get_status_returns_connected_disconnected(self):
        """Test get_status returns connected/disconnected state"""
        controller = VirtualController()
        status = controller.get_status()
        
        self.assertIn("connected", status)
        self.assertIn("controller_id", status)
        self.assertFalse(status["connected"])
    
    def test_after_connect_returns_connected_true(self):
        """Test after connect, status shows connected=True"""
        controller = VirtualController()
        controller.connect()
        status = controller.get_status()
        
        self.assertTrue(status["connected"])


if __name__ == "__main__":
    unittest.main()
