"""
Portfolio – Critical Path Calculation
=======================================

Computes the critical path through a dependency graph using forward/backward
pass scheduling.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations
import logging

from collections import defaultdict
from typing import Dict, List, Set, Tuple

from .dependencies import DependencyManager
from .models import GanttBar


class CriticalPathEngine:
    """Calculates the critical path for a set of Gantt bars.

    The critical path is the longest sequence of dependent tasks that
    determines the minimum project duration.  Tasks on the critical path
    have zero total float.
    """

    def __init__(self, dep_manager: DependencyManager) -> None:
        self._deps = dep_manager

    def compute(self, bars: List[GanttBar]) -> Dict[str, object]:
        """Compute the critical path.

        Returns a dict with:
        - ``critical_items``: list of item IDs on the critical path
        - ``total_duration``: project duration in days
        - ``schedule``: per-item early/late start/finish and float
        """
        bar_map: Dict[str, GanttBar] = {b.item_id: b for b in bars}
        item_ids = list(bar_map.keys())

        if not item_ids:
            return {"critical_items": [], "total_duration": 0, "schedule": {}}

        order = self._deps.topological_sort(item_ids)

        # Forward pass: compute earliest start (ES) and earliest finish (EF)
        es: Dict[str, int] = {}
        ef: Dict[str, int] = {}

        for iid in order:
            preds = self._deps.get_predecessors(iid)
            if not preds or not any(p in bar_map for p in preds):
                es[iid] = 0
            else:
                max_ef = 0
                for pid in preds:
                    if pid in ef:
                        # Find lag
                        lag = self._get_lag(pid, iid)
                        max_ef = max(max_ef, ef[pid] + lag)
                es[iid] = max_ef
            duration = bar_map[iid].duration_days() if iid in bar_map else 0
            ef[iid] = es[iid] + duration

        # Project duration
        project_duration = max(ef.values()) if ef else 0

        # Backward pass: compute latest finish (LF) and latest start (LS)
        lf: Dict[str, int] = {}
        ls: Dict[str, int] = {}

        for iid in reversed(order):
            succs = self._deps.get_successors(iid)
            if not succs or not any(s in bar_map for s in succs):
                lf[iid] = project_duration
            else:
                min_ls = project_duration
                for sid in succs:
                    if sid in ls:
                        lag = self._get_lag(iid, sid)
                        min_ls = min(min_ls, ls[sid] - lag)
                lf[iid] = min_ls
            duration = bar_map[iid].duration_days() if iid in bar_map else 0
            ls[iid] = lf[iid] - duration

        # Total float and critical path
        schedule: Dict[str, Dict[str, int]] = {}
        critical_items: List[str] = []

        for iid in order:
            total_float = ls.get(iid, 0) - es.get(iid, 0)
            schedule[iid] = {
                "early_start": es.get(iid, 0),
                "early_finish": ef.get(iid, 0),
                "late_start": ls.get(iid, 0),
                "late_finish": lf.get(iid, 0),
                "total_float": total_float,
            }
            if total_float == 0:
                critical_items.append(iid)

        return {
            "critical_items": critical_items,
            "total_duration": project_duration,
            "schedule": schedule,
        }

    def _get_lag(self, predecessor_id: str, successor_id: str) -> int:
        """Find the lag between two items."""
        for dep in self._deps.get_dependencies(predecessor_id):
            if dep.successor_id == successor_id:
                return dep.lag_days
        return 0
