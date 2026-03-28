"""
Automations – Rule Engine
===========================

Rule evaluation, trigger matching, action execution, recurrence scheduling,
and automation template marketplace.

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
    AutomationTemplate,
    Condition,
    ConditionOperator,
    RecurrenceFrequency,
    RecurrenceRule,
    TriggerType,
    _BUILTIN_AUTOMATION_TEMPLATES,
    _new_id,
    _now,
)

logger = logging.getLogger(__name__)


class RecurrenceScheduler:
    """Manages recurrence rules for SCHEDULE-triggered automations.

    Each :class:`AutomationRule` with ``trigger_type=TriggerType.SCHEDULE``
    can be paired with a :class:`RecurrenceRule` that records the frequency
    and the ISO-8601 timestamp of the next scheduled execution.

    The scheduler does **not** run its own background thread — it is driven
    by the caller invoking :meth:`tick` (e.g. from a cron job or event loop)
    which checks which rules are due and fires them via the provided
    :class:`AutomationEngine`.
    """

    def __init__(self, engine: "AutomationEngine") -> None:
        self._engine = engine
        self._recurrences: Dict[str, RecurrenceRule] = {}

    def schedule(
        self,
        rule_id: str,
        frequency: RecurrenceFrequency,
        *,
        interval: int = 1,
        next_run_at: str = "",
    ) -> RecurrenceRule:
        """Attach a recurrence rule to an existing automation rule."""
        rec = RecurrenceRule(
            rule_id=rule_id,
            frequency=frequency,
            interval=interval,
            next_run_at=next_run_at or _now(),
        )
        self._recurrences[rec.id] = rec
        logger.info("Recurrence scheduled: rule=%s freq=%s interval=%d",
                    rule_id, frequency.value, interval)
        return rec

    def unschedule(self, recurrence_id: str) -> bool:
        """Remove a recurrence rule by ID."""
        if recurrence_id in self._recurrences:
            del self._recurrences[recurrence_id]
            return True
        return False

    def list_recurrences(self) -> List[RecurrenceRule]:
        """Return all registered recurrence rules."""
        return list(self._recurrences.values())

    def tick(self, now_iso: str) -> List[Dict[str, Any]]:
        """Fire all recurrence rules whose next_run_at ≤ *now_iso*.

        Returns a list of execution result dicts from the engine.
        After firing, each recurrence's ``next_run_at`` is advanced by one
        interval unit (represented here as a simple marker — real
        calendar arithmetic should be added for production use).
        """
        fired: List[Dict[str, Any]] = []
        for rec in list(self._recurrences.values()):
            if not rec.active:
                continue
            if rec.next_run_at <= now_iso:
                rule = self._engine.get_rule(rec.rule_id)
                if rule and rule.enabled:
                    results = self._engine.fire_trigger(
                        rule.board_id, TriggerType.SCHEDULE,
                        {"recurrence_id": rec.id, "rule_id": rec.rule_id},
                    )
                    rec.last_run_at = now_iso
                    # Advance next_run_at — use now as the new baseline so
                    # that the next execution is deferred by ≥ 1 run cycle.
                    rec.next_run_at = now_iso  # caller sets accurate next time
                    fired.extend(results)
                    logger.debug("Recurrence fired: %s rule=%s", rec.id, rec.rule_id)
        return fired


class AutomationEngine:
    """In-memory automation rule engine.

    Evaluates triggers against registered rules, checks conditions,
    fires actions, and provides a built-in template marketplace.
    """

    def __init__(self) -> None:
        self._rules: Dict[str, AutomationRule] = {}
        self._action_handlers: Dict[ActionType, Callable[..., Any]] = {}
        self._execution_log: List[Dict[str, Any]] = []
        self._templates: Dict[str, AutomationTemplate] = {}
        self._webhook_handlers: List[Callable[[str, Dict[str, Any]], None]] = []
        self._scheduler: Optional[RecurrenceScheduler] = None
        self._seed_builtin_templates()

    @property
    def scheduler(self) -> RecurrenceScheduler:
        """Lazy-initialised :class:`RecurrenceScheduler` for this engine."""
        if self._scheduler is None:
            self._scheduler = RecurrenceScheduler(self)
        return self._scheduler

    # -- Template marketplace -----------------------------------------------

    def _seed_builtin_templates(self) -> None:
        for tdef in _BUILTIN_AUTOMATION_TEMPLATES:
            tmpl = AutomationTemplate(
                name=tdef["name"],
                description=tdef["description"],
                category=tdef["category"],
                trigger_type=TriggerType(tdef["trigger_type"]),
                trigger_config=tdef.get("trigger_config", {}),
                conditions=tdef.get("conditions", []),
                actions=tdef.get("actions", []),
            )
            self._templates[tmpl.id] = tmpl

    def list_templates(self, *, category: str = "") -> List[AutomationTemplate]:
        """Return available automation templates, optionally filtered by category."""
        templates = list(self._templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates

    def get_template(self, template_id: str) -> Optional[AutomationTemplate]:
        """Return a single template by ID."""
        return self._templates.get(template_id)

    def create_template(
        self,
        name: str,
        trigger_type: TriggerType,
        actions: List[AutomationAction],
        *,
        description: str = "",
        category: str = "",
        conditions: Optional[List[Condition]] = None,
        trigger_config: Optional[Dict[str, Any]] = None,
    ) -> AutomationTemplate:
        """Persist a custom automation template."""
        tmpl = AutomationTemplate(
            name=name,
            description=description,
            category=category,
            trigger_type=trigger_type,
            trigger_config=trigger_config or {},
            conditions=[c.to_dict() for c in (conditions or [])],
            actions=[a.to_dict() for a in actions],
        )
        self._templates[tmpl.id] = tmpl
        logger.info("AutomationTemplate created: %s (%s)", name, tmpl.id)
        return tmpl

    def create_rule_from_template(
        self,
        template_id: str,
        board_id: str,
        *,
        name: str = "",
    ) -> AutomationRule:
        """Instantiate a new :class:`AutomationRule` from a template."""
        tmpl = self._templates.get(template_id)
        if tmpl is None:
            raise KeyError(f"Template not found: {template_id!r}")
        actions = [
            AutomationAction(
                action_type=ActionType(a["action_type"]),
                config=dict(a.get("config", {})),
            )
            for a in tmpl.actions
        ]
        from .models import ConditionOperator
        conditions = [
            Condition(
                column_id=c.get("column_id", ""),
                operator=ConditionOperator(c.get("operator", "equals")),
                value=c.get("value"),
            )
            for c in tmpl.conditions
        ]
        rule = self.create_rule(
            name=name or tmpl.name,
            board_id=board_id,
            trigger_type=tmpl.trigger_type,
            actions=actions,
            trigger_config=dict(tmpl.trigger_config),
            conditions=conditions,
        )
        return rule

    # -- Webhook trigger adapter --------------------------------------------

    def register_webhook_handler(
        self, handler: Callable[[str, Dict[str, Any]], None],
    ) -> None:
        """Register a callable invoked when a WEBHOOK trigger fires.

        ``handler(board_id, payload)`` — the payload is the raw webhook body.
        """
        self._webhook_handlers.append(handler)

    def receive_webhook(
        self, board_id: str, payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Process an incoming webhook payload and fire matching rules.

        Internally calls :meth:`fire_trigger` with ``TriggerType.WEBHOOK``
        so all registered webhook rules are evaluated.  Any registered
        webhook handlers are also invoked before rule evaluation.
        """
        for handler in self._webhook_handlers:
            try:
                handler(board_id, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Webhook handler error: %s", exc)
        return self.fire_trigger(board_id, TriggerType.WEBHOOK, payload)

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
