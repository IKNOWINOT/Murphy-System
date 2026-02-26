"""Policy training bot using stable-baselines3."""
from __future__ import annotations

from typing import Any

try:
    from stable_baselines3 import PPO
except Exception:  # pragma: no cover
    PPO = None  # type: ignore

from .rl_training import HiveRLTrainingEnv

class PolicyTrainerBot:
    def train(self, timesteps: int = 10000, save_path: str = "policy.zip") -> Any:
        if PPO is None:
            raise ImportError("stable-baselines3 is required")
        env = HiveRLTrainingEnv()
        model = PPO("MlpPolicy", env, verbose=0)
        model.learn(total_timesteps=timesteps)
        model.save(save_path)
        return model
