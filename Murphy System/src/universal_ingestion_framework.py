"""
Universal Ingestion Framework

An extensible adapter registry for ingesting data from ANY automation system.
Supports infinite extensibility with adapter pattern for BACnet, Modbus, OPC UA,
MQTT, Grainger catalogs, and generic formats.
"""

import csv
import io
import json
import logging
import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IngestionFormat(Enum):
    """Supported ingestion formats"""
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    EDE = "ede"
    EXCEL = "excel"
    MODBUS_REGISTER_MAP = "modbus_register_map"
    OPCUA_NODESET = "opcua_nodeset"
    MQTT_SCHEMA = "mqtt_schema"
    BACNET_EDE = "bacnet_ede"
    PROFINET_GSDML = "profinet_gsdml"
    ETHERNETIP_EDS = "ethernetip_eds"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ComponentRecommendation:
    """Component recommendation with Grainger catalog integration"""
    part_number: str
    manufacturer: str
    description: str
    category: str
    application: str
    price_tier: str  # "economy"/"standard"/"premium"
    specifications: Dict[str, Any]
    grainger_category: str
    industry_standard: bool
    why_recommended: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "part_number": self.part_number,
            "manufacturer": self.manufacturer,
            "description": self.description,
            "category": self.category,
            "application": self.application,
            "price_tier": self.price_tier,
            "specifications": self.specifications,
            "grainger_category": self.grainger_category,
            "industry_standard": self.industry_standard,
            "why_recommended": self.why_recommended
        }


@dataclass
class IngestionResult:
    """Result of ingestion operation"""
    result_id: str
    adapter_name: str
    format_used: str
    records_ingested: int
    records_failed: int
    warnings: List[str]
    equipment_specs: List[Dict[str, Any]]
    component_recommendations: List[Dict[str, Any]]
    raw_data: Dict[str, Any]
    ingested_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "result_id": self.result_id,
            "adapter_name": self.adapter_name,
            "format_used": self.format_used,
            "records_ingested": self.records_ingested,
            "records_failed": self.records_failed,
            "warnings": self.warnings,
            "equipment_specs": self.equipment_specs,
            "component_recommendations": self.component_recommendations,
            "raw_data": self.raw_data,
            "ingested_at": self.ingested_at
        }

    def summary(self) -> str:
        """Generate summary string"""
        return (
            f"Ingestion {self.result_id}: {self.adapter_name} "
            f"processed {self.records_ingested} records ({self.records_failed} failed) "
            f"using {self.format_used} format at {self.ingested_at}"
        )


# ---------------------------------------------------------------------------
# Grainger Best Sellers Catalog
# ---------------------------------------------------------------------------

