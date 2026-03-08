"""Reinforcement-learning training harness using gymnasium and stable-baselines3."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import numpy as np

try:  # heavy deps are optional
    from gymnasium import Env, spaces
    import gymnasium
    from stable_baselines3 import PPO
except Exception:  # pragma: no cover - optional deps
    Env = spaces = gymnasium = PPO = None  # type: ignore

try:
    import psutil as _psutil
except Exception:  # pragma: no cover - optional dep
    _psutil = None  # type: ignore

# Set MURPHY_TEST_MODE=1 to enable deterministic mock responses
_TEST_MODE = os.environ.get("MURPHY_TEST_MODE", "0") == "1"


@dataclass
class MetricsSnapshot:
    """System metrics used as RL observations."""
    values: np.ndarray


def simulate_bot_strategy(action: Any, *, _test_mode: bool | None = None) -> dict:
    """Run a bot strategy and return performance metrics.

    In test mode (``_test_mode=True`` or env ``MURPHY_TEST_MODE=1``) a
    deterministic mock is returned so that unit tests are reproducible.
    In production mode the strategy parameters are used to derive realistic
    performance estimates without random noise.

    Returns:
        dict with keys ``reward``, ``latency_ms``, ``success_rate``, ``steps``,
        ``source`` ('mock' or 'sandbox').
    """
    use_mock = _test_mode if _test_mode is not None else _TEST_MODE

    if use_mock:
        # Deterministic mock: derive fixed metrics from the action hash so that
        # identical inputs always produce identical outputs.
        seed = hash(str(action)) % (2 ** 31)
        rng = np.random.default_rng(seed)
        latency_ms = float(rng.integers(5, 50))
        success_rate = float(rng.uniform(0.7, 0.95))
        reward = float(2 * success_rate - 1)  # maps [0,1] → [-1,1]
        steps = int(rng.integers(10, 100))
        return {
            "reward": round(reward, 4),
            "latency_ms": latency_ms,
            "success_rate": round(success_rate, 4),
            "steps": steps,
            "source": "mock",
        }

    # Production path: derive metrics from the action vector without randomness.
    try:
        action_arr = np.asarray(action, dtype=float).flatten()
    except Exception:
        action_arr = np.zeros(2)

    # Normalise action values into [0, 1] for stable estimates.
    norm_action = action_arr / (np.linalg.norm(action_arr) or 1.0)
    base_success = float(np.clip(0.5 + norm_action.mean() * 0.4, 0.0, 1.0))
    base_latency = max(1.0, 20.0 - base_success * 10.0)
    base_steps = max(1, int(50 * (1.0 - base_success) + 5))
    reward = float(np.clip(2 * base_success - 1, -1.0, 1.0))
    return {
        "reward": round(reward, 4),
        "latency_ms": round(base_latency, 2),
        "success_rate": round(base_success, 4),
        "steps": base_steps,
        "source": "sandbox",
    }


def evaluate_policy_metrics(outcome: dict) -> float:
    """Compute reward from strategy outcome."""
    if "reward" in outcome:
        return float(outcome["reward"])
    latency = float(outcome.get("latency", 0.5))
    feedback = float(outcome.get("feedback", 0.5))
    tokens = float(outcome.get("tokens", 1))
    return float(1.0 - latency + feedback - 0.1 * tokens)


def collect_metrics_snapshot() -> np.ndarray:
    """Return a vector of normalised system metrics with shape (10,).

    Metrics (all normalised to approximately [0, 1]):
      0: cpu_percent / 100
      1: memory_percent / 100
      2: virtual_memory_used / virtual_memory_total  (clamped)
      3: swap_percent / 100
      4: disk_read_bytes (normalised, zeroed if unavail)
      5: disk_write_bytes (normalised, zeroed if unavail)
      6: net_bytes_sent (normalised, zeroed if unavail)
      7: net_bytes_recv (normalised, zeroed if unavail)
      8: active_thread_count (normalised by max expected 1000)
      9: load_avg_1m / cpu_count  (zeroed on Windows)

    If ``psutil`` is unavailable all values are 0 with ``partial=True``.
    """
    # Normalisation reference values
    _DISK_IO_REF_BYTES = 500 * 1024 * 1024   # 500 MB/s throughput baseline
    _NET_IO_REF_BYTES = 1024 * 1024 * 1024   # 1 GB cumulative traffic baseline
    _MAX_EXPECTED_PIDS = 1000                 # upper bound for process-count normalisation

    result = np.zeros(10, dtype=float)

    if _psutil is None:
        return result

    try:
        cpu = _psutil.cpu_percent(interval=None) / 100.0
        mem = _psutil.virtual_memory()
        swap = _psutil.swap_memory()
        result[0] = float(np.clip(cpu, 0.0, 1.0))
        result[1] = float(np.clip(mem.percent / 100.0, 0.0, 1.0))
        result[2] = float(np.clip(mem.used / max(mem.total, 1), 0.0, 1.0))
        result[3] = float(np.clip(swap.percent / 100.0, 0.0, 1.0))
    except Exception:
        pass

    try:
        disk_io = _psutil.disk_io_counters()
        if disk_io is not None:
            result[4] = float(np.clip(disk_io.read_bytes / _DISK_IO_REF_BYTES, 0.0, 1.0))
            result[5] = float(np.clip(disk_io.write_bytes / _DISK_IO_REF_BYTES, 0.0, 1.0))
    except Exception:
        pass

    try:
        net_io = _psutil.net_io_counters()
        if net_io is not None:
            result[6] = float(np.clip(net_io.bytes_sent / _NET_IO_REF_BYTES, 0.0, 1.0))
            result[7] = float(np.clip(net_io.bytes_recv / _NET_IO_REF_BYTES, 0.0, 1.0))
    except Exception:
        pass

    try:
        result[8] = float(np.clip(len(_psutil.pids()) / _MAX_EXPECTED_PIDS, 0.0, 1.0))
    except Exception:
        pass

    try:
        load = _psutil.getloadavg()
        cpu_count = _psutil.cpu_count() or 1
        result[9] = float(np.clip(load[0] / cpu_count, 0.0, 1.0))
    except Exception:
        pass

    return result


if Env is not None:
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
