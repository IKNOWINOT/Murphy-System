"""
Feedback Integrator (Gap CFP-4 — Closed Learning Loop).

Provides :class:`FeedbackSignal` and :class:`FeedbackIntegrator` to
structurally reintegrate corrections back into the typed state vector.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from state_schema import StateVariable, TypedStateVector

logger = logging.getLogger(__name__)


@dataclass
class FeedbackSignal:
    """Represents a single piece of feedback to be integrated into state.

    Attributes:
        signal_type: One of ``"correction"``, ``"feedback"``,
            ``"recalibration"``.
        source_task_id: Identifier of the task that generated this signal.
        original_confidence: The confidence value before correction.
        corrected_confidence: The corrected confidence value, if available.
        affected_state_variables: Names of state dimensions affected by this
            signal.
        timestamp: When the signal was generated.
    """

    signal_type: str
    source_task_id: str
    original_confidence: float
    corrected_confidence: Optional[float] = None
    affected_state_variables: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FeedbackIntegrator:
    """Applies :class:`FeedbackSignal` instances to a :class:`TypedStateVector`.

    This closes the learning loop by adjusting per-variable uncertainty
    whenever corrections or recalibration signals are received.
    """

    # ------------------------------------------------------------------
    # Core integration
    # ------------------------------------------------------------------

    def integrate(
        self, signal: FeedbackSignal, state: TypedStateVector
    ) -> TypedStateVector:
        """Apply *signal* to *state* by adjusting affected-variable uncertainty.

        For a *correction* signal, uncertainty is reduced in proportion to the
        magnitude of the confidence correction.  For other signal types the
        uncertainty is nudged down by a small fixed amount.

        Returns the same *state* object (mutated in place) for chaining.
        """
        delta = self._signal_uncertainty_delta(signal)
        for var_name in signal.affected_state_variables:
            sv = state.get(var_name)
            if sv is not None:
                new_uncertainty = max(0.0, min(1.0, sv.uncertainty + delta))
                state.set(
                    var_name,
                    sv.value,
                    uncertainty=new_uncertainty,
                    source=f"feedback:{signal.source_task_id}",
                    dtype=sv.dtype,
                    domain=sv.domain,
                )
            else:
                # Dimension not yet tracked — add it with the given uncertainty
                initial_uncertainty = max(0.0, min(1.0, abs(delta)))
                state.set(
                    var_name,
                    None,
                    uncertainty=initial_uncertainty,
                    source=f"feedback:{signal.source_task_id}",
                )
        return state

    # ------------------------------------------------------------------
    # Batch analysis
    # ------------------------------------------------------------------

    def compute_learning_delta(
        self, signals: List[FeedbackSignal]
    ) -> Dict[str, float]:
        """Compute per-variable uncertainty adjustments from a batch of signals.

        Returns a dict mapping each affected state-variable name to the
        net uncertainty adjustment (negative means *reduce* uncertainty).
        """
        deltas: Dict[str, float] = {}
        for signal in signals:
            d = self._signal_uncertainty_delta(signal)
            for var_name in signal.affected_state_variables:
                deltas[var_name] = deltas.get(var_name, 0.0) + d
        return deltas

    def should_trigger_recalibration(
        self,
        signals: List[FeedbackSignal],
        threshold: float = 0.3,
    ) -> bool:
        """Return ``True`` if the batch of *signals* warrants recalibration.

        Recalibration is triggered when the average absolute confidence
        correction across all signals with a ``corrected_confidence`` exceeds
        *threshold*.
        """
        corrections = [
            abs((s.corrected_confidence or s.original_confidence) - s.original_confidence)
            for s in signals
            if s.corrected_confidence is not None
        ]
        if not corrections:
            return False
        return (sum(corrections) / len(corrections)) >= threshold

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _signal_uncertainty_delta(signal: FeedbackSignal) -> float:
        """Compute the uncertainty delta for a single signal.

        Corrections that move confidence *upward* reduce uncertainty;
        all other signals apply a small fixed reduction.
        """
        if signal.corrected_confidence is not None:
            # Magnitude of correction; reduce uncertainty proportionally
            magnitude = abs(signal.corrected_confidence - signal.original_confidence)
            return -magnitude
        # Non-correction signals: small fixed uncertainty reduction
        return -0.05


__all__ = [
    "FeedbackSignal",
    "FeedbackIntegrator",
]
