"""Break objectives into hierarchical subplans."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class SubPlan:
    id: str
    steps: List[str]
    parent_id: Optional[str] = None
    depth: int = 0
    completed_steps: List[str] = field(default_factory=list)

class PlanStructurerBot:
    def create_subplans(self, plan_id: str, steps: List[str], chunk: int = 2) -> List[SubPlan]:
        return [SubPlan(id=f"{plan_id}-{i}", steps=steps[i:i+chunk], parent_id=plan_id, depth=1) for i in range(0, len(steps), chunk)]
