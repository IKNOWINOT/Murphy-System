"""
Numeric Solver

Executes numeric computations with bounds and sensitivity analysis.
"""

import logging
import math
import time
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


class NumericSolver:
    """
    Execute numeric computations with precision control.

    Supports:
    - Numeric evaluation
    - Bounds computation
    - Sensitivity analysis
    - Error estimation
    """

    def __init__(self):
        """Initialize numeric solver"""
        self.sympy_available = False
        try:
            import sympy
            self.sympy = sympy
            self.sympy_available = True
        except ImportError:
            pass

    def evaluate(self, normalized_expr, precision: int = 10, substitutions: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Evaluate expression numerically with specified precision.

        Args:
            normalized_expr: NormalizedExpression object
            precision: Decimal places of precision
            substitutions: Variable substitutions {var: value}

        Returns:
            Dictionary with result and metadata
        """
        if not self.sympy_available:
            raise RuntimeError("SymPy not available for numeric evaluation")

        start_time = time.time()
        substitutions = substitutions or {}

        try:
            expr = normalized_expr.normalized

            # Check if all variables have substitutions
            free_symbols = expr.free_symbols
            missing_vars = [str(s) for s in free_symbols if str(s) not in substitutions]

            if missing_vars:
                return {
                    'result': None,
                    'error': f"Missing substitutions for variables: {missing_vars}",
                    'execution_time': time.time() - start_time
                }

            # Substitute variables
            subs_dict = {self.sympy.Symbol(k): v for k, v in substitutions.items()}
            evaluated = expr.subs(subs_dict)

            # Convert to float with precision
            result = float(evaluated.evalf(precision))

            execution_time = time.time() - start_time

            return {
                'result': result,
                'precision': precision,
                'substitutions': substitutions,
                'execution_time': execution_time,
                'error': None
            }

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                'result': None,
                'error': str(exc),
                'execution_time': time.time() - start_time
            }

    def compute_bounds(self, normalized_expr, variable_ranges: Dict[str, Tuple[float, float]]) -> Tuple[float, float]:
        """
        Compute numeric bounds for expression over variable ranges.

        Args:
            normalized_expr: NormalizedExpression object
            variable_ranges: Ranges for each variable {var: (min, max)}

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if not self.sympy_available:
            return (float('-inf'), float('inf'))

        try:
            expr = normalized_expr.normalized

            # Sample points in variable ranges
            sample_points = self._generate_sample_points(variable_ranges, num_samples=100)

            # Evaluate at each sample point
            values = []
            for point in sample_points:
                result = self.evaluate(normalized_expr, substitutions=point)
                if result['result'] is not None:
                    values.append(result['result'])

            if not values:
                return (float('-inf'), float('inf'))

            # Return min and max
            return (min(values), max(values))

        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return (float('-inf'), float('inf'))

    def sensitivity_analysis(self, normalized_expr, base_point: Dict[str, float], perturbation: float = 0.01) -> Dict[str, float]:
        """
        Analyze sensitivity to each variable.

        Args:
            normalized_expr: NormalizedExpression object
            base_point: Base point for evaluation {var: value}
            perturbation: Perturbation size (relative)

        Returns:
            Dictionary of sensitivities {var: sensitivity}
        """
        if not self.sympy_available:
            return {}

        sensitivities = {}

        try:
            # Evaluate at base point
            base_result = self.evaluate(normalized_expr, substitutions=base_point)
            if base_result['result'] is None:
                return {}

            base_value = base_result['result']

            # Perturb each variable and measure change
            for var, value in base_point.items():
                # Perturb up
                perturbed_point = base_point.copy()
                perturbed_point[var] = value * (1 + perturbation)

                perturbed_result = self.evaluate(normalized_expr, substitutions=perturbed_point)
                if perturbed_result['result'] is not None:
                    # Compute relative sensitivity
                    delta_output = abs(perturbed_result['result'] - base_value)
                    delta_input = abs(value * perturbation)

                    if delta_input > 0:
                        sensitivity = delta_output / delta_input
                    else:
                        sensitivity = 0.0

                    sensitivities[var] = sensitivity

        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            pass

        return sensitivities

    def estimate_error(self, result: float, precision: int) -> float:
        """
        Estimate numeric error based on precision.

        Args:
            result: Computed result
            precision: Precision used

        Returns:
            Estimated error bound
        """
        # Error is approximately 10^(-precision)
        error = 10 ** (-precision)

        # Scale by magnitude of result
        if abs(result) > 1:
            error *= abs(result)

        return error

    def _generate_sample_points(self, variable_ranges: Dict[str, Tuple[float, float]], num_samples: int = 100) -> list:
        """Generate sample points in variable ranges"""
        import random

        sample_points = []

        for _ in range(num_samples):
            point = {}
            for var, (min_val, max_val) in variable_ranges.items():
                point[var] = random.uniform(min_val, max_val)
            sample_points.append(point)

        return sample_points
