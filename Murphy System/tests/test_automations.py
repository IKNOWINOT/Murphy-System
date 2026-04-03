"""Tests for Phase 7 – Advanced Automations."""

import sys, os

import pytest
from automations.models import (
    ActionType, AutomationAction, AutomationRule, Condition,
    ConditionOperator, TriggerType,
)
from automations.engine import AutomationEngine


class TestConditions:
    def test_equals(self):
        c = Condition(column_id="status", operator=ConditionOperator.EQUALS, value="Done")
        assert c.evaluate("Done")
        assert not c.evaluate("Working")

    def test_not_equals(self):
        c = Condition(operator=ConditionOperator.NOT_EQUALS, value="Done")
        assert c.evaluate("Working")
        assert not c.evaluate("Done")

    def test_contains(self):
        c = Condition(operator=ConditionOperator.CONTAINS, value="bug")
        assert c.evaluate("critical bug fix")
        assert not c.evaluate("feature request")

    def test_greater_than(self):
        c = Condition(operator=ConditionOperator.GREATER_THAN, value=10)
        assert c.evaluate(15)
        assert not c.evaluate(5)

    def test_less_than(self):
        c = Condition(operator=ConditionOperator.LESS_THAN, value=10)
        assert c.evaluate(5)
        assert not c.evaluate(15)

    def test_is_empty(self):
        c = Condition(operator=ConditionOperator.IS_EMPTY)
        assert c.evaluate("")
        assert c.evaluate(None)
        assert not c.evaluate("data")

    def test_is_not_empty(self):
        c = Condition(operator=ConditionOperator.IS_NOT_EMPTY)
        assert c.evaluate("data")
        assert not c.evaluate("")

    def test_to_dict(self):
        c = Condition(column_id="col1", operator=ConditionOperator.EQUALS, value="x")
        assert c.to_dict()["operator"] == "equals"


class TestModels:
    def test_rule_to_dict(self):
        r = AutomationRule(name="My Rule", board_id="b1")
        d = r.to_dict()
        assert d["name"] == "My Rule"
        assert d["enabled"] is True

    def test_action_to_dict(self):
        a = AutomationAction(action_type=ActionType.NOTIFY, config={"msg": "hi"})
        assert a.to_dict()["action_type"] == "notify"


class TestEngine:
    def test_create_rule(self):
        eng = AutomationEngine()
        r = eng.create_rule(
            "Auto", "b1", TriggerType.STATUS_CHANGE,
            [AutomationAction(action_type=ActionType.NOTIFY)],
        )
        assert r.name == "Auto"
        assert eng.get_rule(r.id) is r

    def test_list_rules(self):
        eng = AutomationEngine()
        eng.create_rule("R1", "b1", TriggerType.ITEM_CREATED, [])
        eng.create_rule("R2", "b2", TriggerType.ITEM_CREATED, [])
        assert len(eng.list_rules()) == 2
        assert len(eng.list_rules("b1")) == 1

    def test_update_rule(self):
        eng = AutomationEngine()
        r = eng.create_rule("Old", "b1", TriggerType.STATUS_CHANGE, [])
        eng.update_rule(r.id, name="New", enabled=False)
        assert r.name == "New"
        assert r.enabled is False

    def test_update_rule_not_found(self):
        eng = AutomationEngine()
        with pytest.raises(KeyError):
            eng.update_rule("bad", name="X")

    def test_delete_rule(self):
        eng = AutomationEngine()
        r = eng.create_rule("R", "b1", TriggerType.STATUS_CHANGE, [])
        assert eng.delete_rule(r.id)
        assert not eng.delete_rule(r.id)

    def test_fire_trigger_no_match(self):
        eng = AutomationEngine()
        results = eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {})
        assert results == []

    def test_fire_trigger_simple(self):
        eng = AutomationEngine()
        eng.create_rule(
            "Notify on status", "b1", TriggerType.STATUS_CHANGE,
            [AutomationAction(action_type=ActionType.NOTIFY, config={"msg": "done"})],
        )
        results = eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {"status": "Done"})
        assert len(results) == 1
        assert results[0]["actions_executed"] == 1

    def test_fire_trigger_with_condition(self):
        eng = AutomationEngine()
        eng.create_rule(
            "Only Done", "b1", TriggerType.STATUS_CHANGE,
            [AutomationAction(action_type=ActionType.NOTIFY)],
            conditions=[Condition(column_id="status", operator=ConditionOperator.EQUALS, value="Done")],
        )
        r1 = eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {"status": "Working"})
        assert len(r1) == 0
        r2 = eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {"status": "Done"})
        assert len(r2) == 1

    def test_fire_trigger_disabled_rule(self):
        eng = AutomationEngine()
        r = eng.create_rule("R", "b1", TriggerType.STATUS_CHANGE,
                            [AutomationAction(action_type=ActionType.NOTIFY)])
        eng.update_rule(r.id, enabled=False)
        results = eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {})
        assert len(results) == 0

    def test_fire_with_handler(self):
        eng = AutomationEngine()
        captured = []
        eng.register_action_handler(ActionType.NOTIFY, lambda cfg, ctx: captured.append(cfg))
        eng.create_rule("R", "b1", TriggerType.ITEM_CREATED,
                        [AutomationAction(action_type=ActionType.NOTIFY, config={"x": 1})])
        eng.fire_trigger("b1", TriggerType.ITEM_CREATED, {})
        assert len(captured) == 1

    def test_run_count_increments(self):
        eng = AutomationEngine()
        r = eng.create_rule("R", "b1", TriggerType.STATUS_CHANGE,
                            [AutomationAction(action_type=ActionType.NOTIFY)])
        eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {})
        eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {})
        assert r.run_count == 2

    def test_execution_log(self):
        eng = AutomationEngine()
        eng.create_rule("R", "b1", TriggerType.STATUS_CHANGE,
                        [AutomationAction(action_type=ActionType.NOTIFY)])
        eng.fire_trigger("b1", TriggerType.STATUS_CHANGE, {})
        log = eng.get_execution_log()
        assert len(log) == 1


