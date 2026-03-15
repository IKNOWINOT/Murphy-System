"""
Tests for AdaptiveObserver (Gap F — QuestionSelector wired to ObservationFunction).

Proves:
  - The highest-gain question is selected first.
  - Entropy decreases (or stabilises) across the observation loop.
  - Loop terminates when entropy target is reached.
"""

import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from control_theory.canonical_state import CanonicalStateVector
from control_theory.infinity_metric import (
    CandidateQuestion,
    EntropyTracker,
    QuestionSelector,
)
from control_theory.observation_model import (
    AdaptiveObserver,
    ObservationChannel,
    ObservationData,
    ObservationFunction,
)


def _make_candidates(n: int = 3) -> list:
    """Build n CandidateQuestion objects with decreasing information gain."""
    return [
        CandidateQuestion(
            question_id=f"q{i}",
            description=f"Question {i}",
            expected_H_prior=1.0,
            expected_H_posterior=1.0 - (n - i) * 0.2,  # higher index → less gain
            metadata={"channel": ObservationChannel.INQUISITORY.value},
        )
        for i in range(n)
    ]


def _make_observer() -> AdaptiveObserver:
    obs_fn = ObservationFunction()
    selector = QuestionSelector()
    tracker = EntropyTracker()
    return AdaptiveObserver(obs_fn, selector, tracker)


class TestSelectAndObserve(unittest.TestCase):
    """Single-step select + observe."""

    def test_returns_observation_data_and_question(self):
        observer = _make_observer()
        state = CanonicalStateVector()
        candidates = _make_candidates(3)
        obs, question = observer.select_and_observe(state, candidates, add_noise=False)
        self.assertIsInstance(obs, ObservationData)
        self.assertIsNotNone(question)

    def test_selects_highest_gain_question(self):
        """The question with the highest IG should be selected."""
        observer = _make_observer()
        state = CanonicalStateVector()
        # q0 has IG = 1.0 - 0.4 = 0.6 (highest), q2 has IG = 0.0
        candidates = _make_candidates(3)
        _, selected = observer.select_and_observe(state, candidates, add_noise=False)
        self.assertIsNotNone(selected)
        # The best question is q0 (highest IG among candidates)
        best = max(candidates, key=lambda q: q.information_gain)
        self.assertEqual(selected.question_id, best.question_id)

    def test_empty_candidates_returns_empty_obs(self):
        observer = _make_observer()
        state = CanonicalStateVector()
        obs, question = observer.select_and_observe(state, [], add_noise=False)
        self.assertIsNone(question)
        self.assertIsInstance(obs, ObservationData)

    def test_channel_metadata_used(self):
        """Channel from question metadata should be used for observation."""
        observer = _make_observer()
        state = CanonicalStateVector()
        candidates = [
            CandidateQuestion(
                question_id="q_sensor",
                description="Sensor telemetry",
                expected_H_prior=1.0,
                expected_H_posterior=0.3,
                metadata={"channel": ObservationChannel.SENSOR_TELEMETRY.value},
            )
        ]
        obs, _ = observer.select_and_observe(state, candidates, add_noise=False)
        self.assertEqual(obs.channel, ObservationChannel.SENSOR_TELEMETRY)


class TestObserveLoop(unittest.TestCase):
    """Iterative observation loop."""

    def test_loop_returns_list_of_observation_data(self):
        observer = _make_observer()
        state = CanonicalStateVector()
        candidates = _make_candidates(5)
        results = observer.observe_loop(state, candidates, max_steps=5)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r, ObservationData)

    def test_loop_respects_max_steps(self):
        """Loop should not exceed max_steps observations."""
        observer = _make_observer()
        state = CanonicalStateVector(
            uncertainty_data=0.5,
            uncertainty_authority=0.5,
            uncertainty_information=0.5,
        )
        candidates = _make_candidates(10)
        # Use a very low entropy_target to avoid early stopping
        results = observer.observe_loop(
            state, candidates, max_steps=3, entropy_target=0.0
        )
        self.assertLessEqual(len(results), 3)

    def test_loop_terminates_early_when_entropy_target_reached(self):
        """Loop stops when entropy ≤ entropy_target."""
        observer = _make_observer()
        # State with zero uncertainty → entropy is low (uniform distribution over 5 = ~2.32 bits)
        state = CanonicalStateVector()  # all zeros → uniform → ~2.32 bits
        # Set entropy_target very high so it terminates after first step
        candidates = _make_candidates(5)
        results = observer.observe_loop(
            state, candidates, max_steps=100, entropy_target=100.0
        )
        # With such a high target, should stop after 1 step
        self.assertEqual(len(results), 1)

    def test_loop_records_entropy_history(self):
        """EntropyTracker should record at least one entry per step."""
        observer = _make_observer()
        state = CanonicalStateVector()
        candidates = _make_candidates(3)
        initial_history_len = len(observer.entropy_tracker.history)
        results = observer.observe_loop(
            state, candidates, max_steps=3, entropy_target=0.0
        )
        final_history_len = len(observer.entropy_tracker.history)
        self.assertGreater(final_history_len, initial_history_len)
        self.assertEqual(final_history_len - initial_history_len, len(results))

    def test_loop_does_not_repeat_same_question(self):
        """Each question should be used at most once."""
        observer = _make_observer()
        state = CanonicalStateVector(
            uncertainty_data=0.9,
            uncertainty_authority=0.9,
        )
        candidates = _make_candidates(3)
        results = observer.observe_loop(
            state, candidates, max_steps=10, entropy_target=0.0
        )
        # At most 3 steps (one per candidate)
        self.assertLessEqual(len(results), 3)

    def test_empty_candidates_loop_returns_empty(self):
        """Empty candidate list → empty result list."""
        observer = _make_observer()
        state = CanonicalStateVector()
        results = observer.observe_loop(state, [], max_steps=5, entropy_target=0.0)
        self.assertEqual(results, [])

    def test_entropy_non_increasing_through_loop(self):
        """
        Entropy recorded in tracker should be non-increasing across steps
        (each step reduces or maintains entropy since state is unchanged
        and we're merely recording).

        This test validates that the tracker history is stable when
        the state is constant (zero uncertainty → same entropy each step).
        """
        observer = _make_observer()
        # State with all-zero uncertainties has constant entropy
        state = CanonicalStateVector()
        candidates = _make_candidates(4)
        observer.observe_loop(state, candidates, max_steps=4, entropy_target=0.0)
        history = observer.entropy_tracker.history
        if len(history) > 1:
            for i in range(1, len(history)):
                # Constant state → entropy should be constant (non-increasing)
                self.assertLessEqual(history[i], history[i - 1] + 1e-9)


class TestAdaptiveObserverIntegration(unittest.TestCase):
    """Integration: multiple steps with realistic state."""

    def test_full_loop_with_multiple_questions(self):
        """Full loop runs without errors and returns observations."""
        observer = _make_observer()
        state = CanonicalStateVector(
            uncertainty_data=0.8,
            uncertainty_information=0.7,
        )
        candidates = [
            CandidateQuestion(
                question_id=f"q{i}",
                description=f"Q{i}",
                expected_H_prior=2.0,
                expected_H_posterior=2.0 - i * 0.3,
                metadata={"channel": ObservationChannel.INQUISITORY.value},
            )
            for i in range(5)
        ]
        results = observer.observe_loop(state, candidates, max_steps=5, entropy_target=0.0)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r, ObservationData)


if __name__ == "__main__":
    unittest.main()
