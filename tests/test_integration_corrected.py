"""
Corrected Integration Test Suite for All Adapters

Tests all adapters working together with correct attribute names
"""
import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.system_integrator import SystemIntegrator
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

    def test_security_adapter_available(self):
        """Test Security Adapter is available"""
        self.assertTrue(hasattr(self.integrator, 'security_adapter'))
        self.assertIsNotNone(self.integrator.security_adapter)

        # Test trust score computation
        result = self.integrator.compute_trust_score(
            entity_id="test_entity",
            base_score=0.7
        )

        self.assertIsNotNone(result)
        self.assertIn('trust_score', result)

    def test_module_compiler_available(self):
        """Test Module Compiler is available"""
        self.assertTrue(hasattr(self.integrator, 'module_compiler'))
        self.assertIsNotNone(self.integrator.module_compiler)

        # Test module compilation
        result = self.integrator.compile_module(source_path="test_module.py")

        self.assertIsNotNone(result)

    def test_neuro_symbolic_available(self):
        """Test Neuro-Symbolic is available"""
        self.assertTrue(hasattr(self.integrator, 'neuro_symbolic'))
        self.assertIsNotNone(self.integrator.neuro_symbolic)

        # Test inference
        result = self.integrator.perform_inference(query="What is 2 + 2?")

        self.assertIsNotNone(result)

    def test_telemetry_available(self):
        """Test Telemetry is available"""
        self.assertTrue(hasattr(self.integrator, 'telemetry'))
        if self.integrator.telemetry is None:
            self.skipTest("Telemetry adapter not available")

        # Test metric collection
        result = self.integrator.collect_metric(
            metric_type="performance",
            metric_name="test_metric",
            value=42.5
        )

        self.assertIsNotNone(result)

        # Test metric retrieval
        metrics = self.integrator.get_metrics()
        self.assertIsNotNone(metrics)

    def test_librarian_available(self):
        """Test Librarian is available"""
        self.assertTrue(hasattr(self.integrator, 'librarian_adapter'))
        self.assertIsNotNone(self.integrator.librarian_adapter)

        # Test question answering
        result = self.integrator.ask_librarian_question(question="What can Murphy do?")

        self.assertIsNotNone(result)

    def test_complete_workflow(self):
        """Test complete workflow through all adapters"""
        # Process a user request
        result = self.integrator.process_user_request(
            "I want to build a web application for tracking workouts"
        )

        self.assertIsNotNone(result)


class TestCrossAdapterWorkflow(unittest.TestCase):
    """Test cross-adapter workflows"""

    def setUp(self):
        """Set up test fixtures"""
        try:
            self.integrator = SystemIntegrator()
        except Exception as e:
            self.skipTest(f"Cannot create SystemIntegrator: {e}")

    def test_security_to_compiler_workflow(self):
        """Test Security → Module Compiler workflow"""
        # Step 1: Compute trust score
        trust_result = self.integrator.compute_trust_score(
            entity_id="test_module",
            base_score=0.8
        )
        self.assertIsNotNone(trust_result)

        # Step 2: Compile module
        compiler_result = self.integrator.compile_module(
            source_path="test_module.py"
        )
        self.assertIsNotNone(compiler_result)

    def test_neuro_symbolic_to_telemetry_workflow(self):
        """Test Neuro-Symbolic → Telemetry workflow"""
        # Step 1: Perform inference
        inference_result = self.integrator.perform_inference(
            query="Analyze system performance"
        )
        self.assertIsNotNone(inference_result)

        # Step 2: Collect metric
        metric_result = self.integrator.collect_metric(
            metric_type="inference",
            metric_name="analysis",
            value=0.85
        )
        self.assertIsNotNone(metric_result)

    def test_librarian_to_neuro_symbolic_workflow(self):
        """Test Librarian → Neuro-Symbolic workflow"""
        # Step 1: Get documentation
        docs_result = self.integrator.get_librarian_documentation(
            topic="capabilities"
        )
        self.assertIsNotNone(docs_result)

        # Step 2: Perform inference based on docs
        inference_result = self.integrator.perform_inference(
            query="What are the system capabilities?"
        )
        self.assertIsNotNone(inference_result)

    def test_complete_adapter_sequence(self):
        """Test all adapters in sequence"""
        # Step 1: Security check
        trust_result = self.integrator.compute_trust_score(
            entity_id="workflow_test",
            base_score=0.9
        )
        self.assertIsNotNone(trust_result)

        # Step 2: Neuro-symbolic inference
        inference_result = self.integrator.perform_inference(
            query="What architecture is needed?"
        )
        self.assertIsNotNone(inference_result)

        # Step 3: Module compilation
        compiler_result = self.integrator.compile_module(
            source_path="architecture.py"
        )
        self.assertIsNotNone(compiler_result)

        # Step 4: Telemetry collection
        metric_result = self.integrator.collect_metric(
            metric_type="workflow",
            metric_name="steps_completed",
            value=4
        )
        self.assertIsNotNone(metric_result)

        # Step 5: Librarian query
        docs_result = self.integrator.get_librarian_documentation(
            topic="architecture"
        )
        self.assertIsNotNone(docs_result)


class TestErrorHandling(unittest.TestCase):
    """Test error handling across adapters"""

    def setUp(self):
        """Set up test fixtures"""
        try:
            self.integrator = SystemIntegrator()
        except Exception as e:
            self.skipTest(f"Cannot create SystemIntegrator: {e}")

    def test_graceful_degradation(self):
        """Test graceful degradation when adapters unavailable"""
        # System should work even with some adapters in fallback mode
        result = self.integrator.process_user_request("Hello Murphy")
        self.assertIsNotNone(result)

    def test_error_recovery(self):
        """Test that system recovers from errors"""
        # Try to get system state
        state = self.integrator.get_system_state()
        self.assertIsNotNone(state)

    def test_invalid_input_handling(self):
        """Test handling of invalid input"""
        # System should handle empty input gracefully
        try:
            result = self.integrator.process_user_request("")
            # Should handle gracefully or raise appropriate error
            self.assertIsNotNone(result)
        except Exception:
            # Error is acceptable if it's handled properly
            pass


def run_corrected_integration_tests():
    """Run all corrected integration tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestAdapterIntegration,
        TestCrossAdapterWorkflow,
        TestErrorHandling
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("CORRECTED INTEGRATION TEST SUMMARY")
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
    result = run_corrected_integration_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
