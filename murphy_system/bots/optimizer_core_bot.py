"""OptimizerCoreBot unifies RL tuning, policy training, and Q-learning."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np

from .optimization_bot import choose_action, update_policy, State
from .tuning_refiner_bot import TuningRefinerBot
from .policy_trainer_bot import PolicyTrainerBot
from .rl_training import HiveRLTrainingEnv


class OptimizerCoreBot:
    """Composite optimizer governed primarily by Kiren."""

    def __init__(self) -> None:
        self.tuner = TuningRefinerBot()         # 🧠 Veritas
        self.trainer = PolicyTrainerBot()       # 🛡 Vallon
        self.env = HiveRLTrainingEnv()          # 🌀 Kiren

    def optimize_q_policy(self, episodes: int = 10) -> None:
        """Run a Q-learning loop across episodes."""
        transitions = []
        for _ in range(episodes):
            state, _info = self.env.reset()
            done = False
            while not done:
                action = choose_action(State(np.array(state)))
                next_state, reward, done, _tr, _info2 = self.env.step(action)
                transitions.append((np.array(state), action, reward, np.array(next_state)))
                state = next_state
        update_policy(transitions)

    def tune_hyperparameters(self, n_trials: int = 10) -> Dict[str, Any]:
        """Run Optuna tuning for PPO hyperparameters."""
        return self.tuner.optimize(n_trials)

    def train_policy(self, timesteps: int = 10000, save_path: str = "policy.zip") -> Any:
        """Train a PPO policy using Stable Baselines."""
        return self.trainer.train(timesteps=timesteps, save_path=save_path)

    def get_cognitive_signature(self) -> dict:
        return {
            "kiren": 0.60,    # learning, loop refinement
            "veritas": 0.25,  # tuning metrics
            "vallon": 0.15    # training checkpoint enforcement
        }
