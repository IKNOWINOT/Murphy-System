"""Simple converter from natural language to task JSON."""

from __future__ import annotations

from typing import Dict


def parse_user_input_to_json(text: str) -> Dict[str, any]:
    """Very naive parser converting 'visualize X' to a chart task."""
    if text.startswith("visualize"):
        parts = text.split()
        data = [int(x) for x in parts[1:]] if len(parts) > 1 else []
        return {
            "task_id": "auto", "task_type": "generate_chart", "assigned_to": "VisualizationBot",
            "parameters": {"data": data, "type": "bar"}, "priority": 1
        }
    return {
        "task_id": "auto",
        "task_type": "unknown",
        "assigned_to": "Unknown",
        "parameters": {},
        "priority": 1,
    }
