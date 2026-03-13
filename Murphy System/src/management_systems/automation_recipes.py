"""
Management Systems – Automation Recipes
=====================================

Project management-style "When X happens, do Y" automation recipes.

Provides:
- Trigger types (status change, date arrived, item created, etc.)
- Action types (notify, create item, move item, send Matrix message, etc.)
- Pre-built recipe templates
- Custom recipe builder with condition chains
- Recipe execution log with success/failure tracking
- Rate limiting and circuit breaker for recipe execution

Integration points:
    - Triggers fire from status changes in ``status_engine.py``
    - Matrix messages are sent via ``message_router.py`` (PR 3)
    - Event sourcing via ``event_bridge.py`` (PR 2)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT_WINDOW_SEC: int = 60
DEFAULT_RATE_LIMIT_MAX_CALLS: int = 10
CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
CIRCUIT_BREAKER_RESET_TIMEOUT_SEC: int = 300
MAX_EXECUTION_LOG_ENTRIES: int = 1_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TriggerType(Enum):
    """Event types that can fire an automation recipe."""

    STATUS_CHANGE = "status_change"
    DATE_ARRIVED = "date_arrived"
    ITEM_CREATED = "item_created"
    COLUMN_VALUE_CHANGED = "column_value_changed"
    PERSON_ASSIGNED = "person_assigned"
    EVERY_TIME_PERIOD = "every_time_period"
    SUBITEM_CREATED = "subitem_created"
    FORM_SUBMITTED = "form_submitted"
    BOARD_CREATED = "board_created"
    ITEM_MOVED = "item_moved"


class ActionType(Enum):
    """Actions a recipe can perform when triggered."""

    NOTIFY = "notify"
    CREATE_ITEM = "create_item"
    MOVE_ITEM = "move_item"
    CHANGE_STATUS = "change_status"
    ASSIGN_PERSON = "assign_person"
    SEND_MATRIX_MESSAGE = "send_matrix_message"
    CREATE_SUBITEM = "create_subitem"
    DUPLICATE_GROUP = "duplicate_group"
    ARCHIVE_ITEM = "archive_item"
    SET_COLUMN_VALUE = "set_column_value"
    CREATE_UPDATE = "create_update"
    SEND_EMAIL = "send_email"
    WEBHOOK = "webhook"


class RecipeStatus(Enum):
    """Lifecycle status of a recipe."""

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class CircuitState(Enum):
    """Circuit breaker state machine."""

    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing – reject calls
    HALF_OPEN = "half_open"  # Test recovery


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


def _ts() -> float:
    return time.monotonic()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AutomationTrigger:
    """Describes what event fires a recipe.

    Args:
        trigger_type: The event category.
        board_id: Board scope (empty = any board).
        config: Trigger-specific parameters.
          - STATUS_CHANGE: ``{"column_id": "...", "from": "...", "to": "..."}``
          - DATE_ARRIVED: ``{"column_id": "...", "days_before": 0}``
          - COLUMN_VALUE_CHANGED: ``{"column_id": "...", "to_value": "..."}``
          - EVERY_TIME_PERIOD: ``{"interval_seconds": 3600}``
          - PERSON_ASSIGNED: ``{"column_id": "..."}``
    """

    trigger_type: TriggerType
    board_id: str = ""
    config: Dict[str, Any] = field(default_factory=dict)

    def matches(self, event: Dict[str, Any]) -> bool:
        """Return *True* if *event* satisfies this trigger.

        Args:
            event: Event dict with at least ``type`` and ``board_id``.

        Returns:
            *True* if the trigger condition is met.
        """
        if event.get("type") != self.trigger_type.value:
            return False
        if self.board_id and event.get("board_id") != self.board_id:
            return False
        if self.trigger_type == TriggerType.STATUS_CHANGE:
            cfg_from = self.config.get("from", "*")
            cfg_to = self.config.get("to", "*")
            ev_from = event.get("from_value", "")
            ev_to = event.get("to_value", "")
            col_id = self.config.get("column_id", "")
            if col_id and event.get("column_id") != col_id:
                return False
            if cfg_from != "*" and ev_from != cfg_from:
                return False
            if cfg_to != "*" and ev_to != cfg_to:
                return False
        elif self.trigger_type == TriggerType.COLUMN_VALUE_CHANGED:
            col_id = self.config.get("column_id", "")
            to_value = self.config.get("to_value", "*")
            if col_id and event.get("column_id") != col_id:
                return False
            if to_value != "*" and event.get("to_value") != to_value:
                return False
        elif self.trigger_type == TriggerType.PERSON_ASSIGNED:
            col_id = self.config.get("column_id", "")
            if col_id and event.get("column_id") != col_id:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_type": self.trigger_type.value,
            "board_id": self.board_id,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationTrigger":
        return cls(
            trigger_type=TriggerType(data["trigger_type"]),
            board_id=data.get("board_id", ""),
            config=data.get("config", {}),
        )


@dataclass
class AutomationAction:
    """Describes what a recipe does when triggered.

    Args:
        action_type: The operation to perform.
        config: Action-specific parameters.
          - NOTIFY: ``{"user_id": "...", "message": "..."}``
          - SEND_MATRIX_MESSAGE: ``{"room_id": "...", "message": "..."}``
          - CHANGE_STATUS: ``{"column_id": "...", "to_value": "..."}``
          - CREATE_ITEM: ``{"board_id": "...", "group_id": "...", "name": "..."}``
          - MOVE_ITEM: ``{"target_group_id": "..."}``
          - ASSIGN_PERSON: ``{"column_id": "...", "user_id": "..."}``
          - WEBHOOK: ``{"url": "...", "method": "POST", "payload": {}}``
    """

    action_type: ActionType
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationAction":
        return cls(
            action_type=ActionType(data["action_type"]),
            config=data.get("config", {}),
        )


@dataclass
class RecipeCondition:
    """An additional guard condition that must pass before actions run.

    Args:
        column_id: Column to evaluate.
        operator: Comparison operator string (``eq``, ``neq``, ``contains``,
          ``gt``, ``lt``, ``is_empty``, ``is_not_empty``).
        value: Expected value.
    """

    column_id: str
    operator: str
    value: Any = None

    def evaluate(self, item_data: Dict[str, Any]) -> bool:
        """Evaluate the condition against item data."""
        actual = item_data.get(self.column_id)
        op = self.operator.lower()
        if op == "eq":
            return actual == self.value
        if op == "neq":
            return actual != self.value
        if op == "contains":
            return self.value in str(actual or "")
        if op == "gt":
            try:
                return float(actual) > float(self.value)
            except (TypeError, ValueError):
                return False
        if op == "lt":
            try:
                return float(actual) < float(self.value)
            except (TypeError, ValueError):
                return False
        if op == "is_empty":
            return not actual
        if op == "is_not_empty":
            return bool(actual)
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_id": self.column_id,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecipeCondition":
        return cls(
            column_id=data["column_id"],
            operator=data.get("operator", "eq"),
            value=data.get("value"),
        )


@dataclass
class AutomationRecipe:
    """A complete "when X, do Y" automation recipe.

    Args:
        name: Human-readable name.
        trigger: The event definition.
        actions: Ordered list of actions to execute.
        conditions: Optional extra conditions (all must pass).
        status: Lifecycle state of this recipe.
        description: Optional description.
    """

    name: str
    trigger: AutomationTrigger
    actions: List[AutomationAction] = field(default_factory=list)
    conditions: List[RecipeCondition] = field(default_factory=list)
    status: RecipeStatus = RecipeStatus.ACTIVE
    description: str = ""
    run_count: int = 0
    failure_count: int = 0
    last_run_at: str = ""
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def is_active(self) -> bool:
        return self.status == RecipeStatus.ACTIVE

    def check_conditions(self, item_data: Dict[str, Any]) -> bool:
        """Return *True* if all conditions pass."""
        return all(c.evaluate(item_data) for c in self.conditions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger.to_dict(),
            "actions": [a.to_dict() for a in self.actions],
            "conditions": [c.to_dict() for c in self.conditions],
            "status": self.status.value,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationRecipe":
        obj = cls(
            name=data["name"],
            trigger=AutomationTrigger.from_dict(data["trigger"]),
            actions=[AutomationAction.from_dict(a) for a in data.get("actions", [])],
            conditions=[RecipeCondition.from_dict(c) for c in data.get("conditions", [])],
            status=RecipeStatus(data.get("status", "active")),
            description=data.get("description", ""),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        obj.run_count = data.get("run_count", 0)
        obj.failure_count = data.get("failure_count", 0)
        obj.last_run_at = data.get("last_run_at", "")
        return obj


@dataclass
class ExecutionLogEntry:
    """A single recipe execution record.

    Attributes:
        recipe_id: Recipe that ran.
        success: Whether execution succeeded.
        error: Error message if failed.
        event: The event that triggered execution.
        actions_run: Number of actions executed.
    """

    recipe_id: str
    success: bool
    error: str = ""
    event: Dict[str, Any] = field(default_factory=dict)
    actions_run: int = 0
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "success": self.success,
            "error": self.error,
            "event": self.event,
            "actions_run": self.actions_run,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class _CircuitBreaker:
    """Per-recipe circuit breaker to prevent run-away automation.

    Args:
        failure_threshold: Consecutive failures before opening.
        reset_timeout: Seconds before moving to HALF_OPEN.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        reset_timeout: int = CIRCUIT_BREAKER_RESET_TIMEOUT_SEC,
    ) -> None:
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_ts = 0.0
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if _ts() - self._last_failure_ts >= self._reset_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN – allow one probe
        return True

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_ts = _ts()
        if self._failure_count >= self._threshold:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker OPEN after %d failures", self._failure_count)


