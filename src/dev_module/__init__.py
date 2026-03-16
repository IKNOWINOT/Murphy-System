"""
Dev Module
============

Phase 9 of management systems feature parity for the Murphy System.

Provides developer-centric project management including:

- **Sprint boards** with velocity tracking and burndown
- **Bug tracker** with severity / priority presets
- **Release management** with checklists
- **Git activity feed** (read-only)
- **Product roadmap** timeline
- **REST API** at ``/api/dev``

Quick start::

    from dev_module import DevManager, BugSeverity

    mgr = DevManager()
    sprint = mgr.create_sprint("Sprint 1", "board1", start_date="2025-01-01")
    mgr.add_sprint_item(sprint.id, "item1", story_points=5)
    bug = mgr.create_bug("Login crash", board_id="board1", severity=BugSeverity.HIGH)

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "DevModule"

from .dev_manager import DevManager
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
)

try:
    from .api import create_dev_router
except Exception as exc:  # pragma: no cover
    create_dev_router = None  # type: ignore[assignment]

__all__ = [
    "Bug",
    "BugPriority",
    "BugSeverity",
    "BugStatus",
    "GitActivity",
    "Release",
    "ReleaseChecklist",
    "ReleaseStatus",
    "RoadmapItem",
    "RoadmapItemStatus",
    "Sprint",
    "SprintItem",
    "SprintStatus",
    "DevManager",
    "create_dev_router",
]
