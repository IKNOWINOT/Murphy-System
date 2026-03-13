"""
Board System – Visual Board Management
========================================

Phase 1 of Monday.com feature parity for the Murphy System.

Provides a complete visual board management system including:

- **Board CRUD** – create, read, update, delete boards
- **Groups** – logical item groupings within boards
- **Items** – row-level data with typed cell values
- **Columns** – 20 column types with validation (status, text, number, date, …)
- **Views** – Table, Kanban, Calendar, Timeline, and Chart renderers
- **Permissions** – role-based access control (view / edit / edit_structure / admin)
- **Activity Log** – immutable audit trail of all mutations

Quick start::

    from board_system import BoardManager, ColumnType, ViewType

    mgr = BoardManager()
    board = mgr.create_board("Sprint Board", owner_id="u1")

    col = mgr.create_column(board.id, "Status", ColumnType.STATUS,
                            user_id="u1",
                            settings={"labels": {"0": "To Do", "1": "In Progress", "2": "Done"}})

    group = board.groups[0]
    item = mgr.create_item(board.id, group.id, "Task A", user_id="u1",
                           cell_values={col.id: "To Do"})

    view_data = mgr.render_board_view(board.id, board.views[0].id)

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "Boards"

# -- Models -----------------------------------------------------------------
# -- Board manager ----------------------------------------------------------
from .board_manager import BoardManager

# -- Column types -----------------------------------------------------------
from .column_types import (
    COLUMN_VALIDATORS,
    default_value,
    validate_cell_value,
)
from .models import (
    ActivityAction,
    ActivityLogEntry,
    Board,
    BoardKind,
    BoardPermission,
    CellValue,
    ColumnDefinition,
    ColumnType,
    Group,
    Item,
    Permission,
    ViewConfig,
    ViewType,
)

# -- Permissions ------------------------------------------------------------
from .permissions import PermissionManager

# -- Views ------------------------------------------------------------------
from .views import (
    apply_filters,
    apply_sort,
    render_calendar_view,
    render_chart_view,
    render_kanban_view,
    render_table_view,
    render_timeline_view,
    render_view,
)

# -- API (optional – requires fastapi) -------------------------------------
try:
    from .api import create_board_router
except Exception:  # pragma: no cover
    create_board_router = None  # type: ignore[assignment]

__all__ = [
    # Models
    "ActivityAction",
    "ActivityLogEntry",
    "Board",
    "BoardKind",
    "BoardPermission",
    "CellValue",
    "ColumnDefinition",
    "ColumnType",
    "Group",
    "Item",
    "Permission",
    "ViewConfig",
    "ViewType",
    # Column types
    "COLUMN_VALIDATORS",
    "default_value",
    "validate_cell_value",
    # Permissions
    "PermissionManager",
    # Views
    "apply_filters",
    "apply_sort",
    "render_chart_view",
    "render_calendar_view",
    "render_kanban_view",
    "render_table_view",
    "render_timeline_view",
    "render_view",
    # Manager
    "BoardManager",
    # API
    "create_board_router",
]
