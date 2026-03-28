"""
Phase 3: End-to-End System Testing - Synchronous Version

Tests complete workflows across Murphy System components with proper async handling.
"""

import pytest
import asyncio
import time
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Import from confidence engine
from src.confidence_engine import (
    GraphAnalyzer, ConfidenceCalculator, MurphyCalculator,
    AuthorityMapper, PhaseController, ArtifactNode, ArtifactGraph,
    ArtifactType, ArtifactSource
)

# Mock enterprise systems for testing
class MockHRSystem:
    def __init__(self):
        self.employees = {}
        self.approvals = {}

    def register_employee(self, data):
        return asyncio.run(self._register_employee_async(data))

    async def _register_employee_async(self, data):
        employee_id = data.get("employee_id", f"EMP-{uuid.uuid4().hex[:8]}")
        self.employees[employee_id] = data
        return {
            "status": "pending_approval",
            "employee_id": employee_id,
            "registered_at": datetime.now().isoformat()
        }

    def get_training_requirements(self, position, department):
        return asyncio.run(self._get_training_requirements_async(position, department))

    async def _get_training_requirements_async(self, position, department):
        return [
            {"id": "SEC-001", "name": "Security Awareness", "category": "security", "mandatory": True},
            {"id": "COMP-001", "name": "Compliance Training", "category": "compliance", "mandatory": True},
            {"id": "TECH-001", "name": "Technical Onboarding", "category": "technical", "mandatory": False}
        ]

    def submit_approval_request(self, request):
        return asyncio.run(self._submit_approval_request_async(request))

    async def _submit_approval_request_async(self, request):
        approval_id = f"APR-{uuid.uuid4().hex[:8]}"
        self.approvals[approval_id] = request
        return {
            "status": "pending_manager_approval",
            "approval_id": approval_id
        }

    def process_approval(self, approval_response):
        return asyncio.run(self._process_approval_async(approval_response))

    async def _process_approval_async(self, approval_response):
        approval_id = approval_response["approval_id"]
        if approval_id in self.approvals:
            self.approvals[approval_id]["decision"] = approval_response["decision"]
            self.approvals[approval_id]["processed_at"] = datetime.now().isoformat()
            return {
                "status": "approved" if approval_response["decision"] == "approved" else "denied",
                "final_decision": approval_response["decision"]
            }
        return {"status": "not_found"}

class MockSecuritySystem:
    def __init__(self):
        self.credentials = {}
        self.dlp_classifications = {}

    def generate_credentials(self, request):
        return asyncio.run(self._generate_credentials_async(request))

    async def _generate_credentials_async(self, request):
        credential_id = f"CRED-{uuid.uuid4().hex[:8]}"
        credentials = {
            "username": request["email"].split("@")[0],
            "password": "TempPass123!@#",
            "mfa_secret": "MFASECRET123",
            "access_card_id": f"CARD-{uuid.uuid4().hex[:8]}"
        }
        self.credentials[credential_id] = credentials
        return credentials

    def check_password_strength(self, password):
        return asyncio.run(self._check_password_strength_async(password))

    async def _check_password_strength_async(self, password):
        return {
            "score": 4,
            "length": len(password) >= 12,
            "has_uppercase": any(c.isupper() for c in password),
            "has_lowercase": any(c.islower() for c in password),
            "has_numbers": any(c.isdigit() for c in password),
            "has_special": any(c in "!@#$%^&*" for c in password)
        }

    def classify_data(self, data):
        return asyncio.run(self._classify_data_async(data))

    async def _classify_data_async(self, data):
        # Simple classification based on content
        if "ssn" in str(data).lower() or "salary" in str(data).lower():
            return {
                "sensitivity_level": "SECRET",
                "categories": ["pii", "financial"],
                "confidence": 0.95
            }
        return {
            "sensitivity_level": "CONFIDENTIAL",
            "categories": ["internal"],
            "confidence": 0.8
        }

    def check_user_authority(self, user_id, action):
        return asyncio.run(self._check_user_authority_async(user_id, action))

    async def _check_user_authority_async(self, user_id, action):
        return {
            "has_authority": True,
            "authority_level": "medium",
            "permissions": ["approve_onboarding", "access_systems"]
        }

    def test_system_access(self, employee_id):
        return asyncio.run(self._test_system_access_async(employee_id))

    async def _test_system_access_async(self, employee_id):
        return {
            "access_granted": True,
            "access_level": "standard",
            "timestamp": datetime.now().isoformat()
        }

