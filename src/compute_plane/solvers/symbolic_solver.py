"""
Symbolic Solver

Executes symbolic computations with cross-validation support.
"""

import logging

logger = logging.getLogger(__name__)
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SymbolicResult:
    """Result of symbolic computation"""
    result: Any
    derivation_steps: List[str]
    solver: str
    execution_time: float
    metadata: Dict[str, Any]


class SymbolicSolver:
    """
    Execute symbolic computations using SymPy (and optionally Wolfram).

    Supports:
    - Symbolic integration
    - Symbolic differentiation
    - Equation solving
    - Simplification
    - Expansion
    - Factorization
    """

    def __init__(self):
        """Initialize symbolic solver"""
        self.sympy_available = False
        try:
            import sympy
            self.sympy = sympy
            self.sympy_available = True
        except ImportError:
            pass

    def solve_sympy(self, normalized_expr, operation: str = "simplify") -> SymbolicResult:
        """
        Solve using SymPy.

        Args:
            normalized_expr: NormalizedExpression object
            operation: Operation to perform (simplify, integrate, diff, solve, etc.)

        Returns:
            SymbolicResult with result and derivation steps
        """
        if not self.sympy_available:
            raise RuntimeError("SymPy not available. Install with: pip install sympy")

        start_time = time.time()
        derivation_steps = []

        expr = normalized_expr.normalized
        derivation_steps.append(f"Input: {expr}")

        try:
            if operation == "simplify":
                result = self.sympy.simplify(expr)
                derivation_steps.append(f"Simplified: {result}")

            elif operation == "expand":
                result = self.sympy.expand(expr)
                derivation_steps.append(f"Expanded: {result}")

            elif operation == "factor":
                result = self.sympy.factor(expr)
                derivation_steps.append(f"Factored: {result}")

            elif operation.startswith("integrate"):
                # Extract variable if specified
                var = self._extract_variable(operation, normalized_expr)
                result = self.sympy.integrate(expr, var)
                derivation_steps.append(f"Integrated with respect to {var}: {result}")

            elif operation.startswith("diff"):
                # Extract variable if specified
                var = self._extract_variable(operation, normalized_expr)
                result = self.sympy.diff(expr, var)
                derivation_steps.append(f"Differentiated with respect to {var}: {result}")

            elif operation.startswith("solve"):
                # Extract variable if specified
                var = self._extract_variable(operation, normalized_expr)
                result = self.sympy.solve(expr, var)
                derivation_steps.append(f"Solved for {var}: {result}")

            else:
                # Default to simplify
                result = self.sympy.simplify(expr)
                derivation_steps.append(f"Simplified: {result}")

            execution_time = time.time() - start_time

            return SymbolicResult(
                result=result,
                derivation_steps=derivation_steps,
                solver="sympy",
                execution_time=execution_time,
                metadata={'operation': operation}
            )

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            execution_time = time.time() - start_time
            derivation_steps.append(f"Error: {exc}")

            return SymbolicResult(
                result=None,
                derivation_steps=derivation_steps,
                solver="sympy",
                execution_time=execution_time,
                metadata={'operation': operation, 'error': str(exc)}
            )

    def solve_wolfram(self, normalized_expr, operation: str = "simplify") -> SymbolicResult:
        """
        Solve using Wolfram Engine (placeholder - requires Wolfram Engine installation).

        Args:
            normalized_expr: NormalizedExpression object
            operation: Operation to perform

        Returns:
            SymbolicResult (currently returns unsupported)
        """
        # Wolfram Engine integration deferred; returns unsupported result
        return SymbolicResult(
            result=None,
            derivation_steps=["Wolfram Engine not integrated"],
            solver="wolfram",
            execution_time=0.0,
            metadata={'operation': operation, 'note': 'Wolfram Engine not available'}
        )

    def cross_validate(self, result1: SymbolicResult, result2: SymbolicResult, tolerance: float = 1e-10) -> Dict[str, Any]:
        """
        Compare two solver results for cross-validation.

        Args:
            result1: First solver result
            result2: Second solver result
            tolerance: Numeric tolerance for comparison

        Returns:
            Validation result with agreement status
        """
        validation = {
            'agrees': False,
            'difference': None,
            'confidence': 0.0,
            'notes': []
        }

        # Check if both succeeded
        if result1.result is None or result2.result is None:
            validation['notes'].append("One or both solvers failed")
            return validation

        # Try to compare symbolically
        try:
            if self.sympy_available:
                diff = self.sympy.simplify(result1.result - result2.result)

                if diff == 0:
                    validation['agrees'] = True
                    validation['confidence'] = 1.0
                    validation['notes'].append("Exact symbolic agreement")
                else:
                    # Try numeric comparison
                    try:
                        numeric_diff = float(abs(diff))
                        if numeric_diff < tolerance:
                            validation['agrees'] = True
                            validation['confidence'] = 0.95
                            validation['difference'] = numeric_diff
                            validation['notes'].append(f"Numeric agreement within tolerance: {numeric_diff}")
                        else:
                            validation['difference'] = numeric_diff
                            validation['notes'].append(f"Results differ by: {numeric_diff}")
                    except Exception as exc:
                        logger.debug("Suppressed exception: %s", exc)
                        validation['notes'].append(f"Results differ symbolically: {diff}")

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            validation['notes'].append(f"Comparison failed: {exc}")

        return validation

    def _extract_variable(self, operation: str, normalized_expr) -> Any:
        """Extract variable from operation string or use first variable"""
        # Check if variable specified in operation (e.g., "integrate:x")
        if ':' in operation:
            var_name = operation.split(':')[1].strip()
            if self.sympy_available:
                return self.sympy.Symbol(var_name)

        # Use first variable from expression
        if normalized_expr.variables:
            var_name = list(normalized_expr.variables)[0]
            if self.sympy_available:
                return self.sympy.Symbol(var_name)

        # Default to 'x'
        if self.sympy_available:
            return self.sympy.Symbol('x')

        return 'x'
