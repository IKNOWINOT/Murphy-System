"""
PATCH-130 — src/scheduler_agent.py
Murphy System — Scheduler Agent (position 3 / RosettaSoul)
Decides WHEN and HOW OFTEN actions should execute.
Note: This is the RosettaSoul Scheduler *agent*, distinct from SwarmScheduler (APScheduler wrapper).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.scheduler_agent")


class SchedulerAgent(AgentBase):
    """Position 3 — Scheduler. Methodical, bias: timing_precision."""

    def __init__(self):
        super().__init__("scheduler")

    def act(self, signal: Dict) -> Dict:
        """Evaluate timing for a proposed action and advise on schedule."""
        action = signal.get("action", "unknown")
        urgency = signal.get("urgency", "low")
        domain  = signal.get("domain", "general")

        # Look at current scheduler job list
        try:
            from src.swarm_scheduler import get_swarm_scheduler
            sched = get_swarm_scheduler()
            jobs = sched.list_jobs() if hasattr(sched, "list_jobs") else []
        except Exception:
            jobs = []

        # Recommend timing
        if urgency == "high":
            recommendation = "immediate"
            delay_s = 0
        elif urgency == "medium":
            recommendation = "within_5_minutes"
            delay_s = 300
        else:
            recommendation = "next_scheduled_window"
            delay_s = 900

        return {
            "status": "scheduled",
            "action": action,
            "urgency": urgency,
            "recommendation": recommendation,
            "delay_s": delay_s,
            "active_jobs": len(jobs),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


_scheduler_agent: Optional[SchedulerAgent] = None

def get_scheduler_agent() -> SchedulerAgent:
    global _scheduler_agent
    if _scheduler_agent is None:
        _scheduler_agent = SchedulerAgent()
    return _scheduler_agent