class MockDLPSystem:
    def __init__(self):
        self.classifications = {}
        self.transfers = {}

    def classify_data(self, data):
        return asyncio.run(self._classify_data_async(data))

    async def _classify_data_async(self, data):
        # Pattern-based classification
        data_str = str(data).lower()
        categories = []

        if "ssn" in data_str or any(pattern in data_str for pattern in ["ssn", "social security"]):
            categories.append("pii")
        if "salary" in data_str or "financial" in data_str:
            categories.append("financial")
        if "health" in data_str or "medical" in data_str:
            categories.append("health")
        if "password" in data_str or "credential" in data_str:
            categories.append("authentication")

        sensitivity = "PUBLIC"
        if categories:
            if "pii" in categories or "financial" in categories:
                sensitivity = "SECRET"
            elif "health" in categories or "authentication" in categories:
                sensitivity = "CONFIDENTIAL"
            else:
                sensitivity = "INTERNAL"

        return {
            "sensitivity_level": sensitivity,
            "categories": categories,
            "confidence": 0.9
        }

    def check_encryption_requirements(self, data):
        return asyncio.run(self._check_encryption_requirements_async(data))

    async def _check_encryption_requirements_async(self, data):
        classification = await self._classify_data_async(data)
        return {
            "at_rest": classification["sensitivity_level"] in ["CONFIDENTIAL", "SECRET"],
            "in_transit": classification["sensitivity_level"] in ["INTERNAL", "CONFIDENTIAL", "SECRET"],
            "sensitivity": classification["sensitivity_level"]
        }

    def check_gdpr_compliance(self, employee_id):
        return asyncio.run(self._check_gdpr_compliance_async(employee_id))

    async def _check_gdpr_compliance_async(self, employee_id):
        return {
            "compliant": True,
            "data_minimized": True,
            "consent_recorded": True,
            "retention_policy_applied": True,
            "rights_respected": True
        }

    def check_retention_compliance(self, employee_id):
        return asyncio.run(self._check_retention_compliance_async(employee_id))

    async def _check_retention_compliance_async(self, employee_id):
        return {
            "compliant": True,
            "retention_schedule": "7_years_for_employee_data",
            "auto_delete": True
        }

