"""
Recursion Energy Estimator

Computes the latent control signal Rₜ (Recursion Energy):

    Rₜ = α·Aₜ + β·Gₜ + γ·Eₜ + ε·Mₜ - δ·Cₜ

Where:
- All coefficients are positive
- Rₜ ≥ 0
- Higher Rₜ = more instability

Rₜ is internal only. It is never directly acted upon by external logic.
"""

import logging
from dataclasses import dataclass
from typing import Dict

import numpy as np

from .state_variables import NormalizedState

logger = logging.getLogger("recursive_stability_controller.recursion_energy")


@dataclass
class RecursionEnergyCoefficients:
    """
    Coefficients for recursion energy computation.

    As approved:
    - α = 0.3 (agents)
    - β = 0.2 (gates)
    - γ = 0.4 (entropy)
    - ε = 0.5 (Murphy)
    - δ = 0.6 (confidence)

    IMMUTABLE at runtime unless:
    - System is in frozen state
    - Change is externally approved (config reload / restart)
    """

    alpha: float = 0.3  # Agent weight
    beta: float = 0.2   # Gate weight
    gamma: float = 0.4  # Entropy weight
    epsilon: float = 0.5  # Murphy weight
    delta: float = 0.6  # Confidence weight (negative contribution)

    def validate(self) -> bool:
        """Validate coefficients are positive"""
        return all([
            self.alpha > 0,
            self.beta > 0,
            self.gamma > 0,
            self.epsilon > 0,
            self.delta > 0
        ])

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "gamma": self.gamma,
            "epsilon": self.epsilon,
            "delta": self.delta
        }


class RecursionEnergyEstimator:
    """
    Estimate recursion energy from normalized state.

    Recursion Energy is the latent control signal that measures
    system instability. Higher values indicate more instability.
    """

    def __init__(self, coefficients: RecursionEnergyCoefficients = None):
        """
        Initialize estimator.

        Args:
            coefficients: Recursion energy coefficients (uses defaults if None)
        """
        self.coefficients = coefficients or RecursionEnergyCoefficients()

        # Validate coefficients
        if not self.coefficients.validate():
            raise ValueError("Invalid coefficients: all must be positive")

        # History for analysis
        self.history = []
        self.max_history = 1000

    def estimate(self, state: NormalizedState) -> float:
        """
        Estimate recursion energy from normalized state.

        Formula:
            Rₜ = α·Aₜ + β·Gₜ + γ·Eₜ + ε·Mₜ - δ·Cₜ

        Args:
            state: Normalized state variables

        Returns:
            Recursion energy Rₜ ≥ 0
        """
        # Compute recursion energy
        R_t = (
            self.coefficients.alpha * state.A_t +
            self.coefficients.beta * state.G_t +
            self.coefficients.gamma * state.E_t +
            self.coefficients.epsilon * state.M_t -
            self.coefficients.delta * state.C_t
        )

        # Ensure non-negative
        R_t = max(0.0, R_t)

        # Record in history
        self._record_history(state, R_t)

        return R_t

    def estimate_with_breakdown(self, state: NormalizedState) -> Dict:
        """
        Estimate recursion energy with component breakdown.

        Returns:
            Dictionary with:
            - R_t: Total recursion energy
            - agent_contribution: α·Aₜ
            - gate_contribution: β·Gₜ
            - entropy_contribution: γ·Eₜ
            - murphy_contribution: ε·Mₜ
            - confidence_contribution: -δ·Cₜ
            - dominant_contributor: Component with highest absolute contribution
        """
        # Compute contributions
        agent_contrib = self.coefficients.alpha * state.A_t
        gate_contrib = self.coefficients.beta * state.G_t
        entropy_contrib = self.coefficients.gamma * state.E_t
        murphy_contrib = self.coefficients.epsilon * state.M_t
        confidence_contrib = -self.coefficients.delta * state.C_t

        # Total recursion energy
        R_t = max(0.0, (
            agent_contrib +
            gate_contrib +
            entropy_contrib +
            murphy_contrib +
            confidence_contrib
        ))

        # Find dominant contributor
        contributions = {
            "agents": agent_contrib,
            "gates": gate_contrib,
            "entropy": entropy_contrib,
            "murphy": murphy_contrib,
            "confidence": abs(confidence_contrib)
        }
        dominant = max(contributions.items(), key=lambda x: x[1])

        return {
            "R_t": R_t,
            "agent_contribution": agent_contrib,
            "gate_contribution": gate_contrib,
            "entropy_contribution": entropy_contrib,
            "murphy_contribution": murphy_contrib,
            "confidence_contribution": confidence_contrib,
            "dominant_contributor": dominant[0],
            "dominant_value": dominant[1]
        }

    def _record_history(self, state: NormalizedState, R_t: float):
        """Record recursion energy in history"""
        self.history.append({
            "cycle_id": state.cycle_id,
            "timestamp": state.timestamp,
            "R_t": R_t,
            "A_t": state.A_t,
            "G_t": state.G_t,
            "E_t": state.E_t,
            "C_t": state.C_t,
            "M_t": state.M_t
        })

        # Trim history if needed
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_history(self, n: int = None) -> list:
        """
        Get recursion energy history.

        Args:
            n: Number of recent entries (all if None)

        Returns:
            List of history entries
        """
        if n is None:
            return self.history
        return self.history[-n:]

    def get_statistics(self) -> Dict:
        """
        Get statistics on recursion energy.

        Returns:
            Dictionary with mean, std, min, max, trend
        """
        if not self.history:
            return {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "trend": 0.0,
                "count": 0
            }

        R_values = [h["R_t"] for h in self.history]

        # Compute trend (linear regression slope)
        if len(R_values) >= 3:
            x = np.arange(len(R_values))
            trend = np.polyfit(x, R_values, 1)[0]
        else:
            trend = 0.0

        return {
            "mean": np.mean(R_values),
            "std": np.std(R_values),
            "min": np.min(R_values),
            "max": np.max(R_values),
            "trend": trend,
            "count": len(R_values)
        }

    def update_coefficients(
        self,
        new_coefficients: RecursionEnergyCoefficients,
        force: bool = False
    ) -> bool:
        """
        Update coefficients (restricted operation).

        Args:
            new_coefficients: New coefficients
            force: Force update (use with caution)

        Returns:
            True if update successful, False otherwise
        """
        # Validate new coefficients
        if not new_coefficients.validate():
            logger.info("[ERROR] Invalid coefficients: all must be positive")
            return False

        # Check if update is allowed
        if not force:
            logger.info("[WARNING] Coefficient update requires force=True")
            logger.info("[WARNING] System should be in frozen state")
            return False

        # Update coefficients
        self.coefficients = new_coefficients
        logger.info(f"[INFO] Coefficients updated: {new_coefficients.to_dict()}")

        return True
