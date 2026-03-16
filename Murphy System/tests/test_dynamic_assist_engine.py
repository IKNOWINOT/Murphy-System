"""Tests for the Dynamic Assist Engine module."""

import os

import pytest
from src.dynamic_assist_engine import DynamicAssistEngine, DynamicAssistInput


@pytest.fixture
def engine():
    return DynamicAssistEngine()


def _make_input(
    recall_confidence=0.5,
    impact_weight=0.5,
    k_factor=0.3,
    risk_level=0.2,
    variation_frequency=0.3,
    novelty_rate=0.3,
) -> DynamicAssistInput:
    return DynamicAssistInput(
        recall_confidence=recall_confidence,
        impact_weight=impact_weight,
        k_factor=k_factor,
        risk_level=risk_level,
        variation_frequency=variation_frequency,
        novelty_rate=novelty_rate,
    )


class TestObserveOnly:
    def test_high_kfactor_triggers_observe_only(self, engine):
        inp = _make_input(k_factor=0.9, recall_confidence=0.5)
        out = engine.evaluate(inp)
        assert out.observe_only is True

    def test_low_recall_high_novelty_triggers_observe_only(self, engine):
        inp = _make_input(recall_confidence=0.1, novelty_rate=0.8, k_factor=0.3)
        out = engine.evaluate(inp)
        assert out.observe_only is True

    def test_moderate_kfactor_no_observe_only(self, engine):
        inp = _make_input(k_factor=0.4, recall_confidence=0.6, novelty_rate=0.3)
        out = engine.evaluate(inp)
        assert out.observe_only is False


class TestMaySuggest:
    def test_high_recall_low_kfactor_may_suggest(self, engine):
        inp = _make_input(recall_confidence=0.6, k_factor=0.3, novelty_rate=0.3)
        out = engine.evaluate(inp)
        assert out.may_suggest is True

    def test_observe_only_disables_may_suggest(self, engine):
        inp = _make_input(k_factor=0.9, recall_confidence=0.8)
        out = engine.evaluate(inp)
        assert out.observe_only is True
        assert out.may_suggest is False

    def test_low_recall_disables_may_suggest(self, engine):
        inp = _make_input(recall_confidence=0.3, k_factor=0.3)
        out = engine.evaluate(inp)
        assert out.may_suggest is False


class TestMayExecute:
    def test_high_recall_low_kfactor_low_risk_may_execute(self, engine):
        inp = _make_input(recall_confidence=0.8, k_factor=0.3, risk_level=0.2)
        out = engine.evaluate(inp)
        assert out.may_execute is True

    def test_high_risk_disables_may_execute(self, engine):
        inp = _make_input(recall_confidence=0.8, k_factor=0.3, risk_level=0.6)
        out = engine.evaluate(inp)
        assert out.may_execute is False

    def test_high_kfactor_disables_may_execute(self, engine):
        inp = _make_input(recall_confidence=0.8, k_factor=0.5, risk_level=0.2)
        out = engine.evaluate(inp)
        assert out.may_execute is False


class TestRequiresApproval:
    def test_high_risk_requires_approval(self, engine):
        inp = _make_input(risk_level=0.4, k_factor=0.3, recall_confidence=0.8)
        out = engine.evaluate(inp)
        assert out.requires_approval is True

    def test_high_kfactor_requires_approval(self, engine):
        inp = _make_input(k_factor=0.6, risk_level=0.1, recall_confidence=0.8)
        out = engine.evaluate(inp)
        assert out.requires_approval is True

    def test_no_may_execute_requires_approval(self, engine):
        inp = _make_input(recall_confidence=0.3, k_factor=0.3, risk_level=0.2)
        out = engine.evaluate(inp)
        # may_execute=False when recall<0.7
        assert out.may_execute is False
        assert out.requires_approval is True


