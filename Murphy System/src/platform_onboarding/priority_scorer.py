# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Priority scorer: ranks onboarding tasks by value density, blocker count, and category."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .task_catalog import OnboardingTask

_CATEGORY_PRIORITY: Dict[str, float] = {
    "cloud_credit": 100,
    "grant": 90,
    "api_key": 80,
    "financing": 70,
    "marketplace": 60,
    "compliance": 50,
    "international": 40,
}

_VALUE_TYPE_PRIORITY: Dict[str, float] = {
    "free_money": 100,
    "prerequisite": 90,
    "revenue_channel": 70,
    "trust_signal": 40,
}


def _parse_value_dollars(estimated_value: str | None) -> float:
    """Extract a rough dollar figure from an estimated_value string."""
    if not estimated_value:
        return 0.0
    # Handle "15-20% of qualified R&D spend" → treat as moderate value
    if "%" in estimated_value:
        return 50_000.0
    # Find all numbers (possibly with K/M suffix)
    nums = re.findall(r"\$?([\d,]+)([KkMm]?)", estimated_value.replace(",", ""))
    values = []
    for digits, suffix in nums:
        n = float(digits)
        if suffix.upper() == "K":
            n *= 1_000
        elif suffix.upper() == "M":
            n *= 1_000_000
        values.append(n)
    if not values:
        return 0.0
    return sum(values) / len(values)


class PriorityScorer:
    """Scores and ranks onboarding tasks by multi-factor priority."""

    def score_task(self, task: OnboardingTask, session_state: Dict) -> float:
        """Compute a numeric priority score for a single task."""
        value_dollars = _parse_value_dollars(task.estimated_value)
        time = max(task.time_estimate_minutes, 1)
        value_density = (value_dollars / time) if value_dollars > 0 else 0.0
        # Normalize value_density (cap at 10_000 $/min → score 100)
        value_density_score = min(value_density / 100.0, 100.0)

        blocker_score = len(task.blocks) * 10.0

        cat_score = _CATEGORY_PRIORITY.get(task.category, 50)
        vt_score = _VALUE_TYPE_PRIORITY.get(task.value_type, 50)

        return (
            value_density_score * 0.3
            + blocker_score * 0.3
            + cat_score * 0.2
            + vt_score * 0.2
        )

    def score_tasks(
        self,
        tasks: List[OnboardingTask],
        session_state: Dict,
    ) -> List[Tuple[OnboardingTask, float]]:
        """Return tasks sorted descending by priority score."""
        scored = [(t, self.score_task(t, session_state)) for t in tasks]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
