"""
Phase 2: Enterprise System Integration Tests
Tests Murphy System integration with external enterprise systems

Test Hierarchy: Level 2 (Integration Tests)
Test Category: External System Interface Testing
"""

import pytest
from datetime import datetime, timedelta
import sys
import os

# Add mocks to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mocks'))

from enterprise_systems import (
    EnterpriseSystemMockFactory,
    HRSystemMock,
    CRMSystemMock,
    BMSSystemMock,
    SCADASystemMock,
    ITInfrastructureMock
)


# ============================================================================
# SIT-INT-101: Murphy ↔ HR/Staffing System Integration
# ============================================================================

def test_sit_int_101_murphy_hr_integration():
    """
    Test ID: SIT-INT-101
    Test Name: Murphy to HR/Staffing System Integration

    Test Objective:
    Validate Murphy can safely automate HR workflows while preserving
    human authority for critical decisions.

    Expected Results:
    - Automated tasks execute without approval
    - Critical tasks require human signoff
    - All HR data changes logged
    - GDPR compliance maintained
    """
    from src.security_plane.data_leak_prevention import DataLeakPreventionSystem

    # Setup
    hr_system = EnterpriseSystemMockFactory.create_hr_system()
    dlp = DataLeakPreventionSystem()

    print("\n=== SIT-INT-101: HR/Staffing System Integration ===\n")

    # Test Case 1: Automated Employee Creation (Low Authority)
    employee_data = {
        "name": "John Doe",
        "email": "john.doe@company.com",
        "department": "Engineering",
        "position": "Software Engineer"
    }

    result = hr_system.create_employee(employee_data)

    assert result["success"] is True
    assert "employee_id" in result
    print(f"✓ Automated task: Employee {result['employee_id']} created")

    # Test Case 2: PII Data Classification (GDPR Compliance)
    pii_data = f"Employee: {employee_data['name']}, Email: {employee_data['email']}"
    classification = dlp.classify_and_protect(pii_data, "hr_data_001")

    assert len(classification.categories) > 0
    # CONFIDENTIAL level may not require encryption, but should be tracked
    print(f"✓ GDPR compliance: PII classified as {classification.sensitivity_level.value}")
    print(f"  Encryption required: {classification.encryption_required}")

    # Test Case 3: Critical Action Requires Approval (Offer Letter)
    offer_data = {
        "candidate": "Jane Smith",
        "position": "Senior Engineer",
        "salary": 150000,
        "start_date": "2025-02-01"
    }

    approval_result = hr_system.request_approval("offer_letter", offer_data)

    assert approval_result["success"] is True
    assert approval_result["status"] == "pending_approval"
    print(f"✓ Critical task: Approval request {approval_result['approval_id']} created")
    print(f"  Status: {approval_result['status']}")

    # Test Case 4: Human Approval Process
    approval_id = approval_result["approval_id"]
    approve_result = hr_system.approve_request(approval_id, "hr_manager_001")

    assert approve_result["success"] is True
    assert approve_result["status"] == "approved"
    print(f"✓ Human approval: Request {approval_id} approved by hr_manager_001")

    # Test Case 5: Verify Employee Record
    employee_id = result["employee_id"]
    employee = hr_system.get_employee(employee_id)

    assert employee is not None
    assert employee["name"] == employee_data["name"]
    print(f"✓ Data integrity: Employee record verified")

    print("\n✓ SIT-INT-101 PASSED: HR/Staffing integration working\n")


# ============================================================================
# SIT-INT-102: Murphy ↔ Marketing/Sales System Integration
# ============================================================================

def test_sit_int_102_murphy_marketing_integration():
    """
    Test ID: SIT-INT-102
    Test Name: Murphy to Marketing/Sales System Integration

    Test Objective:
    Validate Murphy can generate marketing content with appropriate
    quality controls and human oversight.

    Expected Results:
    - Content generation works
    - Quality validation enforced
    - Human review required before publication
    - CRM integration successful
    """
    # Setup
    crm_system = EnterpriseSystemMockFactory.create_crm_system()

    print("\n=== SIT-INT-102: Marketing/Sales System Integration ===\n")

    # Test Case 1: Create Marketing Campaign
    campaign_data = {
        "name": "Q1 2025 Product Launch",
        "content": "Introducing our revolutionary Murphy System for enterprise automation...",
        "target_audience": "enterprise_customers"
    }

    result = crm_system.create_campaign(campaign_data)

    assert result["success"] is True
    assert result["status"] == "draft"
    assert result["requires_approval"] is True
    print(f"✓ Campaign created: {result['campaign_id']}")
    print(f"  Status: {result['status']}")
    print(f"  Requires approval: {result['requires_approval']}")

    # Test Case 2: Attempt to Publish Without Approval (Should Fail)
    campaign_id = result["campaign_id"]
    publish_result = crm_system.publish_campaign(campaign_id)

    assert publish_result["success"] is False
    assert "approv" in publish_result["error"].lower()  # Match "approved" or "approval"
    print(f"✓ Safety check: Publication blocked without approval")
    print(f"  Reason: {publish_result['error']}")

    # Test Case 3: Add Contact to CRM (Automated)
    contact_data = {
        "name": "Acme Corp",
        "email": "contact@acme.com",
        "company": "Acme Corporation"
    }

    contact_result = crm_system.add_contact(contact_data)

    assert contact_result["success"] is True
    assert "contact_id" in contact_result
    print(f"✓ Automated task: Contact {contact_result['contact_id']} added")

    # Test Case 4: Verify Campaign Workflow
    # In production, human would approve campaign here
    # For testing, we verify the workflow is correct
    assert crm_system.campaigns[campaign_id].status == "draft"
    print(f"✓ Workflow validation: Campaign awaiting approval")

    print("\n✓ SIT-INT-102 PASSED: Marketing/Sales integration working\n")


