"""
Management Systems – Status Engine
================================

Status and workflow tracking with colour-coded labels, customisable
status columns, change automations, priority levels, progress
calculations, audit history, and a configurable workflow state machine.

Integration points:
    - Status updates are published through ``message_router.py`` (PR 3)
    - Automations trigger actions via ``event_bridge.py`` (PR 2)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_STATUS_LABELS: int = 40
DEFAULT_STATUS_LABELS: Dict[str, Dict[str, str]] = {
    "0": {"label": "Not Started", "color": "#C4C4C4"},
    "1": {"label": "Working On It", "color": "#FDAB3D"},
    "2": {"label": "Stuck", "color": "#E2445C"},
    "3": {"label": "Done", "color": "#00C875"},
}

PRIORITY_LEVELS: Dict[str, Dict[str, str]] = {
    "critical": {"label": "Critical", "color": "#333333", "icon": "🔴"},
    "high":     {"label": "High",     "color": "#E2445C", "icon": "🟠"},
    "medium":   {"label": "Medium",   "color": "#FDAB3D", "icon": "🟡"},
    "low":      {"label": "Low",      "color": "#00C875", "icon": "🟢"},
    "none":     {"label": "None",     "color": "#C4C4C4", "icon": "⚪"},
}


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PriorityLevel(Enum):
    """Priority levels with visual indicators."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

    @property
    def icon(self) -> str:
        return PRIORITY_LEVELS[self.value]["icon"]

    @property
    def color(self) -> str:
        return PRIORITY_LEVELS[self.value]["color"]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class StatusLabel:
    """A single named status value with an associated colour.

    Args:
        key: Unique key for this label (used as cell value).
        label: Human-readable display name.
        color: Hex colour string for visual rendering.
        is_done_state: Whether this label represents task completion.
    """

    key: str
    label: str
    color: str = "#C4C4C4"
    is_done_state: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "color": self.color,
            "is_done_state": self.is_done_state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusLabel":
        return cls(
            key=data["key"],
            label=data["label"],
            color=data.get("color", "#C4C4C4"),
            is_done_state=data.get("is_done_state", False),
        )


@dataclass
class StatusColumn:
    """A column definition that holds a set of :class:`StatusLabel` values.

    Args:
        title: Column title.
        labels: Ordered list of available status labels.
    """

    title: str
    labels: List[StatusLabel] = field(default_factory=list)
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    @classmethod
    def with_defaults(cls, title: str = "Status") -> "StatusColumn":
        """Create a new column pre-populated with the default labels."""
        labels = [
            StatusLabel(
                key=k,
                label=v["label"],
                color=v["color"],
                is_done_state=(v["label"] == "Done"),
            )
            for k, v in DEFAULT_STATUS_LABELS.items()
        ]
        return cls(title=title, labels=labels)

    def get_label(self, key: str) -> Optional[StatusLabel]:
        """Return the label matching *key*, or *None*."""
        return next((lbl for lbl in self.labels if lbl.key == key), None)

    def get_done_keys(self) -> Set[str]:
        """Return the set of keys whose labels are marked as done states."""
        return {lbl.key for lbl in self.labels if lbl.is_done_state}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "labels": [lbl.to_dict() for lbl in self.labels],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusColumn":
        obj = cls(title=data["title"])
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.labels = [StatusLabel.from_dict(lbl) for lbl in data.get("labels", [])]
        return obj


@dataclass
class StatusHistoryEntry:
    """An immutable record of a status change on an item.

    Args:
        item_id: Item that changed.
        column_id: Status column that changed.
        old_value: Previous status key.
        new_value: New status key.
        changed_by: User who made the change.
    """

    item_id: str
    column_id: str
    old_value: str
    new_value: str
    changed_by: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "column_id": self.column_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "timestamp": self.timestamp,
        }


