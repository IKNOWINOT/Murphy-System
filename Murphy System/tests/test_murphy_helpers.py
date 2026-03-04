"""
Tests for Murphy Integration Helpers

Tests helper classes for integrating Module Compiler with Murphy System.
"""

import unittest
from src.module_compiler.integration.murphy_helpers import (
    MurphyIntegrationHelper,
    CapabilityMatch
)


class MockCapability:
    """Mock capability for testing"""
    def __init__(self, name, determinism_level="deterministic", requires_network=False):
        self.name = name
        self.determinism_level = determinism_level
        self.requires_network = requires_network
        self.requires_filesystem = False
        self.cpu_requirement = 1.0
        self.memory_requirement = 512
        self.risk_score = 0.1
        self.test_vectors = []
        self.failure_modes = []


class MockFailureMode:
    """Mock failure mode for testing"""
    def __init__(self, risk_score):
        self.risk_score = risk_score


class MockSandboxProfile:
    """Mock sandbox profile for testing"""
    def __init__(self, cpu_cores=1.0, memory_mb=512, disk_quota_mb=100):
        self.cpu_cores = cpu_cores
        self.memory_mb = memory_mb
        self.disk_quota_mb = disk_quota_mb


class TestMurphyIntegrationHelper(unittest.TestCase):
    """Test Murphy integration helper"""

    def setUp(self):
        self.helper = MurphyIntegrationHelper()

    def test_gate_synthesis_basic(self):
        """Test basic gate synthesis"""
        capability = MockCapability("test_capability")

        gates = self.helper.synthesize_gates_from_capability(capability)

        # Should have at least determinism and risk gates
        self.assertGreater(len(gates), 0)

        # Check gate structure
        for gate in gates:
            self.assertIn('predicate', gate)
            self.assertIn('satisfied', gate)
            self.assertIn('confidence', gate)

    def test_gate_synthesis_with_failure_modes(self):
        """Test gate synthesis with failure modes"""
        capability = MockCapability("test_capability")
        failure_modes = [
            MockFailureMode(0.2),
            MockFailureMode(0.3)
        ]

        gates = self.helper.synthesize_gates_from_capability(
            capability,
            failure_modes=failure_modes
        )

        # Should have risk gate
        risk_gates = [g for g in gates if g['predicate'] == 'risk_acceptable']
        self.assertGreater(len(risk_gates), 0)

        # Risk gate should be satisfied (max risk 0.3 < 0.5)
        self.assertTrue(risk_gates[0]['satisfied'])

    def test_gate_synthesis_with_high_risk(self):
        """Test gate synthesis with high risk failure modes"""
        capability = MockCapability("test_capability")
        failure_modes = [
            MockFailureMode(0.6),  # High risk
            MockFailureMode(0.7)   # High risk
        ]

        gates = self.helper.synthesize_gates_from_capability(
            capability,
            failure_modes=failure_modes
        )

        # Risk gate should not be satisfied (max risk 0.7 > 0.5)
        risk_gates = [g for g in gates if g['predicate'] == 'risk_acceptable']
        self.assertFalse(risk_gates[0]['satisfied'])

    def test_gate_synthesis_with_sandbox_profile(self):
        """Test gate synthesis with sandbox profile"""
        capability = MockCapability("test_capability")
        sandbox_profile = MockSandboxProfile(cpu_cores=2.0, memory_mb=1024)

        gates = self.helper.synthesize_gates_from_capability(
            capability,
            sandbox_profile=sandbox_profile
        )

        # Should have resource availability gate
        resource_gates = [g for g in gates if g['predicate'] == 'resources_available']
        self.assertGreater(len(resource_gates), 0)

    def test_gate_synthesis_with_network_requirement(self):
        """Test gate synthesis for capability requiring network"""
        capability = MockCapability("test_capability", requires_network=True)

        gates = self.helper.synthesize_gates_from_capability(capability)

        # Should have network access gate
        network_gates = [g for g in gates if g['predicate'] == 'network_access_allowed']
        self.assertGreater(len(network_gates), 0)

    def test_gate_synthesis_with_test_coverage(self):
        """Test gate synthesis with test coverage"""
        capability = MockCapability("test_capability")
        capability.test_vectors = list(range(15))  # 15 test vectors

        gates = self.helper.synthesize_gates_from_capability(capability)

        # Should have test coverage gate
        coverage_gates = [g for g in gates if g['predicate'] == 'test_coverage_adequate']
        self.assertGreater(len(coverage_gates), 0)

        # Should be satisfied (15 >= 10)
        self.assertTrue(coverage_gates[0]['satisfied'])

    def test_determinism_check(self):
        """Test determinism checking"""
        # Deterministic capability
        cap1 = MockCapability("cap1", determinism_level="deterministic")
        self.assertTrue(self.helper._check_determinism(cap1))

        # Probabilistic capability
        cap2 = MockCapability("cap2", determinism_level="probabilistic")
        self.assertTrue(self.helper._check_determinism(cap2))

        # External state capability
        cap3 = MockCapability("cap3", determinism_level="external_state")
        self.assertFalse(self.helper._check_determinism(cap3))

    def test_risk_check(self):
        """Test risk checking"""
        # Low risk
        low_risk = [MockFailureMode(0.2), MockFailureMode(0.3)]
        self.assertTrue(self.helper._check_risk(low_risk))

        # High risk
        high_risk = [MockFailureMode(0.6), MockFailureMode(0.7)]
        self.assertFalse(self.helper._check_risk(high_risk))

        # No failure modes
        self.assertTrue(self.helper._check_risk([]))

    def test_resource_constraints_check(self):
        """Test resource constraints checking"""
        sandbox_profile = MockSandboxProfile(cpu_cores=2.0, memory_mb=1024)
        available_resources = {
            'cpu_cores': 4.0,
            'memory_mb': 4096,
            'disk_mb': 10240
        }

        results = self.helper.check_resource_constraints(
            sandbox_profile,
            available_resources
        )

        # Should fit
        self.assertTrue(results['fits'])
        self.assertEqual(len(results['violations']), 0)

    def test_resource_constraints_violation(self):
        """Test resource constraints violation"""
        sandbox_profile = MockSandboxProfile(cpu_cores=8.0, memory_mb=8192)
        available_resources = {
            'cpu_cores': 4.0,
            'memory_mb': 4096,
            'disk_mb': 10240
        }

        results = self.helper.check_resource_constraints(
            sandbox_profile,
            available_resources
        )

        # Should not fit
        self.assertFalse(results['fits'])
        self.assertGreater(len(results['violations']), 0)

    def test_capability_summary(self):
        """Test capability summary generation"""
        capability = MockCapability("test_capability")
        capability.test_vectors = list(range(10))
        capability.failure_modes = list(range(5))

        summary = self.helper.get_capability_summary(capability)

        # Should have all required fields
        self.assertIn('name', summary)
        self.assertIn('determinism_level', summary)
        self.assertIn('requires_network', summary)
        self.assertIn('cpu_requirement', summary)
        self.assertIn('memory_requirement', summary)
        self.assertIn('test_coverage', summary)
        self.assertIn('failure_modes', summary)

        # Check values
        self.assertEqual(summary['name'], 'test_capability')
        self.assertEqual(summary['test_coverage'], 10)
        self.assertEqual(summary['failure_modes'], 5)

    def test_execution_confidence_deterministic(self):
        """Test execution confidence for deterministic capability"""
        capability = MockCapability("test_capability", determinism_level="deterministic")
        capability.test_vectors = list(range(15))

        gates = [
            {'predicate': 'gate1', 'satisfied': True},
            {'predicate': 'gate2', 'satisfied': True},
            {'predicate': 'gate3', 'satisfied': False}
        ]

        confidence = self.helper.compute_execution_confidence(capability, gates)

        # Should have high confidence (deterministic + good test coverage + 2/3 gates)
        self.assertGreater(confidence, 0.6)
        self.assertLessEqual(confidence, 1.0)

    def test_execution_confidence_external_state(self):
        """Test execution confidence for external state capability"""
        capability = MockCapability("test_capability", determinism_level="external_state")
        capability.test_vectors = []

        gates = [
            {'predicate': 'gate1', 'satisfied': False},
            {'predicate': 'gate2', 'satisfied': False}
        ]

        confidence = self.helper.compute_execution_confidence(capability, gates)

        # Should have lower confidence
        self.assertLess(confidence, 0.6)


class TestCapabilityMatch(unittest.TestCase):
    """Test CapabilityMatch data class"""

    def test_valid_capability_match(self):
        """Test creating valid capability match"""
        match = CapabilityMatch(
            capability_name="test_capability",
            match_score=0.8,
            confidence=0.9,
            reasons=["Good match"],
            requirements_met=["deterministic", "network"],
            requirements_missing=[]
        )

        self.assertEqual(match.capability_name, "test_capability")
        self.assertEqual(match.match_score, 0.8)
        self.assertEqual(match.confidence, 0.9)


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
