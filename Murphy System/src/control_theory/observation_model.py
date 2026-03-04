"""
Formal Observation Model for the Murphy System.

Defines:
  - ObservationChannel enum — every measurement source the system can use.
  - ObservationNoise — per-channel Gaussian noise model  v_t ~ N(0, R_t).
  - ObservationFunction — declarative mapping  z_t = h(x_t) + v_t.
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

import numpy as np

from .canonical_state import CanonicalStateVector, _DIMENSION_NAMES


# ------------------------------------------------------------------ #
# Observation channels
# ------------------------------------------------------------------ #

class ObservationChannel(Enum):
    """Every measurement source the Murphy System can ingest."""

    INQUISITORY = "inquisitory"          # question-answer cycles
    DOCUMENT_PARSER = "document_parser"  # SOP / requirement docs
    TICKET_INGEST = "ticket_ingest"      # ticket event ingestor
    MESSAGE_PIPE = "message_pipe"        # communication pipeline
    SIGNAL_INTERPRETER = "signal_interpreter"  # AUAR signal interpreter
    CONFIDENCE_CALC = "confidence_calc"  # confidence calculator
    GATE_CHECK = "gate_check"            # Murphy gate evaluation
    SENSOR_TELEMETRY = "sensor_telemetry"  # runtime CPU / memory / uptime


# ------------------------------------------------------------------ #
# Per-channel noise model
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class ObservationNoise:
    """
    Gaussian noise parameters for a single observation channel.

    v_t ~ N(0, variance) per dimension the channel can observe.
    """

    channel: ObservationChannel
    variance: float = 0.01          # σ² — measurement noise variance
    reliability: float = 1.0        # [0, 1] — overall channel reliability

    @property
    def std_dev(self) -> float:
        """Standard deviation σ = √variance."""
        return math.sqrt(max(self.variance, 0.0))


# ------------------------------------------------------------------ #
# Channel → state-variable mapping
# ------------------------------------------------------------------ #

# Which dimensions each channel is allowed to update.
_CHANNEL_STATE_MAP: Dict[ObservationChannel, Set[str]] = {
    ObservationChannel.INQUISITORY: {
        "confidence", "uncertainty_data", "uncertainty_information",
        "uncertainty_authority", "domain_depth",
    },
    ObservationChannel.DOCUMENT_PARSER: {
        "confidence", "artifact_count", "active_constraints",
        "uncertainty_data", "complexity",
    },
    ObservationChannel.TICKET_INGEST: {
        "active_tasks", "uncertainty_resources", "complexity",
    },
    ObservationChannel.MESSAGE_PIPE: {
        "uncertainty_information", "uncertainty_disagreement",
    },
    ObservationChannel.SIGNAL_INTERPRETER: {
        "confidence", "uncertainty_authority", "uncertainty_information",
    },
    ObservationChannel.CONFIDENCE_CALC: {
        "confidence", "murphy_index",
    },
    ObservationChannel.GATE_CHECK: {
        "gate_count", "murphy_index", "authority",
    },
    ObservationChannel.SENSOR_TELEMETRY: {
        "uptime_seconds", "active_tasks", "cpu_usage_percent",
    },
}


# Default noise parameters per channel.
_DEFAULT_NOISE: Dict[ObservationChannel, ObservationNoise] = {
    ch: ObservationNoise(channel=ch, variance=0.01, reliability=0.95)
    for ch in ObservationChannel
}


# ------------------------------------------------------------------ #
# Observation data
# ------------------------------------------------------------------ #

@dataclass
class ObservationData:
    """A single observation vector from one channel."""

    channel: ObservationChannel
    values: Dict[str, float] = field(default_factory=dict)
    timestamp: Optional[str] = None


# ------------------------------------------------------------------ #
# Observation function  z_t = h(x_t) + v_t
# ------------------------------------------------------------------ #

class ObservationFunction:
    """
    Formal observation model:  z_t = h(x_t) + v_t

    * h(x_t)  projects the full state onto the dimensions visible to a channel.
    * v_t      adds Gaussian noise according to the channel's noise model.
    """

    def __init__(
        self,
        channel_state_map: Optional[Dict[ObservationChannel, Set[str]]] = None,
        noise_models: Optional[Dict[ObservationChannel, ObservationNoise]] = None,
    ):
        self.channel_state_map = channel_state_map or dict(_CHANNEL_STATE_MAP)
        self.noise_models = noise_models or dict(_DEFAULT_NOISE)

    # ---- public API ------------------------------------------------ #

    def observable_dimensions(self, channel: ObservationChannel) -> Set[str]:
        """Return the set of state dimensions this channel can observe."""
        return self.channel_state_map.get(channel, set())

    def all_observable_dimensions(self) -> Set[str]:
        """Union of all observable dimensions across every channel."""
        result: Set[str] = set()
        for dims in self.channel_state_map.values():
            result |= dims
        return result

    def unobservable_dimensions(self) -> Set[str]:
        """Dimensions that no channel can observe."""
        return set(_DIMENSION_NAMES) - self.all_observable_dimensions()

    def is_fully_observable(self) -> bool:
        """True iff every state dimension is observed by at least one channel."""
        return len(self.unobservable_dimensions()) == 0

    def observe(
        self,
        state: CanonicalStateVector,
        channel: ObservationChannel,
        *,
        add_noise: bool = True,
    ) -> ObservationData:
        """
        z_t = h(x_t) + v_t

        Projects *state* onto the dimensions visible to *channel* and
        optionally adds Gaussian noise.
        """
        dims = self.channel_state_map.get(channel, set())
        noise = self.noise_models.get(
            channel, ObservationNoise(channel=channel)
        )
        state_dict = {
            name: val
            for name, val in zip(_DIMENSION_NAMES, state.to_vector())
        }
        values: Dict[str, float] = {}
        for dim in dims:
            true_val = state_dict.get(dim, 0.0)
            if add_noise and noise.variance > 0.0:
                noisy_val = true_val + random.gauss(0.0, noise.std_dev)
            else:
                noisy_val = true_val
            values[dim] = noisy_val
        return ObservationData(channel=channel, values=values)

    def register_channel(
        self,
        channel: ObservationChannel,
        dimensions: Set[str],
        noise: Optional[ObservationNoise] = None,
    ) -> None:
        """Register (or update) a channel's observable dimensions and noise."""
        valid = set(_DIMENSION_NAMES)
        invalid = dimensions - valid
        if invalid:
            raise ValueError(
                f"Unknown dimensions: {invalid}. Valid: {valid}"
            )
        self.channel_state_map[channel] = dimensions
        if noise is not None:
            self.noise_models[channel] = noise


