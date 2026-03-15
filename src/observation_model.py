"""
Observation-to-State Mapping Layer (GAP-4).

Defines:
- :class:`ObservationChannel` — enumeration of measurement sources.
- :class:`Observation` — dataclass carrying a single measurement.
- :class:`ObservationModel` — maps observations to state-variable deltas
  and performs simple Bayesian uncertainty updates.
"""

import logging

logger = logging.getLogger(__name__)
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

try:
    from .mfgc_core import StateVector
except ImportError:
    try:
        from mfgc_core import StateVector
    except ImportError:
        StateVector = None  # type: ignore[assignment,misc]


# ------------------------------------------------------------------ #
# Observation Channel Enum
# ------------------------------------------------------------------ #

class ObservationChannel(Enum):
    """Every measurement source the Murphy System can ingest."""

    USER_INPUT = "user_input"
    DOCUMENT_INGESTION = "document_ingestion"
    LLM_RESPONSE = "llm_response"
    GATE_EVALUATION = "gate_evaluation"
    TELEMETRY = "telemetry"
    HUMAN_FEEDBACK = "human_feedback"


# ------------------------------------------------------------------ #
# Observation Dataclass
# ------------------------------------------------------------------ #

@dataclass
class Observation:
    """A single measurement arriving from an observation channel.

    Attributes:
        channel: The source channel for this observation.
        timestamp: Unix timestamp of the observation (defaults to now).
        raw_data: The unprocessed payload from the channel.
        processed_value: Optional scalar value derived from raw_data.
        noise_estimate: Caller-supplied noise estimate (σ²); overrides the
            channel default when provided.
    """

    channel: ObservationChannel
    raw_data: Any
    timestamp: float = field(default_factory=time.time)
    processed_value: Optional[float] = None
    noise_estimate: Optional[float] = None


# ------------------------------------------------------------------ #
# Observation Model
# ------------------------------------------------------------------ #

# Default noise standard-deviations per channel (σ, not σ²)
MIN_NOISE_VARIANCE: float = 1e-9
"""Floor for noise variance to keep the Kalman-style denominator non-zero."""

_DEFAULT_NOISE: Dict[ObservationChannel, float] = {
    ObservationChannel.USER_INPUT: 0.15,
    ObservationChannel.DOCUMENT_INGESTION: 0.10,
    ObservationChannel.LLM_RESPONSE: 0.20,
    ObservationChannel.GATE_EVALUATION: 0.05,
    ObservationChannel.TELEMETRY: 0.02,
    ObservationChannel.HUMAN_FEEDBACK: 0.12,
}

# Which state dimensions each channel primarily updates
_CHANNEL_DIM_MAP: Dict[ObservationChannel, str] = {
    ObservationChannel.USER_INPUT: "domain_knowledge_level",
    ObservationChannel.DOCUMENT_INGESTION: "information_completeness",
    ObservationChannel.LLM_RESPONSE: "domain_knowledge_level",
    ObservationChannel.GATE_EVALUATION: "verification_coverage",
    ObservationChannel.TELEMETRY: "risk_exposure",
    ObservationChannel.HUMAN_FEEDBACK: "constraint_satisfaction_ratio",
}


