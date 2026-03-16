"""
Board System – Data Models
===========================

Core data structures for the Visual Board System (Phase 1 of Monday.com parity).

Provides dataclass-based models for:
- Boards, Groups, Items, Sub-items
- Column definitions and cell values
- Views (Table, Kanban, Calendar, Timeline, Chart)
- Activity log entries

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ColumnType(Enum):
    """Supported column types mirroring Monday.com column types."""

    STATUS = "status"
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    PERSON = "person"
    TIMELINE = "timeline"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    LINK = "link"
    LONG_TEXT = "long_text"
    EMAIL = "email"
    PHONE = "phone"
    RATING = "rating"
    COLOR = "color"
    TAG = "tag"
    FILE = "file"
    FORMULA = "formula"
    MIRROR = "mirror"
    DEPENDENCY = "dependency"
    AUTO_NUMBER = "auto_number"


class ViewType(Enum):
    """Available board view types."""

    TABLE = "table"
    KANBAN = "kanban"
    CALENDAR = "calendar"
    TIMELINE = "timeline"
    CHART = "chart"
    MAP = "map"
    FORM = "form"
    WORKLOAD = "workload"


class BoardKind(Enum):
    """Board visibility/sharing classification."""

    PUBLIC = "public"
    PRIVATE = "private"
    SHAREABLE = "shareable"


class Permission(Enum):
    """Granular board permissions."""

    VIEW = "view"
    EDIT = "edit"
    EDIT_STRUCTURE = "edit_structure"
    ADMIN = "admin"


class ActivityAction(Enum):
    """Types of recorded activity events."""

    BOARD_CREATED = "board_created"
    BOARD_UPDATED = "board_updated"
    BOARD_DELETED = "board_deleted"
    GROUP_CREATED = "group_created"
    GROUP_UPDATED = "group_updated"
    GROUP_DELETED = "group_deleted"
    ITEM_CREATED = "item_created"
    ITEM_UPDATED = "item_updated"
    ITEM_DELETED = "item_deleted"
    ITEM_MOVED = "item_moved"
    COLUMN_CREATED = "column_created"
    COLUMN_UPDATED = "column_updated"
    COLUMN_DELETED = "column_deleted"
    CELL_UPDATED = "cell_updated"
    VIEW_CREATED = "view_created"
    PERMISSION_CHANGED = "permission_changed"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


@dataclass
class ColumnDefinition:
    """Schema definition for a single board column."""

    id: str = field(default_factory=_new_id)
    title: str = ""
    column_type: ColumnType = ColumnType.TEXT
    description: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    width: int = 150
    position: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "column_type": self.column_type.value,
            "description": self.description,
            "settings": self.settings,
            "width": self.width,
            "position": self.position,
        }


@dataclass
class CellValue:
    """A single cell value within an item row."""

    column_id: str = ""
    value: Any = None
    display_value: str = ""
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_id": self.column_id,
            "value": self.value,
            "display_value": self.display_value,
            "updated_at": self.updated_at,
        }


@dataclass
class Item:
    """A single row/item in a board group."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    group_id: str = ""
    board_id: str = ""
    cells: Dict[str, CellValue] = field(default_factory=dict)
    subitems: List["Item"] = field(default_factory=list)
    creator_id: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    position: int = 0

    def set_cell(self, column_id: str, value: Any, display_value: str = "") -> None:
        self.cells[column_id] = CellValue(
            column_id=column_id,
            value=value,
            display_value=display_value or str(value),
        )
        self.updated_at = _now()

    def get_cell(self, column_id: str) -> Optional[CellValue]:
        return self.cells.get(column_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "group_id": self.group_id,
            "board_id": self.board_id,
            "cells": {k: v.to_dict() for k, v in self.cells.items()},
            "subitems": [s.to_dict() for s in self.subitems],
            "creator_id": self.creator_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "position": self.position,
        }


