"""
Comprehensive tests for Deterministic Compute Plane

Tests all components:
- Expression parsing
- Symbolic solving
- Numeric solving
- Determinism analysis
- Compute service
- API endpoints
"""

import unittest
import time
from unittest.mock import patch
from src.compute_plane.models.compute_request import ComputeRequest
from src.compute_plane.models.compute_result import ComputeResult, ComputeStatus
from src.compute_plane.parsers.expression_parser import ExpressionParser
from src.compute_plane.solvers.symbolic_solver import SymbolicSolver
from src.compute_plane.solvers.numeric_solver import NumericSolver
from src.compute_plane.analyzers.determinism_analyzer import DeterminismAnalyzer
from src.compute_plane.service import ComputeService


class TestExpressionParser(unittest.TestCase):
    """Test expression parsing"""

    def setUp(self):
        self.parser = ExpressionParser()

    def test_parse_simple_sympy(self):
        """Test parsing simple SymPy expression"""
        if not self.parser.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x**2 + 2*x + 1", "sympy")
        self.assertIsNotNone(parsed.parsed)
        self.assertEqual(parsed.language, "sympy")
        self.assertLessEqual(parsed.uncertainty, 0.5)

    def test_parse_with_cleaning(self):
        """Test parsing with expression cleaning"""
        if not self.parser.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x times 2 plus 3", "sympy")
        self.assertIsNotNone(parsed.parsed)
        self.assertGreater(len(parsed.warnings), 0)

    def test_validate_syntax_valid(self):
        """Test syntax validation for valid expression"""
        if not self.parser.sympy_available:
            self.skipTest("SymPy not available")

        validation = self.parser.validate_syntax("x**2 + 1", "sympy")
        self.assertTrue(validation.is_valid)
        self.assertEqual(len(validation.errors), 0)

    def test_validate_syntax_invalid(self):
        """Test syntax validation for invalid expression"""
        validation = self.parser.validate_syntax("", "sympy")
        self.assertFalse(validation.is_valid)
        self.assertGreater(len(validation.errors), 0)


class TestSymbolicSolver(unittest.TestCase):
    """Test symbolic solving"""

    def setUp(self):
        self.parser = ExpressionParser()
        self.solver = SymbolicSolver()

    def test_simplify(self):
        """Test symbolic simplification"""
        if not self.solver.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x**2 + 2*x + 1", "sympy")
        normalized = self.parser.normalize(parsed)

        result = self.solver.solve_sympy(normalized, "simplify")
        self.assertIsNotNone(result.result)
        self.assertEqual(result.solver, "sympy")
        self.assertGreater(len(result.derivation_steps), 0)

    def test_expand(self):
        """Test symbolic expansion"""
        if not self.solver.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("(x + 1)**2", "sympy")
        normalized = self.parser.normalize(parsed)

        result = self.solver.solve_sympy(normalized, "expand")
        self.assertIsNotNone(result.result)

    def test_integrate(self):
        """Test symbolic integration"""
        if not self.solver.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x**2", "sympy")
        normalized = self.parser.normalize(parsed)

        result = self.solver.solve_sympy(normalized, "integrate:x")
        self.assertIsNotNone(result.result)
        self.assertIn("Integrated", result.derivation_steps[1])

    def test_differentiate(self):
        """Test symbolic differentiation"""
        if not self.solver.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x**3", "sympy")
        normalized = self.parser.normalize(parsed)

        result = self.solver.solve_sympy(normalized, "diff:x")
        self.assertIsNotNone(result.result)
        self.assertIn("Differentiated", result.derivation_steps[1])


