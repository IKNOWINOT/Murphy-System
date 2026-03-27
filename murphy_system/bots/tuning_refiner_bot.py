"""Hyperparameter tuning for RL agents using Optuna."""
from __future__ import annotations

from typing import Any

try:
    import optuna
    from stable_baselines3 import PPO
except Exception:  # pragma: no cover
    optuna = None
    PPO = None  # type: ignore

from .rl_training import HiveRLTrainingEnv

class TuningRefinerBot:
    def optimize(self, n_trials: int = 10) -> Any:
        if optuna is None or PPO is None:
            raise ImportError("optuna and stable-baselines3 are required")

        def objective(trial: optuna.Trial) -> float:
            lr = trial.suggest_loguniform("lr", 1e-5, 1e-3)
            gamma = trial.suggest_uniform("gamma", 0.9, 0.999)
            model = PPO("MlpPolicy", HiveRLTrainingEnv(), learning_rate=lr, gamma=gamma, verbose=0)
            model.learn(total_timesteps=1000)
            # simple evaluation metric
            return float(model.ep_info_buffer[-1]["r"] if model.ep_info_buffer else 0.0)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=n_trials)
        return study.best_params
