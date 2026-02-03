"""Parse free-form user text into structured task JSON."""
from __future__ import annotations

from typing import Dict, Any


def parse_user_input(user_text: str) -> Dict[str, Any] | None:
    text = user_text.lower()
    if "simulate" in text:
        return {
            "task_type": "run_simulation",
            "assigned_to": "SimulationBot",
            "parameters": {
                "load": 1200,
                "material": "titanium",
                "temperature": 500,
            },
        }
    if "optimize" in text:
        return {
            "task_type": "refine_workflow",
            "assigned_to": "OptimizationBot",
            "parameters": {"workflow_id": "fusion_energy_matrix"},
        }
    return None
