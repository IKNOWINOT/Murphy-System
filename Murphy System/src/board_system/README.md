# `src/board_system` — Visual Board Management

Full-featured visual board system with typed columns, multiple view renderers, and role-based access control.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The board system is the primary workspace abstraction in Murphy, providing Monday.com-style project boards with rich data types. Boards contain groups of items; each item has typed cell values validated against column schemas that support 20 column types including status, text, number, date, people, and formula. Five view renderers — Table, Kanban, Calendar, Timeline, and Chart — transform the same underlying data into different visual layouts. Every mutation is appended to an immutable activity log, and a permissions layer enforces view / edit / admin roles per board.

## Key Components

| Module | Purpose |
|--------|---------|
| `board_manager.py` | `BoardManager` — CRUD for boards, groups, items, and columns |
| `column_types.py` | Definitions and validators for all 20 supported column types |
| `models.py` | `Board`, `Group`, `Item`, `Column`, `Activity` Pydantic models |
| `views.py` | Table, Kanban, Calendar, Timeline, and Chart view renderers |
| `permissions.py` | Role-based access control (view / edit / edit_structure / admin) |
| `api.py` | FastAPI router for all board operations |

## Usage

```python
from board_system import BoardManager, ColumnType, ViewType

mgr = BoardManager()
board = mgr.create_board("Sprint Board", owner_id="u1")
col = mgr.create_column(board.id, "Status", ColumnType.STATUS, user_id="u1")
item = mgr.create_item(board.id, board.groups[0].id, "Task A", user_id="u1")
view = mgr.render_board_view(board.id, board.views[0].id)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
