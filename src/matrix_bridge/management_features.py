# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Management Features for Matrix — MTX-MGMT-001

Owner: Platform Engineering · Dep: matrix_client, message_router

Implements project management features as Matrix room
state events and structured messages.

Features
--------
- **Boards** — board-like views of tasks/workflows as Matrix state events
- **Status tracking** — Not Started, In Progress, Done, Blocked, Review
- **Timeline/Gantt** — progress tracking via structured messages
- **Automations** — status-change triggered automations
- **Dashboards** — summary messages posted to overview rooms
- **Integration** — wires into the existing ``board_system/`` directory

Classes
-------
ItemStatus : Enum
    Status values for management system column types.
BoardColumn : dataclass
    A board column definition.
BoardItem : dataclass
    A work item on a board (task, bug, feature, etc.).
MurphyBoard : dataclass
    A board containing columns and items.
BoardManager : class
    CRUD and status operations for Murphy boards.
DashboardManager : class
    Posts board/project summaries to Matrix rooms.
AutomationTrigger : dataclass
    A status-change automation trigger.
AutomationEngine : class
    Evaluates and fires automations on item status changes.

Usage::

    from matrix_bridge.management_features import BoardManager, DashboardManager

    mgr = BoardManager()
    board = mgr.create_board("Sprint 12", owner="@murphy-triage")
    item = mgr.add_item(board.id, title="Wire SecurityBot to Matrix")
    mgr.set_status(board.id, item.id, ItemStatus.IN_PROGRESS)

    dashboard = DashboardManager(router=my_router)
    await dashboard.post_board_summary(board)
"""
from __future__ import annotations

import datetime
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ItemStatus(Enum):
    """Work-item status values.  Maps to management system status labels."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    REVIEW = "review"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"

    @property
    def emoji(self) -> str:
        _map = {
            "not_started": "⬜",
            "in_progress": "🔵",
            "done": "✅",
            "blocked": "🔴",
            "review": "🟡",
            "cancelled": "⛔",
            "deferred": "⏸️",
        }
        return _map.get(self.value, "❓")

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class ColumnType(Enum):
    """Types of board columns for management system views."""

    TEXT = "text"
    STATUS = "status"
    PERSON = "person"
    DATE = "date"
    PRIORITY = "priority"
    NUMBER = "number"
    TAGS = "tags"
    TIMELINE = "timeline"
    PROGRESS = "progress"
    LINK = "link"


