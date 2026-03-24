# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Manufacturer Cut Sheet Engine for Murphy System.

Design Label: CSE-001 — Cut Sheet Engine
Owner: Platform Engineering / BMS Domain

Ingests manufacturer product data sheets (cut sheets) and uses the declared
equipment specifications to drive three downstream workflows:

  1. **Drawing generation** — produces submittal-quality control diagrams,
     wiring diagrams, network architecture diagrams, and panel schedules from
     actual equipment I/O counts, terminal designations, and wiring specs.

  2. **Device code generation** — produces BACnet device configuration files
     (JSON), controller point-database entries, and structured-text control
     program stubs that precisely match the equipment's declared I/O, BACnet
     object profile, engineering units, and calibration ranges.

  3. **Commissioning verification** — compares declared manufacturer specs
     against a set of commissioned requirements (RFP spec or field-verified
     data) and produces a detailed pass/fail report with tolerance checking,
     flagged discrepancies, and HITL sign-off requirements for failed items.

Parsing strategy
────────────────
Cut sheets arrive as plain text (PDF-extracted or typed specs).  The parser
uses regex key-value extraction, keyword detection, and structured-section
splitting.  No external NLP library is required.  Parse confidence is
reported so callers can decide whether to escalate to a human reviewer.

Safety invariants
─────────────────
  - Thread-safe: all shared state guarded by threading.Lock.
  - Bounded collections via capped_append (CWE-770).
  - Input validated before processing (CWE-20).
  - Errors sanitised before logging (CWE-209).
  - Document size capped at 5 MB (CWE-400).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants                                                          [CWE-20 / CWE-400]
# ---------------------------------------------------------------------------

_MAX_DOC_LEN: int = 5_000_000          # 5 MB text
_MAX_MANUFACTURER_LEN: int = 200
_MAX_MODEL_LEN: int = 200
_MAX_CUTSHEETS: int = 500              # library hard cap
_MAX_TESTS: int = 10_000
_MAX_AUDIT_LOG: int = 50_000

_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,200}$")
_LABEL_RE = re.compile(r"^[a-zA-Z0-9 _\-.,:()/°]{1,500}$")

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EquipmentCategory(str, Enum):
    DDC_CONTROLLER        = "ddc_controller"
    SENSOR_TEMPERATURE    = "sensor_temperature"
    SENSOR_PRESSURE       = "sensor_pressure"
    SENSOR_FLOW           = "sensor_flow"
    SENSOR_CO2            = "sensor_co2"
    SENSOR_HUMIDITY       = "sensor_humidity"
    SENSOR_OCCUPANCY      = "sensor_occupancy"
    SENSOR_ILLUMINANCE    = "sensor_illuminance"
    ACTUATOR_VALVE        = "actuator_valve"
    ACTUATOR_DAMPER       = "actuator_damper"
    VAV_BOX               = "vav_box"
    AHU                   = "ahu"
    RTU                   = "rtu"
    CHILLER               = "chiller"
    BOILER                = "boiler"
    METER_ELECTRICAL      = "meter_electrical"
    METER_WATER           = "meter_water"
    METER_BTU             = "meter_btu"
    VARIABLE_FREQ_DRIVE   = "variable_freq_drive"
    NETWORK_DEVICE        = "network_device"
    OTHER                 = "other"


class OutputType(str, Enum):
    """Sensor output signal type."""
    ANALOG_420MA    = "4_20mA"
    ANALOG_010V     = "0_10V"
    ANALOG_25V      = "2_5V"
    RESISTANCE      = "resistance"
    DIGITAL         = "digital"
    RS485_MODBUS    = "rs485_modbus"
    BACNET_MSTP     = "bacnet_mstp"
    BACNET_IP       = "bacnet_ip"
    UNKNOWN         = "unknown"


class VerificationStatus(str, Enum):
    PASS            = "pass"
    FAIL            = "fail"
    WARNING         = "warning"
    NOT_TESTED      = "not_tested"
    HITL_REQUIRED   = "hitl_required"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class IOSpec:
    """I/O count specification for a DDC controller or I/O module."""
    ai_count: int = 0       # Analog Inputs
    ao_count: int = 0       # Analog Outputs
    bi_count: int = 0       # Binary (Digital) Inputs
    bo_count: int = 0       # Binary (Digital) Outputs
    av_count: int = 0       # Analog Values (software points)
    bv_count: int = 0       # Binary Values (software points)
    universal_count: int = 0  # Universal points (configurable AI/BI/DI)
    expansion_slots: int = 0
    supported_protocols: List[str] = field(default_factory=list)

    @property
    def total_hardware_io(self) -> int:
        return self.ai_count + self.ao_count + self.bi_count + self.bo_count + self.universal_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ai": self.ai_count,
            "ao": self.ao_count,
            "bi": self.bi_count,
            "bo": self.bo_count,
            "av": self.av_count,
            "bv": self.bv_count,
            "universal": self.universal_count,
            "expansion_slots": self.expansion_slots,
            "total_hardware_io": self.total_hardware_io,
            "supported_protocols": list(self.supported_protocols),
        }


@dataclass
class WiringTerminal:
    """A single wiring terminal on a device."""
    terminal_id: str = ""          # e.g. "T1", "AI1+", "COM"
    label: str = ""                # printed label
    signal_type: str = ""          # "AI", "AO", "BI", "BO", "PWR", "GND", "COM", "RS485"
    wire_gauge_awg: str = ""       # "18 AWG", "14 AWG"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "terminal_id": self.terminal_id,
            "label": self.label,
            "signal_type": self.signal_type,
            "wire_gauge_awg": self.wire_gauge_awg,
            "notes": self.notes,
        }


@dataclass
class CutSheetSpec:
    """
    Fully parsed manufacturer cut sheet / product data sheet.

    All numeric specs (ranges, accuracy, torque, etc.) are stored as floats
    with their units in a companion ``_units`` field so callers can perform
    tolerance checking without re-parsing.
    """
    cutsheet_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    manufacturer: str = ""
    model_number: str = ""
    product_name: str = ""
    category: EquipmentCategory = EquipmentCategory.OTHER
    description: str = ""

    # Power
    power_supply_vac: Optional[float] = None
    power_supply_vdc: Optional[float] = None
    power_consumption_va: Optional[float] = None

    # Environment
    operating_temp_min_f: Optional[float] = None
    operating_temp_max_f: Optional[float] = None
    storage_temp_min_f: Optional[float] = None
    storage_temp_max_f: Optional[float] = None
    humidity_pct_max: Optional[float] = None

    # Physical
    dimensions_hwl_in: Optional[Tuple[float, float, float]] = None
    weight_lb: Optional[float] = None
    enclosure_rating: str = ""     # "NEMA 1", "IP54", etc.

    # Communication
    protocols: List[str] = field(default_factory=list)
    bacnet_device_profile: str = ""   # "B-AAC", "B-SA", "B-BC", etc.
    bacnet_vendor_id: Optional[int] = None
    bacnet_vendor_name: str = ""
    modbus_register_map: Dict[str, Any] = field(default_factory=dict)

    # I/O (controllers and I/O modules)
    io_spec: Optional[IOSpec] = None

    # Measurement (sensors)
    measurement_range_min: Optional[float] = None
    measurement_range_max: Optional[float] = None
    measurement_units: str = ""        # "°F", "psi", "CFM", "%RH", "ppm"
    accuracy_plus_minus: Optional[float] = None
    accuracy_units: str = ""
    output_type: OutputType = OutputType.UNKNOWN
    output_range_min: Optional[float] = None
    output_range_max: Optional[float] = None

    # Actuation (valves, damper actuators)
    actuator_torque_lb_in: Optional[float] = None
    actuator_stroke_seconds: Optional[float] = None
    actuator_fail_position: str = ""   # "normally open", "normally closed", "last position"
    actuator_signal: str = ""          # "0-10V", "4-20mA", "floating"

    # Certifications & compliance
    certifications: List[str] = field(default_factory=list)  # "UL 916", "BTL", "CE", "FCC"

    # Wiring
    wiring_terminals: List[WiringTerminal] = field(default_factory=list)
    wiring_notes: str = ""

    # Raw key-value pairs extracted from the cut sheet
    raw_specs: Dict[str, str] = field(default_factory=dict)

    # Parse metadata
    parse_confidence: float = 0.0
    source_text_len: int = 0
    parsed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cutsheet_id": self.cutsheet_id,
            "manufacturer": self.manufacturer,
            "model_number": self.model_number,
            "product_name": self.product_name,
            "category": self.category.value,
            "description": self.description[:500],
            "power_supply_vac": self.power_supply_vac,
            "power_supply_vdc": self.power_supply_vdc,
            "operating_temp_min_f": self.operating_temp_min_f,
            "operating_temp_max_f": self.operating_temp_max_f,
            "enclosure_rating": self.enclosure_rating,
            "protocols": list(self.protocols),
            "bacnet_device_profile": self.bacnet_device_profile,
            "bacnet_vendor_id": self.bacnet_vendor_id,
            "bacnet_vendor_name": self.bacnet_vendor_name,
            "io_spec": self.io_spec.to_dict() if self.io_spec else None,
            "measurement_range_min": self.measurement_range_min,
            "measurement_range_max": self.measurement_range_max,
            "measurement_units": self.measurement_units,
            "accuracy_plus_minus": self.accuracy_plus_minus,
            "accuracy_units": self.accuracy_units,
            "output_type": self.output_type.value,
            "actuator_torque_lb_in": self.actuator_torque_lb_in,
            "actuator_fail_position": self.actuator_fail_position,
            "certifications": list(self.certifications),
            "wiring_terminals": [t.to_dict() for t in self.wiring_terminals],
            "raw_specs": dict(self.raw_specs),
            "parse_confidence": self.parse_confidence,
            "parsed_at": self.parsed_at,
        }


