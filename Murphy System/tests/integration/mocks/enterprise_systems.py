"""
Enterprise System Mocks for Phase 2 Testing
Provides mock implementations of external enterprise systems
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from uuid import uuid4
import json


# ============================================================================
# HR/STAFFING SYSTEM MOCK
# ============================================================================

@dataclass
class Employee:
    """Employee record"""
    employee_id: str
    name: str
    email: str
    department: str
    position: str
    hire_date: datetime
    status: str = "active"


class HRSystemMock:
    """Mock HR/Staffing System"""
    
    def __init__(self):
        self.employees: Dict[str, Employee] = {}
        self.pending_approvals: List[Dict[str, Any]] = []
        self._last_approval: Optional[Dict[str, Any]] = None
        
    def create_employee(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new employee record"""
        employee_id = f"EMP{len(self.employees) + 1:04d}"
        
        employee = Employee(
            employee_id=employee_id,
            name=employee_data["name"],
            email=employee_data["email"],
            department=employee_data["department"],
            position=employee_data.get("position", "Employee"),
            hire_date=datetime.now(),
            status="pending"
        )
        
        self.employees[employee_id] = employee
        
        return {
            "success": True,
            "employee_id": employee_id,
            "status": "created",
            "message": f"Employee {employee_id} created successfully"
        }
    
    def get_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Get employee by ID"""
        employee = self.employees.get(employee_id)
        if not employee:
            return None
        
        return {
            "employee_id": employee.employee_id,
            "name": employee.name,
            "email": employee.email,
            "department": employee.department,
            "position": employee.position,
            "hire_date": employee.hire_date.isoformat(),
            "status": employee.status
        }
    
    def request_approval(self, approval_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Request human approval for critical HR action"""
        approval_id = f"APR{len(self.pending_approvals) + 1:04d}"
        
        approval = {
            "approval_id": approval_id,
            "type": approval_type,
            "data": data,
            "status": "pending",
            "requested_at": datetime.now().isoformat()
        }
        
        self.pending_approvals.append(approval)
        
        return {
            "success": True,
            "approval_id": approval_id,
            "status": "pending_approval",
            "message": f"Approval request {approval_id} created"
        }
    
    def approve_request(self, approval_id: str, approver: str) -> Dict[str, Any]:
        """Approve pending request"""
        for approval in self.pending_approvals:
            if approval["approval_id"] == approval_id:
                approval["status"] = "approved"
                approval["approver"] = approver
                approval["approved_at"] = datetime.now().isoformat()
                
                return {
                    "success": True,
                    "approval_id": approval_id,
                    "status": "approved"
                }
        
        return {
            "success": False,
            "error": "Approval request not found"
        }

    # --- async methods for e2e tests ---

    async def register_employee(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "pending_approval", "employee_id": "EMP-" + str(uuid4())[:8]}

    async def get_training_requirements(self, position: str, department: str = "") -> List[Dict[str, Any]]:
        return [
            {"id": "TRN-001", "name": "Security Awareness", "category": "Security", "mandatory": True},
            {"id": "TRN-002", "name": "Compliance Basics", "category": "Compliance", "mandatory": True},
            {"id": "TRN-003", "name": "Data Privacy", "category": "Security", "mandatory": True},
        ]

    async def submit_approval_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        approval_id = "APR-" + str(uuid4())[:8]
        self._last_approval = {"id": approval_id, "status": "pending", "data": data}
        return {"approval_id": approval_id, "status": "pending_manager_approval", "approver": data.get("approver_id", "MGR-001")}

    async def process_approval(self, data: Dict[str, Any]) -> Dict[str, Any]:
        approval_id = data.get("approval_id", "")
        if hasattr(self, "_last_approval") and self._last_approval.get("id") == approval_id:
            self._last_approval["status"] = "approved"
            self._last_approval["immutable"] = True
        return {"status": "approved", "final_decision": "approved", "approval_id": approval_id}

    async def modify_approval(self, approval_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if hasattr(self, "_last_approval") and self._last_approval.get("immutable"):
            raise RuntimeError("Cannot modify: approval record is immutable")
        return {"modified": True, "approval_id": approval_id}

    async def check_onboarding_prerequisites(self, employee_id: str) -> Dict[str, Any]:
        return {
            "equipment_provisioned": True,
            "credentials_generated": True,
            "training_assigned": True,
            "manager_approved": True,
            "background_check": "passed",
            "all_met": True,
            "prerequisites": ["background_check", "documentation", "training"],
        }


# ============================================================================
# MARKETING/CRM SYSTEM MOCK
# ============================================================================

@dataclass
class Campaign:
    """Marketing campaign"""
    campaign_id: str
    name: str
    content: str
    target_audience: str
    status: str
    created_at: datetime


class CRMSystemMock:
    """Mock CRM/Marketing System"""
    
    def __init__(self):
        self.campaigns: Dict[str, Campaign] = {}
        self.contacts: Dict[str, Dict[str, Any]] = {}
        
    def create_campaign(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create marketing campaign"""
        campaign_id = f"CMP{len(self.campaigns) + 1:04d}"
        
        campaign = Campaign(
            campaign_id=campaign_id,
            name=campaign_data["name"],
            content=campaign_data["content"],
            target_audience=campaign_data.get("target_audience", "general"),
            status="draft",
            created_at=datetime.now()
        )
        
        self.campaigns[campaign_id] = campaign
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "draft",
            "requires_approval": True
        }
    
    def publish_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Publish campaign (requires approval)"""
        campaign = self.campaigns.get(campaign_id)
        if not campaign:
            return {"success": False, "error": "Campaign not found"}
        
        if campaign.status != "approved":
            return {
                "success": False,
                "error": "Campaign must be approved before publishing",
                "requires_approval": True
            }
        
        campaign.status = "published"
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "published"
        }
    
    def add_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add contact to CRM"""
        contact_id = f"CNT{len(self.contacts) + 1:04d}"
        
        self.contacts[contact_id] = {
            "contact_id": contact_id,
            "name": contact_data["name"],
            "email": contact_data["email"],
            "company": contact_data.get("company", ""),
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "contact_id": contact_id
        }


# ============================================================================
# BUILDING MANAGEMENT SYSTEM (BMS) MOCK
# ============================================================================

@dataclass
class BMSZone:
    """Building zone"""
    zone_id: str
    name: str
    temperature: float
    humidity: float
    occupancy: int
    hvac_status: str


class BMSSystemMock:
    """Mock Building Management System"""
    
    def __init__(self):
        self.zones: Dict[str, BMSZone] = {
            "zone_1": BMSZone("zone_1", "Floor 1", 72.0, 45.0, 20, "auto"),
            "zone_2": BMSZone("zone_2", "Floor 2", 71.5, 46.0, 15, "auto"),
            "zone_3": BMSZone("zone_3", "Floor 3", 72.5, 44.0, 25, "auto"),
        }
        self.safety_limits = {
            "min_temp": 60.0,
            "max_temp": 85.0,
            "min_humidity": 30.0,
            "max_humidity": 70.0
        }
        self.emergency_mode = False
        
    def set_temperature(self, zone_id: str, target_temp: float) -> Dict[str, Any]:
        """Set zone temperature"""
        zone = self.zones.get(zone_id)
        if not zone:
            return {"success": False, "error": "Zone not found"}
        
        # Safety check
        if target_temp < self.safety_limits["min_temp"]:
            return {
                "success": False,
                "error": f"Temperature {target_temp}°F below safety minimum {self.safety_limits['min_temp']}°F",
                "safety_violation": True
            }
        
        if target_temp > self.safety_limits["max_temp"]:
            return {
                "success": False,
                "error": f"Temperature {target_temp}°F above safety maximum {self.safety_limits['max_temp']}°F",
                "safety_violation": True
            }
        
        zone.temperature = target_temp
        
        return {
            "success": True,
            "zone_id": zone_id,
            "temperature": target_temp,
            "status": "temperature_set"
        }
    
    def get_zone_status(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Get zone status"""
        zone = self.zones.get(zone_id)
        if not zone:
            return None
        
        return {
            "zone_id": zone.zone_id,
            "name": zone.name,
            "temperature": zone.temperature,
            "humidity": zone.humidity,
            "occupancy": zone.occupancy,
            "hvac_status": zone.hvac_status
        }
    
    def emergency_shutdown(self, reason: str) -> Dict[str, Any]:
        """Emergency shutdown"""
        self.emergency_mode = True
        
        for zone in self.zones.values():
            zone.hvac_status = "emergency_shutdown"
        
        return {
            "success": True,
            "status": "emergency_shutdown",
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
    
    def unlock_all_exits(self) -> Dict[str, Any]:
        """Unlock all emergency exits"""
        return {
            "success": True,
            "status": "all_exits_unlocked",
            "timestamp": datetime.now().isoformat()
        }

    # --- async methods for e2e tests ---

    async def activate_fire_alarm(self, zone: str = "", severity: str = "high", source: str = "", **kw) -> Dict[str, Any]:
        alarm_id = "FIRE-" + str(uuid4())[:8]
        self.emergency_mode = True
        return {"status": "activated", "alarm_id": alarm_id, "zones_affected": [zone], "timestamp": datetime.now().isoformat()}

    async def get_immediate_responses(self, alarm_id: str = "", **kw) -> Dict[str, Any]:
        return {
            "hvac_shutdown": {"status": "completed"},
            "elevator_recall": {"status": "completed"},
            "emergency_lighting": {"status": "activated"},
            "public_address": {"status": "broadcasting"},
        }

    async def calculate_evacuation_routes(self, affected_zones: List[str] = None, incident_location: str = "", occupancy: int = 0, **kw) -> List[Dict[str, Any]]:
        return [
            {"route_id": "R1", "exit_id": "EXIT-A", "path": "main_exit", "capacity": 100},
            {"route_id": "R2", "exit_id": "EXIT-B", "path": "side_exit", "capacity": 50},
        ]

    async def start_evacuation_monitoring(self, incident_id: str = "", expected_evacuees: int = 0, **kw) -> Dict[str, Any]:
        monitoring_id = "MON-" + str(uuid4())[:8]
        return {"status": "active", "monitoring_id": monitoring_id}

    async def simulate_evacuation_progress(self, monitoring_id: str = "", evacuated_count: int = 0, requires_assistance: int = 0, **kw) -> Dict[str, Any]:
        remaining = max(0, 45 - evacuated_count)
        return {"total_evacuated": evacuated_count, "requires_assistance": requires_assistance, "remaining": remaining, "progress": 100}

    async def update_evacuation_routing(self, monitoring_id: str = "", congestion_zones: List[str] = None, alternate_routes: bool = False, **kw) -> Dict[str, Any]:
        return {"routes_updated": True, "new_routes": [{"route_id": "R3", "exit_id": "EXIT-C", "path": "alternate"}], "updated": True}

    async def complete_evacuation(self, monitoring_id: str = "", final_evacuated: int = 45, assists_completed: int = 0, **kw) -> Dict[str, Any]:
        return {"status": "completed", "all_clear": False, "total_evacuated": final_evacuated, "completed": True}

    async def get_system_status(self, system: str = "", **kw) -> Dict[str, Any]:
        return {"status": "shutdown", "emergency_mode": True, "zones": []}

    async def get_critical_systems_status(self, **kw) -> Dict[str, Any]:
        return {"emergency_lighting": "active", "fire_suppression": "standby", "life_safety": "active", "all_safe": True, "systems": []}

    async def get_system_isolation_status(self, **kw) -> Dict[str, Any]:
        systems = ["access_control", "hvac", "elevators", "electrical", "gas", "water", "data_networks"]
        return {s: {"isolated": True} for s in systems}

    async def get_life_safety_status(self, **kw) -> Dict[str, Any]:
        return {"emergency_lighting": "active", "fire_suppression": "ready", "emergency_power": "active", "communication_systems": "active", "all_safe": True}

    async def get_access_control_status(self, **kw) -> Dict[str, Any]:
        return {"external_access": "blocked", "internal_movement": "restricted", "emergency_exits": "unlocked", "emergency_responder_access": "granted", "locked_down": False}

    async def start_recovery_sequence(self, data: Dict[str, Any] = None, **kw) -> Dict[str, Any]:
        recovery_id = "REC-" + str(uuid4())[:8]
        return {"status": "initiated", "recovery_id": recovery_id, "recovery_started": True, "sequence_id": recovery_id}

    async def restore_safe_areas(self, recovery_id: str = "", areas: List[str] = None, systems: List[str] = None, **kw) -> Dict[str, Any]:
        return {"areas_restored": len(areas) if areas else 0, "systems_active": len(systems) if systems else 0, "restored": True}

    async def restore_access_control(self, recovery_id: str = "", access_level: str = "", authorized_personnel: List[str] = None, **kw) -> Dict[str, Any]:
        return {"access_restored": True, "authorization_required": True, "restored": True}

    async def run_system_diagnostics(self, recovery_id: str = "", all_systems: bool = False, **kw) -> Dict[str, Any]:
        return {"diagnostics_complete": True, "systems_healthy": 10, "systems_needing_attention": 1, "passed": True, "systems_checked": 10}

    async def generate_recovery_report(self, incident_id: str = "", recovery_id: str = "", **kw) -> Dict[str, Any]:
        return {
            "incident_summary": {"incident_type": "fire", "incident_id": incident_id},
            "recovery_actions": {"total_actions": 5},
            "system_status": {"operational_percentage": 95},
            "report": "recovery_complete",
            "all_systems_normal": True,
        }


# ============================================================================
# SCADA/ROBOTICS SYSTEM MOCK
# ============================================================================

@dataclass
class Robot:
    """Industrial robot"""
    robot_id: str
    name: str
    position: tuple
    status: str
    safety_interlocks_active: bool


class SCADASystemMock:
    """Mock SCADA/Robotics System"""
    
    def __init__(self):
        self.robots: Dict[str, Robot] = {
            "robot_1": Robot("robot_1", "Assembly Robot", (0, 0, 0), "idle", True),
            "robot_2": Robot("robot_2", "Welding Robot", (100, 0, 0), "idle", True),
            "robot_3": Robot("robot_3", "Inspection Robot", (200, 0, 0), "idle", True),
        }
        self.emergency_stop_active = False
        self.workspace_bounds = {
            "x_min": -50, "x_max": 250,
            "y_min": -50, "y_max": 250,
            "z_min": 0, "z_max": 100
        }
        
    def move_robot(self, robot_id: str, position: tuple) -> Dict[str, Any]:
        """Move robot to position"""
        robot = self.robots.get(robot_id)
        if not robot:
            return {"success": False, "error": "Robot not found"}
        
        if self.emergency_stop_active:
            return {
                "success": False,
                "error": "Emergency stop active",
                "emergency_stop": True
            }
        
        # Check workspace bounds
        x, y, z = position
        if not (self.workspace_bounds["x_min"] <= x <= self.workspace_bounds["x_max"]):
            return {
                "success": False,
                "error": f"X position {x} outside workspace bounds",
                "safety_violation": True
            }
        
        if not (self.workspace_bounds["y_min"] <= y <= self.workspace_bounds["y_max"]):
            return {
                "success": False,
                "error": f"Y position {y} outside workspace bounds",
                "safety_violation": True
            }
        
        if not (self.workspace_bounds["z_min"] <= z <= self.workspace_bounds["z_max"]):
            return {
                "success": False,
                "error": f"Z position {z} outside workspace bounds",
                "safety_violation": True
            }
        
        robot.position = position
        robot.status = "moving"
        
        return {
            "success": True,
            "robot_id": robot_id,
            "position": position,
            "status": "moving"
        }
    
    def emergency_stop(self) -> Dict[str, Any]:
        """Activate emergency stop"""
        self.emergency_stop_active = True
        
        for robot in self.robots.values():
            robot.status = "emergency_stopped"
        
        return {
            "success": True,
            "status": "emergency_stop_activated",
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": 45  # Simulated <100ms response
        }
    
    def get_robot_status(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """Get robot status"""
        robot = self.robots.get(robot_id)
        if not robot:
            return None
        
        return {
            "robot_id": robot.robot_id,
            "name": robot.name,
            "position": robot.position,
            "status": robot.status,
            "safety_interlocks_active": robot.safety_interlocks_active
        }
    
    def check_safety_interlocks(self) -> Dict[str, Any]:
        """Check all safety interlocks"""
        all_active = all(robot.safety_interlocks_active for robot in self.robots.values())
        
        return {
            "all_interlocks_active": all_active,
            "emergency_stop_ready": not self.emergency_stop_active,
            "workspace_bounds_enforced": True
        }


# ============================================================================
# IT INFRASTRUCTURE MOCK
# ============================================================================

class ITInfrastructureMock:
    """Mock IT Infrastructure"""
    
    def __init__(self):
        self.services_status = {
            "database": "running",
            "backup": "running",
            "monitoring": "running",
            "logging": "running"
        }
        self.backup_power_active = False
        self.data_backed_up = True
        
    def check_service_status(self, service: str) -> Dict[str, Any]:
        """Check service status"""
        status = self.services_status.get(service, "unknown")
        
        return {
            "service": service,
            "status": status,
            "healthy": status == "running"
        }
    
    def trigger_backup(self) -> Dict[str, Any]:
        """Trigger data backup"""
        return {
            "success": True,
            "backup_id": f"BKP{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "status": "backup_started",
            "timestamp": datetime.now().isoformat()
        }
    
    def failover_to_backup_power(self) -> Dict[str, Any]:
        """Failover to backup power"""
        self.backup_power_active = True
        
        return {
            "success": True,
            "status": "backup_power_active",
            "failover_time_seconds": 3.2,  # <5 seconds
            "timestamp": datetime.now().isoformat()
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        healthy_services = sum(1 for status in self.services_status.values() if status == "running")
        total_services = len(self.services_status)
        
        return {
            "overall_health": healthy_services / total_services,
            "services_running": healthy_services,
            "total_services": total_services,
            "backup_power_active": self.backup_power_active,
            "data_backed_up": self.data_backed_up
        }

    # --- async methods for e2e tests ---

    async def get_equipment_requirements(self, position: str, department: str = "") -> Dict[str, Any]:
        return {
            "laptop": {"type": "laptop", "spec": "standard"},
            "monitors": {"type": "monitor", "spec": "dual"},
            "access_card": {"type": "access_card", "spec": "standard"},
        }

    async def check_inventory(self, equipment_requirements: Dict[str, Any]) -> Dict[str, Any]:
        items = list(equipment_requirements.keys())
        return {"available": True, "available_items": len(items), "total_items": len(items), "items": items}


# ============================================================================
# MOCK FACTORY
# ============================================================================

class EnterpriseSystemMockFactory:
    """Factory for creating enterprise system mocks"""
    
    @staticmethod
    def create_hr_system() -> HRSystemMock:
        """Create HR system mock"""
        return HRSystemMock()
    
    @staticmethod
    def create_crm_system() -> CRMSystemMock:
        """Create CRM system mock"""
        return CRMSystemMock()
    
    @staticmethod
    def create_bms_system() -> BMSSystemMock:
        """Create BMS system mock"""
        return BMSSystemMock()
    
    @staticmethod
    def create_scada_system() -> SCADASystemMock:
        """Create SCADA system mock"""
        return SCADASystemMock()
    
    @staticmethod
    def create_it_infrastructure() -> ITInfrastructureMock:
        """Create IT infrastructure mock"""
        return ITInfrastructureMock()
# Aliases for tests that use shorter names
HRSystem = HRSystemMock
BuildingManagementSystem = BMSSystemMock
SCADARoboticsSystem = SCADASystemMock
ITInfrastructureSystem = ITInfrastructureMock
class SecuritySystem:
    """Mock Security System with async methods for e2e tests."""

    def __init__(self, **kw):
        pass

    async def authenticate(self, **kw):
        return {"authenticated": True, "token": "mock-token"}

    async def authorize(self, **kw):
        return {"authorized": True}

    async def get_security_events(self, **kw):
        return []

    async def generate_credentials(self, data: Dict[str, Any] = None, **kw) -> Dict[str, Any]:
        emp_id = (data or {}).get("employee_id", "user")
        return {
            "username": emp_id,
            "password": "TempP@ss123!Xyz",
            "mfa_secret": "MFASECRET1234",
            "access_card_id": "AC-" + str(uuid4())[:8],
            "credentials": {"username": emp_id, "temp_password": "TempP@ss123!Xyz"},
        }

    async def check_password_strength(self, password: str = "", **kw) -> Dict[str, Any]:
        return {
            "strong": True,
            "score": 4,
            "length": len(password) if password else 16,
            "has_uppercase": True,
            "has_lowercase": True,
            "has_numbers": True,
            "has_special": True,
        }

    async def test_system_access(self, employee_id: str = "", **kw) -> Dict[str, Any]:
        return {"access_granted": True, "access_level": "standard"}

    async def check_user_authority(self, user_id: str = "", action: str = "", **kw) -> Dict[str, Any]:
        return {"has_authority": True, "authority_level": "medium", "authorized": True}

    async def notify_emergency_services(self, notification_data: Dict[str, Any] = None, services: List[str] = None, **kw) -> Dict[str, Any]:
        nd = notification_data or {}
        result = {}
        for svc in (services or []):
            result[svc] = {
                "status": "sent",
                "incident_id": nd.get("incident_id", ""),
                "location": nd.get("location", ""),
                "severity": nd.get("severity", ""),
                "access_points": nd.get("access_points", {}),
            }
        return result

    async def track_emergency_response(self, incident_id: str = "", **kw) -> Dict[str, Any]:
        return {
            "incident_status": "active",
            "fire_department": {"eta": 180, "status": "dispatched"},
            "police": {"eta": 240, "status": "dispatched"},
            "ambulance": {"eta": 200, "status": "dispatched"},
            "tracked": True,
        }

    async def update_emergency_access(self, incident_id: str = "", emergency_services: bool = False, access_level: str = "", **kw) -> Dict[str, Any]:
        return {"access_granted": True, "access_points_unlocked": 5, "updated": True}

CRMSystem = CRMSystemMock


class QualityControlSystem:
    """Mock quality control system for manufacturing tests."""

    def __init__(self):
        self._inspections = []

    async def inspect_unit(self, unit_id: str = "", checks: list = None, **kw):
        result = {
            "unit_id": unit_id,
            "quality_pass": True,
            "checks": {c: {"pass": True, "value": 0.99} for c in (checks or [])},
            "inspected": True,
        }
        self._inspections.append(result)
        return result

    async def get_quality_report(self, **kw):
        total = len(self._inspections)
        passed = sum(1 for i in self._inspections if i.get("quality_pass"))
        return {
            "total_inspections": total,
            "passed": passed,
            "failed": total - passed,
            "quality_rate": passed / total if total else 1.0,
        }


class ManufacturingExecutionSystem:
    """Mock MES for manufacturing workflow tests."""

    def __init__(self):
        self._operations = []

    async def execute_operation(self, station: str = "", unit_id: str = "", **kw):
        result = {"station": station, "unit_id": unit_id, "status": "completed", "success": True}
        self._operations.append(result)
        return result

    async def get_production_status(self, **kw):
        return {"total_operations": len(self._operations), "status": "running"}
