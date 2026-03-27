"""
Tests for BAS Equipment Ingestion module
"""
import sys
import unittest
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bas_equipment_ingestion import (
    EquipmentDataIngestion,
    EquipmentSpec,
    ControllerPoint,
    EquipmentPointType,
    EquipmentProtocol,
    EquipmentCategory,
    DEFAULT_POINT_TEMPLATES
)

pytestmark = [pytest.mark.timeout(20)]


class TestEquipmentPointTypes(unittest.TestCase):
    def test_all_enum_values_exist(self):
        """Test all point type enum values exist"""
        expected = ["AI", "AO", "DI", "DO", "AV", "BV"]
        actual = [pt.name for pt in EquipmentPointType]
        for exp in expected:
            self.assertIn(exp, actual)


class TestCSVIngestion(unittest.TestCase):
    def test_valid_csv_with_many_points(self):
        """Test ingesting valid CSV with 10+ points"""
        csv_content = """point_name,point_type,object_type,object_instance,units,low_limit,high_limit,normal_value,setpoint,description
Supply Air Temp,AI,analog-input,0,degF,50.0,90.0,55.0,,Supply air temperature
Return Air Temp,AI,analog-input,1,degF,60.0,85.0,72.0,,Return air temperature
Mixed Air Temp,AI,analog-input,2,degF,30.0,95.0,60.0,,Mixed air temperature
Outside Air Temp,AI,analog-input,3,degF,-20.0,120.0,70.0,,Outside air temperature
Supply Fan Status,DI,binary-input,0,binary,0.0,1.0,0.0,,Fan status
Return Fan Status,DI,binary-input,1,binary,0.0,1.0,0.0,,Fan status
Supply Fan Enable,DO,binary-output,0,binary,0.0,1.0,0.0,,Fan enable command
Cooling Valve,AO,analog-output,0,percent,0.0,100.0,0.0,,Cooling valve position
Heating Valve,AO,analog-output,1,percent,0.0,100.0,0.0,,Heating valve position
OA Damper,AO,analog-output,2,percent,0.0,100.0,20.0,,Outside air damper
Filter DP,AI,analog-input,4,inWC,0.0,2.0,0.3,,Filter differential pressure"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_csv(csv_content, "AHU-1", "BACnet/IP")
        
        self.assertEqual(len(spec.points), 11)
        self.assertEqual(spec.equipment_name, "AHU-1")
        self.assertEqual(spec.protocol, EquipmentProtocol.BACNET_IP)
    
    def test_csv_missing_optional_columns(self):
        """Test CSV with missing optional columns"""
        csv_content = """point_name,point_type,object_type,object_instance,units,low_limit,high_limit,normal_value
Supply Air Temp,AI,analog-input,0,degF,50.0,90.0,55.0
Return Air Temp,AI,analog-input,1,degF,60.0,85.0,72.0"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_csv(csv_content, "AHU-2", "BACnet/IP")
        
        self.assertEqual(len(spec.points), 2)
        self.assertIsNone(spec.points[0].setpoint)
    
    def test_csv_wrong_point_type_fallback(self):
        """Test that invalid point type falls back to AI"""
        csv_content = """point_name,point_type,object_type,object_instance,units,low_limit,high_limit,normal_value
Test Point,INVALID,analog-input,0,degF,0.0,100.0,50.0"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_csv(csv_content, "Test", "BACnet/IP")
        
        self.assertEqual(spec.points[0].point_type, EquipmentPointType.AI)


class TestJSONIngestion(unittest.TestCase):
    def test_valid_json(self):
        """Test valid JSON ingestion"""
        json_data = {
            "equipment_name": "Chiller-1",
            "equipment_type": "Chiller",
            "manufacturer": "Carrier",
            "model": "30XA",
            "protocol": "BACnet/IP",
            "points": [
                {
                    "point_name": "CHW Supply Temp",
                    "point_type": "AI",
                    "object_type": "analog-input",
                    "object_instance": 0,
                    "units": "degF",
                    "low_limit": 35.0,
                    "high_limit": 60.0,
                    "normal_value": 44.0
                },
                {
                    "point_name": "Chiller Enable",
                    "point_type": "DO",
                    "object_type": "binary-output",
                    "object_instance": 0,
                    "units": "binary",
                    "low_limit": 0.0,
                    "high_limit": 1.0,
                    "normal_value": 0.0
                }
            ]
        }
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_json(json_data)
        
        self.assertEqual(spec.equipment_name, "Chiller-1")
        self.assertEqual(len(spec.points), 2)
        self.assertEqual(spec.points[1].point_type, EquipmentPointType.DO)
    
    def test_json_missing_required_fields(self):
        """Test JSON with minimal required fields"""
        json_data = {
            "points": [
                {
                    "point_name": "Test",
                    "point_type": "AI"
                }
            ]
        }
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_json(json_data)
        
        self.assertEqual(spec.equipment_name, "Equipment")
        self.assertEqual(len(spec.points), 1)
    
    def test_json_nested_points_array(self):
        """Test JSON with nested points array"""
        json_data = {
            "equipment_name": "VAV-101",
            "points": [
                {"point_name": "Zone Temp", "point_type": "AI", "units": "degF"},
                {"point_name": "Damper Cmd", "point_type": "AO", "units": "percent"}
            ]
        }
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_json(json_data)
        
        self.assertEqual(len(spec.points), 2)


class TestEDEIngestion(unittest.TestCase):
    def test_valid_ede_format(self):
        """Test valid EDE tab-delimited format"""
        ede_content = """#object-name\tobject-type\tobject-instance\tdescription\tpresent-value-default\tunits-code\tvendor-specific-address
