"""
Tests for Manufacturer Cut Sheet Engine (CSE-001).

Covers:
  - CutSheetSpec / IOSpec / WiringTerminal / BACnetObjectConfig / DeviceConfig /
    WiringDiagram / ControlDiagram / CommissioningTest / VerificationResult
    dataclasses
  - parse_cutsheet() extraction (controller, sensor, actuator, meter)
  - generate_wiring_diagram() / generate_control_diagram() drawings
  - generate_device_configs() BACnet configs and program stubs
  - generate_commissioning_tests() test case generation
  - verify_commissioning() pass/fail / field-measurement integration
  - export helpers (JSON, Markdown, CSV)
  - Input validation guards
  - Thread-safety (concurrent parse)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import threading
import pytest
import os


from cutsheet_engine import (
    BACnetObjectConfig,
    CommissioningTest,
    ControlDiagram,
    CutSheetEngine,
    CutSheetSpec,
    DeviceConfig,
    EquipmentCategory,
    IOSpec,
    OutputType,
    VerificationResult,
    VerificationStatus,
    WiringDiagram,
    WiringTerminal,
    _detect_category,
    _detect_output_type,
    _extract_io_counts,
)

# ---------------------------------------------------------------------------
# Fixture cut sheet texts
# ---------------------------------------------------------------------------

DDC_CONTROLLER_TEXT = """
Manufacturer: Johnson Controls
Model Number: FX-PCG36
Product Name: FX Series Programmable Controller
Description: 36-point programmable DDC controller with BACnet/IP and MS/TP
Supply Voltage: 24 VAC/VDC
Power Consumption: 30 VA
Operating Temperature: 32°F to 120°F
Analog Inputs: 12
Analog Outputs: 6
Binary Inputs: 12
Binary Outputs: 6
BACnet Device Profile: B-AAC
Vendor ID: 5
Protocols: BACnet/IP, BACnet MS/TP
Certifications: UL 916, BTL, CE
Expansion Slots: 2
"""

TEMP_SENSOR_TEXT = """
Manufacturer: Honeywell
Model Number: C7770A1008
Product Name: Duct Temperature Sensor
Description: NTC thermistor, 10kΩ at 77°F, duct mounting
Supply Voltage: 24 VAC
Operating Temperature: -40°F to 185°F
Range: 0°F to 200°F
Accuracy: ±0.5°F
Output: 0-10V
Units: °F
Certifications: UL, CE
"""

ACTUATOR_TEXT = """
Manufacturer: Belimo
Model Number: AF24-SR US
Product Name: Damper Actuator
Description: Spring return damper actuator, 35 lb·in, fail closed
Supply Voltage: 24 VAC
Torque: 35 lb·in
Stroke Time: 95 sec
Fail Position: normally closed
Control Signal: 0-10V
Certifications: UL, CE, RoHS
"""

METER_TEXT = """
Manufacturer: Schneider Electric
Model Number: PM5500
Product Name: PowerLogic PM5500 Energy Meter
Description: Revenue-grade energy meter with Modbus TCP
Supply Voltage: 100-240 VAC
Protocols: Modbus TCP, Modbus RTU
Range: 0 kWh to 999999 kWh
Units: kWh
Certifications: UL, CE, BTL
"""


# ---------------------------------------------------------------------------
# CutSheetEngine — parse_cutsheet
# ---------------------------------------------------------------------------

class TestParseCutsheet:
    @pytest.fixture
    def engine(self):
        return CutSheetEngine()

    def test_parses_ddc_controller(self, engine):
        spec = engine.parse_cutsheet(DDC_CONTROLLER_TEXT, "Johnson Controls", "FX-PCG36")
        assert spec.manufacturer == "Johnson Controls"
        assert spec.model_number == "FX-PCG36"
        assert spec.category == EquipmentCategory.DDC_CONTROLLER
        assert spec.io_spec is not None
        assert spec.io_spec.ai_count == 12
        assert spec.io_spec.ao_count == 6
        assert spec.io_spec.bi_count == 12
        assert spec.io_spec.bo_count == 6
        assert "BACnet/IP" in spec.protocols
        assert spec.bacnet_device_profile == "B-AAC"
        assert "BTL" in spec.certifications

    def test_parses_temperature_sensor(self, engine):
        spec = engine.parse_cutsheet(TEMP_SENSOR_TEXT)
        assert spec.category == EquipmentCategory.SENSOR_TEMPERATURE
        assert spec.measurement_range_min == 0.0
        assert spec.measurement_range_max == 200.0
        assert spec.accuracy_plus_minus == 0.5
        assert spec.measurement_units == "°F"
        assert spec.output_type == OutputType.ANALOG_010V

    def test_parses_actuator(self, engine):
        spec = engine.parse_cutsheet(ACTUATOR_TEXT)
        assert spec.category == EquipmentCategory.ACTUATOR_DAMPER
        assert spec.actuator_torque_lb_in == 35.0
        assert spec.actuator_stroke_seconds == 95.0
        assert spec.actuator_fail_position != ""

    def test_parses_meter(self, engine):
        spec = engine.parse_cutsheet(METER_TEXT)
        assert "meter" in spec.category.value.lower()
        assert "Modbus" in " ".join(spec.protocols)

    def test_parse_confidence_populated(self, engine):
        spec = engine.parse_cutsheet(DDC_CONTROLLER_TEXT)
        assert 0.0 < spec.parse_confidence <= 1.0

    def test_bad_input_raises(self, engine):
        with pytest.raises(ValueError):
            engine.parse_cutsheet(None)  # type: ignore[arg-type]

    def test_stored_in_library(self, engine):
        spec = engine.parse_cutsheet(DDC_CONTROLLER_TEXT)
        retrieved = engine.get_cutsheet(spec.cutsheet_id)
        assert retrieved is not None
        assert retrieved.cutsheet_id == spec.cutsheet_id

    def test_list_cutsheets(self, engine):
        engine.parse_cutsheet(DDC_CONTROLLER_TEXT)
        engine.parse_cutsheet(TEMP_SENSOR_TEXT)
        listing = engine.list_cutsheets()
        assert len(listing) == 2
        assert all("cutsheet_id" in item for item in listing)


# ---------------------------------------------------------------------------
# IOSpec helpers
# ---------------------------------------------------------------------------

class TestExtractIOCounts:
    def test_extracts_ai_ao_bi_bo(self):
        # Use unambiguous label-first format to avoid cross-line bleed
        text = "Analog Inputs: 12\nAnalog Outputs: 6\nBinary Inputs: 12\nBinary Outputs: 6"
        io = _extract_io_counts(text)
        assert io.ai_count == 12
        assert io.ao_count == 6
        assert io.bi_count == 12
        assert io.bo_count == 6

    def test_total_hardware_io(self):
        io = IOSpec(ai_count=4, ao_count=2, bi_count=4, bo_count=2)
        assert io.total_hardware_io == 12

    def test_to_dict(self):
        io = IOSpec(ai_count=4)
        d = io.to_dict()
        assert d["ai"] == 4
        assert "total_hardware_io" in d


# ---------------------------------------------------------------------------
# Category / output type detection
# ---------------------------------------------------------------------------

class TestDetectCategory:
    def test_detects_ddc(self):
        assert _detect_category("DDC direct digital control", "") == EquipmentCategory.DDC_CONTROLLER

    def test_detects_temp_sensor(self):
        assert _detect_category("temperature sensor duct", "") == EquipmentCategory.SENSOR_TEMPERATURE

    def test_detects_vfd(self):
        assert _detect_category("variable frequency drive VFD", "") == EquipmentCategory.VARIABLE_FREQ_DRIVE


class TestDetectOutputType:
    def test_4_20ma(self):
        assert _detect_output_type("output: 4-20mA") == OutputType.ANALOG_420MA

    def test_0_10v(self):
        assert _detect_output_type("output: 0-10V") == OutputType.ANALOG_010V

    def test_bacnet_ip(self):
        assert _detect_output_type("BACnet/IP") == OutputType.BACNET_IP


# ---------------------------------------------------------------------------
# Drawing generation
# ---------------------------------------------------------------------------

class TestWiringDiagram:
    @pytest.fixture
    def engine_with_sheets(self):
        e = CutSheetEngine()
        e.parse_cutsheet(DDC_CONTROLLER_TEXT, "Johnson Controls", "FX-PCG36")
        e.parse_cutsheet(TEMP_SENSOR_TEXT, "Honeywell", "C7770A1008")
        return e

    def test_generate_wiring_diagram(self, engine_with_sheets):
        engine = engine_with_sheets
        cutsheets = [engine.get_cutsheet(cid)
                     for cid in [c["cutsheet_id"] for c in engine.list_cutsheets()]]
        diag = engine.generate_wiring_diagram(cutsheets, project_name="Test Project")
        assert isinstance(diag, WiringDiagram)
        assert len(diag.devices) == 2
        assert diag.markdown_render != ""
        assert diag.wire_list_csv != ""

    def test_wire_list_csv_headers(self, engine_with_sheets):
        engine = engine_with_sheets
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        diag = engine.generate_wiring_diagram(cutsheets)
        assert "Wire ID" in diag.wire_list_csv

    def test_panel_schedule_populated(self, engine_with_sheets):
        engine = engine_with_sheets
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        diag = engine.generate_wiring_diagram(cutsheets)
        assert len(diag.panel_schedule) == 2

    def test_export_wiring_markdown(self, engine_with_sheets):
        engine = engine_with_sheets
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        diag = engine.generate_wiring_diagram(cutsheets)
        md = engine.export_wiring_diagram(diag, fmt="markdown")
        assert "WIRING DIAGRAM" in md.upper() or "Wire" in md

    def test_export_wiring_csv(self, engine_with_sheets):
        engine = engine_with_sheets
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        diag = engine.generate_wiring_diagram(cutsheets)
        csv = engine.export_wiring_diagram(diag, fmt="csv")
        assert "Wire ID" in csv


class TestControlDiagram:
    @pytest.fixture
    def engine_with_full_set(self):
        e = CutSheetEngine()
        e.parse_cutsheet(DDC_CONTROLLER_TEXT, "Johnson Controls", "FX-PCG36")
        e.parse_cutsheet(TEMP_SENSOR_TEXT, "Honeywell", "C7770A1008")
        e.parse_cutsheet(ACTUATOR_TEXT, "Belimo", "AF24-SR US")
        return e

    def test_generate_control_diagram(self, engine_with_full_set):
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        diag = engine.generate_control_diagram(cutsheets, project_name="Test")
        assert isinstance(diag, ControlDiagram)
        assert len(diag.control_loops) >= 1
        assert diag.markdown_render != ""

    def test_network_diagram_generated(self, engine_with_full_set):
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        diag = engine.generate_control_diagram(cutsheets)
        assert "BACnet" in diag.network_diagram_text or "CTRL" in diag.network_diagram_text

    def test_interlock_generated(self, engine_with_full_set):
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        diag = engine.generate_control_diagram(cutsheets)
        assert len(diag.interlocks) >= 1


# ---------------------------------------------------------------------------
# Device code generation
# ---------------------------------------------------------------------------

class TestDeviceConfigs:
    @pytest.fixture
    def engine_with_full_set(self):
        e = CutSheetEngine()
        e.parse_cutsheet(DDC_CONTROLLER_TEXT, "Johnson Controls", "FX-PCG36")
        e.parse_cutsheet(TEMP_SENSOR_TEXT, "Honeywell", "C7770A1008")
        e.parse_cutsheet(ACTUATOR_TEXT, "Belimo", "AF24-SR US")
        return e

    def test_generates_configs(self, engine_with_full_set):
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        configs = engine.generate_device_configs(cutsheets, project_name="TEST")
        assert len(configs) >= 1
        assert isinstance(configs[0], DeviceConfig)

    def test_config_has_objects(self, engine_with_full_set):
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        configs = engine.generate_device_configs(cutsheets)
        total_objects = sum(len(c.objects) for c in configs)
        assert total_objects >= 1

    def test_program_stub_generated(self, engine_with_full_set):
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        configs = engine.generate_device_configs(cutsheets)
        assert configs[0].controller_program_stub != ""

    def test_json_export(self, engine_with_full_set):
        import json
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        configs = engine.generate_device_configs(cutsheets)
        json_str = engine.export_device_configs_json(configs)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1

    def test_to_dict(self, engine_with_full_set):
        engine = engine_with_full_set
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        configs = engine.generate_device_configs(cutsheets)
        d = configs[0].to_dict()
        assert "device_name" in d
        assert "objects" in d
        assert "controller_program_stub" in d


# ---------------------------------------------------------------------------
# Commissioning verification
# ---------------------------------------------------------------------------

class TestCommissioningTests:
    @pytest.fixture
    def engine_with_all(self):
        e = CutSheetEngine()
        e.parse_cutsheet(DDC_CONTROLLER_TEXT, "Johnson Controls", "FX-PCG36")
        e.parse_cutsheet(TEMP_SENSOR_TEXT, "Honeywell", "C7770A1008")
        e.parse_cutsheet(ACTUATOR_TEXT, "Belimo", "AF24-SR US")
        return e

    def test_generates_tests(self, engine_with_all):
        engine = engine_with_all
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        tests = engine.generate_commissioning_tests(cutsheets)
        assert len(tests) > 0
        assert all(isinstance(t, CommissioningTest) for t in tests)

    def test_sensor_calibration_tests(self, engine_with_all):
        engine = engine_with_all
        # Use the sensor-only cut sheet (TEMP_SENSOR_TEXT has range + accuracy)
        sensor_cs = [
            engine.get_cutsheet(c["cutsheet_id"])
            for c in engine.list_cutsheets()
            if "sensor" in engine.get_cutsheet(c["cutsheet_id"]).category.value
        ]
        assert sensor_cs, "No sensor cut sheets found"
        tests = engine.generate_commissioning_tests(sensor_cs)
        cal_tests = [t for t in tests if t.test_type == "calibration"]
        assert len(cal_tests) >= 1

    def test_hitl_flagged_for_safety_critical(self, engine_with_all):
        engine = engine_with_all
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        tests = engine.generate_commissioning_tests(cutsheets)
        hitl_tests = [t for t in tests if t.hitl_required]
        assert len(hitl_tests) >= 1

    def test_to_dict(self, engine_with_all):
        engine = engine_with_all
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        tests = engine.generate_commissioning_tests(cutsheets)
        d = tests[0].to_dict()
        assert "test_id" in d
        assert "status" in d
        assert "hitl_required" in d


class TestVerifyCommissioning:
    @pytest.fixture
    def engine_with_sensor(self):
        e = CutSheetEngine()
        e.parse_cutsheet(TEMP_SENSOR_TEXT, "Honeywell", "C7770A1008")
        return e

    def test_returns_verification_result(self, engine_with_sensor):
        engine = engine_with_sensor
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        vr = engine.verify_commissioning(cutsheets)
        assert isinstance(vr, VerificationResult)

    def test_passes_with_correct_field_measurements(self, engine_with_sensor):
        engine = engine_with_sensor
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        tests = engine.generate_commissioning_tests(cutsheets)
        # Provide perfect measurements for all numeric tests
        field = {}
        for t in tests:
            if t.expected_value is not None:
                try:
                    field[t.test_id] = {"value": float(t.expected_value)}
                except (ValueError, TypeError):
                    pass
        vr = engine.verify_commissioning(
            cutsheets, field_measurements=field
        )
        assert vr.failed == 0

    def test_fails_with_bad_measurements(self, engine_with_sensor):
        engine = engine_with_sensor
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        tests = engine.generate_commissioning_tests(cutsheets)
        # Build field_measurements that deviate wildly for any test with
        # a numeric expected_value and a positive tolerance.  Because
        # CommissioningTest.test_id is now deterministic, these keys
        # will match the IDs that verify_commissioning generates internally.
        field: Dict[str, Any] = {}
        for t in tests:
            if t.expected_value is not None and t.tolerance is not None:
                try:
                    ev = float(t.expected_value)
                    tol = float(t.tolerance)
                    if tol > 0:
                        field[t.test_id] = {"value": ev + tol * 200}
                except (ValueError, TypeError):
                    pass
        assert field, "No testable numeric values found in commissioning tests"
        vr = engine.verify_commissioning(cutsheets, field_measurements=field)
        assert vr.failed > 0

    def test_report_markdown(self, engine_with_sensor):
        engine = engine_with_sensor
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        vr = engine.verify_commissioning(cutsheets)
        report = engine.export_verification_report(vr)
        assert "Commissioning Verification" in report
        assert "Summary" in report

    def test_hitl_required_count(self, engine_with_sensor):
        engine = engine_with_sensor
        cutsheets = [engine.get_cutsheet(c["cutsheet_id"])
                     for c in engine.list_cutsheets()]
        vr = engine.verify_commissioning(cutsheets)
        assert vr.hitl_required_count >= 1

    def test_spec_vs_supplied_fail(self):
        engine = CutSheetEngine()
        spec = engine.parse_cutsheet(TEMP_SENSOR_TEXT, "Honeywell", "C7770A1008")
        reqs = {spec.cutsheet_id: {"required_model": "DIFFERENT-MODEL-XYZ"}}
        cutsheets = [spec]
        tests = engine.generate_commissioning_tests(cutsheets, reqs)
        fail_tests = [t for t in tests if t.status == VerificationStatus.FAIL]
        assert len(fail_tests) >= 1


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_parse(self):
        engine = CutSheetEngine()
        errors = []

        def parse():
            try:
                engine.parse_cutsheet(TEMP_SENSOR_TEXT, "Honeywell", "C7770A1008")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=parse) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(engine.list_cutsheets()) == 10

    def test_concurrent_verify(self):
        engine = CutSheetEngine()
        spec = engine.parse_cutsheet(TEMP_SENSOR_TEXT)
        errors = []

        def verify():
            try:
                engine.verify_commissioning([spec])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=verify) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
