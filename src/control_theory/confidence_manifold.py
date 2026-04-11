"""
Confidence Manifold Router for the Murphy System.
Design Label: MANIFOLD-ROUTE-001

Replaces scalar confidence-threshold phase transitions with geodesic-distance
computation on a confidence manifold, providing smooth phase transitions that
respect the geometry of the confidence-phase space.

Instead of hard if confidence > threshold checks, computes the geodesic
distance from the current state to each phase's attractor point on the
manifold.  Transition occurs when the geodesic distance to the next phase
is less than the distance to the current phase.

Feature flag: MURPHY_MANIFOLD_ROUTING (default: disabled)

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .manifold_projection import Manifold, SphereManifold

logger = logging.getLogger(__name__)

# Feature flag
MANIFOLD_ROUTING_ENABLED: bool = os.environ.get("MURPHY_MANIFOLD_ROUTING", "0") == "1"

# Phase attractor points on the confidence manifold.
# Each phase has a target (confidence, authority, progress) triple
# that defines its ideal operating point.
_PHASE_ATTRACTORS: Dict[str, np.ndarray] = {
    "expand":    np.array([0.30, 0.10, 0.05]),
    "type":      np.array([0.50, 0.30, 0.20]),
    "enumerate": np.array([0.60, 0.45, 0.35]),
    "constrain": np.array([0.65, 0.55, 0.50]),
    "collapse":  np.array([0.70, 0.65, 0.65]),
    "bind":      np.array([0.75, 0.75, 0.80]),
    "execute":   np.array([0.85, 0.90, 0.95]),
}

# Ordered phase names for sequential logic
_PHASE_ORDER: List[str] = [
    "expand", "type", "enumerate", "constrain",
    "collapse", "bind", "execute",
]


@dataclass
class PhaseTransitionResult:
    """Result of a manifold-based phase transition evaluation."""

    current_phase: str
    recommended_phase: str
    should_transition: bool
    current_distance: float
    next_distance: float
    geodesic_distances: Dict[str, float] = field(default_factory=dict)
    reason: str = ""


class ConfidenceManifold(SphereManifold):
    """
    Confidence manifold for phase routing.
    Design Label: MANIFOLD-ROUTE-002

    Models the (confidence, authority, progress) space as a sphere.
    Geodesic distances on this sphere determine phase transitions.
    """

    def __init__(self, radius: float = 1.0) -> None:
        super().__init__(radius=radius)

    def state_to_point(
        self,
        confidence: float,
        authority: float,
        progress: float,
    ) -> np.ndarray:
        """
        Map scalar confidence/authority/progress to a point on the manifold.

        Clamps inputs to [0, 1] and projects to the sphere surface.
        """
        point = np.array([
            max(0.0, min(1.0, confidence)),
            max(0.0, min(1.0, authority)),
            max(0.0, min(1.0, progress)),
        ])
        return self.project(point)


class ConfidenceManifoldRouter:
    """
    Routes phase transitions using geodesic distances on a confidence manifold.
    Design Label: MANIFOLD-ROUTE-003

    Usage::

        router = ConfidenceManifoldRouter()
        result = router.evaluate_transition(
            current_phase="constrain",
            confidence=0.72,
            authority=0.60,
            progress=0.55,
        )
        if result.should_transition:
            new_phase = result.recommended_phase
    """

    def __init__(
        self,
        manifold: Optional[ConfidenceManifold] = None,
        attractors: Optional[Dict[str, np.ndarray]] = None,
        enabled: Optional[bool] = None,
        transition_margin: float = 0.05,
    ) -> None:
        """
        Args:
            manifold: ConfidenceManifold instance (default: unit sphere).
            attractors: phase → attractor-point map (default: built-in).
            enabled: override for feature flag (default: reads env var).
            transition_margin: geodesic margin required for transition to
                prevent oscillation (analogous to HYSTERESIS_BAND).
        """
        self.manifold = manifold or ConfidenceManifold(radius=1.0)
        self.attractors = attractors or dict(_PHASE_ATTRACTORS)
        self.enabled = enabled if enabled is not None else MANIFOLD_ROUTING_ENABLED
        self.transition_margin = transition_margin

    def evaluate_transition(
        self,
        current_phase: str,
        confidence: float,
        authority: float = 0.0,
        progress: float = 0.0,
        max_phase_reversals: int = 3,
        reversal_count: int = 0,
    ) -> PhaseTransitionResult:
        """
        Evaluate whether a phase transition should occur.

        Computes geodesic distance from the current state to every phase
        attractor.  Recommends transition to the *nearest* phase that is
        ahead of or equal to the current phase (no backward jumps unless
        reversal budget allows it).

        Args:
            current_phase: current MFGC phase name.
            confidence: current confidence c_t.
            authority: current authority a_t.
            progress: progress metric (e.g., phase_index / 6).
            max_phase_reversals: reversal limit.
            reversal_count: how many reversals have occurred.

        Returns:
            PhaseTransitionResult with recommendation.
        """
        if not self.enabled:
            return PhaseTransitionResult(
                current_phase=current_phase,
                recommended_phase=current_phase,
                should_transition=False,
                current_distance=0.0,
                next_distance=0.0,
                reason="Manifold routing disabled",
            )

        try:
            return self._evaluate(
                current_phase, confidence, authority, progress,
                max_phase_reversals, reversal_count,
            )
        except Exception as exc:  # MANIFOLD-ROUTE-ERR-001
            logger.warning(
                "MANIFOLD-ROUTE-ERR-001: Geodesic evaluation failed (%s), "
                "no transition recommended",
                exc,
            )
            return PhaseTransitionResult(
                current_phase=current_phase,
                recommended_phase=current_phase,
                should_transition=False,
                current_distance=0.0,
                next_distance=0.0,
                reason=f"Error: {exc}",
            )

    def _evaluate(
        self,
        current_phase: str,
        confidence: float,
        authority: float,
        progress: float,
        max_phase_reversals: int,
        reversal_count: int,
    ) -> PhaseTransitionResult:
        """Core transition evaluation logic."""
        current_point = self.manifold.state_to_point(confidence, authority, progress)

        # Compute geodesic distances to all phase attractors
        distances: Dict[str, float] = {}
        for phase_name, attractor in self.attractors.items():
            attractor_on_manifold = self.manifold.project(attractor)
            distances[phase_name] = self.manifold.geodesic_distance(
                current_point, attractor_on_manifold,
            )

        current_idx = _PHASE_ORDER.index(current_phase) if current_phase in _PHASE_ORDER else 0
        current_dist = distances.get(current_phase, float("inf"))

        # Find the nearest phase that is at or ahead of current
        best_phase = current_phase
        best_dist = current_dist
        forward_locked = reversal_count >= max_phase_reversals

        for phase_name in _PHASE_ORDER:
            phase_idx = _PHASE_ORDER.index(phase_name)
            dist = distances.get(phase_name, float("inf"))

            # Skip backward phases if forward-locked
            if forward_locked and phase_idx < current_idx:
                continue

            if dist < best_dist - self.transition_margin:
                best_phase = phase_name
                best_dist = dist

        should_transition = (best_phase != current_phase)
        next_phase_name = _PHASE_ORDER[min(current_idx + 1, len(_PHASE_ORDER) - 1)]
        next_dist = distances.get(next_phase_name, float("inf"))

        reason = ""
        if should_transition:
            reason = (
                f"Geodesic distance to '{best_phase}' ({best_dist:.4f}) < "
                f"distance to '{current_phase}' ({current_dist:.4f}) "
                f"by margin {self.transition_margin}"
            )
        else:
            reason = f"Current phase '{current_phase}' is nearest (d={current_dist:.4f})"

        return PhaseTransitionResult(
            current_phase=current_phase,
            recommended_phase=best_phase,
            should_transition=should_transition,
            current_distance=current_dist,
            next_distance=next_dist,
            geodesic_distances=distances,
            reason=reason,
        )

    def compute_distances(
        self,
        confidence: float,
        authority: float = 0.0,
        progress: float = 0.0,
    ) -> Dict[str, float]:
        """
        Compute geodesic distances from a state to all phase attractors.

        Useful for diagnostic logging.
        """
        try:
            point = self.manifold.state_to_point(confidence, authority, progress)
            distances: Dict[str, float] = {}
            for phase_name, attractor in self.attractors.items():
                attractor_on_manifold = self.manifold.project(attractor)
                distances[phase_name] = self.manifold.geodesic_distance(
                    point, attractor_on_manifold,
                )
            return distances
        except Exception as exc:  # MANIFOLD-ROUTE-ERR-002
            logger.warning("MANIFOLD-ROUTE-ERR-002: Distance computation failed (%s)", exc)
            return {}