Supply_Air_Temp\tanalog-input\t0\tSupply air temperature\t55.0\t62\t
Return_Air_Temp\tanalog-input\t1\tReturn air temperature\t72.0\t62\t
Fan_Status\tbinary-input\t0\tFan running status\t0.0\t\t
Fan_Enable\tbinary-output\t0\tFan enable command\t0.0\t\t"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_ede(ede_content)
        
        self.assertEqual(len(spec.points), 4)
        self.assertEqual(spec.protocol, EquipmentProtocol.BACNET_IP)
    
    def test_ede_object_type_parsing(self):
        """Test BACnet object type to point type mapping"""
        ede_content = """#object-name\tobject-type\tobject-instance
Test_AI\tanalog-input\t0
Test_AO\tanalog-output\t0
Test_BI\tbinary-input\t0
Test_BO\tbinary-output\t0"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_ede(ede_content)
        
        self.assertEqual(spec.points[0].point_type, EquipmentPointType.AI)
        self.assertEqual(spec.points[1].point_type, EquipmentPointType.AO)
        self.assertEqual(spec.points[2].point_type, EquipmentPointType.DI)
        self.assertEqual(spec.points[3].point_type, EquipmentPointType.DO)
    
    def test_ede_units_code_mapping(self):
        """Test BACnet units code mapping"""
        ede_content = """#object-name\tobject-type\tobject-instance\tdescription\tpresent-value-default\tunits-code
Temp_1\tanalog-input\t0\tTemperature\t70.0\t62"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_ede(ede_content)
        
        self.assertEqual(spec.points[0].engineering_units, "degF")


class TestAutoDetect(unittest.TestCase):
    def test_csv_extension_detection(self):
        """Test auto-detect via .csv extension"""
        csv_content = """point_name,point_type
Test,AI"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_auto(csv_content, "equipment.csv")
        
        self.assertEqual(spec.upload_format, "CSV")
    
    def test_json_extension_detection(self):
        """Test auto-detect via .json extension"""
        json_content = '{"equipment_name": "Test", "points": []}'
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_auto(json_content, "equipment.json")
        
        self.assertEqual(spec.upload_format, "JSON")
    
    def test_ede_content_detection(self):
        """Test auto-detect via EDE content"""
        ede_content = """#object-name\tobject-type\tobject-instance