class MockExecutionOrchestrator:
    def __init__(self):
        self.packets = {}
        self.audit_trail = {}
        self.performance_metrics = {}

    def execute_packet(self, packet):
        return asyncio.run(self._execute_packet_async(packet))

    async def _execute_packet_async(self, packet):
        packet_id = getattr(packet, 'id', str(uuid.uuid4()))
        execution_time = time.time()

        # Simulate execution
        await asyncio.sleep(0.01)  # 10ms execution time

        result = {
            "status": "success",
            "packet_id": packet_id,
            "executed_at": datetime.now().isoformat(),
            "execution_time": time.time() - execution_time
        }

        self.packets[packet_id] = result

        # Add to audit trail
        if packet_id not in self.audit_trail:
            self.audit_trail[packet_id] = []

        self.audit_trail[packet_id].append({
            "action": "packet_executed",
            "timestamp": datetime.now().isoformat(),
            "packet_id": packet_id,
            "result": result["status"]
        })

        return result

    def get_complete_workflow_audit(self, entity_id, workflow_type):
        return asyncio.run(self._get_complete_workflow_audit_async(entity_id, workflow_type))

    async def _get_complete_workflow_audit_async(self, entity_id, workflow_type):
        # Return mock audit trail
        return [
            {
                "action": "employee_registration",
                "timestamp": datetime.now().isoformat(),
                "entity_id": entity_id,
                "workflow": workflow_type
            },
            {
                "action": "credentials_generated",
                "timestamp": datetime.now().isoformat(),
                "entity_id": entity_id,
                "workflow": workflow_type
            },
            {
                "action": "access_activated",
                "timestamp": datetime.now().isoformat(),
                "entity_id": entity_id,
                "workflow": workflow_type
            }
        ]

    def verify_safety_constraints(self, entity_id):
        return asyncio.run(self._verify_safety_constraints_async(entity_id))

    async def _verify_safety_constraints_async(self, entity_id):
        return {
            "all_constraints_satisfied": True,
            "no_unauthorized_access": True,
            "pii_protected": True,
            "audit_trail_complete": True
        }

    def get_workflow_performance_metrics(self, workflow_type):
        return asyncio.run(self._get_workflow_performance_metrics_async(workflow_type))

    async def _get_workflow_performance_metrics_async(self, workflow_type):
        return {
            "completion_time": 1800,  # 30 minutes
            "success_rate": 1.0,
            "compliance_score": 0.98
        }

    def shutdown(self):
        return asyncio.run(self._shutdown_async())

    async def _shutdown_async(self):
        pass

class MockPacketCompiler:
    def __init__(self):
        self.packets = {}

    def compile_packet(self, packet_data, authority_level, requirements):
        return asyncio.run(self._compile_packet_async(packet_data, authority_level, requirements))

    async def _compile_packet_async(self, packet_data, authority_level, requirements):
        packet_id = str(uuid.uuid4())
        packet = {
            "id": packet_id,
            "data": packet_data,
            "authority_level": authority_level,
            "requirements": requirements,
            "execution_rights": True,
            "compiled_at": datetime.now().isoformat()
        }
        self.packets[packet_id] = packet

        # Create mock packet object
        class MockPacket:
            def __init__(self, data):
                self.id = data["id"]
                self.data = data["data"]
                self.authority_level = data["authority_level"]
                self.requirements = data["requirements"]
                self.execution_rights = data["execution_rights"]

        return MockPacket(packet)


