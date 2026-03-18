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
