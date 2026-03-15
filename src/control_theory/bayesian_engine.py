"""Bayesian confidence engine replacing heuristic confidence increments."""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .entropy import (
    information_gain,
    kl_divergence,
    normalize_distribution,
    shannon_entropy,
    uniform_distribution,
)

logger = logging.getLogger(__name__)

_EPSILON = 1e-15


@dataclass
class BeliefState:
    """
    Discrete probability distribution over state hypotheses.

    Represents the system's belief about which "true state" the world is in.
    This replaces the scalar confidence value with a full distribution.
    """

    hypotheses: List[str]
    probabilities: List[float]

    def entropy(self) -> float:
        """H(belief) in bits."""
        return shannon_entropy(self.probabilities)

    def confidence(self) -> float:
        """Max probability — the 'confidence' in the most likely hypothesis."""
        if not self.probabilities:
            return 0.0
        return max(self.probabilities)

    def most_likely(self) -> str:
        """Return the hypothesis with highest probability."""
        if not self.hypotheses:
            return ""
        idx = max(range(len(self.probabilities)), key=lambda i: self.probabilities[i])
        return self.hypotheses[idx]

    def is_valid(self) -> bool:
        """Check that probabilities sum to ~1.0 and are all non-negative."""
        if not self.probabilities:
            return False
        if any(p < 0.0 for p in self.probabilities):
            return False
        return abs(sum(self.probabilities) - 1.0) < 1e-9


@dataclass
class Observation:
    """An observation (answer to a question, measurement, verification result)."""

    observation_id: str
    channel: str
    value: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)


@dataclass
class LikelihoodModel:
    """
    P(observation | hypothesis) for each hypothesis.

    Maps observation_value -> {hypothesis -> probability}
    """

    name: str
    likelihoods: Dict[str, Dict[str, float]]

    def get_likelihood(self, observation_value: str, hypothesis: str) -> float:
        """Return P(observation_value | hypothesis), default 1/n if unknown."""
        obs_likelihoods = self.likelihoods.get(observation_value)
        if obs_likelihoods is None:
            n = len(self.likelihoods)
            return 1.0 / n if n > 0 else 1.0
        return obs_likelihoods.get(hypothesis, 1.0 / max(len(obs_likelihoods), 1))


@dataclass
class UpdateResult:
    """Result of a Bayesian update step."""

    prior: BeliefState
    posterior: BeliefState
    observation: Observation
    prior_entropy: float
    posterior_entropy: float
    information_gained: float
    kl_from_prior: float


