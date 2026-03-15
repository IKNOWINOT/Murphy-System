"""
Murphy System - Murphy Shadow Trainer
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Online exploration and reward-based training system for Murphy's shadow agent.
Implements epsilon-greedy exploration, experience replay, and policy gradient updates.
Integrates with: self_improvement_engine.py, self_fix_loop.py, golden_path_bridge.py
"""

import math
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class ExplorationStrategy(Enum):
    """ExplorationStrategy enumeration."""
    EPSILON_GREEDY = "epsilon_greedy"
    UCB = "ucb"
    THOMPSON_SAMPLING = "thompson_sampling"


class RewardSignal(BaseModel):
    """RewardSignal — reward signal definition."""
    task_id: str
    action_taken: str
    task_success: bool
    confidence_before: float
    confidence_after: float
    latency_ms_before: float
    latency_ms_after: float
    cost_before: float
    cost_after: float
    human_approval_rate: float = 1.0
    computed_reward: float = 0.0


@dataclass
class Experience:
    """Experience — experience definition."""
    exp_id: str
    state: Dict[str, Any]
    action: str
    reward: float
    next_state: Dict[str, Any]
    timestamp: str
    episode_id: str


class ExperienceBuffer:
    """ExperienceBuffer — experience buffer definition."""
    def __init__(self, max_size: int = 10000) -> None:
        self._max_size = max_size
        self._buffer: List[Experience] = []
        self._lock = threading.Lock()

    def add(self, exp: Experience) -> None:
        with self._lock:
            if len(self._buffer) >= self._max_size:
                self._buffer.pop(0)
            capped_append(self._buffer, exp)

    def sample(self, n: int) -> List[Experience]:
        with self._lock:
            count = min(n, len(self._buffer))
            return random.sample(self._buffer, count)

    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()