class ItemPriority(Enum):
    """Priority levels for board items."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def emoji(self) -> str:
        _map = {
            "critical": "🔥",
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢",
        }
        return _map.get(self.value, "⚪")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BoardColumn:
    """A column in a Murphy board.

    Attributes
    ----------
    id:
        Unique column identifier.
    title:
        Display title of the column.
    column_type:
        :class:`ColumnType` indicating what data this column holds.
    settings:
        Column-specific settings (e.g. allowed status values).
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    column_type: ColumnType = ColumnType.TEXT
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BoardItem:
    """A work item on a board.

    Attributes
    ----------
    id:
        Unique item identifier.
    title:
        Short item title.
    status:
        Current :class:`ItemStatus`.
    priority:
        :class:`ItemPriority`.
    assignee:
        Matrix user ID of the assigned person/bot.
    due_date:
        Unix timestamp of the due date (0 = not set).
    progress:
        Completion percentage (0–100).
    tags:
        List of tag strings.
    notes:
        Free-text notes.
    column_values:
        Map of column_id → cell value.
    created_at:
        Unix timestamp of creation.
    updated_at:
        Unix timestamp of last update.
    matrix_event_id:
        Matrix event ID of the last state update posted to Matrix.
    subsystem:
        Murphy subsystem this item is linked to.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    status: ItemStatus = ItemStatus.NOT_STARTED
    priority: ItemPriority = ItemPriority.MEDIUM
    assignee: str = ""
    due_date: float = 0.0
    progress: int = 0
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    column_values: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    matrix_event_id: str = ""
    subsystem: str = ""

    def to_state_event(self) -> Dict[str, object]:
        """Return a Matrix state event content dict for this item."""
        return {
            "item_id": self.id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "assignee": self.assignee,
            "due_date": self.due_date,
            "progress": self.progress,
            "tags": self.tags,
            "subsystem": self.subsystem,
            "updated_at": self.updated_at,
        }

    def format_line(self) -> str:
        """Return a one-line Markdown summary of this item."""
        due = ""
        if self.due_date:
            dt = datetime.datetime.fromtimestamp(self.due_date, tz=datetime.timezone.utc)
            due = f" _(due {dt.strftime('%Y-%m-%d')})_"
        assignee = f" → {self.assignee}" if self.assignee else ""
        return (
            f"{self.status.emoji} **{self.title}**"
            f" [{self.priority.emoji} {self.priority.value.upper()}]"
            f"{assignee}{due} `{self.progress}%`"
        )


@dataclass
class MurphyBoard:
    """A Murphy project board.

    Attributes
    ----------
    id:
        Unique board identifier.
    name:
        Display name of the board.
    description:
        Board description.
    owner:
        Matrix user ID of the board owner.
    matrix_room_alias:
        Matrix room where this board posts updates.
    columns:
        Ordered list of :class:`BoardColumn` definitions.
    items:
        All work items on the board.
    created_at:
        Creation timestamp.
    updated_at:
        Last-update timestamp.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    owner: str = ""
    matrix_room_alias: str = "murphy-task-status"
    columns: List[BoardColumn] = field(default_factory=list)
    items: List[BoardItem] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def _default_columns(self) -> List[BoardColumn]:
        return [
            BoardColumn(title="Status", column_type=ColumnType.STATUS),
            BoardColumn(title="Assignee", column_type=ColumnType.PERSON),
            BoardColumn(title="Priority", column_type=ColumnType.PRIORITY),
            BoardColumn(title="Due Date", column_type=ColumnType.DATE),
            BoardColumn(title="Progress", column_type=ColumnType.PROGRESS),
        ]

    def get_item(self, item_id: str) -> Optional[BoardItem]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def items_by_status(self, status: ItemStatus) -> List[BoardItem]:
        return [i for i in self.items if i.status == status]

    def completion_percentage(self) -> float:
        if not self.items:
            return 0.0
        done = sum(1 for i in self.items if i.status == ItemStatus.DONE)
        return round(done / len(self.items) * 100, 1)

    def format_summary(self) -> str:
        """Return a Markdown summary of the board suitable for Matrix."""
        total = len(self.items)
        done = len(self.items_by_status(ItemStatus.DONE))
        in_progress = len(self.items_by_status(ItemStatus.IN_PROGRESS))
        blocked = len(self.items_by_status(ItemStatus.BLOCKED))
        pct = self.completion_percentage()

        lines = [
            f"## 📋 Board: {self.name}",
            f"**Completion:** {pct}% ({done}/{total} done)",
            f"**In Progress:** {in_progress}  |  **Blocked:** {blocked}",
            "",
        ]
        # Blocked items first
        for item in self.items_by_status(ItemStatus.BLOCKED):
            lines.append(item.format_line())
        # Then in-progress
        for item in self.items_by_status(ItemStatus.IN_PROGRESS):
            lines.append(item.format_line())
        # Then not-started
        for item in self.items_by_status(ItemStatus.NOT_STARTED):
            lines.append(item.format_line())
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# AutomationTrigger
# ---------------------------------------------------------------------------