class TestAPIRouter:
    def test_create_router(self):
        from automations.api import create_automations_router
        router = create_automations_router()
        assert router is not None


# ===================================================================
# Phase 7 additions: Recurrence, Templates, Webhook, Cross-board
# ===================================================================

class TestRecurrenceScheduler:
    def test_schedule_creates_recurrence(self):
        from automations.models import RecurrenceFrequency
        from automations.engine import RecurrenceScheduler
        eng = AutomationEngine()
        rule = eng.create_rule("Sched", "b1", TriggerType.SCHEDULE,
                               [AutomationAction(action_type=ActionType.NOTIFY)])
        scheduler = RecurrenceScheduler(eng)
        rec = scheduler.schedule(rule.id, RecurrenceFrequency.DAILY)
        assert rec.rule_id == rule.id
        assert rec.frequency.value == "daily"
        assert len(scheduler.list_recurrences()) == 1

    def test_unschedule(self):
        from automations.models import RecurrenceFrequency
        from automations.engine import RecurrenceScheduler
        eng = AutomationEngine()
        rule = eng.create_rule("R", "b1", TriggerType.SCHEDULE,
                               [AutomationAction(action_type=ActionType.NOTIFY)])
        scheduler = RecurrenceScheduler(eng)
        rec = scheduler.schedule(rule.id, RecurrenceFrequency.WEEKLY)
        assert scheduler.unschedule(rec.id)
        assert len(scheduler.list_recurrences()) == 0

    def test_tick_fires_due_rules(self):
        from automations.models import RecurrenceFrequency
        from automations.engine import RecurrenceScheduler
        eng = AutomationEngine()
        rule = eng.create_rule("Tick", "b1", TriggerType.SCHEDULE,
                               [AutomationAction(action_type=ActionType.NOTIFY)])
        scheduler = RecurrenceScheduler(eng)
        scheduler.schedule(rule.id, RecurrenceFrequency.HOURLY,
                           next_run_at="2000-01-01T00:00:00+00:00")
        results = scheduler.tick("2026-01-01T00:00:00+00:00")
        assert len(results) == 1
        assert rule.run_count == 1

    def test_engine_scheduler_property(self):
        from automations.models import RecurrenceFrequency
        eng = AutomationEngine()
        rule = eng.create_rule("R2", "b1", TriggerType.SCHEDULE,
                               [AutomationAction(action_type=ActionType.NOTIFY)])
        rec = eng.scheduler.schedule(rule.id, RecurrenceFrequency.DAILY)
        assert rec.rule_id == rule.id


class TestAutomationTemplates:
    def test_builtin_templates_loaded(self):
        eng = AutomationEngine()
        templates = eng.list_templates()
        assert len(templates) >= 5

    def test_list_templates_by_category(self):
        eng = AutomationEngine()
        notif = eng.list_templates(category="notifications")
        assert all(t.category == "notifications" for t in notif)
        assert len(notif) >= 1

    def test_get_template(self):
        eng = AutomationEngine()
        templates = eng.list_templates()
        t = eng.get_template(templates[0].id)
        assert t is not None
        assert t.id == templates[0].id

    def test_create_custom_template(self):
        eng = AutomationEngine()
        tmpl = eng.create_template(
            "My Template", TriggerType.ITEM_CREATED,
            [AutomationAction(action_type=ActionType.NOTIFY)],
            category="custom",
        )
        assert tmpl.category == "custom"
        assert eng.get_template(tmpl.id) is not None

    def test_create_rule_from_template(self):
        eng = AutomationEngine()
        notif_templates = eng.list_templates(category="notifications")
        assert notif_templates
        rule = eng.create_rule_from_template(notif_templates[0].id, "board-x")
        assert rule.board_id == "board-x"
        assert rule.id in [r.id for r in eng.list_rules()]

    def test_template_to_dict(self):
        eng = AutomationEngine()
        t = eng.list_templates()[0]
        d = t.to_dict()
        assert "trigger_type" in d
        assert "actions" in d


class TestWebhookTrigger:
    def test_receive_webhook_fires_rules(self):
        eng = AutomationEngine()
        eng.create_rule("WH Rule", "b1", TriggerType.WEBHOOK,
                        [AutomationAction(action_type=ActionType.NOTIFY)])
        results = eng.receive_webhook("b1", {"event": "new_lead"})
        assert len(results) == 1

    def test_webhook_handler_called(self):
        eng = AutomationEngine()
        calls = []
        eng.register_webhook_handler(lambda bid, p: calls.append((bid, p)))
        eng.receive_webhook("b1", {"key": "val"})
        assert calls == [("b1", {"key": "val"})]

    def test_cross_board_action_types(self):
        from automations.models import ActionType
        assert ActionType.CROSS_BOARD_CREATE.value == "cross_board_create"
        assert ActionType.CROSS_BOARD_UPDATE.value == "cross_board_update"

    def test_schedule_trigger_type(self):
        assert TriggerType.SCHEDULE.value == "schedule"
        assert TriggerType.WEBHOOK.value == "webhook"