# ---------------------------------------------------------------------------
# Pre-built templates
# ---------------------------------------------------------------------------

_RECIPE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Notify on Done",
        "description": "When status changes to Done, send a Matrix notification.",
        "trigger": {
            "trigger_type": "status_change",
            "config": {"to": "3"},  # "3" = Done in default labels
        },
        "actions": [
            {
                "action_type": "send_matrix_message",
                "config": {"message": "✅ Item marked as Done: {item_name}"},
            }
        ],
    },
    {
        "name": "Escalate on Stuck",
        "description": "When status changes to Stuck, notify the assignee.",
        "trigger": {
            "trigger_type": "status_change",
            "config": {"to": "2"},  # "2" = Stuck in default labels
        },
        "actions": [
            {
                "action_type": "notify",
                "config": {"message": "🚨 Item is stuck: {item_name}. Please review."},
            }
        ],
    },
    {
        "name": "Auto-assign on Created",
        "description": "When a new item is created, assign it to the board owner.",
        "trigger": {"trigger_type": "item_created", "config": {}},
        "actions": [
            {
                "action_type": "assign_person",
                "config": {"column_id": "", "user_id": ""},
            }
        ],
    },
    {
        "name": "Archive on Done",
        "description": "When status changes to Done, archive the item after 7 days.",
        "trigger": {
            "trigger_type": "status_change",
            "config": {"to": "3"},
        },
        "actions": [
            {"action_type": "archive_item", "config": {"delay_days": 7}}
        ],
    },
    {
        "name": "Create Bug on Error",
        "description": "When a Murphy module error occurs, create a bug tracker item.",
        "trigger": {
            "trigger_type": "column_value_changed",
            "config": {"column_id": "", "to_value": "error"},
        },
        "actions": [
            {
                "action_type": "create_item",
                "config": {
                    "board_id": "",
                    "group_id": "",
                    "name": "Bug: {item_name}",
                },
            }
        ],
    },
]


