"""
Jurisdiction-aware constraint extensions and probabilistic compliance.

Adds:
  - jurisdiction field to constraints
  - select_constraints(jurisdiction) → List[Constraint]
  - probabilistic compliance  P(g_i(x_t) ≤ 0) ≥ 1 - ε_i
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .canonical_state import CanonicalStateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Jurisdiction model
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class Jurisdiction:
    """
    Legal / geographic jurisdiction.

    Constraints are tagged with a jurisdiction so the system can select
    only those that apply in a given deployment context.
    """

    code: str            # e.g. "US", "EU", "US-CA"
    name: str = ""
    parent: Optional[str] = None  # e.g. "US" is parent of "US-CA"


# Pre-defined jurisdictions
JURISDICTION_US = Jurisdiction(code="US", name="United States")
JURISDICTION_EU = Jurisdiction(code="EU", name="European Union")
JURISDICTION_US_CA = Jurisdiction(code="US-CA", name="California", parent="US")
JURISDICTION_UK = Jurisdiction(code="UK", name="United Kingdom")
JURISDICTION_GLOBAL = Jurisdiction(code="GLOBAL", name="Global")


# ------------------------------------------------------------------ #
# Constraint with jurisdiction
# ------------------------------------------------------------------ #

@dataclass
class JurisdictionConstraint:
    """
    A formal constraint  g_i(x) ≤ 0  with jurisdiction tagging and
    probabilistic compliance support.

    Attributes:
        constraint_id: unique ID.
        name: human-readable label.
        parameter: which state dimension this constrains.
        threshold: the boundary value.
        operator: one of '<=', '>=', '=='.
        jurisdictions: set of jurisdiction codes where this applies.
        epsilon: acceptable violation probability  (1 - ε is confidence).
        uncertainty_variance: estimated variance of the constrained value.
    """

    constraint_id: str
    name: str
    parameter: str
    threshold: float
    operator: str = "<="
    jurisdictions: Set[str] = field(default_factory=lambda: {"GLOBAL"})
    epsilon: float = 0.05       # P(violation) ≤ ε
    uncertainty_variance: float = 0.0  # σ² of the constrained value

    def applies_in(self, jurisdiction_code: str) -> bool:
        """True if this constraint applies in the given jurisdiction."""
        if "GLOBAL" in self.jurisdictions:
            return True
        return jurisdiction_code in self.jurisdictions

    def evaluate_deterministic(self, value: float) -> bool:
        """Binary satisfaction check (no uncertainty)."""
        if self.operator == "<=":
            return value <= self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "==":
            return math.isclose(value, self.threshold, abs_tol=1e-9)
        return False

    def evaluate_probabilistic(self, value: float) -> float:
        """
        Probability of constraint satisfaction under Gaussian uncertainty.

        P(g(x) ≤ 0) using the normal CDF, where the constrained random
        variable is  X ~ N(value, uncertainty_variance).

        Returns probability in [0, 1].
        """
        if self.uncertainty_variance <= 0.0:
            return 1.0 if self.evaluate_deterministic(value) else 0.0

        sigma = math.sqrt(self.uncertainty_variance)
        if self.operator == "<=":
            # P(X ≤ threshold) = Φ((threshold - value) / σ)
            z = (self.threshold - value) / sigma
        elif self.operator == ">=":
            # P(X ≥ threshold) = 1 - Φ((threshold - value) / σ)
            z = (value - self.threshold) / sigma
        elif self.operator == "==":
            return 1.0 if math.isclose(value, self.threshold, abs_tol=3 * sigma) else 0.0
        else:
            return 0.0

        return _normal_cdf(z)

    def is_probabilistically_satisfied(self, value: float) -> bool:
        """
        True if  P(constraint satisfied) ≥ 1 - ε.
        """
        return self.evaluate_probabilistic(value) >= (1.0 - self.epsilon)


# ------------------------------------------------------------------ #
# Jurisdiction-based selection
# ------------------------------------------------------------------ #

class JurisdictionConstraintRegistry:
    """
    Registry of jurisdiction-tagged constraints.

    Supports:
      - select_constraints(jurisdiction) → applicable constraints
      - conflict detection between jurisdictions
    """

    def __init__(self) -> None:
        self._constraints: Dict[str, JurisdictionConstraint] = {}

    def add(self, constraint: JurisdictionConstraint) -> None:
        self._constraints[constraint.constraint_id] = constraint

    def select_constraints(self, jurisdiction_code: str) -> List[JurisdictionConstraint]:
        """Return all constraints that apply in *jurisdiction_code*."""
        return [
            c for c in self._constraints.values()
            if c.applies_in(jurisdiction_code)
        ]

    def detect_conflicts(
        self, jurisdiction_code: str
    ) -> List[tuple]:
        """
        Detect conflicting constraints within a jurisdiction.

        Two constraints conflict if they constrain the same parameter
        with contradictory operators/thresholds.
        """
        applicable = self.select_constraints(jurisdiction_code)
        conflicts = []
        for i, a in enumerate(applicable):
            for b in applicable[i + 1:]:
                if a.parameter == b.parameter:
                    if a.operator == "<=" and b.operator == ">=" and a.threshold < b.threshold:
                        conflicts.append((a.constraint_id, b.constraint_id, "infeasible_range"))
                    elif a.operator == ">=" and b.operator == "<=" and a.threshold > b.threshold:
                        conflicts.append((a.constraint_id, b.constraint_id, "infeasible_range"))
        return conflicts

    @property
    def all_constraints(self) -> List[JurisdictionConstraint]:
        return list(self._constraints.values())


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _normal_cdf(z: float) -> float:
    """Approximate standard normal CDF using the error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
