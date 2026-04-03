"""
Acceptance tests – Management Parity Phase 7: Advanced Automations
==================================================================

Validates the Automations module (``src/automations``):

- Trigger configuration (all TriggerType values)
- Condition evaluation (ConditionOperator comparisons)
- Action execution (registered handlers invoked)
- Automation chains (multiple actions per rule, multiple rules per trigger)

Run selectively::

    pytest -m parity tests/test_mgmt_parity_phase7.py

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import sys
import os
from typing import Any, Dict, List

import pytest


import automations
from automations import (
    ActionType,
    AutomationAction,
    AutomationEngine,
    AutomationRule,
    Condition,
    ConditionOperator,
    TriggerType,
)

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine() -> AutomationEngine:
    return AutomationEngine()


def _notify_action(target_user_id: str = "alice") -> AutomationAction:
    return AutomationAction(
        action_type=ActionType.NOTIFY,
        config={"target_user_id": target_user_id, "message": "Status changed"},
    )


def _set_column_action(column_id: str, value: Any) -> AutomationAction:
    return AutomationAction(
        action_type=ActionType.SET_COLUMN,
        config={"column_id": column_id, "value": value},
    )


# ---------------------------------------------------------------------------
# 1. Module structure
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_package_version_exists(self):
        assert hasattr(automations, "__version__")

    def test_automation_engine_importable(self):
        assert AutomationEngine is not None

    def test_trigger_types_defined(self):
        for tt in (
            TriggerType.STATUS_CHANGE,
            TriggerType.COLUMN_CHANGE,
            TriggerType.ITEM_CREATED,
            TriggerType.DATE_ARRIVED,
            TriggerType.PERIOD_ELAPSED,
            TriggerType.PERSON_ASSIGNED,
            TriggerType.FORM_SUBMITTED,
        ):
            assert tt is not None

    def test_action_types_defined(self):
        for at in (
            ActionType.NOTIFY,
            ActionType.CREATE_ITEM,
            ActionType.MOVE_ITEM,
            ActionType.SET_COLUMN,
            ActionType.SEND_EMAIL,
            ActionType.CREATE_UPDATE,
            ActionType.ARCHIVE_ITEM,
            ActionType.DUPLICATE_ITEM,
            ActionType.ASSIGN_PERSON,
        ):
            assert at is not None

    def test_condition_operators_defined(self):
        for op in (
            ConditionOperator.EQUALS,
            ConditionOperator.NOT_EQUALS,
            ConditionOperator.CONTAINS,
            ConditionOperator.GREATER_THAN,
            ConditionOperator.LESS_THAN,
            ConditionOperator.IS_EMPTY,
            ConditionOperator.IS_NOT_EMPTY,
        ):
            assert op is not None


# ---------------------------------------------------------------------------
# 2. Trigger configuration
# ---------------------------------------------------------------------------


class TestTriggerConfiguration:
    def test_create_rule_with_status_change_trigger(self):
        engine = _make_engine()
        rule = engine.create_rule(
            name="Notify on Done",
            board_id="board-1",
            trigger_type=TriggerType.STATUS_CHANGE,
            actions=[_notify_action()],
            trigger_config={"column_id": "status", "new_value": "done"},
        )
        assert rule.trigger_type == TriggerType.STATUS_CHANGE
        assert rule.name == "Notify on Done"

    def test_create_rule_with_item_created_trigger(self):
        engine = _make_engine()
        rule = engine.create_rule(
            "Welcome New Item", "board-2",
            TriggerType.ITEM_CREATED,
            actions=[_notify_action("team")],
        )
        assert rule.trigger_type == TriggerType.ITEM_CREATED

    def test_create_rule_with_person_assigned_trigger(self):
        engine = _make_engine()
        rule = engine.create_rule(
            "Assignment Notice", "board-3",
            TriggerType.PERSON_ASSIGNED,
            actions=[_notify_action()],
        )
        assert rule.trigger_type == TriggerType.PERSON_ASSIGNED

    def test_rule_enabled_by_default(self):
        engine = _make_engine()
        rule = engine.create_rule(
            "Default Rule", "board-x",
            TriggerType.STATUS_CHANGE,
            actions=[_notify_action()],
        )
        assert rule.enabled is True

    def test_disable_rule(self):
        engine = _make_engine()
        rule = engine.create_rule(
            "Disabled Rule", "board-x",
            TriggerType.STATUS_CHANGE,
            actions=[_notify_action()],
        )
        updated = engine.update_rule(rule.id, enabled=False)
        assert updated.enabled is False

    def test_list_rules_for_board(self):
        engine = _make_engine()
        engine.create_rule("R1", "board-a", TriggerType.STATUS_CHANGE, [_notify_action()])
        engine.create_rule("R2", "board-a", TriggerType.ITEM_CREATED, [_notify_action()])
        engine.create_rule("R3", "board-b", TriggerType.STATUS_CHANGE, [_notify_action()])
        board_a_rules = engine.list_rules("board-a")
        assert len(board_a_rules) == 2

    def test_delete_rule(self):
        engine = _make_engine()
        rule = engine.create_rule("To Delete", "b", TriggerType.STATUS_CHANGE, [_notify_action()])
        removed = engine.delete_rule(rule.id)
        assert removed is True
        assert engine.get_rule(rule.id) is None


# ---------------------------------------------------------------------------
# 3. Condition evaluation
# ---------------------------------------------------------------------------


class TestConditionEvaluation:
    def test_equals_condition_true(self):
        cond = Condition(column_id="status", operator=ConditionOperator.EQUALS, value="done")
        assert cond.evaluate("done") is True

    def test_equals_condition_false(self):
        cond = Condition(column_id="status", operator=ConditionOperator.EQUALS, value="done")
        assert cond.evaluate("pending") is False

    def test_not_equals_condition(self):
        cond = Condition(column_id="status", operator=ConditionOperator.NOT_EQUALS, value="done")
        assert cond.evaluate("pending") is True

    def test_contains_condition(self):
        cond = Condition(column_id="name", operator=ConditionOperator.CONTAINS, value="bug")
        assert cond.evaluate("fix the bug asap") is True

    def test_greater_than_condition(self):
        cond = Condition(column_id="priority", operator=ConditionOperator.GREATER_THAN, value=5)
        assert cond.evaluate(10) is True
        assert cond.evaluate(3) is False

    def test_less_than_condition(self):
        cond = Condition(column_id="priority", operator=ConditionOperator.LESS_THAN, value=5)
        assert cond.evaluate(2) is True

    def test_is_empty_condition(self):
        cond = Condition(column_id="assignee", operator=ConditionOperator.IS_EMPTY)
        assert cond.evaluate("") is True
        assert cond.evaluate("alice") is False

    def test_is_not_empty_condition(self):
        cond = Condition(column_id="assignee", operator=ConditionOperator.IS_NOT_EMPTY)
        assert cond.evaluate("alice") is True
        assert cond.evaluate("") is False

    def test_rule_with_conditions_filters_trigger(self):
        engine = _make_engine()
        executed_actions: List[Dict[str, Any]] = []

        def mock_handler(action_config: Dict[str, Any], context: Dict[str, Any]) -> str:
            executed_actions.append(action_config)
            return "ok"

        engine.register_action_handler(ActionType.NOTIFY, mock_handler)
        rule = engine.create_rule(
            "Status Done Notify", "board-cond",
            TriggerType.STATUS_CHANGE,
            actions=[_notify_action()],
            conditions=[
                Condition(
                    column_id="status",
                    operator=ConditionOperator.EQUALS,
                    value="done",
                )
            ],
        )
        # Fire trigger with matching condition
        engine.fire_trigger("board-cond", TriggerType.STATUS_CHANGE,
                            {"status": "done"})
        assert len(executed_actions) == 1

        # Fire trigger with non-matching condition — should not fire
        executed_actions.clear()
        engine.fire_trigger("board-cond", TriggerType.STATUS_CHANGE,
                            {"status": "in_progress"})
        assert len(executed_actions) == 0


# ---------------------------------------------------------------------------
# 4. Action execution
# ---------------------------------------------------------------------------


class TestActionExecution:
    def test_notify_action_executed(self):
        engine = _make_engine()
        notified: List[Dict[str, Any]] = []

        def notify_handler(config: Dict[str, Any], ctx: Dict[str, Any]) -> str:
            notified.append(config)
            return "sent"

        engine.register_action_handler(ActionType.NOTIFY, notify_handler)
        engine.create_rule(
            "Notify Rule", "board-exec",
            TriggerType.STATUS_CHANGE,
            actions=[_notify_action("alice")],
        )
        results = engine.fire_trigger("board-exec", TriggerType.STATUS_CHANGE, {})
        assert len(results) == 1
        assert len(notified) == 1

    def test_set_column_action_executed(self):
        engine = _make_engine()
        set_ops: List[Dict[str, Any]] = []

        def set_handler(config: Dict[str, Any], ctx: Dict[str, Any]) -> str:
            set_ops.append(config)
            return "set"

        engine.register_action_handler(ActionType.SET_COLUMN, set_handler)
        engine.create_rule(
            "Auto-assign Priority", "board-col",
            TriggerType.ITEM_CREATED,
            actions=[_set_column_action("priority", "high")],
        )
        engine.fire_trigger("board-col", TriggerType.ITEM_CREATED, {})
        assert len(set_ops) == 1
        assert set_ops[0]["value"] == "high"

    def test_execution_log_populated(self):
        engine = _make_engine()
        engine.register_action_handler(ActionType.NOTIFY, lambda c, x: "ok")
        engine.create_rule(
            "Log Test", "board-log",
            TriggerType.STATUS_CHANGE,
            actions=[_notify_action()],
        )
        engine.fire_trigger("board-log", TriggerType.STATUS_CHANGE, {})
        log = engine.get_execution_log()
        assert len(log) >= 1

    def test_disabled_rule_not_executed(self):
        engine = _make_engine()
        executed: List[int] = []
        engine.register_action_handler(ActionType.NOTIFY, lambda c, x: executed.append(1))
        rule = engine.create_rule(
            "Disabled", "board-dis",
            TriggerType.STATUS_CHANGE,
            actions=[_notify_action()],
        )
        engine.update_rule(rule.id, enabled=False)
        engine.fire_trigger("board-dis", TriggerType.STATUS_CHANGE, {})
        assert len(executed) == 0


# ---------------------------------------------------------------------------
# 5. Automation chains (multiple actions / multiple rules)
# ---------------------------------------------------------------------------


class TestAutomationChains:
    def test_rule_with_multiple_actions(self):
        engine = _make_engine()
        results_by_type: Dict[str, int] = {"notify": 0, "set_column": 0}

        def notify_handler(c: Dict[str, Any], x: Dict[str, Any]) -> str:
            results_by_type["notify"] += 1
            return "notified"

        def set_handler(c: Dict[str, Any], x: Dict[str, Any]) -> str:
            results_by_type["set_column"] += 1
            return "set"

        engine.register_action_handler(ActionType.NOTIFY, notify_handler)
        engine.register_action_handler(ActionType.SET_COLUMN, set_handler)
        engine.create_rule(
            "Multi-Action Rule", "board-chain",
            TriggerType.STATUS_CHANGE,
            actions=[
                _notify_action("alice"),
                _set_column_action("notified_at", "now"),
            ],
        )
        engine.fire_trigger("board-chain", TriggerType.STATUS_CHANGE, {})
        assert results_by_type["notify"] == 1
        assert results_by_type["set_column"] == 1

    def test_multiple_rules_fire_in_sequence(self):
        engine = _make_engine()
        fired_rules: List[str] = []

        def handler(config: Dict[str, Any], ctx: Dict[str, Any]) -> str:
            fired_rules.append(config.get("rule_name", "unknown"))
            return "ok"

        engine.register_action_handler(ActionType.NOTIFY, handler)
        for name in ("Rule A", "Rule B", "Rule C"):
            engine.create_rule(
                name, "board-multi",
                TriggerType.ITEM_CREATED,
                actions=[AutomationAction(
                    action_type=ActionType.NOTIFY,
                    config={"rule_name": name, "target_user_id": "u"},
                )],
            )
        engine.fire_trigger("board-multi", TriggerType.ITEM_CREATED, {})
        assert len(fired_rules) == 3

    def test_chain_with_condition_gates(self):
        """Only rules whose conditions pass fire in a chain."""
        engine = _make_engine()
        fired: List[str] = []

        def handler(config: Dict[str, Any], ctx: Dict[str, Any]) -> str:
            fired.append(config.get("msg", ""))
            return "ok"

        engine.register_action_handler(ActionType.NOTIFY, handler)
        engine.create_rule(
            "Gate-Pass", "board-gate",
            TriggerType.STATUS_CHANGE,
            actions=[AutomationAction(ActionType.NOTIFY, {"msg": "pass", "target_user_id": "u"})],
            conditions=[Condition("status", ConditionOperator.EQUALS, "done")],
        )
        engine.create_rule(
            "Gate-Fail", "board-gate",
            TriggerType.STATUS_CHANGE,
            actions=[AutomationAction(ActionType.NOTIFY, {"msg": "fail", "target_user_id": "u"})],
            conditions=[Condition("status", ConditionOperator.EQUALS, "blocked")],
        )
        engine.fire_trigger("board-gate", TriggerType.STATUS_CHANGE, {"status": "done"})
        assert "pass" in fired
        assert "fail" not in fired