@dataclass
class BACnetObjectConfig:
    """A single BACnet object entry in a device configuration."""
    object_type: str = ""       # "Analog Input", "Binary Output", etc.
    object_instance: int = 0
    object_name: str = ""
    description: str = ""
    engineering_units: str = ""
    present_value_default: Optional[float] = None
    cov_increment: Optional[float] = None
    relinquish_default: Optional[float] = None
    high_limit: Optional[float] = None
    low_limit: Optional[float] = None
    terminal_id: str = ""
    wiring_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_instance": self.object_instance,
            "object_name": self.object_name,
            "description": self.description,
            "engineering_units": self.engineering_units,
            "present_value_default": self.present_value_default,
            "cov_increment": self.cov_increment,
            "relinquish_default": self.relinquish_default,
            "high_limit": self.high_limit,
            "low_limit": self.low_limit,
            "terminal_id": self.terminal_id,
            "wiring_ref": self.wiring_ref,
        }


@dataclass
class DeviceConfig:
    """
    BACnet device configuration generated from one or more cut sheets.

    Suitable for import into most BTL-certified BMS front-ends.
    """
    config_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    device_name: str = ""
    device_instance: int = 1
    vendor_id: Optional[int] = None
    vendor_name: str = ""
    model_name: str = ""
    firmware_revision: str = "1.0"
    bacnet_device_profile: str = ""
    network_type: str = "BACnet/IP"
    ip_address: str = ""
    udp_port: int = 47808
    objects: List[BACnetObjectConfig] = field(default_factory=list)
    controller_program_stub: str = ""   # structured text control program skeleton
    generated_from: List[str] = field(default_factory=list)  # cutsheet_ids
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "device_name": self.device_name,
            "device_instance": self.device_instance,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "model_name": self.model_name,
            "bacnet_device_profile": self.bacnet_device_profile,
            "network_type": self.network_type,
            "ip_address": self.ip_address,
            "udp_port": self.udp_port,
            "objects": [o.to_dict() for o in self.objects],
            "controller_program_stub": self.controller_program_stub,
            "generated_from": list(self.generated_from),
            "generated_at": self.generated_at,
        }


@dataclass
class WiringDiagram:
    """
    Submittal-quality wiring diagram specification.

    Rendered as structured Markdown with ASCII-art terminal blocks and
    wire lists. Can be imported into Visio / AutoCAD LT using the wire
    list CSV export.
    """
    diagram_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    project_name: str = ""
    revision: str = "1.0"
    devices: List[Dict[str, Any]] = field(default_factory=list)
    wire_list: List[Dict[str, Any]] = field(default_factory=list)
    panel_schedule: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    markdown_render: str = ""
    wire_list_csv: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagram_id": self.diagram_id,
            "title": self.title,
            "project_name": self.project_name,
            "revision": self.revision,
            "devices": list(self.devices),
            "wire_list": list(self.wire_list),
            "panel_schedule": list(self.panel_schedule),
            "notes": list(self.notes),
            "markdown_render": self.markdown_render,
            "wire_list_csv": self.wire_list_csv,
            "generated_at": self.generated_at,
        }


@dataclass
class ControlDiagram:
    """
    Submittal-quality control diagram / sequence diagram specification.

    Rendered as structured Markdown with ASCII signal-flow blocks,
    control loop descriptions, and cross-references to point schedule.
    """
    diagram_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    project_name: str = ""
    revision: str = "1.0"
    systems_covered: List[str] = field(default_factory=list)
    control_loops: List[Dict[str, Any]] = field(default_factory=list)
    interlocks: List[Dict[str, Any]] = field(default_factory=list)
    network_diagram_text: str = ""
    markdown_render: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagram_id": self.diagram_id,
            "title": self.title,
            "project_name": self.project_name,
            "revision": self.revision,
            "systems_covered": list(self.systems_covered),
            "control_loops": list(self.control_loops),
            "interlocks": list(self.interlocks),
            "network_diagram_text": self.network_diagram_text,
            "markdown_render": self.markdown_render,
            "generated_at": self.generated_at,
        }


@dataclass
class CommissioningTest:
    """A single functional test case derived from cut sheet specifications.

    ``test_id`` is deterministic: it is derived from ``cutsheet_id``,
    ``test_type``, and ``test_description`` so that the same cut sheet and
    description always produce the same ID across multiple calls to
    ``generate_commissioning_tests``.  This allows callers to construct
    ``field_measurements`` dicts from a first call and pass them into
    ``verify_commissioning`` without ID mismatches.
    """
    equipment_tag: str = ""        # e.g. "AHU-01", "VAV-FL1-01"
    cutsheet_id: str = ""
    manufacturer: str = ""
    model_number: str = ""
    test_type: str = ""            # "functional", "calibration", "range", "protocol", "wiring"
    test_description: str = ""
    expected_value: Optional[Any] = None
    expected_units: str = ""
    tolerance: Optional[float] = None
    tolerance_units: str = ""
    actual_value: Optional[Any] = None
    status: VerificationStatus = VerificationStatus.NOT_TESTED
    failure_reason: str = ""
    hitl_required: bool = False    # True when failure requires P.E. / CxA sign-off
    tested_by: str = ""
    tested_at: Optional[str] = None
    # test_id is last so construction by positional args still works, and
    # it is computed post-init if left blank.
    test_id: str = ""

    def __post_init__(self) -> None:
        if not self.test_id:
            import hashlib as _hl
            seed = f"{self.cutsheet_id}|{self.test_type}|{self.test_description}"
            self.test_id = _hl.sha256(seed.encode()).hexdigest()[:10]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "equipment_tag": self.equipment_tag,
            "cutsheet_id": self.cutsheet_id,
            "manufacturer": self.manufacturer,
            "model_number": self.model_number,
            "test_type": self.test_type,
            "test_description": self.test_description,
            "expected_value": self.expected_value,
            "expected_units": self.expected_units,
            "tolerance": self.tolerance,
            "tolerance_units": self.tolerance_units,
            "actual_value": self.actual_value,
            "status": self.status.value,
            "failure_reason": self.failure_reason,
            "hitl_required": self.hitl_required,
            "tested_by": self.tested_by,
            "tested_at": self.tested_at,
        }


