"""
Automations – Data Models
===========================

Core data structures for the Advanced Automations system
(Phase 7 of management systems parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_UTC = timezone.utc


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


class TriggerType(Enum):
    """Event types that can fire an automation."""
    STATUS_CHANGE = "status_change"
    COLUMN_CHANGE = "column_change"
    ITEM_CREATED = "item_created"
    DATE_ARRIVED = "date_arrived"
    PERIOD_ELAPSED = "period_elapsed"
    PERSON_ASSIGNED = "person_assigned"
    FORM_SUBMITTED = "form_submitted"


class ActionType(Enum):
    """Actions an automation can perform."""
    NOTIFY = "notify"
    CREATE_ITEM = "create_item"
    MOVE_ITEM = "move_item"
    SET_COLUMN = "set_column"
    SEND_EMAIL = "send_email"
    CREATE_UPDATE = "create_update"
    ARCHIVE_ITEM = "archive_item"
    DUPLICATE_ITEM = "duplicate_item"
    ASSIGN_PERSON = "assign_person"


class ConditionOperator(Enum):
    """Operators for rule conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"


@dataclass
class Condition:
    """A guard condition that must be true for a rule to fire."""
    column_id: str = ""
    operator: ConditionOperator = ConditionOperator.EQUALS
    value: Any = None

    def evaluate(self, actual_value: Any) -> bool:
        if self.operator == ConditionOperator.EQUALS:
            return actual_value == self.value
        if self.operator == ConditionOperator.NOT_EQUALS:
            return actual_value != self.value
        if self.operator == ConditionOperator.CONTAINS:
            return self.value in str(actual_value)
        if self.operator == ConditionOperator.GREATER_THAN:
            try:
                return float(actual_value) > float(self.value)
            except (TypeError, ValueError):
                return False
        if self.operator == ConditionOperator.LESS_THAN:
            try:
                return float(actual_value) < float(self.value)
            except (TypeError, ValueError):
                return False
        if self.operator == ConditionOperator.IS_EMPTY:
            return not actual_value
        if self.operator == ConditionOperator.IS_NOT_EMPTY:
            return bool(actual_value)
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_id": self.column_id,
            "operator": self.operator.value,
            "value": self.value,
        }


@dataclass
class AutomationAction:
    """An action to perform when a rule fires."""
    action_type: ActionType = ActionType.NOTIFY
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "config": self.config,
        }


@dataclass
class AutomationRule:
    """A complete automation rule: trigger + conditions + actions."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    board_id: str = ""
    trigger_type: TriggerType = TriggerType.STATUS_CHANGE
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Condition] = field(default_factory=list)
    actions: List[AutomationAction] = field(default_factory=list)
    enabled: bool = True
    run_count: int = 0
    last_run_at: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "board_id": self.board_id,
            "trigger_type": self.trigger_type.value,
            "trigger_config": self.trigger_config,
            "conditions": [c.to_dict() for c in self.conditions],
            "actions": [a.to_dict() for a in self.actions],
            "enabled": self.enabled,
            "run_count": self.run_count,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at,
        }