@dataclass
class AutomationTrigger:
    """A status-change automation trigger.

    Attributes
    ----------
    id:
        Unique trigger identifier.
    name:
        Human-readable name.
    board_id:
        Board this trigger watches (``"*"`` = all boards).
    from_status:
        Trigger fires when an item transitions FROM this status.
        ``None`` means "any status".
    to_status:
        Trigger fires when an item transitions TO this status.
    action:
        Async callable ``(board, item) → None`` executed when triggered.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    board_id: str = "*"
    from_status: Optional[ItemStatus] = None
    to_status: ItemStatus = ItemStatus.DONE
    action: Optional[Callable[["MurphyBoard", BoardItem], Any]] = field(
        default=None, repr=False
    )


# ---------------------------------------------------------------------------
# BoardManager
# ---------------------------------------------------------------------------


class BoardManager:
    """CRUD and status operations for Murphy boards.

    All boards are held in memory.  For persistence, use
    :meth:`to_dict` / :meth:`from_dict` and store via the Murphy
    persistence layer.
    """

    def __init__(self) -> None:
        self._boards: Dict[str, MurphyBoard] = {}

    # -----------------------------------------------------------------------
    # Board CRUD
    # -----------------------------------------------------------------------

    def create_board(
        self,
        name: str,
        description: str = "",
        owner: str = "",
        room_alias: str = "murphy-task-status",
    ) -> MurphyBoard:
        """Create a new :class:`MurphyBoard`."""
        board = MurphyBoard(
            name=name,
            description=description,
            owner=owner,
            matrix_room_alias=room_alias,
        )
        board.columns = board._default_columns()
        self._boards[board.id] = board
        logger.info("Created board %r (id=%s)", name, board.id)
        return board

    def get_board(self, board_id: str) -> Optional[MurphyBoard]:
        return self._boards.get(board_id)

    def list_boards(self) -> List[MurphyBoard]:
        return list(self._boards.values())

    def delete_board(self, board_id: str) -> bool:
        if board_id in self._boards:
            del self._boards[board_id]
            logger.info("Deleted board id=%s", board_id)
            return True
        return False

    # -----------------------------------------------------------------------
    # Item CRUD
    # -----------------------------------------------------------------------

    def add_item(
        self,
        board_id: str,
        title: str,
        assignee: str = "",
        priority: ItemPriority = ItemPriority.MEDIUM,
        subsystem: str = "",
        tags: Optional[List[str]] = None,
    ) -> Optional[BoardItem]:
        """Add a new :class:`BoardItem` to board *board_id*."""
        board = self.get_board(board_id)
        if not board:
            logger.warning("add_item: board %r not found", board_id)
            return None
        item = BoardItem(
            title=title,
            assignee=assignee,
            priority=priority,
            subsystem=subsystem,
            tags=tags or [],
        )
        board.items.append(item)
        board.updated_at = time.time()
        return item

    def get_item(self, board_id: str, item_id: str) -> Optional[BoardItem]:
        board = self.get_board(board_id)
        if not board:
            return None
        return board.get_item(item_id)

    def delete_item(self, board_id: str, item_id: str) -> bool:
        board = self.get_board(board_id)
        if not board:
            return False
        before = len(board.items)
        board.items = [i for i in board.items if i.id != item_id]
        board.updated_at = time.time()
        return len(board.items) < before

    # -----------------------------------------------------------------------
    # Status management
    # -----------------------------------------------------------------------

    def set_status(
        self, board_id: str, item_id: str, status: ItemStatus
    ) -> Optional[BoardItem]:
        """Update the status of *item_id* on *board_id*.

        Returns the updated :class:`BoardItem`, or ``None`` if not found.
        """
        item = self.get_item(board_id, item_id)
        if not item:
            logger.warning(
                "set_status: item %r not found on board %r", item_id, board_id
            )
            return None
        old_status = item.status
        item.status = status
        item.updated_at = time.time()
        board = self.get_board(board_id)
        if board:
            board.updated_at = time.time()
        logger.info(
            "Item %r: %s → %s", item.title, old_status.value, status.value
        )
        return item

    def set_progress(
        self, board_id: str, item_id: str, progress: int
    ) -> Optional[BoardItem]:
        """Set the progress percentage (0–100) for *item_id*."""
        item = self.get_item(board_id, item_id)
        if not item:
            return None
        item.progress = max(0, min(100, progress))
        item.updated_at = time.time()
        if item.progress == 100 and item.status not in (
            ItemStatus.DONE,
            ItemStatus.CANCELLED,
        ):
            item.status = ItemStatus.DONE
        if board := self.get_board(board_id):
            board.updated_at = time.time()
        return item

    # -----------------------------------------------------------------------
    # Serialisation
    # -----------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise all boards to a plain dict (for persistence)."""
        result: Dict[str, Any] = {}
        for bid, board in self._boards.items():
            result[bid] = {
                "id": board.id,
                "name": board.name,
                "description": board.description,
                "owner": board.owner,
                "matrix_room_alias": board.matrix_room_alias,
                "created_at": board.created_at,
                "updated_at": board.updated_at,
                "items": [
                    {
                        "id": i.id,
                        "title": i.title,
                        "status": i.status.value,
                        "priority": i.priority.value,
                        "assignee": i.assignee,
                        "due_date": i.due_date,
                        "progress": i.progress,
                        "tags": i.tags,
                        "notes": i.notes,
                        "subsystem": i.subsystem,
                        "created_at": i.created_at,
                        "updated_at": i.updated_at,
                    }
                    for i in board.items
                ],
            }
        return result


# ---------------------------------------------------------------------------
# DashboardManager
# ---------------------------------------------------------------------------


