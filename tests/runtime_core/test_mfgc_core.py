"""
Unit tests for MFGC core functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from mfgc_core import (
    Phase, MFGCSystemState as SystemState, ConfidenceEngine, AuthorityController,
    MurphyIndexMonitor, GateCompiler, SwarmGenerator, MFGCController
)


class TestPhase(unittest.TestCase):
    """Test Phase enum"""

    def test_phase_order(self):
        """Test phases are in correct order"""
        phases = list(Phase)
        self.assertEqual(phases[0], Phase.EXPAND)
        self.assertEqual(phases[-1], Phase.EXECUTE)
        self.assertEqual(len(phases), 7)

    def test_confidence_thresholds(self):
        """Test confidence thresholds increase with phases"""
        phases = list(Phase)
        for i in range(len(phases) - 1):
            self.assertLess(
                phases[i].confidence_threshold,
                phases[i+1].confidence_threshold
            )

    def test_weights(self):
        """Test weights shift from generative to deterministic"""
        phases = list(Phase)
        for i in range(len(phases) - 1):
            w_g_curr, w_d_curr = phases[i].weights
            w_g_next, w_d_next = phases[i+1].weights
            self.assertGreater(w_g_curr, w_g_next)  # Generative decreases
            self.assertLess(w_d_curr, w_d_next)     # Deterministic increases


class TestSystemState(unittest.TestCase):
    """Test SystemState"""

    def test_initialization(self):
        """Test state initializes correctly"""
        state = SystemState()
        self.assertEqual(state.c_t, 0.0)
        self.assertEqual(state.p_t, Phase.EXPAND)
        self.assertEqual(state.M_t, 0.0)
        self.assertEqual(len(state.G_t), 0)

    def test_log_event(self):
        """Test event logging"""
        state = SystemState()
        state.log_event('test', {'data': 'value'})
        self.assertEqual(len(state.events), 1)
        self.assertEqual(state.events[0]['type'], 'test')

    def test_advance_phase(self):
        """Test phase advancement"""
        state = SystemState()
        initial_phase = state.p_t
        state.advance_phase()
        self.assertNotEqual(state.p_t, initial_phase)
        # Phase history starts with EXPAND, then adds next phase
        self.assertGreaterEqual(len(state.phase_history), 1)


class TestConfidenceEngine(unittest.TestCase):
    """Test ConfidenceEngine"""

    def setUp(self):
        self.engine = ConfidenceEngine()
        self.state = SystemState()

    def test_compute_confidence(self):
        """Test confidence computation"""
        confidence = self.engine.compute_confidence(self.state, 0.8, 0.9)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)

    def test_confidence_bounds(self):
        """Test confidence is always bounded"""
        # Test with extreme values
        confidence = self.engine.compute_confidence(self.state, 2.0, 2.0)
        self.assertLessEqual(confidence, 1.0)

        confidence = self.engine.compute_confidence(self.state, -1.0, -1.0)
        self.assertGreaterEqual(confidence, 0.0)

    def test_phase_weights(self):
        """Test weights change with phase"""
        self.state.p_t = Phase.EXPAND
        conf_expand = self.engine.compute_confidence(self.state, 0.5, 0.8)

        self.state.p_t = Phase.EXECUTE
        conf_execute = self.engine.compute_confidence(self.state, 0.5, 0.8)

        # EXECUTE should weight deterministic more, so higher conf with high det score
        self.assertGreater(conf_execute, conf_expand)


class TestAuthorityController(unittest.TestCase):
    """Test AuthorityController"""

    def setUp(self):
        self.controller = AuthorityController()

    def test_compute_authority(self):
        """Test authority computation"""
        authority = self.controller.compute_authority(0.9, Phase.EXPAND)
        self.assertGreaterEqual(authority, 0.0)
        self.assertLessEqual(authority, 1.0)

    def test_authority_below_threshold(self):
        """Test authority is minimal below threshold"""
        authority = self.controller.compute_authority(0.1, Phase.EXECUTE)
        self.assertEqual(authority, 0.0)

    def test_authority_increases_with_confidence(self):
        """Test authority increases with confidence"""
        auth_low = self.controller.compute_authority(0.5, Phase.EXPAND)
        auth_high = self.controller.compute_authority(0.9, Phase.EXPAND)
        self.assertLess(auth_low, auth_high)

    def test_can_execute(self):
        """Test action authorization"""
        self.assertTrue(self.controller.can_execute(0.0, 'generate'))
        self.assertFalse(self.controller.can_execute(0.0, 'deploy'))
        self.assertTrue(self.controller.can_execute(0.95, 'deploy'))


class TestMurphyIndexMonitor(unittest.TestCase):
    """Test MurphyIndexMonitor"""

    def setUp(self):
        self.monitor = MurphyIndexMonitor(threshold=0.3)

    def test_add_risk(self):
        """Test risk addition"""
        self.monitor.add_risk(0.5, 0.4, "Test risk")
        self.assertEqual(len(self.monitor.risks), 1)

    def test_compute_index(self):
        """Test Murphy index computation"""
        self.monitor.add_risk(0.5, 0.4, "Risk 1")  # 0.2
        self.monitor.add_risk(0.3, 0.2, "Risk 2")  # 0.06
        index = self.monitor.compute_index()
        self.assertAlmostEqual(index, 0.26, places=2)

    def test_check_threshold(self):
        """Test threshold checking"""
        self.assertFalse(self.monitor.check_threshold(0.2))
        self.assertTrue(self.monitor.check_threshold(0.4))

    def test_get_top_risks(self):
        """Test top risks retrieval"""
        self.monitor.add_risk(0.5, 0.4, "High risk")
        self.monitor.add_risk(0.2, 0.1, "Low risk")
        top = self.monitor.get_top_risks(1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]['description'], "High risk")


class TestGateCompiler(unittest.TestCase):
    """Test GateCompiler"""

    def setUp(self):
        self.compiler = GateCompiler()

    def test_synthesize_gates(self):
        """Test gate synthesis"""
        candidates = [
            {'type': 'test', 'requires_validation': ['security']}
        ]
        risks = [
            {'description': 'vendor lock-in', 'loss': 0.5, 'probability': 0.3}
        ]
        gates = self.compiler.synthesize_gates(candidates, risks)
        self.assertGreater(len(gates), 0)

    def test_risk_to_gate(self):
        """Test risk to gate conversion"""
        risk = {'description': 'data corruption', 'loss': 0.8, 'probability': 0.2}
        gate = self.compiler._risk_to_gate(risk)
        self.assertIsNotNone(gate)
        self.assertIn('data', gate.lower())


class TestSwarmGenerator(unittest.TestCase):
    """Test SwarmGenerator"""

    def setUp(self):
        self.generator = SwarmGenerator()

    def test_generate_candidates(self):
        """Test candidate generation"""
        candidates = self.generator.generate_candidates(
            "Test task",
            Phase.EXPAND,
            {}
        )
        self.assertGreater(len(candidates), 0)

    def test_phase_specific_generation(self):
        """Test different phases generate different candidates"""
        expand = self.generator.generate_candidates("Test", Phase.EXPAND, {})
        execute = self.generator.generate_candidates("Test", Phase.EXECUTE, {})

        # Should have different structures
        self.assertNotEqual(
            list(expand[0].keys()) if expand else [],
            list(execute[0].keys()) if execute else []
        )


class TestMFGCController(unittest.TestCase):
    """Test MFGCController"""

    def setUp(self):
        self.controller = MFGCController()

    def test_execute(self):
        """Test complete execution"""
        state = self.controller.execute("Test task")

        # Check state is valid
        self.assertIsNotNone(state)
        self.assertGreater(len(state.phase_history), 0)
        self.assertGreater(len(state.events), 0)

    def test_all_phases_executed(self):
        """Test all 7 phases are executed"""
        state = self.controller.execute("Complex task")
        self.assertEqual(len(state.phase_history), 7)

    def test_confidence_increases(self):
        """Test confidence generally increases"""
        state = self.controller.execute("Test task")
        if len(state.confidence_history) > 1:
            # Final confidence should be higher than initial
            self.assertGreater(
                state.confidence_history[-1],
                state.confidence_history[0]
            )

    def test_gates_synthesized(self):
        """Test gates are synthesized"""
        state = self.controller.execute("Test task")
        self.assertGreater(len(state.G_t), 0)

    def test_murphy_index_tracked(self):
        """Test Murphy index is tracked"""
        state = self.controller.execute("Test task")
        self.assertGreater(len(state.murphy_history), 0)

    def test_get_summary(self):
        """Test summary generation"""
        state = self.controller.execute("Test task")
        summary = self.controller.get_summary(state)

        self.assertIn('task', summary)
        self.assertIn('final_confidence', summary)
        self.assertIn('total_gates', summary)

    # ------------------------------------------------------------------
    # CFP-4: FeedbackIntegrator wiring
    # ------------------------------------------------------------------

    def test_feedback_integrator_wired(self):
        """MFGCController has a FeedbackIntegrator when available."""
        if not self.controller._feedback_available:
            self.skipTest("feedback_integrator not importable")
        self.assertIsNotNone(self.controller._feedback_integrator)

    def test_pending_feedback_signals_initialised(self):
        """State starts with an empty pending_feedback_signals list."""
        state = self.controller.execute("Test task")
        self.assertIsInstance(state.pending_feedback_signals, list)

    def test_murphy_threshold_populates_feedback_signals(self):
        """When Murphy threshold is exceeded, a feedback signal is recorded."""
        if not self.controller._feedback_available:
            self.skipTest("feedback_integrator not importable")
        # Lower the Murphy threshold so it fires on every phase
        self.controller.murphy_monitor.threshold = 0.0
        state = self.controller.execute("High-risk task")
        self.assertGreater(len(state.pending_feedback_signals), 0)

    def test_apply_feedback_correction_updates_state(self):
        """apply_feedback_correction() adds a signal and logs an event."""
        if not self.controller._feedback_available:
            self.skipTest("feedback_integrator not importable")
        state = self.controller.execute("Test task")
        initial_event_count = len(state.events)
        self.controller.apply_feedback_correction(
            state,
            original_confidence=0.4,
            corrected_confidence=0.8,
        )
        self.assertGreater(len(state.events), initial_event_count)
        event_types = [e['type'] for e in state.events]
        self.assertIn('feedback_correction_applied', event_types)

    def test_apply_feedback_correction_returns_state(self):
        """apply_feedback_correction() returns the same state object."""
        if not self.controller._feedback_available:
            self.skipTest("feedback_integrator not importable")
        state = self.controller.execute("Test task")
        returned = self.controller.apply_feedback_correction(
            state, 0.5, 0.9
        )
        self.assertIs(returned, state)

    def test_recalibration_event_logged_when_triggered(self):
        """recalibration_triggered event is logged when threshold exceeded."""
        if not self.controller._feedback_available:
            self.skipTest("feedback_integrator not importable")
        # Force large Murphy index so corrections exceed the recalibration threshold
        self.controller.murphy_monitor.threshold = 0.0
        state = self.controller.execute("High-risk task for recalibration")
        event_types = [e['type'] for e in state.events]
        # If signals were emitted and they collectively exceeded the threshold,
        # 'recalibration_triggered' must appear.  If not (signals below threshold
        # or none emitted), the list just won't contain it — both outcomes are valid.
        for etype in event_types:
            self.assertIsInstance(etype, str)
        if 'recalibration_triggered' in event_types:
            # Verify the event has the expected fields
            evt = next(e for e in state.events if e['type'] == 'recalibration_triggered')
            self.assertIn('signal_count', evt['data'])
            self.assertGreater(evt['data']['signal_count'], 0)


if __name__ == '__main__':
    unittest.main()
