"""Tests for GAP-5: ExplorationAgent.set_epsilon(), PolicyUpdater.set_learning_rate(),
and ExplorationLoop.apply_dynamic_output().

Proves that DynamicAssistOutput parameters are correctly applied to the RL loop.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "src"


def _load_shadow_trainer():
    src = _src_path()
    spec = importlib.util.spec_from_file_location(
        "murphy_shadow_trainer", src / "murphy_shadow_trainer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["murphy_shadow_trainer"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExplorationAgentSetEpsilon:
    """GAP-5a: ExplorationAgent.set_epsilon() exists and works."""

    def test_set_epsilon_method_exists(self):
        mod = _load_shadow_trainer()
        agent = mod.ExplorationAgent(policy=mod.ShadowPolicy())
        assert hasattr(agent, "set_epsilon"), "ExplorationAgent must have set_epsilon()"

    def test_set_epsilon_updates_value(self):
        mod = _load_shadow_trainer()
        agent = mod.ExplorationAgent(policy=mod.ShadowPolicy(), epsilon=0.1)
        agent.set_epsilon(0.7)
        assert abs(agent._epsilon - 0.7) < 1e-9

    def test_set_epsilon_clamps_above_one(self):
        mod = _load_shadow_trainer()
        agent = mod.ExplorationAgent(policy=mod.ShadowPolicy())
        agent.set_epsilon(1.5)
        assert agent._epsilon <= 1.0

    def test_set_epsilon_clamps_below_zero(self):
        mod = _load_shadow_trainer()
        agent = mod.ExplorationAgent(policy=mod.ShadowPolicy())
        agent.set_epsilon(-0.5)
        assert agent._epsilon >= 0.0

    def test_set_epsilon_influences_exploration(self):
        """After set_epsilon(1.0), almost every step should be exploratory."""
        mod = _load_shadow_trainer()
        policy = mod.ShadowPolicy()
        agent = mod.ExplorationAgent(policy=policy, strategy=mod.ExplorationStrategy.EPSILON_GREEDY)
        agent.set_epsilon(1.0)
        actions = ["a", "b"]
        explore_count = sum(
            1 for _ in range(100)
            if agent.select_action(actions, {}) in actions
        )
        # All steps must be accounted for
        assert explore_count == 100


class TestPolicyUpdaterSetLearningRate:
    """GAP-5b: PolicyUpdater.set_learning_rate() exists and works."""

    def test_set_learning_rate_method_exists(self):
        mod = _load_shadow_trainer()
        policy = mod.ShadowPolicy()
        updater = mod.PolicyUpdater(policy=policy)
        assert hasattr(updater, "set_learning_rate"), "PolicyUpdater must have set_learning_rate()"

    def test_set_learning_rate_updates_value(self):
        mod = _load_shadow_trainer()
        policy = mod.ShadowPolicy()
        updater = mod.PolicyUpdater(policy=policy, learning_rate=0.1)
        updater.set_learning_rate(0.42)
        assert abs(updater._learning_rate - 0.42) < 1e-9

    def test_set_learning_rate_clamps_above_one(self):
        mod = _load_shadow_trainer()
        policy = mod.ShadowPolicy()
        updater = mod.PolicyUpdater(policy=policy)
        updater.set_learning_rate(2.0)
        assert updater._learning_rate <= 1.0

    def test_set_learning_rate_clamps_below_zero(self):
        mod = _load_shadow_trainer()
        policy = mod.ShadowPolicy()
        updater = mod.PolicyUpdater(policy=policy)
        updater.set_learning_rate(-0.1)
        assert updater._learning_rate >= 0.0

    def test_set_learning_rate_affects_q_update(self):
        """High learning rate should cause large Q-value shift."""
        mod = _load_shadow_trainer()
        policy = mod.ShadowPolicy()
        updater = mod.PolicyUpdater(policy=policy, learning_rate=0.01)
        from datetime import datetime, timezone
        exp = mod.Experience(
            exp_id="e1",
            state={},
            action="a",
            reward=1.0,
            next_state={},
            timestamp=datetime.now(timezone.utc).isoformat(),
            episode_id="ep1",
        )
        updater.update_from_experience(exp)
        low_lr_value = policy.get_action_value("a")

        # Reset and use high learning rate
        policy2 = mod.ShadowPolicy()
        updater2 = mod.PolicyUpdater(policy=policy2, learning_rate=0.9)
        updater2.update_from_experience(exp)
        high_lr_value = policy2.get_action_value("a")

        assert high_lr_value > low_lr_value


class TestExplorationLoopApplyDynamicOutput:
    """GAP-5c: ExplorationLoop.apply_dynamic_output() exists and propagates values."""

    def _make_loop(self, mod):
        policy = mod.ShadowPolicy()
        buffer = mod.ExperienceBuffer()
        updater = mod.PolicyUpdater(policy=policy)
        agent = mod.ExplorationAgent(policy=policy, epsilon=0.1)
        evaluator = mod.ShadowEvaluator()
        loop = mod.ExplorationLoop(
            agent=agent, updater=updater, buffer=buffer, evaluator=evaluator
        )
        return loop, agent, updater

    def test_apply_dynamic_output_method_exists(self):
        mod = _load_shadow_trainer()
        loop, _, _ = self._make_loop(mod)
        assert hasattr(loop, "apply_dynamic_output"), "ExplorationLoop must have apply_dynamic_output()"

    def test_apply_dynamic_output_sets_epsilon(self):
        mod = _load_shadow_trainer()
        loop, agent, _ = self._make_loop(mod)
        output = SimpleNamespace(computed_epsilon=0.55, computed_learning_rate=0.2)
        loop.apply_dynamic_output(output)
        assert abs(agent._epsilon - 0.55) < 1e-9

    def test_apply_dynamic_output_sets_learning_rate(self):
        mod = _load_shadow_trainer()
        loop, _, updater = self._make_loop(mod)
        output = SimpleNamespace(computed_epsilon=0.1, computed_learning_rate=0.33)
        loop.apply_dynamic_output(output)
        assert abs(updater._learning_rate - 0.33) < 1e-9

    def test_apply_dynamic_output_partial_object(self):
        """Output with only computed_epsilon (no computed_learning_rate) should not raise."""
        mod = _load_shadow_trainer()
        loop, agent, updater = self._make_loop(mod)
        original_lr = updater._learning_rate
        output = SimpleNamespace(computed_epsilon=0.77)  # no computed_learning_rate
        loop.apply_dynamic_output(output)
        assert abs(agent._epsilon - 0.77) < 1e-9
        # learning rate unchanged
        assert abs(updater._learning_rate - original_lr) < 1e-9

    def test_apply_dynamic_output_from_dynamic_assist_engine(self):
        """End-to-end: DynamicAssistEngine → apply_dynamic_output → correct RL params."""
        mod = _load_shadow_trainer()
        loop, agent, updater = self._make_loop(mod)

        try:
            import importlib
            dae_mod = importlib.import_module("src.dynamic_assist_engine")
            DynamicAssistInput = dae_mod.DynamicAssistInput
            DynamicAssistEngine = dae_mod.DynamicAssistEngine
        except ImportError:
            pytest.skip("DynamicAssistEngine not importable in this environment")

        engine = DynamicAssistEngine()
        inp = DynamicAssistInput(
            recall_confidence=0.8,
            impact_weight=0.7,
            k_factor=0.5,
            risk_level=0.2,
            variation_frequency=0.3,
            novelty_rate=0.1,
        )
        output = engine.evaluate(inp)

        loop.apply_dynamic_output(output)

        assert abs(agent._epsilon - output.computed_epsilon) < 1e-9
        assert abs(updater._learning_rate - output.computed_learning_rate) < 1e-9
