"""
Unified Confidence Engine

Integrates the original G/D/H confidence calculation with the new
UD/UA/UI/UR/UG uncertainty calculations and Murphy Gate validation.

This is the main integration point between the original murphy_runtime_analysis
confidence system and the new Murphy validation system.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

# Import original confidence system
try:
    from .confidence_calculator import ConfidenceCalculator
    HAS_ORIGINAL_CALCULATOR = True
except ImportError:
    HAS_ORIGINAL_CALCULATOR = False
    logging.warning("Original ConfidenceCalculator not found")

try:
    from .phase_controller import PhaseController
    HAS_PHASE_CONTROLLER = True
except ImportError:
    HAS_PHASE_CONTROLLER = False
    logging.warning("Original PhaseController not found")

# Import new Murphy validation system
from .murphy_gate import MurphyGate
from .murphy_models import ConfidenceReport, GateResult, UncertaintyScores
from .uncertainty_calculator import UncertaintyCalculator

logger = logging.getLogger(__name__)


class UnifiedConfidenceEngine:
    """
    Unified Confidence Engine

    Combines:
    1. Original G/D/H confidence calculation (Goodness/Domain/Hazard)
    2. New UD/UA/UI/UR/UG uncertainty calculation
    3. Murphy Gate threshold-based validation

    This provides a comprehensive confidence assessment that uses both
    the original proven approach and the new enhanced uncertainty analysis.
    """

    def __init__(self):
        """Initialize unified confidence engine"""

        # Original system components
        if HAS_ORIGINAL_CALCULATOR:
            self.confidence_calculator = ConfidenceCalculator()
            logger.info("Loaded original ConfidenceCalculator (G/D/H)")
        else:
            self.confidence_calculator = None
            logger.warning("Original ConfidenceCalculator not available")

        if HAS_PHASE_CONTROLLER:
            self.phase_controller = PhaseController()
            logger.info("Loaded original PhaseController")
        else:
            self.phase_controller = None
            logger.warning("Original PhaseController not available")

        # New Murphy validation components
        self.uncertainty_calculator = UncertaintyCalculator()
        self.murphy_gate = MurphyGate()

        # Configuration
        self.weights = {
            'gdh': 0.5,  # Weight for original G/D/H score
            'uncertainty': 0.5  # Weight for new uncertainty score
        }

        logger.info("UnifiedConfidenceEngine initialized")

    def calculate_confidence(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ConfidenceReport:
        """
        Calculate unified confidence score

        Args:
            task: Task to evaluate
            context: Additional context (optional)

        Returns:
            ConfidenceReport with combined scores and gate decision
        """

        # Calculate original G/D/H confidence if available
        gdh_confidence = None
        if self.confidence_calculator:
            try:
                gdh_confidence = self.confidence_calculator.calculate(task)
                logger.debug(f"G/D/H confidence: {gdh_confidence}")
            except Exception as exc:
                logger.error(f"Error calculating G/D/H confidence: {exc}")

        # Calculate new uncertainty scores
        uncertainty_scores = self.uncertainty_calculator.compute_all_uncertainties(task, context or {})
        logger.debug(f"Uncertainty scores: {uncertainty_scores}")

        # Compute total uncertainty as weighted sum
        total_uncertainty = (
            self.weights.get('uncertainty', 0.5) * (
                uncertainty_scores.UD + uncertainty_scores.UA +
                uncertainty_scores.UI + uncertainty_scores.UR +
                uncertainty_scores.UG
            ) / 5.0
        )

        # Combine scores
        if gdh_confidence is not None:
            # Use weighted average of both approaches
            combined_confidence = (
                self.weights['gdh'] * gdh_confidence +
                self.weights['uncertainty'] * (1.0 - total_uncertainty)
            )
        else:
            # Use only uncertainty-based confidence
            combined_confidence = 1.0 - total_uncertainty

        # Apply Murphy Gate
        gate_result = self.murphy_gate.evaluate(
            confidence=combined_confidence
        )

        # Create comprehensive report
        report = ConfidenceReport(
            uncertainty_scores=uncertainty_scores,
            confidence=combined_confidence,
            confidence_v1=gdh_confidence,
            gate_result=gate_result,
            factors={
                'has_original_calculator': HAS_ORIGINAL_CALCULATOR,
                'has_phase_controller': HAS_PHASE_CONTROLLER,
                'weights': self.weights
            }
        )

        logger.info(
            f"Unified confidence for task {task.get('id')}: "
            f"{combined_confidence:.3f} (allowed: {gate_result.allowed})"
        )

        return report

    def should_proceed(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if task should proceed based on confidence

        Args:
            task: Task to evaluate
            context: Additional context

        Returns:
            True if task should proceed, False otherwise
        """
        report = self.calculate_confidence(task, context)
        return report.gate_result.allowed

    def get_phase_recommendation(
        self,
        task: Dict[str, Any],
        current_phase: str
    ) -> str:
        """
        Get phase recommendation using original phase controller if available

        Args:
            task: Task being executed
            current_phase: Current execution phase

        Returns:
            Recommended next phase
        """
        if self.phase_controller:
            try:
                return self.phase_controller.get_next_phase(task, current_phase)
            except Exception as exc:
                logger.error(f"Error getting phase recommendation: {exc}")

        # Fallback to simple phase progression
        phases = ['EXPAND', 'TYPE', 'ENUMERATE', 'CONSTRAIN', 'COLLAPSE', 'BIND', 'EXECUTE']
        try:
            current_idx = phases.index(current_phase)
            if current_idx < len(phases) - 1:
                return phases[current_idx + 1]
        except ValueError as exc:
            logger.debug("Suppressed %s: %s", type(exc).__name__, exc)  # noqa: E501

        return 'EXECUTE'

    def update_weights(self, gdh_weight: float, uncertainty_weight: float):
        """
        Update weights for combining G/D/H and uncertainty scores

        Args:
            gdh_weight: Weight for G/D/H score (0.0 to 1.0)
            uncertainty_weight: Weight for uncertainty score (0.0 to 1.0)
        """
        total = gdh_weight + uncertainty_weight
        self.weights['gdh'] = gdh_weight / total
        self.weights['uncertainty'] = uncertainty_weight / total

        logger.info(f"Updated weights: G/D/H={self.weights['gdh']:.2f}, "
                   f"Uncertainty={self.weights['uncertainty']:.2f}")
