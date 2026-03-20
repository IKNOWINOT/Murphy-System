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
        hitl_scopes = [
            str((trace.recovery or {}).get("gate_enforcement_summary", {}).get("hitl_scope", "none"))
            for trace in traces
            if trace.execution_status == "hitl_required"
        ]
        counts = {
            "completed": sum(1 for status in statuses if status == "completed"),
            "simulated": sum(1 for status in statuses if status == "simulated"),
            "swarm_planned": sum(1 for status in statuses if status == "swarm_planned"),
            "review_required": sum(1 for status in statuses if status == "review_required"),
            "hitl_required": sum(1 for status in statuses if status == "hitl_required"),
            "fallback_completed": sum(1 for status in statuses if status == "fallback_completed"),
            "blocked": sum(1 for status in statuses if status == "blocked"),
        }
        hitl_scope_counts = {
            "founder": sum(1 for scope in hitl_scopes if scope == "founder"),
            "organization": sum(1 for scope in hitl_scopes if scope == "organization"),
            "generic": sum(1 for scope in hitl_scopes if scope == "generic"),
            "none": sum(1 for scope in hitl_scopes if scope == "none"),
        }
        return {
            "window": limit,
            "total": len(traces),
            "counts": counts,
            "approval_pending": counts["review_required"] + counts["hitl_required"],
            "fallback_engaged": counts["fallback_completed"],
            "blocked": counts["blocked"],
            "hitl_scope_counts": hitl_scope_counts,
            "latest_hitl_scope": hitl_scopes[0] if hitl_scopes else "none",
            "latest_status": statuses[0] if statuses else None,
        }
