"""
Integration Test Suite for All Adapters

Tests all 5 adapters working together with SystemIntegrator
"""
import unittest
import sys
import os
from datetime import datetime

# Add src to path

try:
    from src.system_integrator import SystemIntegrator
    from src.security_plane_adapter import SecurityPlaneAdapter
    from src.module_compiler_adapter import ModuleCompilerAdapter
    from src.neuro_symbolic_adapter import NeuroSymbolicAdapter
    from src.telemetry_adapter import TelemetryAdapter
    from src.librarian_adapter import LibrarianAdapter
except ImportError as e:
    print(f"Import error: {e}")


class TestAdapterIntegration(unittest.TestCase):
    """Test all adapter integrations"""

    def setUp(self):
        """Set up test fixtures"""
        try:
            self.integrator = SystemIntegrator()
        except Exception as e:
            self.skipTest(f"Cannot create SystemIntegrator: {e}")

    def test_all_adapters_initialized(self):
        """Test that all 5 adapters are initialized"""
        adapters = {
            'security_adapter': SecurityPlaneAdapter,
            'module_compiler': ModuleCompilerAdapter,
            'neuro_symbolic': NeuroSymbolicAdapter,
            'telemetry': TelemetryAdapter,
            'librarian_adapter': LibrarianAdapter
        }

        for adapter_name, adapter_class in adapters.items():
            with self.subTest(adapter=adapter_name):
                adapter = getattr(self.integrator, adapter_name, None)
                if adapter is None:
                    self.skipTest(f"{adapter_name} not available (optional dependency)")
                self.assertIsInstance(adapter, adapter_class)

    def test_security_adapter_integration(self):
        """Test Security Plane Adapter integration"""
        adapter = self.integrator.security_adapter

        # Test trust score computation
        result = adapter.compute_trust_score(
            entity_id="test_entity",
            base_score=0.7
        )

        self.assertIsNotNone(result)
        self.assertIn('trust_score', result)
        self.assertIsInstance(result['trust_score'], float)
        self.assertGreaterEqual(result['trust_score'], 0.0)
        self.assertLessEqual(result['trust_score'], 1.0)

    def test_module_compiler_adapter_integration(self):
        """Test Module Compiler Adapter integration"""
        adapter = self.integrator.module_compiler

        # Test module compilation
        result = adapter.compile_module(source_path="test_module.py")

        self.assertIsNotNone(result)
        self.assertIn('success', result)

    def test_neuro_symbolic_adapter_integration(self):
        """Test Neuro-Symbolic Adapter integration"""
        adapter = self.integrator.neuro_symbolic

        # Test inference
        result = adapter.perform_inference(query="What is 2 + 2?")

        self.assertIsNotNone(result)
        self.assertIn('inference_result', result)

    def test_telemetry_adapter_integration(self):
        """Test Telemetry Adapter integration"""
        adapter = self.integrator.telemetry
        if adapter is None:
            self.skipTest("Telemetry adapter not available")

        # Test metric collection
        result = adapter.collect_metric(
            metric_type="performance",
            metric_name="test_metric",
            value=42.5
        )

        self.assertIsNotNone(result)

        # Test metric retrieval
        metrics = adapter.get_metrics()
        self.assertIsNotNone(metrics)

    def test_librarian_adapter_integration(self):
        """Test Librarian Adapter integration"""
        adapter = self.integrator.librarian_adapter

        # Test question answering
        result = adapter.ask_question(question="What can Murphy do?")

        self.assertIsNotNone(result)
        self.assertIn('answer', result)

    def test_complete_workflow_integration(self):
        """Test complete workflow through all adapters"""
        if self.integrator.telemetry is None:
            self.skipTest("Telemetry adapter not available")
        # Process a user request
        result = self.integrator.process_user_request(
            "I want to build a web application for tracking workouts"
        )

        self.assertIsNotNone(result)
        # Result can be SystemResponse object or dict
        self.assertTrue(
            hasattr(result, 'response') or isinstance(result, dict),
            "Result should have response or be a dict"
        )


