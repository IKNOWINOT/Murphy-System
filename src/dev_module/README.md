# `src/dev_module` — Developer Module

Sprint boards, bug tracking, release management, and Git activity feeds for developer-centric project management.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The dev module provides a complete developer workflow layer built on Murphy's board primitives, targeting engineering-team feature parity with tools like Jira. Sprint boards track velocity and burndown; the bug tracker captures issues with severity and priority presets; release checklists enforce readiness gates before deployment. A read-only Git activity feed streams commit and PR events into boards for contextual awareness. All features are accessible via the `DevManager` class and a FastAPI router at `/api/dev`.

## Key Components

| Module | Purpose |
|--------|---------|
| `dev_manager.py` | `DevManager` — sprint, bug, release, roadmap, and Git feed management |
| `models.py` | `Bug`, `BugSeverity`, `BugPriority`, `BugStatus`, `Release`, `ReleaseChecklist`, `GitActivity` |
| `api.py` | FastAPI router (`create_dev_router`) for all developer endpoints |

## Usage

```python
from dev_module import DevManager, BugSeverity

mgr = DevManager()
sprint = mgr.create_sprint("Sprint 1", board_id="board-1", start_date="2025-01-01")
mgr.add_sprint_item(sprint.id, item_id="item-42", story_points=5)
bug = mgr.create_bug("Login crash on Safari", board_id="board-1", severity=BugSeverity.HIGH)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
