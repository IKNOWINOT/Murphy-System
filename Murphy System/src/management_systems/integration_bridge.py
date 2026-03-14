"""
Management Systems – Integration Bridge
=====================================

Bidirectional synchronisation between Murphy System modules and
management board items.

Provides:
- Module health status → board status column updates
- Error events → automatic board item creation in Bug Tracker boards
- Deployment events → timeline milestone updates
- Performance metrics → number column updates
- Event listeners for Murphy subsystem state changes
- Conflict resolution for concurrent updates
- Sync history and audit log

Integration points:
    - Consumes events from ``event_bridge.py`` (PR 2)
    - Updates boards via ``board_engine.py``
    - Updates status via ``status_engine.py``
    - Adds milestones via ``timeline_engine.py``

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

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

MAX_SYNC_HISTORY: int = 5_000
DEFAULT_CONFLICT_POLICY: str = "latest_wins"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SyncDirection(Enum):
    """Direction of a sync rule."""

    MODULE_TO_BOARD = "module_to_board"
    BOARD_TO_MODULE = "board_to_module"
    BIDIRECTIONAL = "bidirectional"


class SyncEventType(Enum):
    """Murphy subsystem event types that trigger sync rules."""

    MODULE_HEALTH_CHANGE = "module_health_change"
    MODULE_ERROR = "module_error"
    DEPLOYMENT_COMPLETE = "deployment_complete"
    DEPLOYMENT_FAILED = "deployment_failed"
    PERFORMANCE_METRIC = "performance_metric"
    STATUS_CHANGE = "status_change"
    ITEM_CREATED = "item_created"
    ITEM_UPDATED = "item_updated"
    CUSTOM = "custom"


class ConflictPolicy(Enum):
    """How to handle concurrent update conflicts."""

    LATEST_WINS = "latest_wins"
    BOARD_WINS = "board_wins"
    MODULE_WINS = "module_wins"
    MANUAL = "manual"


class SyncStatus(Enum):
    """Result of a sync operation."""

    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"
    SKIPPED = "skipped"


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
class SyncRule:
    """Defines how an event maps to a board/item update.

    Args:
        name: Human-readable rule name.
        event_type: Murphy event type that triggers this rule.
        module_name: Source module name (empty = any module).
        board_id: Target board ID (empty = auto-detect from workspace).
        direction: Sync direction.
        column_id: Target column for the update (empty = item-level).
        action: One of ``"update_status"``, ``"create_item"``,
          ``"update_metric"``, ``"add_milestone"``, ``"add_tag"``.
        action_config: Action-specific parameters.
        conflict_policy: Conflict resolution strategy.
        enabled: Whether the rule is active.
    """

    name: str
    event_type: SyncEventType
    module_name: str = ""
    board_id: str = ""
    direction: SyncDirection = SyncDirection.MODULE_TO_BOARD
    column_id: str = ""
    action: str = "update_status"
    action_config: Dict[str, Any] = field(default_factory=dict)
    conflict_policy: ConflictPolicy = ConflictPolicy.LATEST_WINS
    enabled: bool = True
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def matches(self, event: "SyncEvent") -> bool:
        """Return *True* if this rule should handle *event*."""
        if not self.enabled:
            return False
        if event.event_type != self.event_type:
            return False
        if self.module_name and event.module_name != self.module_name:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "event_type": self.event_type.value,
            "module_name": self.module_name,
            "board_id": self.board_id,
            "direction": self.direction.value,
            "column_id": self.column_id,
            "action": self.action,
            "action_config": self.action_config,
            "conflict_policy": self.conflict_policy.value,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncRule":
        obj = cls(
            name=data["name"],
            event_type=SyncEventType(data["event_type"]),
            module_name=data.get("module_name", ""),
            board_id=data.get("board_id", ""),
            direction=SyncDirection(data.get("direction", "module_to_board")),
            column_id=data.get("column_id", ""),
            action=data.get("action", "update_status"),
            action_config=data.get("action_config", {}),
            conflict_policy=ConflictPolicy(data.get("conflict_policy", "latest_wins")),
            enabled=data.get("enabled", True),
        )
        obj.id = data.get("id", obj.id)
        obj.created_at = data.get("created_at", obj.created_at)
        return obj


@dataclass
class SyncEvent:
    """An incoming Murphy subsystem event for bridge processing.

    Args:
        event_type: Category of this event.
        module_name: Originating Murphy module.
        payload: Event-specific data.
          - MODULE_HEALTH_CHANGE: ``{"status": "healthy|degraded|failed", "message": "..."}``
          - MODULE_ERROR: ``{"error": "...", "severity": "critical|high|medium|low"}``
          - DEPLOYMENT_COMPLETE: ``{"version": "...", "environment": "...", "milestone_id": "..."}``
          - PERFORMANCE_METRIC: ``{"metric": "latency_ms", "value": 250, "column_id": "..."}``
    """

    event_type: SyncEventType
    module_name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_uid)
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "module_name": self.module_name,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncEvent":
        obj = cls(
            event_type=SyncEventType(data["event_type"]),
            module_name=data.get("module_name", ""),
            payload=data.get("payload", {}),
        )
        obj.id = data.get("id", obj.id)
        obj.timestamp = data.get("timestamp", obj.timestamp)
        return obj


@dataclass
class SyncHistoryEntry:
    """A record of a completed sync operation.

    Attributes:
        rule_id: Rule that handled the event.
        event_id: Processed event.
        status: Outcome of the sync.
        detail: Human-readable description of what happened.
    """

    rule_id: str
    event_id: str
    status: SyncStatus
    detail: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "event_id": self.event_id,
            "status": self.status.value,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Integration Bridge
# ---------------------------------------------------------------------------


class IntegrationBridge:
    """Bidirectional sync bridge between Murphy modules and Monday boards.

    Registers sync rules, processes incoming Murphy events, applies actions
    to boards (via pluggable action handlers), and maintains an audit log.

    Usage::

        bridge = IntegrationBridge()

        # Register a rule: health changes → update board status
        rule = bridge.add_rule(SyncRule(
            name="Health → Status",
            event_type=SyncEventType.MODULE_HEALTH_CHANGE,
            action="update_status",
            action_config={"status_map": {"healthy": "1", "degraded": "2", "failed": "3"}},
        ))

        # Register action handlers
        bridge.register_action_handler("update_status", my_status_updater)
        bridge.register_action_handler("create_item", my_item_creator)

        # Process an incoming event
        event = SyncEvent(SyncEventType.MODULE_HEALTH_CHANGE, "llm_controller",
                          {"status": "degraded", "message": "High latency"})
        bridge.process_event(event)
    """

    def __init__(self) -> None:
        self._rules: Dict[str, SyncRule] = {}
        self._handlers: Dict[str, Callable[["SyncRule", "SyncEvent"], SyncStatus]] = {}
        self._history: List[SyncHistoryEntry] = []
        self._conflict_log: List[Dict[str, Any]] = []

    # -- Rule management ----------------------------------------------------

    def add_rule(self, rule: SyncRule) -> SyncRule:
        """Register a sync rule.

        Args:
            rule: The rule to register.

        Returns:
            The registered rule.
        """
        self._rules[rule.id] = rule
        logger.info("Sync rule added: %s (%s)", rule.name, rule.id)
        return rule

    def create_rule(
        self,
        name: str,
        event_type: SyncEventType,
        *,
        module_name: str = "",
        board_id: str = "",
        column_id: str = "",
        action: str = "update_status",
        action_config: Optional[Dict[str, Any]] = None,
        direction: SyncDirection = SyncDirection.MODULE_TO_BOARD,
        conflict_policy: ConflictPolicy = ConflictPolicy.LATEST_WINS,
    ) -> SyncRule:
        """Create and register a new sync rule.

        Args:
            name: Human-readable name.
            event_type: Triggering event type.
            module_name: Source module filter (empty = any).
            board_id: Target board.
            column_id: Target column.
            action: Action identifier.
            action_config: Action parameters.
            direction: Sync direction.
            conflict_policy: Conflict resolution policy.

        Returns:
            The new :class:`SyncRule`.
        """
        rule = SyncRule(
            name=name,
            event_type=event_type,
            module_name=module_name,
            board_id=board_id,
            direction=direction,
            column_id=column_id,
            action=action,
            action_config=action_config or {},
            conflict_policy=conflict_policy,
        )
        return self.add_rule(rule)

    def get_rule(self, rule_id: str) -> Optional[SyncRule]:
        return self._rules.get(rule_id)

    def list_rules(
        self, *, event_type: Optional[SyncEventType] = None, enabled_only: bool = False
    ) -> List[SyncRule]:
        """List sync rules with optional filters."""
        rules = list(self._rules.values())
        if event_type is not None:
            rules = [r for r in rules if r.event_type == event_type]
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return sorted(rules, key=lambda r: r.created_at)

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a disabled rule."""
        rule = self._rules.get(rule_id)
        if rule is None:
            return False
        rule.enabled = True
        return True

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule without deleting it."""
        rule = self._rules.get(rule_id)
        if rule is None:
            return False
        rule.enabled = False
        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Remove a rule permanently."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    # -- Action handlers ----------------------------------------------------

    def register_action_handler(
        self,
        action: str,
        handler: Callable[["SyncRule", "SyncEvent"], SyncStatus],
    ) -> None:
        """Register a callable to execute a named action.

        Args:
            action: Action identifier string (e.g. ``"update_status"``).
            handler: ``(rule, event) -> SyncStatus``
        """
        self._handlers[action] = handler
        logger.debug("Action handler registered: %s", action)

    # -- Pre-wired default rules --------------------------------------------

    def bootstrap_default_rules(self) -> List[SyncRule]:
        """Create the default set of Murphy sync rules.

        Returns:
            List of created rules.
        """
        default_rules = [
            SyncRule(
                name="Module Health → Board Status",
                event_type=SyncEventType.MODULE_HEALTH_CHANGE,
                action="update_status",
                action_config={
                    "status_map": {
                        "healthy": "3",    # Done / green
                        "degraded": "1",   # Working On It / orange
                        "failed": "2",     # Stuck / red
                        "unknown": "0",    # Not Started / grey
                    }
                },
            ),
            SyncRule(
                name="Module Error → Bug Item",
                event_type=SyncEventType.MODULE_ERROR,
                action="create_item",
                action_config={
                    "item_name_template": "Error: {module_name} – {error}",
                    "group": "Critical",
                },
            ),
            SyncRule(
                name="Deployment Complete → Milestone",
                event_type=SyncEventType.DEPLOYMENT_COMPLETE,
                action="add_milestone",
                action_config={"name_template": "Deployed {version} to {environment}"},
            ),
            SyncRule(
                name="Deployment Failed → Bug Item",
                event_type=SyncEventType.DEPLOYMENT_FAILED,
                action="create_item",
                action_config={
                    "item_name_template": "Deploy Failed: {module_name} {version}",
                    "group": "High",
                },
            ),
            SyncRule(
                name="Performance Metric → Number Column",
                event_type=SyncEventType.PERFORMANCE_METRIC,
                action="update_metric",
                action_config={},
            ),
        ]
        created = []
        for rule in default_rules:
            self._rules[rule.id] = rule
            created.append(rule)
        logger.info("Bootstrapped %d default sync rules", len(created))
        return created

    # -- Event processing ---------------------------------------------------

    def process_event(self, event: SyncEvent) -> List[SyncHistoryEntry]:
        """Process an incoming Murphy event against all matching rules.

        Args:
            event: The Murphy subsystem event to handle.

        Returns:
            List of history entries for every rule that processed the event.
        """
        entries: List[SyncHistoryEntry] = []
        matching_rules = [r for r in self._rules.values() if r.matches(event)]

        if not matching_rules:
            logger.debug(
                "No rules matched event %s from %s",
                event.event_type.value,
                event.module_name,
            )
            return entries

        for rule in matching_rules:
            entry = self._apply_rule(rule, event)
            entries.append(entry)
            capped_append(self._history, entry)

        if len(self._history) > MAX_SYNC_HISTORY:
            self._history = self._history[-MAX_SYNC_HISTORY:]

        return entries

    def emit_event(
        self,
        event_type: SyncEventType,
        module_name: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> List[SyncHistoryEntry]:
        """Convenience wrapper to create and immediately process an event.

        Args:
            event_type: Type of the event.
            module_name: Originating Murphy module.
            payload: Event data.

        Returns:
            List of sync history entries.
        """
        event = SyncEvent(event_type=event_type, module_name=module_name, payload=payload or {})
        return self.process_event(event)

    # -- History and audit --------------------------------------------------

    def get_history(
        self,
        *,
        rule_id: Optional[str] = None,
        status: Optional[SyncStatus] = None,
        limit: int = 100,
    ) -> List[SyncHistoryEntry]:
        """Return sync history entries.

        Args:
            rule_id: Filter by rule.
            status: Filter by outcome status.
            limit: Maximum entries to return (most recent first).

        Returns:
            Filtered and limited history list.
        """
        history = self._history
        if rule_id is not None:
            history = [e for e in history if e.rule_id == rule_id]
        if status is not None:
            history = [e for e in history if e.status == status]
        return list(reversed(history[-limit:]))

    def get_conflict_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent conflict resolution records."""
        return list(reversed(self._conflict_log[-limit:]))

    def render_sync_status(self) -> str:
        """Render a Markdown summary of the bridge status for Matrix."""
        rules = self.list_rules()
        active = sum(1 for r in rules if r.enabled)
        total_syncs = len(self._history)
        failures = sum(1 for e in self._history if e.status == SyncStatus.FAILED)
        conflicts = len(self._conflict_log)
        lines = [
            "**Integration Bridge Status**",
            "```",
            f"Rules:       {active} active / {len(rules)} total",
            f"Total Syncs: {total_syncs}",
            f"Failures:    {failures}",
            f"Conflicts:   {conflicts}",
            "```",
        ]
        return "\n".join(lines)

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rules": {rid: r.to_dict() for rid, r in self._rules.items()},
            "history": [e.to_dict() for e in self._history[-500:]],
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        self._rules = {
            rid: SyncRule.from_dict(rdata)
            for rid, rdata in data.get("rules", {}).items()
        }

    # -- Private helpers ----------------------------------------------------

    def _apply_rule(
        self, rule: SyncRule, event: SyncEvent
    ) -> SyncHistoryEntry:
        """Execute a rule's action handler and return a history entry."""
        handler = self._handlers.get(rule.action)
        if handler is None:
            logger.debug(
                "No handler for action '%s' (rule %s)", rule.action, rule.id
            )
            return SyncHistoryEntry(
                rule_id=rule.id,
                event_id=event.id,
                status=SyncStatus.SKIPPED,
                detail=f"No handler registered for action '{rule.action}'",
            )

        try:
            status = handler(rule, event)
            detail = f"Action '{rule.action}' executed successfully"
            logger.debug("Rule %s applied to event %s: %s", rule.id, event.id, status.value)
        except Exception as exc:
            status = SyncStatus.FAILED
            detail = "Action execution failed"
            logger.error(
                "Rule %s failed on event %s: %s", rule.id, event.id, exc
            )

        if status == SyncStatus.CONFLICT:
            capped_append(self._conflict_log, {
                "rule_id": rule.id,
                "event_id": event.id,
                "policy": rule.conflict_policy.value,
                "timestamp": _now(),
            })

        return SyncHistoryEntry(
            rule_id=rule.id,
            event_id=event.id,
            status=status,
            detail=detail,
        )