class TestComputedEpsilon:
    def test_epsilon_scales_with_variation_frequency(self, engine):
        inp_low = _make_input(variation_frequency=0.1, novelty_rate=0.1)
        inp_high = _make_input(variation_frequency=0.8, novelty_rate=0.1)
        out_low = engine.evaluate(inp_low)
        out_high = engine.evaluate(inp_high)
        assert out_high.computed_epsilon > out_low.computed_epsilon

    def test_epsilon_clamped_at_1(self, engine):
        inp = _make_input(variation_frequency=0.9, novelty_rate=0.9)
        out = engine.evaluate(inp)
        assert out.computed_epsilon <= 1.0

    def test_epsilon_minimum_is_zero(self, engine):
        inp = _make_input(variation_frequency=0.0, novelty_rate=0.0)
        out = engine.evaluate(inp)
        assert out.computed_epsilon >= 0.0


class TestComputedLearningRate:
    def test_lr_clamps_minimum_at_0_01(self, engine):
        inp = _make_input(k_factor=0.0)
        out = engine.evaluate(inp)
        assert out.computed_learning_rate >= 0.01

    def test_lr_clamps_maximum_at_0_5(self, engine):
        inp = _make_input(k_factor=1.0)
        out = engine.evaluate(inp)
        assert out.computed_learning_rate <= 0.5

    def test_lr_equals_kfactor_in_range(self, engine):
        inp = _make_input(k_factor=0.25)
        out = engine.evaluate(inp)
        assert abs(out.computed_learning_rate - 0.25) < 1e-9


class TestComputedConfidenceThreshold:
    def test_high_recall_lowers_threshold(self, engine):
        inp_low = _make_input(recall_confidence=0.1)
        inp_high = _make_input(recall_confidence=0.9)
        out_low = engine.evaluate(inp_low)
        out_high = engine.evaluate(inp_high)
        assert out_high.computed_confidence_threshold < out_low.computed_confidence_threshold

    def test_threshold_clamped_between_0_5_and_0_99(self, engine):
        for rc in [0.0, 0.5, 1.0]:
            inp = _make_input(recall_confidence=rc)
            out = engine.evaluate(inp)
            assert 0.5 <= out.computed_confidence_threshold <= 0.99


class TestPureFunction:
    def test_same_inputs_same_outputs(self, engine):
        inp = _make_input(
            recall_confidence=0.6, k_factor=0.3, risk_level=0.15,
            variation_frequency=0.2, novelty_rate=0.25
        )
        out1 = engine.evaluate(inp)
        out2 = engine.evaluate(inp)
        assert out1.observe_only == out2.observe_only
        assert out1.may_suggest == out2.may_suggest
        assert out1.may_execute == out2.may_execute
        assert out1.computed_epsilon == out2.computed_epsilon
        assert out1.computed_learning_rate == out2.computed_learning_rate
        assert out1.computed_confidence_threshold == out2.computed_confidence_threshold


class TestEdgeCases:
    def test_all_zeros(self, engine):
        inp = _make_input(
            recall_confidence=0.0, impact_weight=0.0, k_factor=0.0,
            risk_level=0.0, variation_frequency=0.0, novelty_rate=0.0
        )
        out = engine.evaluate(inp)
        # Low recall + low novelty + low k_factor → observe_only=False, may_suggest=False
        assert out.observe_only is False
        assert out.may_suggest is False
        assert out.computed_epsilon == 0.0
        assert out.computed_learning_rate == 0.01  # clamped min

    def test_all_ones(self, engine):
        inp = _make_input(
            recall_confidence=1.0, impact_weight=1.0, k_factor=1.0,
            risk_level=1.0, variation_frequency=1.0, novelty_rate=1.0
        )
        out = engine.evaluate(inp)
        assert out.observe_only is True  # k_factor=1.0 > 0.85
        assert out.computed_epsilon == 1.0  # clamped max
        assert out.computed_learning_rate == 0.5  # clamped max