class TestNumericSolver(unittest.TestCase):
    """Test numeric solving"""

    def setUp(self):
        self.parser = ExpressionParser()
        self.solver = NumericSolver()

    def test_evaluate(self):
        """Test numeric evaluation"""
        if not self.solver.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x**2 + 1", "sympy")
        normalized = self.parser.normalize(parsed)

        result = self.solver.evaluate(normalized, substitutions={'x': 2.0})
        self.assertIsNotNone(result['result'])
        self.assertEqual(result['result'], 5.0)

    def test_compute_bounds(self):
        """Test bounds computation"""
        if not self.solver.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x**2", "sympy")
        normalized = self.parser.normalize(parsed)

        bounds = self.solver.compute_bounds(normalized, {'x': (0, 10)})
        self.assertIsInstance(bounds, tuple)
        self.assertEqual(len(bounds), 2)
        self.assertLessEqual(bounds[0], bounds[1])

    def test_sensitivity_analysis(self):
        """Test sensitivity analysis"""
        if not self.solver.sympy_available:
            self.skipTest("SymPy not available")

        parsed = self.parser.parse("x**2 + y", "sympy")
        normalized = self.parser.normalize(parsed)

        sensitivity = self.solver.sensitivity_analysis(
            normalized,
            {'x': 2.0, 'y': 1.0}
        )
        self.assertIsInstance(sensitivity, dict)
        self.assertIn('x', sensitivity)
        self.assertIn('y', sensitivity)


class TestDeterminismAnalyzer(unittest.TestCase):
    """Test determinism analysis"""

    def setUp(self):
        self.analyzer = DeterminismAnalyzer()

    def test_compute_stability_high(self):
        """Test stability computation for stable result"""
        stability = self.analyzer.compute_stability(5.0, {'x': 0.1})
        self.assertGreater(stability, 0.5)

    def test_compute_stability_low(self):
        """Test stability computation for unstable result"""
        stability = self.analyzer.compute_stability(5.0, {'x': 100.0})
        self.assertLess(stability, 0.5)

    def test_compute_confidence(self):
        """Test confidence computation"""
        confidence = self.analyzer.compute_confidence(5.0, 0.9)
        self.assertGreater(confidence, 0.5)

    def test_analyze_result(self):
        """Test complete result analysis"""
        analysis = self.analyzer.analyze_result(
            5.0,
            sensitivity={'x': 0.1},
            assumptions={'x': 'real'}
        )
        self.assertIn('stability_estimate', analysis)
        self.assertIn('confidence_score', analysis)
        self.assertIn('is_deterministic', analysis)


