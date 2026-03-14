"""
Dev Module – Dev Manager
==========================

Sprint management, bug tracking, release management, velocity tracking,
git activity feed, and product roadmap.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .models import (
    Bug,
    BugPriority,
    BugSeverity,
    BugStatus,
    GitActivity,
    Release,
    ReleaseChecklist,
    ReleaseStatus,
    RoadmapItem,
    RoadmapItemStatus,
    Sprint,
    SprintItem,
    SprintStatus,
    _now,
)

logger = logging.getLogger(__name__)


class DevManager:
    """In-memory dev module manager."""

    def __init__(self) -> None:
        self._sprints: Dict[str, Sprint] = {}
        self._bugs: Dict[str, Bug] = {}
        self._releases: Dict[str, Release] = {}
        self._git_activities: List[GitActivity] = []
        self._roadmap_items: Dict[str, RoadmapItem] = {}

    # -- Sprint CRUD --------------------------------------------------------

    def create_sprint(
        self,
        name: str,
        board_id: str,
        *,
        start_date: str = "",
        end_date: str = "",
        goal: str = "",
    ) -> Sprint:
        sprint = Sprint(
            name=name,
            board_id=board_id,
            start_date=start_date,
            end_date=end_date,
            goal=goal,
        )
        self._sprints[sprint.id] = sprint
        logger.info("Sprint created: %s (%s)", name, sprint.id)
        return sprint

    def get_sprint(self, sprint_id: str) -> Optional[Sprint]:
        return self._sprints.get(sprint_id)

    def list_sprints(self, board_id: str = "") -> List[Sprint]:
        sprints = list(self._sprints.values())
        if board_id:
            sprints = [s for s in sprints if s.board_id == board_id]
        return sprints

    def start_sprint(self, sprint_id: str) -> Sprint:
        sprint = self._sprints.get(sprint_id)
        if sprint is None:
            raise KeyError(f"Sprint not found: {sprint_id!r}")
        sprint.status = SprintStatus.ACTIVE
        return sprint

    def complete_sprint(self, sprint_id: str) -> Sprint:
        sprint = self._sprints.get(sprint_id)
        if sprint is None:
            raise KeyError(f"Sprint not found: {sprint_id!r}")
        sprint.status = SprintStatus.COMPLETED
        return sprint

    def add_sprint_item(
        self, sprint_id: str, item_id: str, story_points: int = 0,
    ) -> SprintItem:
        sprint = self._sprints.get(sprint_id)
        if sprint is None:
            raise KeyError(f"Sprint not found: {sprint_id!r}")
        si = SprintItem(item_id=item_id, story_points=story_points)
        sprint.items.append(si)
        return si

    def complete_sprint_item(self, sprint_id: str, item_id: str) -> bool:
        sprint = self._sprints.get(sprint_id)
        if sprint is None:
            raise KeyError(f"Sprint not found: {sprint_id!r}")
        for item in sprint.items:
            if item.item_id == item_id:
                item.completed = True
                return True
        return False

    # -- Velocity -----------------------------------------------------------

    def velocity_history(self, board_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        completed = [
            s for s in self._sprints.values()
            if s.board_id == board_id and s.status == SprintStatus.COMPLETED
        ]
        completed.sort(key=lambda s: s.created_at, reverse=True)
        return [
            {"sprint_id": s.id, "name": s.name, "velocity": s.velocity}
            for s in completed[:limit]
        ]

    def burndown(self, sprint_id: str) -> Dict[str, Any]:
        sprint = self._sprints.get(sprint_id)
        if sprint is None:
            raise KeyError(f"Sprint not found: {sprint_id!r}")
        return {
            "sprint_id": sprint.id,
            "total_points": sprint.total_points,
            "completed_points": sprint.completed_points,
            "remaining_points": sprint.total_points - sprint.completed_points,
        }

    # -- Bug tracking -------------------------------------------------------

    def create_bug(
        self,
        title: str,
        *,
        board_id: str = "",
        description: str = "",
        severity: BugSeverity = BugSeverity.MEDIUM,
        priority: BugPriority = BugPriority.P2,
        reporter_id: str = "",
        assignee_id: str = "",
    ) -> Bug:
        bug = Bug(
            title=title,
            board_id=board_id,
            description=description,
            severity=severity,
            priority=priority,
            reporter_id=reporter_id,
            assignee_id=assignee_id,
        )
        self._bugs[bug.id] = bug
        logger.info("Bug created: %s (%s)", title, bug.id)
        return bug

    def get_bug(self, bug_id: str) -> Optional[Bug]:
        return self._bugs.get(bug_id)

    def list_bugs(
        self,
        *,
        board_id: str = "",
        status: Optional[BugStatus] = None,
        severity: Optional[BugSeverity] = None,
    ) -> List[Bug]:
        bugs = list(self._bugs.values())
        if board_id:
            bugs = [b for b in bugs if b.board_id == board_id]
        if status is not None:
            bugs = [b for b in bugs if b.status == status]
        if severity is not None:
            bugs = [b for b in bugs if b.severity == severity]
        return bugs

    def resolve_bug(self, bug_id: str) -> Bug:
        bug = self._bugs.get(bug_id)
        if bug is None:
            raise KeyError(f"Bug not found: {bug_id!r}")
        bug.status = BugStatus.RESOLVED
        bug.resolved_at = _now()
        return bug

    def close_bug(self, bug_id: str) -> Bug:
        bug = self._bugs.get(bug_id)
        if bug is None:
            raise KeyError(f"Bug not found: {bug_id!r}")
        bug.status = BugStatus.CLOSED
        return bug

    # -- Release management -------------------------------------------------

    def create_release(
        self,
        version: str,
        name: str = "",
        *,
        sprint_ids: Optional[List[str]] = None,
        release_notes: str = "",
    ) -> Release:
        release = Release(
            version=version,
            name=name,
            sprint_ids=sprint_ids or [],
            release_notes=release_notes,
        )
        self._releases[release.id] = release
        return release

    def get_release(self, release_id: str) -> Optional[Release]:
        return self._releases.get(release_id)

    def list_releases(self) -> List[Release]:
        return list(self._releases.values())

    def add_checklist_item(self, release_id: str, label: str) -> ReleaseChecklist:
        release = self._releases.get(release_id)
        if release is None:
            raise KeyError(f"Release not found: {release_id!r}")
        item = ReleaseChecklist(label=label)
        release.checklist.append(item)
        return item

    def check_checklist_item(self, release_id: str, item_id: str) -> bool:
        release = self._releases.get(release_id)
        if release is None:
            raise KeyError(f"Release not found: {release_id!r}")
        for ci in release.checklist:
            if ci.id == item_id:
                ci.checked = True
                return True
        return False

    def publish_release(self, release_id: str) -> Release:
        release = self._releases.get(release_id)
        if release is None:
            raise KeyError(f"Release not found: {release_id!r}")
        release.status = ReleaseStatus.RELEASED
        release.released_at = _now()
        return release

    # -- Git activity feed --------------------------------------------------

    def log_git_activity(
        self,
        board_id: str,
        event_type: str,
        *,
        author: str = "",
        message: str = "",
        ref: str = "",
        url: str = "",
    ) -> GitActivity:
        activity = GitActivity(
            board_id=board_id,
            event_type=event_type,
            author=author,
            message=message,
            ref=ref,
            url=url,
        )
        capped_append(self._git_activities, activity)
        return activity

    def git_feed(self, board_id: str = "", limit: int = 50) -> List[GitActivity]:
        acts = self._git_activities
        if board_id:
            acts = [a for a in acts if a.board_id == board_id]
        return list(reversed(acts[-limit:]))

    # -- Product roadmap ----------------------------------------------------

    def create_roadmap_item(
        self,
        title: str,
        *,
        description: str = "",
        quarter: str = "",
        owner_id: str = "",
        tags: Optional[List[str]] = None,
    ) -> RoadmapItem:
        item = RoadmapItem(
            title=title,
            description=description,
            quarter=quarter,
            owner_id=owner_id,
            tags=tags or [],
        )
        self._roadmap_items[item.id] = item
        return item

    def get_roadmap_item(self, item_id: str) -> Optional[RoadmapItem]:
        return self._roadmap_items.get(item_id)

    def list_roadmap(self, quarter: str = "") -> List[RoadmapItem]:
        items = list(self._roadmap_items.values())
        if quarter:
            items = [i for i in items if i.quarter == quarter]
        return items

    def update_roadmap_item(
        self,
        item_id: str,
        *,
        status: Optional[RoadmapItemStatus] = None,
        quarter: Optional[str] = None,
    ) -> RoadmapItem:
        item = self._roadmap_items.get(item_id)
        if item is None:
            raise KeyError(f"Roadmap item not found: {item_id!r}")
        if status is not None:
            item.status = status
        if quarter is not None:
            item.quarter = quarter
        return item
