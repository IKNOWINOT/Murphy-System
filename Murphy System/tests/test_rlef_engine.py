# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for rlef_engine module.

Covers reward computation, reward weight validation, preference pair
generation, retrain threshold logic, DPO stub mode, full RLEF cycle,
and edge cases with all-success or all-failure traces.
"""

from __future__ import annotations

import os

import pytest


from murphy_foundation_model.rlef_engine import (
    PreferencePair,
    RLEFConfig,
    RLEFEngine,
)


def _labeled_trace(
    intent="test_intent",
    success=1.0,
    efficiency=0.8,
    safety=0.9,
    calibration=0.7,
    human_agreement=0.6,
):
    return {
        "intent": intent,
        "labels": {
            "success": success,
            "efficiency": efficiency,
            "safety_score": safety,
            "confidence_calibration": calibration,
            "human_agreement": human_agreement,
        },
    }


class TestRewardComputation:
    """Test reward computation with known inputs."""

    def test_perfect_trace_reward(self):
        engine = RLEFEngine()
        reward = engine.compute_reward(
            {},
            {
                "success": 1.0,
                "efficiency": 1.0,
                "safety_score": 1.0,
                "confidence_calibration": 1.0,
                "human_agreement": 1.0,
            },
        )
        assert reward == pytest.approx(1.0)

    def test_zero_labels_reward(self):
        engine = RLEFEngine()
        reward = engine.compute_reward(
            {},
            {
                "success": 0.0,
                "efficiency": 0.0,
                "safety_score": 0.0,
                "confidence_calibration": 0.0,
                "human_agreement": 0.0,
            },
        )
        # human_agreement=0 → human_override=1 → contribution = 0.1*(1-1) = 0
        assert reward == pytest.approx(0.0)

    def test_reward_uses_labels_from_trace(self):
        engine = RLEFEngine()
        trace = _labeled_trace(success=1.0, efficiency=0.5, safety=0.5,
                               calibration=0.5, human_agreement=1.0)
        reward = engine.compute_reward(trace)
        expected = 0.4 * 1.0 + 0.2 * 0.5 + 0.2 * 0.5 + 0.1 * 0.5 + 0.1 * 1.0
        assert reward == pytest.approx(expected, abs=0.001)

    def test_reward_empty_labels_returns_zero(self):
        engine = RLEFEngine()
        reward = engine.compute_reward({}, {})
        assert reward == 0.0

    def test_reward_no_labels_at_all(self):
        engine = RLEFEngine()
        reward = engine.compute_reward({})
        assert reward == 0.0

    def test_reward_clamped_to_0_1(self):
        engine = RLEFEngine()
        reward = engine.compute_reward(
            {},
            {"success": 1.0, "efficiency": 1.0, "safety_score": 1.0,
             "confidence_calibration": 1.0, "human_agreement": 1.0},
        )
        assert 0.0 <= reward <= 1.0

    def test_reward_with_human_override_key(self):
        engine = RLEFEngine()
        reward = engine.compute_reward(
            {},
            {"success": 1.0, "efficiency": 0.5, "safety_score": 0.5,
             "calibration": 0.5, "human_override": 0.0},
        )
        # human_override=0 → contribution = 0.1*(1-0) = 0.1
        expected = 0.4 * 1.0 + 0.2 * 0.5 + 0.2 * 0.5 + 0.1 * 0.5 + 0.1 * 1.0
        assert reward == pytest.approx(expected, abs=0.001)


class TestRewardWeights:
    """Test reward weights sum to 1.0."""

    def test_default_weights_sum_to_1(self):
        config = RLEFConfig()
        total = sum(config.reward_weights.values())
        assert total == pytest.approx(1.0)

    def test_custom_weights(self):
        custom = {"success": 0.5, "efficiency": 0.2, "safety": 0.2,
                  "calibration": 0.05, "human_agreement": 0.05}
        config = RLEFConfig(reward_weights=custom)
        assert sum(config.reward_weights.values()) == pytest.approx(1.0)

    def test_weight_keys(self):
        config = RLEFConfig()
        expected_keys = {"success", "efficiency", "safety", "calibration", "human_agreement"}
        assert set(config.reward_weights.keys()) == expected_keys


class TestPreferencePairGeneration:
    """Test preference pair generation from mixed traces."""

    def test_pairs_from_good_and_bad_traces(self):
        engine = RLEFEngine()
        traces = [
            _labeled_trace(intent="goal", success=1.0, efficiency=0.9),
            _labeled_trace(intent="goal", success=0.0, efficiency=0.2),
        ]
        pairs = engine.create_preference_pairs(traces)
        assert len(pairs) >= 1
        assert all(isinstance(p, PreferencePair) for p in pairs)
        assert pairs[0].chosen_reward > pairs[0].rejected_reward

    def test_no_pairs_from_single_trace(self):
        engine = RLEFEngine()
        traces = [_labeled_trace(intent="solo")]
        pairs = engine.create_preference_pairs(traces)
        assert len(pairs) == 0

    def test_no_pairs_when_gap_too_small(self):
        engine = RLEFEngine()
        traces = [
            _labeled_trace(intent="close", success=0.8, efficiency=0.8,
                           safety=0.8, calibration=0.8, human_agreement=0.8),
            _labeled_trace(intent="close", success=0.8, efficiency=0.78,
                           safety=0.8, calibration=0.8, human_agreement=0.8),
        ]
        pairs = engine.create_preference_pairs(traces)
        # Reward difference < 0.1 → no pairs
        assert len(pairs) == 0

    def test_multiple_intents_generate_separate_pairs(self):
        engine = RLEFEngine()
        traces = [
            _labeled_trace(intent="A", success=1.0),
            _labeled_trace(intent="A", success=0.0),
            _labeled_trace(intent="B", success=1.0),
            _labeled_trace(intent="B", success=0.0),
        ]
        pairs = engine.create_preference_pairs(traces)
        intents = {p.intent for p in pairs}
        assert "A" in intents
        assert "B" in intents

    def test_pairs_accumulate_in_buffer(self):
        engine = RLEFEngine()
        traces = [
            _labeled_trace(intent="x", success=1.0),
            _labeled_trace(intent="x", success=0.0),
        ]
        engine.create_preference_pairs(traces)
        engine.create_preference_pairs(traces)
        assert len(engine._preference_buffer) >= 2


class TestShouldRetrain:
    """Test should_retrain threshold check."""

    def test_below_threshold_returns_false(self):
        config = RLEFConfig(min_preference_pairs=1000)
        engine = RLEFEngine(config=config)
        traces = [
            _labeled_trace(intent="t", success=1.0),
            _labeled_trace(intent="t", success=0.0),
        ]
        assert engine.should_retrain(traces) is False

    def test_above_threshold_returns_true(self):
        config = RLEFConfig(min_preference_pairs=2)
        engine = RLEFEngine(config=config)
        # Generate enough pairs
        traces = [
            _labeled_trace(intent="t", success=1.0),
            _labeled_trace(intent="t", success=0.0),
        ]
        # Call multiple times to accumulate
        for _ in range(5):
            engine.create_preference_pairs(traces)
        result = engine.should_retrain(traces)
        assert result is True


class TestDPOTrainingStub:
    """Test DPO training stub mode."""

    def test_insufficient_data(self):
        engine = RLEFEngine(config=RLEFConfig(min_preference_pairs=100))
        result = engine.train_dpo(model=None, preference_pairs=[])
        assert result["status"] == "insufficient_data"

    def test_train_dpo_without_torch(self):
        config = RLEFConfig(min_preference_pairs=1)
        engine = RLEFEngine(config=config)
        pair = PreferencePair(
            intent="test",
            chosen_trace=_labeled_trace(success=1.0),
            rejected_trace=_labeled_trace(success=0.0),
            chosen_reward=0.9,
            rejected_reward=0.1,
        )
        result = engine.train_dpo(model=None, preference_pairs=[pair])
        # Without torch or with None model → skipped
        assert result["status"] in ("skipped", "insufficient_data")


class TestFullRLEFCycle:
    """Test full RLEF cycle (stub mode)."""

    def test_cycle_waiting_insufficient_pairs(self):
        engine = RLEFEngine(config=RLEFConfig(min_preference_pairs=1000))
        traces = [
            _labeled_trace(intent="cycle", success=1.0),
            _labeled_trace(intent="cycle", success=0.0),
        ]
        result = engine.run_rlef_cycle(model=None, traces=traces)
        assert result["status"] == "waiting"
        assert "pairs_buffered" in result
        assert "pairs_needed" in result


class TestEdgeCases:
    """Test edge cases: all success, all failure."""

    def test_all_success_no_pairs(self):
        engine = RLEFEngine()
        traces = [
            _labeled_trace(intent="same", success=1.0, efficiency=0.9,
                           safety=0.9, calibration=0.9, human_agreement=0.9)
            for _ in range(5)
        ]
        pairs = engine.create_preference_pairs(traces)
        # All same reward → no gap ≥ 0.1 → no pairs
        assert len(pairs) == 0

    def test_all_failure_no_pairs(self):
        engine = RLEFEngine()
        traces = [
            _labeled_trace(intent="same", success=0.0, efficiency=0.0,
                           safety=0.0, calibration=0.0, human_agreement=0.0)
            for _ in range(5)
        ]
        pairs = engine.create_preference_pairs(traces)
        assert len(pairs) == 0

    def test_empty_traces_no_pairs(self):
        engine = RLEFEngine()
        pairs = engine.create_preference_pairs([])
        assert len(pairs) == 0
