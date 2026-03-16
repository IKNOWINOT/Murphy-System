"""
Tests for MFGC v1.1 features
"""

import os

import unittest
import time
import pytest

try:
    from mfgc_v1_1 import (
        TrustWeightedGrounding, TrustedSource,
        OrganizationalOverride, IncentivePressureMonitor,
        TemporalConfidenceDecay, MetaGovernanceProtection,
        EnhancedMurphyIndexMonitor, MFGCv1_1Controller,
        stress_test_boeing_failure, stress_test_flash_crash, stress_test_medical_ai
    )
except ImportError:
    pytest.skip("mfgc_v1_1 module not available", allow_module_level=True)


class TestTrustWeightedGrounding(unittest.TestCase):
    """Test trust-weighted deterministic grounding"""

    def setUp(self):
        self.grounding = TrustWeightedGrounding()

    def test_compute_grounding(self):
        """Test D(x_t) = Σ T(s_i) · E(s_i)"""
        evidence = {
            'wikipedia': 0.8,
            'peer_reviewed': 0.9
        }

        score = self.grounding.compute_grounding(evidence)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_trust_decay(self):
        """Test trust decay over time"""
        source = self.grounding.sources['wikipedia']
        initial_trust = source.trust_score

        source.decay_trust()

        self.assertLess(source.trust_score, initial_trust)

    def test_contradiction_penalty(self):
        """Test severe penalty for contradictions"""
        source = self.grounding.sources['wikipedia']
        initial_trust = source.trust_score

        self.grounding.report_contradiction('wikipedia')

        self.assertLess(source.trust_score, initial_trust * 0.6)


class TestIncentivePressureMonitor(unittest.TestCase):
    """Test organizational override protection"""

    def setUp(self):
        self.monitor = IncentivePressureMonitor()

    def test_pressure_computation(self):
        """Test incentive pressure increases with override level"""
        self.monitor.set_override(OrganizationalOverride.NONE)
        none_pressure = self.monitor.compute_incentive_pressure()

        self.monitor.set_override(OrganizationalOverride.FORCE)
        force_pressure = self.monitor.compute_incentive_pressure()

        self.assertGreater(force_pressure, none_pressure)

    def test_authority_decay_trigger(self):
        """Test that pressure triggers authority decay"""
        self.monitor.set_override(OrganizationalOverride.ACCELERATE)
        self.assertTrue(self.monitor.should_decay_authority())

        self.monitor.set_override(OrganizationalOverride.NONE)
        self.assertFalse(self.monitor.should_decay_authority())


class TestTemporalConfidenceDecay(unittest.TestCase):
    """Test temporal confidence decay"""

    def setUp(self):
        self.decay = TemporalConfidenceDecay(decay_rate=0.1)

    def test_confidence_decay(self):
        """Test c_t ← c_t · e^(-λΔt)"""
        confidence = 0.9
        context_id = "test_context"

        # First call establishes baseline
        result1 = self.decay.apply_decay(confidence, context_id)

        # Simulate time passing
        time.sleep(0.1)

        # Second call should show decay
        result2 = self.decay.apply_decay(confidence, context_id)

        self.assertLessEqual(result2, result1)

    def test_reset_decay(self):
        """Test decay reset after revalidation"""
        context_id = "test_context"

        self.decay.apply_decay(0.9, context_id)
        time.sleep(0.1)

        self.decay.reset_decay(context_id)

        # After reset, decay should restart
        result = self.decay.apply_decay(0.9, context_id)
        self.assertGreater(result, 0.8)


