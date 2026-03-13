"""
Dynamic State Space Expansion for the Murphy System.

Provides:
  - DimensionExpander: adds state dimensions when new domain knowledge arrives
  - ConstraintInjector: adds constraints dynamically with consistency checking
  - AuthorityExpander: expands authority graph when new roles are discovered
  - RefinementLoop: recursive refinement that tightens state estimates

Control-theoretic motivation:
  A static state space cannot accommodate new domain knowledge at runtime.
  The InfinityExpansionEngine has ExpansionAxis but no mechanism for:
    - Adding state dimensions while preserving existing covariance structure
    - Injecting new constraints while verifying overall feasibility
    - Running iterative Kalman-style refinement to tighten state estimates
  These mechanisms are required for a true adaptive control system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .state_model import StateDimension, StateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Dimension expander
# ------------------------------------------------------------------ #

class DimensionExpander:
    """
    Adds state dimensions to an existing StateVector at runtime.

    The expansion preserves the existing covariance structure:
      - Existing dimensions keep their covariance entries intact.
      - The new dimension gets an initial variance on the diagonal.
      - Off-diagonal cross-covariances with new dimensions start at 0.
    """

    def expand_state(
        self,
        state: StateVector,
        new_dimensions: List[Tuple[StateDimension, float, float]],
    ) -> StateVector:
        """
        Add multiple dimensions to *state* in one operation.

        Args:
            state: existing StateVector.
            new_dimensions: list of (StateDimension, initial_value, initial_variance).

        Returns:
            New StateVector with all original + new dimensions.

        Raises:
            ValueError: if any dimension name already exists in *state*.
        """
        existing_names = set(state.dimension_names)
        for dim, _, _ in new_dimensions:
            if dim.name in existing_names:
                raise ValueError(
                    f"Dimension '{dim.name}' already exists in the state vector."
                )

        expanded = state
        for dim, init_val, init_var in new_dimensions:
            expanded = expanded.add_dimension(
                dimension=dim,
                initial_value=init_val,
                initial_variance=max(0.0, init_var),
            )
            existing_names.add(dim.name)
        return expanded

    def check_expansion_valid(
        self,
        state: StateVector,
        new_dimensions: List[StateDimension],
    ) -> Tuple[bool, List[str]]:
        """
        Check whether the proposed expansion is valid (no name collisions).

        Returns:
            (is_valid, list_of_conflicts)
        """
        existing = set(state.dimension_names)
        conflicts = [d.name for d in new_dimensions if d.name in existing]
        return len(conflicts) == 0, conflicts


# ------------------------------------------------------------------ #
# Constraint injector
# ------------------------------------------------------------------ #

@dataclass
class InjectedConstraint:
    """A dynamically injected constraint g(x) ≤ 0."""

    constraint_id: str
    description: str
    g: Callable[[np.ndarray], float]           # constraint function g(x) ≤ 0
    jacobian: Optional[Callable[[np.ndarray], np.ndarray]] = None  # ∂g/∂x
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_satisfied(self, x: np.ndarray, tolerance: float = 1e-9) -> bool:
        """True if g(x) ≤ tolerance."""
        return float(self.g(x)) <= tolerance

    def evaluate(self, x: np.ndarray) -> float:
        """Return g(x)."""
        return float(self.g(x))


class ConstraintInjector:
    """
    Adds constraints dynamically and verifies global feasibility.

    Constraints are stored as a registry and checked against a
    test point to detect infeasibility before committing to injection.
    """

    def __init__(self) -> None:
        self._constraints: Dict[str, InjectedConstraint] = {}

    @property
    def constraints(self) -> List[InjectedConstraint]:
        return list(self._constraints.values())

    def inject_constraint(
        self,
        constraint: InjectedConstraint,
        test_point: Optional[np.ndarray] = None,
    ) -> bool:
        """
        Add *constraint* to the registry after feasibility check.

        If *test_point* is provided, evaluates g(test_point) before injection.
        Returns True if injection succeeded, False if infeasible.
        """
        if test_point is not None:
            val = constraint.evaluate(test_point)
            if val > 0:
                return False  # constraint violated at test point

        self._constraints[constraint.constraint_id] = constraint
        return True

    def check_consistency(self, test_point: np.ndarray) -> Tuple[bool, List[str]]:
        """
        Verify all constraints are simultaneously satisfied at *test_point*.

        Returns:
            (all_satisfied, list_of_violated_constraint_ids)
        """
        violated = [
            cid
            for cid, c in self._constraints.items()
            if not c.is_satisfied(test_point)
        ]
        return len(violated) == 0, violated

    def remove_constraint(self, constraint_id: str) -> bool:
        """Remove a constraint by ID.  Returns True if it existed."""
        if constraint_id in self._constraints:
            del self._constraints[constraint_id]
            return True
        return False

    def count(self) -> int:
        return len(self._constraints)


# ------------------------------------------------------------------ #
# Authority expander
# ------------------------------------------------------------------ #

@dataclass
class RoleNode:
    """A node in the authority delegation graph."""

    role_id: str
    name: str
    authority_level: float = 0.0      # [0.0, 1.0]
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthorityExpander:
    """
    Expands the authority graph when new roles are discovered.

    Maintains a directed acyclic graph (DAG) of role → subordinate role
    edges, supporting transitive authority queries.
    """

    def __init__(self) -> None:
        self._roles: Dict[str, RoleNode] = {}
        self._edges: Dict[str, List[str]] = {}   # parent_id → [child_id]

    def add_role(self, role: RoleNode) -> None:
        """Register a new role in the authority graph."""
        self._roles[role.role_id] = role
        if role.role_id not in self._edges:
            self._edges[role.role_id] = []

    def add_delegation(self, parent_id: str, child_id: str) -> None:
        """Add delegation edge parent → child (parent delegates to child)."""
        if parent_id not in self._roles:
            raise ValueError(f"Parent role '{parent_id}' not registered.")
        if child_id not in self._roles:
            raise ValueError(f"Child role '{child_id}' not registered.")
        if child_id not in self._edges[parent_id]:
            self._edges[parent_id].append(child_id)

    def get_authority(self, role_id: str) -> float:
        """Return the authority level for *role_id*."""
        role = self._roles.get(role_id)
        return role.authority_level if role else 0.0

    def subordinates(self, role_id: str, transitive: bool = True) -> List[str]:
        """
        Return all subordinate role IDs.

        If *transitive* is True, performs a full BFS to include indirect
        subordinates.
        """
        if not transitive:
            return list(self._edges.get(role_id, []))

        visited: List[str] = []
        stack = list(self._edges.get(role_id, []))
        while stack:
            current = stack.pop()
            if current not in visited:
                visited.append(current)
                stack.extend(self._edges.get(current, []))
        return visited

    def role_count(self) -> int:
        return len(self._roles)


# ------------------------------------------------------------------ #
# Refinement loop
# ------------------------------------------------------------------ #

@dataclass
class RefinementResult:
    """Outcome of an iterative state refinement loop."""

    initial_entropy: float
    final_entropy: float
    iterations_run: int
    converged: bool
    final_state: StateVector


class RefinementLoop:
    """
    Iterative Kalman-style refinement that tightens state estimates.

    Each iteration applies a Kalman measurement update using the
    provided observations, progressively reducing P_t until the
    entropy change falls below *convergence_threshold*.
    """

    def __init__(
        self,
        convergence_threshold: float = 1e-4,
    ) -> None:
        self.convergence_threshold = convergence_threshold

    def refine(
        self,
        state: StateVector,
        observations: List[Tuple[np.ndarray, np.ndarray, np.ndarray]],
        iterations: int = 10,
    ) -> RefinementResult:
        """
        Run iterative refinement.

        Args:
            state: initial StateVector.
            observations: list of (measurement_z, H_matrix, R_matrix).
            iterations: maximum number of refinement passes.

        Returns:
            RefinementResult with final state and convergence statistics.
        """
        initial_entropy = state.get_entropy()
        current = state
        prev_entropy = initial_entropy
        converged = False

        for i in range(iterations):
            for z, H, R in observations:
                current, _ = current.update(z, H, R)

            new_entropy = current.get_entropy()
            if abs(prev_entropy - new_entropy) < self.convergence_threshold:
                converged = True
                break
            prev_entropy = new_entropy

        return RefinementResult(
            initial_entropy=initial_entropy,
            final_entropy=current.get_entropy(),
            iterations_run=i + 1,
            converged=converged,
            final_state=current,
        )
