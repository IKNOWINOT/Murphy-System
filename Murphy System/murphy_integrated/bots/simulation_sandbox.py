"""Physics simulation sandbox."""
from __future__ import annotations

import numpy as np


def simulate(step_count: int, gravity: float = 9.81) -> np.ndarray:
    """Return simple projectile path as a demo."""
    t = np.linspace(0, step_count / 10, step_count)
    y = 0.5 * -gravity * t ** 2
    return y


def iteration_loss(v_prev: np.ndarray, v_next: np.ndarray) -> float:
    """Return L2 loss between iterations."""
    return float(np.linalg.norm(v_next - v_prev))


def convergence_checker(loss: float, eps: float = 1e-3) -> bool:
    """Return True if convergence reached."""
    return loss < eps