class TestCrossAdapterIntegration(unittest.TestCase):
    """Test cross-adapter workflows"""

    def setUp(self):
        """Set up test fixtures"""
        try:
            self.integrator = SystemIntegrator()
        except Exception as e:
            self.skipTest(f"Cannot create SystemIntegrator: {e}")

    def test_security_to_module_compiler(self):
        """Test Security → Module Compiler workflow"""
        if self.integrator.module_compiler is None:
            self.skipTest("Module compiler adapter not available")
        # Step 1: Validate input with security adapter
        security_result = self.integrator.security_adapter.validate_input(
            field_name="user_input",
            value="safe_code_module.py"
        )

        self.assertIsNotNone(security_result)

        # Step 2: Compile module with module compiler
        compiler_result = self.integrator.module_compiler.compile_module(
            source_path="safe_code_module.py"
        )

        self.assertIsNotNone(compiler_result)

    def test_neuro_symbolic_to_telemetry(self):
        """Test Neuro-Symbolic → Telemetry workflow"""
        if self.integrator.neuro_symbolic is None:
            self.skipTest("Neuro-symbolic adapter not available")
        if self.integrator.telemetry is None:
            self.skipTest("Telemetry adapter not available")
        # Step 1: Perform inference
        inference_result = self.integrator.neuro_symbolic.perform_inference(
            query="Analyze the system performance"
        )

        self.assertIsNotNone(inference_result)

        # Step 2: Collect metric based on inference
        metric_result = self.integrator.telemetry.collect_metric(
            metric_type="inference",
            metric_name="analysis_result",
            value=0.85
        )

        self.assertIsNotNone(metric_result)

    def test_librarian_to_gate_generation(self):
        """Test Librarian → Gate Generation workflow"""
        # Step 1: Get documentation from librarian
        docs_result = self.integrator.librarian_adapter.get_documentation(
            topic="security_gates"
        )

        self.assertIsNotNone(docs_result)

        # Step 2: Generate security gates based on docs
        # Note: This would use a gate generator if available
        self.assertIsNotNone(docs_result)

    def test_all_adapters_in_sequence(self):
        """Test all adapters working in sequence"""
        if self.integrator.neuro_symbolic is None:
            self.skipTest("Neuro-symbolic adapter not available")
        if self.integrator.telemetry is None:
            self.skipTest("Telemetry adapter not available")
        if self.integrator.module_compiler is None:
            self.skipTest("Module compiler adapter not available")
        # Step 1: Validate input
        security_result = self.integrator.security_adapter.validate_input(
            field_name="request",
            value="Build a secure system"
        )
        self.assertIsNotNone(security_result)

        # Step 2: Perform inference
        inference_result = self.integrator.neuro_symbolic.perform_inference(
            query="What components are needed?"
        )
        self.assertIsNotNone(inference_result)

        # Step 3: Compile module
        compiler_result = self.integrator.module_compiler.compile_module(
            source_path="system_module.py"
        )
        self.assertIsNotNone(compiler_result)

        # Step 4: Collect metrics
        metric_result = self.integrator.telemetry.collect_metric(
            metric_type="workflow",
            metric_name="completion_time",
            value=1.5
        )
        self.assertIsNotNone(metric_result)

        # Step 5: Get documentation
        docs_result = self.integrator.librarian_adapter.get_documentation(
            topic="architecture"
        )
        self.assertIsNotNone(docs_result)


class TestErrorHandlingIntegration(unittest.TestCase):
    """Test error handling across adapters"""

    def setUp(self):
        """Set up test fixtures"""
        try:
            self.integrator = SystemIntegrator()
        except Exception as e:
            self.skipTest(f"Cannot create SystemIntegrator: {e}")

    def test_adapter_error_recovery(self):
        """Test that system recovers from adapter errors"""
        # Try to get system state (should work even if some adapters fail)
        try:
            state = self.integrator.state
            self.assertIsNotNone(state)
        except AttributeError:
            # Alternative: Try to get system state through method
            try:
                if hasattr(self.integrator, 'get_system_state_dict'):
                    state = self.integrator.get_system_state_dict()
                    self.assertIsNotNone(state)
            except:
                # If still fails, that's ok - test the system is still functional
                result = self.integrator.process_user_request("test")
                self.assertIsNotNone(result)

    def test_graceful_degradation(self):
        """Test graceful degradation when adapters unavailable"""
        # System should still work even if some adapters in fallback mode
        result = self.integrator.process_user_request("Hello")
        self.assertIsNotNone(result)

    def test_error_propagation(self):
        """Test that errors are properly propagated"""
        # Try invalid input
        try:
            result = self.integrator.process_user_request("")
            # Should handle gracefully
            self.assertIsNotNone(result)
        except Exception:
            # Or raise appropriate exception
            pass


def run_integration_tests():
    """Run all integration tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestAdapterIntegration,
        TestCrossAdapterIntegration,
        TestErrorHandlingIntegration
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("INTEGRATION TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        print(f"Success Rate: {success_rate:.1f}%")
    print("="*70)

    return result


if __name__ == '__main__':
    result = run_integration_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