class TestComputeService(unittest.TestCase):
    """Test compute service"""

    def setUp(self):
        self.service = ComputeService(enable_caching=True)

    def _wait_for_result(self, request_id, retries=20, interval=0.1):
        result = None
        for _ in range(retries):
            result = self.service.get_result(request_id)
            if result is not None:
                return result
            time.sleep(interval)
        return result

    def test_submit_and_get_result(self):
        """Test submitting request and getting result"""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request = ComputeRequest(
            expression="x**2 + 1",
            language="sympy",
            metadata={'operation': 'simplify'}
        )

        request_id = self.service.submit_request(request)
        self.assertIsNotNone(request_id)

        # Wait for computation
        time.sleep(1)

        result = self.service.get_result(request_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, ComputeStatus.SUCCESS)

    def test_get_result_returns_copy(self):
        """Mutating retrieved results should not mutate cached results."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="result-copy-request",
            metadata={"operation": "simplify"},
        )
        request_id = self.service.submit_request(request)

        retrieved = None
        for _ in range(20):
            retrieved = self.service.get_result(request_id)
            if retrieved is not None:
                break
            time.sleep(0.1)

        self.assertIsNotNone(retrieved)
        baseline_metadata = dict(retrieved.metadata)
        baseline_steps = list(retrieved.derivation_steps)
        retrieved.metadata["note"] = "mutated"
        retrieved.derivation_steps.append("step-2")

        fresh = self.service.get_result(request_id)
        self.assertEqual(fresh.metadata, baseline_metadata)
        self.assertEqual(fresh.derivation_steps, baseline_steps)

    def test_submit_request_deduplicates_pending_request(self):
        """Test that duplicate pending requests do not spawn duplicate workers"""
        request = ComputeRequest(
            expression="x**2 + 1",
            language="sympy",
            request_id="dedup-pending-request"
        )

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            mock_thread = mock_thread_cls.return_value

            request_id_1 = self.service.submit_request(request)
            request_id_2 = self.service.submit_request(request)

            self.assertEqual(request_id_1, request.request_id)
            self.assertEqual(request_id_2, request.request_id)
            self.assertEqual(mock_thread_cls.call_count, 1)
            self.assertEqual(mock_thread.start.call_count, 1)

    def test_submit_request_prevents_caller_mutation_of_queued_request(self):
        """Caller mutation after submit should not alter the queued compute request."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="mutation-snapshot-request",
            metadata={"operation": "simplify"},
        )

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            mock_thread = mock_thread_cls.return_value
            mock_thread.start.return_value = None

            request_id = self.service.submit_request(request)
            submitted_request = mock_thread_cls.call_args.kwargs["args"][0]

            request.expression = "x + 999"
            request.metadata["operation"] = "expand"

            self.assertEqual(submitted_request.expression, "x + 1")
            self.assertEqual(submitted_request.metadata.get("operation"), "simplify")

        # Process outside mock context so ThreadPoolExecutor can spawn workers.
        self.service._process_request(submitted_request)

        result = self.service.get_result(request_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, ComputeStatus.SUCCESS)
        self.assertEqual(str(result.result), "x + 1")

    def test_submit_request_respects_timeout(self):
        """Test that long-running computations return TIMEOUT"""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request = ComputeRequest(
            expression="x**2 + 1",
            language="sympy",
            timeout=1,
            request_id="timeout-request"
        )

        def mock_slow_execute(*args, **kwargs):
            time.sleep(1.5)
            return None

        with patch.object(self.service, "_execute_sympy", side_effect=mock_slow_execute):
            request_id = self.service.submit_request(request)
            result = None
            for _ in range(20):
                result = self.service.get_result(request_id)
                if result is not None:
                    break
                time.sleep(0.1)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.TIMEOUT)
            self.assertIn("timed out", result.error_message)

    def test_submit_request_after_shutdown_fails_immediately(self):
        """Test that requests submitted after shutdown fail without background work."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="shutdown-request",
        )

        self.service.shutdown()

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)
            result = self.service.get_result(request_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.FAIL)
            self.assertIn("shut down", result.error_message)
            mock_thread_cls.assert_not_called()

    def test_shutdown_clears_pending_requests_with_fail_results(self):
        """Test that shutdown resolves pending requests to FAIL and clears pending state."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="shutdown-pending-request",
        )

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            mock_thread = mock_thread_cls.return_value
            mock_thread.start.return_value = None

            request_id = self.service.submit_request(request)
            self.assertIn(request_id, self.service.pending_requests)

            self.service.shutdown()

            self.assertNotIn(request_id, self.service.pending_requests)
            result = self.service.get_result(request_id)
            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.FAIL)
            self.assertIn("shut down", result.error_message)

    def test_shutdown_submit_same_signature_reuses_existing_fail_result(self):
        """Repeated same-signature submissions after shutdown should reuse one fail cache entry."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="shutdown-repeat-fail",
        )

        self.service.shutdown()

        first_id = self.service.submit_request(request)
        second_id = self.service.submit_request(request)
        self.assertEqual(first_id, second_id)

        result = self.service.get_result(first_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, ComputeStatus.FAIL)
        self.assertIn("shut down", result.error_message)

    def test_shutdown_submit_does_not_overwrite_existing_success_result(self):
        """Submitting after shutdown should preserve an existing success result for same request ID."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="shutdown-existing-success",
            metadata={"operation": "simplify"},
        )

        request_id = self.service.submit_request(request)
        baseline = self._wait_for_result(request_id)
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline.status, ComputeStatus.SUCCESS)

        self.service.shutdown()
        replay_id = self.service.submit_request(request)
        self.assertEqual(replay_id, request_id)

        after = self.service.get_result(request_id)
        self.assertIsNotNone(after)
        self.assertEqual(after.status, ComputeStatus.SUCCESS)
        self.assertEqual(after.result, baseline.result)

    def test_shutdown_submit_with_different_signature_uses_new_request_id(self):
        """Submitting a different payload after shutdown should not clobber an existing success."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request_id = "shutdown-existing-success-different-payload"
        request_1 = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id=request_id,
            metadata={"operation": "simplify"},
        )
        request_2 = ComputeRequest(
            expression="x + 2",
            language="sympy",
            request_id=request_id,
            metadata={"operation": "simplify"},
        )

        first_id = self.service.submit_request(request_1)
        baseline = self._wait_for_result(first_id)
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline.status, ComputeStatus.SUCCESS)

        self.service.shutdown()
        second_id = self.service.submit_request(request_2)
        self.assertNotEqual(second_id, first_id)
        self.assertTrue(second_id.startswith(f"{first_id}-"))
        self.assertEqual(request_2.request_id, request_id)

        original_after = self.service.get_result(first_id)
        shutdown_after = self.service.get_result(second_id)
        self.assertIsNotNone(original_after)
        self.assertEqual(original_after.status, ComputeStatus.SUCCESS)
        self.assertIsNotNone(shutdown_after)
        self.assertEqual(shutdown_after.status, ComputeStatus.FAIL)
        self.assertIn("shut down", shutdown_after.error_message)

    def test_inflight_request_does_not_overwrite_shutdown_failure(self):
        """In-flight workers should not overwrite failure results written during shutdown."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="shutdown-inflight-request",
            metadata={"operation": "simplify"},
        )

        def slow_success(*args, **kwargs):
            time.sleep(0.3)
            return ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.SUCCESS,
                result="unexpected-success-after-shutdown",
            )

        with patch.object(self.service, "_execute_sympy", side_effect=slow_success):
            request_id = self.service.submit_request(request)
            time.sleep(0.05)
            self.service.shutdown()
            time.sleep(0.4)

        result = self.service.get_result(request_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, ComputeStatus.FAIL)
        self.assertIn("shut down", result.error_message)

    def test_submit_request_id_collision_creates_new_request_id(self):
        """Test reused request_id with different payload does not return stale cache."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request_id = "collision-request-id"
        request_1 = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id=request_id,
            metadata={"operation": "simplify"},
        )
        request_2 = ComputeRequest(
            expression="x + 2",
            language="sympy",
            request_id=request_id,
            metadata={"operation": "simplify"},
        )

        first_id = self.service.submit_request(request_1)
        time.sleep(1)
        first_result = self.service.get_result(first_id)
        self.assertIsNotNone(first_result)
        self.assertEqual(first_result.status, ComputeStatus.SUCCESS)

        second_id = self.service.submit_request(request_2)
        self.assertNotEqual(second_id, first_id)
        self.assertEqual(request_2.request_id, request_id)
        time.sleep(1)
        second_result = self.service.get_result(second_id)
        self.assertIsNotNone(second_result)
        self.assertEqual(second_result.status, ComputeStatus.SUCCESS)

    def test_submit_request_equivalent_nested_metadata_reuses_cached_request_id(self):
        """Equivalent nested metadata should not trigger a synthetic request_id suffix."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request_id = "nested-metadata-collision"
        request_1 = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id=request_id,
            metadata={"operation": "simplify", "context": {"alpha": 1, "beta": 2}},
        )
        request_2 = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id=request_id,
            metadata={"operation": "simplify", "context": {"beta": 2, "alpha": 1}},
        )

        first_id = self.service.submit_request(request_1)
        time.sleep(1)
        first_result = self.service.get_result(first_id)
        self.assertIsNotNone(first_result)
        self.assertEqual(first_result.status, ComputeStatus.SUCCESS)

        second_id = self.service.submit_request(request_2)
        self.assertEqual(second_id, first_id)
        second_result = self.service.get_result(second_id)
        self.assertIsNotNone(second_result)
        self.assertEqual(second_result.status, first_result.status)
        self.assertEqual(second_result.result, first_result.result)

    def test_submit_without_caching_hides_stale_result_while_pending(self):
        """Re-submission with caching disabled should hide stale cached results while pending."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        service = ComputeService(enable_caching=False)
        request_id = "no-cache-repeat-request"
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id=request_id,
            metadata={"operation": "simplify"},
        )

        try:
            first_id = service.submit_request(request)
            self.assertEqual(first_id, request_id)
            time.sleep(1)
            first_result = service.get_result(request_id)
            self.assertIsNotNone(first_result)
            self.assertEqual(first_result.status, ComputeStatus.SUCCESS)

            def slow_second_result(*args, **kwargs):
                time.sleep(0.2)
                return ComputeResult(
                    request_id=request_id,
                    status=ComputeStatus.SUCCESS,
                    result="second-pass-result",
                )

            with patch.object(service, "_execute_sympy", side_effect=slow_second_result):
                second_id = service.submit_request(request)
                self.assertEqual(second_id, request_id)
                self.assertIsNone(service.get_result(request_id))
                time.sleep(0.05)
                self.assertIsNone(service.get_result(request_id))
                time.sleep(0.4)

            second_result = service.get_result(request_id)
            self.assertIsNotNone(second_result)
            self.assertEqual(second_result.status, ComputeStatus.SUCCESS)
            self.assertEqual(second_result.result, "second-pass-result")
        finally:
            service.shutdown()

    def test_validate_expression(self):
        """Test expression validation"""
        validation = self.service.validate_expression("x**2 + 1", "sympy")
        self.assertIn('is_valid', validation)

    def test_metadata_none_is_normalized_for_sympy_execution(self):
        """None metadata should be normalized so default sympy execution succeeds."""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="metadata-none-request",
            metadata=None,
        )

        request_id = self.service.submit_request(request)
        result = None
        max_retries = 20
        retry_interval_seconds = 0.1
        for _ in range(max_retries):
            result = self.service.get_result(request_id)
            if result is not None:
                break
            time.sleep(retry_interval_seconds)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ComputeStatus.SUCCESS)

    def test_mutated_unsupported_language_returns_unsupported_status(self):
        """Runtime should guard against unsupported language values even if object is mutated."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="mutated-unsupported-language",
        )
        request.language = "python"

        request_id = self.service.submit_request(request)
        result = None
        max_retries = 20
        retry_interval_seconds = 0.1
        for _ in range(max_retries):
            result = self.service.get_result(request_id)
            if result is not None:
                break
            time.sleep(retry_interval_seconds)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ComputeStatus.UNSUPPORTED)
        self.assertIn("Unsupported language", result.error_message)

    def test_submit_request_unsupported_language_skips_background_worker(self):
        """Unsupported requests should resolve synchronously without worker threads."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="unsupported-sync-request",
        )
        # ComputeRequest validates language at construction time, so mutate after
        # creation to exercise the runtime unsupported-language guard path.
        request.language = "python"

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)
            result = self.service.get_result(request_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.UNSUPPORTED)
            self.assertNotIn(request_id, self.service.pending_requests)
            mock_thread_cls.assert_not_called()

    def test_submit_request_normalizes_supported_language_variant(self):
        """Whitespace/case variants of supported language should normalize preflight."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="supported-language-variant",
        )
        # ComputeRequest validates language at construction time, so mutate after
        # creation to exercise runtime language normalization behavior.
        request.language = "  SyMpY  "

        request_id = self.service.submit_request(request)
        result = self._wait_for_result(request_id)

        self.assertIsNotNone(result)
        self.assertNotEqual(result.status, ComputeStatus.UNSUPPORTED)
        self.assertNotIn(request_id, self.service.pending_requests)

    def test_submit_request_invalid_timeout_skips_background_worker(self):
        """Invalid timeout values should fail preflight without worker threads."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="invalid-timeout-sync-request",
        )
        # ComputeRequest validates timeout at construction time, so mutate after
        # creation to exercise runtime preflight guard behavior.
        request.timeout = "forever"

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)
            result = self.service.get_result(request_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.FAIL)
            self.assertIn("Timeout must be between 1 and 300 seconds", result.error_message)
            self.assertNotIn(request_id, self.service.pending_requests)
            mock_thread_cls.assert_not_called()

    def test_submit_request_invalid_precision_skips_background_worker(self):
        """Invalid precision values should fail preflight without worker threads."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="invalid-precision-sync-request",
        )
        # ComputeRequest validates precision at construction time, so mutate after
        # creation to exercise runtime preflight guard behavior.
        request.precision = "max"

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)
            result = self.service.get_result(request_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.FAIL)
            self.assertIn("Precision must be between 1 and 50", result.error_message)
            self.assertNotIn(request_id, self.service.pending_requests)
            mock_thread_cls.assert_not_called()

    def test_submit_request_invalid_metadata_type_skips_background_worker(self):
        """Invalid metadata container types should fail preflight without worker threads."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="invalid-metadata-sync-request",
        )
        # ComputeRequest defaults metadata to dict, so mutate post-creation to
        # exercise runtime preflight guard behavior.
        request.metadata = "not-a-dict"

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)
            result = self.service.get_result(request_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.FAIL)
            self.assertIn("Metadata must be a dictionary", result.error_message)
            self.assertNotIn(request_id, self.service.pending_requests)
            mock_thread_cls.assert_not_called()

    def test_submit_request_whitespace_expression_skips_background_worker(self):
        """Whitespace-only expressions should fail preflight without worker threads."""
        request = ComputeRequest(
            expression="placeholder",
            language="sympy",
            request_id="invalid-expression-sync-request",
        )
        # ComputeRequest validates expression at construction time, so mutate after
        # creation to exercise runtime preflight guard behavior.
        request.expression = "   "

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)
            result = self.service.get_result(request_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.FAIL)
            self.assertIn("Expression must be a non-empty string", result.error_message)
            self.assertNotIn(request_id, self.service.pending_requests)
            mock_thread_cls.assert_not_called()

    def test_submit_request_whitespace_request_id_generates_fallback_id(self):
        """Whitespace request IDs should be normalized to a generated non-empty ID."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="placeholder-id",
        )
        # ComputeRequest validates request_id at construction time; mutate afterward
        # to exercise runtime preflight normalization behavior.
        request.request_id = "   "

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)

            self.assertIsInstance(request_id, str)
            self.assertNotEqual(request_id, "")
            self.assertNotEqual(request_id, "   ")
            self.assertIn(request_id, self.service.pending_requests)
            mock_thread_cls.assert_called_once()

    def test_submit_request_trims_request_id_whitespace(self):
        """Request IDs with surrounding whitespace should be normalized before pending registration."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="placeholder-id",
        )
        # Mutate after creation to exercise runtime normalization behavior.
        request.request_id = "  spaced-request-id  "

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            request_id = self.service.submit_request(request)

            self.assertEqual(request_id, "spaced-request-id")
            self.assertIn("spaced-request-id", self.service.pending_requests)
            self.assertNotIn("  spaced-request-id  ", self.service.pending_requests)
            mock_thread_cls.assert_called_once()

    def test_submit_request_worker_start_failure_returns_fail_without_pending_leak(self):
        """Worker start failures should return FAIL and clean pending state."""
        request = ComputeRequest(
            expression="x + 1",
            language="sympy",
            request_id="worker-start-failure-request",
        )

        with patch("src.compute_plane.service.threading.Thread") as mock_thread_cls:
            mock_thread = mock_thread_cls.return_value
            mock_thread.start.side_effect = RuntimeError("thread start failed")

            request_id = self.service.submit_request(request)
            result = self.service.get_result(request_id)

            self.assertIsNotNone(result)
            self.assertEqual(result.status, ComputeStatus.FAIL)
            self.assertIn("Failed to start compute worker", result.error_message)
            self.assertNotIn(request_id, self.service.pending_requests)

    def test_get_statistics(self):
        """Test getting service statistics"""
        stats = self.service.get_statistics()
        self.assertIn('total_requests', stats)
        self.assertIn('success_rate', stats)


class TestComputePlaneIntegration(unittest.TestCase):
    """Integration tests for complete compute plane"""

    def setUp(self):
        self.service = ComputeService(enable_caching=True)

    def test_end_to_end_symbolic(self):
        """Test end-to-end symbolic computation"""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        # Submit request
        request = ComputeRequest(
            expression="(x + 1)**2",
            language="sympy",
            assumptions={'x': 'real'},
            metadata={'operation': 'expand'}
        )

        request_id = self.service.submit_request(request)

        # Wait for result
        time.sleep(1)

        # Get result
        result = self.service.get_result(request_id)

        # Verify result
        self.assertEqual(result.status, ComputeStatus.SUCCESS)
        self.assertIsNotNone(result.result)
        self.assertGreater(len(result.derivation_steps), 0)
        self.assertGreater(result.confidence_score, 0.0)
        self.assertGreater(result.stability_estimate, 0.0)

    def test_end_to_end_with_sensitivity(self):
        """Test end-to-end with sensitivity analysis"""
        if not self.service.parser.sympy_available:
            self.skipTest("SymPy not available")

        # Submit request with base point for sensitivity
        request = ComputeRequest(
            expression="x**2 + y",
            language="sympy",
            assumptions={'x': 'real', 'y': 'real'},
            metadata={
                'operation': 'simplify',
                'base_point': {'x': 2.0, 'y': 1.0}
            }
        )

        request_id = self.service.submit_request(request)

        # Wait for result
        time.sleep(1)

        # Get result
        result = self.service.get_result(request_id)

        # Verify sensitivity analysis
        self.assertEqual(result.status, ComputeStatus.SUCCESS)
        self.assertGreater(len(result.sensitivity_to_assumptions), 0)


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
