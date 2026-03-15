"""
Gap-closing tests for the Bayesian Confidence Engine.

Each test targets a specific gap identified in the structural audit:
- GAP: "No H(X) computation"
- GAP: "No Bayesian posterior"
- GAP: "IG is heuristic (+0.1)"
- GAP: "No uncertainty reduction mechanism"
- GAP: "No optimal question selection"
- GAP: "No formal uncertainty measure"
"""

import math

import pytest

from control_theory.entropy import (
    information_gain,
    kl_divergence,
    max_entropy,
    normalize_distribution,
    shannon_entropy,
    uniform_distribution,
)
from control_theory.bayesian_engine import (
    BayesianConfidenceEngine,
    BeliefState,
    LikelihoodModel,
    Observation,
    UpdateResult,
)


class TestShannonEntropy:
    """GAP: 'No H(X) computation' — must prove entropy is computable."""

    def test_entropy_of_uniform_distribution(self):
        """Uniform distribution has maximum entropy = log₂(n)."""
        probs = [0.25, 0.25, 0.25, 0.25]
        H = shannon_entropy(probs)
        assert abs(H - 2.0) < 1e-10  # log₂(4) = 2.0

    def test_entropy_of_point_mass(self):
        """Point mass has zero entropy."""
        probs = [1.0, 0.0, 0.0]
        H = shannon_entropy(probs)
        assert abs(H - 0.0) < 1e-10

    def test_entropy_non_negative(self):
        """H(X) >= 0 for all valid distributions."""
        for probs in [[0.5, 0.5], [0.9, 0.1], [0.01, 0.99], [1.0]]:
            assert shannon_entropy(probs) >= 0.0

    def test_entropy_maximum_is_uniform(self):
        """Uniform achieves max entropy."""
        n = 5
        uniform = [1 / n] * n
        non_uniform = [0.5, 0.2, 0.15, 0.1, 0.05]
        assert shannon_entropy(uniform) > shannon_entropy(non_uniform)

    def test_entropy_empty_distribution(self):
        """Empty distribution returns 0."""
        assert shannon_entropy([]) == 0.0

    def test_binary_entropy_symmetric(self):
        """H(p, 1-p) = H(1-p, p)."""
        H1 = shannon_entropy([0.3, 0.7])
        H2 = shannon_entropy([0.7, 0.3])
        assert abs(H1 - H2) < 1e-10


class TestKLDivergence:
    """GAP: 'No formal uncertainty measure' — prove KL divergence works."""

    def test_kl_divergence_non_negative(self):
        """D_KL(P || Q) >= 0 (Gibbs' inequality)."""
        P = [0.5, 0.3, 0.2]
        Q = [0.33, 0.33, 0.34]
        assert kl_divergence(P, Q) >= 0.0

    def test_kl_divergence_zero_for_identical(self):
        """D_KL(P || P) = 0."""
        P = [0.5, 0.3, 0.2]
        assert abs(kl_divergence(P, P)) < 1e-10

    def test_kl_divergence_asymmetric(self):
        """D_KL(P||Q) ≠ D_KL(Q||P) in general."""
        P = [0.9, 0.1]
        Q = [0.5, 0.5]
        assert abs(kl_divergence(P, Q) - kl_divergence(Q, P)) > 0.01


class TestBayesianUpdate:
    """GAP: 'Heuristic +0.1' — prove updates are observation-dependent."""

    def test_posterior_sums_to_one(self):
        """Posterior must be a valid probability distribution."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        obs = Observation(observation_id="obs1", channel="test", value="success")
        lm = engine.create_magnify_likelihood()
        result = engine.update(belief, obs, lm)
        total = sum(result.posterior.probabilities)
        assert abs(total - 1.0) < 1e-10

    def test_different_observations_yield_different_posteriors(self):
        """GAP: Heuristic always adds same amount. Bayesian: different obs → different update."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()

        obs_success = Observation(observation_id="o1", channel="test", value="success")
        obs_failure = Observation(observation_id="o2", channel="test", value="failure")
        lm = engine.create_magnify_likelihood()

        result_success = engine.update(belief, obs_success, lm)
        result_failure = engine.update(belief, obs_failure, lm)

        # Must produce DIFFERENT posteriors
        assert result_success.posterior.probabilities != result_failure.posterior.probabilities

    def test_information_gain_non_negative(self):
        """IG = H(prior) - H(posterior) >= 0 for informative observations."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        obs = Observation(observation_id="o1", channel="test", value="success")
        lm = engine.create_magnify_likelihood()
        result = engine.update(belief, obs, lm)
        assert result.information_gained >= 0.0

    def test_entropy_decreases_with_evidence(self):
        """H(posterior) <= H(prior) for informative observations."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        obs = Observation(observation_id="o1", channel="test", value="success")
        lm = engine.create_magnify_likelihood()
        result = engine.update(belief, obs, lm)
        assert result.posterior_entropy <= result.prior_entropy + 1e-10

    def test_repeated_evidence_increases_confidence(self):
        """Multiple consistent observations should increase confidence monotonically."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm = engine.create_magnify_likelihood()

        confidences = [engine.get_confidence_from_belief(belief)]
        for i in range(5):
            obs = Observation(observation_id=f"o{i}", channel="test", value="success")
            result = engine.update(belief, obs, lm)
            belief = result.posterior
            confidences.append(engine.get_confidence_from_belief(belief))

        # Confidence should be strictly increasing
        for i in range(len(confidences) - 1):
            assert confidences[i + 1] > confidences[i]

    def test_contradictory_evidence_decreases_confidence(self):
        """Failure observation after successes should decrease confidence."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm_magnify = engine.create_magnify_likelihood()

        # Build up some confidence with successes
        for i in range(3):
            obs = Observation(observation_id=f"s{i}", channel="test", value="success")
            result = engine.update(belief, obs, lm_magnify)
            belief = result.posterior

        conf_before_failure = engine.get_confidence_from_belief(belief)

        # Now observe a failure
        obs_fail = Observation(observation_id="f1", channel="test", value="failure")
        result = engine.update(belief, obs_fail, lm_magnify)
        conf_after_failure = engine.get_confidence_from_belief(result.posterior)

        assert conf_after_failure < conf_before_failure