# ------------------------------------------------------------------ #
# Kalman-based observation — matrix formulation
# ------------------------------------------------------------------ #



class KalmanObserver:
    """
    Matrix-based observation model providing Kalman gain and information gain.

    Supplements ObservationFunction with the formal linear algebra needed
    for covariance-aware state estimation:

        Innovation:  y = z - H x_predicted
        Kalman gain: K = P Hᵀ (H P Hᵀ + R)⁻¹
        Info gain:   IG = 0.5 * ln( det(P_prior) / det(P_posterior) )
    """

    def observe(
        self,
        x_predicted: np.ndarray,
        measurement: np.ndarray,
        H: np.ndarray,
        P: np.ndarray,
        R: np.ndarray,
    ) -> tuple:
        """
        Compute innovation and Kalman gain.

        Args:
            x_predicted: predicted state vector ∈ ℝ^n.
            measurement: observed measurement z ∈ ℝ^m.
            H: measurement matrix ∈ ℝ^{m×n}.
            P: state covariance ∈ ℝ^{n×n}.
            R: measurement noise covariance ∈ ℝ^{m×m}.

        Returns:
            (innovation, kalman_gain) — y ∈ ℝ^m, K ∈ ℝ^{n×m}.
        """
        innovation = measurement - H @ x_predicted
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        return innovation, K

    def compute_information_gain(
        self,
        P: np.ndarray,
        H: np.ndarray,
        R: np.ndarray,
    ) -> float:
        """
        Compute expected information gain for a Kalman measurement step.

            IG = 0.5 * ln( det(P_prior) / det(P_posterior) )

        where P_posterior = (I - K H) P_prior.

        Args:
            P: prior covariance ∈ ℝ^{n×n}.
            H: measurement matrix ∈ ℝ^{m×n}.
            R: measurement noise covariance ∈ ℝ^{m×m}.

        Returns:
            Information gain ≥ 0.0.
        """
        n = P.shape[0]
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        P_post = (np.eye(n) - K @ H) @ P

        sign_prior, logdet_prior = np.linalg.slogdet(P)
        sign_post, logdet_post = np.linalg.slogdet(P_post)

        if sign_prior <= 0 or sign_post <= 0:
            return 0.0

        return 0.5 * (logdet_prior - logdet_post)

    def select_best_question(
        self,
        P: np.ndarray,
        candidate_channels: list,
    ) -> Optional[str]:
        """
        Select the observation channel that maximises information gain.

        Args:
            P: current prior covariance ∈ ℝ^{n×n}.
            candidate_channels: list of (channel_id, H_matrix, R_matrix).

        Returns:
            channel_id of the best question, or None if the list is empty.
        """
        if not candidate_channels:
            return None

        best_id: Optional[str] = None
        best_ig = -math.inf

        for ch_id, H, R in candidate_channels:
            ig = self.compute_information_gain(P, H, R)
            if ig > best_ig:
                best_ig = ig
                best_id = ch_id

        return best_id
