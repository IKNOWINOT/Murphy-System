"""
Global Aggregator for Rosetta State Management.

Provides system-wide views by aggregating metrics across all agents.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .rosetta_manager import RosettaManager

logger = logging.getLogger(__name__)


class GlobalAggregator:
    """Aggregate Rosetta metrics across all agents."""

    def __init__(self, manager: RosettaManager) -> None:
        self._manager = manager

    def aggregate_system_health(self) -> Dict[str, Any]:
        """Aggregate system health across all agents."""
        agents = self._manager.list_agents()
        total_uptime = 0.0
        total_memory = 0.0
        total_cpu = 0.0
        total_active_tasks = 0
        status_counts: Dict[str, int] = {}
        count = 0

        for aid in agents:
            state = self._manager.load_state(aid)
            if state is None:
                continue
            count += 1
            ss = state.system_state
            total_uptime += ss.uptime_seconds
            total_memory += ss.memory_usage_mb
            total_cpu += ss.cpu_usage_percent
            total_active_tasks += ss.active_tasks
            status_counts[ss.status] = status_counts.get(ss.status, 0) + 1

        return {
            "agent_count": count,
            "total_uptime_seconds": total_uptime,
            "avg_memory_mb": total_memory / count if count else 0,
            "avg_cpu_percent": total_cpu / count if count else 0,
            "total_active_tasks": total_active_tasks,
            "status_counts": status_counts,
        }

    def aggregate_goal_progress(self) -> Dict[str, Any]:
        """Aggregate goal completion rates across all agents."""
        agents = self._manager.list_agents()
        total = 0
        by_status: Dict[str, int] = {}
        progress_sum = 0.0

        for aid in agents:
            state = self._manager.load_state(aid)
            if state is None:
                continue
            for goal in state.agent_state.active_goals:
                total += 1
                status_val = goal.status if isinstance(goal.status, str) else goal.status.value
                by_status[status_val] = by_status.get(status_val, 0) + 1
                progress_sum += goal.progress_percent

        return {
            "total_goals": total,
            "by_status": by_status,
            "avg_progress_percent": progress_sum / total if total else 0,
        }

    def aggregate_automation_coverage(self) -> Dict[str, Any]:
        """Aggregate automation coverage metrics across all agents."""
        agents = self._manager.list_agents()
        by_category: Dict[str, Dict[str, Any]] = {}

        for aid in agents:
            state = self._manager.load_state(aid)
            if state is None:
                continue
            for ap in state.automation_progress:
                cat = ap.category
                if cat not in by_category:
                    by_category[cat] = {
                        "total_items": 0,
                        "completed_items": 0,
                    }
                by_category[cat]["total_items"] += ap.total_items
                by_category[cat]["completed_items"] += ap.completed_items

        for cat, info in by_category.items():
            total = info["total_items"]
            info["coverage_percent"] = (
                (info["completed_items"] / total * 100) if total else 0.0
            )

        return {"by_category": by_category}

    def get_global_view(self) -> Dict[str, Any]:
        """Full system-wide aggregation."""
        return {
            "system_health": self.aggregate_system_health(),
            "goal_progress": self.aggregate_goal_progress(),
            "automation_coverage": self.aggregate_automation_coverage(),
        }