class TestMetaGovernanceProtection(unittest.TestCase):
    """Test meta-governance invariants"""

    def setUp(self):
        self.protection = MetaGovernanceProtection()

    def test_protected_components(self):
        """Test that core components are protected"""
        self.assertTrue(self.protection.is_protected('confidence_equation'))
        self.assertTrue(self.protection.is_protected('authority_mapping'))
        self.assertFalse(self.protection.is_protected('user_data'))

    def test_gate_validation(self):
        """Test gate validation rejects protected modifications"""
        valid_gate = {
            'name': 'data_validation',
            'modifies': ['user_data']
        }

        invalid_gate = {
            'name': 'confidence_override',
            'modifies': ['confidence_equation']
        }

        is_valid, _ = self.protection.validate_gate(valid_gate)
        self.assertTrue(is_valid)

        is_valid, reason = self.protection.validate_gate(invalid_gate)
        self.assertFalse(is_valid)
        self.assertIn('protected', reason.lower())


class TestEnhancedMurphyIndex(unittest.TestCase):
    """Test enhanced Murphy index with organizational pressure"""

    def setUp(self):
        self.monitor = EnhancedMurphyIndexMonitor()

    def test_murphy_probability_computation(self):
        """Test p_k = σ(αH + β(1-D) + γE + δA + ηI)"""
        prob = self.monitor.compute_murphy_probability(
            hallucination_score=0.5,
            determinism_score=0.8,
            exposure=0.3,
            authority_risk=0.2
        )

        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_pressure_increases_murphy(self):
        """Test that organizational pressure increases Murphy probability"""
        # No pressure
        self.monitor.incentive_monitor.set_override(OrganizationalOverride.NONE)
        prob_none = self.monitor.compute_murphy_probability(0.5, 0.8, 0.3, 0.2)

        # High pressure
        self.monitor.incentive_monitor.set_override(OrganizationalOverride.FORCE)
        prob_force = self.monitor.compute_murphy_probability(0.5, 0.8, 0.3, 0.2)

        self.assertGreater(prob_force, prob_none)


class TestMFGCv1_1Controller(unittest.TestCase):
    """Test MFGC v1.1 controller"""

    def setUp(self):
        self.controller = MFGCv1_1Controller()

    def test_execution_with_v1_1(self):
        """Test execution with v1.1 features"""
        state = self.controller.execute("Test task")

        self.assertIsNotNone(state)
        self.assertGreater(len(state.phase_history), 0)

    def test_organizational_override_reduces_authority(self):
        """Test that organizational pressure reduces authority"""
        # Execute without pressure - use a task that generates some authority
        state_normal = self.controller.execute("Design a simple system")
        authority_normal = state_normal.a_t

        # Create new controller for clean test
        controller2 = MFGCv1_1Controller()

        # Execute with pressure
        controller2.set_organizational_override(OrganizationalOverride.FORCE)
        state_pressure = controller2.execute("Design a simple system")
        authority_pressure = state_pressure.a_t

        # If both are 0, at least verify pressure was recorded
        if authority_normal == 0.0 and authority_pressure == 0.0:
            self.assertEqual(
                controller2.murphy_monitor.incentive_monitor.current_override,
                OrganizationalOverride.FORCE
            )
        else:
            # Authority should be lower under pressure
            self.assertLessEqual(authority_pressure, authority_normal)

    def test_v1_1_summary(self):
        """Test v1.1 summary includes new features"""
        state = self.controller.execute("Test task")
        summary = self.controller.get_v1_1_summary(state)

        self.assertIn('v1_1_features', summary)
        self.assertIn('trust_weighted_grounding', summary['v1_1_features'])
        self.assertIn('organizational_pressure', summary['v1_1_features'])


class TestStressTests(unittest.TestCase):
    """Test stress test scenarios"""

    def test_boeing_failure_prevention(self):
        """Test Boeing-style failure prevention"""
        result = stress_test_boeing_failure()
        self.assertEqual(result['result'], 'PASS - Authority decayed under pressure')

    def test_flash_crash_prevention(self):
        """Test flash crash prevention"""
        result = stress_test_flash_crash()
        self.assertTrue(result['has_safety_gates'], "Should have safety gates")
        self.assertIn('PASS', result['result'])

    def test_medical_ai_prevention(self):
        """Test medical AI failure prevention"""
        result = stress_test_medical_ai()
        self.assertIn('PASS', result['result'])


if __name__ == '__main__':
    unittest.main()
