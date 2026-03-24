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
    SCHEDULE = "schedule"          # recurrence / cron-based trigger
    WEBHOOK = "webhook"            # external HTTP trigger


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
    CROSS_BOARD_CREATE = "cross_board_create"   # create item on another board
    CROSS_BOARD_UPDATE = "cross_board_update"   # update item on another board


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


# ---------------------------------------------------------------------------
# Recurrence / Schedule support
# ---------------------------------------------------------------------------

class RecurrenceFrequency(Enum):
    """How often a scheduled automation fires."""
    MINUTELY = "minutely"   # for testing / high-frequency use-cases
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"           # arbitrary cron expression in trigger_config["cron"]


@dataclass
class RecurrenceRule:
    """Recurrence configuration attached to a SCHEDULE-triggered automation.

    For CRON frequency the ``trigger_config`` of the parent rule should
    contain a ``"cron"`` key with a 5-field cron expression, e.g.
    ``"0 9 * * 1"`` (every Monday at 09:00).
    """
    id: str = field(default_factory=_new_id)
    rule_id: str = ""            # ID of the parent AutomationRule
    frequency: RecurrenceFrequency = RecurrenceFrequency.DAILY
    interval: int = 1            # fire every ``interval`` units of frequency
    next_run_at: str = field(default_factory=_now)
    last_run_at: str = ""
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "frequency": self.frequency.value,
            "interval": self.interval,
            "next_run_at": self.next_run_at,
            "last_run_at": self.last_run_at,
            "active": self.active,
        }


# ---------------------------------------------------------------------------
# Automation template marketplace
# ---------------------------------------------------------------------------

@dataclass
class AutomationTemplate:
    """A reusable automation blueprint.

    Templates describe a trigger + typical conditions + actions so users can
    instantiate a :class:`AutomationRule` without building it from scratch.
    """
    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    category: str = ""   # "project_management", "notifications", "crm", etc.
    trigger_type: TriggerType = TriggerType.STATUS_CHANGE
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "trigger_type": self.trigger_type.value,
            "trigger_config": self.trigger_config,
            "conditions": self.conditions,
            "actions": self.actions,
            "created_at": self.created_at,
        }


# Built-in template definitions
_BUILTIN_AUTOMATION_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Notify on Status Change",
        "description": "Send a notification when an item status changes",
        "category": "notifications",
        "trigger_type": "status_change",
        "actions": [{"action_type": "notify", "config": {"message": "Status changed"}}],
    },
    {
        "name": "Daily Standup Reminder",
        "description": "Post a recurring daily standup checklist item",
        "category": "project_management",
        "trigger_type": "schedule",
        "trigger_config": {"frequency": "daily", "interval": 1},
        "actions": [{"action_type": "create_item", "config": {"title": "Daily Standup"}}],
    },
    {
        "name": "Overdue Item Alert",
        "description": "Notify assignee when a date column arrives without completion",
        "category": "project_management",
        "trigger_type": "date_arrived",
        "actions": [{"action_type": "notify", "config": {"message": "Item is due today"}}],
    },
    {
        "name": "New Lead to CRM",
        "description": "When a form is submitted, create an item on the CRM board",
        "category": "crm",
        "trigger_type": "form_submitted",
        "actions": [{"action_type": "cross_board_create", "config": {"target_board_id": ""}}],
    },
    {
        "name": "Weekly Summary Email",
        "description": "Send a weekly summary email of board activity",
        "category": "notifications",
        "trigger_type": "schedule",
        "trigger_config": {"frequency": "weekly", "interval": 1},
        "actions": [{"action_type": "send_email", "config": {"subject": "Weekly Summary"}}],
    },
    {
        "name": "Auto-assign on Item Create",
        "description": "Automatically assign a default person when an item is created",
        "category": "project_management",
        "trigger_type": "item_created",
        "actions": [{"action_type": "assign_person", "config": {"user_id": ""}}],
    },
    {
        "name": "Webhook on Deal Close",
        "description": "Fire a webhook when a deal is moved to Closed Won",
        "category": "crm",
        "trigger_type": "status_change",
        "conditions": [{"column_id": "stage", "operator": "equals", "value": "closed_won"}],
        "actions": [{"action_type": "notify", "config": {"message": "Deal closed!"}}],
    },
]
