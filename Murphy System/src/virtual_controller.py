"""
Virtual Controller Module

Provides virtual controller emulation and wiring verification for BAS equipment.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
import random
import uuid

from bas_equipment_ingestion import (
    EquipmentSpec, ControllerPoint, EquipmentPointType, 
    EquipmentProtocol, EquipmentCategory
)


@dataclass
class WiringIssue:
    """Represents a wiring or configuration issue"""
    point_id: str
    point_name: str
    issue_type: str  # "missing_point", "units_mismatch", "range_invalid", "duplicate_instance", "orphaned_point"
    severity: str  # "error", "warning", "info"
    message: str
    recommendation: str


@dataclass
class VerificationReport:
    """Wiring verification report"""
    report_id: str
    spec_id: str
    equipment_name: str
    verified_at: str
    passed: bool
    error_count: int
    warning_count: int
    info_count: int
    issues: List[WiringIssue]
    point_count_summary: dict
    overall_recommendation: str

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "spec_id": self.spec_id,
            "equipment_name": self.equipment_name,
            "verified_at": self.verified_at,
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [
                {
                    "point_id": issue.point_id,
                    "point_name": issue.point_name,
                    "issue_type": issue.issue_type,
                    "severity": issue.severity,
                    "message": issue.message,
                    "recommendation": issue.recommendation
                }
                for issue in self.issues
            ],
            "point_count_summary": self.point_count_summary,
            "overall_recommendation": self.overall_recommendation
        }

    def summary(self) -> str:
        """One-line human-readable summary"""
        status = "PASSED" if self.passed else "FAILED"
        return f"{status}: {self.equipment_name} - {self.error_count} errors, {self.warning_count} warnings, {len(self.issues)} total issues"


# Minimum point requirements per equipment category
MINIMUM_POINT_REQUIREMENTS = {
    EquipmentCategory.HVAC: {
        "required_types": [EquipmentPointType.AI, EquipmentPointType.DO],
        "min_count": 2,
        "description": "HVAC requires at least 1 supply temp AI and 1 enable DO"
    },
    EquipmentCategory.ELECTRICAL: {
        "required_types": [EquipmentPointType.AI],
        "min_count": 1,
        "description": "Electrical equipment requires at least 1 power measurement AI"
    },
    EquipmentCategory.LIGHTING: {
        "required_types": [EquipmentPointType.DO, EquipmentPointType.DI],
        "min_count": 1,
        "description": "Lighting requires at least 1 control DO or status DI"
    },
    EquipmentCategory.PLUMBING: {
        "required_types": [EquipmentPointType.AI],
        "min_count": 1,
        "description": "Plumbing equipment requires at least 1 flow/pressure AI"
    },
    EquipmentCategory.FIRE_SAFETY: {
        "required_types": [EquipmentPointType.DI],
        "min_count": 1,
        "description": "Fire safety requires at least 1 alarm status DI"
    },
    EquipmentCategory.INDUSTRIAL_PLC: {
        "required_types": [EquipmentPointType.DI, EquipmentPointType.DO],
        "min_count": 1,
        "description": "Industrial PLC requires status inputs and control outputs"
    },
    EquipmentCategory.METERING: {
        "required_types": [EquipmentPointType.AI],
        "min_count": 1,
        "description": "Metering requires at least 1 measurement AI"
    }
}


# Valid units per point type
VALID_UNITS_PER_TYPE = {
    EquipmentPointType.AI: [
        "degF", "degC", "percent", "%", "PSI", "inWC", "kW", "kWh", "CFM", "GPM",
        "V", "A", "Hz", "RPM", "PPM", "CO2", "humidity", "PF", "kVAR", "BTU",
        "tons", "CFH", "inHg", "mbar"
    ],
    EquipmentPointType.AO: [
        "percent", "%", "PSI", "V", "mA", "Hz"
    ],
    EquipmentPointType.DI: [
        "binary", "on/off", "bool", "status", ""
    ],
    EquipmentPointType.DO: [
        "binary", "on/off", "bool", "enable", ""
    ],
    EquipmentPointType.AV: [
        "degF", "degC", "percent", "%", "PSI", "inWC", "CFM", "GPM", "setpoint"
    ],
    EquipmentPointType.BV: [
        "binary", "on/off", "bool", "mode", ""
    ]
}


class VirtualController:
    """Virtual controller for equipment simulation and testing"""

    def __init__(self, spec: Optional[EquipmentSpec] = None):
        self.controller_id = str(uuid.uuid4())
        self.equipment_name = ""
        self.protocol = EquipmentProtocol.BACNET_IP
        self.points: Dict[str, ControllerPoint] = {}
        self.connected = False
        
        if spec:
            self.populate_from_spec(spec)

    def populate_from_spec(self, spec: EquipmentSpec) -> int:
        """Populate controller from equipment spec, returns count of points loaded"""
        self.equipment_name = spec.equipment_name
        self.protocol = spec.protocol
        self.points = {point.point_id: point for point in spec.points}
        return len(self.points)

    def read_point(self, point_id: str) -> Optional[float]:
        """Read a point value (returns current_value or simulated)"""
        if point_id not in self.points:
            return None
        
        point = self.points[point_id]
        if point.current_value is not None:
            return point.current_value
        
        # Return simulated value
        return self.simulate_reading(point)

    def write_point(self, point_id: str, value: float) -> bool:
        """Write to a commandable point"""
        if point_id not in self.points:
            return False
        
        point = self.points[point_id]
        
        # Only commandable outputs can be written
        if not point.is_commandable:
            return False
        
        # Clamp to limits
        if value < point.low_limit:
            value = point.low_limit
        elif value > point.high_limit:
            value = point.high_limit
        
        point.current_value = value
        return True

    def get_point_by_name(self, name: str) -> Optional[ControllerPoint]:
        """Get point by name"""
        for point in self.points.values():
            if point.point_name == name:
                return point
        return None

    def list_points(self, point_type: Optional[str] = None) -> List[dict]:
        """List all points, optionally filtered by type"""
        result = []
        for point in self.points.values():
            if point_type is None or point.point_type.name == point_type:
                result.append(point.to_dict())
        return result

    def verify_wiring(self, spec: EquipmentSpec) -> VerificationReport:
        """Verify wiring and configuration"""
        engine = WiringVerificationEngine()
        return engine.verify(spec)

    def connect(self, backend: Any = None) -> bool:
        """Connect to backend (stub implementation)"""
        self.connected = True
        return True

    def disconnect(self) -> bool:
        """Disconnect from backend"""
        self.connected = False
        return True

    def get_status(self) -> dict:
        """Get controller status"""
        return {
            "controller_id": self.controller_id,
            "connected": self.connected,
            "point_count": len(self.points),
            "equipment_name": self.equipment_name,
            "protocol": self.protocol.name
        }

    def simulate_reading(self, point: ControllerPoint) -> float:
        """Generate realistic simulated value within limits"""
        # Use normal_value as baseline with some variance
        if point.point_type in [EquipmentPointType.DI, EquipmentPointType.DO, 
                                EquipmentPointType.BV]:
            # Binary points: 0 or 1
            return float(random.choice([0, 1]))
        
        # Analog points: add +/- 10% variance to normal_value
        variance = (point.high_limit - point.low_limit) * 0.1
        value = point.normal_value + random.uniform(-variance, variance)
        
        # Clamp to limits
        value = max(point.low_limit, min(point.high_limit, value))
        
        return round(value, 2)


class WiringVerificationEngine:
    """Standalone engine for wiring verification"""

    def verify(self, spec: EquipmentSpec) -> VerificationReport:
        """Perform complete wiring verification"""
        issues: List[WiringIssue] = []
        
        # Run all checks
        self._check_minimum_points(spec, issues)
        self._check_units_validity(spec, issues)
        self._check_range_logic(spec, issues)
        self._check_duplicate_instances(spec, issues)
        self._check_commandable_outputs(spec, issues)
        
        # Count by severity
        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        info_count = sum(1 for issue in issues if issue.severity == "info")
        
        # Passed if no errors
        passed = error_count == 0
        
        # Overall recommendation
        overall_rec = self._generate_overall_recommendation(spec, issues)
        
        report = VerificationReport(
            report_id=str(uuid.uuid4()),
            spec_id=spec.spec_id,
            equipment_name=spec.equipment_name,
            verified_at=datetime.now().isoformat(),
            passed=passed,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            issues=issues,
            point_count_summary=spec.point_summary(),
            overall_recommendation=overall_rec
        )
        
        return report

    def _check_minimum_points(self, spec: EquipmentSpec, issues: List[WiringIssue]):
        """Check if equipment has minimum required points"""
        requirements = MINIMUM_POINT_REQUIREMENTS.get(spec.category)
        if not requirements:
            return
        
        # Count points by type
        point_counts = {pt: 0 for pt in EquipmentPointType}
        for point in spec.points:
            point_counts[point.point_type] += 1
        
        # Check required types
        missing_types = []
        for req_type in requirements["required_types"]:
            if point_counts[req_type] < 1:
                missing_types.append(req_type.name)
        
        if missing_types:
            issues.append(WiringIssue(
                point_id="",
                point_name="",
                issue_type="missing_point",
                severity="error",
                message=f"Missing required point types: {', '.join(missing_types)}",
                recommendation=requirements["description"]
            ))
        
        # Check total count
        total_points = len(spec.points)
        if total_points < requirements["min_count"]:
            issues.append(WiringIssue(
                point_id="",
                point_name="",
                issue_type="missing_point",
                severity="warning",
                message=f"Only {total_points} points configured, minimum {requirements['min_count']} recommended",
                recommendation="Add additional monitoring and control points"
            ))

    def _check_units_validity(self, spec: EquipmentSpec, issues: List[WiringIssue]):
        """Check if engineering units are valid for point type"""
        for point in spec.points:
            valid_units = VALID_UNITS_PER_TYPE.get(point.point_type, [])
            if not valid_units:
                continue
            
            if point.engineering_units and point.engineering_units not in valid_units:
                issues.append(WiringIssue(
                    point_id=point.point_id,
                    point_name=point.point_name,
                    issue_type="units_mismatch",
                    severity="warning",
                    message=f"Units '{point.engineering_units}' not typical for {point.point_type.name}",
                    recommendation=f"Verify units; typical units: {', '.join(valid_units[:5])}"
                ))

    def _check_range_logic(self, spec: EquipmentSpec, issues: List[WiringIssue]):
        """Check if ranges are logically valid"""
        for point in spec.points:
            # Check low < high
            if point.low_limit >= point.high_limit:
                issues.append(WiringIssue(
                    point_id=point.point_id,
                    point_name=point.point_name,
                    issue_type="range_invalid",
                    severity="error",
                    message=f"low_limit ({point.low_limit}) >= high_limit ({point.high_limit})",
                    recommendation="Correct the limit values so low_limit < high_limit"
                ))
            
            # Check normal value in range
            if not (point.low_limit <= point.normal_value <= point.high_limit):
                issues.append(WiringIssue(
                    point_id=point.point_id,
                    point_name=point.point_name,
                    issue_type="range_invalid",
                    severity="warning",
                    message=f"normal_value ({point.normal_value}) outside operational range",
                    recommendation="Set normal_value within low_limit and high_limit"
                ))
            
            # Check alarm limits if present
            if point.alarm_low is not None and point.alarm_low < point.low_limit:
                issues.append(WiringIssue(
                    point_id=point.point_id,
                    point_name=point.point_name,
                    issue_type="range_invalid",
                    severity="warning",
                    message=f"alarm_low ({point.alarm_low}) below operational range",
                    recommendation="Set alarm_low >= low_limit"
                ))
            
            if point.alarm_high is not None and point.alarm_high > point.high_limit:
                issues.append(WiringIssue(
                    point_id=point.point_id,
                    point_name=point.point_name,
                    issue_type="range_invalid",
                    severity="warning",
                    message=f"alarm_high ({point.alarm_high}) above operational range",
                    recommendation="Set alarm_high <= high_limit"
                ))

    def _check_duplicate_instances(self, spec: EquipmentSpec, issues: List[WiringIssue]):
        """Check for duplicate BACnet object instances within same object type"""
        # Only relevant for BACnet protocols
        if "BACNET" not in spec.protocol.name:
            return
        
        # Group by object_type
        instances_by_type: Dict[str, List[tuple]] = {}
        for point in spec.points:
            obj_type = point.object_type
            if obj_type not in instances_by_type:
                instances_by_type[obj_type] = []
            instances_by_type[obj_type].append((point.object_instance, point.point_id, point.point_name))
        
        # Check for duplicates
        for obj_type, instances in instances_by_type.items():
            instance_nums = [inst[0] for inst in instances]
            if len(instance_nums) != len(set(instance_nums)):
                # Found duplicates
                duplicates = [inst for inst in set(instance_nums) if instance_nums.count(inst) > 1]
                for dup_num in duplicates:
                    dup_points = [inst for inst in instances if inst[0] == dup_num]
                    for _, point_id, point_name in dup_points:
                        issues.append(WiringIssue(
                            point_id=point_id,
                            point_name=point_name,
                            issue_type="duplicate_instance",
                            severity="error",
                            message=f"Duplicate {obj_type} instance {dup_num}",
                            recommendation="Assign unique object instances per object type"
                        ))

    def _check_commandable_outputs(self, spec: EquipmentSpec, issues: List[WiringIssue]):
        """Check that output points are marked commandable"""
        for point in spec.points:
            if point.point_type in [EquipmentPointType.AO, EquipmentPointType.DO]:
                if not point.is_commandable:
                    issues.append(WiringIssue(
                        point_id=point.point_id,
                        point_name=point.point_name,
                        issue_type="orphaned_point",
                        severity="warning",
                        message=f"{point.point_type.name} point not marked as commandable",
                        recommendation="Set is_commandable=True for output points"
                    ))

    def _generate_overall_recommendation(self, spec: EquipmentSpec, issues: List[WiringIssue]) -> str:
        """Generate overall recommendation based on issues"""
        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        
        if error_count == 0 and warning_count == 0:
            return f"{spec.equipment_name} wiring verified successfully. Equipment is ready for commissioning."
        elif error_count == 0:
            return f"{spec.equipment_name} has {warning_count} warnings. Review and address warnings before production deployment."
        else:
            return f"{spec.equipment_name} has {error_count} errors that must be resolved before commissioning. Address all errors and re-verify."
