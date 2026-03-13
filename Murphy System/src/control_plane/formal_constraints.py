"""
Formal Constraints for the MFGC Control Plane (Gap CFP-4).

Defines:
- ``FormalConstraint`` — g(x_t) ≤ 0 evaluation.
- ``JurisdictionRegistry`` — maps jurisdiction codes to constraint sets.
- ``ProbabilisticConstraintChecker`` — P(g(x_t) ≤ 0) given state uncertainty.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .state_vector import StateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Formal Constraint base
# ------------------------------------------------------------------ #


class FormalConstraint(ABC):
    """Abstract constraint g(x_t).

    ``evaluate(state)`` returns a float value.
    - Negative (or zero) → constraint satisfied (g(x_t) ≤ 0).
    - Positive → constraint violated.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def evaluate(self, state: StateVector) -> float:
        """Return g(x_t).  Negative means satisfied, positive means violated."""

    def is_satisfied(self, state: StateVector) -> bool:
        """Return True when the constraint is satisfied."""
        return self.evaluate(state) <= 0.0


# ------------------------------------------------------------------ #
# Concrete constraint implementations
# ------------------------------------------------------------------ #


class MinimumConfidenceConstraint(FormalConstraint):
    """Constraint: confidence must be ≥ threshold.

    g(x) = threshold − confidence(x)   (≤ 0 when satisfied)
    """

    def __init__(self, threshold: float = 0.5) -> None:
        super().__init__(
            name="minimum_confidence",
            description=f"confidence ≥ {threshold}",
        )
        self.threshold = threshold

    def evaluate(self, state: StateVector) -> float:
        return self.threshold - state.confidence


class MaximumRiskConstraint(FormalConstraint):
    """Constraint: risk_exposure must be ≤ threshold.

    g(x) = risk_exposure(x) − threshold   (≤ 0 when satisfied)
    """

    def __init__(self, threshold: float = 0.7) -> None:
        super().__init__(
            name="maximum_risk",
            description=f"risk_exposure ≤ {threshold}",
        )
        self.threshold = threshold

    def evaluate(self, state: StateVector) -> float:
        return state.risk_exposure - self.threshold


class LambdaConstraint(FormalConstraint):
    """Constraint defined by a callable ``g: StateVector -> float``."""

    def __init__(
        self,
        name: str,
        g: Callable[[StateVector], float],
        description: str = "",
    ) -> None:
        super().__init__(name=name, description=description)
        self._g = g

    def evaluate(self, state: StateVector) -> float:
        return self._g(state)


# ------------------------------------------------------------------ #
# Jurisdiction Registry
# ------------------------------------------------------------------ #


class JurisdictionRegistry:
    """Maps jurisdiction codes (e.g. ``"EU"`` , ``"US"``) to constraint sets."""

    def __init__(self) -> None:
        self._registry: Dict[str, List[FormalConstraint]] = {}

    def register(
        self, jurisdiction: str, constraint: FormalConstraint
    ) -> None:
        """Add *constraint* to *jurisdiction*."""
        self._registry.setdefault(jurisdiction, []).append(constraint)

    def get_constraints(
        self, jurisdiction: str
    ) -> List[FormalConstraint]:
        """Return all constraints for *jurisdiction* (empty list if unknown)."""
        return list(self._registry.get(jurisdiction, []))

    def evaluate_all(
        self, jurisdiction: str, state: StateVector
    ) -> Dict[str, float]:
        """Evaluate all constraints for *jurisdiction* and return name→value."""
        return {
            c.name: c.evaluate(state)
            for c in self.get_constraints(jurisdiction)
        }

    def all_satisfied(self, jurisdiction: str, state: StateVector) -> bool:
        """Return True when every constraint for *jurisdiction* is satisfied."""
        return all(
            c.is_satisfied(state)
            for c in self.get_constraints(jurisdiction)
        )

    def list_jurisdictions(self) -> List[str]:
        """Return all registered jurisdiction codes."""
        return list(self._registry.keys())


# ------------------------------------------------------------------ #
# Probabilistic Constraint Checker
# ------------------------------------------------------------------ #


class ProbabilisticConstraintChecker:
    """Compute P(g(x_t) ≤ 0) given state uncertainty.

    Uses a Monte-Carlo approximation: sample the state dimensions according
    to their uncertainty, evaluate the constraint, and return the fraction
    of satisfied samples.
    """

    def __init__(self, n_samples: int = 200, seed: int = 42) -> None:
        self._n_samples = n_samples
        # Simple LCG PRNG to avoid numpy dependency
        self._state = seed

    def _next_rand(self) -> float:
        """Return next pseudo-random float in [0, 1) via LCG."""
        self._state = (1664525 * self._state + 1013904223) & 0xFFFFFFFF
        return self._state / 0x100000000

    def _randn(self) -> float:
        """Box-Muller transform for N(0,1) samples."""
        u1 = max(self._next_rand(), 1e-10)
        u2 = self._next_rand()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def probability_satisfied(
        self,
        constraint: FormalConstraint,
        state: StateVector,
        uncertainty: float = 0.1,
    ) -> float:
        """Estimate P(g(x_t) ≤ 0).

        Args:
            constraint: The constraint to check.
            state: Current state estimate.
            uncertainty: Global uncertainty σ applied to all base dimensions.

        Returns:
            Probability in [0.0, 1.0].
        """
        satisfied = 0
        base = state.to_dict()
        keys = [
            k for k, v in base.items() if isinstance(v, (int, float))
        ]

        for _ in range(self._n_samples):
            # Perturb each dimension with N(0, uncertainty)
            perturbed: Dict[str, float] = {}
            for k in keys:
                v = float(base[k])
                noise = self._randn() * uncertainty
                # Clamp to [0.0, max(1.0, v + noise)]
                perturbed[k] = max(0.0, v + noise)

            try:
                sampled_state = StateVector(**perturbed)
            except Exception as exc:
                # If clamping still violates Pydantic bounds, skip sample
                logger.debug("Suppressed exception: %s", exc)
                continue

            if constraint.is_satisfied(sampled_state):
                satisfied += 1

        return satisfied / self._n_samples


__all__ = [
    "FormalConstraint",
    "MinimumConfidenceConstraint",
    "MaximumRiskConstraint",
    "LambdaConstraint",
    "JurisdictionRegistry",
    "ProbabilisticConstraintChecker",
]
