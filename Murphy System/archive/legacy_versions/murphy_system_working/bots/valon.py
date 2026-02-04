"""Valon planning with dynamic weights and hierarchical subplans."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
try:
    import lightgbm as lgb
except Exception:  # pragma: no cover - optional dependency
    lgb = None


@dataclass
class Plan:
    name: str
    weight: float = 1.0
    progress: float = 0.0  # percentage completion
    subplans: List['Plan'] = field(default_factory=list)


def prioritize(plans: List[Plan], features: np.ndarray) -> List[Plan]:
    """Default prioritization using exponential weights."""
    weights = np.exp(features)
    for plan, w in zip(plans, weights):
        plan.weight = float(w)
    return sorted(plans, key=lambda p: p.weight, reverse=True)


class Prioritizer:
    def __init__(self, coef: np.ndarray):
        self.coef = coef

    def prioritize(self, plans: List[Plan], feature_matrix: np.ndarray) -> List[Plan]:
        logits = feature_matrix @ self.coef
        weights = 1 / (1 + np.exp(-logits))
        for plan, w in zip(plans, weights):
            plan.weight = float(w)
        return sorted(plans, key=lambda p: p.weight, reverse=True)


def ml_prioritize(plans: List[Plan], feature_matrix: np.ndarray, model_path: str) -> List[Plan]:
    """Prioritize plans using a LightGBM model."""
    if lgb is None:
        raise ImportError('lightgbm is required for ml_prioritize')
    booster = lgb.Booster(model_file=model_path)
    scores = booster.predict(feature_matrix)
    for plan, score in zip(plans, scores):
        plan.weight = float(score)
    return sorted(plans, key=lambda p: p.weight, reverse=True)


def execute_partial_plan(plan: Plan, step: int) -> None:
    """Mark a portion of a plan as completed."""
    if plan.subplans:
        n = len(plan.subplans)
        increment = 100 / n
        for idx, sub in enumerate(plan.subplans, start=1):
            if idx <= step:
                sub.progress = 100.0
        plan.progress = min(100.0, step * increment)
    else:
        plan.progress = min(100.0, step)