@dataclass
class VerificationResult:
    """
    Full commissioning verification report.

    Produced by ``CutSheetEngine.verify_commissioning()``.
    Compares what the cut sheet declares against the commissioned
    requirements and field-measured values.
    """
    result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_name: str = ""
    tests: List[CommissioningTest] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    not_tested: int = 0
    hitl_required_count: int = 0
    overall_status: VerificationStatus = VerificationStatus.NOT_TESTED
    compliance_flags: List[str] = field(default_factory=list)
    summary: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "project_name": self.project_name,
            "tests": [t.to_dict() for t in self.tests],
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "not_tested": self.not_tested,
            "hitl_required_count": self.hitl_required_count,
            "overall_status": self.overall_status.value,
            "compliance_flags": list(self.compliance_flags),
            "summary": self.summary,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_error(exc: Exception) -> str:  # [CWE-209]
    return f"ERR-{type(exc).__name__}-{id(exc) & 0xFFFF:04X}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_kv(text: str, *patterns: str) -> Optional[str]:
    """Try each regex pattern and return the first match group 1."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:300]
    return None


def _extract_float(text: str, *patterns: str) -> Optional[float]:
    """Extract a float from the first matching pattern."""
    raw = _extract_kv(text, *patterns)
    if raw is None:
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", raw)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


def _extract_io_counts(text: str) -> IOSpec:
    """Parse I/O counts from controller cut sheet text.

    Only looks for labels-first patterns (e.g. "AI: 12") or count-first
    patterns on the *same line* using ``[ \\t]*`` instead of ``\\s*`` so
    that a count on one line never bleeds into a label on the next line.
    """
    spec = IOSpec()
    # Patterns: (regex, field_name).
    # Use [ \t]* (not \s*) to prevent cross-line matches.
    for pat, field_name in [
        # "Universal: 8"  /  "8 universal"
        (r"universal[ \t]*[:\-=][ \t]*(\d+)", "universal"),
        (r"(\d+)[ \t]*universal", "universal"),
        # "AI: 12"  /  "Analog Inputs: 12"
        (r"(?:analog[ \t]*inputs?|AI)[ \t]*[:\-=][ \t]*(\d+)", "ai"),
        (r"(\d+)[ \t]*(?:analog[ \t]*inputs?|A\.?I\.?)", "ai"),
        # "AO: 6"  /  "Analog Outputs: 6"
        (r"(?:analog[ \t]*outputs?|AO)[ \t]*[:\-=][ \t]*(\d+)", "ao"),
        (r"(\d+)[ \t]*(?:analog[ \t]*outputs?|A\.?O\.?)", "ao"),
        # "BI: 12"  /  "Binary Inputs: 12"
        (r"(?:binary[ \t]*inputs?|digital[ \t]*inputs?|BI|DI)[ \t]*[:\-=][ \t]*(\d+)", "bi"),
        (r"(\d+)[ \t]*(?:binary[ \t]*inputs?|digital[ \t]*inputs?|B\.?I\.?|D\.?I\.?)", "bi"),
        # "BO: 6"  /  "Binary Outputs: 6"
        (r"(?:binary[ \t]*outputs?|digital[ \t]*outputs?|BO|DO)[ \t]*[:\-=][ \t]*(\d+)", "bo"),
        (r"(\d+)[ \t]*(?:binary[ \t]*outputs?|digital[ \t]*outputs?|B\.?O\.?|D\.?O\.?)", "bo"),
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if val > 256:   # sanity cap
                    continue
                if field_name == "ai" and spec.ai_count == 0:
                    spec.ai_count = val
                elif field_name == "ao" and spec.ao_count == 0:
                    spec.ao_count = val
                elif field_name == "bi" and spec.bi_count == 0:
                    spec.bi_count = val
                elif field_name == "bo" and spec.bo_count == 0:
                    spec.bo_count = val
                elif field_name == "universal" and spec.universal_count == 0:
                    spec.universal_count = val
            except (ValueError, IndexError):
                continue

    # Expansion slots
    m = re.search(r"(\d+)\s*expansion\s*slots?", text, re.IGNORECASE)
    if m:
        spec.expansion_slots = min(int(m.group(1)), 16)

    return spec


def _detect_category(text: str, model: str) -> EquipmentCategory:
    """Infer equipment category from cut sheet text."""
    lower = text.lower() + " " + model.lower()
    checks = [
        (EquipmentCategory.DDC_CONTROLLER,
         ["ddc", "direct digital control", "programmable controller",
          "field controller", "bacnet controller", "unitary controller"]),
        (EquipmentCategory.SENSOR_TEMPERATURE,
         ["temperature sensor", "temp sensor", "thermostat", "thermistor",
          "rtd sensor", "duct temperature", "space temperature"]),
        (EquipmentCategory.SENSOR_PRESSURE,
         ["pressure sensor", "pressure transducer", "differential pressure",
          "static pressure", "duct pressure"]),
        (EquipmentCategory.SENSOR_FLOW,
         ["flow sensor", "flow meter", "airflow", "cfm sensor", "velocity sensor"]),
        (EquipmentCategory.SENSOR_CO2,
         ["co2 sensor", "carbon dioxide", "co₂", "voc sensor"]),
        (EquipmentCategory.SENSOR_HUMIDITY,
         ["humidity sensor", "rh sensor", "humidity transmitter", "dewpoint"]),
        (EquipmentCategory.SENSOR_OCCUPANCY,
         ["occupancy sensor", "motion sensor", "pir sensor", "presence sensor"]),
        (EquipmentCategory.SENSOR_ILLUMINANCE,
         ["light sensor", "photocell", "illuminance", "daylight sensor", "lux"]),
        (EquipmentCategory.ACTUATOR_VALVE,
         ["valve actuator", "control valve", "modulating valve", "globe valve"]),
        (EquipmentCategory.ACTUATOR_DAMPER,
         ["damper actuator", "vav actuator", "volume control damper"]),
        (EquipmentCategory.VAV_BOX,
         ["vav box", "vav terminal", "variable air volume"]),
        (EquipmentCategory.AHU,
         ["air handling unit", "ahu", "air handler"]),
        # Meters checked BEFORE RTU so "Modbus RTU" in text doesn't override
        # a dedicated energy/power meter product name.
        (EquipmentCategory.METER_ELECTRICAL,
         ["power meter", "electrical meter", "energy meter", "kwh", "demand meter",
          "powerlogic", "power quality"]),
        (EquipmentCategory.METER_BTU,
         ["btu meter", "heat meter", "cooling meter", "btu/hr meter"]),
        (EquipmentCategory.RTU,
         # Require word boundary so "Modbus RTU" alone doesn't classify as RTU
         ["rooftop unit", "packaged unit", "rooftop hvac"]),
        (EquipmentCategory.VARIABLE_FREQ_DRIVE,
         ["variable frequency drive", "vfd", "variable speed drive", "vsd",
          "adjustable frequency"]),
    ]
    for category, keywords in checks:
        if any(k in lower for k in keywords):
            return category
    return EquipmentCategory.OTHER


def _detect_output_type(text: str) -> OutputType:
    lower = text.lower()
    if "4-20" in lower or "4 to 20" in lower:
        return OutputType.ANALOG_420MA
    if "0-10" in lower or "0 to 10v" in lower:
        return OutputType.ANALOG_010V
    if "2-5v" in lower or "2 to 5v" in lower:
        return OutputType.ANALOG_25V
    if "resistance" in lower or "ntc" in lower or "ptc" in lower:
        return OutputType.RESISTANCE
    if "bacnet/ip" in lower or "bacnetip" in lower:
        return OutputType.BACNET_IP
    if "bacnet" in lower or "mstp" in lower:
        return OutputType.BACNET_MSTP
    if "modbus" in lower or "rs-485" in lower or "rs485" in lower:
        return OutputType.RS485_MODBUS
    if "digital" in lower or "dry contact" in lower or "on/off" in lower:
        return OutputType.DIGITAL
    return OutputType.UNKNOWN


# ---------------------------------------------------------------------------
# Core engine                                                        CSE-001
# ---------------------------------------------------------------------------

class CutSheetEngine:
    """
    Manufacturer Cut Sheet Engine — CSE-001.

    Stateful library of parsed cut sheets per project.  Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._library: Dict[str, CutSheetSpec] = {}   # cutsheet_id → spec
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Ingestion / parsing
    # ------------------------------------------------------------------

    def parse_cutsheet(
        self,
        text: str,
        manufacturer: str = "",
        model: str = "",
    ) -> CutSheetSpec:
        """Parse raw cut sheet text and return a CutSheetSpec.

        Args:
            text: plain-text content of the cut sheet (PDF-extracted or typed).
            manufacturer: optional override for manufacturer name.
            model: optional override for model number.

        Returns:
            CutSheetSpec with all extractable fields populated and a
            ``parse_confidence`` score in [0, 1].
        """
        # Input validation                                            [CWE-20]
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        doc = text[:_MAX_DOC_LEN]
        mfr = str(manufacturer)[:_MAX_MANUFACTURER_LEN] if manufacturer else ""
        mdl = str(model)[:_MAX_MODEL_LEN] if model else ""

        spec = CutSheetSpec(source_text_len=len(doc))

        # ── Manufacturer / model ────────────────────────────────────────
        spec.manufacturer = mfr or _extract_kv(
            doc,
            r"(?:manufacturer|mfr|brand)\s*[:\-]\s*([A-Za-z0-9 &.,/\-]{2,100})",
            r"^([A-Z][A-Za-z0-9 &.,]{2,40})\s*$",  # first all-caps line
        ) or "Unknown"

        spec.model_number = mdl or _extract_kv(
            doc,
            r"(?:model\s*(?:number|no\.?|#)?|part\s*(?:number|no\.?|#)?)\s*[:\-]\s*"
            r"([A-Za-z0-9\-_/ ]{2,80})",
        ) or "Unknown"

        spec.product_name = _extract_kv(
            doc,
            r"(?:product\s*name|name)\s*[:\-]\s*(.{5,120})",
        ) or spec.model_number

        # ── Category ────────────────────────────────────────────────────
        spec.category = _detect_category(doc, spec.model_number)

        # ── Description ─────────────────────────────────────────────────
        spec.description = _extract_kv(
            doc,
            r"(?:description|overview|product\s*overview)\s*[:\-]\s*(.{10,500})",
        ) or ""

        # ── Power ───────────────────────────────────────────────────────
        spec.power_supply_vac = _extract_float(
            doc,
            r"(\d+(?:\.\d+)?)\s*v\s*ac",
            r"supply\s*voltage\s*[:\-]\s*(\d+(?:\.\d+)?)\s*v",
        )
        spec.power_supply_vdc = _extract_float(
            doc,
            r"(\d+(?:\.\d+)?)\s*v\s*dc",
        )
        spec.power_consumption_va = _extract_float(
            doc,
            r"(\d+(?:\.\d+)?)\s*va",
            r"power\s*consumption\s*[:\-]\s*(\d+(?:\.\d+)?)",
        )

        # ── Environment ─────────────────────────────────────────────────
        temps = re.findall(
            r"([-+]?\d+(?:\.\d+)?)\s*°?[fc]", doc, re.IGNORECASE
        )
        if len(temps) >= 2:
            floats = [float(t) for t in temps[:4]]
            # Heuristic: lowest is min operating, highest is max operating
            spec.operating_temp_min_f = min(floats)
            spec.operating_temp_max_f = max(floats)

        spec.humidity_pct_max = _extract_float(
            doc,
            r"(\d+(?:\.\d+)?)\s*%\s*(?:rh|relative\s*humidity)",
            r"humidity\s*[:\-]\s*(\d+(?:\.\d+)?)\s*%",
        )

        spec.enclosure_rating = _extract_kv(
            doc,
            r"(?:enclosure|ip\s*rating|nema)\s*[:\-]?\s*((?:NEMA|IP|TYPE)\s*\d+[A-Z0-9]*)",
        ) or ""

        # ── Communication ───────────────────────────────────────────────
        proto_map = {
            "BACnet/IP": ["bacnet/ip", "bacnet ip", "bacnetip"],
            "BACnet MS/TP": ["bacnet ms/tp", "mstp", "ms/tp"],
            "Modbus RTU": ["modbus rtu", "modbus"],
            "Modbus TCP": ["modbus tcp"],
            "LonWorks": ["lonworks", "lon"],
            "KNX": ["knx"],
            "DALI": ["dali"],
            "OPC-UA": ["opc-ua", "opcua"],
        }
        lower_doc = doc.lower()
        spec.protocols = [
            p for p, kws in proto_map.items() if any(k in lower_doc for k in kws)
        ]

        spec.bacnet_device_profile = _extract_kv(
            doc,
            r"(?:bacnet\s*)?device\s*profile\s*[:\-]\s*([B][A-Z\-]{2,20})",
            r"profile\s*[:\-]\s*(B-[A-Z]{2,8})",
        ) or ""

        spec.bacnet_vendor_id = None
        vid_raw = _extract_kv(doc, r"vendor\s*id\s*[:\-]\s*(\d+)")
        if vid_raw:
            try:
                spec.bacnet_vendor_id = int(vid_raw)
            except ValueError:
                pass

        spec.bacnet_vendor_name = _extract_kv(
            doc,
            r"vendor\s*(?:name|company)\s*[:\-]\s*([A-Za-z0-9 &.,/\-]{2,100})",
        ) or spec.manufacturer

        # ── Certifications ──────────────────────────────────────────────
        cert_keywords = ["UL", "cUL", "CSA", "CE", "FCC", "BTL", "RoHS", "ETL",
                         "UL 916", "UL 508", "UL 864"]
        spec.certifications = [
            c for c in cert_keywords if re.search(r"\b" + re.escape(c) + r"\b", doc)
        ]

        # ── I/O spec (controllers) ──────────────────────────────────────
        if spec.category == EquipmentCategory.DDC_CONTROLLER:
            spec.io_spec = _extract_io_counts(doc)
            if spec.io_spec.total_hardware_io > 0:
                spec.wiring_terminals = self._generate_terminals_from_io(spec.io_spec)

        # ── Measurement (sensors) ───────────────────────────────────────
        spec.measurement_range_min = _extract_float(
            doc,
            # "Range: 0°F to 200°F" — allow optional unit chars between number and "to"
            r"range\s*[:\-]\s*([-+]?\d+(?:\.\d+)?)\s*[^\d\n]*?\s*(?:to|–|-)",
            r"minimum\s*range\s*[:\-]\s*([-+]?\d+(?:\.\d+)?)",
        )
        spec.measurement_range_max = _extract_float(
            doc,
            # "Range: 0°F to 200°F" — capture number after "to"
            r"range\s*[:\-]\s*[-+]?\d+(?:\.\d+)?\s*[^\d\n]*?\s*(?:to|–|-)\s*([-+]?\d+(?:\.\d+)?)",
            r"maximum\s*range\s*[:\-]\s*([-+]?\d+(?:\.\d+)?)",
        )
        spec.measurement_units = _extract_kv(
            doc,
            r"(?:units?|engineering\s*units?|range\s*units?)\s*[:\-]\s*([°%A-Za-z/]+)",
        ) or ""

        spec.accuracy_plus_minus = _extract_float(
            doc,
            r"accuracy\s*[:\-]\s*[±+\-]?\s*([\d.]+)",
            r"±\s*([\d.]+)",
        )
        spec.accuracy_units = _extract_kv(
            doc,
            r"accuracy\s*[:\-]\s*[±+\-]?[\d.]+\s*([°%A-Za-z/]+)",
        ) or ""

        spec.output_type = _detect_output_type(doc)
        spec.output_range_min = _extract_float(
            doc,
            r"output\s*[:\-]\s*([\d.]+)\s*(?:to|\-)",
        )
        spec.output_range_max = _extract_float(
            doc,
            r"output\s*[:\-]\s*[\d.]+\s*(?:to|\-)\s*([\d.]+)",
        )

        # ── Actuation ───────────────────────────────────────────────────
        spec.actuator_torque_lb_in = _extract_float(
            doc,
            # matches "35 lb·in", "35 lb-in", "35 lb in", "35 in-lb", "35 Nm"
            r"torque\s*[:\-]\s*([\d.]+)\s*(?:lb[\s\-·]?in|in[\s\-·]?lb|nm)",
        )
        spec.actuator_stroke_seconds = _extract_float(
            doc,
            r"(?:stroke|running)\s*time\s*[:\-]\s*([\d.]+)\s*(?:sec|s\b)",
        )
        spec.actuator_fail_position = _extract_kv(
            doc,
            r"fail\s*(?:safe|position)\s*[:\-]\s*(normally\s+(?:open|closed)|last\s+position)",
        ) or ""
        spec.actuator_signal = _extract_kv(
            doc,
            r"(?:control|input)\s*signal\s*[:\-]\s*([\d\-\/VMAvac ]{3,30})",
        ) or ""

        # ── Wiring notes ────────────────────────────────────────────────
        spec.wiring_notes = _extract_kv(
            doc,
            r"(?:wiring|wiring\s*notes?)\s*[:\-]\s*(.{10,500})",
        ) or ""

        # ── Raw key-value pairs ─────────────────────────────────────────
        kv_pairs = re.findall(
            r"([A-Za-z][A-Za-z0-9 _/\-]{1,60})\s*[:\-]\s*([^\n]{1,200})",
            doc,
        )
        spec.raw_specs = {
            k.strip()[:80]: v.strip()[:200]
            for k, v in kv_pairs[:100]
        }

        # ── Parse confidence ─────────────────────────────────────────────
        score = 0.3  # base
        if spec.manufacturer not in ("Unknown", ""):
            score += 0.1
        if spec.model_number not in ("Unknown", ""):
            score += 0.1
        if spec.protocols:
            score += 0.1
        if spec.io_spec and spec.io_spec.total_hardware_io > 0:
            score += 0.1
        if spec.measurement_range_min is not None:
            score += 0.1
        if spec.accuracy_plus_minus is not None:
            score += 0.1
        if spec.certifications:
            score += 0.05
        if len(spec.raw_specs) >= 5:
            score += 0.05
        spec.parse_confidence = min(round(score, 3), 0.99)

        with self._lock:
            if len(self._library) >= _MAX_CUTSHEETS:
                raise RuntimeError("CSE-001: cut sheet library at capacity")
            self._library[spec.cutsheet_id] = spec

        self._audit("parse_cutsheet",
                    cutsheet_id=spec.cutsheet_id,
                    manufacturer=spec.manufacturer,
                    model=spec.model_number,
                    category=spec.category.value,
                    confidence=spec.parse_confidence)
        logger.info(
            "CSE-001 parse_cutsheet %s (%s %s) category=%s confidence=%.3f",
            spec.cutsheet_id, spec.manufacturer, spec.model_number,
            spec.category.value, spec.parse_confidence,
        )
        return spec

    # ------------------------------------------------------------------
    # Drawing generation
    # ------------------------------------------------------------------

    def generate_wiring_diagram(
        self,
        cutsheets: List[CutSheetSpec],
        project_name: str = "",
        title: str = "",
    ) -> WiringDiagram:
        """Generate a submittal-quality wiring diagram from cut sheet specs.

        Produces:
          - Device blocks with terminal designations from cut sheet data.
          - Wire list (from → to, signal type, wire gauge).
          - Panel schedule listing all devices with power requirements.
          - Rendered Markdown + CSV wire list for import into CAD tools.
        """
        diag = WiringDiagram(
            title=title or "WIRING DIAGRAM — BMS FIELD DEVICES",
            project_name=project_name,
        )

        wire_counter = 1
        for idx, cs in enumerate(cutsheets):
            tag = f"{cs.category.value.upper()[:6]}-{idx+1:02d}"
            device_block = {
                "tag": tag,
                "manufacturer": cs.manufacturer,
                "model": cs.model_number,
                "category": cs.category.value,
                "power": (
                    f"{cs.power_supply_vac} VAC" if cs.power_supply_vac
                    else f"{cs.power_supply_vdc} VDC" if cs.power_supply_vdc
                    else "24 VAC (assumed)"
                ),
                "terminals": [t.to_dict() for t in cs.wiring_terminals[:20]],
                "notes": cs.wiring_notes[:200] if cs.wiring_notes else "",
            }
            diag.devices.append(device_block)

            # Panel schedule entry
            diag.panel_schedule.append({
                "tag": tag,
                "description": cs.product_name or cs.model_number,
                "manufacturer": cs.manufacturer,
                "model": cs.model_number,
                "power_va": cs.power_consumption_va or 10.0,
                "enclosure": cs.enclosure_rating or "N/A",
                "certifications": ", ".join(cs.certifications[:5]),
            })

            # Wire list entries (controller ↔ sensor / actuator)
            for term in cs.wiring_terminals[:10]:
                diag.wire_list.append({
                    "wire_id": f"W{wire_counter:04d}",
                    "from_device": tag,
                    "from_terminal": term.terminal_id,
                    "to_device": "CTRL-01",
                    "to_terminal": f"{term.signal_type}-{wire_counter}",
                    "signal": term.signal_type,
                    "wire_gauge": term.wire_gauge_awg or "18 AWG",
                    "shield": term.signal_type in ("AI", "AO"),
                })
                wire_counter += 1

        diag.notes = [
            "All field wiring shall be installed in dedicated conduit.",
            "Shielded cable required for all analog signal wiring.",
            "Ground shields at one end only (controller end).",
            "Minimum wire gauge: 18 AWG for signal, 14 AWG for power.",
            "All conduit entries shall be sealed with duct seal.",
            "Label all wires at both ends per wire list.",
            "Verify wire gauge matches cut sheet requirements before installation.",
        ]

        diag.markdown_render = self._render_wiring_markdown(diag)
        diag.wire_list_csv = self._render_wire_list_csv(diag)

        self._audit("generate_wiring_diagram", diagram_id=diag.diagram_id,
                    device_count=len(cutsheets))
        return diag

    def generate_control_diagram(
        self,
        cutsheets: List[CutSheetSpec],
        project_name: str = "",
        title: str = "",
    ) -> ControlDiagram:
        """Generate a submittal-quality control diagram from cut sheet specs."""
        diag = ControlDiagram(
            title=title or "CONTROL DIAGRAM — BMS SYSTEMS",
            project_name=project_name,
        )

        # Group cut sheets by system
        controllers = [c for c in cutsheets
                       if c.category == EquipmentCategory.DDC_CONTROLLER]
        sensors = [c for c in cutsheets
                   if "sensor" in c.category.value]
        actuators = [c for c in cutsheets
                     if "actuator" in c.category.value]
        meters = [c for c in cutsheets
                  if "meter" in c.category.value]

        diag.systems_covered = list({c.category.value for c in cutsheets})

        # Control loops
        for idx, ctrl in enumerate(controllers):
            io = ctrl.io_spec
            loop = {
                "controller_tag": f"CTRL-{idx+1:02d}",
                "manufacturer": ctrl.manufacturer,
                "model": ctrl.model_number,
                "io_summary": io.to_dict() if io else {},
                "bacnet_profile": ctrl.bacnet_device_profile,
                "connected_sensors": [
                    {
                        "tag": f"SENS-{i+1:02d}",
                        "type": s.category.value,
                        "model": s.model_number,
                        "range": (
                            f"{s.measurement_range_min}–{s.measurement_range_max} "
                            f"{s.measurement_units}"
                            if s.measurement_range_min is not None else "N/A"
                        ),
                        "output": s.output_type.value,
                    }
                    for i, s in enumerate(sensors[:io.ai_count if io else 8])
                ],
                "connected_actuators": [
                    {
                        "tag": f"ACT-{i+1:02d}",
                        "type": a.category.value,
                        "model": a.model_number,
                        "torque": (
                            f"{a.actuator_torque_lb_in} lb·in"
                            if a.actuator_torque_lb_in else "N/A"
                        ),
                        "fail_safe": a.actuator_fail_position or "N/A",
                    }
                    for i, a in enumerate(actuators[:io.ao_count if io else 4])
                ],
            }
            diag.control_loops.append(loop)

        # Interlocks
        has_fire = any("fire" in c.category.value.lower()
                       or "fire" in c.product_name.lower() for c in cutsheets)
        if has_fire:
            diag.interlocks.append({
                "interlock": "Fire Alarm ↔ HVAC Shutdown",
                "condition": "Fire alarm panel ALARM status input asserted",
                "action": "Command all AHU supply fans OFF; close all smoke dampers",
                "priority": 1,
                "override": "Manual reset required after fire alarm clear",
            })

        diag.interlocks.append({
            "interlock": "High Space Temperature Override",
            "condition": "Space temperature sensor > 85°F for 5 minutes",
            "action": "Force cooling to maximum; alarm operator",
            "priority": 2,
            "override": "Auto-resets when temperature < 82°F",
        })

        # Network diagram
        diag.network_diagram_text = self._render_network_ascii(controllers, cutsheets)
        diag.markdown_render = self._render_control_markdown(diag)

        self._audit("generate_control_diagram", diagram_id=diag.diagram_id,
                    loops=len(diag.control_loops))
        return diag

    # ------------------------------------------------------------------
    # Device code generation
    # ------------------------------------------------------------------

    def generate_device_configs(
        self,
        cutsheets: List[CutSheetSpec],
        project_name: str = "",
        start_device_instance: int = 1,
    ) -> List[DeviceConfig]:
        """Generate BACnet device configuration files from cut sheets.

        One DeviceConfig is produced per DDC controller cut sheet found in
        the list.  Sensor and actuator cut sheets are mapped to BACnet
        objects within the nearest controller.

        Returns a list of DeviceConfig objects ready for JSON export and
        import into a BTL-certified BMS front-end.
        """
        controllers = [c for c in cutsheets
                       if c.category == EquipmentCategory.DDC_CONTROLLER]
        sensors = [c for c in cutsheets if "sensor" in c.category.value]
        actuators = [c for c in cutsheets if "actuator" in c.category.value]
        meters = [c for c in cutsheets if "meter" in c.category.value]

        configs: List[DeviceConfig] = []
        obj_instance_base = 1

        for ctrl_idx, ctrl in enumerate(controllers if controllers else [None]):  # type: ignore[list-item]
            cfg = DeviceConfig(
                device_name=(
                    f"{project_name}-CTRL-{ctrl_idx+1:02d}"
                    if project_name else f"BAS-CTRL-{ctrl_idx+1:02d}"
                ),
                device_instance=start_device_instance + ctrl_idx,
                vendor_id=ctrl.bacnet_vendor_id if ctrl else None,
                vendor_name=ctrl.bacnet_vendor_name if ctrl else "Murphy System",
                model_name=ctrl.model_number if ctrl else "Generic DDC",
                bacnet_device_profile=ctrl.bacnet_device_profile if ctrl else "B-AAC",
                network_type=(
                    "BACnet/IP" if ctrl and "BACnet/IP" in ctrl.protocols
                    else "BACnet MS/TP"
                ),
                generated_from=[ctrl.cutsheet_id] if ctrl else [],
            )

            io = ctrl.io_spec if ctrl else None

            # Analog Input objects — sensors
            for sens_idx, sens in enumerate(sensors):
                ai_obj = BACnetObjectConfig(
                    object_type="Analog Input",
                    object_instance=obj_instance_base + sens_idx,
                    object_name=f"AI-{sens_idx+1:03d}-{sens.category.value[:6].upper()}",
                    description=(
                        f"{sens.manufacturer} {sens.model_number} — "
                        f"{sens.product_name[:60]}"
                    ),
                    engineering_units=sens.measurement_units or "No-Units",
                    present_value_default=(
                        (sens.measurement_range_min or 0.0 +
                         (sens.measurement_range_max or 100.0)) / 2.0
                    ),
                    cov_increment=0.5,
                    high_limit=sens.measurement_range_max,
                    low_limit=sens.measurement_range_min,
                    terminal_id=f"AI{sens_idx+1}",
                    wiring_ref=(
                        f"W{(ctrl_idx * 100 + sens_idx + 1):04d}"
                    ),
                )
                cfg.objects.append(ai_obj)
                capped_append(cfg.generated_from, sens.cutsheet_id, max_size=200)

            obj_instance_base += max(len(sensors), 1)

            # Analog Output objects — actuators
            for act_idx, act in enumerate(actuators):
                obj_type = (
                    "Analog Output"
                    if act.actuator_signal and any(
                        x in act.actuator_signal for x in ["0-10", "4-20", "V", "mA"]
                    )
                    else "Binary Output"
                )
                ao_obj = BACnetObjectConfig(
                    object_type=obj_type,
                    object_instance=obj_instance_base + act_idx,
                    object_name=f"AO-{act_idx+1:03d}-{act.category.value[:5].upper()}",
                    description=(
                        f"{act.manufacturer} {act.model_number} — "
                        f"{act.product_name[:60]}"
                    ),
                    engineering_units="Percent",
                    present_value_default=0.0,
                    relinquish_default=0.0,
                    terminal_id=f"AO{act_idx+1}",
                    wiring_ref=f"W{(ctrl_idx * 100 + act_idx + 101):04d}",
                )
                cfg.objects.append(ao_obj)
                capped_append(cfg.generated_from, act.cutsheet_id, max_size=200)

            obj_instance_base += max(len(actuators), 1)

            # Meter objects
            for met_idx, met in enumerate(meters):
                cfg.objects.append(BACnetObjectConfig(
                    object_type="Analog Input",
                    object_instance=obj_instance_base + met_idx,
                    object_name=f"AI-MET-{met_idx+1:03d}",
                    description=f"{met.manufacturer} {met.model_number} — Energy Meter",
                    engineering_units="kilowatt-hours",
                    terminal_id=f"AI-MET{met_idx+1}",
                ))
                capped_append(cfg.generated_from, met.cutsheet_id, max_size=200)

            # Controller program stub
            cfg.controller_program_stub = self._generate_program_stub(
                cfg, sensors, actuators
            )

            configs.append(cfg)

        self._audit("generate_device_configs",
                    config_count=len(configs),
                    total_objects=sum(len(c.objects) for c in configs))
        return configs

    # ------------------------------------------------------------------
    # Commissioning verification
    # ------------------------------------------------------------------

    def generate_commissioning_tests(
        self,
        cutsheets: List[CutSheetSpec],
        commissioned_requirements: Optional[Dict[str, Any]] = None,
    ) -> List[CommissioningTest]:
        """Generate functional test cases from cut sheet specifications.

        Each cut sheet produces tests appropriate to its category:
          - Sensors: range check, accuracy check, output calibration
          - Controllers: I/O count check, BACnet profile check, protocol check
          - Actuators: stroke test, fail-safe position, signal range
          - Meters: register map check, pulse output, communication test

        Args:
            cutsheets: list of parsed CutSheetSpec objects.
            commissioned_requirements: optional dict from the RFP / spec
                sheet describing what was ordered (model, range, accuracy, etc.)
                Used for spec-vs-supplied verification.
        """
        tests: List[CommissioningTest] = []
        reqs = commissioned_requirements or {}

        for cs in cutsheets:
            tag = reqs.get(cs.cutsheet_id, {}).get("equipment_tag",
                  f"{cs.category.value[:6].upper()}-{cs.cutsheet_id[:4]}")

            # ── Universal tests (all equipment) ─────────────────────────
            tests.append(CommissioningTest(
                equipment_tag=tag,
                cutsheet_id=cs.cutsheet_id,
                manufacturer=cs.manufacturer,
                model_number=cs.model_number,
                test_type="power",
                test_description=(
                    f"Verify power supply: {cs.power_supply_vac} VAC or "
                    f"{cs.power_supply_vdc} VDC per cut sheet"
                ),
                expected_value=cs.power_supply_vac or cs.power_supply_vdc,
                expected_units="V",
                tolerance=1.5,
                tolerance_units="V",
                hitl_required=False,
            ))

            if cs.operating_temp_min_f is not None:
                tests.append(CommissioningTest(
                    equipment_tag=tag,
                    cutsheet_id=cs.cutsheet_id,
                    manufacturer=cs.manufacturer,
                    model_number=cs.model_number,
                    test_type="environment",
                    test_description=(
                        f"Verify installation environment within rated operating "
                        f"range: {cs.operating_temp_min_f}°F – {cs.operating_temp_max_f}°F"
                    ),
                    expected_value=cs.operating_temp_min_f,
                    expected_units="°F",
                    tolerance=5.0,
                    tolerance_units="°F",
                ))

            # ── Certification check ──────────────────────────────────────
            if "BTL" in cs.certifications or "bacnet" in " ".join(cs.protocols).lower():
                tests.append(CommissioningTest(
                    equipment_tag=tag,
                    cutsheet_id=cs.cutsheet_id,
                    manufacturer=cs.manufacturer,
                    model_number=cs.model_number,
                    test_type="protocol",
                    test_description=(
                        "Verify BTL certification and BACnet device profile: "
                        f"{cs.bacnet_device_profile or 'TBD'}"
                    ),
                    expected_value=cs.bacnet_device_profile or "B-AAC",
                    expected_units="BACnet Profile",
                    hitl_required=True,   # P.E. / CxA sign-off on BACnet conformance
                ))

            # ── Sensor-specific tests ────────────────────────────────────
            if "sensor" in cs.category.value:
                if cs.measurement_range_min is not None:
                    tests.append(CommissioningTest(
                        equipment_tag=tag,
                        cutsheet_id=cs.cutsheet_id,
                        manufacturer=cs.manufacturer,
                        model_number=cs.model_number,
                        test_type="calibration",
                        test_description=(
                            f"Verify sensor output at minimum range: "
                            f"{cs.measurement_range_min} {cs.measurement_units} "
                            f"→ expected output {cs.output_range_min} "
                            f"({cs.output_type.value})"
                        ),
                        expected_value=cs.measurement_range_min,
                        expected_units=cs.measurement_units,
                        tolerance=cs.accuracy_plus_minus or 1.0,
                        tolerance_units=cs.accuracy_units or cs.measurement_units,
                    ))
                    tests.append(CommissioningTest(
                        equipment_tag=tag,
                        cutsheet_id=cs.cutsheet_id,
                        manufacturer=cs.manufacturer,
                        model_number=cs.model_number,
                        test_type="calibration",
                        test_description=(
                            f"Verify sensor output at maximum range: "
                            f"{cs.measurement_range_max} {cs.measurement_units} "
                            f"→ expected output {cs.output_range_max} "
                            f"({cs.output_type.value})"
                        ),
                        expected_value=cs.measurement_range_max,
                        expected_units=cs.measurement_units,
                        tolerance=cs.accuracy_plus_minus or 1.0,
                        tolerance_units=cs.accuracy_units or cs.measurement_units,
                    ))
                if cs.accuracy_plus_minus is not None:
                    tests.append(CommissioningTest(
                        equipment_tag=tag,
                        cutsheet_id=cs.cutsheet_id,
                        manufacturer=cs.manufacturer,
                        model_number=cs.model_number,
                        test_type="accuracy",
                        test_description=(
                            f"Verify sensor accuracy ≤ ±{cs.accuracy_plus_minus} "
                            f"{cs.accuracy_units or cs.measurement_units} "
                            f"across full range using calibrated reference"
                        ),
                        expected_value=cs.accuracy_plus_minus,
                        expected_units=cs.accuracy_units or "units",
                        tolerance=cs.accuracy_plus_minus,
                        hitl_required=True,  # CxA to witness calibration
                    ))

            # ── DDC controller tests ─────────────────────────────────────
            elif cs.category == EquipmentCategory.DDC_CONTROLLER and cs.io_spec:
                io = cs.io_spec
                tests.append(CommissioningTest(
                    equipment_tag=tag,
                    cutsheet_id=cs.cutsheet_id,
                    manufacturer=cs.manufacturer,
                    model_number=cs.model_number,
                    test_type="io_count",
                    test_description=(
                        f"Verify I/O count: AI={io.ai_count}, AO={io.ao_count}, "
                        f"BI={io.bi_count}, BO={io.bo_count}, "
                        f"Universal={io.universal_count}"
                    ),
                    expected_value=io.total_hardware_io,
                    expected_units="total I/O points",
                    hitl_required=True,
                ))
                tests.append(CommissioningTest(
                    equipment_tag=tag,
                    cutsheet_id=cs.cutsheet_id,
                    manufacturer=cs.manufacturer,
                    model_number=cs.model_number,
                    test_type="protocol",
                    test_description=(
                        f"Verify BACnet communication: "
                        f"protocols={cs.protocols}"
                    ),
                    expected_value=", ".join(cs.protocols),
                    expected_units="protocol list",
                    hitl_required=True,
                ))

            # ── Actuator tests ───────────────────────────────────────────
            elif "actuator" in cs.category.value:
                if cs.actuator_stroke_seconds:
                    tests.append(CommissioningTest(
                        equipment_tag=tag,
                        cutsheet_id=cs.cutsheet_id,
                        manufacturer=cs.manufacturer,
                        model_number=cs.model_number,
                        test_type="functional",
                        test_description=(
                            f"Verify full stroke time: 0% → 100% in "
                            f"{cs.actuator_stroke_seconds}s per cut sheet"
                        ),
                        expected_value=cs.actuator_stroke_seconds,
                        expected_units="seconds",
                        tolerance=cs.actuator_stroke_seconds * 0.1,
                    ))
                if cs.actuator_fail_position:
                    tests.append(CommissioningTest(
                        equipment_tag=tag,
                        cutsheet_id=cs.cutsheet_id,
                        manufacturer=cs.manufacturer,
                        model_number=cs.model_number,
                        test_type="fail_safe",
                        test_description=(
                            f"Verify fail-safe position on loss of power/signal: "
                            f"expected={cs.actuator_fail_position}"
                        ),
                        expected_value=cs.actuator_fail_position,
                        expected_units="position",
                        hitl_required=True,
                    ))

            # ── Spec-vs-supplied verification ────────────────────────────
            spec_req = reqs.get(cs.cutsheet_id, {})
            if spec_req:
                required_model = spec_req.get("required_model", "")
                if required_model and required_model.lower() not in cs.model_number.lower():
                    tests.append(CommissioningTest(
                        equipment_tag=tag,
                        cutsheet_id=cs.cutsheet_id,
                        manufacturer=cs.manufacturer,
                        model_number=cs.model_number,
                        test_type="spec_compliance",
                        test_description=(
                            f"Verify supplied model matches spec: "
                            f"required={required_model}, supplied={cs.model_number}"
                        ),
                        expected_value=required_model,
                        expected_units="model number",
                        status=VerificationStatus.FAIL,
                        failure_reason=f"Supplied model {cs.model_number!r} "
                                       f"does not match required {required_model!r}",
                        hitl_required=True,
                    ))

        return tests[:_MAX_TESTS]

    def verify_commissioning(
        self,
        cutsheets: List[CutSheetSpec],
        commissioned_requirements: Optional[Dict[str, Any]] = None,
        field_measurements: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify equipment cut sheet specs against commissioned requirements and
        optional field-measured values.

        Args:
            cutsheets: list of CutSheetSpec for equipment on the project.
            commissioned_requirements: dict mapping cutsheet_id → requirement dict
                (required_model, required_range_min/max, required_accuracy, etc.)
            field_measurements: dict mapping test_id → measured_value dict.
                If provided, test results are computed rather than left NOT_TESTED.

        Returns:
            VerificationResult with full pass/fail breakdown, compliance flags,
            and HITL sign-off requirements for failed items.
        """
        vr = VerificationResult()

        tests = self.generate_commissioning_tests(cutsheets, commissioned_requirements)
        measurements = field_measurements or {}

        for test in tests:
            measured = measurements.get(test.test_id)
            if measured is not None:
                # Apply measurement and check tolerance
                test.actual_value = measured.get("value")
                test.tested_by = measured.get("tested_by", "")
                test.tested_at = measured.get("tested_at", _ts())

                if test.expected_value is not None and test.actual_value is not None:
                    try:
                        diff = abs(float(test.actual_value) - float(test.expected_value))
                        tol = test.tolerance or 0.0
                        test.status = (
                            VerificationStatus.PASS
                            if diff <= tol
                            else VerificationStatus.FAIL
                        )
                        if test.status == VerificationStatus.FAIL:
                            test.failure_reason = (
                                f"Measured {test.actual_value} "
                                f"{test.expected_units}; "
                                f"expected {test.expected_value} ± {tol}"
                            )
                    except (TypeError, ValueError):
                        # Non-numeric comparison
                        test.status = (
                            VerificationStatus.PASS
                            if str(test.actual_value).lower()
                               == str(test.expected_value).lower()
                            else VerificationStatus.FAIL
                        )
            elif test.status == VerificationStatus.NOT_TESTED:
                test.status = VerificationStatus.NOT_TESTED

        vr.tests = tests
        vr.passed = sum(1 for t in tests if t.status == VerificationStatus.PASS)
        vr.failed = sum(1 for t in tests if t.status == VerificationStatus.FAIL)
        vr.warnings = sum(1 for t in tests if t.status == VerificationStatus.WARNING)
        vr.not_tested = sum(1 for t in tests if t.status == VerificationStatus.NOT_TESTED)
        vr.hitl_required_count = sum(1 for t in tests if t.hitl_required)

        # Overall status
        if vr.failed > 0:
            vr.overall_status = VerificationStatus.FAIL
            vr.compliance_flags.append(
                f"{vr.failed} test(s) FAILED — HITL review required before final acceptance"
            )
        elif vr.not_tested > 0:
            vr.overall_status = VerificationStatus.WARNING
            vr.compliance_flags.append(
                f"{vr.not_tested} test(s) not yet executed — commissioning incomplete"
            )
        else:
            vr.overall_status = VerificationStatus.PASS

        if vr.hitl_required_count > 0:
            vr.compliance_flags.append(
                f"{vr.hitl_required_count} test(s) require HITL sign-off "
                f"(CxA / P.E. per ASHRAE Guideline 0)"
            )

        total = max(len(tests), 1)
        pass_rate = round(vr.passed / total * 100, 1)
        vr.summary = (
            f"Commissioning verification: {vr.passed}/{total} passed ({pass_rate}%). "
            f"Failed: {vr.failed}. "
            f"Not tested: {vr.not_tested}. "
            f"HITL sign-offs required: {vr.hitl_required_count}."
        )

        self._audit("verify_commissioning",
                    result_id=vr.result_id,
                    passed=vr.passed,
                    failed=vr.failed,
                    overall=vr.overall_status.value)
        logger.info(
            "CSE-001 verify_commissioning %s: %s pass=%d fail=%d hitl=%d",
            vr.result_id, vr.overall_status.value,
            vr.passed, vr.failed, vr.hitl_required_count,
        )
        return vr

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def export_device_configs_json(self, configs: List[DeviceConfig]) -> str:
        """Export device configs as a JSON string."""
        return json.dumps(
            [c.to_dict() for c in configs], indent=2, default=str
        )

    def export_wiring_diagram(self, diag: WiringDiagram, fmt: str = "markdown") -> str:
        """Export wiring diagram as markdown or wire-list CSV."""
        if fmt == "csv":
            return diag.wire_list_csv
        return diag.markdown_render

    def export_verification_report(self, vr: VerificationResult) -> str:
        """Export commissioning verification as a Markdown report."""
        lines = [
            "# Commissioning Verification Report",
            "",
            f"**Project:** {vr.project_name or 'N/A'}",
            f"**Report ID:** {vr.result_id}",
            f"**Generated:** {vr.generated_at}",
            f"**Overall Status:** {vr.overall_status.value.upper()}",
            "",
            "## Summary",
            "",
            vr.summary,
            "",
        ]
        if vr.compliance_flags:
            lines += ["## Compliance Flags", ""]
            for flag in vr.compliance_flags:
                lines.append(f"- ⚠ {flag}")
            lines.append("")

        lines += ["## Test Results", ""]
        lines += [
            "| # | Tag | Type | Description | Expected | Actual | Status | HITL |",
            "|---|-----|------|-------------|----------|--------|--------|------|",
        ]
        for i, t in enumerate(vr.tests[:200]):
            status_icon = {
                "pass": "✅", "fail": "❌", "warning": "⚠",
                "not_tested": "⬜", "hitl_required": "👤",
            }.get(t.status.value, "❓")
            hitl_icon = "👤" if t.hitl_required else ""
            lines.append(
                f"| {i+1} | {t.equipment_tag} | {t.test_type} "
                f"| {t.test_description[:60]} "
                f"| {t.expected_value} {t.expected_units} "
                f"| {t.actual_value or '—'} "
                f"| {status_icon} {t.status.value} "
                f"| {hitl_icon} |"
            )
        return "\n".join(lines)

    def get_cutsheet(self, cutsheet_id: str) -> Optional[CutSheetSpec]:
        with self._lock:
            return self._library.get(cutsheet_id)

    def list_cutsheets(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "cutsheet_id": cs.cutsheet_id,
                    "manufacturer": cs.manufacturer,
                    "model_number": cs.model_number,
                    "category": cs.category.value,
                    "confidence": cs.parse_confidence,
                }
                for cs in self._library.values()
            ]

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_terminals_from_io(io: IOSpec) -> List[WiringTerminal]:
        """Generate wiring terminal list from I/O spec."""
        terminals: List[WiringTerminal] = []
        for i in range(io.ai_count):
            terminals.append(WiringTerminal(
                terminal_id=f"AI{i+1}+",
                label=f"Analog Input {i+1} (+)",
                signal_type="AI",
                wire_gauge_awg="18 AWG",
                notes="Shielded, 4-20mA or 0-10V; ground shield at controller",
            ))
        for i in range(io.ao_count):
            terminals.append(WiringTerminal(
                terminal_id=f"AO{i+1}",
                label=f"Analog Output {i+1}",
                signal_type="AO",
                wire_gauge_awg="18 AWG",
                notes="0-10V or 4-20mA signal; shielded",
            ))
        for i in range(io.bi_count):
            terminals.append(WiringTerminal(
                terminal_id=f"BI{i+1}",
                label=f"Binary Input {i+1}",
                signal_type="BI",
                wire_gauge_awg="18 AWG",
                notes="Dry contact or 0/24V",
            ))
        for i in range(io.bo_count):
            terminals.append(WiringTerminal(
                terminal_id=f"BO{i+1}",
                label=f"Binary Output {i+1}",
                signal_type="BO",
                wire_gauge_awg="18 AWG",
                notes="Relay output 24VAC/DC or triac",
            ))
        terminals.append(WiringTerminal(
            terminal_id="PWR+", label="24 VAC/VDC Power (+)",
            signal_type="PWR", wire_gauge_awg="14 AWG"))
        terminals.append(WiringTerminal(
            terminal_id="COM", label="Common / Ground",
            signal_type="GND", wire_gauge_awg="14 AWG"))
        if "BACnet MS/TP" in io.supported_protocols or not io.supported_protocols:
            terminals.append(WiringTerminal(
                terminal_id="NET+", label="MS/TP Network (+)",
                signal_type="RS485", wire_gauge_awg="22 AWG",
                notes="Shielded twisted pair, 120Ω termination at segment ends"))
            terminals.append(WiringTerminal(
                terminal_id="NET-", label="MS/TP Network (-)",
                signal_type="RS485", wire_gauge_awg="22 AWG"))
        return terminals

    @staticmethod
    def _generate_program_stub(
        cfg: DeviceConfig,
        sensors: List[CutSheetSpec],
        actuators: List[CutSheetSpec],
    ) -> str:
        """Generate a structured-text control program skeleton."""
        lines = [
            "(* BACnet Controller Program Stub",
            f"   Device: {cfg.device_name}",
            f"   Profile: {cfg.bacnet_device_profile}",
            "   Generated by Murphy System CSE-001",
            "   Requires review and commissioning by licensed controls engineer *)",
            "",
            f"PROGRAM {cfg.device_name.replace('-', '_')}",
            "",
            "(* ── Variable declarations ── *)",
        ]

        for obj in cfg.objects[:30]:
            safe_name = re.sub(r"[^A-Za-z0-9_]", "_", obj.object_name)
            if "Input" in obj.object_type:
                lines.append(f"  {safe_name} : REAL; (* {obj.description[:60]} *)")
            else:
                lines.append(f"  {safe_name}_CMD : REAL; (* {obj.description[:60]} *)")

        lines += [
            "",
            "(* ── Main control loop ── *)",
            "BEGIN",
            "  (* TODO: Implement sequences of operations per spec *)",
        ]

        if sensors:
            lines.append("  (* Read sensor inputs *)")
            for i, s in enumerate(sensors[:8]):
                safe_name = f"AI_{i+1:03d}_{s.category.value[:6].upper()}"
                lines.append(
                    f"  {safe_name} := BACnet_Read(AI, {i+1}); "
                    f"(* {s.manufacturer} {s.model_number} *)"
                )

        if actuators:
            lines.append("  (* Write actuator outputs *)")
            for i, a in enumerate(actuators[:4]):
                safe_name = f"AO_{i+1:03d}_{a.category.value[:5].upper()}"
                lines.append(
                    f"  BACnet_Write(AO, {i+1}, {safe_name}_CMD); "
                    f"(* {a.manufacturer} {a.model_number} *)"
                )

        lines += [
            "",
            "END",
            "",
            "(* END PROGRAM *)",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_wiring_markdown(diag: WiringDiagram) -> str:
        lines = [
            f"# {diag.title}",
            f"**Project:** {diag.project_name}  **Rev:** {diag.revision}",
            f"**Generated:** {diag.generated_at}",
            "",
            "## Device List",
            "",
            "| Tag | Manufacturer | Model | Category | Power |",
            "|-----|-------------|-------|----------|-------|",
        ]
        for dev in diag.devices:
            lines.append(
                f"| {dev['tag']} | {dev['manufacturer']} | {dev['model']} "
                f"| {dev['category']} | {dev['power']} |"
            )

        lines += ["", "## Panel Schedule", "",
                  "| Tag | Description | Manufacturer | Model | Power (VA) | Enclosure | Certs |",
                  "|-----|-------------|-------------|-------|-----------|-----------|-------|"]
        for ps in diag.panel_schedule:
            lines.append(
                f"| {ps['tag']} | {ps['description'][:40]} | {ps['manufacturer']} "
                f"| {ps['model']} | {ps['power_va']} | {ps['enclosure']} "
                f"| {ps['certifications'][:30]} |"
            )

        lines += ["", "## Wire List", "",
                  "| Wire ID | From Device | From Terminal | To Device | To Terminal "
                  "| Signal | Gauge | Shield |",
                  "|---------|------------|--------------|----------|-------------|"
                  "-------|-------|--------|"]
        for w in diag.wire_list[:100]:
            lines.append(
                f"| {w['wire_id']} | {w['from_device']} | {w['from_terminal']} "
                f"| {w['to_device']} | {w['to_terminal']} | {w['signal']} "
                f"| {w['wire_gauge']} | {'Yes' if w['shield'] else 'No'} |"
            )

        lines += ["", "## Wiring Notes", ""]
        for note in diag.notes:
            lines.append(f"- {note}")
        return "\n".join(lines)

    @staticmethod
    def _render_wire_list_csv(diag: WiringDiagram) -> str:
        rows = ["Wire ID,From Device,From Terminal,To Device,To Terminal,"
                "Signal,Wire Gauge,Shield"]
        for w in diag.wire_list:
            rows.append(
                f"{w['wire_id']},{w['from_device']},{w['from_terminal']},"
                f"{w['to_device']},{w['to_terminal']},{w['signal']},"
                f"{w['wire_gauge']},{'Yes' if w['shield'] else 'No'}"
            )
        return "\n".join(rows)

    @staticmethod
    def _render_network_ascii(
        controllers: List[CutSheetSpec],
        all_devices: List[CutSheetSpec],
    ) -> str:
        lines = [
            "BMS NETWORK ARCHITECTURE",
            "========================",
            "",
            "  [OPERATOR WORKSTATION]",
            "         |",
            "   [BACnet/IP LAN - 1 Gbps Ethernet VLAN]",
            "         |",
        ]
        for i, ctrl in enumerate(controllers[:4]):
            lines.append(f"   [CTRL-{i+1:02d}: {ctrl.manufacturer} {ctrl.model_number}]")
            lines.append("         |-- BACnet MS/TP Bus")
            sensor_count = sum(
                1 for d in all_devices if "sensor" in d.category.value
            )
            lines.append(f"         |   +-- {sensor_count} Field Devices (Sensors/Actuators)")
            lines.append("         |")
        lines += ["", "(Generated by Murphy System CSE-001 — for reference only)"]
        return "\n".join(lines)

    @staticmethod
    def _render_control_markdown(diag: ControlDiagram) -> str:
        lines = [
            f"# {diag.title}",
            f"**Project:** {diag.project_name}  **Rev:** {diag.revision}",
            f"**Systems:** {', '.join(diag.systems_covered)}",
            "",
            "## Network Architecture",
            "```",
            diag.network_diagram_text,
            "```",
            "",
            "## Control Loops",
        ]
        for loop in diag.control_loops:
            lines += [
                "",
                f"### {loop['controller_tag']} — {loop.get('manufacturer', '')} "
                f"{loop.get('model', '')}",
                f"**BACnet Profile:** {loop.get('bacnet_profile', 'N/A')}",
                f"**I/O:** {loop.get('io_summary', {})}",
                "",
                "**Connected Sensors:**",
            ]
            for s in loop.get("connected_sensors", []):
                lines.append(f"- `{s['tag']}` {s['type']} — {s['model']} "
                              f"Range: {s['range']} Output: {s['output']}")
            lines.append("\n**Connected Actuators:**")
            for a in loop.get("connected_actuators", []):
                lines.append(f"- `{a['tag']}` {a['type']} — {a['model']} "
                              f"Torque: {a['torque']} Fail-Safe: {a['fail_safe']}")

        lines += ["", "## Interlocks", ""]
        for il in diag.interlocks:
            lines += [
                f"### {il['interlock']}",
                f"**Condition:** {il['condition']}",
                f"**Action:** {il['action']}",
                f"**Override:** {il.get('override', 'N/A')}",
                f"**Priority:** {il.get('priority', 2)}",
                "",
            ]
        return "\n".join(lines)

    def _audit(self, action: str, **kwargs: Any) -> None:
        entry = {"action": action, "timestamp": _ts(), **kwargs}
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)
