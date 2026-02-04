"""Rate-of-change metrics for Vanta control adjustments."""
from __future__ import annotations

from typing import Dict, Any


def compute_roc(current: float, previous: float, time_elapsed: float) -> float:
    """Compute rate of change given current and previous values."""
    return (current - previous) / max(time_elapsed, 1e-3)


def adjust_vanta_params(roc_dict: Dict[str, float], *, aion=None, scheduler=None) -> None:
    """Adjust system parameters based on ROC thresholds."""
    if roc_dict.get("trust_drift", 0.0) > 0.15 and hasattr(aion, "reduce_memory_scope"):
        aion.reduce_memory_scope()
    elif roc_dict.get("latency_gain", 0.0) > 0.2 and hasattr(scheduler, "increase_batch_parallelism"):
        scheduler.increase_batch_parallelism()
