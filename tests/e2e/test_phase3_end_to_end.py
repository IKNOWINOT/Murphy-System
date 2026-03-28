"""
Phase 3: End-to-End System Testing

Tests complete workflows across all Murphy System components to ensure
end-to-end functionality, safety constraints, and performance requirements.
"""

import pytest
import asyncio
import time
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Import all Murphy System components
import pytest
try:
    from src.confidence_engine import ConfidenceEngine
    from src.gate_synthesis import GateSynthesisEngine
    from src.deterministic_compute import ComputePlane
    from src.execution_compiler import ExecutionPacketCompiler
    from src.execution_orchestrator import ExecutionOrchestrator
    from src.synthetic_failure_generator import SyntheticFailureGenerator
    from src.supervisor_system.assumption_management import AssumptionRegistry
    from src.org_compiler.shadow_learning import ShadowLearningAgent
    from src.communication_system.pipeline import MessageIngestor
    from src.security_plane.data_leak_prevention import DataLeakPreventionSystem

    # Import enterprise system mocks
    from tests.integration.mocks.enterprise_systems import (
        HRSystem, BuildingManagementSystem, SCADARoboticsSystem,
        ITInfrastructureSystem, SecuritySystem
    )
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)


class TestHROnboardingWorkflow:
    """Test complete HR onboarding workflow (SIT-E2E-201)"""

    @pytest.fixture
    async def setup(self):
        """Setup test environment"""
        # Initialize all Murphy components
        self.confidence_engine = ConfidenceEngine()
        self.gate_synthesis = GateSynthesisEngine()
        self.compute_plane = ComputePlane()
        self.packet_compiler = ExecutionPacketCompiler()
        self.orchestrator = ExecutionOrchestrator()
        self.failure_generator = SyntheticFailureGenerator()
        self.assumption_registry = AssumptionRegistry()
        self.dlp_system = DataLeakPreventionSystem()

        # Initialize enterprise systems
        self.hr_system = HRSystem()
        self.it_system = ITInfrastructureSystem()
        self.security_system = SecuritySystem()

        # Test data
        self.employee_data = {
            "employee_id": "E2024-001",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@company.com",
            "phone": "+1-555-123-4567",
            "ssn": "123-45-6789",  # PII
            "address": "123 Main St, City, ST 12345",
            "date_of_birth": "1990-01-01",
            "department": "Engineering",
            "position": "Software Engineer",
            "salary": 95000,
            "start_date": "2024-02-01",
            "manager_id": "MGR-001"
        }

        yield

        # Cleanup
        await self.orchestrator.shutdown()
        await self.failure_generator.shutdown()

    async def test_01_employee_registration_and_pii_protection(self, setup):
        """Test new employee registration with PII classification"""
        print("\n=== Testing Employee Registration and PII Protection ===")

        # Step 1: Submit employee registration
        registration_result = await self.hr_system.register_employee(self.employee_data)
        assert registration_result["status"] == "pending_approval"
        assert "employee_id" in registration_result
        print(f"✓ Employee registration submitted: {registration_result['employee_id']}")

        # Step 2: Verify PII classification by DLP
        classified_data = await self.dlp_system.classify_data(self.employee_data)
        assert classified_data["sensitivity_level"] in ["CONFIDENTIAL", "SECRET"]
        assert "pii" in classified_data["categories"]
        assert "financial" in classified_data["categories"]
        print(f"✓ PII classified as: {classified_data['sensitivity_level']}")

        # Step 3: Verify encryption requirements enforced
        encryption_required = await self.dlp_system.check_encryption_requirements(self.employee_data)
        assert encryption_required["at_rest"] == True
        assert encryption_required["in_transit"] == True
        print("✓ Encryption requirements enforced")

        # Step 4: Create hypothesis for approval workflow
        from src.bridge_layer.hypothesis import HypothesisArtifact
        hypothesis = HypothesisArtifact(
            id=str(uuid.uuid4()),
            title="Employee Onboarding Approval",
            description=f"Approve onboarding for {self.employee_data['first_name']} {self.employee_data['last_name']}",
            plan_summary=f"New employee {self.employee_data['employee_id']} requires access provisioning",
            assumptions=[
                "Employee background check will pass",
                "Manager has authority to approve",
                "IT resources are available"
            ],
            created_by="hr_system",
            status="sandbox"
        )

        # Step 5: Register assumptions
        for assumption_text in hypothesis.assumptions:
            assumption = await self.assumption_registry.register_assumption(
                text=assumption_text,
                context=hypothesis.id,
                source="hr_system"
            )
            assert assumption.requires_external_validation == True
        print(f"✓ Registered {len(hypothesis.assumptions)} assumptions")

        print("✓ Employee registration and PII protection test PASSED")

    async def test_02_it_equipment_provisioning(self, setup):
        """Test IT equipment provisioning workflow"""
        print("\n=== Testing IT Equipment Provisioning ===")

        # Step 1: Determine equipment requirements based on position
        equipment_requirements = await self.it_system.get_equipment_requirements(
            self.employee_data["position"],
            self.employee_data["department"]
        )
        assert "laptop" in equipment_requirements
        assert "monitors" in equipment_requirements
        assert "access_card" in equipment_requirements
        print(f"✓ Equipment requirements determined: {list(equipment_requirements.keys())}")

        # Step 2: Check inventory availability
        inventory_status = await self.it_system.check_inventory(equipment_requirements)
        assert inventory_status["available"] == True
        print(f"✓ Inventory check passed: {inventory_status['available_items']}/{inventory_status['total_items']}")

        # Step 3: Create execution packet for equipment provisioning
        packet_data = {
            "employee_id": self.employee_data["employee_id"],
            "equipment": equipment_requirements,
            "action": "provision",
            "priority": "normal"
        }

        compiled_packet = await self.packet_compiler.compile_packet(
            packet_data=packet_data,
            authority_level="medium",
            requirements=["inventory_check", "manager_approval"]
        )
        assert compiled_packet is not None
        assert compiled_packet.execution_rights == True
        print("✓ Equipment provisioning packet compiled")

        # Step 4: Execute provisioning through orchestrator
        execution_result = await self.orchestrator.execute_packet(compiled_packet)
        assert execution_result["status"] == "success"
        assert "provisioned_items" in execution_result
        print(f"✓ Equipment provisioned: {execution_result['provisioned_items']}")

        print("✓ IT equipment provisioning test PASSED")

    async def test_03_access_credentials_generation(self, setup):
        """Test access credentials generation with security"""
        print("\n=== Testing Access Credentials Generation ===")

        # Step 1: Generate system credentials
        credentials_request = {
            "employee_id": self.employee_data["employee_id"],
            "email": self.employee_data["email"],
            "department": self.employee_data["department"],
            "position": self.employee_data["position"],
            "access_level": "standard"
        }

        credentials = await self.security_system.generate_credentials(credentials_request)
        assert "username" in credentials
        assert "password" in credentials  # Temporary password
        assert "mfa_secret" in credentials
        assert "access_card_id" in credentials
        print("✓ System credentials generated")

        # Step 2: Verify credentials meet security requirements
        password_strength = await self.security_system.check_password_strength(credentials["password"])
        assert password_strength["score"] >= 3  # Minimum strength
        assert password_strength["length"] >= 12
        assert password_strength["has_uppercase"] == True
        assert password_strength["has_lowercase"] == True
        assert password_strength["has_numbers"] == True
        assert password_strength["has_special"] == True
        print("✓ Password strength requirements met")

        # Step 3: Check DLP classification for credentials
        credentials_classified = await self.dlp_system.classify_data(credentials)
        assert credentials_classified["sensitivity_level"] == "SECRET"
        assert "authentication" in credentials_classified["categories"]
        print("✓ Credentials properly classified as SECRET")

        # Step 4: Verify credentials are encrypted
        encryption_check = await self.dlp_system.check_encryption_requirements(credentials)
        assert encryption_check["at_rest"] == True
        assert encryption_check["in_transit"] == True
        print("✓ Credentials encryption enforced")

        print("✓ Access credentials generation test PASSED")

    async def test_04_compliance_training_assignment(self, setup):
        """Test compliance training assignment workflow"""
        print("\n=== Testing Compliance Training Assignment ===")

        # Step 1: Determine required training based on role
        training_requirements = await self.hr_system.get_training_requirements(
            self.employee_data["position"],
            self.employee_data["department"]
        )
        assert len(training_requirements) > 0
        assert any("security" in t["category"].lower() for t in training_requirements)
        assert any("compliance" in t["category"].lower() for t in training_requirements)
        print(f"✓ Training requirements determined: {len(training_requirements)} courses")

        # Step 2: Create training assignments
        assignments = []
        for training in training_requirements:
            assignment = {
                "employee_id": self.employee_data["employee_id"],
                "course_id": training["id"],
                "course_name": training["name"],
                "category": training["category"],
                "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
                "mandatory": training["mandatory"]
            }
            assignments.append(assignment)

        # Step 3: Submit assignments through execution packet
        training_packet = await self.packet_compiler.compile_packet(
            packet_data={
                "action": "assign_training",
                "assignments": assignments
            },
            authority_level="medium",
            requirements=["hr_approval"]
        )

        training_result = await self.orchestrator.execute_packet(training_packet)
        assert training_result["status"] == "success"
        assert training_result["assigned_courses"] == len(assignments)
        print(f"✓ Training assignments created: {training_result['assigned_courses']} courses")

        # Step 4: Verify audit trail for compliance
        audit_trail = await self.orchestrator.get_audit_trail(training_packet.id)
        assert len(audit_trail) > 0
        assert any("training_assigned" in entry["action"] for entry in audit_trail)
        print("✓ Compliance audit trail verified")

        print("✓ Compliance training assignment test PASSED")

    async def test_05_manager_approval_workflow(self, setup):
        """Test manager approval workflow with safety checks"""
        print("\n=== Testing Manager Approval Workflow ===")

        # Step 1: Create approval request for manager
        approval_request = {
            "request_id": str(uuid.uuid4()),
            "employee_id": self.employee_data["employee_id"],
            "request_type": "onboarding_approval",
            "requested_by": "hr_system",
            "approver_id": self.employee_data["manager_id"],
            "details": {
                "employee_name": f"{self.employee_data['first_name']} {self.employee_data['last_name']}",
                "position": self.employee_data["position"],
                "department": self.employee_data["department"],
                "start_date": self.employee_data["start_date"],
                "equipment_provisioned": True,
                "credentials_generated": True,
                "training_assigned": True
            }
        }

        # Step 2: Submit approval request
        approval_result = await self.hr_system.submit_approval_request(approval_request)
        assert approval_result["status"] == "pending_manager_approval"
        assert "approval_id" in approval_result
        print(f"✓ Approval request submitted: {approval_result['approval_id']}")

        # Step 3: Verify manager authority
        manager_authority = await self.security_system.check_user_authority(
            self.employee_data["manager_id"],
            "approve_onboarding"
        )
        assert manager_authority["has_authority"] == True
        assert manager_authority["authority_level"] >= "medium"
        print("✓ Manager authority verified")

        # Step 4: Process manager approval
        approval_response = {
            "approval_id": approval_result["approval_id"],
            "decision": "approved",
            "approver_id": self.employee_data["manager_id"],
            "approver_comments": "All requirements met, approve onboarding",
            "timestamp": datetime.now().isoformat()
        }

        processed_approval = await self.hr_system.process_approval(approval_response)
        assert processed_approval["status"] == "approved"
        assert processed_approval["final_decision"] == "approved"
        print("✓ Manager approval processed")

        # Step 5: Verify approval cannot be modified (immutable)
        try:
            modification_attempt = await self.hr_system.modify_approval(
                approval_result["approval_id"],
                {"decision": "denied"}
            )
            assert False, "Should not allow modification of approved request"
        except Exception as e:
            assert "immutable" in str(e).lower()
            print("✓ Approval immutability enforced")

        print("✓ Manager approval workflow test PASSED")

    async def test_06_system_access_activation(self, setup):
        """Test final system access activation"""
        print("\n=== Testing System Access Activation ===")

        # Step 1: Verify all prerequisites are met
        prerequisites = await self.hr_system.check_onboarding_prerequisites(
            self.employee_data["employee_id"]
        )
        assert prerequisites["equipment_provisioned"] == True
        assert prerequisites["credentials_generated"] == True
        assert prerequisites["training_assigned"] == True
        assert prerequisites["manager_approved"] == True
        assert prerequisites["background_check"] == "passed"
        print("✓ All prerequisites verified")

        # Step 2: Create activation execution packet
        activation_packet = await self.packet_compiler.compile_packet(
            packet_data={
                "action": "activate_system_access",
                "employee_id": self.employee_data["employee_id"],
                "activation_timestamp": datetime.now().isoformat()
            },
            authority_level="high",
            requirements=[
                "prerequisites_met",
                "manager_approval",
                "security_clearance"
            ]
        )

        # Step 3: Execute activation
        activation_result = await self.orchestrator.execute_packet(activation_packet)
        assert activation_result["status"] == "success"
        assert activation_result["access_activated"] == True
        assert "activation_timestamp" in activation_result
        print(f"✓ System access activated: {activation_result['activation_timestamp']}")

        # Step 4: Verify access is functional
        access_test = await self.security_system.test_system_access(
            self.employee_data["employee_id"]
        )
        assert access_test["access_granted"] == True
        assert access_test["access_level"] == "standard"
        print("✓ System access functionality verified")

        # Step 5: Complete audit trail verification
        complete_audit_trail = await self.orchestrator.get_complete_workflow_audit(
            self.employee_data["employee_id"],
            "onboarding"
        )
        assert len(complete_audit_trail) >= 6  # All major steps
        required_steps = [
            "employee_registration",
            "equipment_provisioned",
            "credentials_generated",
            "training_assigned",
            "manager_approval",
            "access_activated"
        ]
        for step in required_steps:
            assert any(step in entry["action"] for entry in complete_audit_trail)
        print(f"✓ Complete audit trail verified: {len(complete_audit_trail)} steps")

        print("✓ System access activation test PASSED")

    async def test_07_compliance_and_safety_validation(self, setup):
        """Test overall compliance and safety constraints"""
        print("\n=== Testing Compliance and Safety Validation ===")

        # Step 1: GDPR compliance check
        gdpr_compliance = await self.dlp_system.check_gdpr_compliance(
            self.employee_data["employee_id"]
        )
        assert gdpr_compliance["compliant"] == True
        assert gdpr_compliance["data_minimized"] == True
        assert gdpr_compliance["consent_recorded"] == True
        assert gdpr_compliance["retention_policy_applied"] == True
        print("✓ GDPR compliance verified")

        # Step 2: Data retention policy
        retention_check = await self.dlp_system.check_retention_compliance(
            self.employee_data["employee_id"]
        )
        assert retention_check["compliant"] == True
        assert retention_check["retention_schedule"] == "7_years_for_employee_data"
        print("✓ Data retention policy enforced")

        # Step 3: Safety constraints verification
        safety_constraints = await self.orchestrator.verify_safety_constraints(
            self.employee_data["employee_id"]
        )
        assert safety_constraints["all_constraints_satisfied"] == True
        assert safety_constraints["no_unauthorized_access"] == True
        assert safety_constraints["pii_protected"] == True
        assert safety_constraints["audit_trail_complete"] == True
        print("✅ All safety constraints satisfied")

        # Step 4: Performance metrics
        performance_metrics = await self.orchestrator.get_workflow_performance_metrics(
            "hr_onboarding"
        )
        assert performance_metrics["completion_time"] < 3600  # Less than 1 hour
        assert performance_metrics["success_rate"] == 1.0  # 100% success
        assert performance_metrics["compliance_score"] >= 0.95  # 95%+ compliant
        print(f"✓ Performance targets met: {performance_metrics['completion_time']}s completion")

        print("✅ Compliance and safety validation test PASSED")


