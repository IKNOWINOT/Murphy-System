"""
Portfolio – Gantt Engine
=========================

Gantt chart rendering and scheduling engine.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .critical_path import CriticalPathEngine
from .dependencies import DependencyManager
from .models import Baseline, GanttBar, Milestone, MilestoneStatus, _now

logger = logging.getLogger(__name__)


class GanttEngine:
    """Gantt chart engine with dependency tracking, milestones, and baselines.

    Parameters
    ----------
    dep_manager : DependencyManager, optional
        Shared dependency manager.
    """

    def __init__(self, dep_manager: Optional[DependencyManager] = None) -> None:
        self.deps = dep_manager or DependencyManager()
        self._critical_path = CriticalPathEngine(self.deps)
        self._bars: Dict[str, GanttBar] = {}
        self._milestones: Dict[str, Milestone] = {}
        self._baselines: Dict[str, Baseline] = {}

    # -- Gantt bars ---------------------------------------------------------

    def add_bar(
        self,
        item_id: str,
        item_name: str,
        start_date: str,
        end_date: str,
        *,
        board_id: str = "",
        group_id: str = "",
        progress: float = 0.0,
        assignee_ids: Optional[List[str]] = None,
    ) -> GanttBar:
        bar = GanttBar(
            item_id=item_id,
            item_name=item_name,
            board_id=board_id,
            group_id=group_id,
            start_date=start_date,
            end_date=end_date,
            progress=progress,
            assignee_ids=assignee_ids or [],
        )
        self._bars[item_id] = bar
        return bar

    def update_bar(
        self,
        item_id: str,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        progress: Optional[float] = None,
    ) -> GanttBar:
        bar = self._bars.get(item_id)
        if bar is None:
            raise KeyError(f"Gantt bar not found: {item_id!r}")
        if start_date is not None:
            bar.start_date = start_date
        if end_date is not None:
            bar.end_date = end_date
        if progress is not None:
            bar.progress = progress
        return bar

    def remove_bar(self, item_id: str) -> bool:
        if item_id in self._bars:
            del self._bars[item_id]
            return True
        return False

    def get_bars(self, board_id: str = "") -> List[GanttBar]:
        bars = list(self._bars.values())
        if board_id:
            bars = [b for b in bars if b.board_id == board_id]
        return bars

    # -- Milestones ---------------------------------------------------------

    def add_milestone(
        self,
        name: str,
        target_date: str,
        *,
        board_id: str = "",
        owner_id: str = "",
        linked_item_ids: Optional[List[str]] = None,
    ) -> Milestone:
        ms = Milestone(
            name=name,
            board_id=board_id,
            target_date=target_date,
            owner_id=owner_id,
            linked_item_ids=linked_item_ids or [],
        )
        self._milestones[ms.id] = ms
        return ms

    def update_milestone(
        self,
        milestone_id: str,
        *,
        status: Optional[MilestoneStatus] = None,
        target_date: Optional[str] = None,
    ) -> Milestone:
        ms = self._milestones.get(milestone_id)
        if ms is None:
            raise KeyError(f"Milestone not found: {milestone_id!r}")
        if status is not None:
            ms.status = status
        if target_date is not None:
            ms.target_date = target_date
        return ms

    def get_milestones(self, board_id: str = "") -> List[Milestone]:
        milestones = list(self._milestones.values())
        if board_id:
            milestones = [m for m in milestones if m.board_id == board_id]
        return milestones

    # -- Baselines ----------------------------------------------------------

    def create_baseline(
        self,
        name: str,
        board_id: str = "",
        *,
        created_by: str = "",
    ) -> Baseline:
        """Snapshot current bars for a board into a baseline."""
        bars = self.get_bars(board_id)
        # Deep-copy bars for the snapshot
        snapshot_bars = [
            GanttBar(
                item_id=b.item_id,
                item_name=b.item_name,
                board_id=b.board_id,
                group_id=b.group_id,
                start_date=b.start_date,
                end_date=b.end_date,
                progress=b.progress,
                assignee_ids=list(b.assignee_ids),
            )
            for b in bars
        ]
        baseline = Baseline(
            name=name,
            board_id=board_id,
            bars=snapshot_bars,
            created_by=created_by,
        )
        self._baselines[baseline.id] = baseline
        return baseline

    def get_baselines(self, board_id: str = "") -> List[Baseline]:
        baselines = list(self._baselines.values())
        if board_id:
            baselines = [bl for bl in baselines if bl.board_id == board_id]
        return baselines

    def get_baseline(self, baseline_id: str) -> Optional[Baseline]:
        return self._baselines.get(baseline_id)

    # -- Critical path ------------------------------------------------------

    def compute_critical_path(self, board_id: str = "") -> Dict[str, Any]:
        """Compute critical path for bars, optionally filtered by board."""
        bars = self.get_bars(board_id)
        result = self._critical_path.compute(bars)
        # Mark bars as critical
        critical_set = set(result.get("critical_items", []))
        for bar in bars:
            bar.is_critical = bar.item_id in critical_set
        return result

    # -- Full render --------------------------------------------------------

    def render_gantt(self, board_id: str = "") -> Dict[str, Any]:
        """Render complete Gantt data with bars, dependencies, milestones."""
        bars = self.get_bars(board_id)
        cp = self.compute_critical_path(board_id)
        milestones = self.get_milestones(board_id)
        baselines = self.get_baselines(board_id)

        # Collect relevant dependencies
        item_ids = {b.item_id for b in bars}
        all_deps = []
        for iid in item_ids:
            for dep in self.deps.get_dependencies(iid):
                if dep.to_dict() not in all_deps:
                    all_deps.append(dep.to_dict())

        return {
            "bars": [b.to_dict() for b in bars],
            "dependencies": all_deps,
            "milestones": [m.to_dict() for m in milestones],
            "baselines": [bl.to_dict() for bl in baselines],
            "critical_path": cp,
        }