@dataclass
class WorkflowTransition:
    """Allowed transition between two status keys.

    Args:
        from_key: Source status key (``"*"`` means any status).
        to_key: Target status key.
        condition: Optional guard callable ``(item_data) -> bool``.
        on_enter: Optional callback fired when transition occurs.
    """

    from_key: str
    to_key: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = field(
        default=None, repr=False, compare=False
    )
    on_enter: Optional[Callable[[str, str, str], None]] = field(
        default=None, repr=False, compare=False
    )

    def allows(self, current_key: str, item_data: Dict[str, Any]) -> bool:
        """Return whether this transition is applicable given the current key."""
        if self.from_key != "*" and self.from_key != current_key:
            return False
        if self.condition is not None:
            try:
                return bool(self.condition(item_data))
            except Exception as exc:
                return False
        return True


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class WorkflowStateMachine:
    """Configurable state machine for a status column.

    Validates and executes transitions between status values.  If no
    transitions are registered the machine allows all changes (open mode).

    Example::

        sm = WorkflowStateMachine()
        sm.add_transition("0", "1")   # Not Started → Working On It
        sm.add_transition("1", "2")   # Working On It → Stuck
        sm.add_transition("1", "3")   # Working On It → Done
        sm.add_transition("*", "0")   # Any → Not Started (reset)

        ok, err = sm.transition("item1", "0", "1", {})
        assert ok
    """

    def __init__(self) -> None:
        self._transitions: List[WorkflowTransition] = []
        self._history: List[StatusHistoryEntry] = []
        self._open_mode: bool = True  # no constraints if no transitions registered

    def add_transition(
        self,
        from_key: str,
        to_key: str,
        *,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        on_enter: Optional[Callable[[str, str, str], None]] = None,
    ) -> None:
        """Register a new allowed transition.

        Args:
            from_key: Source key (or ``"*"`` for any).
            to_key: Destination key.
            condition: Guard callable ``(item_data) -> bool``.
            on_enter: Callback ``(item_id, from_key, to_key)`` on success.
        """
        capped_append(self._transitions,
            WorkflowTransition(
                from_key=from_key,
                to_key=to_key,
                condition=condition,
                on_enter=on_enter,
            )
        )
        self._open_mode = False  # explicit transitions registered → enforce

    def can_transition(
        self,
        item_id: str,
        current_key: str,
        target_key: str,
        item_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if a transition is allowed without executing it."""
        if self._open_mode:
            return True
        return any(
            t.allows(current_key, item_data or {})
            for t in self._transitions
            if t.to_key == target_key
        )

    def transition(
        self,
        item_id: str,
        current_key: str,
        target_key: str,
        item_data: Optional[Dict[str, Any]] = None,
        *,
        column_id: str = "",
        changed_by: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """Attempt a status transition.

        Args:
            item_id: Item being transitioned.
            current_key: Current status key.
            target_key: Desired status key.
            item_data: Item metadata for condition evaluation.
            column_id: Column being changed (for history).
            changed_by: User initiating the change.

        Returns:
            ``(True, None)`` on success, ``(False, reason)`` on failure.
        """
        if current_key == target_key:
            return True, None

        if not self._open_mode:
            matching = [
                t for t in self._transitions
                if t.to_key == target_key and t.allows(current_key, item_data or {})
            ]
            if not matching:
                return False, (
                    f"Transition from '{current_key}' to '{target_key}' is not allowed"
                )
            # Fire on_enter callbacks
            for t in matching:
                if t.on_enter is not None:
                    try:
                        t.on_enter(item_id, current_key, target_key)
                    except Exception as exc:
                        logger.warning("on_enter callback failed: %s", exc)

        entry = StatusHistoryEntry(
            item_id=item_id,
            column_id=column_id,
            old_value=current_key,
            new_value=target_key,
            changed_by=changed_by,
        )
        capped_append(self._history, entry)
        logger.debug(
            "Transition recorded: item=%s %s→%s", item_id, current_key, target_key
        )
        return True, None

    def get_history(self, item_id: Optional[str] = None) -> List[StatusHistoryEntry]:
        """Return transition history, optionally filtered by item.

        Args:
            item_id: If provided, only entries for this item are returned.

        Returns:
            List of history entries in chronological order.
        """
        if item_id is None:
            return list(self._history)
        return [e for e in self._history if e.item_id == item_id]

    def clear_history(self) -> None:
        """Remove all recorded transition history entries."""
        self._history.clear()


# ---------------------------------------------------------------------------
# Status Engine
# ---------------------------------------------------------------------------


class StatusEngine:
    """Central engine for status and workflow management.

    Maintains a registry of :class:`StatusColumn` definitions and
    :class:`WorkflowStateMachine` instances, tracks item status values,
    and provides progress calculations.

    Example::

        engine = StatusEngine()
        col = engine.create_column("Status")
        engine.set_status("board1", "item1", col.id, "1")
        pct = engine.calculate_progress("board1", ["item1", "item2"], col.id)
    """

    def __init__(self) -> None:
        self._columns: Dict[str, StatusColumn] = {}
        self._machines: Dict[str, WorkflowStateMachine] = {}
        # status store: {board_id: {item_id: {column_id: current_key}}}
        self._store: Dict[str, Dict[str, Dict[str, str]]] = {}
        # automation callbacks: {column_id: list of (from_key, to_key, callback)}
        self._automations: List[Tuple[str, str, str, Callable[..., None]]] = []

    # -- Column management --------------------------------------------------

    def create_column(
        self,
        title: str,
        *,
        with_defaults: bool = True,
        labels: Optional[List[StatusLabel]] = None,
    ) -> StatusColumn:
        """Create and register a new status column.

        Args:
            title: Column display name.
            with_defaults: Pre-populate with default labels if *True*.
            labels: Explicit label list (overrides *with_defaults*).

        Returns:
            The new :class:`StatusColumn`.
        """
        if with_defaults and labels is None:
            col = StatusColumn.with_defaults(title)
        else:
            col = StatusColumn(title=title, labels=labels or [])
        self._columns[col.id] = col
        self._machines[col.id] = WorkflowStateMachine()
        logger.info("Status column created: %s (%s)", title, col.id)
        return col

    def get_column(self, column_id: str) -> Optional[StatusColumn]:
        return self._columns.get(column_id)

    def list_columns(self) -> List[StatusColumn]:
        return list(self._columns.values())

    def add_label(
        self,
        column_id: str,
        key: str,
        label: str,
        color: str = "#C4C4C4",
        *,
        is_done_state: bool = False,
    ) -> StatusLabel:
        """Add a new label to a status column.

        Args:
            column_id: Target column.
            key: Unique key for this label.
            label: Display name.
            color: Hex colour string.
            is_done_state: Whether completion semantics apply.

        Returns:
            The new :class:`StatusLabel`.

        Raises:
            KeyError: If *column_id* is not found.
            ValueError: If the column is already at ``MAX_STATUS_LABELS``.
        """
        col = self._columns.get(column_id)
        if col is None:
            raise KeyError(f"Status column not found: {column_id}")
        if len(col.labels) >= MAX_STATUS_LABELS:
            raise ValueError("Status column has reached maximum label limit")
        lbl = StatusLabel(key=key, label=label, color=color, is_done_state=is_done_state)
        col.labels.append(lbl)
        return lbl

    # -- State machine ------------------------------------------------------

    def get_machine(self, column_id: str) -> Optional[WorkflowStateMachine]:
        """Return the workflow state machine for a column."""
        return self._machines.get(column_id)

    def add_transition(
        self,
        column_id: str,
        from_key: str,
        to_key: str,
        *,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        on_enter: Optional[Callable[[str, str, str], None]] = None,
    ) -> None:
        """Register an allowed transition in a column's state machine.

        Args:
            column_id: Target status column.
            from_key: Source key (``"*"`` for any).
            to_key: Destination key.
            condition: Guard callable.
            on_enter: Entry callback.

        Raises:
            KeyError: If *column_id* is not found.
        """
        machine = self._machines.get(column_id)
        if machine is None:
            raise KeyError(f"State machine not found for column: {column_id}")
        machine.add_transition(from_key, to_key, condition=condition, on_enter=on_enter)

    # -- Status CRUD --------------------------------------------------------

    def set_status(
        self,
        board_id: str,
        item_id: str,
        column_id: str,
        new_key: str,
        *,
        changed_by: str = "",
        item_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Set the status of an item.

        Validates the transition through the associated state machine
        and fires registered automation callbacks.

        Args:
            board_id: Board context.
            item_id: Item being updated.
            column_id: Status column.
            new_key: Desired new status key.
            changed_by: User making the change.
            item_data: Item metadata for guard evaluation.

        Returns:
            ``(True, None)`` on success or ``(False, reason)`` on failure.
        """
        current_key = (
            self._store.get(board_id, {}).get(item_id, {}).get(column_id, "")
        )
        machine = self._machines.get(column_id)
        if machine is None:
            # No machine registered, allow freely
            pass
        else:
            ok, err = machine.transition(
                item_id,
                current_key,
                new_key,
                item_data,
                column_id=column_id,
                changed_by=changed_by,
            )
            if not ok:
                return False, err

        # Persist
        self._store.setdefault(board_id, {}).setdefault(item_id, {})[column_id] = new_key

        # Fire automations
        self._fire_automations(column_id, current_key, new_key, item_id, board_id)
        return True, None

    def get_status(
        self,
        board_id: str,
        item_id: str,
        column_id: str,
    ) -> Optional[str]:
        """Return the current status key for an item, or *None* if unset."""
        return self._store.get(board_id, {}).get(item_id, {}).get(column_id)

    # -- Progress tracking --------------------------------------------------

    def calculate_progress(
        self,
        board_id: str,
        item_ids: List[str],
        column_id: str,
    ) -> float:
        """Calculate percentage of items in a done state.

        Args:
            board_id: Board context.
            item_ids: List of item IDs to measure.
            column_id: Status column to evaluate.

        Returns:
            Float in ``[0.0, 100.0]`` representing percentage complete.
        """
        if not item_ids:
            return 0.0
        col = self._columns.get(column_id)
        done_keys = col.get_done_keys() if col else set()
        done_count = sum(
            1
            for iid in item_ids
            if self._store.get(board_id, {}).get(iid, {}).get(column_id) in done_keys
        )
        return round(done_count / (len(item_ids) or 1) * 100, 1)

    def render_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Render a text-based progress bar.

        Args:
            percentage: Value in ``[0, 100]``.
            width: Character width of the bar.

        Returns:
            String like ``[████░░░░░░]  45.0%``.
        """
        filled = int(width * percentage / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {percentage:.1f}%"

    # -- Automations --------------------------------------------------------

    def register_automation(
        self,
        column_id: str,
        from_key: str,
        to_key: str,
        callback: Callable[[str, str, str, str], None],
    ) -> None:
        """Register a callback to fire on a specific status change.

        Args:
            column_id: Status column to watch.
            from_key: Source status key (``"*"`` for any).
            to_key: Target status key (``"*"`` for any).
            callback: ``(column_id, item_id, board_id, new_key) -> None``.
        """
        capped_append(self._automations, (column_id, from_key, to_key, callback))

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise engine state to a JSON-compatible dict."""
        return {
            "columns": {cid: col.to_dict() for cid, col in self._columns.items()},
            "store": self._store,
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        """Restore engine state from a previously serialised dict."""
        self._columns = {
            cid: StatusColumn.from_dict(cdata)
            for cid, cdata in data.get("columns", {}).items()
        }
        self._store = data.get("store", {})
        # Re-create machines for loaded columns
        for cid in self._columns:
            if cid not in self._machines:
                self._machines[cid] = WorkflowStateMachine()

    # -- Private helpers ----------------------------------------------------

    def _fire_automations(
        self,
        column_id: str,
        old_key: str,
        new_key: str,
        item_id: str,
        board_id: str,
    ) -> None:
        for ac_col, ac_from, ac_to, cb in self._automations:
            if ac_col != column_id:
                continue
            from_match = ac_from == "*" or ac_from == old_key
            to_match = ac_to == "*" or ac_to == new_key
            if from_match and to_match:
                try:
                    cb(column_id, item_id, board_id, new_key)
                except Exception as exc:
                    logger.warning("Automation callback failed: %s", exc)
