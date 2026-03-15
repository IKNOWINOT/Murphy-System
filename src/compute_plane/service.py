"""
Compute Service

Main service that orchestrates computation requests.
"""

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from copy import deepcopy
from dataclasses import replace
from queue import Queue
from typing import Dict, Optional

from .analyzers.determinism_analyzer import DeterminismAnalyzer
from .models.compute_request import ComputeRequest
from .models.compute_result import ComputeResult, ComputeStatus
from .parsers.expression_parser import ExpressionParser
from .solvers.numeric_solver import NumericSolver
from .solvers.symbolic_solver import SymbolicSolver

logger = logging.getLogger(__name__)


class ComputeService:
    """
    Main compute verification service.

    This service:
    - Accepts computation requests
    - Parses and validates expressions
    - Executes computations with timeout
    - Performs cross-validation
    - Analyzes determinism
    - Returns verified results

    This is a READ-ONLY verification oracle that:
    - Does NOT modify system state
    - Does NOT invoke execution plane
    - Does NOT call external APIs
    - Only returns verified results
    """

    SUPPORTED_LANGUAGES = set(ComputeRequest.SUPPORTED_LANGUAGES)
    MIN_TIMEOUT = 1
    MAX_TIMEOUT = 300
    MIN_PRECISION = 1
    MAX_PRECISION = 50

    def __init__(self, enable_caching: bool = True):
        """
        Initialize compute service.

        Args:
            enable_caching: Whether to cache results
        """
        self.parser = ExpressionParser()
        self.symbolic_solver = SymbolicSolver()
        self.numeric_solver = NumericSolver()
        self.determinism_analyzer = DeterminismAnalyzer()

        self.enable_caching = enable_caching
        self.request_cache: Dict[str, ComputeResult] = {}
        self.pending_requests: Dict[str, ComputeRequest] = {}
        self.request_signatures: Dict[str, str] = {}
        self._is_shutdown = False
        self._execution_executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="compute-service"
        )

        self._lock = threading.Lock()

    def submit_request(self, request: ComputeRequest) -> str:
        """
        Submit computation request.

        Args:
            request: ComputeRequest object

        Returns:
            request_id for tracking
        """
        if not isinstance(request.request_id, str):
            request = replace(request, request_id=str(uuid.uuid4()))
        else:
            normalized_request_id = request.request_id.strip()
            if not normalized_request_id:
                request = replace(request, request_id=str(uuid.uuid4()))
            elif normalized_request_id != request.request_id:
                request = replace(request, request_id=normalized_request_id)
        if isinstance(request.language, str):
            normalized_language = request.language.strip().lower()
            if normalized_language != request.language:
                request = replace(request, language=normalized_language)
        # Normalize None container fields to empty dicts so downstream code
        # (validation, metadata.get(), deepcopy) never encounters None.
        if request.assumptions is None:
            request = replace(request, assumptions={})
        if request.metadata is None:
            request = replace(request, metadata={})
        request_signature = self._request_signature(request)

        with self._lock:
            if self._is_shutdown:
                if request.request_id in self.request_cache:
                    existing_signature = self.request_signatures.get(request.request_id)
                    existing_result = self.request_cache.get(request.request_id)
                    if (
                        existing_signature == request_signature
                        and existing_result is not None
                    ):
                        return request.request_id
                    # Preserve existing cache entry by suffixing conflicting IDs during shutdown.
                    request = replace(
                        request,
                        request_id=f"{request.request_id}-{uuid.uuid4().hex[:8]}"
                    )
                    request_signature = self._request_signature(request)
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.FAIL,
                    error_message="Compute service has been shut down"
                )
                self.request_cache[request.request_id] = result
                self.request_signatures[request.request_id] = request_signature
                return request.request_id

            if not self.enable_caching and request.request_id in self.request_cache:
                self.request_cache.pop(request.request_id, None)
                self.request_signatures.pop(request.request_id, None)

            # Check cache
            if self.enable_caching and request.request_id in self.request_cache:
                if self.request_signatures.get(request.request_id) == request_signature:
                    return request.request_id
                request = replace(
                    request,
                    request_id=f"{request.request_id}-{uuid.uuid4().hex[:8]}"
                )
                request_signature = self._request_signature(request)

            # Avoid duplicate processing for pending requests
            if request.request_id in self.pending_requests:
                if self.request_signatures.get(request.request_id) == request_signature:
                    return request.request_id
                request = replace(
                    request,
                    request_id=f"{request.request_id}-{uuid.uuid4().hex[:8]}"
                )
                request_signature = self._request_signature(request)

            if request.language not in self.SUPPORTED_LANGUAGES:
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.UNSUPPORTED,
                    error_message=f"Unsupported language: {request.language}",
                )
                self.request_cache[request.request_id] = result
                self.request_signatures[request.request_id] = request_signature
                return request.request_id

            # Preflight returns on the first invalid container field so callers
            # can fix issues incrementally with deterministic error semantics.
            # Validation order is intentional: assumptions are checked first,
            # then metadata, to keep error messaging stable.
            for value, error_message in (
                (request.assumptions, "Assumptions must be a dictionary"),
                (request.metadata, "Metadata must be a dictionary"),
            ):
                if not isinstance(value, dict):
                    result = ComputeResult(
                        request_id=request.request_id,
                        status=ComputeStatus.FAIL,
                        error_message=error_message,
                    )
                    self.request_cache[request.request_id] = result
                    self.request_signatures[request.request_id] = request_signature
                    return request.request_id

            if (
                not isinstance(request.expression, str)
                or not request.expression
                or not request.expression.strip()
            ):
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.FAIL,
                    error_message="Expression must be a non-empty string",
                )
                self.request_cache[request.request_id] = result
                self.request_signatures[request.request_id] = request_signature
                return request.request_id

            if not self._validate_numeric_range(request.timeout, self.MIN_TIMEOUT, self.MAX_TIMEOUT):
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.FAIL,
                    error_message=f"Timeout must be between {self.MIN_TIMEOUT} and {self.MAX_TIMEOUT} seconds",
                )
                self.request_cache[request.request_id] = result
                self.request_signatures[request.request_id] = request_signature
                return request.request_id

            if not self._validate_numeric_range(
                request.precision, self.MIN_PRECISION, self.MAX_PRECISION, allow_float=False
            ):
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.FAIL,
                    error_message=f"Precision must be between {self.MIN_PRECISION} and {self.MAX_PRECISION}",
                )
                self.request_cache[request.request_id] = result
                self.request_signatures[request.request_id] = request_signature
                return request.request_id

            # Snapshot request to avoid caller-side mutations affecting background execution.
            request_for_processing = replace(
                request,
                assumptions=deepcopy(request.assumptions),
                metadata=deepcopy(request.metadata),
            )

            # Store as pending
            self.pending_requests[request.request_id] = request_for_processing
            self.request_signatures[request.request_id] = request_signature

            # Start computation in background
            thread = threading.Thread(target=self._process_request, args=(request_for_processing,))
            thread.daemon = True
            try:
                thread.start()
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                self.pending_requests.pop(request.request_id, None)
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.FAIL,
                    error_message=f"Failed to start compute worker: {exc}",
                )
                self.request_cache[request.request_id] = result
                self.request_signatures[request.request_id] = request_signature

            return request.request_id

    def get_result(self, request_id: str) -> Optional[ComputeResult]:
        """
        Get computation result.

        Args:
            request_id: Request ID

        Returns:
            ComputeResult if available, None if still pending
        """
        with self._lock:
            result = self.request_cache.get(request_id)
            return deepcopy(result) if result is not None else None

    def validate_expression(self, expression: str, language: str) -> Dict:
        """
        Validate expression syntax.

        Args:
            expression: Expression string
            language: Language to validate

        Returns:
            Validation result dictionary
        """
        validation = self.parser.validate_syntax(expression, language)
        return validation.to_dict()

    def _process_request(self, request: ComputeRequest):
        """
        Process computation request (runs in background thread).

        Args:
            request: ComputeRequest object
        """
        start_time = time.time()
        if request.language not in self.SUPPORTED_LANGUAGES:
            result = ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.UNSUPPORTED,
                error_message=f"Unsupported language: {request.language}",
                execution_time=time.time() - start_time,
            )
            with self._lock:
                if not (self._is_shutdown and request.request_id in self.request_cache):
                    self.request_cache[request.request_id] = result
                if request.request_id in self.pending_requests:
                    del self.pending_requests[request.request_id]
            return

        try:
            # Parse expression
            parsed = self.parser.parse(
                request.expression,
                request.language,
                request.assumptions
            )

            # Normalize expression
            normalized = self.parser.normalize(parsed)

            def run_computation():
                # Execute computation based on language
                if request.language == "sympy":
                    return self._execute_sympy(request, normalized)
                elif request.language == "wolfram":
                    return self._execute_wolfram(request, normalized)
                elif request.language == "lp":
                    return self._execute_lp(request, normalized)
                elif request.language == "sat":
                    return self._execute_sat(request, normalized)
                return ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.UNSUPPORTED,
                    error_message=f"Unsupported language: {request.language}"
                )

            future = self._execution_executor.submit(run_computation)
            try:
                result = future.result(timeout=request.timeout)
            except FuturesTimeoutError:
                cancelled = future.cancel()
                # If the future was successfully cancelled it means the
                # executor never dispatched it (e.g. threads unavailable).
                # Fall back to direct, synchronous execution.
                if cancelled:
                    result = self._run_fallback_computation(
                        run_computation, request
                    )
                else:
                    result = ComputeResult(
                        request_id=request.request_id,
                        status=ComputeStatus.TIMEOUT,
                        error_message=f"Computation timed out after {request.timeout} seconds"
                    )

            result.execution_time = time.time() - start_time

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            result = ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.FAIL,
                error_message=str(exc),
                execution_time=time.time() - start_time
            )

        # Store result
        with self._lock:
            if not (self._is_shutdown and request.request_id in self.request_cache):
                self.request_cache[request.request_id] = result
            if request.request_id in self.pending_requests:
                del self.pending_requests[request.request_id]

    def _execute_sympy(self, request: ComputeRequest, normalized) -> ComputeResult:
        """Execute SymPy computation"""
        # Determine operation from metadata
        operation = request.metadata.get('operation', 'simplify')

        # Solve symbolically
        symbolic_result = self.symbolic_solver.solve_sympy(normalized, operation)

        if symbolic_result.result is None:
            return ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.FAIL,
                error_message=symbolic_result.metadata.get('error', 'Symbolic computation failed'),
                derivation_steps=symbolic_result.derivation_steps
            )

        # Compute numeric bounds if possible
        numeric_bounds = (float('-inf'), float('inf'))
        sensitivity = {}

        if request.metadata.get('compute_bounds') and request.metadata.get('variable_ranges'):
            numeric_bounds = self.numeric_solver.compute_bounds(
                normalized,
                request.metadata['variable_ranges']
            )

        # Sensitivity analysis if base point provided
        if request.metadata.get('base_point'):
            sensitivity = self.numeric_solver.sensitivity_analysis(
                normalized,
                request.metadata['base_point']
            )

        # Analyze determinism
        analysis = self.determinism_analyzer.analyze_result(
            symbolic_result.result,
            sensitivity=sensitivity,
            assumptions=request.assumptions
        )

        return ComputeResult(
            request_id=request.request_id,
            status=ComputeStatus.SUCCESS,
            result=symbolic_result.result,
            derivation_steps=symbolic_result.derivation_steps,
            numeric_bounds=numeric_bounds,
            confidence_score=analysis['confidence_score'],
            stability_estimate=analysis['stability_estimate'],
            sensitivity_to_assumptions=analysis['sensitivity_to_assumptions'],
            metadata=analysis['metadata']
        )

    def _execute_wolfram(self, request: ComputeRequest, normalized) -> ComputeResult:
        """Execute Wolfram computation (placeholder)"""
        return ComputeResult(
            request_id=request.request_id,
            status=ComputeStatus.UNSUPPORTED,
            error_message="Wolfram Engine not integrated"
        )

    def _execute_lp(self, request: ComputeRequest, normalized) -> ComputeResult:
        """Execute linear programming using scipy.optimize.linprog.

        Parses a simple LP problem from the request expression.
        The expression metadata should contain:
          - ``c``: objective coefficients (list of floats)
          - ``A_ub``: inequality constraint matrix (list of lists)
          - ``b_ub``: inequality constraint bounds (list of floats)
          - ``bounds``: variable bounds (list of (min, max) tuples), optional

        Falls back to UNSUPPORTED when scipy is not installed or the
        metadata is missing required LP parameters.
        """
        try:
            from scipy.optimize import linprog  # type: ignore[import]
        except ImportError:
            return ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.UNSUPPORTED,
                error_message=(
                    "LP solver requires scipy. Install with: pip install scipy"
                ),
            )

        meta = request.metadata or {}
        c = meta.get("c")
        if c is None:
            return ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.UNSUPPORTED,
                error_message=(
                    "LP solver requires 'c' (objective coefficients) in request.metadata. "
                    "Optionally include 'A_ub', 'b_ub', and 'bounds'."
                ),
            )

        try:
            result = linprog(
                c,
                A_ub=meta.get("A_ub"),
                b_ub=meta.get("b_ub"),
                A_eq=meta.get("A_eq"),
                b_eq=meta.get("b_eq"),
                bounds=meta.get("bounds"),
                method=meta.get("method", "highs"),
            )
            if result.success:
                return ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.SUCCESS,
                    result={"x": result.x.tolist(), "fun": float(result.fun)},
                    metadata={"message": result.message, "nit": result.nit},
                )
            return ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.FAIL,
                error_message=f"LP solver failed: {result.message}",
            )
        except Exception as exc:
            return ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.FAIL,
                error_message=f"LP solver error: {exc}",
            )

    def _execute_sat(self, request: ComputeRequest, normalized) -> ComputeResult:
        """SAT solving — planned but not yet implemented.

        .. note::
            SAT solving is on the capability roadmap.  A suitable solver
            (e.g. python-sat, pysat) will be wired in a future release.
            See ``src/capability_map.py`` for current status.
        """
        return ComputeResult(
            request_id=request.request_id,
            status=ComputeStatus.UNSUPPORTED,
            error_message=(
                "SAT solver is planned but not yet integrated. "
                "See capability_map for roadmap status."
            ),
        )

    def get_statistics(self) -> Dict:
        """Get service statistics"""
        with self._lock:
            return {
                'total_requests': len(self.request_cache) + len(self.pending_requests),
                'completed': len(self.request_cache),
                'pending': len(self.pending_requests),
                'cache_enabled': self.enable_caching,
                'success_rate': self._compute_success_rate()
            }

    def _run_fallback_computation(self, run_computation, request) -> "ComputeResult":
        """Execute computation synchronously as a fallback after timeout cancellation."""
        try:
            fallback_start = time.time()
            result = run_computation()
            if time.time() - fallback_start > request.timeout:
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.TIMEOUT,
                    error_message=f"Computation timed out after {request.timeout} seconds"
                )
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            result = ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.FAIL,
                error_message=str(exc),
            )
        return result

    def _compute_success_rate(self) -> float:
        """Compute success rate of completed requests"""
        if not self.request_cache:
            return 0.0

        successful = sum(1 for r in self.request_cache.values() if r.status == ComputeStatus.SUCCESS)
        return successful / len(self.request_cache)

    def _request_signature(self, request: ComputeRequest) -> str:
        """Create stable signature for request identity and cache safety."""
        return json.dumps(
            {
                "expression": request.expression,
                "language": request.language,
                "precision": request.precision,
                "timeout": request.timeout,
                "assumptions": request.assumptions,
                "metadata": request.metadata,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @staticmethod
    def _validate_numeric_range(value, min_value: float, max_value: float, allow_float: bool = True) -> bool:
        """Validate numeric range while excluding booleans."""
        if allow_float:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
        else:
            if not isinstance(value, int) or isinstance(value, bool):
                return False
        return min_value <= value <= max_value

    def shutdown(self):
        """Shutdown service resources."""
        with self._lock:
            self._is_shutdown = True
            for request_id in list(self.pending_requests.keys()):
                if request_id not in self.request_cache:
                    self.request_cache[request_id] = ComputeResult(
                        request_id=request_id,
                        status=ComputeStatus.FAIL,
                        error_message="Compute service has been shut down",
                    )
            self.pending_requests.clear()
            self._execution_executor.shutdown(wait=False, cancel_futures=True)

    def close(self) -> None:
        """Release resources. Prefer using as a context manager."""
        try:
            self.shutdown()
        except Exception as exc:
            logger.debug("Suppressed: %s", exc)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