class DashboardManager:
    """Posts board and project summaries to Matrix overview rooms.

    Parameters
    ----------
    router:
        Connected :class:`~message_router.MessageRouter` instance.
        If ``None``, posting operations log-only (offline mode).
    """

    def __init__(self, router: Optional[Any] = None) -> None:
        self._router = router

    async def post_board_summary(
        self,
        board: MurphyBoard,
        room_alias: Optional[str] = None,
    ) -> None:
        """Post a formatted board summary to *room_alias* (or the board's room)."""
        target = room_alias or board.matrix_room_alias
        summary = board.format_summary()
        if self._router:
            await self._router.route_to_room(
                subsystem_name="board_system",
                text=summary,
            )
        else:
            logger.info("DashboardManager (offline): summary for %r:\n%s", target, summary)

    async def post_status_change(
        self,
        board: MurphyBoard,
        item: BoardItem,
        old_status: ItemStatus,
        room_alias: Optional[str] = None,
    ) -> None:
        """Post a status-change notification to the board's room."""
        target = room_alias or board.matrix_room_alias
        msg = (
            f"{item.status.emoji} **{item.title}** changed: "
            f"{old_status.label} → {item.status.label}"
        )
        if item.assignee:
            msg += f" (assigned to {item.assignee})"
        if self._router:
            await self._router.route_to_room(
                subsystem_name="board_system",
                text=msg,
            )
        else:
            logger.info("DashboardManager (offline): status change for %r: %s", target, msg)

    async def post_weekly_summary(
        self,
        boards: List[MurphyBoard],
        room_alias: str = "murphy-task-status",
    ) -> None:
        """Post a cross-board weekly summary to *room_alias*."""
        total_items = sum(len(b.items) for b in boards)
        total_done = sum(
            len(b.items_by_status(ItemStatus.DONE)) for b in boards
        )
        blocked_boards = [b for b in boards if b.items_by_status(ItemStatus.BLOCKED)]

        lines = [
            "## 📊 Weekly Murphy Board Summary",
            f"**Boards:** {len(boards)}  |  **Items:** {total_items}  |  "
            f"**Done:** {total_done}",
        ]
        if blocked_boards:
            lines.append(
                f"⚠️ **Blocked items on:** "
                f"{', '.join(b.name for b in blocked_boards)}"
            )
        for board in boards:
            pct = board.completion_percentage()
            lines.append(f"  • **{board.name}**: {pct}% complete")

        msg = "\n".join(lines)
        if self._router:
            await self._router.route_to_room(
                subsystem_name="board_system",
                text=msg,
            )
        else:
            logger.info("DashboardManager (offline): weekly summary:\n%s", msg)


# ---------------------------------------------------------------------------
# AutomationEngine
# ---------------------------------------------------------------------------


class AutomationEngine:
    """Evaluates and fires automations on board item status changes.

    Register :class:`AutomationTrigger` objects; then call
    :meth:`evaluate` after every :meth:`~BoardManager.set_status` call.
    """

    def __init__(self) -> None:
        self._triggers: List[AutomationTrigger] = []

    def register(self, trigger: AutomationTrigger) -> None:
        """Register an :class:`AutomationTrigger`."""
        capped_append(self._triggers, trigger)
        logger.debug("Registered automation %r", trigger.name)

    async def evaluate(
        self,
        board: MurphyBoard,
        item: BoardItem,
        old_status: ItemStatus,
    ) -> None:
        """Evaluate all triggers against the *old_status* → *item.status* transition."""
        for trigger in self._triggers:
            if trigger.board_id not in ("*", board.id):
                continue
            if trigger.from_status is not None and trigger.from_status != old_status:
                continue
            if trigger.to_status != item.status:
                continue
            if trigger.action:
                try:
                    import asyncio  # local import

                    result = trigger.action(board, item)
                    if asyncio.iscoroutine(result):
                        await result
                    logger.info(
                        "Automation %r fired for item %r", trigger.name, item.title
                    )
                except Exception:
                    logger.exception(
                        "Automation %r raised an exception", trigger.name
                    )

    def list_triggers(self) -> List[Dict[str, object]]:
        """Return a summary list of all registered triggers."""
        return [
            {
                "id": t.id,
                "name": t.name,
                "board_id": t.board_id,
                "from_status": t.from_status.value if t.from_status else None,
                "to_status": t.to_status.value,
            }
            for t in self._triggers
        ]