class ObservationModel:
    """Maps raw observations to typed state-variable deltas.

    Usage::

        model = ObservationModel()
        model.register_channel(ObservationChannel.USER_INPUT, noise_std=0.1)
        obs = Observation(channel=ObservationChannel.USER_INPUT, raw_data="hello")
        deltas = model.process_observation(obs)
    """

    def __init__(self) -> None:
        # Per-channel noise σ (standard deviation)
        self._noise: Dict[ObservationChannel, float] = dict(_DEFAULT_NOISE)
        # Per-channel reliability ∈ [0, 1]
        self._reliability: Dict[ObservationChannel, float] = {
            ch: 1.0 for ch in ObservationChannel
        }

    # -------------------------------------------------------------- #
    # Channel management
    # -------------------------------------------------------------- #

    def register_channel(
        self, channel: ObservationChannel, noise_std: float, reliability: float = 1.0
    ) -> None:
        """Register or update the noise and reliability for a channel.

        Args:
            channel: The channel to configure.
            noise_std: Gaussian noise standard deviation (σ ≥ 0).
            reliability: Channel reliability in [0, 1].
        """
        if noise_std < 0:
            raise ValueError("noise_std must be >= 0")
        reliability = max(0.0, min(1.0, reliability))
        self._noise[channel] = noise_std
        self._reliability[channel] = reliability

    def get_channel_reliability(self, channel: ObservationChannel) -> float:
        """Return the reliability score for *channel* in [0, 1]."""
        return self._reliability.get(channel, 1.0)

    # -------------------------------------------------------------- #
    # Observation processing
    # -------------------------------------------------------------- #

    def process_observation(self, obs: Observation) -> Dict[str, float]:
        """Map an observation to state-variable deltas.

        Returns a dict mapping dimension name → delta value.  The delta is
        derived from the observation's processed_value (or a heuristic from
        raw_data) scaled by channel reliability and attenuated by noise.
        """
        value = self._extract_value(obs)
        reliability = self._reliability.get(obs.channel, 1.0)
        noise_std = (
            obs.noise_estimate if obs.noise_estimate is not None
            else self._noise.get(obs.channel, 0.1)
        )

        # Simple noise attenuation: weight = reliability / (1 + noise_std)
        weight = reliability / (1.0 + noise_std)
        delta = value * weight

        # Map to primary state dimension
        dim = _CHANNEL_DIM_MAP.get(obs.channel, "domain_knowledge_level")
        return {dim: delta}

    def compute_information_gain(
        self, obs: Observation, current_state: Any
    ) -> float:
        """Estimate information gain from an observation given the current state.

        Uses a simplified Bayesian update: information gain is proportional
        to the reduction in uncertainty achievable by the observation.

        Args:
            obs: The incoming observation.
            current_state: A :class:`~mfgc_core.StateVector` (or any object
                with an ``uncertainty`` dict attribute).

        Returns:
            Estimated information gain (≥ 0).
        """
        noise_std = (
            obs.noise_estimate if obs.noise_estimate is not None
            else self._noise.get(obs.channel, 0.1)
        )
        reliability = self._reliability.get(obs.channel, 1.0)

        # Prior uncertainty for the dimension this channel updates
        dim = _CHANNEL_DIM_MAP.get(obs.channel, "domain_knowledge_level")
        prior_uncertainty = 1.0
        if current_state is not None:
            try:
                uncertainty_dict = (
                    current_state.uncertainty
                    if hasattr(current_state, "uncertainty")
                    else {}
                )
                prior_uncertainty = uncertainty_dict.get(dim, 1.0)
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                prior_uncertainty = 1.0

        # Kalman-style information gain approximation:
        # IG = prior_var / (prior_var + noise_var) × reliability
        prior_var = prior_uncertainty ** 2
        noise_var = (noise_std ** 2) if noise_std > 0 else MIN_NOISE_VARIANCE
        info_gain = (prior_var / (prior_var + noise_var)) * reliability

        # Update the uncertainty dict in-place (Bayesian update)
        if current_state is not None and hasattr(current_state, "uncertainty"):
            posterior_var = (prior_var * noise_var) / (prior_var + noise_var)
            current_state.uncertainty[dim] = math.sqrt(posterior_var)

        return max(0.0, info_gain)

    # -------------------------------------------------------------- #
    # Internal helpers
    # -------------------------------------------------------------- #

    @staticmethod
    def _extract_value(obs: Observation) -> float:
        """Extract or infer a scalar value from the observation."""
        if obs.processed_value is not None:
            return float(obs.processed_value)
        raw = obs.raw_data
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, dict):
            for key in ("value", "score", "confidence", "level"):
                if key in raw:
                    return float(raw[key])
        if isinstance(raw, str) and raw:
            return min(1.0, len(raw) / 500.0)
        return 0.5


__all__ = [
    "ObservationChannel",
    "Observation",
    "ObservationModel",
]