Test\tanalog-input\t0"""
        
        ingestion = EquipmentDataIngestion()
        spec = ingestion.ingest_auto(ede_content)
        
        self.assertEqual(spec.upload_format, "EDE")
    
    def test_unknown_format_raises_error(self):
        """Test that unknown format raises ValueError"""
        ingestion = EquipmentDataIngestion()
        
        with self.assertRaises(ValueError):
            ingestion.ingest_auto("random text", "file.txt")


class TestEquipmentCategoryDetection(unittest.TestCase):
    def test_ahu_keywords_detected_as_hvac(self):
        """Test AHU keywords detected as HVAC"""
        ingestion = EquipmentDataIngestion()
        category = ingestion.detect_equipment_category("AHU-1", [])
        
        self.assertEqual(category, EquipmentCategory.HVAC)
    
    def test_power_keywords_detected_as_electrical(self):
        """Test power keywords detected as ELECTRICAL"""
        ingestion = EquipmentDataIngestion()
        category = ingestion.detect_equipment_category("Power Meter Main", [])
        
        self.assertEqual(category, EquipmentCategory.ELECTRICAL)
    
    def test_flow_meter_detected_as_plumbing(self):
        """Test flow meter detected as PLUMBING"""
        ingestion = EquipmentDataIngestion()
        category = ingestion.detect_equipment_category("Water Flow Meter", [])
        
        self.assertEqual(category, EquipmentCategory.PLUMBING)


class TestPointValidation(unittest.TestCase):
    def test_valid_point_passes(self):
        """Test that valid point has no warnings"""
        point = ControllerPoint(
            point_id="test",
            point_name="Test Point",
            point_type=EquipmentPointType.AI,
            object_type="analog-input",
            object_instance=0,
            description="Test",
            engineering_units="degF",
            low_limit=0.0,
            high_limit=100.0,
            normal_value=50.0,
            is_commandable=False
        )
        
        ingestion = EquipmentDataIngestion()
        warnings = ingestion.validate_point(point)
        
        self.assertEqual(len(warnings), 0)
    
    def test_reversed_limits_fails(self):
        """Test that reversed limits generates warning"""
        point = ControllerPoint(
            point_id="test",
            point_name="Bad Point",
            point_type=EquipmentPointType.AI,
            object_type="analog-input",
            object_instance=0,
            description="",
            engineering_units="",
            low_limit=100.0,
            high_limit=0.0,
            normal_value=50.0,
            is_commandable=False
        )
        
        ingestion = EquipmentDataIngestion()
        warnings = ingestion.validate_point(point)
        
        self.assertGreater(len(warnings), 0)
    
    def test_units_mismatch_warns(self):
        """Test missing units generates warning"""
        point = ControllerPoint(
            point_id="test",
            point_name="No Units",
            point_type=EquipmentPointType.AI,
            object_type="analog-input",
            object_instance=0,
            description="",
            engineering_units="",
            low_limit=0.0,
            high_limit=100.0,
            normal_value=50.0,
            is_commandable=False
        )
        
        ingestion = EquipmentDataIngestion()
        warnings = ingestion.validate_point(point)
        
        self.assertTrue(any("units" in w.lower() for w in warnings))


class TestRecommendations(unittest.TestCase):
    def test_chiller_returns_ashrae_recommendation(self):
        """Test chiller gets ASHRAE recommendation"""
        spec = EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="Chiller-1",
            equipment_type="Chiller",
            category=EquipmentCategory.HVAC,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.1",
            port=47808,
            device_id=1,
            points=[],
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )
        
        ingestion = EquipmentDataIngestion()
        recs = ingestion.get_recommendations(spec)
        
        self.assertGreater(len(recs), 0)
        self.assertTrue(any("ASHRAE" in r for r in recs))
    
    def test_ahu_returns_dcv_recommendation(self):
        """Test AHU gets DCV recommendation"""
        spec = EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="AHU-1",
            equipment_type="AHU",
            category=EquipmentCategory.HVAC,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.1",
            port=47808,
            device_id=1,
            points=[],
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )
        
        ingestion = EquipmentDataIngestion()
        recs = ingestion.get_recommendations(spec)
        
        self.assertTrue(any("ventilation" in r.lower() or "ashrae" in r.lower() for r in recs))
    
    def test_power_meter_returns_submetering_recommendation(self):
        """Test power meter gets sub-metering recommendation"""
        spec = EquipmentSpec(
            spec_id="test",
            equipment_id="test",
            equipment_name="Power Meter",
            equipment_type="Power Meter",
            category=EquipmentCategory.ELECTRICAL,
            manufacturer="Test",
            model="Test",
            serial_number="",
            protocol=EquipmentProtocol.MODBUS_TCP,
            ip_address="192.168.1.1",
            port=502,
            device_id=1,
            points=[],
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="JSON",
            created_at=""
        )
        
        ingestion = EquipmentDataIngestion()
        recs = ingestion.get_recommendations(spec)
        
        self.assertTrue(any("sub-metering" in r.lower() or "leed" in r.lower() for r in recs))


class TestPointSummary(unittest.TestCase):
    def test_counts_by_type_correct(self):
        """Test point summary counts by type"""
        points = [
            ControllerPoint("1", "AI1", EquipmentPointType.AI, "ai", 0, "", "", 0, 100, 50),
            ControllerPoint("2", "AI2", EquipmentPointType.AI, "ai", 1, "", "", 0, 100, 50),
            ControllerPoint("3", "DO1", EquipmentPointType.DO, "do", 0, "", "", 0, 1, 0),
        ]
        
        spec = EquipmentSpec(
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
        
        summary = spec.point_summary()
        
        self.assertEqual(summary["AI"], 2)
        self.assertEqual(summary["DO"], 1)
        self.assertEqual(summary["AO"], 0)
    
    def test_to_dict_round_trips(self):
        """Test spec to_dict is serializable"""
        spec = EquipmentSpec(
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
            points=[],
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={},
            upload_format="CSV",
            created_at=""
        )
        
        spec_dict = spec.to_dict()
        
        self.assertIn("spec_id", spec_dict)
        self.assertIn("equipment_name", spec_dict)
        self.assertIsInstance(spec_dict["points"], list)


class TestDefaultTemplates(unittest.TestCase):
    def test_ahu_template_has_required_points(self):
        """Test AHU template has supply/return temp AI and fan DO"""
        template = DEFAULT_POINT_TEMPLATES.get("AHU", [])
        
        self.assertGreater(len(template), 0)
        
        point_names = [p["name"] for p in template]
        types = [p["type"] for p in template]
        
        self.assertTrue(any("Supply" in name and "Temp" in name for name in point_names))
        self.assertTrue(any("Return" in name and "Temp" in name for name in point_names))
        self.assertTrue("DO" in types)
    
    def test_chiller_template_has_chw_supply_temp(self):
        """Test Chiller template has CHW supply temp"""
        template = DEFAULT_POINT_TEMPLATES.get("Chiller", [])
        
        self.assertGreater(len(template), 0)
        
        point_names = [p["name"] for p in template]
        self.assertTrue(any("CHW" in name and "Supply" in name for name in point_names))


if __name__ == "__main__":
    unittest.main()
