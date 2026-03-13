"""Information-theoretic primitives for the Murphy System control theory layer."""

import logging
import math
from typing import List

logger = logging.getLogger(__name__)


def shannon_entropy(probabilities: List[float]) -> float:
    """
    Compute Shannon entropy H(X) = -Σ p(xᵢ) log₂ p(xᵢ)

    Args:
        probabilities: List of probabilities that should sum to ~1.0

    Returns:
        Entropy in bits. Returns 0.0 for empty or degenerate distributions.

    Properties:
        - H(X) >= 0 for all distributions
        - H(X) = 0 iff distribution is a point mass
        - H(X) is maximized by uniform distribution (= log₂(n))
    """
    if not probabilities:
        return 0.0
    h = 0.0
    for p in probabilities:
        if p > 0.0:
            h -= p * math.log2(p)
    return h


def kl_divergence(p: List[float], q: List[float]) -> float:
    """
    Compute KL divergence D_KL(P || Q) = Σ p(xᵢ) log₂(p(xᵢ)/q(xᵢ))

    Properties:
        - D_KL(P || Q) >= 0 (Gibbs' inequality)
        - D_KL(P || Q) = 0 iff P = Q
        - NOT symmetric: D_KL(P||Q) ≠ D_KL(Q||P)
    """
    _EPSILON = 1e-15
    if len(p) != len(q):
        raise ValueError("Distributions must have the same length.")
    result = 0.0
    for pi, qi in zip(p, q):
        if pi > 0.0:
            result += pi * math.log2(pi / (qi + _EPSILON))
    return result


def information_gain(prior_entropy: float, posterior_entropy: float) -> float:
    """
    IG = H(prior) - H(posterior)

    Non-negative when observation reduces uncertainty.
    """
    return prior_entropy - posterior_entropy


def normalize_distribution(weights: List[float]) -> List[float]:
    """Normalize to a valid probability distribution summing to 1.0."""
    total = sum(weights)
    if total == 0.0:
        n = len(weights)
        return [1.0 / n] * n if n > 0 else []
    return [w / total for w in weights]


def uniform_distribution(n: int) -> List[float]:
    """Return uniform distribution over n outcomes."""
    if n <= 0:
        return []
    return [1.0 / n] * n


def max_entropy(n: int) -> float:
    """Maximum possible entropy for n outcomes = log₂(n)."""
    if n <= 0:
        return 0.0
    return math.log2(n)