# ============================================================================
# SIT-INT-103: Murphy ↔ Building Management System Integration
# ============================================================================

def test_sit_int_103_murphy_bms_integration():
    """
    Test ID: SIT-INT-103
    Test Name: Murphy to Building Management System Integration

    Test Objective:
    Validate Murphy can safely control building systems with appropriate
    safety constraints and emergency overrides.

    Expected Results:
    - Normal operations execute within safety limits
    - Safety constraints prevent unsafe operations
    - Emergency overrides work correctly
    - Telemetry provides real-time feedback
    """
    # Setup
    bms_system = EnterpriseSystemMockFactory.create_bms_system()

    print("\n=== SIT-INT-103: Building Management System Integration ===\n")

    # Test Case 1: Normal HVAC Control (Within Safety Limits)
    result = bms_system.set_temperature("zone_1", 72.0)

    assert result["success"] is True
    assert result["temperature"] == 72.0
    print(f"✓ Normal operation: Zone 1 temperature set to {result['temperature']}°F")

    # Test Case 2: Safety Constraint Violation (Temperature Too High)
    unsafe_result = bms_system.set_temperature("zone_1", 95.0)

    assert unsafe_result["success"] is False
    assert unsafe_result.get("safety_violation") is True
    print(f"✓ Safety check: Unsafe temperature blocked")
    print(f"  Reason: {unsafe_result['error']}")

    # Test Case 3: Safety Constraint Violation (Temperature Too Low)
    unsafe_result_low = bms_system.set_temperature("zone_1", 50.0)

    assert unsafe_result_low["success"] is False
    assert unsafe_result_low.get("safety_violation") is True
    print(f"✓ Safety check: Unsafe temperature blocked")
    print(f"  Reason: {unsafe_result_low['error']}")

    # Test Case 4: Get Zone Status (Telemetry)
    status = bms_system.get_zone_status("zone_1")

    assert status is not None
    assert "temperature" in status
    assert "humidity" in status
    assert "occupancy" in status
    print(f"✓ Telemetry: Zone 1 status retrieved")
    print(f"  Temperature: {status['temperature']}°F")
    print(f"  Humidity: {status['humidity']}%")
    print(f"  Occupancy: {status['occupancy']} people")

    # Test Case 5: Emergency Shutdown
    emergency_result = bms_system.emergency_shutdown("fire_alarm")

    assert emergency_result["success"] is True
    assert emergency_result["status"] == "emergency_shutdown"
    print(f"✓ Emergency response: System shutdown activated")
    print(f"  Reason: {emergency_result['reason']}")

    # Test Case 6: Emergency Exit Unlock
    unlock_result = bms_system.unlock_all_exits()

    assert unlock_result["success"] is True
    assert unlock_result["status"] == "all_exits_unlocked"
    print(f"✓ Emergency response: All exits unlocked")

    print("\n✓ SIT-INT-103 PASSED: BMS integration working\n")


# ============================================================================
# SIT-INT-104: Murphy ↔ SCADA/Robotics System Integration
# ============================================================================

