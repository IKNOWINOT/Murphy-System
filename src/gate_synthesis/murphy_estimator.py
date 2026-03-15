"""
Murphy Probability Estimator
Estimates probability of Murphy paths and determines when gates are required
"""

import logging
import math
from typing import Any, Dict, List, Optional

from .models import ExposureSignal, FailureMode, RiskPath, RiskVector

logger = logging.getLogger(__name__)


class MurphyProbabilityEstimator:
    """
    Estimates Murphy probability using sigmoid function:

    p_k = σ(α×H + β×(1-D) + γ×Exposure + δ×AuthorityRisk)

    If p_k exceeds threshold → gate required
    """

    def __init__(self):
        # Sigmoid parameters (weights for each risk component)
        self.alpha = 2.0    # Weight for epistemic instability
        self.beta = 1.5     # Weight for lack of grounding
        self.gamma = 1.8    # Weight for exposure
        self.delta = 1.2    # Weight for authority risk

        # Thresholds
        self.gate_required_threshold = 0.6  # If p_k > 0.6, gate required
        self.high_risk_threshold = 0.8      # If p_k > 0.8, critical gate required

    def estimate_murphy_probability(
        self,
        risk_vector: RiskVector
    ) -> float:
        """
        Estimate Murphy probability using sigmoid function

        Args:
            risk_vector: Risk vector with H, 1-D, Exposure, AuthorityRisk

        Returns:
            Probability in [0, 1]
        """
        # Calculate weighted sum
        z = (
            self.alpha * risk_vector.H +
            self.beta * risk_vector.one_minus_D +
            self.gamma * risk_vector.exposure +
            self.delta * risk_vector.authority_risk
        )

        # Apply sigmoid
        probability = self._sigmoid(z)

        return probability

    def _sigmoid(self, x: float) -> float:
        """Sigmoid function"""
        return 1.0 / (1.0 + math.exp(-x))

    def requires_gate(
        self,
        murphy_probability: float
    ) -> bool:
        """
        Determine if gate is required based on Murphy probability

        Args:
            murphy_probability: Estimated Murphy probability

        Returns:
            True if gate required
        """
        return murphy_probability > self.gate_required_threshold

    def is_high_risk(
        self,
        murphy_probability: float
    ) -> bool:
        """
        Determine if situation is high risk

        Args:
            murphy_probability: Estimated Murphy probability

        Returns:
            True if high risk
        """
        return murphy_probability > self.high_risk_threshold

    def estimate_failure_mode_probability(
        self,
        failure_mode: FailureMode
    ) -> float:
        """
        Estimate probability for a specific failure mode

        Uses the failure mode's risk vector
        """
        return self.estimate_murphy_probability(failure_mode.risk_vector)

    def forecast_risk_path(
        self,
        failure_modes: List[FailureMode],
        path_steps: List[str]
    ) -> RiskPath:
        """
        Forecast risk path showing how risk evolves

        Args:
            failure_modes: List of failure modes along the path
            path_steps: Sequence of artifact IDs

        Returns:
            Risk path with cumulative risk
        """
        # Calculate cumulative risk
        cumulative_risk = 0.0
        for failure_mode in failure_modes:
            murphy_prob = self.estimate_failure_mode_probability(failure_mode)
            cumulative_risk += murphy_prob * failure_mode.impact

        # Normalize
        cumulative_risk = min(1.0, cumulative_risk)

        # Calculate path likelihood (product of probabilities)
        likelihood = 1.0
        for failure_mode in failure_modes:
            likelihood *= failure_mode.probability

        # Generate path ID
        path_id = f"path_{'_'.join(path_steps[:3])}"

        risk_path = RiskPath(
            path_id=path_id,
            steps=path_steps,
            failure_modes=failure_modes,
            cumulative_risk=cumulative_risk,
            likelihood=likelihood
        )

        return risk_path

    def analyze_exposure(
        self,
        exposure_signal: ExposureSignal
    ) -> Dict[str, Any]:
        """
        Analyze exposure signal and determine risk level

        Args:
            exposure_signal: Exposure signal

        Returns:
            Analysis with risk assessment
        """
        # Create risk vector from exposure
        risk_vector = RiskVector(
            H=0.0,  # Not applicable for exposure analysis
            one_minus_D=0.0,
            exposure=exposure_signal.blast_radius_estimate,
            authority_risk=0.0
        )

        # Estimate probability
        murphy_prob = self.estimate_murphy_probability(risk_vector)

        # Determine if gate required
        gate_required = self.requires_gate(murphy_prob)
        high_risk = self.is_high_risk(murphy_prob)

        return {
            'murphy_probability': murphy_prob,
            'gate_required': gate_required,
            'high_risk': high_risk,
            'risk_level': exposure_signal.risk_level,
            'reversibility': exposure_signal.reversibility,
            'blast_radius': exposure_signal.blast_radius_estimate,
            'external_side_effects': exposure_signal.external_side_effects
        }

    def calculate_gate_priority(
        self,
        murphy_probability: float,
        failure_mode: FailureMode
    ) -> int:
        """
        Calculate priority for gate (1-10, higher = more critical)

        Args:
            murphy_probability: Murphy probability
            failure_mode: Failure mode being addressed

        Returns:
            Priority level (1-10)
        """
        # Base priority from Murphy probability
        base_priority = int(murphy_probability * 10)

        # Adjust for impact
        impact_adjustment = int(failure_mode.impact * 3)

        # Adjust for failure mode type
        type_priorities = {
            'irreversible_action': 3,
            'blast_radius_exceeded': 3,
            'authority_misuse': 2,
            'semantic_drift': 2,
            'constraint_violation': 1,
            'verification_insufficient': 1
        }

        type_adjustment = type_priorities.get(failure_mode.type.value, 1)

        # Calculate final priority
        priority = base_priority + impact_adjustment + type_adjustment

        # Clamp to [1, 10]
        priority = max(1, min(10, priority))

        return priority

    def get_risk_summary(
        self,
        failure_modes: List[FailureMode]
    ) -> Dict[str, Any]:
        """
        Get summary of risk across all failure modes

        Args:
            failure_modes: List of failure modes

        Returns:
            Risk summary
        """
        if not failure_modes:
            return {
                'total_failure_modes': 0,
                'average_murphy_probability': 0.0,
                'max_murphy_probability': 0.0,
                'gates_required': 0,
                'high_risk_modes': 0
            }

        # Calculate Murphy probabilities
        murphy_probs = [
            self.estimate_failure_mode_probability(fm)
            for fm in failure_modes
        ]

        # Count gates required
        gates_required = sum(1 for p in murphy_probs if self.requires_gate(p))

        # Count high risk modes
        high_risk_modes = sum(1 for p in murphy_probs if self.is_high_risk(p))

        return {
            'total_failure_modes': len(failure_modes),
            'average_murphy_probability': sum(murphy_probs) / (len(murphy_probs) or 1),
            'max_murphy_probability': max(murphy_probs),
            'gates_required': gates_required,
            'high_risk_modes': high_risk_modes,
            'failure_mode_types': {
                fm.type.value: fm.probability
                for fm in failure_modes
            }
        }
