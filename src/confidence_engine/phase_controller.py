"""
Phase Controller
Controls phase transitions based on confidence thresholds
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .models import ConfidenceState, Phase

logger = logging.getLogger(__name__)


class PhaseController:
    """
    Controls phase transitions

    Rules:
    - if c_t >= θ_p: p_t+1 = p_t + 1
    - else: p_t+1 = p_t
    - Phase skipping is forbidden
    - No reverse transitions
    """

    def __init__(self):
        self.phase_history: List[Dict[str, Any]] = []

    def check_phase_transition(
        self,
        current_phase: Phase,
        confidence_state: ConfidenceState
    ) -> tuple[Phase, bool, str]:
        """
        Check if phase transition should occur

        Args:
            current_phase: Current phase
            confidence_state: Current confidence state

        Returns:
            (new_phase, transitioned, reason)
        """
        confidence = confidence_state.confidence
        threshold = current_phase.confidence_threshold

        # Check if confidence meets threshold
        if confidence >= threshold:
            # Advance to next phase
            new_phase = self._get_next_phase(current_phase)

            if new_phase != current_phase:
                # Transition occurred
                self._log_transition(
                    current_phase,
                    new_phase,
                    confidence,
                    threshold,
                    "Confidence threshold met"
                )
                return new_phase, True, f"Advanced from {current_phase.value} to {new_phase.value}"
            else:
                # Already at final phase
                return current_phase, False, "Already at final phase (EXECUTE)"
        else:
            # Stay in current phase
            gap = threshold - confidence
            return current_phase, False, f"Confidence gap: {gap:.3f} (need {threshold:.2f}, have {confidence:.2f})"

    def _get_next_phase(self, current_phase: Phase) -> Phase:
        """
        Get next phase in sequence

        Phase skipping is forbidden
        """
        phases = list(Phase)
        current_idx = phases.index(current_phase)

        if current_idx < len(phases) - 1:
            return phases[current_idx + 1]
        else:
            # Already at final phase
            return current_phase

    def _log_transition(
        self,
        from_phase: Phase,
        to_phase: Phase,
        confidence: float,
        threshold: float,
        reason: str
    ) -> None:
        """Log phase transition"""
        self.phase_history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'from_phase': from_phase.value,
            'to_phase': to_phase.value,
            'confidence': confidence,
            'threshold': threshold,
            'reason': reason
        })

    def get_phase_progress(self, current_phase: Phase) -> Dict[str, Any]:
        """
        Get progress through phases

        Returns:
            Progress information
        """
        phases = list(Phase)
        current_idx = phases.index(current_phase)
        total_phases = len(phases)

        return {
            'current_phase': current_phase.value,
            'phase_index': current_idx,
            'total_phases': total_phases,
            'progress_ratio': (current_idx + 1) / total_phases,
            'remaining_phases': total_phases - current_idx - 1,
            'next_phase': phases[current_idx + 1].value if current_idx < total_phases - 1 else None,
            'confidence_threshold': current_phase.confidence_threshold
        }

    def get_phase_history(self) -> List[Dict[str, Any]]:
        """Get complete phase transition history"""
        return self.phase_history.copy()

    def can_skip_phase(self) -> bool:
        """
        Check if phase skipping is allowed

        Always returns False - phase skipping is forbidden
        """
        return False

    def can_reverse_phase(self) -> bool:
        """
        Check if reverse phase transitions are allowed

        Always returns False - no reverse transitions
        """
        return False