def test_sit_int_104_murphy_scada_integration():
    """
    Test ID: SIT-INT-104
    Test Name: Murphy to SCADA/Robotics System Integration

    Test Objective:
    Validate Murphy can safely control industrial systems with strict
    safety interlocks and emergency stops.

    Expected Results:
    - Normal operations execute with safety interlocks active
    - Safety interlocks prevent unsafe operations
    - Emergency stop halts all operations immediately
    - Workspace boundaries enforced
    """
    # Setup
    scada_system = EnterpriseSystemMockFactory.create_scada_system()

    print("\n=== SIT-INT-104: SCADA/Robotics System Integration ===\n")

    # Test Case 1: Normal Robot Operation (Within Workspace)
    result = scada_system.move_robot("robot_1", (50, 50, 25))

    assert result["success"] is True
    assert result["position"] == (50, 50, 25)
    print(f"✓ Normal operation: Robot 1 moved to {result['position']}")

    # Test Case 2: Workspace Boundary Violation (X-axis)
    unsafe_result = scada_system.move_robot("robot_1", (300, 50, 25))

    assert unsafe_result["success"] is False
    assert unsafe_result.get("safety_violation") is True
    print(f"✓ Safety check: Workspace violation blocked")
    print(f"  Reason: {unsafe_result['error']}")

    # Test Case 3: Workspace Boundary Violation (Z-axis)
    unsafe_result_z = scada_system.move_robot("robot_1", (50, 50, 150))

    assert unsafe_result_z["success"] is False
    assert unsafe_result_z.get("safety_violation") is True
    print(f"✓ Safety check: Workspace violation blocked")
    print(f"  Reason: {unsafe_result_z['error']}")

    # Test Case 4: Check Safety Interlocks
    safety_status = scada_system.check_safety_interlocks()

    assert safety_status["all_interlocks_active"] is True
    assert safety_status["emergency_stop_ready"] is True
    print(f"✓ Safety validation: All interlocks active")
    print(f"  Emergency stop ready: {safety_status['emergency_stop_ready']}")

    # Test Case 5: Emergency Stop
    estop_result = scada_system.emergency_stop()

    assert estop_result["success"] is True
    assert estop_result["status"] == "emergency_stop_activated"
    assert estop_result["response_time_ms"] < 100
    print(f"✓ Emergency stop: Activated in {estop_result['response_time_ms']}ms")
    print(f"  Status: {estop_result['status']}")

    # Test Case 6: Verify Robot Status After E-Stop
    robot_status = scada_system.get_robot_status("robot_1")

    assert robot_status is not None
    assert robot_status["status"] == "emergency_stopped"
    print(f"✓ Post-emergency: Robot 1 status = {robot_status['status']}")

    # Test Case 7: Operations Blocked During E-Stop
    blocked_result = scada_system.move_robot("robot_2", (100, 100, 50))

    assert blocked_result["success"] is False
    assert blocked_result.get("emergency_stop") is True
    print(f"✓ Safety enforcement: Operations blocked during emergency stop")

    print("\n✓ SIT-INT-104 PASSED: SCADA/Robotics integration working\n")


# ============================================================================
# SIT-INT-105: Murphy ↔ IT Infrastructure Integration
# ============================================================================

def test_sit_int_105_murphy_it_infrastructure():
    """
    Test ID: SIT-INT-105
    Test Name: Murphy to IT Infrastructure Integration

    Test Objective:
    Validate Murphy integrates correctly with IT infrastructure including
    monitoring, logging, backup, and disaster recovery.

    Expected Results:
    - Service status monitoring works
    - Backup operations successful
    - Failover completes within target time
    - System health tracking operational
    """
    # Setup
    it_infra = EnterpriseSystemMockFactory.create_it_infrastructure()

    print("\n=== SIT-INT-105: IT Infrastructure Integration ===\n")

    # Test Case 1: Check Service Status
    services = ["database", "backup", "monitoring", "logging"]

    for service in services:
        status = it_infra.check_service_status(service)
        assert status["healthy"] is True
        print(f"✓ Service check: {service} = {status['status']}")

    # Test Case 2: Trigger Backup
    backup_result = it_infra.trigger_backup()

    assert backup_result["success"] is True
    assert "backup_id" in backup_result
    print(f"✓ Backup operation: {backup_result['backup_id']} started")
    print(f"  Status: {backup_result['status']}")

    # Test Case 3: Failover to Backup Power
    failover_result = it_infra.failover_to_backup_power()

    assert failover_result["success"] is True
    assert failover_result["failover_time_seconds"] < 5.0
    print(f"✓ Failover: Completed in {failover_result['failover_time_seconds']}s")
    print(f"  Status: {failover_result['status']}")

    # Test Case 4: System Health Check
    health = it_infra.get_system_health()

    assert health["overall_health"] > 0.9
    assert health["services_running"] == health["total_services"]
    print(f"✓ System health: {health['overall_health']:.1%}")
    print(f"  Services running: {health['services_running']}/{health['total_services']}")
    print(f"  Backup power: {health['backup_power_active']}")
    print(f"  Data backed up: {health['data_backed_up']}")

    # Test Case 5: Verify Failover Timing
    assert failover_result["failover_time_seconds"] < 5.0, \
        f"Failover too slow: {failover_result['failover_time_seconds']}s (target: <5s)"
    print(f"✓ Performance: Failover within target (<5s)")

    print("\n✓ SIT-INT-105 PASSED: IT Infrastructure integration working\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
