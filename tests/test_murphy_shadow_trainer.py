"""
Murphy System - Tests for Murphy Shadow Trainer
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import uuid
from datetime import datetime, timezone

import pytest

from murphy_shadow_trainer import (
    ExplorationStrategy,
    RewardSignal,
    Experience,
    ExperienceBuffer,
    ShadowPolicy,
    PolicyUpdater,
    ExplorationAgent,
    ShadowEvaluator,
    ExplorationLoop,
    create_shadow_trainer,
    get_global_policy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_experience(action: str = "action_a", reward: float = 1.0, episode_id: str = None) -> Experience:
    return Experience(
        exp_id=str(uuid.uuid4()),
        state={"step": 0},
        action=action,
        reward=reward,
        next_state={"step": 1},
        timestamp=_now(),
        episode_id=episode_id or uuid.uuid4().hex[:8],
    )


def _make_reward_signal(success: bool = True, computed_reward: float = 0.5) -> RewardSignal:
    return RewardSignal(
        task_id=uuid.uuid4().hex[:8],
        action_taken="action_a",
        task_success=success,
        confidence_before=0.5,
        confidence_after=0.7,
        latency_ms_before=100.0,
        latency_ms_after=80.0,
        cost_before=1.0,
        cost_after=0.8,
        human_approval_rate=1.0,
        computed_reward=computed_reward,
    )


def _simple_task_runner(action: str, state: dict) -> RewardSignal:
    return _make_reward_signal(success=True)


# ---------------------------------------------------------------------------
# TestExperienceBuffer
# ---------------------------------------------------------------------------

class TestExperienceBuffer:
    def test_add_and_size(self):
        buf = ExperienceBuffer()
        assert buf.size() == 0
        buf.add(_make_experience())
        assert buf.size() == 1

    def test_add_multiple(self):
        buf = ExperienceBuffer()
        for _ in range(5):
            buf.add(_make_experience())
        assert buf.size() == 5

    def test_sample_returns_list(self):
        buf = ExperienceBuffer()
        for _ in range(10):
            buf.add(_make_experience())
        samples = buf.sample(5)
        assert isinstance(samples, list)
        assert len(samples) == 5

    def test_sample_fewer_than_available(self):
        buf = ExperienceBuffer()
        for _ in range(3):
            buf.add(_make_experience())
        samples = buf.sample(10)
        assert len(samples) == 3

    def test_max_size_evicts_old_entries(self):
        buf = ExperienceBuffer(max_size=3)
        for i in range(5):
            buf.add(_make_experience(action=f"act_{i}"))
        assert buf.size() == 3

    def test_clear(self):
        buf = ExperienceBuffer()
        for _ in range(5):
            buf.add(_make_experience())
        buf.clear()
        assert buf.size() == 0

    def test_sample_empty_returns_empty(self):
        buf = ExperienceBuffer()
        assert buf.sample(5) == []


# ---------------------------------------------------------------------------
# TestShadowPolicy
# ---------------------------------------------------------------------------

class TestShadowPolicy:
    def test_get_best_action_from_single(self):
        policy = ShadowPolicy()
        policy.action_values["act_a"] = 0.8
        best = policy.get_best_action(["act_a"])
        assert best == "act_a"

    def test_get_best_action_picks_highest_value(self):
        policy = ShadowPolicy()
        policy.action_values["low"] = 0.1
        policy.action_values["high"] = 0.9
        best = policy.get_best_action(["low", "high"])
        assert best == "high"

    def test_get_best_action_empty_returns_none(self):
        policy = ShadowPolicy()
        assert policy.get_best_action([]) is None

    def test_update_value_changes_action_value(self):
        policy = ShadowPolicy()
        policy.update_value("act_x", 1.0, learning_rate=1.0)
        assert policy.action_values["act_x"] == pytest.approx(1.0)

    def test_update_value_increments_visit_count(self):
        policy = ShadowPolicy()
        policy.update_value("act_y", 0.5)
        assert policy.visit_counts.get("act_y", 0) == 1

    def test_to_dict_roundtrip(self):
        policy = ShadowPolicy(policy_id="p1")
        policy.update_value("act_z", 0.7)
        d = policy.to_dict()
        restored = ShadowPolicy.from_dict(d)
        assert restored.policy_id == "p1"
        assert "act_z" in restored.action_values

    def test_get_action_value_default_zero(self):
        policy = ShadowPolicy()
        assert policy.get_action_value("unknown") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestPolicyUpdater
# ---------------------------------------------------------------------------

class TestPolicyUpdater:
    def test_compute_reward_success(self):
        updater = PolicyUpdater(ShadowPolicy())
        signal = _make_reward_signal(success=True)
        reward = updater.compute_reward(signal)
        assert isinstance(reward, float)

    def test_compute_reward_failure_lower_than_success(self):
        updater = PolicyUpdater(ShadowPolicy())
        success_reward = updater.compute_reward(_make_reward_signal(success=True))
        fail_reward = updater.compute_reward(_make_reward_signal(success=False))
        assert success_reward > fail_reward

    def test_update_from_experience(self):
        policy = ShadowPolicy()
        updater = PolicyUpdater(policy)
        exp = _make_experience(action="upd_action", reward=1.0)
        updater.update_from_experience(exp)
        assert "upd_action" in policy.action_values

    def test_update_from_buffer(self):
        policy = ShadowPolicy()
        updater = PolicyUpdater(policy)
        buf = ExperienceBuffer()
        for _ in range(10):
            buf.add(_make_experience(action="buf_action", reward=0.5))
        count = updater.update_from_buffer(buf, batch_size=5)
        assert count == 5

    def test_update_from_buffer_empty_returns_zero(self):
        policy = ShadowPolicy()
        updater = PolicyUpdater(policy)
        buf = ExperienceBuffer()
        count = updater.update_from_buffer(buf)
        assert count == 0


# ---------------------------------------------------------------------------
# TestExplorationAgent
# ---------------------------------------------------------------------------

class TestExplorationAgent:
    def test_select_action_epsilon_greedy_returns_valid(self):
        policy = ShadowPolicy()
        agent = ExplorationAgent(policy, strategy=ExplorationStrategy.EPSILON_GREEDY, epsilon=0.5)
        actions = ["a", "b", "c"]
        action = agent.select_action(actions, {})
        assert action in actions

    def test_select_action_ucb_returns_valid(self):
        policy = ShadowPolicy()
        agent = ExplorationAgent(policy, strategy=ExplorationStrategy.UCB)
        actions = ["x", "y", "z"]
        action = agent.select_action(actions, {})
        assert action in actions

    def test_select_action_thompson_sampling_returns_valid(self):
        policy = ShadowPolicy()
        agent = ExplorationAgent(policy, strategy=ExplorationStrategy.THOMPSON_SAMPLING)
        actions = ["m", "n"]
        action = agent.select_action(actions, {})
        assert action in actions

    def test_select_action_empty_raises(self):
        policy = ShadowPolicy()
        agent = ExplorationAgent(policy)
        with pytest.raises(ValueError):
            agent.select_action([], {})

    def test_decay_epsilon_reduces_value(self):
        policy = ShadowPolicy()
        agent = ExplorationAgent(policy, epsilon=0.5)
        original = agent._epsilon
        agent.decay_epsilon(factor=0.9)
        assert agent._epsilon < original

    def test_decay_epsilon_floor_at_minimum(self):
        policy = ShadowPolicy()
        agent = ExplorationAgent(policy, epsilon=0.001)
        for _ in range(100):
            agent.decay_epsilon(factor=0.5)
        assert agent._epsilon >= 0.01

    def test_exploration_ratio_between_0_and_1(self):
        policy = ShadowPolicy()
        agent = ExplorationAgent(policy, epsilon=1.0)
        for _ in range(20):
            agent.select_action(["a", "b"], {})
        ratio = agent.get_exploration_ratio()
        assert 0.0 <= ratio <= 1.0


# ---------------------------------------------------------------------------
# TestShadowEvaluator
# ---------------------------------------------------------------------------

class TestShadowEvaluator:
    def test_compare_matching_actions(self):
        evaluator = ShadowEvaluator()
        signal = _make_reward_signal(computed_reward=0.5)
        result = evaluator.compare("action_a", "action_a", signal)
        assert result["match"] is True

    def test_compare_different_actions(self):
        evaluator = ShadowEvaluator()
        signal = _make_reward_signal(computed_reward=0.8)
        result = evaluator.compare("shadow_act", "primary_act", signal)
        assert result["match"] is False

    def test_compare_returns_improvement(self):
        evaluator = ShadowEvaluator()
        signal = _make_reward_signal(computed_reward=0.9)
        result = evaluator.compare("shadow", "primary", signal)
        assert "improvement" in result

    def test_track_improvement_empty_returns_zeros(self):
        evaluator = ShadowEvaluator()
        stats = evaluator.track_improvement([])
        assert stats["improvement_velocity"] == pytest.approx(0.0)
        assert stats["win_rate"] == pytest.approx(0.0)

    def test_track_improvement_with_wins(self):
        evaluator = ShadowEvaluator()
        evals = [
            {"match": False, "shadow_better": True, "improvement": 0.5},
            {"match": False, "shadow_better": True, "improvement": 0.6},
            {"match": True, "shadow_better": False, "improvement": 0.0},
        ]
        stats = evaluator.track_improvement(evals)
        assert stats["win_rate"] > 0.0

    def test_track_improvement_convergence_nonnegative(self):
        evaluator = ShadowEvaluator()
        evals = [{"improvement": float(i) * 0.1, "shadow_better": True} for i in range(6)]
        stats = evaluator.track_improvement(evals)
        assert stats["convergence_score"] >= 0.0


# ---------------------------------------------------------------------------
# TestExplorationLoop
# ---------------------------------------------------------------------------

class TestExplorationLoop:
    def _make_loop(self, max_episodes: int = 3) -> ExplorationLoop:
        policy = ShadowPolicy()
        buffer = ExperienceBuffer()
        updater = PolicyUpdater(policy)
        agent = ExplorationAgent(policy, epsilon=0.5)
        evaluator = ShadowEvaluator()
        return ExplorationLoop(
            agent=agent,
            updater=updater,
            buffer=buffer,
            evaluator=evaluator,
            max_episodes=max_episodes,
        )

    def test_run_episode_returns_experiences(self):
        loop = self._make_loop()
        experiences = loop.run_episode(
            episode_id=uuid.uuid4().hex[:8],
            available_actions=["act_a", "act_b"],
            task_runner=_simple_task_runner,
        )
        assert isinstance(experiences, list)
        assert len(experiences) >= 1

    def test_run_episode_experience_has_fields(self):
        loop = self._make_loop()
        experiences = loop.run_episode(
            episode_id=uuid.uuid4().hex[:8],
            available_actions=["act_a"],
            task_runner=_simple_task_runner,
        )
        exp = experiences[0]
        assert isinstance(exp, Experience)
        assert exp.action in ["act_a"]
        assert isinstance(exp.reward, float)

    def test_run_returns_summary_dict(self):
        loop = self._make_loop(max_episodes=2)
        result = loop.run(
            initial_state={"step": 0},
            available_actions=["act_a", "act_b"],
            task_runner=_simple_task_runner,
        )
        assert isinstance(result, dict)
        assert "avg_reward" in result
        assert "total_episodes" in result
        assert "win_rate" in result

    def test_run_total_episodes_matches(self):
        loop = self._make_loop(max_episodes=4)
        result = loop.run(
            initial_state={},
            available_actions=["a", "b"],
            task_runner=_simple_task_runner,
        )
        assert result["total_episodes"] == 4


# ---------------------------------------------------------------------------
# TestConvenience
# ---------------------------------------------------------------------------

class TestConvenience:
    def test_create_shadow_trainer_returns_tuple(self):
        result = create_shadow_trainer(policy_id="test_policy")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_create_shadow_trainer_components(self):
        loop, policy, buffer = create_shadow_trainer()
        assert isinstance(loop, ExplorationLoop)
        assert isinstance(policy, ShadowPolicy)
        assert isinstance(buffer, ExperienceBuffer)

    def test_create_shadow_trainer_policy_id(self):
        _, policy, _ = create_shadow_trainer(policy_id="my_trainer")
        assert policy.policy_id == "my_trainer"

    def test_get_global_policy_returns_shadow_policy(self):
        policy = get_global_policy()
        assert isinstance(policy, ShadowPolicy)

    def test_get_global_policy_is_stable(self):
        p1 = get_global_policy()
        p2 = get_global_policy()
        assert p1 is p2

    def test_get_global_policy_has_default_id(self):
        policy = get_global_policy()
        assert policy.policy_id == "murphy_global"
