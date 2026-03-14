"""
Formal Uncertainty Measure with Entropy for the Murphy System.

Provides information-theoretic tools to quantify system uncertainty and
drive question selection:

  - compute_differential_entropy(cov): H = 0.5 * ln((2πe)^n |P|)
  - compute_murphy_index_formal(state): combines loss×probability with entropy
  - UncertaintyBudget: per-dimension maximum-acceptable variance allocation
  - QuestionSelector: selects questions that maximally reduce state entropy

Control-theoretic motivation:
  The Murphy Index M_t = Σ(L_k × p_k) captures expected loss but provides
  no information about COVARIANCE — i.e., how confident we are about each
  loss estimate.  Adding the differential entropy H(P_t) turns M_t into a
  rigorous risk-plus-uncertainty measure.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Differential entropy
# ------------------------------------------------------------------ #

def compute_differential_entropy(covariance_matrix: np.ndarray) -> float:
    """
    Differential entropy of a multivariate Gaussian N(μ, Σ):

        H = 0.5 * ln((2πe)^n * det(Σ))

    Args:
        covariance_matrix: n×n positive-semi-definite covariance matrix.

    Returns:
        Differential entropy (nats). Returns 0.0 for singular covariance.
    """
    if covariance_matrix.ndim != 2:
        raise ValueError("covariance_matrix must be 2-D.")
    n = covariance_matrix.shape[0]
    if covariance_matrix.shape != (n, n):
        raise ValueError("covariance_matrix must be square.")

    sign, log_det = np.linalg.slogdet(covariance_matrix)
    if sign <= 0:
        return 0.0
    return 0.5 * (n * (1.0 + math.log(2.0 * math.pi)) + log_det)


# ------------------------------------------------------------------ #
# Formal Murphy Index
# ------------------------------------------------------------------ #

def compute_murphy_index_formal(
    loss_probabilities: Sequence[Tuple[float, float]],
    covariance_matrix: Optional[np.ndarray] = None,
    entropy_weight: float = 0.1,
) -> float:
    """
    Formal Murphy Index combining expected loss with uncertainty:

        M_formal = M_t + λ · H(P_t)

    where  M_t = Σ(L_k × p_k)  and  H(P_t) is differential entropy.

    Args:
        loss_probabilities: sequence of (loss, probability) pairs.
        covariance_matrix: optional state covariance P_t.  If None,
            the entropy term is omitted.
        entropy_weight: λ — how much entropy contributes relative to expected loss.

    Returns:
        Formal Murphy Index ≥ 0.
    """
    # Standard Murphy Index: expected loss
    murphy_index = sum(L * p for L, p in loss_probabilities)

    # Add entropy contribution when covariance is available
    if covariance_matrix is not None:
        entropy = compute_differential_entropy(covariance_matrix)
        murphy_index += entropy_weight * max(0.0, entropy)

    return murphy_index


# ------------------------------------------------------------------ #
# Uncertainty budget
# ------------------------------------------------------------------ #

@dataclass
class UncertaintyBudget:
    """
    Allocates maximum acceptable variance per state dimension.

    Provides a threshold map that can be compared against the diagonal of
    the covariance matrix P_t to detect dimensions that need more
    observations.
    """

    budgets: Dict[str, float] = field(default_factory=dict)
    default_budget: float = 0.1

    def set_budget(self, dimension: str, max_variance: float) -> None:
        """Set the maximum acceptable variance for *dimension*."""
        if max_variance < 0.0:
            raise ValueError("max_variance must be non-negative.")
        self.budgets[dimension] = max_variance

    def get_budget(self, dimension: str) -> float:
        """Return the maximum acceptable variance for *dimension*."""
        return self.budgets.get(dimension, self.default_budget)

    def over_budget(self, dimension: str, variance: float) -> bool:
        """True if the current variance exceeds the budget."""
        return variance > self.get_budget(dimension)

    def over_budget_dimensions(
        self, dimension_variances: Dict[str, float]
    ) -> List[str]:
        """Return dimensions whose variance exceeds their budget."""
        return [
            dim
            for dim, var in dimension_variances.items()
            if self.over_budget(dim, var)
        ]

    def get_uncertainty_budget(self) -> Dict[str, float]:
        """Return the full budget mapping."""
        return dict(self.budgets)


# ------------------------------------------------------------------ #
# Entropy tracker
# ------------------------------------------------------------------ #

class EntropyTracker:
    """Tracks differential entropy over time and detects divergence."""

    def __init__(self) -> None:
        self._history: List[float] = []

    def record(self, covariance_matrix: np.ndarray) -> float:
        """Record entropy at the current time step and return it."""
        h = compute_differential_entropy(covariance_matrix)
        capped_append(self._history, h)
        return h

    @property
    def history(self) -> List[float]:
        return list(self._history)

    def is_non_increasing(self, tolerance: float = 1e-9) -> bool:
        """True if entropy is monotonically non-increasing (Bayes-optimal)."""
        for i in range(1, len(self._history)):
            if self._history[i] > self._history[i - 1] + tolerance:
                return False
        return True

    def latest(self) -> Optional[float]:
        return self._history[-1] if self._history else None


# ------------------------------------------------------------------ #
# Question selector
# ------------------------------------------------------------------ #

@dataclass
class CandidateQuestion:
    """A candidate question / observation channel with expected information gain."""

    question_id: str
    description: str
    expected_H_prior: float        # entropy of P_t before observing
    expected_H_posterior: float    # expected entropy of P_t after observing
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def information_gain(self) -> float:
        """IG = H_prior - H_posterior."""
        return self.expected_H_prior - self.expected_H_posterior


class QuestionSelector:
    """
    Selects questions that maximally reduce state-vector entropy.

    Implements the information-theoretic selection criterion:

        q* = argmax_q IG(q)  where  IG(q) = H(P_prior) - H(P_posterior | q)

    The posterior covariance after a measurement with noise R through
    measurement matrix H is given by the Kalman update formula:

        P' = (I - K H) P,   K = P Hᵀ (H P Hᵀ + R)⁻¹
    """

    def compute_information_gain_kalman(
        self,
        P_prior: np.ndarray,
        H_obs: np.ndarray,
        R: np.ndarray,
    ) -> float:
        """
        Compute information gain for a single Kalman observation step.

            IG = 0.5 * ln( det(P_prior) / det(P_posterior) )

        Args:
            P_prior: prior covariance n×n.
            H_obs: measurement matrix m×n.
            R: measurement noise covariance m×m.

        Returns:
            Information gain ≥ 0.
        """
        n = P_prior.shape[0]
        S = H_obs @ P_prior @ H_obs.T + R
        K = P_prior @ H_obs.T @ np.linalg.inv(S)
        P_post = (np.eye(n) - K @ H_obs) @ P_prior

        sign_prior, logdet_prior = np.linalg.slogdet(P_prior)
        sign_post, logdet_post = np.linalg.slogdet(P_post)

        if sign_prior <= 0 or sign_post <= 0:
            return 0.0

        return 0.5 * (logdet_prior - logdet_post)

    def select_best_question(
        self, candidate_questions: List[CandidateQuestion]
    ) -> Optional[CandidateQuestion]:
        """
        Return the question with the highest information gain.

        Returns None if the candidate list is empty.
        """
        if not candidate_questions:
            return None
        return max(candidate_questions, key=lambda q: q.information_gain)

    def select_next_question(
        self,
        P_prior: np.ndarray,
        candidates: List[Tuple[str, np.ndarray, np.ndarray]],
    ) -> Optional[str]:
        """
        Select the next question by maximising Kalman information gain.

        Args:
            P_prior: current state covariance n×n.
            candidates: list of (question_id, H_obs m×n, R m×m) tuples.

        Returns:
            The question_id with the highest information gain, or None.
        """
        if not candidates:
            return None

        best_id = None
        best_ig = -math.inf

        for q_id, H_obs, R in candidates:
            ig = self.compute_information_gain_kalman(P_prior, H_obs, R)
            if ig > best_ig:
                best_ig = ig
                best_id = q_id

        return best_id