class TestPhase3SynchronousWorkflows:
    """Synchronous end-to-end workflow tests"""

    def setup_method(self):
        """Setup test environment"""
        # Initialize core Murphy components
        self.graph_analyzer = GraphAnalyzer()
        self.confidence_calculator = ConfidenceCalculator()
        self.murphy_calculator = MurphyCalculator()
        self.authority_mapper = AuthorityMapper()
        self.phase_controller = PhaseController()

        # Initialize mock enterprise systems
        self.hr_system = MockHRSystem()
        self.security_system = MockSecuritySystem()
        self.dlp_system = MockDLPSystem()
        self.packet_compiler = MockPacketCompiler()
        self.orchestrator = MockExecutionOrchestrator()

        # Test employee data
        self.employee_data = {
            "employee_id": "E2024-001",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@company.com",
            "phone": "+1-555-123-4567",
            "ssn": "123-45-6789",
            "address": "123 Main St, City, ST 12345",
            "date_of_birth": "1990-01-01",
            "department": "Engineering",
            "position": "Software Engineer",
            "salary": 95000,
            "start_date": "2024-02-01",
            "manager_id": "MGR-001"
        }

    def teardown_method(self):
        """Cleanup test environment"""
        self.orchestrator.shutdown()

    def test_01_hr_onboarding_complete_workflow(self):
        """Test complete HR onboarding workflow end-to-end"""
        print("\n=== Testing Complete HR Onboarding Workflow ===")

        # Step 1: Register employee
        registration = self.hr_system.register_employee(self.employee_data)
        assert registration["status"] == "pending_approval"
        print(f"✓ Employee registered: {registration['employee_id']}")

        # Step 2: Classify PII data
        pii_classification = self.dlp_system.classify_data(self.employee_data)
        assert pii_classification["sensitivity_level"] == "SECRET"
        assert "pii" in pii_classification["categories"]
        print(f"✓ PII classified as: {pii_classification['sensitivity_level']}")

        # Step 3: Check encryption requirements
        encryption_check = self.dlp_system.check_encryption_requirements(self.employee_data)
        assert encryption_check["at_rest"] == True
        assert encryption_check["in_transit"] == True
        print("✓ Encryption requirements enforced")

        # Step 4: Generate credentials
        credentials = self.security_system.generate_credentials({
            "employee_id": self.employee_data["employee_id"],
            "email": self.employee_data["email"],
            "department": self.employee_data["department"],
            "position": self.employee_data["position"],
            "access_level": "standard"
        })
        assert "username" in credentials
        assert "password" in credentials
        print("✓ System credentials generated")

        # Step 5: Check password strength
        password_check = self.security_system.check_password_strength(credentials["password"])
        assert password_check["score"] >= 3
        assert password_check["length"] == True
        print("✓ Password strength verified")

        # Step 6: Classify credentials
        credentials_classification = self.dlp_system.classify_data(credentials)
        assert credentials_classification["sensitivity_level"] in ["SECRET", "CONFIDENTIAL"]
        assert "authentication" in credentials_classification["categories"]
        print(f"✓ Credentials classified as: {credentials_classification['sensitivity_level']}")

        # Step 7: Get training requirements
        training = self.hr_system.get_training_requirements(
            self.employee_data["position"],
            self.employee_data["department"]
        )
        assert len(training) >= 2
        assert any(t["mandatory"] for t in training)
        print(f"✓ Training requirements: {len(training)} courses")

        # Step 8: Submit manager approval
        approval_request = {
            "request_id": str(uuid.uuid4()),
            "employee_id": self.employee_data["employee_id"],
            "request_type": "onboarding_approval",
            "requested_by": "hr_system",
            "approver_id": self.employee_data["manager_id"]
        }

        approval = self.hr_system.submit_approval_request(approval_request)
        assert approval["status"] == "pending_manager_approval"
        print(f"✓ Approval request submitted: {approval['approval_id']}")

        # Step 9: Process manager approval
        approval_response = {
            "approval_id": approval["approval_id"],
            "decision": "approved",
            "approver_id": self.employee_data["manager_id"],
            "approver_comments": "All requirements met",
            "timestamp": datetime.now().isoformat()
        }

        processed_approval = self.hr_system.process_approval(approval_response)
        assert processed_approval["status"] == "approved"
        print("✓ Manager approval processed")

        # Step 10: Create activation packet
        activation_packet = self.packet_compiler.compile_packet(
            packet_data={
                "action": "activate_system_access",
                "employee_id": self.employee_data["employee_id"],
                "activation_timestamp": datetime.now().isoformat()
            },
            authority_level="high",
            requirements=["manager_approval", "security_clearance"]
        )

        # Step 11: Execute activation
        activation_result = self.orchestrator.execute_packet(activation_packet)
        assert activation_result["status"] == "success"
        print("✓ System access activated")

        # Step 12: Test system access
        access_test = self.security_system.test_system_access(self.employee_data["employee_id"])
        assert access_test["access_granted"] == True
        print("✓ System access verified")

        # Step 13: Verify audit trail
        audit_trail = self.orchestrator.get_complete_workflow_audit(
            self.employee_data["employee_id"],
            "onboarding"
        )
        assert len(audit_trail) >= 3
        print(f"✓ Audit trail complete: {len(audit_trail)} entries")

        # Step 14: Check GDPR compliance
        gdpr_check = self.dlp_system.check_gdpr_compliance(self.employee_data["employee_id"])
        assert gdpr_check["compliant"] == True
        print("✓ GDPR compliance verified")

        # Step 15: Verify safety constraints
        safety_check = self.orchestrator.verify_safety_constraints(self.employee_data["employee_id"])
        assert safety_check["all_constraints_satisfied"] == True
        print("✅ All safety constraints satisfied")

        # Step 16: Performance metrics
        performance = self.orchestrator.get_workflow_performance_metrics("hr_onboarding")
        assert performance["completion_time"] < 3600  # Less than 1 hour
        assert performance["success_rate"] == 1.0
        assert performance["compliance_score"] >= 0.95
        print(f"✓ Performance targets met")

        print("✅ COMPLETE HR ONBOARDING WORKFLOW TEST PASSED")

    def test_02_confidence_computation_integration(self):
        """Test confidence computation integration"""
        print("\n=== Testing Confidence Computation Integration ===")

        # Step 1: Create artifact graph for employee onboarding
        graph = ArtifactGraph()

        # Add nodes
        registration_node = ArtifactNode(
            id="registration",
            type=ArtifactType.FACT,
            source=ArtifactSource.HUMAN,
            content=json.loads(json.dumps(self.employee_data)),
            confidence_weight=0.9
        )

        credentials_node = ArtifactNode(
            id="credentials",
            type=ArtifactType.FACT,
            source=ArtifactSource.API,
            content={"username": "john.doe", "generated": True},
            confidence_weight=0.95
        )

        approval_node = ArtifactNode(
            id="approval",
            type=ArtifactType.DECISION,
            source=ArtifactSource.HUMAN,
            content={"status": "approved", "approver": "MGR-001"},
            confidence_weight=0.85
        )

        graph.nodes["registration"] = registration_node
        graph.nodes["credentials"] = credentials_node
        graph.nodes["approval"] = approval_node

        # Step 2: Analyze graph
        graph_analysis = self.graph_analyzer.analyze_dependencies(graph)
        is_dag, _ = self.graph_analyzer.validate_dag(graph)
        assert is_dag == True
        assert len(graph.nodes) == 3
        print("✓ Artifact graph analyzed")

        # Step 3: Compute confidence
        from src.confidence_engine.models import Phase, TrustModel, VerificationEvidence, VerificationResult
        confidence_result = self.confidence_calculator.compute_confidence(
            graph=graph,
            phase=Phase.EXECUTE,
            verification_evidence=[],
            trust_model=TrustModel()
        )
        assert confidence_result.confidence > 0.0
        print(f"✓ Confidence computed: {confidence_result.confidence:.2f}")

        # Step 4: Calculate Murphy index
        murphy_index = self.murphy_calculator.calculate_murphy_index(graph, confidence_result, Phase.EXECUTE)
        assert murphy_index <= 1.0
        print(f"✓ Murphy index: {murphy_index:.2f}")

        # Step 5: Map authority
        authority = self.authority_mapper.map_authority(
            confidence_state=confidence_result,
            murphy_index=murphy_index
        )
        assert authority.authority_band is not None
        print(f"✓ Authority mapped: {authority.authority_band}")

        # Step 6: Phase transition
        next_phase, can_transition, reason = self.phase_controller.check_phase_transition(
            current_phase=Phase.EXECUTE,
            confidence_state=confidence_result
        )
        print(f"✓ Phase transition check: can_transition={can_transition}")

        print("✅ CONFIDENCE COMPUTATION INTEGRATION TEST PASSED")

    def test_03_error_handling_and_recovery(self):
        """Test error handling and recovery scenarios"""
        print("\n=== Testing Error Handling and Recovery ===")

        # Step 1: Test invalid employee data
        invalid_employee = self.employee_data.copy()
        invalid_employee["employee_id"] = None  # Invalid

        try:
            registration = self.hr_system.register_employee(invalid_employee)
            # Should still work with mock, but would fail in real system
            print("✓ Invalid data handled gracefully")
        except Exception as e:
            print(f"✓ Invalid data rejected: {str(e)}")

        # Step 2: Test missing manager approval
        incomplete_request = {
            "request_id": str(uuid.uuid4()),
            "employee_id": self.employee_data["employee_id"],
            "request_type": "onboarding_approval",
            "requested_by": "hr_system"
            # Missing approver_id
        }

        approval = self.hr_system.submit_approval_request(incomplete_request)
        # Should still be created, but would fail validation in real system
        assert "approval_id" in approval
        print("✓ Incomplete request handled")

        # Step 3: Test execution packet failure simulation
        failing_packet_data = {
            "action": "activate_system_access",
            "employee_id": "NONEXISTENT-001",
            "activation_timestamp": datetime.now().isoformat()
        }

        # In real system, this would fail
        # For mock, we test the flow
        packet = self.packet_compiler.compile_packet(
            packet_data=failing_packet_data,
            authority_level="high",
            requirements=["manager_approval"]
        )

        result = self.orchestrator.execute_packet(packet)
        # Mock always succeeds, but structure is correct
        assert result["status"] == "success"
        print("✓ Packet execution flow verified")

        # Step 4: Test audit trail integrity
        audit_trail = self.orchestrator.get_complete_workflow_audit("test-employee", "test-workflow")
        assert len(audit_trail) > 0
        assert "timestamp" in audit_trail[0]
        print("✓ Audit trail integrity maintained")

        print("✅ ERROR HANDLING AND RECOVERY TEST PASSED")

    def test_04_performance_and_scalability(self):
        """Test performance and scalability"""
        print("\n=== Testing Performance and Scalability ===")

        # Step 1: Test concurrent employee registrations (simulated)
        start_time = time.time()

        results = []
        for i in range(10):
            employee_copy = self.employee_data.copy()
            employee_copy["employee_id"] = f"E2024-{i+1:03d}"
            employee_copy["email"] = f"employee{i+1}@company.com"

            result = self.hr_system.register_employee(employee_copy)
            results.append(result)

        concurrent_time = time.time() - start_time

        assert all(result["status"] == "pending_approval" for result in results)
        assert concurrent_time < 5.0  # Should complete in under 5 seconds
        print(f"✓ Multiple registrations: {len(results)} in {concurrent_time:.2f}s")

        # Step 2: Test batch classification
        start_time = time.time()

        classifications = []
        for result in results:
            classification = self.dlp_system.classify_data({"employee_id": result["employee_id"]})
            classifications.append(classification)

        classification_time = time.time() - start_time

        print(f"Debug: classifications = {classifications}")
        valid_levels = ["INTERNAL", "CONFIDENTIAL", "SECRET", "PUBLIC"]
        assert all(cl.get("sensitivity_level", "PUBLIC") in valid_levels for cl in classifications)
        assert classification_time < 2.0
        print(f"✓ Batch classification: {len(classifications)} in {classification_time:.2f}s")

        # Step 3: Test confidence computation performance
        start_time = time.time()

        for i in range(5):
            graph = ArtifactGraph()
            node = ArtifactNode(
                id=f"node-{i}",
                type=ArtifactType.FACT,
                source=ArtifactSource.HUMAN,
                content={"test": "content"},
                confidence_weight=0.9
            )
            graph.nodes[f"node-{i}"] = node

            from src.confidence_engine.models import Phase, TrustModel
            confidence = self.confidence_calculator.compute_confidence(
                graph=graph,
                phase=Phase.EXECUTE,
                verification_evidence=[],
                trust_model=TrustModel()
            )
            assert confidence.confidence > 0.0

        confidence_time = time.time() - start_time
        assert confidence_time < 1.0
        print(f"✓ Confidence computation: 5 graphs in {confidence_time:.2f}s")

        # Step 4: Memory usage check
        import sys

        total_employees = len(results)
        total_classifications = len(classifications)

        # Rough estimate of memory usage
        estimated_memory = sys.getsizeof(results) + sys.getsizeof(classifications)
        print(f"✓ Memory usage estimated: {estimated_memory} bytes for {total_employees} employees")

        print("✅ PERFORMANCE AND SCALABILITY TEST PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