class ShadowPolicy:
    """ShadowPolicy — shadow policy definition."""
    def __init__(self, policy_id: str = "default") -> None:
        self.policy_id = policy_id
        self.action_values: Dict[str, float] = {}
        self.visit_counts: Dict[str, int] = {}

    def get_best_action(self, available_actions: List[str]) -> Optional[str]:
        if not available_actions:
            return None
        return max(available_actions, key=lambda a: self.action_values.get(a, 0.0))

    def get_action_value(self, action: str) -> float:
        return self.action_values.get(action, 0.0)

    def update_value(self, action: str, value: float, learning_rate: float = 0.1) -> None:
        current = self.action_values.get(action, 0.0)
        self.action_values[action] = current + learning_rate * (value - current)
        self.visit_counts[action] = self.visit_counts.get(action, 0) + 1

    def to_dict(self) -> Dict:
        return {
            "policy_id": self.policy_id,
            "action_values": dict(self.action_values),
            "visit_counts": dict(self.visit_counts),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ShadowPolicy":
        policy = cls(policy_id=d.get("policy_id", "default"))
        policy.action_values = dict(d.get("action_values", {}))
        policy.visit_counts = dict(d.get("visit_counts", {}))
        return policy


class PolicyUpdater:
    """PolicyUpdater — policy updater definition."""
    def __init__(
        self,
        policy: ShadowPolicy,
        learning_rate: float = 0.1,
        discount: float = 0.95,
    ) -> None:
        self._policy = policy
        self._learning_rate = learning_rate
        self._discount = discount

    def update_from_experience(self, exp: Experience) -> None:
        current_q = self._policy.get_action_value(exp.action)
        next_values = list(exp.next_state.values()) if exp.next_state else [0.0]
        numeric_next = [v for v in next_values if isinstance(v, (int, float))]
        max_next_q = max(numeric_next) if numeric_next else 0.0
        target = exp.reward + self._discount * max_next_q
        new_q = current_q + self._learning_rate * (target - current_q)
        self._policy.action_values[exp.action] = new_q
        self._policy.visit_counts[exp.action] = (
            self._policy.visit_counts.get(exp.action, 0) + 1
        )

    def update_from_buffer(self, buffer: ExperienceBuffer, batch_size: int = 32) -> int:
        batch = buffer.sample(batch_size)
        for exp in batch:
            self.update_from_experience(exp)
        return len(batch)

    def set_learning_rate(self, value: float) -> None:
        """Set the learning rate directly (called by apply_dynamic_output)."""
        self._learning_rate = max(0.0, min(1.0, float(value)))

    def compute_reward(self, signal: RewardSignal) -> float:
        success_reward = 1.0 if signal.task_success else -0.5

        confidence_delta = signal.confidence_after - signal.confidence_before
        latency_improvement = (
            (signal.latency_ms_before - signal.latency_ms_after)
            / (signal.latency_ms_before or 1)
        )
        cost_improvement = (
            (signal.cost_before - signal.cost_after)
            / (signal.cost_before or 1)
        )

        reward = (
            0.4 * success_reward
            + 0.2 * confidence_delta
            + 0.2 * latency_improvement
            + 0.1 * cost_improvement
            + 0.1 * signal.human_approval_rate
        )
        return reward


class ExplorationAgent:
    """ExplorationAgent — exploration agent definition."""
    def __init__(
        self,
        policy: ShadowPolicy,
        strategy: ExplorationStrategy = ExplorationStrategy.EPSILON_GREEDY,
        epsilon: float = 0.1,
        ucb_c: float = 1.414,
    ) -> None:
        self._policy = policy
        self._strategy = strategy
        self._epsilon = epsilon
        self._ucb_c = ucb_c
        self._total_steps = 0
        self._explore_steps = 0

    def select_action(self, available_actions: List[str], state: Dict) -> str:
        if not available_actions:
            raise ValueError("available_actions must not be empty")

        self._total_steps += 1

        if self._strategy == ExplorationStrategy.EPSILON_GREEDY:
            if random.random() < self._epsilon:
                self._explore_steps += 1
                return random.choice(available_actions)
            best = self._policy.get_best_action(available_actions)
            return best if best is not None else random.choice(available_actions)

        if self._strategy == ExplorationStrategy.UCB:
            total_visits = sum(
                self._policy.visit_counts.get(a, 0) for a in available_actions
            )
            scores = {}
            for action in available_actions:
                q = self._policy.get_action_value(action)
                visits = self._policy.visit_counts.get(action, 0)
                bonus = self._ucb_c * math.sqrt(
                    math.log(total_visits + 1) / (visits + 1)
                )
                scores[action] = q + bonus
            chosen = max(available_actions, key=lambda a: scores[a])
            if self._policy.visit_counts.get(chosen, 0) == 0:
                self._explore_steps += 1
            return chosen

        # Thompson Sampling via heuristic Beta approximation
        scores = {}
        for action in available_actions:
            q = self._policy.get_action_value(action)
            visits = self._policy.visit_counts.get(action, 0)
            noise = random.random() * (1.0 / math.sqrt(visits + 1))
            scores[action] = q + noise
        chosen = max(available_actions, key=lambda a: scores[a])
        if self._policy.visit_counts.get(chosen, 0) == 0:
            self._explore_steps += 1
        return chosen

    def set_epsilon(self, value: float) -> None:
        """Set the exploration epsilon directly (called by apply_dynamic_output)."""
        self._epsilon = max(0.0, min(1.0, float(value)))

    def decay_epsilon(self, factor: float = 0.995) -> None:
        self._epsilon = max(0.01, self._epsilon * factor)

    def get_exploration_ratio(self) -> float:
        total = self._total_steps
        return self._explore_steps / (total or 1)


class ShadowEvaluator:
    """ShadowEvaluator — shadow evaluator definition."""
    def __init__(self) -> None:
        pass

    def compare(
        self,
        shadow_action: str,
        primary_action: str,
        outcome: RewardSignal,
    ) -> Dict:
        match = shadow_action == primary_action
        shadow_reward = outcome.computed_reward
        shadow_better = shadow_reward > 0.0 and not match
        improvement = shadow_reward if shadow_better else 0.0
        return {
            "match": match,
            "shadow_better": shadow_better,
            "improvement": improvement,
        }

    def track_improvement(self, evaluations: List[Dict]) -> Dict:
        if not evaluations:
            return {
                "improvement_velocity": 0.0,
                "convergence_score": 0.0,
                "win_rate": 0.0,
            }

        improvements = [e.get("improvement", 0.0) for e in evaluations]
        wins = [1 for e in evaluations if e.get("shadow_better", False)]

        avg_improvement = sum(improvements) / (len(improvements) or 1)
        win_rate = len(wins) / (len(evaluations) or 1)

        n = len(evaluations)
        if n >= 2:
            first_half = improvements[: n // 2]
            second_half = improvements[n // 2 :]
            first_avg = sum(first_half) / (len(first_half) or 1)
            second_avg = sum(second_half) / (len(second_half) or 1)
            improvement_velocity = second_avg - first_avg
        else:
            improvement_velocity = avg_improvement

        convergence_score = win_rate * (1.0 - abs(improvement_velocity))

        return {
            "improvement_velocity": improvement_velocity,
            "convergence_score": max(0.0, convergence_score),
            "win_rate": win_rate,
        }


class ExplorationLoop:
    """ExplorationLoop — exploration loop definition."""
    def __init__(
        self,
        agent: ExplorationAgent,
        updater: PolicyUpdater,
        buffer: ExperienceBuffer,
        evaluator: ShadowEvaluator,
        max_episodes: int = 100,
    ) -> None:
        self._agent = agent
        self._updater = updater
        self._buffer = buffer
        self._evaluator = evaluator
        self._max_episodes = max_episodes

    def apply_dynamic_output(self, output: Any) -> None:
        """Apply a DynamicAssistOutput to the agent and updater.

        Reads ``computed_epsilon`` and ``computed_learning_rate`` from *output*
        and forwards them to the agent and updater respectively.  Accepts any
        object with those attributes so callers are not hard-coupled to the
        DynamicAssistEngine import.
        """
        epsilon = getattr(output, "computed_epsilon", None)
        if epsilon is not None:
            self._agent.set_epsilon(epsilon)

        learning_rate = getattr(output, "computed_learning_rate", None)
        if learning_rate is not None:
            self._updater.set_learning_rate(learning_rate)

    def run_episode(
        self,
        episode_id: str,
        available_actions: List[str],
        task_runner: Callable[[str, Dict], RewardSignal],
    ) -> List[Experience]:
        experiences: List[Experience] = []
        state: Dict[str, Any] = {"episode_id": episode_id, "step": 0}

        action = self._agent.select_action(available_actions, state)

        try:
            signal = task_runner(action, state)
        except Exception as exc:
            signal = RewardSignal(
                task_id=str(uuid.uuid4()),
                action_taken=action,
                task_success=False,
                confidence_before=0.0,
                confidence_after=0.0,
                latency_ms_before=0.0,
                latency_ms_after=0.0,
                cost_before=0.0,
                cost_after=0.0,
                computed_reward=-1.0,
            )
            signal.task_id = f"error:{exc.__class__.__name__}:{exc}"

        reward = self._updater.compute_reward(signal)
        signal.computed_reward = reward

        next_state: Dict[str, Any] = {
            "episode_id": episode_id,
            "step": 1,
            "last_reward": reward,
        }

        exp = Experience(
            exp_id=str(uuid.uuid4()),
            state=dict(state),
            action=action,
            reward=reward,
            next_state=next_state,
            timestamp=datetime.now(timezone.utc).isoformat(),
            episode_id=episode_id,
        )
        self._buffer.add(exp)
        experiences.append(exp)
        self._updater.update_from_experience(exp)
        self._agent.decay_epsilon()

        return experiences

    def run(
        self,
        initial_state: Dict,
        available_actions: List[str],
        task_runner: Callable[[str, Dict], RewardSignal],
    ) -> Dict:
        all_experiences: List[Experience] = []
        evaluations: List[Dict] = []

        for _ in range(self._max_episodes):
            episode_id = str(uuid.uuid4())
            eps = self.run_episode(episode_id, available_actions, task_runner)
            all_experiences.extend(eps)

            if self._buffer.size() >= 32:
                self._updater.update_from_buffer(self._buffer, batch_size=32)

            for exp in eps:
                best = self._agent._policy.get_best_action(available_actions)
                primary = best if best is not None else available_actions[0]
                dummy_signal = RewardSignal(
                    task_id=exp.exp_id,
                    action_taken=exp.action,
                    task_success=exp.reward > 0,
                    confidence_before=0.5,
                    confidence_after=min(1.0, 0.5 + exp.reward * 0.1),
                    latency_ms_before=100.0,
                    latency_ms_after=100.0,
                    cost_before=1.0,
                    cost_after=1.0,
                    computed_reward=exp.reward,
                )
                evaluation = self._evaluator.compare(exp.action, primary, dummy_signal)
                evaluations.append(evaluation)

        rewards = [e.reward for e in all_experiences]
        avg_reward = sum(rewards) / (len(rewards) or 1)
        improvement_stats = self._evaluator.track_improvement(evaluations)

        return {
            "total_episodes": self._max_episodes,
            "total_experiences": len(all_experiences),
            "avg_reward": avg_reward,
            "exploration_ratio": self._agent.get_exploration_ratio(),
            "improvement_velocity": improvement_stats["improvement_velocity"],
            "convergence_score": improvement_stats["convergence_score"],
            "win_rate": improvement_stats["win_rate"],
        }


def create_shadow_trainer(
    policy_id: str = "murphy_shadow",
) -> tuple:
    policy = ShadowPolicy(policy_id=policy_id)
    buffer = ExperienceBuffer()
    updater = PolicyUpdater(policy=policy)
    agent = ExplorationAgent(policy=policy)
    evaluator = ShadowEvaluator()
    loop = ExplorationLoop(
        agent=agent,
        updater=updater,
        buffer=buffer,
        evaluator=evaluator,
    )
    return loop, policy, buffer


_GLOBAL_POLICY: ShadowPolicy = ShadowPolicy(policy_id="murphy_global")


def get_global_policy() -> ShadowPolicy:
    return _GLOBAL_POLICY
