"""
BAS Equipment Ingestion Module

Handles ingestion of Building Automation System (BAS) and Energy Management System (EMS)
equipment data from various formats (CSV, JSON, EDE).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import csv
import json
import io
import uuid


class EquipmentPointType(Enum):
    """BACnet/industrial point types"""
    AI = "Analog Input"
    AO = "Analog Output"
    DI = "Digital Input"
    DO = "Digital Output"
    AV = "Analog Value"
    BV = "Binary Value"


class EquipmentProtocol(Enum):
    """Communication protocols"""
    BACNET_IP = "BACnet/IP"
    BACNET_MSTP = "BACnet MS/TP"
    MODBUS_TCP = "Modbus TCP"
    MODBUS_RTU = "Modbus RTU"
    LONWORKS = "LonWorks"
    OPC_UA = "OPC-UA"
    OPC_DA = "OPC-DA"
    MQTT = "MQTT"
    ETHERNET_IP = "EtherNet/IP"
    PROFINET = "PROFINET"
    DNP3 = "DNP3"
    NATIVE = "Native"


class EquipmentCategory(Enum):
    """Equipment categories"""
    HVAC = "HVAC"
    ELECTRICAL = "Electrical"
    LIGHTING = "Lighting"
    PLUMBING = "Plumbing"
    FIRE_SAFETY = "Fire Safety"
    INDUSTRIAL_PLC = "Industrial PLC"
    METERING = "Metering"


@dataclass
class ControllerPoint:
    """Individual point/tag in a controller"""
    point_id: str
    point_name: str
    point_type: EquipmentPointType
    object_type: str
    object_instance: int
    description: str
    engineering_units: str
    low_limit: float
    high_limit: float
    normal_value: float
    current_value: Optional[float] = None
    alarm_low: Optional[float] = None
    alarm_high: Optional[float] = None
    setpoint: Optional[float] = None
    is_commandable: bool = False
    wiring_verified: bool = False
    verification_notes: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "point_type": self.point_type.name,
            "object_type": self.object_type,
            "object_instance": self.object_instance,
            "description": self.description,
            "engineering_units": self.engineering_units,
            "low_limit": self.low_limit,
            "high_limit": self.high_limit,
            "normal_value": self.normal_value,
            "current_value": self.current_value,
            "alarm_low": self.alarm_low,
            "alarm_high": self.alarm_high,
            "setpoint": self.setpoint,
            "is_commandable": self.is_commandable,
            "wiring_verified": self.wiring_verified,
            "verification_notes": self.verification_notes
        }


@dataclass
class EquipmentSpec:
    """Complete equipment specification"""
    spec_id: str
    equipment_id: str
    equipment_name: str
    equipment_type: str
    category: EquipmentCategory
    manufacturer: str
    model: str
    serial_number: str
    protocol: EquipmentProtocol
    ip_address: str
    port: int
    device_id: int
    points: List[ControllerPoint]
    location: str
    commissioned_date: str
    firmware_version: str
    raw_upload_data: dict
    upload_format: str
    created_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "spec_id": self.spec_id,
            "equipment_id": self.equipment_id,
            "equipment_name": self.equipment_name,
            "equipment_type": self.equipment_type,
            "category": self.category.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "protocol": self.protocol.name,
            "ip_address": self.ip_address,
            "port": self.port,
            "device_id": self.device_id,
            "points": [p.to_dict() for p in self.points],
            "location": self.location,
            "commissioned_date": self.commissioned_date,
            "firmware_version": self.firmware_version,
            "raw_upload_data": self.raw_upload_data,
            "upload_format": self.upload_format,
            "created_at": self.created_at
        }

    def point_summary(self) -> dict:
        """Get point count summary by type"""
        summary = {pt.name: 0 for pt in EquipmentPointType}
        for point in self.points:
            summary[point.point_type.name] += 1
        return summary


# Default point templates for common equipment types
DEFAULT_POINT_TEMPLATES = {
    "AHU": [
        {"name": "Supply Air Temp", "type": "AI", "units": "degF", "low": 50.0, "high": 90.0, "normal": 55.0},
        {"name": "Return Air Temp", "type": "AI", "units": "degF", "low": 50.0, "high": 90.0, "normal": 72.0},
        {"name": "Mixed Air Temp", "type": "AI", "units": "degF", "low": 30.0, "high": 95.0, "normal": 60.0},
        {"name": "Outside Air Temp", "type": "AI", "units": "degF", "low": -20.0, "high": 120.0, "normal": 70.0},
        {"name": "Supply Fan Status", "type": "DI", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Return Fan Status", "type": "DI", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Supply Fan Enable", "type": "DO", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Cooling Valve", "type": "AO", "units": "percent", "low": 0.0, "high": 100.0, "normal": 0.0},
        {"name": "Heating Valve", "type": "AO", "units": "percent", "low": 0.0, "high": 100.0, "normal": 0.0},
        {"name": "Outdoor Air Damper", "type": "AO", "units": "percent", "low": 0.0, "high": 100.0, "normal": 20.0},
        {"name": "Filter DP", "type": "AI", "units": "inWC", "low": 0.0, "high": 2.0, "normal": 0.3},
    ],
    "Chiller": [
        {"name": "CHW Supply Temp", "type": "AI", "units": "degF", "low": 35.0, "high": 60.0, "normal": 44.0},
        {"name": "CHW Return Temp", "type": "AI", "units": "degF", "low": 40.0, "high": 70.0, "normal": 56.0},
        {"name": "Condenser Water Supply Temp", "type": "AI", "units": "degF", "low": 60.0, "high": 100.0, "normal": 85.0},
        {"name": "Condenser Water Return Temp", "type": "AI", "units": "degF", "low": 65.0, "high": 110.0, "normal": 95.0},
        {"name": "Chiller Enable", "type": "DO", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Chiller Status", "type": "DI", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Chiller kW", "type": "AI", "units": "kW", "low": 0.0, "high": 1000.0, "normal": 100.0},
        {"name": "CHW Flow", "type": "AI", "units": "GPM", "low": 0.0, "high": 500.0, "normal": 200.0},
        {"name": "CHW Supply Temp Setpoint", "type": "AV", "units": "degF", "low": 38.0, "high": 50.0, "normal": 44.0},
    ],
    "Boiler": [
        {"name": "HW Supply Temp", "type": "AI", "units": "degF", "low": 100.0, "high": 200.0, "normal": 180.0},
        {"name": "HW Return Temp", "type": "AI", "units": "degF", "low": 90.0, "high": 190.0, "normal": 160.0},
        {"name": "Boiler Enable", "type": "DO", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Boiler Status", "type": "DI", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Gas Flow", "type": "AI", "units": "CFH", "low": 0.0, "high": 1000.0, "normal": 100.0},
        {"name": "HW Supply Temp Setpoint", "type": "AV", "units": "degF", "low": 120.0, "high": 200.0, "normal": 180.0},
    ],
    "VAV": [
        {"name": "Zone Temp", "type": "AI", "units": "degF", "low": 60.0, "high": 85.0, "normal": 72.0},
        {"name": "Discharge Air Temp", "type": "AI", "units": "degF", "low": 50.0, "high": 90.0, "normal": 55.0},
        {"name": "Damper Position", "type": "AI", "units": "percent", "low": 0.0, "high": 100.0, "normal": 30.0},
        {"name": "Damper Command", "type": "AO", "units": "percent", "low": 0.0, "high": 100.0, "normal": 30.0},
        {"name": "Reheat Valve", "type": "AO", "units": "percent", "low": 0.0, "high": 100.0, "normal": 0.0},
        {"name": "Zone Temp Setpoint", "type": "AV", "units": "degF", "low": 65.0, "high": 78.0, "normal": 72.0},
    ],
    "Power Meter": [
        {"name": "Voltage L1-N", "type": "AI", "units": "V", "low": 0.0, "high": 500.0, "normal": 277.0},
        {"name": "Voltage L2-N", "type": "AI", "units": "V", "low": 0.0, "high": 500.0, "normal": 277.0},
        {"name": "Voltage L3-N", "type": "AI", "units": "V", "low": 0.0, "high": 500.0, "normal": 277.0},
        {"name": "Current L1", "type": "AI", "units": "A", "low": 0.0, "high": 5000.0, "normal": 100.0},
        {"name": "Current L2", "type": "AI", "units": "A", "low": 0.0, "high": 5000.0, "normal": 100.0},
        {"name": "Current L3", "type": "AI", "units": "A", "low": 0.0, "high": 5000.0, "normal": 100.0},
        {"name": "Real Power", "type": "AI", "units": "kW", "low": 0.0, "high": 10000.0, "normal": 500.0},
        {"name": "Reactive Power", "type": "AI", "units": "kVAR", "low": -5000.0, "high": 5000.0, "normal": 0.0},
        {"name": "Power Factor", "type": "AI", "units": "PF", "low": 0.0, "high": 1.0, "normal": 0.95},
        {"name": "Energy", "type": "AI", "units": "kWh", "low": 0.0, "high": 999999999.0, "normal": 0.0},
    ],
    "Cooling Tower": [
        {"name": "Condenser Water Supply Temp", "type": "AI", "units": "degF", "low": 60.0, "high": 100.0, "normal": 85.0},
        {"name": "Condenser Water Return Temp", "type": "AI", "units": "degF", "low": 65.0, "high": 110.0, "normal": 95.0},
        {"name": "Fan Enable", "type": "DO", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Fan Status", "type": "DI", "units": "binary", "low": 0.0, "high": 1.0, "normal": 0.0},
        {"name": "Fan Speed", "type": "AO", "units": "percent", "low": 0.0, "high": 100.0, "normal": 50.0},
    ],
}


class EquipmentDataIngestion:
    """Main ingestion engine for equipment data"""

    def __init__(self):
        pass

    def ingest_csv(self, content: str, equipment_name: str, protocol: str) -> EquipmentSpec:
        """
        Ingest CSV format equipment data.
        Expected columns: point_name, point_type, object_type, object_instance, units,
                         low_limit, high_limit, normal_value, setpoint, description
        """
        reader = csv.DictReader(io.StringIO(content))
        points = []
        
        for idx, row in enumerate(reader):
            # Map point_type string to enum
            pt_type = row.get("point_type", "AI").upper()
            try:
                point_type = EquipmentPointType[pt_type]
            except KeyError:
                point_type = EquipmentPointType.AI  # Fallback
            
            point = ControllerPoint(
                point_id=f"point_{idx}",
                point_name=row.get("point_name", f"Point_{idx}"),
                point_type=point_type,
                object_type=row.get("object_type", pt_type),
                object_instance=int(row.get("object_instance", idx)),
                description=row.get("description", ""),
                engineering_units=row.get("units", ""),
                low_limit=float(row.get("low_limit", 0.0)),
                high_limit=float(row.get("high_limit", 100.0)),
                normal_value=float(row.get("normal_value", 50.0)),
                setpoint=float(row["setpoint"]) if row.get("setpoint") else None,
                is_commandable=pt_type in ["AO", "DO"]
            )
            points.append(point)
        
        # Build spec
        protocol_enum = self._parse_protocol(protocol)
        category = self.detect_equipment_category(equipment_name, points)
        
        spec = EquipmentSpec(
            spec_id=str(uuid.uuid4()),
            equipment_id=str(uuid.uuid4()),
            equipment_name=equipment_name,
            equipment_type=equipment_name.split()[0] if " " in equipment_name else equipment_name,
            category=category,
            manufacturer="Unknown",
            model="Unknown",
            serial_number="",
            protocol=protocol_enum,
            ip_address="192.168.1.100",
            port=47808 if "BACNET" in protocol.upper() else 502,
            device_id=1,
            points=points,
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={"content": content},
            upload_format="CSV",
            created_at=datetime.now().isoformat()
        )
        
        return spec

    def ingest_json(self, data: dict) -> EquipmentSpec:
        """Ingest JSON format equipment data"""
        points = []
        
        for idx, pt in enumerate(data.get("points", [])):
            pt_type_str = pt.get("point_type", "AI").upper()
            try:
                point_type = EquipmentPointType[pt_type_str]
            except KeyError:
                point_type = EquipmentPointType.AI
            
            point = ControllerPoint(
                point_id=pt.get("point_id", f"point_{idx}"),
                point_name=pt.get("point_name", f"Point_{idx}"),
                point_type=point_type,
                object_type=pt.get("object_type", pt_type_str),
                object_instance=int(pt.get("object_instance", idx)),
                description=pt.get("description", ""),
                engineering_units=pt.get("units", pt.get("engineering_units", "")),
                low_limit=float(pt.get("low_limit", 0.0)),
                high_limit=float(pt.get("high_limit", 100.0)),
                normal_value=float(pt.get("normal_value", 50.0)),
                setpoint=float(pt["setpoint"]) if pt.get("setpoint") else None,
                is_commandable=pt_type_str in ["AO", "DO"]
            )
            points.append(point)
        
        equipment_name = data.get("equipment_name", "Equipment")
        protocol = self.detect_protocol(data)
        category = self.detect_equipment_category(equipment_name, points)
        
        spec = EquipmentSpec(
            spec_id=data.get("spec_id", str(uuid.uuid4())),
            equipment_id=data.get("equipment_id", str(uuid.uuid4())),
            equipment_name=equipment_name,
            equipment_type=data.get("equipment_type", equipment_name),
            category=category,
            manufacturer=data.get("manufacturer", "Unknown"),
            model=data.get("model", "Unknown"),
            serial_number=data.get("serial_number", ""),
            protocol=protocol,
            ip_address=data.get("ip_address", "192.168.1.100"),
            port=int(data.get("port", 47808)),
            device_id=int(data.get("device_id", 1)),
            points=points,
            location=data.get("location", ""),
            commissioned_date=data.get("commissioned_date", ""),
            firmware_version=data.get("firmware_version", ""),
            raw_upload_data=data,
            upload_format="JSON",
            created_at=data.get("created_at", datetime.now().isoformat())
        )
        
        return spec

    def ingest_ede(self, content: str) -> EquipmentSpec:
        """
        Ingest BACnet EDE (Engineering Data Exchange) format.
        Tab-delimited with columns: #object-name, object-type, object-instance,
        description, present-value-default, units-code, vendor-specific-address
        """
        lines = content.strip().split("\n")
        points = []
        
        # Find header line
        header_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("#object-name") or "object-name" in line.lower():
                header_idx = i
                break
        
        # Parse data lines
        for idx, line in enumerate(lines[header_idx + 1:]):
            if not line.strip() or line.startswith("#"):
                continue
            
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            
            object_name = parts[0].strip()
            object_type = parts[1].strip() if len(parts) > 1 else "analog-input"
            object_instance = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else idx
            description = parts[3].strip() if len(parts) > 3 else ""
            default_value = float(parts[4]) if len(parts) > 4 and parts[4].strip() else 0.0
            units_code = parts[5].strip() if len(parts) > 5 else ""
            
            # Map BACnet object type to point type
            point_type = self._bacnet_object_to_point_type(object_type)
            
            point = ControllerPoint(
                point_id=f"point_{idx}",
                point_name=object_name,
                point_type=point_type,
                object_type=object_type,
                object_instance=object_instance,
                description=description,
                engineering_units=self._bacnet_units_code_to_string(units_code),
                low_limit=0.0,
                high_limit=100.0,
                normal_value=default_value,
                is_commandable="output" in object_type.lower()
            )
            points.append(point)
        
        equipment_name = "BACnet Device"
        category = self.detect_equipment_category(equipment_name, points)
        
        spec = EquipmentSpec(
            spec_id=str(uuid.uuid4()),
            equipment_id=str(uuid.uuid4()),
            equipment_name=equipment_name,
            equipment_type="BACnet Device",
            category=category,
            manufacturer="Unknown",
            model="Unknown",
            serial_number="",
            protocol=EquipmentProtocol.BACNET_IP,
            ip_address="192.168.1.100",
            port=47808,
            device_id=1,
            points=points,
            location="",
            commissioned_date="",
            firmware_version="",
            raw_upload_data={"content": content},
            upload_format="EDE",
            created_at=datetime.now().isoformat()
        )
        
        return spec

    def ingest_auto(self, content: str, filename: str = "") -> EquipmentSpec:
        """Auto-detect format and ingest"""
        # Check filename extension first
        if filename:
            ext = filename.lower().split(".")[-1] if "." in filename else ""
            if ext == "csv":
                return self.ingest_csv(content, filename.replace(".csv", ""), "BACnet/IP")
            elif ext == "json":
                return self.ingest_json(json.loads(content))
            elif ext in ["ede", "txt"]:
                if "#object-name" in content or "object-type" in content:
                    return self.ingest_ede(content)
        
        # Content-based detection
        if content.strip().startswith("{") or content.strip().startswith("["):
            return self.ingest_json(json.loads(content))
        elif "#object-name" in content or ("\t" in content and "object-type" in content.lower()):
            return self.ingest_ede(content)
        elif "," in content and "\n" in content:
            # Assume CSV
            return self.ingest_csv(content, "Equipment", "BACnet/IP")
        else:
            raise ValueError("Unable to auto-detect format")

    def detect_equipment_category(self, equipment_type: str, points: List[ControllerPoint]) -> EquipmentCategory:
        """Detect equipment category from type and points"""
        eq_lower = equipment_type.lower()
        
        # Plumbing keywords - check first as "flow" and "water" are more specific than "meter"
        plumb_keywords = ["flow", "water", "pressure", "plumbing", "pump"]
        if any(kw in eq_lower for kw in plumb_keywords):
            return EquipmentCategory.PLUMBING
        
        # HVAC keywords
        hvac_keywords = ["ahu", "air handler", "rtu", "vav", "fcu", "chiller", "boiler", 
                         "cooling tower", "heat pump", "fan coil", "hvac"]
        if any(kw in eq_lower for kw in hvac_keywords):
            return EquipmentCategory.HVAC
        
        # Electrical keywords
        elec_keywords = ["power", "meter", "ups", "generator", "vfd", "mcc", "electrical",
                        "voltage", "current", "kwh"]
        if any(kw in eq_lower for kw in elec_keywords):
            return EquipmentCategory.ELECTRICAL
        
        # Lighting keywords
        light_keywords = ["light", "lighting", "occupancy", "daylight"]
        if any(kw in eq_lower for kw in light_keywords):
            return EquipmentCategory.LIGHTING
        
        # Fire safety keywords
        fire_keywords = ["fire", "alarm", "emergency", "sprinkler"]
        if any(kw in eq_lower for kw in fire_keywords):
            return EquipmentCategory.FIRE_SAFETY
        
        # Industrial PLC keywords
        plc_keywords = ["plc", "scada", "robot", "cnc", "conveyor", "press"]
        if any(kw in eq_lower for kw in plc_keywords):
            return EquipmentCategory.INDUSTRIAL_PLC
        
        # Metering keywords
        meter_keywords = ["meter", "btu", "gas meter", "water meter"]
        if any(kw in eq_lower for kw in meter_keywords):
            return EquipmentCategory.METERING
        
        # Point-based heuristics
        point_names = " ".join([p.point_name.lower() for p in points])
        if "temp" in point_names and "fan" in point_names:
            return EquipmentCategory.HVAC
        elif "voltage" in point_names or "current" in point_names:
            return EquipmentCategory.ELECTRICAL
        elif "flow" in point_names:
            return EquipmentCategory.PLUMBING
        
        return EquipmentCategory.HVAC  # Default

    def detect_protocol(self, raw_data: dict) -> EquipmentProtocol:
        """Detect protocol from raw data"""
        protocol_str = raw_data.get("protocol", "").upper()
        
        if "BACNET" in protocol_str:
            return EquipmentProtocol.BACNET_IP
        elif "MODBUS" in protocol_str:
            return EquipmentProtocol.MODBUS_TCP
        elif "OPC" in protocol_str:
            return EquipmentProtocol.OPC_UA
        elif "MQTT" in protocol_str:
            return EquipmentProtocol.MQTT
        else:
            return EquipmentProtocol.BACNET_IP  # Default

    def validate_point(self, point: ControllerPoint) -> List[str]:
        """Validate a point and return list of warnings"""
        warnings = []
        
        if point.low_limit >= point.high_limit:
            warnings.append(f"{point.point_name}: low_limit >= high_limit")
        
        if point.alarm_low is not None and point.alarm_low < point.low_limit:
            warnings.append(f"{point.point_name}: alarm_low below operational range")
        
        if point.alarm_high is not None and point.alarm_high > point.high_limit:
            warnings.append(f"{point.point_name}: alarm_high above operational range")
        
        if not point.engineering_units:
            warnings.append(f"{point.point_name}: missing engineering units")
        
        if point.point_type in [EquipmentPointType.AO, EquipmentPointType.DO] and not point.is_commandable:
            warnings.append(f"{point.point_name}: output point should be commandable")
        
        return warnings

    def get_recommendations(self, spec: EquipmentSpec) -> List[str]:
        """Get industry best-practice recommendations for equipment"""
        recommendations = []
        eq_type = spec.equipment_type.lower()
        
        if "chiller" in eq_type:
            recommendations.append(
                "ASHRAE 90.1 requires chiller plant optimization; consider delta-T optimization at 10-14°F"
            )
            recommendations.append(
                "Monitor chiller COP (Coefficient of Performance) ≥ 6.1 at AHRI conditions"
            )
            recommendations.append(
                "Implement condenser water temperature reset based on wet-bulb temperature"
            )
        
        if "ahu" in eq_type or "air handler" in eq_type:
            recommendations.append(
                "ASHRAE 62.1 minimum OA requirement; enable demand-controlled ventilation with CO2 sensors"
            )
            recommendations.append(
                "Implement economizer control with dry-bulb or enthalpy-based changeover"
            )
            recommendations.append(
                "Monitor filter differential pressure; replace filters at 1.5-2.0 inWC"
            )
        
        if "boiler" in eq_type:
            recommendations.append(
                "Implement outdoor air reset control for supply water temperature"
            )
            recommendations.append(
                "Monitor combustion efficiency; maintain >80% for gas-fired boilers"
            )
        
        if "power" in eq_type or "meter" in eq_type or spec.category == EquipmentCategory.ELECTRICAL:
            recommendations.append(
                "Install sub-metering per LEED EA Credit; 15-minute interval logging recommended"
            )
            recommendations.append(
                "Monitor power quality metrics: voltage THD <5%, current THD <8%"
            )
            recommendations.append(
                "Track power factor; maintain >0.95 to avoid utility penalties"
            )
        
        if "vav" in eq_type:
            recommendations.append(
                "Set minimum airflow to greater of code minimum or 30% of design CFM"
            )
            recommendations.append(
                "Calibrate damper actuators annually; verify full stroke 0-100%"
            )
        
        if spec.category == EquipmentCategory.INDUSTRIAL_PLC:
            recommendations.append(
                "Implement redundant safety interlocks per OSHA requirements"
            )
            recommendations.append(
                "Log all alarm and fault events with timestamp and operator ID"
            )
        
        if not recommendations:
            recommendations.append(
                "Implement continuous monitoring and trending of key performance indicators"
            )
            recommendations.append(
                "Schedule preventive maintenance per manufacturer recommendations"
            )
        
        return recommendations[:5]  # Return max 5

    def _parse_protocol(self, protocol: str) -> EquipmentProtocol:
        """Parse protocol string to enum"""
        protocol_upper = protocol.upper().replace(" ", "_").replace("/", "_")
        for proto in EquipmentProtocol:
            if protocol_upper in proto.name or protocol_upper in proto.value.upper():
                return proto
        return EquipmentProtocol.BACNET_IP

    def _bacnet_object_to_point_type(self, object_type: str) -> EquipmentPointType:
        """Map BACnet object type to point type"""
        obj_lower = object_type.lower()
        if "analog-input" in obj_lower or "ai" == obj_lower:
            return EquipmentPointType.AI
        elif "analog-output" in obj_lower or "ao" == obj_lower:
            return EquipmentPointType.AO
        elif "binary-input" in obj_lower or "di" == obj_lower:
            return EquipmentPointType.DI
        elif "binary-output" in obj_lower or "do" == obj_lower:
            return EquipmentPointType.DO
        elif "analog-value" in obj_lower or "av" == obj_lower:
            return EquipmentPointType.AV
        elif "binary-value" in obj_lower or "bv" == obj_lower:
            return EquipmentPointType.BV
        else:
            return EquipmentPointType.AI

    def _bacnet_units_code_to_string(self, units_code: str) -> str:
        """Map BACnet units code to string"""
        units_map = {
            "62": "degF",
            "64": "degC",
            "95": "percent",
            "98": "PSI",
            "99": "inWC",
            "48": "kW",
            "19": "CFM",
            "74": "GPM",
        }
        return units_map.get(units_code, units_code)
