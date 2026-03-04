"""
Phase 3: End-to-End System Testing - Manufacturing & Disaster Recovery

Tests industrial manufacturing workflow and disaster recovery workflow
across all Murphy System components.
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
    from src.security_plane.data_leak_prevention import DataLeakPreventionSystem
    from src.recursive_stability_controller import RecursiveStabilityController

    # Import enterprise system mocks
    from tests.integration.mocks.enterprise_systems import (
        SCADARoboticsSystem, ITInfrastructureSystem, QualityControlSystem,
        ManufacturingExecutionSystem, SecuritySystem, BuildingManagementSystem
    )
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)


class TestIndustrialManufacturingWorkflow:
    """Test industrial manufacturing workflow (SIT-E2E-203)"""

    @pytest.fixture
    async def setup(self):
        """Setup test environment"""
        # Initialize Murphy components
        self.confidence_engine = ConfidenceEngine()
        self.gate_synthesis = GateSynthesisEngine()
        self.compute_plane = ComputePlane()
        self.packet_compiler = ExecutionPacketCompiler()
        self.orchestrator = ExecutionOrchestrator()
        self.failure_generator = SyntheticFailureGenerator()
        self.rsc = RecursiveStabilityController()
        self.dlp_system = DataLeakPreventionSystem()

        # Initialize enterprise systems
        self.scada_system = SCADARoboticsSystem()
        self.scada_system.set_runtime_bounds({
            "x_min": 0, "x_max": 1000,
            "y_min": 0, "y_max": 800,
            "z_min": 0, "z_max": 500
        })
        self.mes_system = ManufacturingExecutionSystem()
        self.qc_system = QualityControlSystem()
        self.security_system = SecuritySystem()
        self.bms = BuildingManagementSystem()

        # Manufacturing order data
        self.production_order = {
            "order_id": "PO-2024-001",
            "product_id": "PRD-001",
            "product_name": "Industrial Component A",
            "quantity": 1000,
            "priority": "normal",
            "due_date": (datetime.now() + timedelta(days=7)).isoformat(),
            "specifications": {
                "material": "Steel-316",
                "tolerance": "±0.01mm",
                "surface_finish": "Ra 0.8",
                "strength_requirement": "≥500 MPa"
            },
            "production_line": "Line-3",
            "required_equipment": [
                "CNC-Mill-001", "Robot-Arm-001",
                "Quality-Scanner-001", "Conveyor-001"
            ]
        }

        yield

        await self.orchestrator.shutdown()
        await self.failure_generator.shutdown()
        await self.rsc.shutdown()

    async def test_01_production_order_processing(self, setup):
        """Test production order processing and validation"""
        print("\n=== Testing Production Order Processing ===")

        # Step 1: Submit production order
        order_submission = await self.mes_system.submit_production_order(self.production_order)
        assert order_submission["status"] == "validated"
        assert order_submission["order_id"] == self.production_order["order_id"]
        assert "production_schedule" in order_submission
        print(f"✓ Production order validated: {order_submission['order_id']}")

        # Step 2: Verify resource availability
        resource_check = await self.mes_system.check_resource_availability(
            equipment=self.production_order["required_equipment"],
            line=self.production_order["production_line"]
        )
        assert resource_check["available"] == True
        assert resource_check["available_equipment"] >= len(self.production_order["required_equipment"])
        print(f"✓ Resource availability confirmed: {resource_check['available_equipment']} units")

        # Step 3: Compute production confidence
        production_confidence = await self.confidence_engine.compute_confidence({
            "order_complexity": "medium",
            "equipment_reliability": 0.95,
            "operator_availability": 1.0,
            "material_availability": 1.0,
            "quality_requirements": "standard"
        })
        assert production_confidence["confidence"] >= 0.8
        assert production_confidence["authority"] == "medium"
        print(f"✓ Production confidence: {production_confidence['confidence']:.2f}")

        # Step 4: Generate gates for safety and quality
        safety_gates = await self.gate_synthesis.generate_gates({
            "operation_type": "manufacturing",
            "risk_level": "medium",
            "safety_critical": True,
            "quality_requirements": self.production_order["specifications"]
        })
        assert len(safety_gates) >= 3  # Safety, quality, operational gates
        assert any("safety_interlock" in gate.type for gate in safety_gates)
        print(f"✓ Safety gates generated: {len(safety_gates)} gates")

        # Step 5: Create manufacturing execution packet
        manufacturing_packet = await self.packet_compiler.compile_packet(
            packet_data={
                "action": "execute_production",
                "order_id": self.production_order["order_id"],
                "production_line": self.production_order["production_line"],
                "equipment": self.production_order["required_equipment"],
                "specifications": self.production_order["specifications"]
            },
            authority_level="medium",
            requirements=[
                "resource_availability",
                "safety_interlocks_active",
                "quality_systems_ready"
            ]
        )

        print("✓ Production order processing test PASSED")
        return manufacturing_packet

    async def test_02_robot_arm_control_and_safety(self, setup):
        """Test robot arm control with safety interlocks"""
        print("\n=== Testing Robot Arm Control and Safety ===")

        # Step 1: Initialize robot arm for production
        robot_initialization = {
            "robot_id": "Robot-Arm-001",
            "operation_mode": "production",
            "program": "PRD-001-Program",
            "workspace_boundaries": {
                "x_min": 0, "x_max": 1000,
                "y_min": 0, "y_max": 800,
                "z_min": 0, "z_max": 500
            },
            "safety_limits": {
                "max_velocity": 1000,  # mm/s
                "max_acceleration": 5000,  # mm/s²
                "max_force": 500  # N
            }
        }

        robot_packet = await self.packet_compiler.compile_packet(
            packet_data={
                "action": "initialize_robot",
                **robot_initialization
            },
            authority_level="medium",
            requirements=["safety_check", "workspace_validation"]
        )

        init_result = await self.orchestrator.execute_packet(robot_packet)
        assert init_result["status"] == "success"
        assert init_result["robot_status"] == "initialized"
        print(f"✓ Robot arm initialized: {robot_initialization['robot_id']}")

        # Step 2: Verify safety interlocks are active
        safety_status = await self.scada_system.get_safety_interlock_status()
        assert safety_status["emergency_stop"] == "ready"
        assert safety_status["light_curtain"] == "active"
        assert safety_status["pressure_mat"] == "active"
        assert safety_status["safety_zone"] == "enforced"
        print("✓ Safety interlocks verified active")

        # Step 3: Test normal operation within boundaries
        normal_operation = {
            "robot_id": "Robot-Arm-001",
            "command": "move_to_position",
            "target_position": {"x": 500, "y": 400, "z": 250},
            "velocity": 500,  # Within limit
            "acceleration": 2000  # Within limit
        }

        operation_result = await self.scada_system.execute_robot_command(normal_operation)
        assert operation_result["status"] == "success"
        assert operation_result["position_reached"] == True
        assert operation_result["within_boundaries"] == True
        print("✓ Normal operation completed successfully")

        # Step 4: Test workspace boundary enforcement
        boundary_violation = {
            "robot_id": "Robot-Arm-001",
            "command": "move_to_position",
            "target_position": {"x": 1500, "y": 400, "z": 250},  # Outside boundary
            "velocity": 500
        }

        try:
            violation_result = await self.scada_system.execute_robot_command(boundary_violation)
            assert False, "Should not allow movement outside boundaries"
        except Exception as e:
            assert "boundary" in str(e).lower() or "violation" in str(e).lower()
            print("✓ Workspace boundary enforcement verified")

        # Step 5: Test emergency stop functionality
        emergency_stop_start = time.time()
        e_stop_result = await self.scada_system.trigger_emergency_stop("Robot-Arm-001")
        emergency_stop_time = time.time() - emergency_stop_start

        assert e_stop_result["status"] == "stopped"
        assert emergency_stop_time < 0.1  # 100ms target
        print(f"✓ Emergency stop activated in {emergency_stop_time*1000:.1f}ms")

        print("✓ Robot arm control and safety test PASSED")

    async def test_03_quality_assurance_inspection(self, setup):
        """Test quality assurance inspection workflow"""
        print("\n=== Testing Quality Assurance Inspection ===")

        # Step 1: Configure quality inspection parameters
        inspection_config = {
            "product_id": self.production_order["product_id"],
            "specifications": self.production_order["specifications"],
            "inspection_points": [
                {"dimension": "length", "nominal": 100.0, "tolerance": 0.01},
                {"dimension": "width", "nominal": 50.0, "tolerance": 0.01},
                {"dimension": "height", "nominal": 25.0, "tolerance": 0.01},
                {"property": "surface_finish", "max_ra": 0.8},
                {"property": "material_hardness", "min_hrc": 45}
            ],
            "sampling_rate": 0.1  # 10% sampling
        }

        inspection_setup = await self.qc_system.setup_inspection(inspection_config)
        assert inspection_setup["status"] == "ready"
        assert inspection_setup["inspection_id"] is not None
        print(f"✓ Quality inspection configured: {inspection_setup['inspection_id']}")

        # Step 2: Simulate production inspection data
        inspection_data = []
        for i in range(10):  # 10 sample parts
            part_data = {
                "part_id": f"PART-{i+1:04d}",
                "timestamp": datetime.now().isoformat(),
                "measurements": {
                    "length": 100.001 + (i % 3) * 0.002,  # Small variations
                    "width": 50.002 + (i % 2) * 0.001,
                    "height": 25.001 + (i % 4) * 0.001,
                    "surface_finish": 0.75 + (i % 5) * 0.05,
                    "material_hardness": 46 + (i % 3)
                },
                "operator_id": "OP-001",
                "inspection_station": "QC-STATION-1"
            }
            inspection_data.append(part_data)

        # Step 3: Process quality inspection
        inspection_result = await self.qc_system.process_inspection(
            inspection_id=inspection_setup["inspection_id"],
            data=inspection_data
        )
        assert inspection_result["status"] == "completed"
        assert inspection_result["total_inspected"] == 10
        assert inspection_result["pass_rate"] >= 0.8  # 80% minimum
        print(f"✓ Quality inspection completed: {inspection_result['pass_rate']*100:.1f}% pass rate")

        # Step 4: Analyze quality trends
        quality_trends = await self.qc_system.analyze_quality_trends(
            inspection_id=inspection_setup["inspection_id"],
            lookback_periods=5
        )
        assert quality_trends["trend_stable"] == True
        assert quality_trends["cpk"] >= 1.33  # Process capability index
        print(f"✓ Quality trends stable (Cpk: {quality_trends['cpk']:.2f})")

        # Step 5: Generate quality report
        quality_report = await self.qc_system.generate_quality_report(
            inspection_id=inspection_setup["inspection_id"],
            order_id=self.production_order["order_id"]
        )
        assert quality_report["report_id"] is not None
        assert quality_report["compliance_status"] == "compliant"
        assert "statistical_analysis" in quality_report
        print(f"✓ Quality report generated: {quality_report['report_id']}")

        print("✓ Quality assurance inspection test PASSED")

    async def test_04_safety_interlock_enforcement(self, setup):
        """Test safety interlock enforcement during operation"""
        print("\n=== Testing Safety Interlock Enforcement ===")

        # Step 1: Establish safety-critical operation
        safety_operation = {
            "operation_id": "SAFE-OP-001",
            "equipment": ["Robot-Arm-001", "CNC-Mill-001"],
            "safety_zones": [
                {"zone_id": "SZ-001", "equipment": "Robot-Arm-001", "radius": 2000},
                {"zone_id": "SZ-002", "equipment": "CNC-Mill-001", "radius": 1500}
            ],
            "interlock_requirements": [
                "light_curtain_active",
                "pressure_mat_clear",
                "emergency_stop_ready",
                "access_gates_closed"
            ]
        }

        safety_setup = await self.scada_system.setup_safety_zones(safety_operation)
        assert safety_setup["status"] == "active"
        assert safety_setup["zones_configured"] == 2
        print(f"✓ Safety zones configured: {safety_setup['zones_configured']} zones")

        # Step 2: Verify all interlocks are satisfied
        interlock_status = await self.scada_system.check_interlock_status(safety_operation["operation_id"])
        assert interlock_status["all_satisfied"] == True
        for requirement in safety_operation["interlock_requirements"]:
            assert interlock_status[requirement] == True
        print("✓ All safety interlocks satisfied")

        # Step 3: Simulate interlock violation (light curtain broken)
        print("Simulating safety interlock violation...")
        violation_simulation = await self.scada_system.simulate_interlock_violation(
            operation_id=safety_operation["operation_id"],
            violation_type="light_curtain_broken",
            violation_location="SZ-001"
        )
        assert violation_simulation["violation_detected"] == True
        print("✓ Interlock violation detected")

        # Step 4: Verify automatic safety shutdown
        shutdown_time_start = time.time()
        shutdown_result = await self.scada_system.execute_safety_shutdown(safety_operation["operation_id"])
        shutdown_time = time.time() - shutdown_time_start

        assert shutdown_result["status"] == "shutdown_complete"
        assert shutdown_time < 0.5  # 500ms target for safety shutdown
        print(f"✓ Safety shutdown completed in {shutdown_time*1000:.1f}ms")

        # Step 5: Verify equipment cannot operate with violated interlocks
        try:
            unsafe_operation = await self.scada_system.attempt_unsafe_operation(
                operation_id=safety_operation["operation_id"]
            )
            assert False, "Should not allow unsafe operation"
        except Exception as e:
            assert "safety" in str(e).lower() or "interlock" in str(e).lower()
            print("✓ Unsafe operation blocked by safety interlocks")

        # Step 6: Reset interlocks and verify recovery
        interlock_reset = await self.scada_system.reset_safety_interlocks(
            operation_id=safety_operation["operation_id"]
        )
        assert interlock_reset["status"] == "reset_complete"
        assert interlock_reset["all_interlocks_normal"] == True
        print("✓ Safety interlocks reset successfully")

        print("✓ Safety interlock enforcement test PASSED")

    async def test_05_emergency_stop_handling(self, setup):
        """Test emergency stop handling across all equipment"""
        print("\n=== Testing Emergency Stop Handling ===")

        # Step 1: Start coordinated production operation
        coordinated_operation = {
            "operation_id": "COORD-OP-001",
            "equipment": ["Robot-Arm-001", "CNC-Mill-001", "Conveyor-001"],
            "operation_type": "coordinated_production",
            "e_stops_linked": True,  # All e-stops linked
            "safety_level": "high"
        }

        operation_start = await self.scada_system.start_coordinated_operation(coordinated_operation)
        assert operation_start["status"] == "running"
        assert operation_start["equipment_active"] == 3
        print(f"✓ Coordinated operation started: {operation_start['equipment_active']} equipment")

        # Step 2: Test emergency stop from different locations
        e_stop_tests = [
            {"location": "robot_panel", "equipment": "Robot-Arm-001"},
            {"location": "cnc_panel", "equipment": "CNC-Mill-001"},
            {"location": "wireless_remote", "equipment": "all"}
        ]

        for test in e_stop_tests:
            print(f"Testing E-stop from {test['location']}...")

            # Reset and restart operation
            await self.scada_system.reset_equipment(test["equipment"])
            await self.scada_system.start_coordinated_operation(coordinated_operation)

            # Trigger emergency stop
            e_stop_start = time.time()
            e_stop_result = await self.scada_system.trigger_emergency_stop(
                equipment=test["equipment"],
                location=test["location"]
            )
            e_stop_time = time.time() - e_stop_start

            assert e_stop_result["status"] == "stopped"
            assert e_stop_time < 0.1  # 100ms target
            print(f"  ✓ E-stop from {test['location']}: {e_stop_time*1000:.1f}ms")

        # Step 3: Verify complete system shutdown on any E-stop
        complete_shutdown_test = await self.scada_system.test_complete_shutdown()
        assert complete_shutdown_test["all_equipment_stopped"] == True
        assert complete_shutdown_test["shutdown_time"] < 0.2  # 200ms for complete shutdown
        print(f"✓ Complete system shutdown: {complete_shutdown_test['shutdown_time']*1000:.1f}ms")

        # Step 4: Test emergency stop cannot be overridden
        try:
            override_attempt = await self.scada_system.attempt_e_stop_override()
            assert False, "Should not allow E-stop override"
        except Exception as e:
            assert "override" in str(e).lower() or "blocked" in str(e).lower()
            print("✓ E-stop override blocked")

        # Step 5: Test safe restart procedure
        safe_restart = await self.scada_system.execute_safe_restart(coordinated_operation["operation_id"])
        assert safe_restart["status"] == "ready_for_restart"
        assert safe_restart["safety_checks_passed"] == True
        print("✓ Safe restart procedure verified")

        print("✓ Emergency stop handling test PASSED")

    async def test_06_production_reporting(self, setup):
        """Test production reporting and analytics"""
        print("\n=== Testing Production Reporting ===")

        # Step 1: Collect production data
        production_data = await self.mes_system.collect_production_metrics(
            order_id=self.production_order["order_id"],
            time_range="current_shift"
        )
        assert production_data["status"] == "collected"
        assert "production_metrics" in production_data
        print("✓ Production data collected")

        # Step 2: Generate OEE (Overall Equipment Effectiveness) report
        oee_report = await self.mes_system.calculate_oee(
            equipment=self.production_order["required_equipment"],
            shift="current"
        )
        assert oee_report["availability"] >= 0.8  # 80% minimum
        assert oee_report["performance"] >= 0.85  # 85% minimum
        assert oee_report["quality"] >= 0.95  # 95% minimum
        assert oee_report["overall_oee"] >= 0.65  # 65% minimum overall
        print(f"✓ OEE Report: {oee_report['overall_oee']*100:.1f}% overall")

        # Step 3: Generate production efficiency analysis
        efficiency_analysis = await self.mes_system.analyze_production_efficiency(
            order_id=self.production_order["order_id"]
        )
        assert efficiency_analysis["cycle_time_actual"] <= efficiency_analysis["cycle_time_target"]
        assert efficiency_analysis["utilization_rate"] >= 0.75
        assert efficiency_analysis["bottlenecks_identified"] >= 0
        print("✓ Production efficiency analysis completed")

        # Step 4: Create shift report
        shift_report = await self.mes_system.generate_shift_report(
            shift_id="SHIFT-001",
            date=datetime.now().date().isoformat()
        )
        assert shift_report["shift_summary"]["total_produced"] > 0
        assert shift_report["quality_summary"]["first_pass_yield"] >= 0.9
        assert shift_report["safety_summary"]["incidents"] == 0
        print("✓ Shift report generated")

        # Step 5: Verify report data integrity
        data_integrity = await self.mes_system.verify_report_data_integrity(shift_report["report_id"])
        assert data_integrity["integrity_valid"] == True
        assert data_integrity["data_complete"] == True
        assert data_integrity["no_anomalies"] == True
        print("✓ Report data integrity verified")

        print("✓ Production reporting test PASSED")

    async def test_07_equipment_maintenance_scheduling(self, setup):
        """Test predictive maintenance scheduling"""
        print("\n=== Testing Equipment Maintenance Scheduling ===")

        # Step 1: Collect equipment health data
        health_data = await self.scada_system.collect_equipment_health(
            equipment=self.production_order["required_equipment"]
        )
        assert health_data["status"] == "collected"
        assert len(health_data["equipment_health"]) == len(self.production_order["required_equipment"])
        print("✓ Equipment health data collected")

        # Step 2: Analyze maintenance requirements
        maintenance_analysis = await self.scada_system.analyze_maintenance_requirements(health_data)
        assert len(maintenance_analysis["maintenance_scheduled"]) >= 0
        assert len(maintenance_analysis["immediate_attention"]) >= 0
        print(f"✓ Maintenance analysis: {len(maintenance_analysis['maintenance_scheduled'])} scheduled")

        # Step 3: Create maintenance execution packet if needed
        if maintenance_analysis["maintenance_scheduled"]:
            maintenance_packet = await self.packet_compiler.compile_packet(
                packet_data={
                    "action": "schedule_maintenance",
                    "maintenance_items": maintenance_analysis["maintenance_scheduled"],
                    "priority": "scheduled"
                },
                authority_level="medium",
                requirements=["production_window", "qualified_technician"]
            )

            maintenance_result = await self.orchestrator.execute_packet(maintenance_packet)
            assert maintenance_result["status"] == "success"
            print(f"✓ Maintenance scheduled: {maintenance_result['items_scheduled']} items")

        # Step 4: Verify maintenance doesn't impact production
        production_impact = await self.mes_system.assess_maintenance_impact(
            maintenance_items=maintenance_analysis.get("maintenance_scheduled", [])
        )
        assert production_impact["impact_acceptable"] == True
        assert production_impact["production_disruption"] <= 0.05  # 5% max disruption
        print("✓ Production impact verified")

        print("✓ Equipment maintenance scheduling test PASSED")


class TestDisasterRecoveryWorkflow:
    """Test disaster recovery workflow (SIT-E2E-204)"""

    @pytest.fixture
    async def setup(self):
        """Setup test environment"""
        # Initialize Murphy components
        self.confidence_engine = ConfidenceEngine()
        self.gate_synthesis = GateSynthesisEngine()
        self.compute_plane = ComputePlane()
        self.packet_compiler = ExecutionPacketCompiler()
        self.orchestrator = ExecutionOrchestrator()
        self.failure_generator = SyntheticFailureGenerator()
        self.rsc = RecursiveStabilityController()

        # Initialize enterprise systems
        self.it_system = ITInfrastructureSystem()
        self.bms = BuildingManagementSystem()
        self.scada_system = SCADARoboticsSystem()

        # Disaster scenario
        self.disaster_scenario = {
            "incident_id": "DIS-2024-001",
            "incident_type": "power_outage_cascade",
            "severity": "critical",
            "start_time": datetime.now().isoformat(),
            "affected_systems": [
                "primary_power", "backup_power", "cooling_system",
                "primary_network", "database_cluster", "application_servers"
            ],
            "business_impact": {
                "production_lines_down": 2,
                "data_services_unavailable": True,
                "safety_systems_degraded": True
            }
        }

        yield

        await self.orchestrator.shutdown()
        await self.failure_generator.shutdown()
        await self.rsc.shutdown()

    async def test_01_system_failure_detection(self, setup):
        """Test automatic system failure detection"""
        print("\n=== Testing System Failure Detection ===")

        # Step 1: Simulate cascading system failures
        failure_simulation = {
            "cascade_sequence": [
                {"system": "primary_power", "failure_time": "0s", "failure_type": "grid_outage"},
                {"system": "backup_power", "failure_time": "30s", "failure_type": "generator_failure"},
                {"system": "cooling_system", "failure_time": "60s", "failure_type": "overheating"},
                {"system": "primary_network", "failure_time": "90s", "failure_type": "switch_failure"},
                {"system": "database_cluster", "failure_time": "120s", "failure_type": "node_failure"}
            ]
        }

        cascade_start = await self.it_system.simulate_cascade_failure(failure_simulation)
        assert cascade_start["status"] == "initiated"
        print("✓ Cascading failure simulation initiated")

        # Step 2: Monitor failure detection timing
        detection_times = []
        for failure in failure_simulation["cascade_sequence"]:
            detection_time = await self.it_system.monitor_failure_detection(failure["system"])
            detection_times.append(detection_time)
            print(f"  {failure['system']}: {detection_time:.2f}s to detect")

        # Step 3: Verify detection within SLA
        avg_detection_time = sum(detection_times) / len(detection_times)
        assert avg_detection_time < 10.0  # 10 second average detection target
        print(f"✓ Average failure detection: {avg_detection_time:.2f}s")

        # Step 4: Compute disaster confidence
        disaster_confidence = await self.confidence_engine.compute_confidence({
            "incident_type": "cascade_failure",
            "systems_affected": len(self.disaster_scenario["affected_systems"]),
            "business_impact": "critical",
            "recovery_capability": "available"
        })
        assert disaster_confidence["confidence"] >= 0.7  # Moderate confidence in recovery
        assert disaster_confidence["authority"] == "high"
        print(f"✓ Disaster recovery confidence: {disaster_confidence['confidence']:.2f}")

        # Step 5: Generate disaster response gates
        response_gates = await self.gate_synthesis.generate_gates({
            "operation_type": "disaster_recovery",
            "severity": "critical",
            "safety_implications": True,
            "business_continuity": True
        })
        assert len(response_gates) >= 4  # Safety, data, business, communication gates
        print(f"✓ Disaster response gates generated: {len(response_gates)} gates")

        print("✓ System failure detection test PASSED")

    async def test_02_automatic_failover_activation(self, setup):
        """Test automatic failover to backup systems"""
        print("\n=== Testing Automatic Failover Activation ===")

        # Step 1: Identify failover targets
        failover_plan = await self.it_system.generate_failover_plan(
            failed_systems=self.disaster_scenario["affected_systems"],
            priority="business_critical"
        )
        assert failover_plan["status"] == "ready"
        assert len(failover_plan["failover_targets"]) > 0
        print(f"✓ Failover plan generated: {len(failover_plan['failover_targets'])} targets")

        # Step 2: Initiate automated failover
        failover_packet = await self.packet_compiler.compile_packet(
            packet_data={
                "action": "execute_failover",
                "incident_id": self.disaster_scenario["incident_id"],
                "failover_plan": failover_plan,
                "priority": "critical"
            },
            authority_level="emergency",
            requirements=["disaster_detected", "failover_ready", "safety_critical"]
        )

        failover_start = time.time()
        failover_result = await self.orchestrator.execute_packet(failover_packet)
        failover_time = time.time() - failover_start

        assert failover_result["status"] == "success"
        assert failover_time < 60.0  # 60 second RTO target
        print(f"✓ Failover completed in {failover_time:.2f}s")

        # Step 3: Verify critical services are online
        service_status = await self.it_system.check_critical_service_status()
        critical_services = ["database", "application_api", "monitoring", "safety_systems"]

        for service in critical_services:
            assert service_status[service]["status"] == "online"
            assert service_status[service]["response_time"] < 1000  # 1 second response
        print("✓ All critical services online")

        # Step 4: Verify data consistency after failover
        data_consistency = await self.it_system.verify_data_consistency()
        assert data_consistency["consistent"] == True
        assert data_consistency["missing_data"] == 0
        assert data_consistency["corrupted_data"] == 0
        print("✓ Data consistency verified")

        # Step 5: Test failover performance
        performance_metrics = await self.it_system.get_failover_performance_metrics()
        assert performance_metrics["rto_actual"] <= performance_metrics["rto_target"]
        assert performance_metrics["data_loss"] <= 60  # Max 1 minute data loss (RPO)
        print(f"✓ Performance targets met (RTO: {performance_metrics['rto_actual']}s, RPO: {performance_metrics['data_loss']}s)")

        print("✓ Automatic failover activation test PASSED")

    async def test_03_data_consistency_validation(self, setup):
        """Test data consistency and integrity validation"""
        print("\n=== Testing Data Consistency Validation ===")

        # Step 1: Perform comprehensive data validation
        validation_plan = {
            "databases": ["primary_db", "transaction_db", "analytics_db"],
            "file_systems": ["document_storage", "backup_storage"],
            "config_data": ["system_config", "security_config"],
            "audit_logs": ["access_logs", "operation_logs", "security_logs"]
        }

        validation_start = time.time()
        validation_result = await self.it_system.validate_data_consistency(validation_plan)
        validation_time = time.time() - validation_start

        assert validation_result["status"] == "completed"
        assert validation_time < 300  # 5 minute validation target
        print(f"✓ Data validation completed in {validation_time:.2f}s")

        # Step 2: Verify database consistency
        for db in validation_plan["databases"]:
            db_status = validation_result["databases"][db]
            assert db_status["consistent"] == True
            assert db_status["checksum_valid"] == True
            assert db_status["transaction_integrity"] == True
            print(f"  ✓ {db}: Consistent and intact")

        # Step 3: Verify file system integrity
        for fs in validation_plan["file_systems"]:
            fs_status = validation_result["file_systems"][fs]
            assert fs_status["integrity_verified"] == True
            assert fs_status["no_corruption"] == True
            assert fs_status["permissions_valid"] == True
            print(f"  ✓ {fs}: Integrity verified")

        # Step 4: Verify audit trail completeness
        audit_verification = await self.it_system.verify_audit_trail_completeness()
        assert audit_verification["no_gaps"] == True
        assert audit_verification["chronological_order"] == True
        assert audit_verification["signatures_valid"] == True
        print("✓ Audit trail completeness verified")

        # Step 5: Generate consistency report
        consistency_report = await self.it_system.generate_consistency_report(
            validation_result=validation_result,
            incident_id=self.disaster_scenario["incident_id"]
        )
        assert consistency_report["report_id"] is not None
        assert consistency_report["overall_status"] == "consistent"
        assert consistency_report["recommendations"] is not None
        print(f"✓ Consistency report generated: {consistency_report['report_id']}")

        print("✓ Data consistency validation test PASSED")

    async def test_04_service_restoration(self, setup):
        """Test systematic service restoration"""
        print("\n=== Testing Service Restoration ===")

        # Step 1: Create restoration sequence
        restoration_plan = {
            "phase_1_critical": [
                {"service": "safety_systems", "priority": 1},
                {"service": "emergency_communications", "priority": 1},
                {"service": "core_database", "priority": 1}
            ],
            "phase_2_business": [
                {"service": "production_control", "priority": 2},
                {"service": "inventory_system", "priority": 2},
                {"service": "quality_system", "priority": 2}
            ],
            "phase_3_support": [
                {"service": "analytics", "priority": 3},
                {"service": "reporting", "priority": 3},
                {"service": "development_tools", "priority": 3}
            ]
        }

        restoration_start = time.time()

        # Execute restoration in phases
        for phase_name, services in restoration_plan.items():
            print(f"Executing {phase_name}...")

            phase_packet = await self.packet_compiler.compile_packet(
                packet_data={
                    "action": "restore_services",
                    "phase": phase_name,
                    "services": services,
                    "incident_id": self.disaster_scenario["incident_id"]
                },
                authority_level="high",
                requirements=["previous_phase_complete", "safety_verified"]
            )

            phase_result = await self.orchestrator.execute_packet(phase_packet)
            assert phase_result["status"] == "success"
            assert phase_result["services_restored"] == len(services)
            print(f"  ✓ {phase_name}: {phase_result['services_restored']} services")

        total_restoration_time = time.time() - restoration_start

        # Step 2: Verify all services are operational
        service_status = await self.it_system.get_comprehensive_service_status()
        total_services = sum(len(services) for services in restoration_plan.values())

        operational_count = sum(1 for status in service_status.values()
                              if status["status"] == "operational")
        assert operational_count == total_services
        print(f"✓ All {total_services} services restored in {total_restoration_time:.2f}s")

        # Step 3: Test service functionality
        functionality_tests = await self.it_system.test_service_functionality()
        assert functionality_tests["all_tests_passed"] == True
        assert functionality_tests["critical_operations"] == "working"
        print("✓ Service functionality verified")

        # Step 4: Verify restoration within SLA
        restoration_sla = await self.it_system.check_restoration_sla_compliance()
        assert restoration_sla["compliant"] == True
        assert restoration_sla["actual_time"] <= restoration_sla["target_time"]
        print(f"✓ Restoration SLA met: {restoration_sla['actual_time']:.2f}s ≤ {restoration_sla['target_time']:.2f}s")

        print("✓ Service restoration test PASSED")

    async def test_05_performance_verification(self, setup):
        """Test system performance after recovery"""
        print("\n=== Testing Performance Verification ===")

        # Step 1: Measure system performance metrics
        performance_test = await self.it_system.run_performance_assessment()
        assert performance_test["status"] == "completed"

        # Verify key performance indicators
        kpis = performance_test["key_performance_indicators"]
        assert kpis["response_time_avg"] < 500  # 500ms average response
        assert kpis["throughput"] >= 1000  # 1000 requests/second
        assert kpis["error_rate"] < 0.01  # <1% error rate
        assert kpis["cpu_utilization"] < 0.8  # <80% CPU utilization
        assert kpis["memory_utilization"] < 0.8  # <80% memory utilization
        print("✓ Performance KPIs within acceptable ranges")

        # Step 2: Test load handling
        load_test = await self.it_system.run_load_test(
            concurrent_users=100,
            duration=300  # 5 minutes
        )
        assert load_test["passed"] == True
        assert load_test["avg_response_time"] < 1000  # 1 second under load
        assert load_test["peak_throughput"] >= 800  # 800 req/s minimum
        print(f"✓ Load test passed: {load_test['avg_response_time']:.1f}ms avg response")

        # Step 3: Verify Murphy System performance
        murphy_performance = await self.rsc.get_system_performance_metrics()
        assert murphy_performance["confidence_computation"] < 100  # <100ms
        assert murphy_performance["gate_synthesis"] < 200  # <200ms
        assert murphy_performance["packet_execution"] < 50  # <50ms
        print("✓ Murphy System performance verified")

        # Step 4: Compare to pre-disaster performance
        performance_comparison = await self.it_system.compare_to_baseline_performance()
        assert performance_comparison["degradation"] < 0.1  # <10% degradation
        assert performance_comparison["acceptable"] == True
        print(f"✓ Performance degradation: {performance_comparison['degradation']*100:.1f}%")

        print("✓ Performance verification test PASSED")

    async def test_06_recovery_time_measurement(self, setup):
        """Test comprehensive recovery time measurement"""
        print("\n=== Testing Recovery Time Measurement ===")

        # Step 1: Get detailed recovery timeline
        recovery_timeline = await self.it_system.get_recovery_timeline(
            incident_id=self.disaster_scenario["incident_id"]
        )

        # Verify all recovery phases are recorded
        required_phases = [
            "failure_detection",
            "impact_assessment",
            "failover_initiation",
            "service_restoration",
            "performance_verification",
            "recovery_completion"
        ]

        for phase in required_phases:
            assert phase in recovery_timeline
            assert recovery_timeline[phase]["start_time"] is not None
            assert recovery_timeline[phase]["end_time"] is not None
            assert recovery_timeline[phase]["duration"] >= 0

        print("✓ Recovery timeline complete")

        # Step 2: Calculate key recovery metrics
        recovery_metrics = await self.it_system.calculate_recovery_metrics(recovery_timeline)

        # Verify recovery time objectives
        assert recovery_metrics["mttr"] <= 3600  # 1 hour MTTR target
        assert recovery_metrics["rto"] <= 60  # 1 minute RTO target
        assert recovery_metrics["rpo"] <= 60  # 1 minute RPO target
        assert recovery_metrics["time_to_detect"] <= 300  # 5 minutes detection

        print(f"✓ Recovery metrics:")
        print(f"  - MTTR: {recovery_metrics['mttr']:.1f}s")
        print(f"  - RTO: {recovery_metrics['rpo']:.1f}s")
        print(f"  - RPO: {recovery_metrics['rpo']:.1f}s")
        print(f"  - Detection: {recovery_metrics['time_to_detect']:.1f}s")

        # Step 3: Verify SLA compliance
        sla_compliance = await self.it_system.verify_sla_compliance(recovery_metrics)
        assert sla_compliance["overall_compliant"] == True
        assert sla_compliance["all_slas_met"] == True
        print("✓ All SLAs compliant")

        # Step 4: Generate recovery performance report
        recovery_report = await self.it_system.generate_recovery_performance_report(
            incident_id=self.disaster_scenario["incident_id"],
            metrics=recovery_metrics,
            timeline=recovery_timeline
        )
        assert recovery_report["report_id"] is not None
        assert recovery_report["sla_status"] == "compliant"
        assert recovery_report["performance_grade"] in ["excellent", "good", "acceptable"]
        print(f"✓ Recovery report generated: Grade {recovery_report['performance_grade']}")

        print("✓ Recovery time measurement test PASSED")

    async def test_07_post_mortem_analysis(self, setup):
        """Test comprehensive post-mortem analysis"""
        print("\n=== Testing Post-Mortem Analysis ===")

        # Step 1: Collect incident data for analysis
        incident_data = await self.it_system.collect_incident_data(
            incident_id=self.disaster_scenario["incident_id"]
        )
        assert incident_data["status"] == "collected"
        assert len(incident_data["data_sources"]) >= 5
        print(f"✓ Incident data collected: {len(incident_data['data_sources'])} sources")

        # Step 2: Analyze root causes
        root_cause_analysis = await self.it_system.perform_root_cause_analysis(incident_data)
        assert root_cause_analysis["primary_cause"] is not None
        assert root_cause_analysis["contributing_factors"] is not None
        assert len(root_cause_analysis["contributing_factors"]) >= 0
        print(f"✓ Root cause identified: {root_cause_analysis['primary_cause']}")

        # Step 3: Analyze response effectiveness
        response_analysis = await self.it_system.analyze_response_effectiveness(
            incident_data=incident_data,
            recovery_metrics=root_cause_analysis.get("recovery_metrics", {})
        )
        assert response_analysis["overall_effectiveness"] >= 0.8  # 80% minimum
        assert response_analysis["strengths"] is not None
        assert response_analysis["improvement_areas"] is not None
        print(f"✓ Response effectiveness: {response_analysis['overall_effectiveness']*100:.1f}%")

        # Step 4: Generate improvement recommendations
        recommendations = await self.it_system.generate_improvement_recommendations(
            root_cause_analysis=root_cause_analysis,
            response_analysis=response_analysis
        )
        assert len(recommendations["recommendations"]) >= 0
        assert recommendations["priority_matrix"] is not None
        print(f"✓ Improvement recommendations: {len(recommendations['recommendations'])} items")

        # Step 5: Create comprehensive post-mortem report
        post_mortem_report = await self.it_system.create_post_mortem_report(
            incident_id=self.disaster_scenario["incident_id"],
            analysis_data={
                "root_cause": root_cause_analysis,
                "response": response_analysis,
                "recommendations": recommendations,
                "timeline": incident_data.get("recovery_timeline", {})
            }
        )

        assert post_mortem_report["report_id"] is not None
        assert post_mortem_report["executive_summary"] is not None
        assert post_mortem_report["detailed_findings"] is not None
        assert post_mortem_report["action_items"] is not None
        print(f"✓ Post-mortem report generated: {post_mortem_report['report_id']}")

        # Step 6: Verify lessons learned integration
        lessons_integrated = await self.it_system.verify_lessons_learned_integration(
            post_mortem_report["report_id"]
        )
        assert lessons_integrated["integration_status"] == "completed"
        assert lessons_integrated["updates_applied"] >= 0
        print(f"✓ Lessons learned integrated: {lessons_integrated['updates_applied']} updates")

        print("✓ Post-mortem analysis test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
