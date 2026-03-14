"""
Board System – Board Manager
==============================

Central façade for board CRUD operations.  All mutations are recorded in
an in-memory activity log.

Provides:
- Board lifecycle (create / read / update / delete)
- Group management within boards
- Item management within groups
- Column management
- Cell value updates with type validation
- View management
- Activity log querying

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

from .column_types import validate_cell_value
from .models import (
    ActivityAction,
    ActivityLogEntry,
    Board,
    BoardKind,
    ColumnDefinition,
    ColumnType,
    Group,
    Item,
    Permission,
    ViewConfig,
    ViewType,
    _new_id,
    _now,
)
from .permissions import PermissionManager
from .views import render_view

logger = logging.getLogger(__name__)


class BoardManager:
    """In-memory board management engine.

    This class owns the complete lifecycle of boards and delegates to
    :class:`PermissionManager` and the view engine as needed.

    Storage is kept in memory (dict-based) to keep the module dependency-free.
    A persistence backend can be plugged in via ``set_storage``.
    """

    def __init__(self) -> None:
        self._boards: Dict[str, Board] = {}
        self._activity_log: List[ActivityLogEntry] = []

    # -- Internal helpers ---------------------------------------------------

    def _log(self, board_id: str, action: ActivityAction, entity_type: str,
             entity_id: str, user_id: str, changes: Optional[Dict[str, Any]] = None) -> None:
        entry = ActivityLogEntry(
            board_id=board_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            changes=changes or {},
        )
        capped_append(self._activity_log, entry)

    def _check_perm(self, board: Board, user_id: str, required: Permission,
                    user_teams: Optional[List[str]] = None) -> None:
        if not PermissionManager.has_permission(board, user_id, required, user_teams):
            raise PermissionError(
                f"User {user_id!r} lacks {required.value!r} on board {board.id!r}"
            )

    # ======================================================================
    # Board CRUD
    # ======================================================================

    def create_board(
        self,
        name: str,
        *,
        description: str = "",
        kind: BoardKind = BoardKind.PUBLIC,
        workspace_id: str = "",
        owner_id: str = "",
        columns: Optional[List[ColumnDefinition]] = None,
    ) -> Board:
        """Create a new board and return it."""
        board = Board(
            name=name,
            description=description,
            kind=kind,
            workspace_id=workspace_id,
            owner_id=owner_id,
        )
        if columns:
            for col in columns:
                board.add_column(col)

        # Every new board gets a default group and a default table view.
        default_group = Group(title="New Group", board_id=board.id)
        board.groups.append(default_group)
        board.views.append(ViewConfig(name="Main Table", view_type=ViewType.TABLE, board_id=board.id))

        self._boards[board.id] = board
        self._log(board.id, ActivityAction.BOARD_CREATED, "board", board.id, owner_id)
        logger.info("Board created: %s (%s)", board.name, board.id)
        return board

    def get_board(self, board_id: str) -> Optional[Board]:
        return self._boards.get(board_id)

    def list_boards(self, workspace_id: str = "") -> List[Board]:
        boards = list(self._boards.values())
        if workspace_id:
            boards = [b for b in boards if b.workspace_id == workspace_id]
        return boards

    def update_board(self, board_id: str, *, user_id: str = "",
                     name: Optional[str] = None, description: Optional[str] = None,
                     kind: Optional[BoardKind] = None) -> Board:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT_STRUCTURE)
        changes: Dict[str, Any] = {}
        if name is not None:
            changes["name"] = {"old": board.name, "new": name}
            board.name = name
        if description is not None:
            changes["description"] = {"old": board.description, "new": description}
            board.description = description
        if kind is not None:
            changes["kind"] = {"old": board.kind.value, "new": kind.value}
            board.kind = kind
        board.updated_at = _now()
        self._log(board_id, ActivityAction.BOARD_UPDATED, "board", board_id, user_id, changes)
        return board

    def delete_board(self, board_id: str, *, user_id: str = "") -> bool:
        board = self._boards.get(board_id)
        if board is None:
            return False
        self._check_perm(board, user_id, Permission.ADMIN)
        del self._boards[board_id]
        self._log(board_id, ActivityAction.BOARD_DELETED, "board", board_id, user_id)
        logger.info("Board deleted: %s", board_id)
        return True

    # ======================================================================
    # Group management
    # ======================================================================

    def create_group(self, board_id: str, title: str = "New Group", *,
                     user_id: str = "", color: str = "#579bfc") -> Group:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT_STRUCTURE)
        group = Group(title=title, color=color)
        board.add_group(group)
        self._log(board_id, ActivityAction.GROUP_CREATED, "group", group.id, user_id)
        return group

    def update_group(self, board_id: str, group_id: str, *, user_id: str = "",
                     title: Optional[str] = None, color: Optional[str] = None) -> Group:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT_STRUCTURE)
        group = board.get_group(group_id)
        if group is None:
            raise KeyError(f"Group not found: {group_id!r}")
        if title is not None:
            group.title = title
        if color is not None:
            group.color = color
        board.updated_at = _now()
        self._log(board_id, ActivityAction.GROUP_UPDATED, "group", group_id, user_id)
        return group

    def delete_group(self, board_id: str, group_id: str, *, user_id: str = "") -> bool:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT_STRUCTURE)
        removed = board.remove_group(group_id)
        if removed is None:
            return False
        self._log(board_id, ActivityAction.GROUP_DELETED, "group", group_id, user_id)
        return True

    # ======================================================================
    # Item management
    # ======================================================================

    def create_item(self, board_id: str, group_id: str, name: str, *,
                    user_id: str = "", cell_values: Optional[Dict[str, Any]] = None) -> Item:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT)
        group = board.get_group(group_id)
        if group is None:
            raise KeyError(f"Group not found: {group_id!r}")

        item = Item(name=name, creator_id=user_id)
        group.add_item(item)

        if cell_values:
            for col_id, raw_val in cell_values.items():
                col = board.get_column(col_id)
                if col is not None:
                    val, display = validate_cell_value(col.column_type, raw_val, col.settings)
                    item.set_cell(col_id, val, display)

        self._log(board_id, ActivityAction.ITEM_CREATED, "item", item.id, user_id)
        return item

    def update_item(self, board_id: str, item_id: str, *, user_id: str = "",
                    name: Optional[str] = None) -> Item:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT)

        for grp in board.groups:
            for it in grp.items:
                if it.id == item_id:
                    if name is not None:
                        it.name = name
                    it.updated_at = _now()
                    self._log(board_id, ActivityAction.ITEM_UPDATED, "item", item_id, user_id)
                    return it
        raise KeyError(f"Item not found: {item_id!r}")

    def delete_item(self, board_id: str, item_id: str, *, user_id: str = "") -> bool:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT)

        for grp in board.groups:
            removed = grp.remove_item(item_id)
            if removed is not None:
                board.updated_at = _now()
                self._log(board_id, ActivityAction.ITEM_DELETED, "item", item_id, user_id)
                return True
        return False

    def move_item(self, board_id: str, item_id: str, target_group_id: str,
                  *, user_id: str = "") -> Item:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT)

        # Remove from current group
        item: Optional[Item] = None
        for grp in board.groups:
            item = grp.remove_item(item_id)
            if item is not None:
                break
        if item is None:
            raise KeyError(f"Item not found: {item_id!r}")

        target = board.get_group(target_group_id)
        if target is None:
            raise KeyError(f"Target group not found: {target_group_id!r}")

        target.add_item(item)
        board.updated_at = _now()
        self._log(board_id, ActivityAction.ITEM_MOVED, "item", item_id, user_id,
                  {"target_group": target_group_id})
        return item

    # ======================================================================
    # Column management
    # ======================================================================

    def create_column(self, board_id: str, title: str, column_type: ColumnType = ColumnType.TEXT,
                      *, user_id: str = "", settings: Optional[Dict[str, Any]] = None,
                      description: str = "") -> ColumnDefinition:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT_STRUCTURE)

        col = ColumnDefinition(
            title=title,
            column_type=column_type,
            description=description,
            settings=settings or {},
        )
        board.add_column(col)
        self._log(board_id, ActivityAction.COLUMN_CREATED, "column", col.id, user_id)
        return col

    def update_column(self, board_id: str, column_id: str, *, user_id: str = "",
                      title: Optional[str] = None,
                      settings: Optional[Dict[str, Any]] = None) -> ColumnDefinition:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT_STRUCTURE)
        col = board.get_column(column_id)
        if col is None:
            raise KeyError(f"Column not found: {column_id!r}")
        if title is not None:
            col.title = title
        if settings is not None:
            col.settings.update(settings)
        board.updated_at = _now()
        self._log(board_id, ActivityAction.COLUMN_UPDATED, "column", column_id, user_id)
        return col

    def delete_column(self, board_id: str, column_id: str, *, user_id: str = "") -> bool:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT_STRUCTURE)
        removed = board.remove_column(column_id)
        if removed is None:
            return False
        self._log(board_id, ActivityAction.COLUMN_DELETED, "column", column_id, user_id)
        return True

    # ======================================================================
    # Cell value updates
    # ======================================================================

    def update_cell(self, board_id: str, item_id: str, column_id: str, value: Any,
                    *, user_id: str = "") -> Item:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT)

        col = board.get_column(column_id)
        if col is None:
            raise KeyError(f"Column not found: {column_id!r}")

        validated, display = validate_cell_value(col.column_type, value, col.settings)

        for grp in board.groups:
            for it in grp.items:
                if it.id == item_id:
                    it.set_cell(column_id, validated, display)
                    self._log(board_id, ActivityAction.CELL_UPDATED, "cell",
                              f"{item_id}:{column_id}", user_id,
                              {"value": validated})
                    return it
        raise KeyError(f"Item not found: {item_id!r}")

    # ======================================================================
    # View management
    # ======================================================================

    def create_view(self, board_id: str, name: str, view_type: ViewType = ViewType.TABLE,
                    *, user_id: str = "", settings: Optional[Dict[str, Any]] = None) -> ViewConfig:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        self._check_perm(board, user_id, Permission.EDIT)

        view = ViewConfig(
            name=name,
            view_type=view_type,
            settings=settings or {},
        )
        board.add_view(view)
        self._log(board_id, ActivityAction.VIEW_CREATED, "view", view.id, user_id)
        return view

    def render_board_view(self, board_id: str, view_id: str) -> Dict[str, Any]:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id!r}")
        view = board.get_view(view_id)
        if view is None:
            raise KeyError(f"View not found: {view_id!r}")
        return render_view(board, view)

    # ======================================================================
    # Activity log
    # ======================================================================

    def get_activity_log(self, board_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        entries = [e for e in self._activity_log if e.board_id == board_id]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return [e.to_dict() for e in entries[:limit]]
