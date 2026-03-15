"""
Automations – Rule Engine
===========================

Rule evaluation, trigger matching, and action execution.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .models import (
    ActionType,
    AutomationAction,
    AutomationRule,
    Condition,
    ConditionOperator,
    TriggerType,
    _now,
)

logger = logging.getLogger(__name__)


class AutomationEngine:
    """In-memory automation rule engine.

    Evaluates triggers against registered rules, checks conditions,
    and fires actions.
    """

    def __init__(self) -> None:
        self._rules: Dict[str, AutomationRule] = {}
        self._action_handlers: Dict[ActionType, Callable[..., Any]] = {}
        self._execution_log: List[Dict[str, Any]] = []

    # -- Rule CRUD ----------------------------------------------------------

    def create_rule(
        self,
        name: str,
        board_id: str,
        trigger_type: TriggerType,
        actions: List[AutomationAction],
        *,
        trigger_config: Optional[Dict[str, Any]] = None,
        conditions: Optional[List[Condition]] = None,
    ) -> AutomationRule:
        rule = AutomationRule(
            name=name,
            board_id=board_id,
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            conditions=conditions or [],
            actions=actions,
        )
        self._rules[rule.id] = rule
        logger.info("Automation rule created: %s (%s)", name, rule.id)
        return rule

    def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        return self._rules.get(rule_id)

    def list_rules(self, board_id: str = "") -> List[AutomationRule]:
        rules = list(self._rules.values())
        if board_id:
            rules = [r for r in rules if r.board_id == board_id]
        return rules

    def update_rule(
        self,
        rule_id: str,
        *,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
        conditions: Optional[List[Condition]] = None,
        actions: Optional[List[AutomationAction]] = None,
    ) -> AutomationRule:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise KeyError(f"Rule not found: {rule_id!r}")
        if name is not None:
            rule.name = name
        if enabled is not None:
            rule.enabled = enabled
        if conditions is not None:
            rule.conditions = conditions
        if actions is not None:
            rule.actions = actions
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    # -- Action handlers ----------------------------------------------------

    def register_action_handler(
        self, action_type: ActionType, handler: Callable[..., Any],
    ) -> None:
        self._action_handlers[action_type] = handler

    # -- Trigger evaluation -------------------------------------------------

    def fire_trigger(
        self,
        board_id: str,
        trigger_type: TriggerType,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Evaluate all matching rules for a trigger and execute actions.

        Returns a list of execution results.
        """
        results: List[Dict[str, Any]] = []
        matching = [
            r for r in self._rules.values()
            if r.board_id == board_id
            and r.trigger_type == trigger_type
            and r.enabled
        ]

        for rule in matching:
            if not self._check_conditions(rule, context):
                continue
            action_results = self._execute_actions(rule, context)
            rule.run_count += 1
            rule.last_run_at = _now()
            result = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "trigger_type": trigger_type.value,
                "actions_executed": len(action_results),
                "results": action_results,
            }
            results.append(result)
            capped_append(self._execution_log, result)

        return results

    def _check_conditions(
        self, rule: AutomationRule, context: Dict[str, Any],
    ) -> bool:
        for cond in rule.conditions:
            actual = context.get(cond.column_id)
            if not cond.evaluate(actual):
                return False
        return True

    def _execute_actions(
        self, rule: AutomationRule, context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for action in rule.actions:
            handler = self._action_handlers.get(action.action_type)
            if handler:
                try:
                    result = handler(action.config, context)
                    results.append({"action": action.action_type.value, "success": True, "result": result})
                except Exception as exc:
                    results.append({"action": action.action_type.value, "success": False, "error": str(exc)})
            else:
                results.append({
                    "action": action.action_type.value,
                    "success": True,
                    "result": f"No handler for {action.action_type.value} — logged",
                })
        return results

    def get_execution_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._execution_log[-limit:]))