# ---------------------------------------------------------------------------
# Recipe Engine
# ---------------------------------------------------------------------------


class RecipeEngine:
    """Central engine for automation recipe management and execution.

    Manages recipe lifecycle, validates triggers against incoming events,
    enforces rate limits and circuit breakers, and maintains an execution log.

    Example::

        engine = RecipeEngine()
        recipe = engine.create_recipe(
            "Notify on Done",
            AutomationTrigger(TriggerType.STATUS_CHANGE, config={"to": "3"}),
            actions=[AutomationAction(ActionType.SEND_MATRIX_MESSAGE,
                                      config={"message": "Done: {item_name}"})],
        )

        def my_handler(action, event):
            print(f"Execute {action.action_type.value}: {action.config}")

        engine.register_action_handler(ActionType.SEND_MATRIX_MESSAGE, my_handler)
        engine.process_event({"type": "status_change", "to_value": "3",
                               "item_name": "Fix login bug"})
    """

    def __init__(
        self,
        rate_limit_window: int = DEFAULT_RATE_LIMIT_WINDOW_SEC,
        rate_limit_max: int = DEFAULT_RATE_LIMIT_MAX_CALLS,
    ) -> None:
        self._recipes: Dict[str, AutomationRecipe] = {}
        self._handlers: Dict[ActionType, Callable[[AutomationAction, Dict[str, Any]], None]] = {}
        self._log: List[ExecutionLogEntry] = []
        self._circuit_breakers: Dict[str, _CircuitBreaker] = {}
        # Rate limiting: {recipe_id: [timestamps]}
        self._rate_windows: Dict[str, List[float]] = {}
        self._rate_window = rate_limit_window
        self._rate_max = rate_limit_max

    # -- Recipe CRUD --------------------------------------------------------

    def create_recipe(
        self,
        name: str,
        trigger: AutomationTrigger,
        actions: Optional[List[AutomationAction]] = None,
        *,
        conditions: Optional[List[RecipeCondition]] = None,
        description: str = "",
    ) -> AutomationRecipe:
        """Create and register a new automation recipe.

        Args:
            name: Human-readable recipe name.
            trigger: Event trigger definition.
            actions: List of actions to run.
            conditions: Optional additional conditions.
            description: Human-readable description.

        Returns:
            The created :class:`AutomationRecipe`.
        """
        recipe = AutomationRecipe(
            name=name,
            trigger=trigger,
            actions=actions or [],
            conditions=conditions or [],
            description=description,
        )
        self._recipes[recipe.id] = recipe
        self._circuit_breakers[recipe.id] = _CircuitBreaker()
        logger.info("Recipe created: %s (%s)", name, recipe.id)
        return recipe

    def get_recipe(self, recipe_id: str) -> Optional[AutomationRecipe]:
        return self._recipes.get(recipe_id)

    def list_recipes(
        self,
        *,
        board_id: str = "",
        status: Optional[RecipeStatus] = None,
    ) -> List[AutomationRecipe]:
        """List recipes, optionally filtered by board or status.

        Args:
            board_id: Limit to recipes scoped to this board.
            status: Lifecycle status filter.

        Returns:
            Matching recipes sorted by creation time.
        """
        recipes = list(self._recipes.values())
        if board_id:
            recipes = [r for r in recipes if r.trigger.board_id in ("", board_id)]
        if status is not None:
            recipes = [r for r in recipes if r.status == status]
        return sorted(recipes, key=lambda r: r.created_at)

    def pause_recipe(self, recipe_id: str) -> bool:
        """Pause a recipe so it does not fire."""
        recipe = self._recipes.get(recipe_id)
        if recipe is None:
            return False
        recipe.status = RecipeStatus.PAUSED
        return True

    def resume_recipe(self, recipe_id: str) -> bool:
        """Re-activate a previously paused recipe."""
        recipe = self._recipes.get(recipe_id)
        if recipe is None:
            return False
        recipe.status = RecipeStatus.ACTIVE
        return True

    def delete_recipe(self, recipe_id: str) -> bool:
        """Remove a recipe permanently."""
        if recipe_id in self._recipes:
            del self._recipes[recipe_id]
            self._circuit_breakers.pop(recipe_id, None)
            self._rate_windows.pop(recipe_id, None)
            return True
        return False

    # -- Action handlers ----------------------------------------------------

    def register_action_handler(
        self,
        action_type: ActionType,
        handler: Callable[[AutomationAction, Dict[str, Any]], None],
    ) -> None:
        """Register a callable to execute when *action_type* fires.

        Args:
            action_type: The action type this handler processes.
            handler: ``(action, event) -> None``
        """
        self._handlers[action_type] = handler
        logger.debug("Action handler registered for %s", action_type.value)

    # -- Event processing ---------------------------------------------------

    def process_event(
        self,
        event: Dict[str, Any],
        *,
        item_data: Optional[Dict[str, Any]] = None,
    ) -> List[ExecutionLogEntry]:
        """Process an event against all active recipes.

        Args:
            event: Event dict (must contain ``type``).
            item_data: Item-level data for condition evaluation.

        Returns:
            List of log entries for triggered recipes.
        """
        entries: List[ExecutionLogEntry] = []
        for recipe in self._recipes.values():
            if not recipe.is_active():
                continue
            if not recipe.trigger.matches(event):
                continue
            if not recipe.check_conditions(item_data or {}):
                continue
            entry = self._execute_recipe(recipe, event, item_data or {})
            entries.append(entry)
        return entries

    def get_execution_log(
        self,
        *,
        recipe_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ExecutionLogEntry]:
        """Return execution log entries.

        Args:
            recipe_id: Filter by recipe (all if *None*).
            limit: Maximum number of entries to return (most recent first).

        Returns:
            List of log entries.
        """
        log = self._log
        if recipe_id is not None:
            log = [e for e in log if e.recipe_id == recipe_id]
        return list(reversed(log[-limit:]))

    # -- Template loading ---------------------------------------------------

    @staticmethod
    def list_templates() -> List[Dict[str, Any]]:
        """Return all pre-built recipe templates."""
        return list(_RECIPE_TEMPLATES)

    def create_from_template(
        self,
        template_name: str,
        *,
        board_id: str = "",
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Optional[AutomationRecipe]:
        """Instantiate a recipe from a named template.

        Args:
            template_name: Name of the template (case-insensitive match).
            board_id: Board scope to apply.
            overrides: Dict merged into the template before creation.

        Returns:
            The created recipe or *None* if template not found.
        """
        tpl = next(
            (t for t in _RECIPE_TEMPLATES if t["name"].lower() == template_name.lower()),
            None,
        )
        if tpl is None:
            return None
        data = {**tpl, **(overrides or {})}
        trigger_data = data["trigger"].copy()
        if board_id:
            trigger_data["board_id"] = board_id
        trigger = AutomationTrigger.from_dict(trigger_data)
        actions = [AutomationAction.from_dict(a) for a in data.get("actions", [])]
        return self.create_recipe(
            data["name"],
            trigger,
            actions,
            description=data.get("description", ""),
        )

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipes": {rid: r.to_dict() for rid, r in self._recipes.items()},
            "log": [e.to_dict() for e in self._log[-500:]],
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        self._recipes = {
            rid: AutomationRecipe.from_dict(rdata)
            for rid, rdata in data.get("recipes", {}).items()
        }
        for rid in self._recipes:
            if rid not in self._circuit_breakers:
                self._circuit_breakers[rid] = _CircuitBreaker()

    # -- Private helpers ----------------------------------------------------

    def _execute_recipe(
        self,
        recipe: AutomationRecipe,
        event: Dict[str, Any],
        item_data: Dict[str, Any],
    ) -> ExecutionLogEntry:
        """Execute a recipe's actions and record the outcome."""
        cb = self._circuit_breakers.get(recipe.id)
        if cb and not cb.allow_request():
            logger.warning(
                "Circuit breaker OPEN for recipe %s – skipping", recipe.id
            )
            return ExecutionLogEntry(
                recipe_id=recipe.id,
                success=False,
                error="Circuit breaker open",
                event=event,
            )

        if not self._check_rate_limit(recipe.id):
            return ExecutionLogEntry(
                recipe_id=recipe.id,
                success=False,
                error="Rate limit exceeded",
                event=event,
            )

        actions_run = 0
        error_msg = ""
        success = True
        for action in recipe.actions:
            handler = self._handlers.get(action.action_type)
            if handler is None:
                logger.debug(
                    "No handler for action type %s (recipe %s)",
                    action.action_type.value,
                    recipe.id,
                )
                actions_run += 1
                continue
            try:
                handler(action, event)
                actions_run += 1
            except Exception as exc:
                error_msg = str(exc)
                success = False
                logger.error(
                    "Action %s failed in recipe %s: %s",
                    action.action_type.value,
                    recipe.id,
                    exc,
                )
                break

        recipe.run_count += 1
        recipe.last_run_at = _now()
        if not success:
            recipe.failure_count += 1
            if cb:
                cb.record_failure()
        else:
            if cb:
                cb.record_success()

        entry = ExecutionLogEntry(
            recipe_id=recipe.id,
            success=success,
            error=error_msg,
            event=event,
            actions_run=actions_run,
        )
        self._log.append(entry)
        if len(self._log) > MAX_EXECUTION_LOG_ENTRIES:
            self._log = self._log[-MAX_EXECUTION_LOG_ENTRIES:]
        return entry

    def _check_rate_limit(self, recipe_id: str) -> bool:
        """Return *False* if the recipe has exceeded its rate limit."""
        now = _ts()
        window = self._rate_windows.setdefault(recipe_id, [])
        # Remove timestamps outside the window
        self._rate_windows[recipe_id] = [t for t in window if now - t < self._rate_window]
        if len(self._rate_windows[recipe_id]) >= self._rate_max:
            return False
        self._rate_windows[recipe_id].append(now)
        return True
