from __future__ import annotations

from typing import Dict, List, Optional

from .contracts import ControlTrace


class TraceStore:
    def __init__(self) -> None:
        self._traces: Dict[str, ControlTrace] = {}
        self._order: List[str] = []

    def save(self, trace: ControlTrace) -> ControlTrace:
        self._traces[trace.trace_id] = trace
        if trace.trace_id not in self._order:
            self._order.append(trace.trace_id)
        trace.touch()
        return trace

    def get(self, trace_id: str) -> Optional[ControlTrace]:
        return self._traces.get(trace_id)

    def recent(self, limit: int = 20) -> List[ControlTrace]:
        ids = list(reversed(self._order[-limit:]))
        return [self._traces[i] for i in ids if i in self._traces]

    def outcome_summary(self, limit: int = 20) -> Dict[str, object]:
        traces = self.recent(limit)
        statuses = [trace.execution_status for trace in traces]
        counts = {
            "completed": sum(1 for status in statuses if status == "completed"),
            "simulated": sum(1 for status in statuses if status == "simulated"),
            "swarm_planned": sum(1 for status in statuses if status == "swarm_planned"),
            "review_required": sum(1 for status in statuses if status == "review_required"),
            "hitl_required": sum(1 for status in statuses if status == "hitl_required"),
            "fallback_completed": sum(1 for status in statuses if status == "fallback_completed"),
            "blocked": sum(1 for status in statuses if status == "blocked"),
        }
        return {
            "window": limit,
            "total": len(traces),
            "counts": counts,
            "approval_pending": counts["review_required"] + counts["hitl_required"],
            "fallback_engaged": counts["fallback_completed"],
            "blocked": counts["blocked"],
            "latest_status": statuses[0] if statuses else None,
        }