GRAINGER_BEST_SELLERS = {
    "temperature_sensors": [
        ComponentRecommendation(
            part_number="6FLF8", manufacturer="Dwyer",
            description="Duct Temperature Sensor, NTC 10K, 4-inch probe",
            category="temperature_sensor", application="duct_air_temperature",
            price_tier="standard",
            specifications={"type": "NTC 10K", "range": "-40 to 250°F", "accuracy": "±0.5°F"},
            grainger_category="HVAC Controls & Thermostats",
            industry_standard=True,
            why_recommended="ASHRAE 62.1 requires supply air temp monitoring"
        ),
        ComponentRecommendation(
            part_number="2E372", manufacturer="Johnson Controls",
            description="Immersion Temperature Sensor, 1000 ohm platinum RTD",
            category="temperature_sensor", application="water_temperature",
            price_tier="premium",
            specifications={"type": "RTD Pt1000", "range": "-40 to 250°F", "accuracy": "±0.1°F"},
            grainger_category="HVAC Controls & Thermostats",
            industry_standard=True,
            why_recommended="High accuracy for chilled water loops per ASHRAE 90.1"
        ),
        ComponentRecommendation(
            part_number="3FLN9", manufacturer="Honeywell",
            description="Room Temperature Sensor, 10K Type II thermistor",
            category="temperature_sensor", application="room_temperature",
            price_tier="economy",
            specifications={"type": "10K Thermistor", "range": "32 to 120°F", "accuracy": "±1°F"},
            grainger_category="HVAC Controls & Thermostats",
            industry_standard=True,
            why_recommended="Standard zone control per ASHRAE 55 comfort requirements"
        ),
    ],
    "pressure_sensors": [
        ComponentRecommendation(
            part_number="4TMP5", manufacturer="Setra",
            description="Differential Pressure Transmitter, 0-1 inch WC",
            category="pressure_sensor", application="filter_monitoring",
            price_tier="standard",
            specifications={"range": "0-1 inch WC", "output": "4-20mA", "accuracy": "±0.5%"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="Filter maintenance per ASHRAE 62.1 ventilation requirements"
        ),
        ComponentRecommendation(
            part_number="2RLL6", manufacturer="Dwyer",
            description="Static Pressure Sensor, 0-5 inch WC, 0-10VDC output",
            category="pressure_sensor", application="duct_static_pressure",
            price_tier="economy",
            specifications={"range": "0-5 inch WC", "output": "0-10VDC", "accuracy": "±1%"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="VAV duct static pressure control ASHRAE Guideline 36"
        ),
        ComponentRecommendation(
            part_number="5ZLK3", manufacturer="Honeywell",
            description="Pressure Transducer, 0-300 PSI, modbus output",
            category="pressure_sensor", application="hydronic_pressure",
            price_tier="premium",
            specifications={"range": "0-300 PSI", "output": "Modbus RTU", "accuracy": "±0.25%"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="Pump control and hydronic system monitoring"
        ),
    ],
    "flow_meters": [
        ComponentRecommendation(
            part_number="4YLC2", manufacturer="Badger Meter",
            description="Electromagnetic Flow Meter, 2-inch, pulse output",
            category="flow_meter", application="chilled_water_flow",
            price_tier="premium",
            specifications={"size": "2 inch", "output": "pulse + 4-20mA", "accuracy": "±0.5%"},
            grainger_category="Flow Meters",
            industry_standard=True,
            why_recommended="Chilled water energy metering ASHRAE 90.1 M&V"
        ),
        ComponentRecommendation(
            part_number="6DWK1", manufacturer="Onicon",
            description="BTU Meter, ultrasonic, 1-inch",
            category="flow_meter", application="thermal_energy_metering",
            price_tier="premium",
            specifications={"size": "1 inch", "output": "BACnet", "accuracy": "±1%"},
            grainger_category="Flow Meters",
            industry_standard=True,
            why_recommended="Energy measurement for LEED and utility billing"
        ),
        ComponentRecommendation(
            part_number="2HLN6", manufacturer="Dwyer",
            description="Paddlewheel Flow Switch, 2-inch",
            category="flow_meter", application="flow_proving",
            price_tier="economy",
            specifications={"size": "2 inch", "output": "dry contact", "accuracy": "±5%"},
            grainger_category="Flow Meters",
            industry_standard=False,
            why_recommended="Low cost flow proving for pump status"
        ),
    ],
    "vfds": [
        ComponentRecommendation(
            part_number="2XKM7", manufacturer="ABB",
            description="Variable Frequency Drive, 10HP, 480V",
            category="vfd", application="fan_motor_control",
            price_tier="premium",
            specifications={"hp": 10, "voltage": "480V 3-phase", "features": "BACnet, bypass"},
            grainger_category="Variable Frequency Drives",
            industry_standard=True,
            why_recommended="ASHRAE 90.1 requires VFD on fans >5HP"
        ),
        ComponentRecommendation(
            part_number="4YWP9", manufacturer="Schneider Electric",
            description="VFD, 5HP, 208-230V, compact",
            category="vfd", application="pump_motor_control",
            price_tier="standard",
            specifications={"hp": 5, "voltage": "208-230V 3-phase", "features": "Modbus RTU"},
            grainger_category="Variable Frequency Drives",
            industry_standard=True,
            why_recommended="Pump energy savings 30-50% vs constant speed"
        ),
        ComponentRecommendation(
            part_number="1HMC3", manufacturer="Yaskawa",
            description="VFD, 3HP, 230V, general purpose",
            category="vfd", application="general_motor_control",
            price_tier="economy",
            specifications={"hp": 3, "voltage": "230V 3-phase", "features": "0-10V input"},
            grainger_category="Variable Frequency Drives",
            industry_standard=True,
            why_recommended="Cost-effective motor speed control"
        ),
    ],
    "power_meters": [
        ComponentRecommendation(
            part_number="6ZWL4", manufacturer="Schneider Electric",
            description="PowerLogic PM8000, revenue grade, modbus",
            category="power_meter", application="utility_metering",
            price_tier="premium",
            specifications={"accuracy": "IEC 62053-22 Class 0.2S", "output": "Modbus TCP, BACnet"},
            grainger_category="Power Meters",
            industry_standard=True,
            why_recommended="Revenue grade metering per ASHRAE 90.1 and LEED"
        ),
        ComponentRecommendation(
            part_number="3DPM2", manufacturer="Siemens",
            description="SENTRON PAC3200, submetering panel meter",
            category="power_meter", application="submetering",
            price_tier="standard",
            specifications={"accuracy": "Class 1", "output": "Modbus RTU"},
            grainger_category="Power Meters",
            industry_standard=True,
            why_recommended="Equipment level submetering for energy analysis"
        ),
        ComponentRecommendation(
            part_number="7YKC1", manufacturer="Veris",
            description="Basic power meter, CT input, pulse output",
            category="power_meter", application="monitoring",
            price_tier="economy",
            specifications={"accuracy": "±2%", "output": "pulse"},
            grainger_category="Power Meters",
            industry_standard=False,
            why_recommended="Low cost trend data for BAS systems"
        ),
    ],
    "actuators": [
        ComponentRecommendation(
            part_number="1ZPN4", manufacturer="Belimo",
            description="Spring Return Actuator, 24VAC, 90 sec, 35 in-lb",
            category="actuator", application="vav_damper",
            price_tier="premium",
            specifications={"voltage": "24VAC", "timing": "90 sec", "torque": "35 in-lb"},
            grainger_category="HVAC Actuators",
            industry_standard=True,
            why_recommended="VAV box control per ASHRAE Guideline 36"
        ),
        ComponentRecommendation(
            part_number="4HLC9", manufacturer="Honeywell",
            description="Modulating Actuator, 24V, 120 sec, floating control",
            category="actuator", application="valve_control",
            price_tier="standard",
            specifications={"voltage": "24VAC/DC", "timing": "120 sec", "control": "floating"},
            grainger_category="HVAC Actuators",
            industry_standard=True,
            why_recommended="Chilled/hot water valve modulation"
        ),
        ComponentRecommendation(
            part_number="2GLK7", manufacturer="Johnson Controls",
            description="Proportional Actuator, 0-10VDC input",
            category="actuator", application="general_damper",
            price_tier="economy",
            specifications={"voltage": "24VAC", "timing": "60 sec", "control": "0-10VDC"},
            grainger_category="HVAC Actuators",
            industry_standard=True,
            why_recommended="General purpose damper control"
        ),
    ],
    "co2_sensors": [
        ComponentRecommendation(
            part_number="3NMK6", manufacturer="Telaire",
            description="CO2 Sensor, 0-2000 ppm, NDIR, 4-20mA output",
            category="co2_sensor", application="demand_controlled_ventilation",
            price_tier="standard",
            specifications={"range": "0-2000 ppm", "technology": "NDIR", "output": "4-20mA"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="DCV per ASHRAE 62.1 and 90.1 for occupancy"
        ),
        ComponentRecommendation(
            part_number="6YLC4", manufacturer="Greystone",
            description="Wall Mount CO2 Sensor, 0-2000 ppm, BACnet",
            category="co2_sensor", application="indoor_air_quality",
            price_tier="premium",
            specifications={"range": "0-2000 ppm", "technology": "NDIR", "output": "BACnet MS/TP"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="IAQ monitoring for LEED and WELL Building"
        ),
        ComponentRecommendation(
            part_number="1HMN2", manufacturer="Veris",
            description="Duct CO2 Sensor, 0-2000 ppm, 0-10VDC",
            category="co2_sensor", application="outdoor_air_monitoring",
            price_tier="economy",
            specifications={"range": "0-2000 ppm", "technology": "NDIR", "output": "0-10VDC"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="Economizer control outdoor air quality"
        ),
    ],
    "controllers": [
        ComponentRecommendation(
            part_number="5ZLP8", manufacturer="Honeywell",
            description="Spyder Controller, 16 I/O, BACnet, web server",
            category="controller", application="vav_control",
            price_tier="premium",
            specifications={"io": "16 universal", "protocol": "BACnet IP/MSTP", "features": "web"},
            grainger_category="HVAC Controllers",
            industry_standard=True,
            why_recommended="VAV zone control ASHRAE Guideline 36 sequences"
        ),
        ComponentRecommendation(
            part_number="2DKM9", manufacturer="Siemens",
            description="APOGEE PXC Controller, 12 I/O, BACnet",
            category="controller", application="ahu_control",
            price_tier="premium",
            specifications={"io": "12 universal", "protocol": "BACnet IP", "features": "trending"},
            grainger_category="HVAC Controllers",
            industry_standard=True,
            why_recommended="AHU control with economizer and DCV"
        ),
        ComponentRecommendation(
            part_number="7HMC1", manufacturer="Schneider Electric",
            description="TAC Controller, 8 I/O, modbus",
            category="controller", application="equipment_control",
            price_tier="standard",
            specifications={"io": "8 universal", "protocol": "Modbus RTU", "features": "basic"},
            grainger_category="HVAC Controllers",
            industry_standard=True,
            why_recommended="General equipment control applications"
        ),
    ],
    "humidity_sensors": [
        ComponentRecommendation(
            part_number="4GLC2", manufacturer="Honeywell",
            description="Duct Humidity Sensor, 0-100% RH, 4-20mA",
            category="humidity_sensor", application="duct_humidity",
            price_tier="standard",
            specifications={"range": "0-100% RH", "accuracy": "±2%", "output": "4-20mA"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="Humidity control per ASHRAE 55 comfort"
        ),
        ComponentRecommendation(
            part_number="6YMN1", manufacturer="Greystone",
            description="Room Humidity Sensor with temperature",
            category="humidity_sensor", application="room_conditions",
            price_tier="standard",
            specifications={"range": "0-100% RH", "accuracy": "±3%", "output": "0-10VDC"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=True,
            why_recommended="Zone comfort monitoring"
        ),
        ComponentRecommendation(
            part_number="1NMK4", manufacturer="Veris",
            description="Outdoor Humidity Sensor, weatherproof",
            category="humidity_sensor", application="outdoor_conditions",
            price_tier="economy",
            specifications={"range": "0-100% RH", "accuracy": "±5%", "output": "0-10VDC"},
            grainger_category="HVAC Controls & Sensors",
            industry_standard=False,
            why_recommended="Economizer and enthalpy control"
        ),
    ],
    "valves": [
        ComponentRecommendation(
            part_number="3WLP9", manufacturer="Belimo",
            description="2-way Control Valve, 1-inch, characterized ball",
            category="valve", application="hydronic_control",
            price_tier="premium",
            specifications={"size": "1 inch", "type": "2-way ball", "cv": 7.5},
            grainger_category="HVAC Valves",
            industry_standard=True,
            why_recommended="Chilled/hot water modulating control"
        ),
        ComponentRecommendation(
            part_number="5HMK7", manufacturer="Honeywell",
            description="3-way Mixing Valve, 1-inch",
            category="valve", application="temperature_control",
            price_tier="standard",
            specifications={"size": "1 inch", "type": "3-way", "cv": 6.3},
            grainger_category="HVAC Valves",
            industry_standard=True,
            why_recommended="Temperature mixing applications"
        ),
        ComponentRecommendation(
            part_number="2DLC3", manufacturer="Siemens",
            description="Globe Valve, 2-inch, equal percentage",
            category="valve", application="flow_control",
            price_tier="standard",
            specifications={"size": "2 inch", "type": "globe", "cv": 20},
            grainger_category="HVAC Valves",
            industry_standard=True,
            why_recommended="General hydronic flow control"
        ),
    ],
    "occupancy_sensors": [
        ComponentRecommendation(
            part_number="6ZMN4", manufacturer="Leviton",
            description="PIR Occupancy Sensor, ceiling mount, 360°",
            category="occupancy_sensor", application="lighting_control",
            price_tier="economy",
            specifications={"coverage": "360°", "range": "1000 sqft", "output": "relay"},
            grainger_category="Lighting Controls",
            industry_standard=True,
            why_recommended="ASHRAE 90.1 lighting control requirement"
        ),
        ComponentRecommendation(
            part_number="4HLK1", manufacturer="Lutron",
            description="Dual Tech Sensor, PIR+ultrasonic, wall switch",
            category="occupancy_sensor", application="hvac_setback",
            price_tier="standard",
            specifications={"coverage": "180°", "range": "500 sqft", "output": "0-10VDC"},
            grainger_category="Lighting Controls",
            industry_standard=True,
            why_recommended="HVAC unoccupied setback control"
        ),
        ComponentRecommendation(
            part_number="2YLC8", manufacturer="Honeywell",
            description="Wireless Occupancy Sensor, BACnet",
            category="occupancy_sensor", application="building_automation",
            price_tier="premium",
            specifications={"coverage": "360°", "range": "1200 sqft", "output": "BACnet wireless"},
            grainger_category="Lighting Controls",
            industry_standard=True,
            why_recommended="Wireless retrofit for demand-based control"
        ),
    ],
}


INDUSTRY_STANDARD_COMPONENTS = {
    "AHU": [
        ComponentRecommendation(
            part_number="AHU-PKG-01", manufacturer="Various",
            description="AHU Control Package: controller, sensors, actuators",
            category="control_package", application="air_handling_unit",
            price_tier="premium",
            specifications={"components": "controller, temp/pressure/CO2 sensors, damper/valve actuators"},
            grainger_category="HVAC Controls",
            industry_standard=True,
            why_recommended="Complete AHU control per ASHRAE Guideline 36"
        ),
    ],
    "chiller": [
        ComponentRecommendation(
            part_number="CHW-MTR-01", manufacturer="Onicon",
            description="Chiller Energy Meter Package",
            category="metering_package", application="chiller_plant",
            price_tier="premium",
            specifications={"components": "BTU meter, temperature sensors, flow meter"},
            grainger_category="Flow Meters",
            industry_standard=True,
            why_recommended="Chiller plant efficiency monitoring ASHRAE 90.1"
        ),
    ],
    "boiler": [
        ComponentRecommendation(
            part_number="BLR-CTL-01", manufacturer="Honeywell",
            description="Boiler Control Package with O2 trim",
            category="control_package", application="boiler",
            price_tier="premium",
            specifications={"components": "controller, O2 sensor, flame safeguard, VFD"},
            grainger_category="Boiler Controls",
            industry_standard=True,
            why_recommended="Combustion efficiency 3-5% improvement"
        ),
    ],
}


# ---------------------------------------------------------------------------
# Abstract Base Adapter
# ---------------------------------------------------------------------------

class IngestionAdapter(ABC):
    """Abstract base class for ingestion adapters"""
    name: str = "base"
    supported_formats: List[IngestionFormat] = []

    @abstractmethod
    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if this adapter can handle the content"""
        pass

    @abstractmethod
    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest content and return result"""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Return field schema for this adapter"""
        return {"fields": [], "description": "No schema defined"}

    def get_component_recommendations(self, equipment_type: str) -> List[ComponentRecommendation]:
        """Get component recommendations for equipment type"""
        equipment_lower = equipment_type.lower()
        recommendations = []
        
        for category, items in GRAINGER_BEST_SELLERS.items():
            for rec in items:
                if equipment_lower in rec.application.lower() or equipment_lower in rec.category.lower():
                    recommendations.append(rec)
        
        for category, items in INDUSTRY_STANDARD_COMPONENTS.items():
            if equipment_lower in category.lower():
                recommendations.extend(items)
        
        return recommendations


# ---------------------------------------------------------------------------
# Concrete Adapters
# ---------------------------------------------------------------------------

class BACnetEDEAdapter(IngestionAdapter):
    """BACnet EDE (Engineering Data Exchange) tab-delimited format adapter"""
    name = "bacnet_ede"
    supported_formats = [IngestionFormat.BACNET_EDE, IngestionFormat.EDE]

    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if content is BACnet EDE format"""
        if filename.lower().endswith('.ede') or filename.lower().endswith('.csv'):
            lines = content.strip().split('\n')
            if len(lines) > 0:
                first_line = lines[0].lower()
                return '#object-name' in first_line or 'object-name' in first_line
        return False

    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest BACnet EDE content"""
        result_id = str(uuid.uuid4())
        warnings = []
        equipment_specs = []
        records_ingested = 0
        records_failed = 0

        try:
            lines = content.strip().split('\n')
            if not lines:
                raise ValueError("Empty EDE content")

            header = None
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    if header is None and line.startswith('#'):
                        header_parts = line.lstrip('#').split('\t')
                        header = [h.strip().lower() for h in header_parts]
                    continue

                if header is None:
                    warnings.append("No header found, using default")
                    header = ['object-name', 'object-type', 'object-instance', 'units']

                parts = line.split('\t')
                if len(parts) < len(header):
                    records_failed += 1
                    continue

                spec = {}
                for i, col in enumerate(header):
                    if i < len(parts):
                        spec[col] = parts[i].strip()

                equipment_specs.append(spec)
                records_ingested += 1

        except Exception as e:
            logger.error(f"EDE ingestion error: {e}")
            warnings.append(str(e))

        return IngestionResult(
            result_id=result_id,
            adapter_name=self.name,
            format_used=IngestionFormat.BACNET_EDE.value,
            records_ingested=records_ingested,
            records_failed=records_failed,
            warnings=warnings,
            equipment_specs=equipment_specs,
            component_recommendations=[],
            raw_data={"content_length": len(content)},
            ingested_at=datetime.now(timezone.utc).isoformat()
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return EDE schema"""
        return {
            "fields": ["object-name", "object-type", "object-instance", "units-code", "description"],
            "description": "BACnet EDE tab-delimited format"
        }


class ModbusRegisterMapAdapter(IngestionAdapter):
    """Modbus register map CSV adapter"""
    name = "modbus_register_map"
    supported_formats = [IngestionFormat.MODBUS_REGISTER_MAP, IngestionFormat.CSV]

    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if content is Modbus register map"""
        lines = content.strip().split('\n')
        if lines:
            first_line = lines[0].lower()
            modbus_keywords = ['address', 'register', 'modbus', 'holding', 'coil']
            return any(kw in first_line for kw in modbus_keywords)
        return False

    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest Modbus register map"""
        result_id = str(uuid.uuid4())
        warnings = []
        equipment_specs = []
        records_ingested = 0
        records_failed = 0

        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                if not row:
                    continue
                    
                spec = {
                    "address": row.get("address", ""),
                    "register_type": row.get("register_type", row.get("type", "")),
                    "description": row.get("description", ""),
                    "units": row.get("units", ""),
                    "scale_factor": row.get("scale_factor", "1"),
                    "data_type": row.get("data_type", "uint16")
                }
                
                if spec["address"]:
                    equipment_specs.append(spec)
                    records_ingested += 1
                else:
                    records_failed += 1

        except Exception as e:
            logger.error(f"Modbus ingestion error: {e}")
            warnings.append(str(e))

        return IngestionResult(
            result_id=result_id,
            adapter_name=self.name,
            format_used=IngestionFormat.MODBUS_REGISTER_MAP.value,
            records_ingested=records_ingested,
            records_failed=records_failed,
            warnings=warnings,
            equipment_specs=equipment_specs,
            component_recommendations=[],
            raw_data={"content_length": len(content)},
            ingested_at=datetime.now(timezone.utc).isoformat()
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return Modbus register map schema"""
        return {
            "fields": ["address", "register_type", "description", "units", "scale_factor", "data_type"],
            "description": "Modbus register map CSV format"
        }


class OpcUaNodeSetAdapter(IngestionAdapter):
    """OPC UA NodeSet2 XML adapter"""
    name = "opcua_nodeset"
    supported_formats = [IngestionFormat.OPCUA_NODESET, IngestionFormat.XML]

    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if content is OPC UA NodeSet"""
        if filename.lower().endswith('.xml'):
            return 'UANodeSet' in content or 'NodeSet2' in content
        return False

    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest OPC UA NodeSet"""
        result_id = str(uuid.uuid4())
        warnings = []
        equipment_specs = []
        records_ingested = 0
        records_failed = 0

        try:
            root = ET.fromstring(content)
            
            namespaces = {'ua': 'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'}
            
            for node in root.findall('.//ua:UAVariable', namespaces):
                try:
                    spec = {
                        "node_id": node.get('NodeId', ''),
                        "browse_name": node.get('BrowseName', ''),
                        "data_type": node.get('DataType', ''),
                        "display_name": ""
                    }
                    
                    display = node.find('ua:DisplayName', namespaces)
                    if display is not None:
                        spec["display_name"] = display.text or ""
                    
                    equipment_specs.append(spec)
                    records_ingested += 1
                except Exception:
                    records_failed += 1

        except Exception as e:
            logger.error(f"OPC UA ingestion error: {e}")
            warnings.append(str(e))

        return IngestionResult(
            result_id=result_id,
            adapter_name=self.name,
            format_used=IngestionFormat.OPCUA_NODESET.value,
            records_ingested=records_ingested,
            records_failed=records_failed,
            warnings=warnings,
            equipment_specs=equipment_specs,
            component_recommendations=[],
            raw_data={"content_length": len(content)},
            ingested_at=datetime.now(timezone.utc).isoformat()
        )


class GenericCSVAdapter(IngestionAdapter):
    """Generic CSV adapter with auto-mapping"""
    name = "generic_csv"
    supported_formats = [IngestionFormat.CSV]

    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if content is generic CSV"""
        if filename.lower().endswith('.csv'):
            return True
        lines = content.strip().split('\n')
        if lines and ',' in lines[0]:
            return True
        return False

    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest generic CSV"""
        result_id = str(uuid.uuid4())
        warnings = []
        equipment_specs = []
        records_ingested = 0
        records_failed = 0

        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                if row:
                    equipment_specs.append(dict(row))
                    records_ingested += 1

        except Exception as e:
            logger.error(f"CSV ingestion error: {e}")
            warnings.append(str(e))
            records_failed = 1

        return IngestionResult(
            result_id=result_id,
            adapter_name=self.name,
            format_used=IngestionFormat.CSV.value,
            records_ingested=records_ingested,
            records_failed=records_failed,
            warnings=warnings,
            equipment_specs=equipment_specs,
            component_recommendations=[],
            raw_data={"content_length": len(content)},
            ingested_at=datetime.now(timezone.utc).isoformat()
        )


class GenericJSONAdapter(IngestionAdapter):
    """Generic JSON adapter"""
    name = "generic_json"
    supported_formats = [IngestionFormat.JSON]

    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if content is JSON"""
        if filename.lower().endswith('.json'):
            return True
        try:
            json.loads(content)
            return True
        except Exception:
            return False

    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest JSON content"""
        result_id = str(uuid.uuid4())
        warnings = []
        equipment_specs = []
        records_ingested = 0
        records_failed = 0

        try:
            data = json.loads(content)
            
            if isinstance(data, list):
                equipment_specs = data
                records_ingested = len(data)
            elif isinstance(data, dict):
                if 'points' in data:
                    equipment_specs = data['points'] if isinstance(data['points'], list) else [data['points']]
                    records_ingested = len(equipment_specs)
                elif 'equipment' in data:
                    equipment_specs = data['equipment'] if isinstance(data['equipment'], list) else [data['equipment']]
                    records_ingested = len(equipment_specs)
                else:
                    equipment_specs = [data]
                    records_ingested = 1

        except Exception as e:
            logger.error(f"JSON ingestion error: {e}")
            warnings.append(str(e))
            records_failed = 1

        return IngestionResult(
            result_id=result_id,
            adapter_name=self.name,
            format_used=IngestionFormat.JSON.value,
            records_ingested=records_ingested,
            records_failed=records_failed,
            warnings=warnings,
            equipment_specs=equipment_specs,
            component_recommendations=[],
            raw_data={"content_length": len(content)},
            ingested_at=datetime.now(timezone.utc).isoformat()
        )


class GraingerCatalogAdapter(IngestionAdapter):
    """Grainger catalog product export adapter"""
    name = "grainger_catalog"
    supported_formats = [IngestionFormat.CSV]

    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if content is Grainger catalog format"""
        lines = content.strip().split('\n')
        if lines:
            first_line = lines[0].lower()
            grainger_keywords = ['part', 'manufacturer', 'description', 'price']
            matches = sum(1 for kw in grainger_keywords if kw in first_line)
            return matches >= 2
        return False

    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest Grainger catalog"""
        result_id = str(uuid.uuid4())
        warnings = []
        equipment_specs = []
        component_recommendations = []
        records_ingested = 0
        records_failed = 0

        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                if not row:
                    continue
                
                spec = dict(row)
                equipment_specs.append(spec)
                
                rec = ComponentRecommendation(
                    part_number=row.get('part_number', row.get('part', '')),
                    manufacturer=row.get('manufacturer', 'Unknown'),
                    description=row.get('description', ''),
                    category=row.get('category', 'general'),
                    application=row.get('application', 'general'),
                    price_tier=row.get('price_tier', 'standard'),
                    specifications=spec,
                    grainger_category=row.get('grainger_category', 'General'),
                    industry_standard=row.get('industry_standard', 'false').lower() == 'true',
                    why_recommended=row.get('why_recommended', 'Catalog item')
                )
                component_recommendations.append(rec.to_dict())
                records_ingested += 1

        except Exception as e:
            logger.error(f"Grainger catalog ingestion error: {e}")
            warnings.append(str(e))

        return IngestionResult(
            result_id=result_id,
            adapter_name=self.name,
            format_used=IngestionFormat.CSV.value,
            records_ingested=records_ingested,
            records_failed=records_failed,
            warnings=warnings,
            equipment_specs=equipment_specs,
            component_recommendations=component_recommendations,
            raw_data={"content_length": len(content)},
            ingested_at=datetime.now(timezone.utc).isoformat()
        )


class MQTTTopicMapAdapter(IngestionAdapter):
    """MQTT topic map adapter"""
    name = "mqtt_topic_map"
    supported_formats = [IngestionFormat.MQTT_SCHEMA, IngestionFormat.CSV, IngestionFormat.JSON]

    def can_handle(self, content: str, filename: str = "") -> bool:
        """Check if content is MQTT topic map"""
        lines = content.strip().split('\n')
        if lines:
            first_line = lines[0].lower()
            mqtt_keywords = ['topic', 'mqtt', 'subscribe', 'publish']
            return any(kw in first_line for kw in mqtt_keywords)
        return False

    def ingest(self, content: str, context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest MQTT topic map"""
        result_id = str(uuid.uuid4())
        warnings = []
        equipment_specs = []
        records_ingested = 0
        records_failed = 0

        try:
            if content.strip().startswith('{') or content.strip().startswith('['):
                data = json.loads(content)
                if isinstance(data, list):
                    equipment_specs = data
                else:
                    equipment_specs = [data]
                records_ingested = len(equipment_specs)
            else:
                reader = csv.DictReader(io.StringIO(content))
                for row in reader:
                    if row and row.get('topic'):
                        equipment_specs.append(dict(row))
                        records_ingested += 1

        except Exception as e:
            logger.error(f"MQTT topic map ingestion error: {e}")
            warnings.append(str(e))

        return IngestionResult(
            result_id=result_id,
            adapter_name=self.name,
            format_used=IngestionFormat.MQTT_SCHEMA.value,
            records_ingested=records_ingested,
            records_failed=records_failed,
            warnings=warnings,
            equipment_specs=equipment_specs,
            component_recommendations=[],
            raw_data={"content_length": len(content)},
            ingested_at=datetime.now(timezone.utc).isoformat()
        )


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------

class AdapterRegistry:
    """Registry for managing ingestion adapters"""

    def __init__(self):
        """Initialize registry with built-in adapters"""
        self._adapters: List[IngestionAdapter] = []
        self._register_builtin_adapters()

    def _register_builtin_adapters(self):
        """Register all built-in adapters"""
        self.register(BACnetEDEAdapter())
        self.register(ModbusRegisterMapAdapter())
        self.register(OpcUaNodeSetAdapter())
        self.register(MQTTTopicMapAdapter())
        self.register(GraingerCatalogAdapter())
        self.register(GenericJSONAdapter())
        self.register(GenericCSVAdapter())

    def register(self, adapter: IngestionAdapter) -> None:
        """Register an adapter"""
        self._adapters.append(adapter)
        logger.info(f"Registered adapter: {adapter.name}")

    def auto_detect_and_ingest(self, content: str, filename: str = "", 
                                context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Auto-detect format and ingest"""
        for adapter in self._adapters:
            if adapter.can_handle(content, filename):
                logger.info(f"Auto-detected adapter: {adapter.name}")
                return adapter.ingest(content, context)
        
        raise ValueError(f"No adapter found for content (filename: {filename})")

    def ingest_with(self, adapter_name: str, content: str, 
                    context: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """Ingest with specific adapter"""
        for adapter in self._adapters:
            if adapter.name == adapter_name:
                return adapter.ingest(content, context)
        
        raise ValueError(f"Adapter not found: {adapter_name}")

    def list_adapters(self) -> List[Dict[str, Any]]:
        """List all registered adapters"""
        return [
            {
                "name": adapter.name,
                "supported_formats": [fmt.value for fmt in adapter.supported_formats],
                "schema": adapter.get_schema()
            }
            for adapter in self._adapters
        ]

    def get_component_recommendations(self, equipment_type: str, 
                                      application: str = "") -> List[ComponentRecommendation]:
        """Get component recommendations"""
        recommendations = []
        equipment_lower = equipment_type.lower()
        application_lower = application.lower()
        
        for category, items in GRAINGER_BEST_SELLERS.items():
            for rec in items:
                if (equipment_lower in rec.application.lower() or 
                    equipment_lower in rec.category.lower() or
                    (application_lower and application_lower in rec.application.lower())):
                    recommendations.append(rec)
        
        for category, items in INDUSTRY_STANDARD_COMPONENTS.items():
            if equipment_lower in category.lower():
                recommendations.extend(items)
        
        return recommendations