class BayesianConfidenceEngine:
    """
    Replaces heuristic confidence increments with Bayesian updates.

    Instead of:
        self.confidence += 0.1  (magnify)
        self.confidence += 0.05 (simplify)
        self.confidence += 0.2  (solidify)

    Does:
        posterior = bayes_update(prior, observation, likelihood_model)
        info_gained = H(prior) - H(posterior)

    The confidence is derived FROM the belief, not incremented arbitrarily.
    """

    def __init__(self, default_hypotheses: Optional[List[str]] = None):
        """
        Initialize with default hypothesis space.

        Default hypotheses model the system's understanding quality:
        ["fully_understood", "mostly_understood", "partially_understood",
         "poorly_understood", "not_understood"]
        """
        self.default_hypotheses = default_hypotheses or [
            "fully_understood",
            "mostly_understood",
            "partially_understood",
            "poorly_understood",
            "not_understood",
        ]
        self.update_history: List[UpdateResult] = []

    def create_prior(self, hypotheses: Optional[List[str]] = None) -> BeliefState:
        """
        Create a maximum-entropy (uniform) prior.
        This is the "I know nothing" starting state.
        """
        hyps = hypotheses or self.default_hypotheses
        return BeliefState(
            hypotheses=hyps,
            probabilities=uniform_distribution(len(hyps)),
        )

    def update(
        self,
        belief: BeliefState,
        observation: Observation,
        likelihood_model: LikelihoodModel,
    ) -> UpdateResult:
        """
        Perform Bayesian update: P(H|O) ∝ P(O|H) × P(H)

        Steps:
        1. Compute unnormalized posterior: P(O|Hᵢ) × P(Hᵢ) for each hypothesis
        2. Normalize to get P(Hᵢ|O)
        3. Compute entropy change and information gain
        4. Return UpdateResult with full audit trail
        """
        prior_entropy = belief.entropy()

        unnormalized = [
            likelihood_model.get_likelihood(observation.value, h) * p
            for h, p in zip(belief.hypotheses, belief.probabilities)
        ]
        posterior_probs = normalize_distribution(unnormalized)

        posterior = BeliefState(
            hypotheses=belief.hypotheses,
            probabilities=posterior_probs,
        )
        posterior_entropy = posterior.entropy()
        ig = information_gain(prior_entropy, posterior_entropy)
        kl = kl_divergence(posterior_probs, belief.probabilities)

        result = UpdateResult(
            prior=belief,
            posterior=posterior,
            observation=observation,
            prior_entropy=prior_entropy,
            posterior_entropy=posterior_entropy,
            information_gained=ig,
            kl_from_prior=kl,
        )
        self.update_history.append(result)
        return result

    def select_optimal_question(
        self,
        belief: BeliefState,
        candidate_questions: List[str],
        likelihood_models: Dict[str, LikelihoodModel],
    ) -> Tuple[str, float]:
        """
        Select the question that maximizes expected information gain.

        q* = argmax_q E[IG(belief | answer(q))]
           = argmax_q E[H(belief) - H(belief | answer(q))]

        For each candidate question:
        1. Consider all possible answers
        2. For each answer, compute the posterior entropy
        3. Weight by probability of getting that answer
        4. Expected IG = H(prior) - Σ P(answer) × H(posterior|answer)

        Returns:
            (best_question, expected_information_gain)
        """
        prior_entropy = belief.entropy()
        best_q = candidate_questions[0] if candidate_questions else ""
        best_eig = 0.0

        for q in candidate_questions:
            lm = likelihood_models.get(q)
            if lm is None:
                continue
            expected_posterior_entropy = 0.0
            for obs_value, hyp_likelihoods in lm.likelihoods.items():
                # Compute P(obs_value) = Σ P(obs|hyp) * P(hyp)
                p_obs = sum(
                    hyp_likelihoods.get(h, _EPSILON) * p
                    for h, p in zip(belief.hypotheses, belief.probabilities)
                )
                if p_obs <= 0.0:
                    continue
                # Compute posterior given this obs_value
                unnormalized = [
                    hyp_likelihoods.get(h, _EPSILON) * p
                    for h, p in zip(belief.hypotheses, belief.probabilities)
                ]
                posterior_probs = normalize_distribution(unnormalized)
                h_posterior = shannon_entropy(posterior_probs)
                expected_posterior_entropy += p_obs * h_posterior

            eig = prior_entropy - expected_posterior_entropy
            if eig > best_eig:
                best_eig = eig
                best_q = q

        return best_q, best_eig

    def get_confidence_from_belief(self, belief: BeliefState) -> float:
        """
        Extract a scalar confidence from the belief state.

        Confidence = P(fully_understood) * 1.0 + P(mostly_understood) * 0.75
                   + P(partially_understood) * 0.5 + P(poorly_understood) * 0.25
                   + P(not_understood) * 0.0

        This gives a [0,1] scalar that is DERIVED from the belief,
        not an independent heuristic variable.
        """
        weights = {
            "fully_understood": 1.0,
            "mostly_understood": 0.75,
            "partially_understood": 0.5,
            "poorly_understood": 0.25,
            "not_understood": 0.0,
        }
        confidence = 0.0
        for h, p in zip(belief.hypotheses, belief.probabilities):
            confidence += weights.get(h, 0.0) * p
        return confidence

    def create_magnify_likelihood(self) -> LikelihoodModel:
        """
        Create the likelihood model for a 'magnify' (domain expansion) observation.

        When domain is expanded successfully, it's more likely the system
        understands well. When it struggles, it's more likely understanding is poor.
        """
        return LikelihoodModel(
            name="magnify",
            likelihoods={
                "success": {
                    "fully_understood": 0.90,
                    "mostly_understood": 0.70,
                    "partially_understood": 0.40,
                    "poorly_understood": 0.15,
                    "not_understood": 0.05,
                },
                "failure": {
                    "fully_understood": 0.10,
                    "mostly_understood": 0.30,
                    "partially_understood": 0.60,
                    "poorly_understood": 0.85,
                    "not_understood": 0.95,
                },
            },
        )

    def create_simplify_likelihood(self) -> LikelihoodModel:
        """
        Create the likelihood model for a 'simplify' observation.
        """
        return LikelihoodModel(
            name="simplify",
            likelihoods={
                "success": {
                    "fully_understood": 0.85,
                    "mostly_understood": 0.65,
                    "partially_understood": 0.45,
                    "poorly_understood": 0.20,
                    "not_understood": 0.10,
                },
                "failure": {
                    "fully_understood": 0.15,
                    "mostly_understood": 0.35,
                    "partially_understood": 0.55,
                    "poorly_understood": 0.80,
                    "not_understood": 0.90,
                },
            },
        )

    def create_solidify_likelihood(self) -> LikelihoodModel:
        """
        Create the likelihood model for a 'solidify' observation.
        Solidification with high quality = strong evidence of understanding.
        """
        return LikelihoodModel(
            name="solidify",
            likelihoods={
                "success": {
                    "fully_understood": 0.95,
                    "mostly_understood": 0.75,
                    "partially_understood": 0.35,
                    "poorly_understood": 0.10,
                    "not_understood": 0.02,
                },
                "failure": {
                    "fully_understood": 0.05,
                    "mostly_understood": 0.25,
                    "partially_understood": 0.65,
                    "poorly_understood": 0.90,
                    "not_understood": 0.98,
                },
            },
        )

    def create_gate_check_likelihood(self) -> LikelihoodModel:
        """
        Create the likelihood model for a gate check passing/failing.
        """
        return LikelihoodModel(
            name="gate_check",
            likelihoods={
                "pass": {
                    "fully_understood": 0.92,
                    "mostly_understood": 0.72,
                    "partially_understood": 0.38,
                    "poorly_understood": 0.12,
                    "not_understood": 0.04,
                },
                "fail": {
                    "fully_understood": 0.08,
                    "mostly_understood": 0.28,
                    "partially_understood": 0.62,
                    "poorly_understood": 0.88,
                    "not_understood": 0.96,
                },
            },
        )

    def get_total_information_gained(self) -> float:
        """Sum of all information gains across all updates."""
        return sum(r.information_gained for r in self.update_history)

    def get_entropy_trajectory(self) -> List[float]:
        """List of entropy values after each update — should be non-increasing."""
        return [r.posterior_entropy for r in self.update_history]