class TestBuildingEmergencyWorkflow:
    """Test building emergency response workflow (SIT-E2E-202)"""

    @pytest.fixture
    async def setup(self):
        """Setup test environment"""
        # Initialize components
        self.orchestrator = ExecutionOrchestrator()
        self.packet_compiler = ExecutionPacketCompiler()
        self.confidence_engine = ConfidenceEngine()
        self.gate_synthesis = GateSynthesisEngine()
        self.failure_generator = SyntheticFailureGenerator()

        # Initialize systems
        self.bms = BuildingManagementSystem()
        self.security_system = SecuritySystem()
        self.it_system = ITInfrastructureSystem()

        # Emergency scenario data
        self.emergency_scenario = {
            "incident_id": "EMR-2024-001",
            "incident_type": "fire",
            "location": "Building A, Floor 3, Room 301",
            "severity": "high",
            "timestamp": datetime.now().isoformat(),
            "affected_zones": ["A-3-301", "A-3-302", "A-3-303"],
            "occupants": {
                "total": 45,
                "evacuated": 0,
                "requires_assistance": 2
            }
        }

        yield

        await self.orchestrator.shutdown()
        await self.failure_generator.shutdown()

    async def test_01_fire_alarm_detection_and_initial_response(self, setup):
        """Test fire alarm detection and initial response"""
        print("\n=== Testing Fire Alarm Detection and Initial Response ===")

        # Step 1: Simulate fire alarm activation
        alarm_activation = await self.bms.activate_fire_alarm(
            zone="A-3-301",
            severity="high",
            source="smoke_detector_301"
        )
        assert alarm_activation["status"] == "activated"
        assert alarm_activation["alarm_id"] is not None
        print(f"✓ Fire alarm activated: {alarm_activation['alarm_id']}")

        # Step 2: Verify immediate safety responses
        initial_responses = await self.bms.get_immediate_responses(alarm_activation["alarm_id"])
        assert "hvac_shutdown" in initial_responses
        assert "elevator_recall" in initial_responses
        assert "emergency_lighting" in initial_responses
        assert "public_address" in initial_responses
        print(f"✓ Immediate safety responses: {list(initial_responses.keys())}")

        # Step 3: Check confidence computation for emergency response
        confidence_assessment = await self.confidence_engine.compute_confidence({
            "incident_type": "fire",
            "severity": "high",
            "detection_confidence": 0.95,
            "multiple_detectors": True
        })
        assert confidence_assessment["confidence"] >= 0.9
        assert confidence_assessment["authority"] == "high"
        print(f"✓ Emergency confidence: {confidence_assessment['confidence']:.2f}")

        # Step 4: Create emergency response packet
        emergency_packet = await self.packet_compiler.compile_packet(
            packet_data={
                "action": "emergency_response",
                "incident_id": self.emergency_scenario["incident_id"],
                "incident_type": "fire",
                "location": self.emergency_scenario["location"],
                "severity": self.emergency_scenario["severity"]
            },
            authority_level="emergency",
            requirements=["fire_alarm_active", "safety_critical"]
        )

        # Step 5: Execute emergency response
        response_result = await self.orchestrator.execute_packet(emergency_packet)
        assert response_result["status"] == "success"
        assert response_result["emergency_mode"] == True
        print("✓ Emergency response initiated")

        print("✓ Fire alarm detection test PASSED")

    async def test_02_emergency_shutdown_activation(self, setup):
        """Test emergency shutdown of building systems"""
        print("\n=== Testing Emergency Shutdown Activation ===")

        # Step 1: Initiate emergency shutdown
        shutdown_command = {
            "incident_id": self.emergency_scenario["incident_id"],
            "shutdown_type": "emergency_fire",
            "zones": self.emergency_scenario["affected_zones"],
            "systems": ["hvac", "electrical_non_essential", "gas", "elevators"]
        }

        shutdown_packet = await self.packet_compiler.compile_packet(
            packet_data=shutdown_command,
            authority_level="emergency",
            requirements=["emergency_authority", "safety_critical"]
        )

        shutdown_result = await self.orchestrator.execute_packet(shutdown_packet)
        assert shutdown_result["status"] == "success"
        assert shutdown_result["systems_shutdown"] == len(shutdown_command["systems"])
        print(f"✓ Emergency shutdown: {shutdown_result['systems_shutdown']} systems")

        # Step 2: Verify individual system shutdowns
        for system in shutdown_command["systems"]:
            system_status = await self.bms.get_system_status(system)
            assert system_status["status"] == "shutdown"
            assert system_status["emergency_mode"] == True
        print("✓ All systems verified in shutdown state")

        # Step 3: Maintain critical systems
        critical_systems = await self.bms.get_critical_systems_status()
        assert critical_systems["emergency_lighting"] == "active"
        assert critical_systems["fire_suppression"] == "standby"
        assert critical_systems["life_safety"] == "active"
        print("✓ Critical systems maintained")

        # Step 4: Verify shutdown timing < 5 seconds
        shutdown_timing = await self.orchestrator.get_execution_timing(shutdown_packet.id)
        assert shutdown_timing["total_time"] < 5.0
        print(f"✓ Emergency shutdown completed in {shutdown_timing['total_time']:.2f}s")

        print("✓ Emergency shutdown test PASSED")

    async def test_03_occupant_evacuation_routing(self, setup):
        """Test occupant evacuation and routing"""
        print("\n=== Testing Occupant Evacuation Routing ===")

        # Step 1: Calculate optimal evacuation routes
        evacuation_routes = await self.bms.calculate_evacuation_routes(
            affected_zones=self.emergency_scenario["affected_zones"],
            incident_location=self.emergency_scenario["location"],
            occupancy=self.emergency_scenario["occupants"]["total"]
        )
        assert len(evacuation_routes) > 0
        assert all("exit_id" in route for route in evacuation_routes)
        assert all("capacity" in route for route in evacuation_routes)
        print(f"✓ Evacuation routes calculated: {len(evacuation_routes)} routes")

        # Step 2: Start evacuation monitoring
        evacuation_monitor = await self.bms.start_evacuation_monitoring(
            incident_id=self.emergency_scenario["incident_id"],
            expected_evacuees=self.emergency_scenario["occupants"]["total"]
        )
        assert evacuation_monitor["status"] == "active"
        assert evacuation_monitor["monitoring_id"] is not None
        print(f"✓ Evacuation monitoring started: {evacuation_monitor['monitoring_id']}")

        # Step 3: Simulate occupant evacuation
        evacuation_progress = await self.bms.simulate_evacuation_progress(
            monitoring_id=evacuation_monitor["monitoring_id"],
            evacuated_count=35,
            requires_assistance=2
        )
        assert evacuation_progress["total_evacuated"] == 35
        assert evacuation_progress["requires_assistance"] == 2
        assert evacuation_progress["remaining"] == 10
        print(f"✓ Evacuation progress: {evacuation_progress['total_evacuated']}/{self.emergency_scenario['occupants']['total']}")

        # Step 4: Update routing based on congestion
        routing_update = await self.bms.update_evacuation_routing(
            monitoring_id=evacuation_monitor["monitoring_id"],
            congestion_zones=["A-3-corridor-1"],
            alternate_routes=True
        )
        assert routing_update["routes_updated"] == True
        assert len(routing_update["new_routes"]) > 0
        print("✓ Dynamic routing updated for congestion")

        # Step 5: Complete evacuation
        evacuation_complete = await self.bms.complete_evacuation(
            monitoring_id=evacuation_monitor["monitoring_id"],
            final_evacuated=45,
            assists_completed=2
        )
        assert evacuation_complete["status"] == "completed"
        assert evacuation_complete["all_clear"] == False  # Still need fire department
        print(f"✓ Evacuation completed: {evacuation_complete['total_evacuated']} evacuated")

        print("✓ Occupant evacuation test PASSED")

    async def test_04_emergency_services_notification(self, setup):
        """Test emergency services notification"""
        print("\n=== Testing Emergency Services Notification ===")

        # Step 1: Prepare emergency notification data
        notification_data = {
            "incident_id": self.emergency_scenario["incident_id"],
            "incident_type": "fire",
            "severity": "high",
            "location": self.emergency_scenario["location"],
            "reporting_time": datetime.now().isoformat(),
            "occupant_status": {
                "total_occupants": self.emergency_scenario["occupants"]["total"],
                "evacuated": 45,
                "requires_assistance": 2,
                "assisted": 2
            },
            "building_status": {
                "fire_alarm": "active",
                "sprinkler_system": "activated",
                "emergency_lighting": "active",
                "hvac": "shutdown"
            },
            "access_points": {
                "main_entrance": "accessible",
                "emergency_exits": "all_unlocked",
                "fire_lane": "clear"
            }
        }

        # Step 2: Send notifications to emergency services
        notifications_sent = await self.security_system.notify_emergency_services(
            notification_data=notification_data,
            services=["fire_department", "police", "ambulance"]
        )
        assert notifications_sent["fire_department"]["status"] == "sent"
        assert notifications_sent["police"]["status"] == "sent"
        assert notifications_sent["ambulance"]["status"] == "sent"
        print(f"✓ Emergency notifications sent: {len(notifications_sent)} services")

        # Step 3: Verify notification content
        fire_notification = notifications_sent["fire_department"]
        assert "incident_id" in fire_notification
        assert "location" in fire_notification
        assert "severity" in fire_notification
        assert "access_points" in fire_notification
        print("✓ Notification content verified")

        # Step 4: Track emergency services response
        response_tracking = await self.security_system.track_emergency_response(
            incident_id=self.emergency_scenario["incident_id"]
        )
        assert response_tracking["fire_department"]["eta"] <= 300  # 5 minutes max
        assert response_tracking["incident_status"] == "active"
        print(f"✓ Emergency response tracking: ETA {response_tracking['fire_department']['eta']}s")

        # Step 5: Update building access for emergency services
        access_update = await self.security_system.update_emergency_access(
            incident_id=self.emergency_scenario["incident_id"],
            emergency_services=True,
            access_level="emergency_responder"
        )
        assert access_update["access_granted"] == True
        assert access_update["access_points_unlocked"] > 0
        print("✓ Emergency services access configured")

        print("✓ Emergency services notification test PASSED")

    async def test_05_building_systems_lockdown(self, setup):
        """Test building systems lockdown procedures"""
        print("\n=== Testing Building Systems Lockdown ===")

        # Step 1: Implement full building lockdown
        lockdown_command = {
            "incident_id": self.emergency_scenario["incident_id"],
            "lockdown_type": "emergency_fire",
            "affected_areas": ["entire_building"],
            "systems_to_control": [
                "access_control", "hvac", "elevators", "electrical",
                "gas", "water", "data_networks"
            ]
        }

        lockdown_packet = await self.packet_compiler.compile_packet(
            packet_data=lockdown_command,
            authority_level="emergency",
            requirements=["emergency_authority", "life_safety_priority"]
        )

        lockdown_result = await self.orchestrator.execute_packet(lockdown_packet)
        assert lockdown_result["status"] == "success"
        assert lockdown_result["lockdown_active"] == True
        print("✓ Building lockdown implemented")

        # Step 2: Verify access control lockdown
        access_status = await self.bms.get_access_control_status()
        assert access_status["external_access"] == "blocked"
        assert access_status["internal_movement"] == "restricted"
        assert access_status["emergency_exits"] == "unlocked"
        assert access_status["emergency_responder_access"] == "granted"
        print("✓ Access control lockdown verified")

        # Step 3: Verify system isolation
        system_isolation = await self.bms.get_system_isolation_status()
        for system in lockdown_command["systems_to_control"]:
            if system in system_isolation:
                assert system_isolation[system]["isolated"] == True
        print("✓ System isolation verified")

        # Step 4: Maintain life safety systems
        life_safety = await self.bms.get_life_safety_status()
        assert life_safety["emergency_lighting"] == "active"
        assert life_safety["fire_suppression"] == "ready"
        assert life_safety["emergency_power"] == "active"
        assert life_safety["communication_systems"] == "active"
        print("✓ Life safety systems maintained")

        # Step 5: Verify lockdown timing
        lockdown_timing = await self.orchestrator.get_execution_timing(lockdown_packet.id)
        assert lockdown_timing["total_time"] < 10.0  # 10 second target
        print(f"✓ Lockdown completed in {lockdown_timing['total_time']:.2f}s")

        print("✓ Building systems lockdown test PASSED")

    async def test_06_post_event_recovery(self, setup):
        """Test post-event recovery procedures"""
        print("\n=== Testing Post-Event Recovery ===")

        # Step 1: Wait for all-clear from fire department
        all_clear_simulation = {
            "incident_id": self.emergency_scenario["incident_id"],
            "all_clear": True,
            "clearing_authority": "fire_department",
            "clear_time": datetime.now().isoformat(),
            "inspected_areas": self.emergency_scenario["affected_zones"],
            "safe_areas": ["Building A - Floors 1,2,4,5"],
            "restricted_areas": ["Building A - Floor 3"]
        }

        # Step 2: Start controlled recovery sequence
        recovery_sequence = await self.bms.start_recovery_sequence(all_clear_simulation)
        assert recovery_sequence["status"] == "initiated"
        assert recovery_sequence["recovery_id"] is not None
        print(f"✓ Recovery sequence started: {recovery_sequence['recovery_id']}")

        # Step 3: Phase 1 - Restore safe areas
        safe_areas_restored = await self.bms.restore_safe_areas(
            recovery_id=recovery_sequence["recovery_id"],
            areas=all_clear_simulation["safe_areas"],
            systems=["hvac", "lighting", "data_networks"]
        )
        assert safe_areas_restored["areas_restored"] == len(all_clear_simulation["safe_areas"])
        assert safe_areas_restored["systems_active"] > 0
        print(f"✓ Safe areas restored: {safe_areas_restored['areas_restored']} areas")

        # Step 4: Phase 2 - Controlled access restoration
        access_restoration = await self.bms.restore_access_control(
            recovery_id=recovery_sequence["recovery_id"],
            access_level="restricted",
            authorized_personnel=["maintenance", "security", "management"]
        )
        assert access_restoration["access_restored"] == True
        assert access_restoration["authorization_required"] == True
        print("✓ Controlled access restored")

        # Step 5: Phase 3 - System diagnostics
        system_diagnostics = await self.bms.run_system_diagnostics(
            recovery_id=recovery_sequence["recovery_id"],
            all_systems=True
        )
        assert system_diagnostics["diagnostics_complete"] == True
        assert system_diagnostics["systems_healthy"] > 0
        assert system_diagnostics["systems_needing_attention"] >= 0
        print(f"✓ System diagnostics: {system_diagnostics['systems_healthy']} healthy")

        # Step 6: Generate recovery report
        recovery_report = await self.bms.generate_recovery_report(
            incident_id=self.emergency_scenario["incident_id"],
            recovery_id=recovery_sequence["recovery_id"]
        )
        assert recovery_report["incident_summary"]["incident_type"] == "fire"
        assert recovery_report["recovery_actions"]["total_actions"] > 0
        assert recovery_report["system_status"]["operational_percentage"] > 0
        print("✓ Recovery report generated")

        print("✓ Post-event recovery test PASSED")

    async def test_07_safety_audit_trail(self, setup):
        """Test complete safety audit trail"""
        print("\n=== Testing Safety Audit Trail ===")

        # Step 1: Collect complete emergency workflow audit
        emergency_audit = await self.orchestrator.get_workflow_audit_trail(
            workflow_id=self.emergency_scenario["incident_id"],
            workflow_type="emergency_response"
        )
        assert len(emergency_audit) >= 10  # All major emergency steps

        # Step 2: Verify critical events are logged
        critical_events = [
            "fire_alarm_activated",
            "emergency_shutdown",
            "evacuation_started",
            "emergency_services_notified",
            "building_lockdown",
            "recovery_initiated"
        ]

        for event in critical_events:
            assert any(event in entry["action"].lower() for entry in emergency_audit), f"Missing event: {event}"
        print(f"✓ All critical events logged: {len(emergency_audit)} entries")

        # Step 3: Verify audit trail integrity
        audit_integrity = await self.orchestrator.verify_audit_integrity(emergency_audit)
        assert audit_integrity["integrity_valid"] == True
        assert audit_integrity["tampering_detected"] == False
        print("✓ Audit trail integrity verified")

        # Step 4: Check compliance with safety regulations
        safety_compliance = await self.orchestrator.check_safety_compliance(emergency_audit)
        assert safety_compliance["compliant"] == True
        assert safety_compliance["response_time_within_limits"] == True
        assert safety_compliance["all_protocols_followed"] == True
        print("✓ Safety compliance verified")

        # Step 5: Generate emergency response metrics
        response_metrics = await self.orchestrator.generate_response_metrics(
            incident_id=self.emergency_scenario["incident_id"]
        )
        assert response_metrics["total_response_time"] < 600  # 10 minutes max
        assert response_metrics["evacuation_time"] < 300  # 5 minutes max
        assert response_metrics["shutdown_time"] < 5  # 5 seconds max
        assert response_metrics["notification_time"] < 60  # 1 minute max
        print(f"✓ Response metrics within targets")
        print(f"  - Total response: {response_metrics['total_response_time']}s")
        print(f"  - Evacuation: {response_metrics['evacuation_time']}s")
        print(f"  - Shutdown: {response_metrics['shutdown_time']}s")
        print(f"  - Notifications: {response_metrics['notification_time']}s")

        print("✓ Safety audit trail test PASSED")


# Additional test classes for manufacturing and disaster recovery workflows
# would be implemented here following the same pattern...

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
