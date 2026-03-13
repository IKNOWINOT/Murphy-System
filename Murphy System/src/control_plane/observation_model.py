"""
Observation Model for the MFGC Control Plane (Gap CFP-2).

Defines:
- ``ObservationChannel`` — enumeration of all measurement channels.
- ``ObservationVector`` — typed Pydantic model for a single observation snapshot.
- ``ObservationNoise`` — per-channel confidence intervals.
- ``ObservationMapping`` — maps observations to state updates (the H function).
- ``information_gain`` — expected reduction in uncertainty from an observation.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field

from .state_vector import StateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Observation Channel Enum
# ------------------------------------------------------------------ #


class ObservationChannel(str, Enum):
    """All measurement channels the Murphy System can ingest."""

    USER_INPUT = "user_input"
    LLM_RESPONSE_QUALITY = "llm_response_quality"
    GATE_EVALUATION_RESULT = "gate_evaluation_result"
    CONSTRAINT_CHECK_RESULT = "constraint_check_result"
    TELEMETRY_READING = "telemetry_reading"
    HUMAN_FEEDBACK = "human_feedback"
    DOCUMENT_INGESTION = "document_ingestion"
    CROSS_DOMAIN_SIGNAL = "cross_domain_signal"


# ------------------------------------------------------------------ #
# Observation Vector (Pydantic)
# ------------------------------------------------------------------ #


class ObservationVector(BaseModel):
    """Typed observation snapshot z_t.

    Each field represents a single measurement channel value in [0.0, 1.0]
    (or None when the channel is not active in this observation).
    """

    user_input_signal: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    llm_response_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    gate_evaluation_result: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    constraint_check_result: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    telemetry_reading: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    human_feedback: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    document_ingestion: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    cross_domain_signal: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = {"extra": "forbid"}

    def active_channels(self) -> Dict[ObservationChannel, float]:
        """Return only the channels that carry a non-None value."""
        mapping = {
            ObservationChannel.USER_INPUT: self.user_input_signal,
            ObservationChannel.LLM_RESPONSE_QUALITY: self.llm_response_quality,
            ObservationChannel.GATE_EVALUATION_RESULT: self.gate_evaluation_result,
            ObservationChannel.CONSTRAINT_CHECK_RESULT: self.constraint_check_result,
            ObservationChannel.TELEMETRY_READING: self.telemetry_reading,
            ObservationChannel.HUMAN_FEEDBACK: self.human_feedback,
            ObservationChannel.DOCUMENT_INGESTION: self.document_ingestion,
            ObservationChannel.CROSS_DOMAIN_SIGNAL: self.cross_domain_signal,
        }
        return {ch: v for ch, v in mapping.items() if v is not None}


# ------------------------------------------------------------------ #
# Observation Noise
# ------------------------------------------------------------------ #


@dataclass
class ObservationNoise:
    """Per-channel noise model (Gaussian σ and confidence intervals)."""

    channel: ObservationChannel
    sigma: float = 0.1  # standard deviation
    confidence_lower: float = field(init=False)
    confidence_upper: float = field(init=False)

    def __post_init__(self) -> None:
        # 95 % confidence interval (±1.96 σ), clamped to [0, 1]
        self.confidence_lower = max(0.0, -1.96 * self.sigma)
        self.confidence_upper = min(1.0, 1.96 * self.sigma)


# Default noise per channel
_DEFAULT_NOISE: Dict[ObservationChannel, float] = {
    ObservationChannel.USER_INPUT: 0.15,
    ObservationChannel.LLM_RESPONSE_QUALITY: 0.20,
    ObservationChannel.GATE_EVALUATION_RESULT: 0.05,
    ObservationChannel.CONSTRAINT_CHECK_RESULT: 0.05,
    ObservationChannel.TELEMETRY_READING: 0.02,
    ObservationChannel.HUMAN_FEEDBACK: 0.12,
    ObservationChannel.DOCUMENT_INGESTION: 0.10,
    ObservationChannel.CROSS_DOMAIN_SIGNAL: 0.18,
}

# Channel → state dimension mapping (H matrix rows)
_CHANNEL_TO_DIM: Dict[ObservationChannel, str] = {
    ObservationChannel.USER_INPUT: "information_completeness",
    ObservationChannel.LLM_RESPONSE_QUALITY: "confidence",
    ObservationChannel.GATE_EVALUATION_RESULT: "verification_coverage",
    ObservationChannel.CONSTRAINT_CHECK_RESULT: "constraint_satisfaction",
    ObservationChannel.TELEMETRY_READING: "risk_exposure",
    ObservationChannel.HUMAN_FEEDBACK: "authority",
    ObservationChannel.DOCUMENT_INGESTION: "domain_depth",
    ObservationChannel.CROSS_DOMAIN_SIGNAL: "information_completeness",
}


# ------------------------------------------------------------------ #
# Observation Mapping (H function)
# ------------------------------------------------------------------ #


class ObservationMapping:
    """Maps an ``ObservationVector`` to a posterior ``StateVector``.

    This is the H function in the control-theoretic formulation:
        x_{t+1} ≈ x_t + K · (z_t − H·x_t)

    A simplified Kalman-style update is used.
    """

    def __init__(
        self,
        noise_overrides: Optional[Dict[ObservationChannel, float]] = None,
    ) -> None:
        self._noise: Dict[ObservationChannel, float] = dict(_DEFAULT_NOISE)
        if noise_overrides:
            self._noise.update(noise_overrides)

    def map_to_state(
        self,
        observation: ObservationVector,
        prior_state: StateVector,
    ) -> StateVector:
        """Apply observation to prior state and return posterior state.

        Each active channel nudges the corresponding state dimension toward
        the observed value, weighted by channel reliability (1 / (1 + σ)).
        """
        updates: Dict[str, float] = {}
        for channel, obs_value in observation.active_channels().items():
            dim = _CHANNEL_TO_DIM.get(channel)
            if dim is None:
                continue
            sigma = self._noise.get(channel, 0.1)
            weight = 1.0 / (1.0 + sigma)
            prior_value = getattr(prior_state, dim, 0.0)
            if isinstance(prior_value, (int, float)):
                # Kalman-style blending
                updated = prior_value + weight * (obs_value - prior_value)
                updates[dim] = float(updated)

        if not updates:
            return prior_state

        return prior_state.with_update(**updates)

    def information_gain(
        self,
        question: str,
        prior_state: StateVector,
    ) -> float:
        """Estimate expected reduction in uncertainty from asking *question*.

        Uses a heuristic: longer, more specific questions yield higher
        expected information gain, bounded by prior uncertainty.
        """
        prior_uncertainty = max(
            1.0 - prior_state.confidence,
            1.0 - prior_state.information_completeness,
        )
        # Heuristic: question length as a proxy for specificity
        specificity = min(1.0, len(question) / 200.0)
        sigma_avg = sum(_DEFAULT_NOISE.values()) / (len(_DEFAULT_NOISE) or 1)
        noise_var = sigma_avg ** 2
        prior_var = prior_uncertainty ** 2
        gain = (prior_var / (prior_var + noise_var + 1e-9)) * specificity
        return float(max(0.0, gain))


__all__ = [
    "ObservationChannel",
    "ObservationVector",
    "ObservationNoise",
    "ObservationMapping",
    "information_gain",
]


def information_gain(
    question: str,
    prior_state: StateVector,
) -> float:
    """Module-level helper: estimate information gain of *question* given *prior_state*."""
    return ObservationMapping().information_gain(question, prior_state)
