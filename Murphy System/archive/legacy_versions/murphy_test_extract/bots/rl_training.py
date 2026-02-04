"""Reinforcement-learning training harness using gymnasium and stable-baselines3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:  # heavy deps are optional
    from gymnasium import Env, spaces
    import gymnasium
    from stable_baselines3 import PPO
except Exception:  # pragma: no cover - optional deps
    Env = spaces = gymnasium = PPO = None  # type: ignore


@dataclass
class MetricsSnapshot:
    """System metrics used as RL observations."""
    values: np.ndarray


def simulate_bot_strategy(action: Any) -> dict:
    """Placeholder strategy simulation."""
    # In real usage this would run the chosen strategy in a sandbox and
    # return performance metrics.
    return {
        "latency": np.random.rand(),
        "tokens": np.random.randint(1, 10),
        "feedback": np.random.rand(),
        "trust": np.random.rand(),
    }


def evaluate_policy_metrics(outcome: dict) -> float:
    """Compute reward from strategy outcome."""
    return float(1.0 - outcome["latency"] + outcome["feedback"] - 0.1 * outcome["tokens"])


def collect_metrics_snapshot() -> np.ndarray:
    """Return a vector of normalized system metrics."""
    return np.random.rand(10)


class HiveRLTrainingEnv(Env):
    """Simple environment exposing system metrics."""

    def __init__(self) -> None:
        if spaces is None:
            raise ImportError("gymnasium is required for HiveRLTrainingEnv")
        super().__init__()
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(10,))
        self.action_space = spaces.MultiDiscrete([5, 4])

    def step(self, action: np.ndarray):
        outcome = simulate_bot_strategy(action)
        reward = evaluate_policy_metrics(outcome)
        obs = collect_metrics_snapshot()
        terminated = False
        truncated = False
        info = {}
        return obs, reward, terminated, truncated, info

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        return collect_metrics_snapshot(), {}


def train_rl_policy(total_timesteps: int = 100000, save_path: str = "hive_optimizer_policy.zip") -> Any:
    """Train a PPO policy in the Hive environment."""
    if PPO is None:
        raise ImportError("stable-baselines3 and gymnasium are required for training")
    env = HiveRLTrainingEnv()
    model = PPO("MlpPolicy", env, verbose=0)
    model.learn(total_timesteps=total_timesteps)
    model.save(save_path)
    return model
