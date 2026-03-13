"""Management Systems – Board Engine.

Core board/project management for the Management Systems package.
Columns, items, groups, views, templates, sub-items, and permissions.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# Constants
MAX_COLUMNS: int = 50
MAX_ITEMS_PER_GROUP: int = 10_000
DEFAULT_GROUP_NAME: str = "Main Group"
BOARD_TABLE_MAX_COL_WIDTH: int = 20

# Enumerations
class ColumnType(Enum):
    """Supported column types."""

    STATUS = "status"
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    PERSON = "person"
    TIMELINE = "timeline"
    DROPDOWN = "dropdown"
    TAGS = "tags"
    CHECKBOX = "checkbox"
    LINK = "link"
    LONG_TEXT = "long_text"
    EMAIL = "email"
    PHONE = "phone"
    RATING = "rating"
    FILE = "file"
    FORMULA = "formula"
    MIRROR = "mirror"
    DEPENDENCY = "dependency"
    AUTO_NUMBER = "auto_number"
    PRIORITY = "priority"

class ViewType(Enum):
    """Available board view types."""

    MAIN_TABLE = "main_table"
    KANBAN = "kanban"
    CALENDAR = "calendar"
    CHART = "chart"
    TIMELINE = "timeline"
    FILES_GALLERY = "files_gallery"

class BoardPermissionLevel(Enum):
    """Board permission levels."""

    OWNER = "owner"
    SUBSCRIBER = "subscriber"
    VIEWER = "viewer"

class TemplateType(Enum):
    """Pre-defined board templates."""

    SPRINT_BOARD = "sprint_board"
    BUG_TRACKER = "bug_tracker"
    CONTENT_CALENDAR = "content_calendar"
    CLIENT_ONBOARDING = "client_onboarding"
    PROJECT_ROADMAP = "project_roadmap"
    EMPLOYEE_ONBOARDING = "employee_onboarding"
    MARKETING_CAMPAIGN = "marketing_campaign"
    SALES_CRM = "sales_crm"
    IT_REQUESTS = "it_requests"
    RELEASE_PLAN = "release_plan"

# Helper
def _uid() -> str:
    return uuid.uuid4().hex[:12]

def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()

# Data classes

@dataclass
class BoardColumn:
    """Represents a single typed column in a board.

    Args:
        title: Human-readable column title.
        col_type: Data type for this column.
        settings: Type-specific configuration (e.g. label map for status).
        width: Display width hint for ASCII rendering.
    """

    title: str
    col_type: ColumnType = ColumnType.TEXT
    settings: Dict[str, Any] = field(default_factory=dict)
    width: int = 15
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "col_type": self.col_type.value,
            "settings": self.settings,
            "width": self.width,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoardColumn":
        obj = cls(
            title=data["title"],
            col_type=ColumnType(data.get("col_type", "text")),
            settings=data.get("settings", {}),
            width=data.get("width", 15),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        return obj

@dataclass
class BoardItem:
    """A single row/item in a board group.

    Args:
        name: Display name of the item.
        group_id: Parent group identifier.
        cell_values: Mapping of column_id → cell value.
        subitems: Child items for task decomposition.
        created_by: User ID of creator.
    """

    name: str
    group_id: str
    cell_values: Dict[str, Any] = field(default_factory=dict)
    subitems: List["BoardItem"] = field(default_factory=list)
    created_by: str = ""
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "group_id": self.group_id,
            "cell_values": self.cell_values,
            "subitems": [s.to_dict() for s in self.subitems],
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoardItem":
        obj = cls(
            name=data["name"],
            group_id=data.get("group_id", ""),
            cell_values=data.get("cell_values", {}),
            created_by=data.get("created_by", ""),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.updated_at = data.get("updated_at", obj.updated_at)
        obj.subitems = [BoardItem.from_dict(s) for s in data.get("subitems", [])]
        return obj

@dataclass
class BoardGroup:
    """A section within a board that organises items.

    Args:
        title: Display name for this group.
        color: Optional colour for visual differentiation.
    """

    title: str
    color: str = "#579BFC"
    items: List[BoardItem] = field(default_factory=list)
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "color": self.color,
            "items": [i.to_dict() for i in self.items],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoardGroup":
        obj = cls(
            title=data["title"],
            color=data.get("color", "#579BFC"),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.items = [BoardItem.from_dict(i) for i in data.get("items", [])]
        return obj

@dataclass
class BoardView:
    """A saved view configuration for a board.

    Args:
        name: Human-readable view name.
        view_type: The rendering type for this view.
        config: View-specific configuration options.
    """

    name: str
    view_type: ViewType = ViewType.MAIN_TABLE
    config: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "view_type": self.view_type.value,
            "config": self.config,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoardView":
        obj = cls(
            name=data["name"],
            view_type=ViewType(data.get("view_type", "main_table")),
            config=data.get("config", {}),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        return obj

@dataclass
class BoardPermission:
    """A user's permission on a specific board.

    Args:
        user_id: Identifier of the user.
        level: Permission level granted to the user.
    """

    user_id: str
    level: BoardPermissionLevel = BoardPermissionLevel.VIEWER
    granted_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "level": self.level.value,
            "granted_at": self.granted_at,
        }

@dataclass
class Board:
    """A project board containing columns, groups, items and views.

    Args:
        name: Display name of the board.
        description: Optional description.
        workspace_id: Parent workspace identifier.
        owner_id: User ID of the board owner.
    """

    name: str
    description: str = ""
    workspace_id: str = ""
    owner_id: str = ""
    columns: List[BoardColumn] = field(default_factory=list)
    groups: List[BoardGroup] = field(default_factory=list)
    views: List[BoardView] = field(default_factory=list)
    permissions: List[BoardPermission] = field(default_factory=list)
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace_id": self.workspace_id,
            "owner_id": self.owner_id,
            "columns": [c.to_dict() for c in self.columns],
            "groups": [g.to_dict() for g in self.groups],
            "views": [v.to_dict() for v in self.views],
            "permissions": [p.to_dict() for p in self.permissions],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Board":
        obj = cls(
            name=data["name"],
            description=data.get("description", ""),
            workspace_id=data.get("workspace_id", ""),
            owner_id=data.get("owner_id", ""),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.updated_at = data.get("updated_at", obj.updated_at)
        obj.columns = [BoardColumn.from_dict(c) for c in data.get("columns", [])]
        obj.groups = [BoardGroup.from_dict(g) for g in data.get("groups", [])]
        obj.views = [BoardView.from_dict(v) for v in data.get("views", [])]
        obj.permissions = [
            BoardPermission(
                user_id=p["user_id"],
                level=BoardPermissionLevel(p.get("level", "viewer")),
                granted_at=p.get("granted_at", _now()),
            )
            for p in data.get("permissions", [])
        ]
        return obj

@dataclass
class BoardTemplate:
    """A pre-configured board template.

    Args:
        name: Display name for the template.
        template_type: Enum identifying the template.
        description: Brief description of use case.
        default_columns: Pre-defined column configurations.
        default_groups: Pre-defined group names.
    """

    name: str
    template_type: TemplateType
    description: str = ""
    default_columns: List[Dict[str, Any]] = field(default_factory=list)
    default_groups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "template_type": self.template_type.value,
            "description": self.description,
            "default_columns": self.default_columns,
            "default_groups": self.default_groups,
        }

# Built-in templates

_TEMPLATES: Dict[TemplateType, BoardTemplate] = {
    TemplateType.SPRINT_BOARD: BoardTemplate(
        name="Sprint Board",
        template_type=TemplateType.SPRINT_BOARD,
        description="Agile sprint tracking with story points and status.",
        default_columns=[
            {"title": "Status", "col_type": "status", "settings": {
                "labels": {"0": "To Do", "1": "In Progress", "2": "Done", "3": "Blocked"},
            }},
            {"title": "Assignee", "col_type": "person"},
            {"title": "Story Points", "col_type": "number"},
            {"title": "Due Date", "col_type": "date"},
            {"title": "Priority", "col_type": "priority"},
        ],
        default_groups=["Backlog", "Sprint 1", "Sprint 2", "Done"],
    ),
    TemplateType.BUG_TRACKER: BoardTemplate(
        name="Bug Tracker",
        template_type=TemplateType.BUG_TRACKER,
        description="Track, triage, and resolve bugs.",
        default_columns=[
            {"title": "Status", "col_type": "status", "settings": {
                "labels": {"0": "New", "1": "In Progress", "2": "Resolved", "3": "Closed"},
            }},
            {"title": "Severity", "col_type": "priority"},
            {"title": "Reporter", "col_type": "person"},
            {"title": "Assignee", "col_type": "person"},
            {"title": "Module", "col_type": "dropdown"},
            {"title": "Found Date", "col_type": "date"},
        ],
        default_groups=["Critical", "High", "Medium", "Low"],
    ),
    TemplateType.CONTENT_CALENDAR: BoardTemplate(
        name="Content Calendar",
        template_type=TemplateType.CONTENT_CALENDAR,
        description="Plan and track content publication schedule.",
        default_columns=[
            {"title": "Status", "col_type": "status", "settings": {
                "labels": {"0": "Idea", "1": "Draft", "2": "Review", "3": "Published"},
            }},
            {"title": "Publish Date", "col_type": "date"},
            {"title": "Channel", "col_type": "dropdown"},
            {"title": "Author", "col_type": "person"},
            {"title": "Tags", "col_type": "tags"},
        ],
        default_groups=["Blog", "Social Media", "Email", "Video"],
    ),
    TemplateType.CLIENT_ONBOARDING: BoardTemplate(
        name="Client Onboarding",
        template_type=TemplateType.CLIENT_ONBOARDING,
        description="Structured onboarding workflow for new clients.",
        default_columns=[
            {"title": "Status", "col_type": "status", "settings": {
                "labels": {"0": "Not Started", "1": "In Progress", "2": "Complete", "3": "Blocked"},
            }},
            {"title": "Owner", "col_type": "person"},
            {"title": "Due Date", "col_type": "date"},
            {"title": "Notes", "col_type": "long_text"},
        ],
        default_groups=["Pre-Sales", "Kickoff", "Setup", "Training", "Go Live"],
    ),
    TemplateType.PROJECT_ROADMAP: BoardTemplate(
        name="Project Roadmap",
        template_type=TemplateType.PROJECT_ROADMAP,
        description="High-level strategic project roadmap.",
        default_columns=[
            {"title": "Status", "col_type": "status", "settings": {
                "labels": {"0": "Planned", "1": "In Progress", "2": "Complete", "3": "At Risk"},
            }},
            {"title": "Timeline", "col_type": "timeline"},
            {"title": "Owner", "col_type": "person"},
            {"title": "Priority", "col_type": "priority"},
            {"title": "Dependencies", "col_type": "dependency"},
        ],
        default_groups=["Q1", "Q2", "Q3", "Q4"],
    ),
    TemplateType.IT_REQUESTS: BoardTemplate(
        name="IT Requests",
        template_type=TemplateType.IT_REQUESTS,
        description="Track IT service requests and incidents.",
        default_columns=[
            {"title": "Status", "col_type": "status", "settings": {
                "labels": {"0": "Open", "1": "In Progress", "2": "Resolved", "3": "Closed"},
            }},
            {"title": "Type", "col_type": "dropdown"},
            {"title": "Priority", "col_type": "priority"},
            {"title": "Requester", "col_type": "person"},
            {"title": "Assignee", "col_type": "person"},
            {"title": "Due Date", "col_type": "date"},
        ],
        default_groups=["New Requests", "In Progress", "Resolved"],
    ),
}

# Board Engine

class BoardEngine:
    """Central engine for board/project management.

    Manages the full lifecycle of boards, columns, groups, items,
    sub-items, views, and permissions.  All state is stored in-memory
    and serialisable to plain dicts for JSON persistence.

    Example::

        engine = BoardEngine()
        board = engine.create_board("Sprint 1", owner_id="@alice:example.com")
        col = engine.add_column(board.id, "Status", ColumnType.STATUS)
        group = engine.add_group(board.id, "Backlog")
        item = engine.add_item(board.id, group.id, "Fix login bug")
        engine.set_cell(board.id, item.id, col.id, "In Progress")
        print(engine.render_table(board.id))
    """

    def __init__(self) -> None:
        self._boards: Dict[str, Board] = {}

    # -- Board CRUD ---------------------------------------------------------

    def create_board(
        self,
        name: str,
        *,
        description: str = "",
        workspace_id: str = "",
        owner_id: str = "",
        template: Optional[TemplateType] = None,
    ) -> Board:
        """Create a new board, optionally pre-populated from a template.

        Args:
            name: Display name for the board.
            description: Optional human-readable description.
            workspace_id: Parent workspace ID.
            owner_id: Matrix user ID of the creator.
            template: Pre-built template to apply.

        Returns:
            The newly created :class:`Board`.
        """
        board = Board(
            name=name,
            description=description,
            workspace_id=workspace_id,
            owner_id=owner_id,
        )
        # Default table view
        board.views.append(BoardView(name="Main Table", view_type=ViewType.MAIN_TABLE))

        if owner_id:
            board.permissions.append(
                BoardPermission(user_id=owner_id, level=BoardPermissionLevel.OWNER)
            )

        if template is not None:
            self._apply_template(board, template)
        else:
            # Default columns
            board.columns.append(BoardColumn(title="Name", col_type=ColumnType.TEXT))
            board.columns.append(BoardColumn(title="Status", col_type=ColumnType.STATUS))
            board.groups.append(BoardGroup(title=DEFAULT_GROUP_NAME))

        self._boards[board.id] = board
        logger.info("Board created: %s (%s)", name, board.id)
        return board

    def get_board(self, board_id: str) -> Optional[Board]:
        """Return a board by ID or *None* if not found."""
        return self._boards.get(board_id)

    def list_boards(self, *, workspace_id: str = "") -> List[Board]:
        """List boards, optionally filtered by workspace.

        Args:
            workspace_id: If non-empty, only boards in this workspace.

        Returns:
            Sorted list of matching boards.
        """
        boards = list(self._boards.values())
        if workspace_id:
            boards = [b for b in boards if b.workspace_id == workspace_id]
        return sorted(boards, key=lambda b: b.created_at)

    def delete_board(self, board_id: str) -> bool:
        """Delete a board by ID.

        Returns:
            *True* if the board was found and removed, *False* otherwise.
        """
        if board_id in self._boards:
            del self._boards[board_id]
            logger.info("Board deleted: %s", board_id)
            return True
        return False

    # -- Column management --------------------------------------------------

    def add_column(
        self,
        board_id: str,
        title: str,
        col_type: ColumnType = ColumnType.TEXT,
        *,
        settings: Optional[Dict[str, Any]] = None,
        width: int = 15,
    ) -> BoardColumn:
        """Add a column to an existing board.

        Args:
            board_id: Target board.
            title: Column title.
            col_type: Column data type.
            settings: Type-specific configuration.
            width: Display width for ASCII rendering.

        Returns:
            The new :class:`BoardColumn`.

        Raises:
            KeyError: If *board_id* is not found.
            ValueError: If the board already has ``MAX_COLUMNS`` columns.
        """
        board = self._get_board_or_raise(board_id)
        if len(board.columns) >= MAX_COLUMNS:
            raise ValueError(f"Board {board_id} has reached maximum column limit ({MAX_COLUMNS})")
        col = BoardColumn(title=title, col_type=col_type, settings=settings or {}, width=width)
        board.columns.append(col)
        board.updated_at = _now()
        logger.debug("Column '%s' added to board %s", title, board_id)
        return col

    def remove_column(self, board_id: str, column_id: str) -> bool:
        """Remove a column from a board.

        Returns:
            *True* if removed, *False* if not found.
        """
        board = self._get_board_or_raise(board_id)
        original = len(board.columns)
        board.columns = [c for c in board.columns if c.id != column_id]
        board.updated_at = _now()
        return len(board.columns) < original

    # -- Group management ---------------------------------------------------

    def add_group(
        self,
        board_id: str,
        title: str,
        *,
        color: str = "#579BFC",
    ) -> BoardGroup:
        """Add a group to a board.

        Args:
            board_id: Target board.
            title: Group display name.
            color: Hex colour for the group header.

        Returns:
            The new :class:`BoardGroup`.
        """
        board = self._get_board_or_raise(board_id)
        group = BoardGroup(title=title, color=color)
        board.groups.append(group)
        board.updated_at = _now()
        logger.debug("Group '%s' added to board %s", title, board_id)
        return group

    def remove_group(self, board_id: str, group_id: str) -> bool:
        """Remove a group and all its items from a board."""
        board = self._get_board_or_raise(board_id)
        original = len(board.groups)
        board.groups = [g for g in board.groups if g.id != group_id]
        board.updated_at = _now()
        return len(board.groups) < original

    # -- Item management ----------------------------------------------------

    def add_item(
        self,
        board_id: str,
        group_id: str,
        name: str,
        *,
        cell_values: Optional[Dict[str, Any]] = None,
        created_by: str = "",
    ) -> BoardItem:
        """Create a new item in a group.

        Args:
            board_id: Target board.
            group_id: Target group within the board.
            name: Display name for the item.
            cell_values: Initial column values.
            created_by: Matrix user ID of creator.

        Returns:
            The new :class:`BoardItem`.

        Raises:
            KeyError: If *board_id* or *group_id* is not found.
        """
        group = self._get_group_or_raise(board_id, group_id)
        if len(group.items) >= MAX_ITEMS_PER_GROUP:
            raise ValueError(f"Group {group_id} has reached maximum item limit")
        item = BoardItem(
            name=name,
            group_id=group_id,
            cell_values=cell_values or {},
            created_by=created_by,
        )
        group.items.append(item)
        self._boards[board_id].updated_at = _now()
        logger.debug("Item '%s' added to group %s", name, group_id)
        return item

    def get_item(self, board_id: str, item_id: str) -> Optional[BoardItem]:
        """Find an item across all groups in a board."""
        board = self._boards.get(board_id)
        if board is None:
            return None
        for group in board.groups:
            for item in group.items:
                if item.id == item_id:
                    return item
        return None

    def update_item(
        self,
        board_id: str,
        item_id: str,
        *,
        name: Optional[str] = None,
    ) -> Optional[BoardItem]:
        """Rename an item.

        Returns:
            Updated item or *None* if not found.
        """
        item = self.get_item(board_id, item_id)
        if item is None:
            return None
        if name is not None:
            item.name = name
        item.updated_at = _now()
        self._boards[board_id].updated_at = _now()
        return item

    def delete_item(self, board_id: str, item_id: str) -> bool:
        """Remove an item from whichever group it belongs to."""
        board = self._boards.get(board_id)
        if board is None:
            return False
        for group in board.groups:
            original = len(group.items)
            group.items = [i for i in group.items if i.id != item_id]
            if len(group.items) < original:
                board.updated_at = _now()
                return True
        return False

    def add_subitem(
        self,
        board_id: str,
        parent_item_id: str,
        name: str,
        *,
        cell_values: Optional[Dict[str, Any]] = None,
    ) -> BoardItem:
        """Add a sub-item to an existing item.

        Args:
            board_id: Target board.
            parent_item_id: The parent item's ID.
            name: Sub-item display name.
            cell_values: Initial cell values.

        Returns:
            The new sub-item.

        Raises:
            KeyError: If parent item is not found.
        """
        parent = self.get_item(board_id, parent_item_id)
        if parent is None:
            raise KeyError(f"Item {parent_item_id} not found in board {board_id}")
        subitem = BoardItem(
            name=name,
            group_id=parent.group_id,
            cell_values=cell_values or {},
        )
        parent.subitems.append(subitem)
        parent.updated_at = _now()
        return subitem

    # -- Cell values --------------------------------------------------------

    def set_cell(
        self,
        board_id: str,
        item_id: str,
        column_id: str,
        value: Any,
    ) -> bool:
        """Set a cell value for an item.

        Args:
            board_id: Target board.
            item_id: Target item.
            column_id: Target column.
            value: New value to store.

        Returns:
            *True* on success, *False* if item not found.
        """
        item = self.get_item(board_id, item_id)
        if item is None:
            return False
        item.cell_values[column_id] = value
        item.updated_at = _now()
        return True

    # -- Permissions --------------------------------------------------------

    def set_permission(
        self,
        board_id: str,
        user_id: str,
        level: BoardPermissionLevel,
    ) -> None:
        """Grant or update a user's permission on a board.

        Args:
            board_id: Target board.
            user_id: Matrix user ID.
            level: Permission level to grant.
        """
        board = self._get_board_or_raise(board_id)
        for perm in board.permissions:
            if perm.user_id == user_id:
                perm.level = level
                perm.granted_at = _now()
                return
        board.permissions.append(BoardPermission(user_id=user_id, level=level))

    def check_permission(
        self,
        board_id: str,
        user_id: str,
        required: BoardPermissionLevel,
    ) -> bool:
        """Check whether a user has at least a given permission level.

        Permission hierarchy: OWNER > SUBSCRIBER > VIEWER.

        Args:
            board_id: Target board.
            user_id: Matrix user ID.
            required: Minimum required level.

        Returns:
            *True* if access is granted, *False* otherwise.
        """
        board = self._boards.get(board_id)
        if board is None:
            return False
        _rank = {
            BoardPermissionLevel.VIEWER: 0,
            BoardPermissionLevel.SUBSCRIBER: 1,
            BoardPermissionLevel.OWNER: 2,
        }
        for perm in board.permissions:
            if perm.user_id == user_id:
                return _rank[perm.level] >= _rank[required]
        return False

    # -- Views --------------------------------------------------------------

    def add_view(
        self,
        board_id: str,
        name: str,
        view_type: ViewType,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> BoardView:
        """Add a view to a board."""
        board = self._get_board_or_raise(board_id)
        view = BoardView(name=name, view_type=view_type, config=config or {})
        board.views.append(view)
        return view

    # -- Rendering (Matrix / ASCII) -----------------------------------------

    def render_table(self, board_id: str) -> str:
        """Render a board as a Markdown-friendly ASCII table.

        Returns a string suitable for sending to a Matrix room.

        Args:
            board_id: Board to render.

        Returns:
            Multi-line string with ASCII table representation.
        """
        board = self._boards.get(board_id)
        if board is None:
            return f"Board {board_id} not found."

        # Limit displayed columns for readability in chat
        columns = board.columns[:6]
        col_titles = ["Item"] + [c.title[:BOARD_TABLE_MAX_COL_WIDTH] for c in columns]
        widths = [max(20, len(t)) for t in col_titles]

        def row_str(cells: Sequence[str]) -> str:
            return "| " + " | ".join(
                str(c)[:w].ljust(w) for c, w in zip(cells, widths)
            ) + " |"

        sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
        lines: List[str] = [
            f"**{board.name}**",
            "```",
            sep,
            row_str(col_titles),
            sep,
        ]
        for group in board.groups:
            if group.items:
                lines.append(f"  {group.title}")
            for item in group.items:
                cells = [item.name[:20]] + [
                    str(item.cell_values.get(c.id, ""))[:BOARD_TABLE_MAX_COL_WIDTH]
                    for c in columns
                ]
                lines.append(row_str(cells))
        lines += [sep, "```"]
        return "\n".join(lines)

    def render_kanban(self, board_id: str, status_column_id: Optional[str] = None) -> str:
        """Render a lightweight Kanban view grouped by status value.

        Args:
            board_id: Board to render.
            status_column_id: Column whose value is used as the lane key.
              If *None*, the first status column is used.

        Returns:
            Multi-line Markdown string.
        """
        board = self._boards.get(board_id)
        if board is None:
            return f"Board {board_id} not found."

        # Find status column
        status_col = None
        if status_column_id:
            status_col = next((c for c in board.columns if c.id == status_column_id), None)
        if status_col is None:
            status_col = next(
                (c for c in board.columns if c.col_type == ColumnType.STATUS), None
            )

        lanes: Dict[str, List[str]] = {}
        for group in board.groups:
            for item in group.items:
                lane = (
                    str(item.cell_values.get(status_col.id, "No Status"))
                    if status_col
                    else "Items"
                )
                lanes.setdefault(lane, []).append(item.name)

        lines = [f"**{board.name}** – Kanban", "```"]
        for lane, items in lanes.items():
            lines.append(f"\n[ {lane} ]  ({len(items)} items)")
            for itm in items[:10]:
                lines.append(f"  • {itm}")
            if len(items) > 10:
                lines.append(f"  … +{len(items) - 10} more")
        lines.append("```")
        return "\n".join(lines)

    # -- Templates ----------------------------------------------------------

    @staticmethod
    def list_templates() -> List[BoardTemplate]:
        """Return all available board templates."""
        return list(_TEMPLATES.values())

    @staticmethod
    def get_template(template_type: TemplateType) -> Optional[BoardTemplate]:
        """Return a specific template or *None* if not available."""
        return _TEMPLATES.get(template_type)

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise entire engine state to a JSON-compatible dict."""
        return {board_id: board.to_dict() for board_id, board in self._boards.items()}

    def load_dict(self, data: Dict[str, Any]) -> None:
        """Restore engine state from a previously serialised dict."""
        self._boards = {bid: Board.from_dict(bdata) for bid, bdata in data.items()}

    # -- Private helpers ----------------------------------------------------

    def _get_board_or_raise(self, board_id: str) -> Board:
        board = self._boards.get(board_id)
        if board is None:
            raise KeyError(f"Board not found: {board_id}")
        return board

    def _get_group_or_raise(self, board_id: str, group_id: str) -> BoardGroup:
        board = self._get_board_or_raise(board_id)
        for group in board.groups:
            if group.id == group_id:
                return group
        raise KeyError(f"Group {group_id} not found in board {board_id}")

    def _apply_template(self, board: Board, template_type: TemplateType) -> None:
        """Apply a template's columns and groups to a board in-place."""
        tpl = _TEMPLATES.get(template_type)
        if tpl is None:
            logger.warning("Unknown template type: %s", template_type)
            return
        for col_data in tpl.default_columns:
            col = BoardColumn(
                title=col_data["title"],
                col_type=ColumnType(col_data.get("col_type", "text")),
                settings=col_data.get("settings", {}),
            )
            board.columns.append(col)
        for group_title in tpl.default_groups:
            board.groups.append(BoardGroup(title=group_title))
        logger.debug("Template '%s' applied to board %s", template_type.value, board.id)