class TestQuestionSelection:
    """GAP: 'No optimal question selection' — prove argmax IG works."""

    def test_question_selection_returns_best_question(self):
        """select_optimal_question should return a question and expected IG."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()

        questions = ["q_informative", "q_uninformative"]
        likelihood_models = {}

        # Informative question has very different likelihoods per hypothesis
        likelihood_models["q_informative"] = LikelihoodModel(
            name="informative",
            likelihoods={
                "yes": {
                    "fully_understood": 0.9,
                    "mostly_understood": 0.7,
                    "partially_understood": 0.3,
                    "poorly_understood": 0.1,
                    "not_understood": 0.05,
                },
                "no": {
                    "fully_understood": 0.1,
                    "mostly_understood": 0.3,
                    "partially_understood": 0.7,
                    "poorly_understood": 0.9,
                    "not_understood": 0.95,
                },
            },
        )

        # Uninformative question has same likelihoods regardless of hypothesis
        likelihood_models["q_uninformative"] = LikelihoodModel(
            name="uninformative",
            likelihoods={
                "yes": {
                    "fully_understood": 0.5,
                    "mostly_understood": 0.5,
                    "partially_understood": 0.5,
                    "poorly_understood": 0.5,
                    "not_understood": 0.5,
                },
                "no": {
                    "fully_understood": 0.5,
                    "mostly_understood": 0.5,
                    "partially_understood": 0.5,
                    "poorly_understood": 0.5,
                    "not_understood": 0.5,
                },
            },
        )

        best_q, expected_ig = engine.select_optimal_question(
            belief, questions, likelihood_models
        )
        assert best_q == "q_informative"
        assert expected_ig > 0.0

    def test_expected_ig_non_negative(self):
        """Expected information gain must be >= 0."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm = engine.create_magnify_likelihood()
        _, expected_ig = engine.select_optimal_question(belief, ["q1"], {"q1": lm})
        assert expected_ig >= 0.0


class TestEntropyTrajectory:
    """GAP: 'No uncertainty reduction mechanism' — prove entropy decreases over time."""

    def test_entropy_trajectory_non_increasing(self):
        """With consistent evidence, entropy should trend downward."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm = engine.create_magnify_likelihood()

        for i in range(10):
            obs = Observation(observation_id=f"o{i}", channel="test", value="success")
            result = engine.update(belief, obs, lm)
            belief = result.posterior

        trajectory = engine.get_entropy_trajectory()
        assert len(trajectory) == 10

        # Overall trend should be decreasing (allow small fluctuations)
        assert trajectory[-1] < trajectory[0]

    def test_total_information_gained_positive(self):
        """Total IG across all updates should be positive with informative evidence."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        lm = engine.create_magnify_likelihood()

        for i in range(5):
            obs = Observation(observation_id=f"o{i}", channel="test", value="success")
            result = engine.update(belief, obs, lm)
            belief = result.posterior

        assert engine.get_total_information_gained() > 0.0


class TestConfidenceDerivation:
    """GAP: 'Confidence is scalar +0.1' — prove confidence is DERIVED from belief."""

    def test_uniform_prior_has_low_confidence(self):
        """Uniform (maximum ignorance) should yield low confidence."""
        engine = BayesianConfidenceEngine()
        belief = engine.create_prior()
        conf = engine.get_confidence_from_belief(belief)
        assert conf <= 0.5 + 1e-9  # Uniform over 5 hypotheses should be low

    def test_point_mass_has_full_confidence(self):
        """Point mass on 'fully_understood' = confidence 1.0."""
        engine = BayesianConfidenceEngine()
        hypotheses = engine.default_hypotheses
        belief = BeliefState(
            hypotheses=hypotheses,
            probabilities=[1.0] + [0.0] * (len(hypotheses) - 1),
        )
        conf = engine.get_confidence_from_belief(belief)
        assert abs(conf - 1.0) < 1e-10

    def test_confidence_bounded_zero_one(self):
        """Derived confidence always in [0, 1]."""
        engine = BayesianConfidenceEngine()
        for probs in [
            [0.2] * 5,
            [1.0, 0, 0, 0, 0],
            [0, 0, 0, 0, 1.0],
            [0.5, 0.3, 0.1, 0.05, 0.05],
        ]:
            belief = BeliefState(
                hypotheses=engine.default_hypotheses, probabilities=probs
            )
            conf = engine.get_confidence_from_belief(belief)
            assert 0.0 <= conf <= 1.0


class TestLikelihoodModels:
    """Test that the built-in likelihood models are valid."""

    def test_magnify_likelihood_valid(self):
        engine = BayesianConfidenceEngine()
        lm = engine.create_magnify_likelihood()
        assert len(lm.likelihoods) >= 2  # At least success/failure

    def test_simplify_likelihood_valid(self):
        engine = BayesianConfidenceEngine()
        lm = engine.create_simplify_likelihood()
        assert len(lm.likelihoods) >= 2

    def test_solidify_likelihood_valid(self):
        engine = BayesianConfidenceEngine()
        lm = engine.create_solidify_likelihood()
        assert len(lm.likelihoods) >= 2

    def test_gate_check_likelihood_valid(self):
        engine = BayesianConfidenceEngine()
        lm = engine.create_gate_check_likelihood()
        assert len(lm.likelihoods) >= 2
