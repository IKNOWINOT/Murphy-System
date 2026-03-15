"""
Determinism Analyzer

Analyzes determinism properties of computation results.
"""

import logging
import math
from typing import Any, Dict

logger = logging.getLogger(__name__)


class DeterminismAnalyzer:
    """
    Analyze determinism properties of computation results.

    Computes:
    - Stability estimate (how stable is result to input perturbations)
    - Sensitivity to assumptions (which assumptions matter most)
    - Overall confidence in result
    """

    def compute_stability(self, result: Any, sensitivity: Dict[str, float] = None) -> float:
        """
        Estimate result stability.

        Stability is high when:
        - Result is not sensitive to input perturbations
        - Result is well-defined (not near singularities)
        - Result is reproducible

        Args:
            result: Computation result
            sensitivity: Sensitivity analysis results

        Returns:
            Stability estimate (0.0 to 1.0)
        """
        sensitivity = sensitivity or {}

        # Start with high stability
        stability = 1.0

        # Check if result is numeric
        if result is None:
            return 0.0

        try:
            numeric_result = float(result)

            # Penalize for extreme values
            if abs(numeric_result) > 1e10:
                stability *= 0.5

            # Penalize for very small values (near zero)
            if abs(numeric_result) < 1e-10:
                stability *= 0.7

            # Penalize for NaN or Inf
            if math.isnan(numeric_result) or math.isinf(numeric_result):
                return 0.0

        except (ValueError, TypeError):
            # Non-numeric result - moderate stability
            stability *= 0.8

        # Factor in sensitivity
        if sensitivity:
            avg_sensitivity = sum(sensitivity.values()) / (len(sensitivity) or 1)

            # High sensitivity reduces stability
            if avg_sensitivity > 10:
                stability *= 0.3
            elif avg_sensitivity > 1:
                stability *= 0.6
            elif avg_sensitivity > 0.1:
                stability *= 0.8

        return max(0.0, min(1.0, stability))

    def compute_sensitivity(self, sensitivity_analysis: Dict[str, float], assumptions: Dict[str, Any]) -> Dict[str, float]:
        """
        Compute sensitivity to each assumption.

        Args:
            sensitivity_analysis: Sensitivity to each variable
            assumptions: Assumptions about variables

        Returns:
            Dictionary of sensitivities {assumption: sensitivity}
        """
        sensitivities = {}

        # Map variables to assumptions
        for var, sensitivity in sensitivity_analysis.items():
            if var in assumptions:
                # Normalize sensitivity to 0-1 range
                normalized = min(1.0, sensitivity / 10.0)
                sensitivities[var] = normalized

        return sensitivities

    def compute_confidence(self, result: Any, stability: float, cross_validation: Dict[str, Any] = None) -> float:
        """
        Compute overall confidence in result.

        Confidence is high when:
        - Result is stable
        - Cross-validation agrees (if available)
        - No errors occurred

        Args:
            result: Computation result
            stability: Stability estimate
            cross_validation: Cross-validation results (if available)

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # Start with stability
        confidence = stability

        # Check if result exists
        if result is None:
            return 0.0

        # Factor in cross-validation
        if cross_validation:
            if cross_validation.get('agrees', False):
                # Boost confidence if cross-validation agrees
                cv_confidence = cross_validation.get('confidence', 0.5)
                confidence = (confidence + cv_confidence) / 2
            else:
                # Reduce confidence if cross-validation disagrees
                confidence *= 0.5

        return max(0.0, min(1.0, confidence))

    def analyze_result(self, result: Any, sensitivity: Dict[str, float] = None,
                      cross_validation: Dict[str, Any] = None,
                      assumptions: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Complete determinism analysis of result.

        Args:
            result: Computation result
            sensitivity: Sensitivity analysis
            cross_validation: Cross-validation results
            assumptions: Assumptions used

        Returns:
            Complete analysis with stability, sensitivity, and confidence
        """
        sensitivity = sensitivity or {}
        assumptions = assumptions or {}

        # Compute stability
        stability = self.compute_stability(result, sensitivity)

        # Compute sensitivity to assumptions
        assumption_sensitivity = self.compute_sensitivity(sensitivity, assumptions)

        # Compute confidence
        confidence = self.compute_confidence(result, stability, cross_validation)

        return {
            'stability_estimate': stability,
            'sensitivity_to_assumptions': assumption_sensitivity,
            'confidence_score': confidence,
            'is_deterministic': stability > 0.8 and confidence > 0.8,
            'metadata': {
                'avg_sensitivity': sum(sensitivity.values()) / len(sensitivity) if sensitivity else 0.0,
                'num_assumptions': len(assumptions),
                'cross_validated': cross_validation is not None
            }
        }
