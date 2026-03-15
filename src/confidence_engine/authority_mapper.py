"""
Authority Mapper
Maps confidence to authority bands: a_t = Γ(c_t)
"""

import logging
from typing import Any, Dict

from .models import AuthorityBand, AuthorityState, ConfidenceState, Phase

logger = logging.getLogger(__name__)


class AuthorityMapper:
    """
    Maps confidence to authority bands

    Authority automatically revokes if confidence drops
    No hysteresis allowed

    Policy table:
    Confidence      Authority
    <0.3           Ask only
    0.3–0.5        Generate
    0.5–0.7        Propose
    0.7–0.85       Negotiate
    ≥0.85          Execute
    """

    def __init__(self):
        # Authority thresholds (no hysteresis)
        self.thresholds = [
            (0.85, AuthorityBand.EXECUTE),
            (0.70, AuthorityBand.NEGOTIATE),
            (0.50, AuthorityBand.PROPOSE),
            (0.30, AuthorityBand.GENERATE),
            (0.00, AuthorityBand.ASK_ONLY)
        ]

    def map_authority(
        self,
        confidence_state: ConfidenceState,
        murphy_index: float,
        gate_satisfaction: float = 0.0,
        unknowns: int = 0
    ) -> AuthorityState:
        """
        Map confidence to authority band

        Args:
            confidence_state: Current confidence state
            murphy_index: Current Murphy index
            gate_satisfaction: Gate satisfaction ratio [0, 1]
            unknowns: Number of unresolved unknowns

        Returns:
            Authority state with execution eligibility
        """
        confidence = confidence_state.confidence

        # Determine authority band based on confidence
        authority_band = self._get_authority_band(confidence)

        # Check execution eligibility
        can_execute = self._check_execution_eligibility(
            confidence,
            murphy_index,
            gate_satisfaction,
            unknowns,
            confidence_state.phase
        )

        # Create authority state
        authority_state = AuthorityState(
            authority_band=authority_band,
            confidence=confidence,
            can_execute=can_execute,
            phase=confidence_state.phase,
            gate_satisfaction=gate_satisfaction,
            murphy_index=murphy_index,
            unknowns=unknowns
        )

        return authority_state

    def _get_authority_band(self, confidence: float) -> AuthorityBand:
        """
        Get authority band for given confidence

        No hysteresis - strictly based on current confidence
        """
        for threshold, band in self.thresholds:
            if confidence >= threshold:
                return band

        return AuthorityBand.ASK_ONLY

    def _check_execution_eligibility(
        self,
        confidence: float,
        murphy_index: float,
        gate_satisfaction: float,
        unknowns: int,
        phase: Phase
    ) -> bool:
        """
        Check if system can execute

        Execution requires ALL of:
        1. Confidence ≥ 0.85
        2. Murphy Index ≤ 0.5
        3. Gate Satisfaction ≥ 70%
        4. Unknowns ≤ 2
        5. Phase = EXECUTE

        Returns:
            True if execution is allowed
        """
        # Check all criteria
        confidence_ok = confidence >= 0.85
        murphy_ok = murphy_index <= 0.5
        gates_ok = gate_satisfaction >= 0.70
        unknowns_ok = unknowns <= 2
        phase_ok = phase == Phase.EXECUTE

        # ALL must be satisfied
        can_execute = (
            confidence_ok and
            murphy_ok and
            gates_ok and
            unknowns_ok and
            phase_ok
        )

        return can_execute

    def get_execution_blockers(
        self,
        confidence: float,
        murphy_index: float,
        gate_satisfaction: float,
        unknowns: int,
        phase: Phase
    ) -> Dict[str, Any]:
        """
        Get detailed breakdown of execution blockers

        Returns:
            Dictionary with blocker status
        """
        blockers = {
            'confidence': {
                'current': confidence,
                'required': 0.85,
                'satisfied': confidence >= 0.85,
                'gap': max(0.0, 0.85 - confidence)
            },
            'murphy_index': {
                'current': murphy_index,
                'max_allowed': 0.5,
                'satisfied': murphy_index <= 0.5,
                'excess': max(0.0, murphy_index - 0.5)
            },
            'gate_satisfaction': {
                'current': gate_satisfaction,
                'required': 0.70,
                'satisfied': gate_satisfaction >= 0.70,
                'gap': max(0.0, 0.70 - gate_satisfaction)
            },
            'unknowns': {
                'current': unknowns,
                'max_allowed': 2,
                'satisfied': unknowns <= 2,
                'excess': max(0, unknowns - 2)
            },
            'phase': {
                'current': phase.value,
                'required': Phase.EXECUTE.value,
                'satisfied': phase == Phase.EXECUTE
            }
        }

        # Count total blockers
        total_blockers = sum(1 for b in blockers.values() if not b['satisfied'])
        blockers['total_blockers'] = total_blockers
        blockers['can_execute'] = total_blockers == 0

        return blockers

    def calculate_authority_decay(
        self,
        current_authority: AuthorityBand,
        new_confidence: float
    ) -> AuthorityBand:
        """
        Calculate authority decay when confidence drops

        Authority automatically revokes - no hysteresis

        Args:
            current_authority: Current authority band
            new_confidence: New confidence value

        Returns:
            New authority band (may be lower)
        """
        # Simply remap based on new confidence
        # No hysteresis - immediate revocation
        return self._get_authority_band(new_confidence)
