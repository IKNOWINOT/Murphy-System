"""
Compute Service

Main service that orchestrates computation requests.
"""

import json
import time
import threading
import uuid
from copy import deepcopy
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, Optional
from queue import Queue
from .models.compute_request import ComputeRequest
from .models.compute_result import ComputeResult, ComputeStatus
from .parsers.expression_parser import ExpressionParser
from .solvers.symbolic_solver import SymbolicSolver
from .solvers.numeric_solver import NumericSolver
from .analyzers.determinism_analyzer import DeterminismAnalyzer


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
        if not isinstance(request.assumptions, dict) or not isinstance(request.metadata, dict):
            request = replace(
                request,
                assumptions=request.assumptions if isinstance(request.assumptions, dict) else {},
                metadata=request.metadata if isinstance(request.metadata, dict) else {},
            )

        request_signature = self._request_signature(request)

        with self._lock:
            if self._is_shutdown:
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.FAIL,
                    error_message="Compute service has been shut down"
                )
                self.request_cache[request.request_id] = result
                self.request_signatures[request.request_id] = request_signature
                return request.request_id

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
            
            # Store as pending
            self.pending_requests[request.request_id] = request
            self.request_signatures[request.request_id] = request_signature
            
            # Start computation in background
            thread = threading.Thread(target=self._process_request, args=(request,))
            thread.daemon = True
            thread.start()
            
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
                future.cancel()
                result = ComputeResult(
                    request_id=request.request_id,
                    status=ComputeStatus.TIMEOUT,
                    error_message=f"Computation timed out after {request.timeout} seconds"
                )

            result.execution_time = time.time() - start_time
            
        except Exception as e:
            result = ComputeResult(
                request_id=request.request_id,
                status=ComputeStatus.FAIL,
                error_message=str(e),
                execution_time=time.time() - start_time
            )
        
        # Store result
        with self._lock:
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
        """Execute linear programming (placeholder)"""
        return ComputeResult(
            request_id=request.request_id,
            status=ComputeStatus.UNSUPPORTED,
            error_message="LP solver not integrated"
        )
    
    def _execute_sat(self, request: ComputeRequest, normalized) -> ComputeResult:
        """Execute SAT solving (placeholder)"""
        return ComputeResult(
            request_id=request.request_id,
            status=ComputeStatus.UNSUPPORTED,
            error_message="SAT solver not integrated"
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

    def shutdown(self):
        """Shutdown service resources."""
        with self._lock:
            self._is_shutdown = True
            self._execution_executor.shutdown(wait=False, cancel_futures=True)

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass
