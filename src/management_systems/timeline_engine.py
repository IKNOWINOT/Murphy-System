"""
Management Systems – Timeline Engine
=================================

Gantt-style timeline management with task dependencies, milestone
tracking, critical-path calculation, baseline comparison, resource
allocation, conflict detection, auto-scheduling, and ASCII-based
rendering for Matrix messages.

Integration points:
    - Timeline items link to :class:`~board_engine.BoardItem` by ID
    - Milestone events are published via ``event_bridge.py`` (PR 2)
    - ASCII output is sent through ``message_router.py`` (PR 3)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GANTT_BAR_CHAR: str = "█"
GANTT_DONE_CHAR: str = "░"
GANTT_MILESTONE_CHAR: str = "◆"
GANTT_DISPLAY_WIDTH: int = 40   # characters for the bar area
DATE_FMT: str = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DependencyType(Enum):
    """Dependency relationship between two timeline items."""

    FINISH_TO_START = "finish_to_start"   # B starts after A finishes
    START_TO_START = "start_to_start"     # B starts after A starts
    FINISH_TO_FINISH = "finish_to_finish" # B finishes after A finishes
    START_TO_FINISH = "start_to_finish"   # B finishes after A starts


class ConstraintType(Enum):
    """Scheduling constraint types."""

    ASAP = "asap"             # As Soon As Possible
    ALAP = "alap"             # As Late As Possible
    MUST_START_ON = "must_start_on"
    MUST_FINISH_ON = "must_finish_on"
    START_NO_EARLIER_THAN = "start_no_earlier_than"
    FINISH_NO_LATER_THAN = "finish_no_later_than"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FMT).date()


def _fmt_date(d: date) -> str:
    return d.strftime(DATE_FMT)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Dependency:
    """Directed dependency between two timeline items.

    Args:
        from_id: Predecessor item ID.
        to_id: Successor item ID.
        dep_type: Relationship type.
        lag_days: Additional lag in calendar days.
    """

    from_id: str
    to_id: str
    dep_type: DependencyType = DependencyType.FINISH_TO_START
    lag_days: int = 0
    id: str = field(default_factory=_uid)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "dep_type": self.dep_type.value,
            "lag_days": self.lag_days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Dependency":
        obj = cls(
            from_id=data["from_id"],
            to_id=data["to_id"],
            dep_type=DependencyType(data.get("dep_type", "finish_to_start")),
            lag_days=data.get("lag_days", 0),
        )
        obj.id = data.get("id", obj.id)
        return obj


@dataclass
class Milestone:
    """A dated marker on the timeline.

    Args:
        name: Display name.
        target_date: Planned completion date (ISO 8601).
        completed: Whether the milestone has been achieved.
        description: Optional detail text.
    """

    name: str
    target_date: str
    completed: bool = False
    description: str = ""
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    @property
    def date_obj(self) -> date:
        return _parse_date(self.target_date)

    @property
    def is_overdue(self) -> bool:
        return not self.completed and self.date_obj < date.today()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "target_date": self.target_date,
            "completed": self.completed,
            "description": self.description,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Milestone":
        obj = cls(
            name=data["name"],
            target_date=data["target_date"],
            completed=data.get("completed", False),
            description=data.get("description", ""),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        return obj


@dataclass
class TimelineItem:
    """A task or work package on the Gantt chart.

    Args:
        name: Display name.
        start_date: Planned start date (ISO 8601).
        end_date: Planned end date (ISO 8601).
        assignee: Responsible party (Matrix user ID or name).
        progress: Completion percentage ``[0, 100]``.
        board_item_id: Optional linked :class:`~board_engine.BoardItem` ID.
        baseline_start: Original planned start for baseline comparison.
        baseline_end: Original planned end for baseline comparison.
        resource: Resource/team name for allocation view.
        constraint_type: Scheduling constraint.
        constraint_date: Date for must_start_on / finish_no_later_than.
    """

    name: str
    start_date: str
    end_date: str
    assignee: str = ""
    progress: float = 0.0
    board_item_id: str = ""
    baseline_start: str = ""
    baseline_end: str = ""
    resource: str = ""
    constraint_type: ConstraintType = ConstraintType.ASAP
    constraint_date: str = ""
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    @property
    def start(self) -> date:
        return _parse_date(self.start_date)

    @property
    def end(self) -> date:
        return _parse_date(self.end_date)

    @property
    def duration_days(self) -> int:
        return max(0, (self.end - self.start).days + 1)

    @property
    def is_overdue(self) -> bool:
        return self.progress < 100.0 and self.end < date.today()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "assignee": self.assignee,
            "progress": self.progress,
            "board_item_id": self.board_item_id,
            "baseline_start": self.baseline_start,
            "baseline_end": self.baseline_end,
            "resource": self.resource,
            "constraint_type": self.constraint_type.value,
            "constraint_date": self.constraint_date,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineItem":
        obj = cls(
            name=data["name"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            assignee=data.get("assignee", ""),
            progress=float(data.get("progress", 0.0)),
            board_item_id=data.get("board_item_id", ""),
            baseline_start=data.get("baseline_start", ""),
            baseline_end=data.get("baseline_end", ""),
            resource=data.get("resource", ""),
            constraint_type=ConstraintType(
                data.get("constraint_type", ConstraintType.ASAP.value)
            ),
            constraint_date=data.get("constraint_date", ""),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        return obj


@dataclass
class CriticalPath:
    """Result of a critical-path analysis.

    Attributes:
        item_ids: Ordered list of item IDs on the critical path.
        total_duration_days: Total duration of the critical path.
        slack_map: Mapping of item_id → total float (slack days).
    """

    item_ids: List[str]
    total_duration_days: int
    slack_map: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_ids": self.item_ids,
            "total_duration_days": self.total_duration_days,
            "slack_map": self.slack_map,
        }


# ---------------------------------------------------------------------------
# Timeline Engine
# ---------------------------------------------------------------------------


class TimelineEngine:
    """Gantt-style timeline manager for Murphy Monday.

    Supports items, milestones, dependencies, critical-path analysis,
    conflict detection, auto-scheduling, and ASCII rendering.

    Example::

        engine = TimelineEngine()
        a = engine.add_item("Design", "2025-01-06", "2025-01-10")
        b = engine.add_item("Development", "2025-01-13", "2025-01-24")
        engine.add_dependency(a.id, b.id)
        cp = engine.calculate_critical_path()
        print(engine.render_gantt())
    """

    def __init__(self) -> None:
        self._items: Dict[str, TimelineItem] = {}
        self._milestones: Dict[str, Milestone] = {}
        self._dependencies: Dict[str, Dependency] = {}

    # -- Items --------------------------------------------------------------

    def add_item(
        self,
        name: str,
        start_date: str,
        end_date: str,
        *,
        assignee: str = "",
        progress: float = 0.0,
        board_item_id: str = "",
        resource: str = "",
        constraint_type: ConstraintType = ConstraintType.ASAP,
        constraint_date: str = "",
    ) -> TimelineItem:
        """Add a task to the timeline.

        Args:
            name: Task display name.
            start_date: ISO 8601 start date.
            end_date: ISO 8601 end date.
            assignee: Responsible party.
            progress: Current completion percentage.
            board_item_id: Linked board item.
            resource: Resource / team name.
            constraint_type: Scheduling constraint.
            constraint_date: Date for date-based constraints.

        Returns:
            The created :class:`TimelineItem`.
        """
        item = TimelineItem(
            name=name,
            start_date=start_date,
            end_date=end_date,
            assignee=assignee,
            progress=progress,
            board_item_id=board_item_id,
            resource=resource,
            constraint_type=constraint_type,
            constraint_date=constraint_date,
        )
        self._items[item.id] = item
        logger.debug("Timeline item added: %s", name)
        return item

    def get_item(self, item_id: str) -> Optional[TimelineItem]:
        return self._items.get(item_id)

    def list_items(self) -> List[TimelineItem]:
        """Return all timeline items sorted by start date."""
        return sorted(self._items.values(), key=lambda i: i.start_date)

    def update_progress(self, item_id: str, progress: float) -> bool:
        """Update the completion percentage of a timeline item.

        Args:
            item_id: Target item.
            progress: New progress value ``[0, 100]``.

        Returns:
            *True* on success, *False* if not found.
        """
        item = self._items.get(item_id)
        if item is None:
            return False
        item.progress = max(0.0, min(100.0, progress))
        return True

    def delete_item(self, item_id: str) -> bool:
        """Remove an item and all its dependencies."""
        if item_id not in self._items:
            return False
        del self._items[item_id]
        # Remove related dependencies
        self._dependencies = {
            did: dep
            for did, dep in self._dependencies.items()
            if dep.from_id != item_id and dep.to_id != item_id
        }
        return True

    # -- Milestones ---------------------------------------------------------

    def add_milestone(
        self,
        name: str,
        target_date: str,
        *,
        description: str = "",
    ) -> Milestone:
        """Create a new milestone marker.

        Args:
            name: Milestone display name.
            target_date: ISO 8601 target date.
            description: Optional description.

        Returns:
            The created :class:`Milestone`.
        """
        ms = Milestone(name=name, target_date=target_date, description=description)
        self._milestones[ms.id] = ms
        logger.debug("Milestone added: %s on %s", name, target_date)
        return ms

    def complete_milestone(self, milestone_id: str) -> bool:
        """Mark a milestone as completed."""
        ms = self._milestones.get(milestone_id)
        if ms is None:
            return False
        ms.completed = True
        return True

    def list_milestones(self) -> List[Milestone]:
        """Return all milestones sorted by target date."""
        return sorted(self._milestones.values(), key=lambda m: m.target_date)

    # -- Dependencies -------------------------------------------------------

    def add_dependency(
        self,
        from_id: str,
        to_id: str,
        dep_type: DependencyType = DependencyType.FINISH_TO_START,
        *,
        lag_days: int = 0,
    ) -> Dependency:
        """Register a dependency between two timeline items.

        Args:
            from_id: Predecessor item ID.
            to_id: Successor item ID.
            dep_type: Relationship type.
            lag_days: Additional lag in calendar days.

        Returns:
            The new :class:`Dependency`.

        Raises:
            ValueError: If a cycle would be introduced.
        """
        if self._would_create_cycle(from_id, to_id):
            raise ValueError(
                f"Adding dependency {from_id}→{to_id} would create a cycle"
            )
        dep = Dependency(
            from_id=from_id, to_id=to_id, dep_type=dep_type, lag_days=lag_days
        )
        self._dependencies[dep.id] = dep
        return dep

    def remove_dependency(self, dep_id: str) -> bool:
        """Remove a dependency by ID."""
        if dep_id in self._dependencies:
            del self._dependencies[dep_id]
            return True
        return False

    def get_dependencies_for(self, item_id: str) -> List[Dependency]:
        """Return all dependencies where *item_id* is the successor."""
        return [d for d in self._dependencies.values() if d.to_id == item_id]

    # -- Critical Path Analysis ---------------------------------------------

    def calculate_critical_path(self) -> CriticalPath:
        """Compute the critical path using a simplified CPM algorithm.

        Performs forward and backward passes based on item durations and
        finish-to-start dependencies.  Items with zero total float are on
        the critical path.

        Returns:
            A :class:`CriticalPath` result.
        """
        items = self._items
        if not items:
            return CriticalPath(item_ids=[], total_duration_days=0, slack_map={})

        # Build adjacency (FS only for simplicity)
        successors: Dict[str, List[str]] = {iid: [] for iid in items}
        predecessors: Dict[str, List[str]] = {iid: [] for iid in items}
        for dep in self._dependencies.values():
            if dep.dep_type == DependencyType.FINISH_TO_START:
                if dep.from_id in successors and dep.to_id in predecessors:
                    successors[dep.from_id].append(dep.to_id)
                    predecessors[dep.to_id].append(dep.from_id)

        # Topological sort (Kahn's algorithm)
        in_degree = {iid: len(predecessors[iid]) for iid in items}
        queue = [iid for iid, deg in in_degree.items() if deg == 0]
        topo_order: List[str] = []
        while queue:
            node = queue.pop(0)
            topo_order.append(node)
            for succ in successors[node]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        # Forward pass – earliest start/finish
        es: Dict[str, int] = {}  # earliest start (day offset from project start)
        ef: Dict[str, int] = {}  # earliest finish
        min_start = min(it.start for it in items.values())
        for iid in topo_order:
            item = items[iid]
            day_offset = (item.start - min_start).days
            if predecessors[iid]:
                es[iid] = max(ef.get(p, 0) for p in predecessors[iid])
            else:
                es[iid] = day_offset
            ef[iid] = es[iid] + items[iid].duration_days

        project_duration = max(ef.values()) if ef else 0

        # Backward pass – latest start/finish
        lf: Dict[str, int] = {}
        ls: Dict[str, int] = {}
        for iid in reversed(topo_order):
            if successors[iid]:
                lf[iid] = min(ls.get(s, project_duration) for s in successors[iid])
            else:
                lf[iid] = project_duration
            ls[iid] = lf[iid] - items[iid].duration_days

        # Total float
        slack: Dict[str, int] = {
            iid: (ls.get(iid, 0) - es.get(iid, 0)) for iid in items
        }
        critical_ids = [
            iid for iid in topo_order if slack.get(iid, 0) == 0
        ]

        return CriticalPath(
            item_ids=critical_ids,
            total_duration_days=project_duration,
            slack_map=slack,
        )

    # -- Conflict Detection -------------------------------------------------

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """Detect scheduling conflicts (dependency violations).

        Checks whether each dependency's relationship constraint is
        satisfied given current planned dates.

        Returns:
            List of conflict dicts with keys ``from_id``, ``to_id``,
            ``dep_type``, and ``description``.
        """
        conflicts: List[Dict[str, Any]] = []
        for dep in self._dependencies.values():
            pred = self._items.get(dep.from_id)
            succ = self._items.get(dep.to_id)
            if pred is None or succ is None:
                continue
            lag = timedelta(days=dep.lag_days)
            if dep.dep_type == DependencyType.FINISH_TO_START:
                if succ.start < pred.end + lag:
                    conflicts.append({
                        "from_id": dep.from_id,
                        "to_id": dep.to_id,
                        "dep_type": dep.dep_type.value,
                        "description": (
                            f"'{succ.name}' starts on {succ.start_date} but "
                            f"'{pred.name}' finishes on {pred.end_date}"
                        ),
                    })
            elif dep.dep_type == DependencyType.START_TO_START:
                if succ.start < pred.start + lag:
                    conflicts.append({
                        "from_id": dep.from_id,
                        "to_id": dep.to_id,
                        "dep_type": dep.dep_type.value,
                        "description": (
                            f"'{succ.name}' starts before '{pred.name}' does"
                        ),
                    })
        return conflicts

    # -- Auto-Scheduling ----------------------------------------------------

    def auto_schedule(self, project_start: str) -> Dict[str, Tuple[str, str]]:
        """Reschedule all items based on dependencies from *project_start*.

        Performs a forward pass and assigns earliest-start dates while
        preserving each item's original duration.

        Args:
            project_start: ISO 8601 date for the project start.

        Returns:
            Mapping of item_id → ``(new_start_date, new_end_date)``.
        """
        base = _parse_date(project_start)

        # Build finish-to-start map
        successors: Dict[str, List[Dependency]] = {iid: [] for iid in self._items}
        predecessors: Dict[str, List[str]] = {iid: [] for iid in self._items}
        for dep in self._dependencies.values():
            if dep.from_id in successors and dep.to_id in predecessors:
                successors[dep.from_id].append(dep)
                predecessors[dep.to_id].append(dep.from_id)

        # Topological sort
        in_degree = {iid: len(predecessors[iid]) for iid in self._items}
        queue = [iid for iid, deg in in_degree.items() if deg == 0]
        topo: List[str] = []
        while queue:
            node = queue.pop(0)
            topo.append(node)
            for dep in successors[node]:
                succ = dep.to_id
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        new_dates: Dict[str, date] = {}  # item_id → new start date
        result: Dict[str, Tuple[str, str]] = {}

        for iid in topo:
            item = self._items[iid]
            preds = [dep for dep in self._dependencies.values() if dep.to_id == iid]
            if not preds:
                earliest = base
            else:
                earliest = base
                for dep in preds:
                    pred_start = new_dates.get(dep.from_id, base)
                    pred_item = self._items.get(dep.from_id)
                    if pred_item is None:
                        continue
                    # duration_days uses inclusive counting: end = start + (duration-1).
                    # E.g. Jan 1–Jan 5 → duration_days=5; pred ends Jan 5
                    # (pred_start + timedelta(5) = Jan 6) which is the correct
                    # FINISH_TO_START successor start. The -1 only applies when
                    # computing an end date from a start date (line below).
                    dur = pred_item.duration_days
                    lag = timedelta(days=dep.lag_days)
                    if dep.dep_type == DependencyType.FINISH_TO_START:
                        # successor starts the day after predecessor ends
                        cand = pred_start + timedelta(days=dur) + lag
                    elif dep.dep_type == DependencyType.START_TO_START:
                        cand = pred_start + lag
                    elif dep.dep_type == DependencyType.FINISH_TO_FINISH:
                        # both items finish on the same day; back-compute successor start
                        cand = pred_start + timedelta(days=dur) + lag - timedelta(days=item.duration_days)
                    else:  # START_TO_FINISH: successor finishes when predecessor starts
                        cand = pred_start + lag
                    earliest = max(earliest, cand)

            new_dates[iid] = earliest
            # end = start + (duration - 1) because both endpoints are inclusive
            new_end = earliest + timedelta(days=item.duration_days - 1)
            item.start_date = _fmt_date(earliest)
            item.end_date = _fmt_date(new_end)
            result[iid] = (item.start_date, item.end_date)

        return result

    # -- ASCII Rendering ----------------------------------------------------

    def render_gantt(
        self,
        *,
        title: str = "Timeline",
        show_milestones: bool = True,
        bar_width: int = GANTT_DISPLAY_WIDTH,
    ) -> str:
        """Render a Gantt chart as an ASCII string suitable for Matrix.

        Args:
            title: Chart title.
            show_milestones: Include milestone markers.
            bar_width: Width of the bar region in characters.

        Returns:
            Multi-line Markdown code block.
        """
        items = self.list_items()
        if not items:
            return "No timeline items to display."

        all_starts = [i.start for i in items]
        all_ends = [i.end for i in items]
        if show_milestones:
            for ms in self._milestones.values():
                all_starts.append(ms.date_obj)
                all_ends.append(ms.date_obj)

        proj_start = min(all_starts)
        proj_end = max(all_ends)
        total_days = max(1, (proj_end - proj_start).days + 1)

        name_width = min(30, max((len(i.name) for i in items), default=10))
        lines = [
            f"**{title}**",
            "```",
            f"{'Task':<{name_width}} │ {'Start':>10} {'End':>10} │ Chart",
            "─" * (name_width + 1) + "┼" + "─" * 23 + "┼" + "─" * bar_width,
        ]

        for item in items:
            offset_start = (item.start - proj_start).days
            offset_end = (item.end - proj_start).days
            bar_start = int(offset_start / total_days * bar_width)
            bar_len = max(1, int((offset_end - offset_start + 1) / total_days * bar_width))
            done_len = int(item.progress / 100 * bar_len)
            bar = (
                " " * bar_start
                + GANTT_BAR_CHAR * done_len
                + GANTT_DONE_CHAR * (bar_len - done_len)
            )
            overdue = " ⚠" if item.is_overdue else ""
            lines.append(
                f"{item.name[:name_width]:<{name_width}} │ "
                f"{item.start_date:>10} {item.end_date:>10} │ "
                f"{bar}{overdue}"
            )

        if show_milestones:
            lines.append("─" * (name_width + 1) + "┼" + "─" * 23 + "┼" + "─" * bar_width)
            for ms in self.list_milestones():
                offset = (ms.date_obj - proj_start).days
                pos = int(offset / total_days * bar_width)
                marker = " " * pos + GANTT_MILESTONE_CHAR
                done_flag = " ✓" if ms.completed else (" ⚠" if ms.is_overdue else "")
                lines.append(
                    f"{ms.name[:name_width]:<{name_width}} │ "
                    f"{ms.target_date:>10} {'':>10} │ "
                    f"{marker}{done_flag}"
                )

        lines.append("```")
        return "\n".join(lines)

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": {iid: i.to_dict() for iid, i in self._items.items()},
            "milestones": {mid: m.to_dict() for mid, m in self._milestones.items()},
            "dependencies": {did: d.to_dict() for did, d in self._dependencies.items()},
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        self._items = {
            iid: TimelineItem.from_dict(idata)
            for iid, idata in data.get("items", {}).items()
        }
        self._milestones = {
            mid: Milestone.from_dict(mdata)
            for mid, mdata in data.get("milestones", {}).items()
        }
        self._dependencies = {
            did: Dependency.from_dict(ddata)
            for did, ddata in data.get("dependencies", {}).items()
        }

    # -- Private helpers ----------------------------------------------------

    def _would_create_cycle(self, from_id: str, to_id: str) -> bool:
        """Return *True* if adding from→to would create a dependency cycle."""
        if from_id == to_id:
            return True
        # DFS from to_id; if we reach from_id, there's a cycle
        visited: Set[str] = set()
        stack = [to_id]
        while stack:
            node = stack.pop()
            if node == from_id:
                return True
            if node in visited:
                continue
            visited.add(node)
            for dep in self._dependencies.values():
                if dep.from_id == node and dep.to_id not in visited:
                    stack.append(dep.to_id)
        return False
