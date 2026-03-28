# `src/management_systems` — Management Systems

Full project management and workflow automation layer delivered through Matrix chat commands and boards.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The management systems package maps Murphy's entire subsystem portfolio onto a Monday.com-style project management surface accessible directly from Matrix chat rooms. Board-based task tracking, workflow automation recipes, Gantt timelines, and rich dashboards are all exposed via `!murphy` commands. Workspaces are domain-scoped to Murphy's internal modules so every subsystem has a dedicated board. A bidirectional `IntegrationBridge` keeps board state in sync with live Murphy subsystem events.

## Key Components

| Module | Purpose |
|--------|---------|
| `board_engine.py` | Core board/group/item management with column types |
| `status_engine.py` | Status label definitions and workflow state machine |
| `timeline_engine.py` | Gantt timelines, critical path calculation, milestones |
| `automation_recipes.py` | "When X, do Y" recipe automation engine |
| `workspace_manager.py` | Workspaces mapped to Murphy subsystem domains |
| `dashboard_generator.py` | ASCII/Markdown dashboard reports for Matrix |
| `integration_bridge.py` | Bidirectional Murphy module ↔ board synchronisation |
| `form_builder.py` | Intake forms that auto-create board items |
| `doc_manager.py` | Workdoc management linked to boards and items |
| `management_commands.py` | `!murphy` command definitions for all management features |

## Usage

```python
from management_systems import BoardEngine, WorkspaceManager, DashboardGenerator

ws_mgr = WorkspaceManager()
ws_mgr.bootstrap_murphy_workspaces()

board_engine = BoardEngine()
board = board_engine.create_board("AI Sprint 1", workspace_id=ws_mgr.get("ai_ml_pipeline").id,
                                  owner_id="@alice:example.com")

dashboard = DashboardGenerator()
print(dashboard.render_board_summary(board.id))
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
