"""Execute hierarchical plans recursively."""
from __future__ import annotations

from typing import List
from .plan_structurer_bot import SubPlan

class RecursiveExecutorBot:
    def execute(self, plan: SubPlan) -> List[str]:
        executed = []
        for step in plan.steps:
            executed.append(step)
            plan.completed_steps.append(step)
        return executed