@dataclass
class Group:
    """A logical grouping of items within a board."""

    id: str = field(default_factory=_new_id)
    title: str = "New Group"
    color: str = "#579bfc"
    board_id: str = ""
    items: List[Item] = field(default_factory=list)
    position: int = 0
    collapsed: bool = False

    def add_item(self, item: Item) -> Item:
        item.group_id = self.id
        item.board_id = self.board_id
        item.position = len(self.items)
        self.items.append(item)
        return item

    def remove_item(self, item_id: str) -> Optional[Item]:
        for i, item in enumerate(self.items):
            if item.id == item_id:
                return self.items.pop(i)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "color": self.color,
            "board_id": self.board_id,
            "items": [it.to_dict() for it in self.items],
            "position": self.position,
            "collapsed": self.collapsed,
        }


@dataclass
class ViewConfig:
    """Configuration for a board view."""

    id: str = field(default_factory=_new_id)
    name: str = "Main Table"
    view_type: ViewType = ViewType.TABLE
    board_id: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    filters: List[Dict[str, Any]] = field(default_factory=list)
    sort_by: List[Dict[str, str]] = field(default_factory=list)
    hidden_columns: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "view_type": self.view_type.value,
            "board_id": self.board_id,
            "settings": self.settings,
            "filters": self.filters,
            "sort_by": self.sort_by,
            "hidden_columns": self.hidden_columns,
            "created_at": self.created_at,
        }


@dataclass
class BoardPermission:
    """Maps a user or team to a permission level on a board."""

    user_id: str = ""
    team_id: str = ""
    permission: Permission = Permission.VIEW
    granted_at: str = field(default_factory=_now)
    granted_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "team_id": self.team_id,
            "permission": self.permission.value,
            "granted_at": self.granted_at,
            "granted_by": self.granted_by,
        }


@dataclass
class Board:
    """Top-level board entity — the primary organisational unit."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    kind: BoardKind = BoardKind.PUBLIC
    workspace_id: str = ""
    owner_id: str = ""
    columns: List[ColumnDefinition] = field(default_factory=list)
    groups: List[Group] = field(default_factory=list)
    views: List[ViewConfig] = field(default_factory=list)
    permissions: List[BoardPermission] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    # Convenience helpers ------------------------------------------------

    def add_column(self, col: ColumnDefinition) -> ColumnDefinition:
        col.position = len(self.columns)
        self.columns.append(col)
        self.updated_at = _now()
        return col

    def get_column(self, column_id: str) -> Optional[ColumnDefinition]:
        for c in self.columns:
            if c.id == column_id:
                return c
        return None

    def remove_column(self, column_id: str) -> Optional[ColumnDefinition]:
        for i, c in enumerate(self.columns):
            if c.id == column_id:
                self.updated_at = _now()
                return self.columns.pop(i)
        return None

    def add_group(self, group: Group) -> Group:
        group.board_id = self.id
        group.position = len(self.groups)
        self.groups.append(group)
        self.updated_at = _now()
        return group

    def get_group(self, group_id: str) -> Optional[Group]:
        for g in self.groups:
            if g.id == group_id:
                return g
        return None

    def remove_group(self, group_id: str) -> Optional[Group]:
        for i, g in enumerate(self.groups):
            if g.id == group_id:
                self.updated_at = _now()
                return self.groups.pop(i)
        return None

    def add_view(self, view: ViewConfig) -> ViewConfig:
        view.board_id = self.id
        self.views.append(view)
        self.updated_at = _now()
        return view

    def get_view(self, view_id: str) -> Optional[ViewConfig]:
        for v in self.views:
            if v.id == view_id:
                return v
        return None

    def all_items(self) -> List[Item]:
        """Return all items across all groups."""
        items: List[Item] = []
        for g in self.groups:
            items.extend(g.items)
        return items

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind.value,
            "workspace_id": self.workspace_id,
            "owner_id": self.owner_id,
            "columns": [c.to_dict() for c in self.columns],
            "groups": [g.to_dict() for g in self.groups],
            "views": [v.to_dict() for v in self.views],
            "permissions": [p.to_dict() for p in self.permissions],
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ActivityLogEntry:
    """Immutable record of an action performed on a board entity."""

    id: str = field(default_factory=_new_id)
    board_id: str = ""
    action: ActivityAction = ActivityAction.BOARD_CREATED
    entity_type: str = ""
    entity_id: str = ""
    user_id: str = ""
    timestamp: str = field(default_factory=_now)
    changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "board_id": self.board_id,
            "action": self.action.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "changes": self.changes,
        }
