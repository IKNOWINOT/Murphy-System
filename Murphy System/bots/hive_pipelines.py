"""Predefined cross-module pipelines from hive_mind_math_patch_v2.0."""
from __future__ import annotations

import json
import os
from typing import Optional

from .scheduler_bot import SchedulerBot
from .memory_manager_bot import MemoryManagerBot
from .scaling_bot import ScalingBot
from .feedback_bot import FeedbackBot
from .optimization_bot import rank_via_centrality
try:
    from .rubixcube_bot import RubixCubeBot
except ImportError:  # pragma: no cover - optional dependency
    RubixCubeBot = None  # type: ignore

_DEFAULT_LOG_PATH = os.environ.get("TASK_TIMING_LOG", "logs/task_timing_log.json")
# Minimum sample size required for a meaningful EWMA estimate.
# With fewer points the average is too noisy to be useful.
_MIN_HISTORY_POINTS = 3
_EWMA_ALPHA = 0.3  # weight for the most-recent observation


def _load_task_durations(task_type: Optional[str] = None, log_path: str = _DEFAULT_LOG_PATH) -> list[float]:
    """Load historical task durations from the execution log.

    Args:
        task_type: Filter to a specific task type.  If ``None``, all records
            are used.
        log_path: Path to the JSON task-timing log.

    Returns:
        List of durations (floats, in seconds), newest-last order.
    """
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    durations: list[float] = []
    for record in data:
        if task_type is None or record.get("task_type") == task_type:
            val = record.get("actual_time") or record.get("duration")
            if val is not None:
                try:
                    durations.append(float(val))
                except (TypeError, ValueError):
                    pass
    return durations


def _ewma(values: list[float], alpha: float = _EWMA_ALPHA) -> float:
    """Compute exponentially weighted moving average (recency-biased).

    Args:
        values: Observations in chronological order (oldest first).
        alpha: Smoothing factor in (0, 1].  Higher ⟹ more weight on recent.

    Returns:
        EWMA of *values*.
    """
    if not values:
        return 1.0
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1.0 - alpha) * result
    return result


def predictive_scheduler(
    sched: SchedulerBot,
    mem: MemoryManagerBot,
    scaling: ScalingBot,
    *,
    task_type: Optional[str] = None,
    log_path: str = _DEFAULT_LOG_PATH,
) -> dict:
    """Run predictive scheduling using historical task-duration data.

    Wires to the task execution log (``log_path``) to retrieve real durations.
    Uses exponentially weighted moving average (EWMA) so that recent durations
    are weighted more heavily.  Falls back to ``[1.0]`` when fewer than
    ``_MIN_HISTORY_POINTS`` data-points exist.

    Returns:
        dict with keys ``etc_seconds`` (float), ``confidence`` (float),
        ``sample_size`` (int), ``source`` ('history' | 'default').
    """
    durations = _load_task_durations(task_type=task_type, log_path=log_path)

    if len(durations) >= _MIN_HISTORY_POINTS:
        etc = _ewma(durations)
        confidence = min(1.0, len(durations) / 20.0)
        source = "history"
    else:
        durations = [1.0]
        etc = 1.0
        confidence = 0.0
        source = "default"

    sched.update_model(durations)
    mem.ttl_check()
    scaling.forecast_demand([int(max(1, etc))])

    return {
        "etc_seconds": round(etc, 4),
        "confidence": round(confidence, 4),
        "sample_size": len(durations),
        "source": source,
    }


def feedback_optimization_cycle(feedback: FeedbackBot, sched: SchedulerBot) -> None:
    centrality = feedback.build_feedback_graph()
    ordering = rank_via_centrality(centrality)
    RubixCubeBot.suggest_reordering = lambda: ordering  # type: ignore
    sched.update_model([1.0])
