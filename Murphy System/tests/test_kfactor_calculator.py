"""Tests for the K-Factor Calculator module."""

import os

import pytest
from src.kfactor_calculator import KFactorCalculator, KFactorInput


@pytest.fixture
def calc():
    return KFactorCalculator()


def _make_input(
    recall_confidence=0.5,
    impact_weight=0.5,
    variation_frequency=0.3,
    outcome_consistency=0.8,
    novelty_rate=0.2,
) -> KFactorInput:
    return KFactorInput(
        recall_confidence=recall_confidence,
        impact_weight=impact_weight,
        variation_frequency=variation_frequency,
        outcome_consistency=outcome_consistency,
        novelty_rate=novelty_rate,
    )


class TestKFactorComputation:
    def test_high_recall_consistency_low_novelty_gives_low_kfactor(self, calc):
        inp = _make_input(
            recall_confidence=0.95,
            impact_weight=0.9,
            variation_frequency=0.05,
            outcome_consistency=0.95,
            novelty_rate=0.05,
        )
        result = calc.compute(inp)
        assert result.k_factor < 0.3

    def test_low_recall_high_variation_novelty_gives_high_kfactor(self, calc):
        inp = _make_input(
            recall_confidence=0.05,
            impact_weight=0.1,
            variation_frequency=0.9,
            outcome_consistency=0.1,
            novelty_rate=0.9,
        )
        result = calc.compute(inp)
        assert result.k_factor > 0.6

    def test_kfactor_clamped_between_0_and_1(self, calc):
        for rc, vf, nr in [(0.0, 1.0, 1.0), (1.0, 0.0, 0.0), (0.5, 0.5, 0.5)]:
            inp = _make_input(recall_confidence=rc, variation_frequency=vf, novelty_rate=nr)
            result = calc.compute(inp)
            assert 0.0 <= result.k_factor <= 1.0

    def test_components_sum_equals_kfactor(self, calc):
        inp = _make_input(
            recall_confidence=0.4,
            impact_weight=0.5,
            variation_frequency=0.3,
            outcome_consistency=0.7,
            novelty_rate=0.2,
        )
        result = calc.compute(inp)
        component_sum = sum(result.components.values())
        assert abs(component_sum - result.k_factor) < 1e-9

    def test_all_five_components_present(self, calc):
        inp = _make_input()
        result = calc.compute(inp)
        assert set(result.components.keys()) == {
            "recall", "impact", "variation", "consistency", "novelty"
        }


class TestRecommendedStrategy:
    def test_high_novelty_gives_thompson_sampling(self, calc):
        inp = _make_input(novelty_rate=0.7)
        result = calc.compute(inp)
        assert result.recommended_strategy == "thompson_sampling"

    def test_moderate_novelty_gives_ucb(self, calc):
        inp = _make_input(novelty_rate=0.4)
        result = calc.compute(inp)
        assert result.recommended_strategy == "ucb"

    def test_low_novelty_gives_epsilon_greedy(self, calc):
        inp = _make_input(novelty_rate=0.1)
        result = calc.compute(inp)
        assert result.recommended_strategy == "epsilon_greedy"

    def test_boundary_0_6_is_thompson(self, calc):
        inp = _make_input(novelty_rate=0.61)
        result = calc.compute(inp)
        assert result.recommended_strategy == "thompson_sampling"

    def test_boundary_0_3_is_ucb(self, calc):
        inp = _make_input(novelty_rate=0.31)
        result = calc.compute(inp)
        assert result.recommended_strategy == "ucb"


class TestRecommendedParameters:
    def test_recommended_epsilon_formula(self, calc):
        inp = _make_input(variation_frequency=0.3, novelty_rate=0.4)
        result = calc.compute(inp)
        expected = min(1.0, 0.3 + 0.4 * 0.3)
        assert abs(result.recommended_epsilon - expected) < 1e-9

    def test_recommended_lr_clamped(self, calc):
        for vf, nr in [(0.0, 0.0), (1.0, 1.0)]:
            inp = _make_input(variation_frequency=vf, novelty_rate=nr)
            result = calc.compute(inp)
            assert 0.01 <= result.recommended_lr <= 0.5


class TestAlphaWeights:
    def test_zero_alpha_removes_component_contribution(self):
        """Setting one alpha to 0 removes that component from k_factor."""
        calc_no_recall = KFactorCalculator(alpha_recall=0.0, alpha_impact=0.20,
                                           alpha_variation=0.25, alpha_consistency=0.15,
                                           alpha_novelty=0.15)
        calc_with_recall = KFactorCalculator(alpha_recall=0.25, alpha_impact=0.20,
                                             alpha_variation=0.25, alpha_consistency=0.15,
                                             alpha_novelty=0.15)
        inp = _make_input(recall_confidence=0.0)  # max contribution from recall
        result_no = calc_no_recall.compute(inp)
        result_with = calc_with_recall.compute(inp)
        assert result_no.components["recall"] == 0.0
        assert result_with.components["recall"] > 0.0
        assert result_no.k_factor < result_with.k_factor

    def test_all_alphas_used_in_compute(self):
        """All alpha weights contribute non-zero amounts with appropriate inputs."""
        calc = KFactorCalculator()
        inp = KFactorInput(
            recall_confidence=0.0,
            impact_weight=0.0,
            variation_frequency=1.0,
            outcome_consistency=0.0,
            novelty_rate=1.0,
        )
        result = calc.compute(inp)
        for name, val in result.components.items():
            assert val > 0.0, f"Component {name} should be > 0 but got {val}"


class TestComputeFromMemories:
    def test_empty_memories_returns_high_kfactor(self, calc):
        result = calc.compute_from_memories([])
        assert result.k_factor > 0.5  # high k = still learning (no memories)

    def test_memories_with_high_recall_weight(self, calc):
        memories = [
            {"recall_confidence": 0.9, "weight": 0.8, "was_variation": False,
             "had_recall": True, "outcome": 0.9},
            {"recall_confidence": 0.85, "weight": 0.75, "was_variation": False,
             "had_recall": True, "outcome": 0.85},
        ]
        result = calc.compute_from_memories(memories)
        assert result.k_factor < 0.5

    def test_memories_with_high_variation_no_recall(self, calc):
        memories = [
            {"recall_confidence": 0.1, "weight": 0.1, "was_variation": True,
             "had_recall": False, "outcome": 0.1},
            {"recall_confidence": 0.05, "weight": 0.05, "was_variation": True,
             "had_recall": False, "outcome": 0.05},
        ]
        result = calc.compute_from_memories(memories)
        assert result.k_factor > 0.4
