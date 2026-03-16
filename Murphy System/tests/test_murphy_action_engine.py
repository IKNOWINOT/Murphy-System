"""
Murphy System - Tests for Murphy Action Engine
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""
import os

import uuid
from datetime import datetime, timezone

import pytest

from murphy_action_engine import (
    ActionParameter,
    ActionSchema,
    ActionResult,
    ActionRegistry,
    ActionPlanner,
    ActionExecutor,
    get_global_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_schema(name: str = None, with_required_param: bool = False) -> ActionSchema:
    name = name or f"action_{uuid.uuid4().hex[:8]}"
    params = []
    if with_required_param:
        params.append(
            ActionParameter(name="query", description="Search query", type="string", required=True)
        )
    return ActionSchema(
        name=name,
        description=f"Test action {name}",
        parameters=params,
        returns="str",
    )


def _noop(*args, **kwargs) -> str:
    return "ok"


def _failing(*args, **kwargs) -> str:
    raise RuntimeError("simulated failure")


# ---------------------------------------------------------------------------
# TestActionSchema
# ---------------------------------------------------------------------------

class TestActionSchema:
    def test_create_minimal(self):
        schema = ActionSchema(name="my_action", description="Does something")
        assert schema.name == "my_action"
        assert schema.parameters == []
        assert schema.returns == "Any"

    def test_create_with_parameter(self):
        param = ActionParameter(
            name="limit",
            description="Max results",
            type="number",
            required=False,
            default=10,
        )
        schema = ActionSchema(
            name="list_items",
            description="Lists items up to limit",
            parameters=[param],
        )
        assert len(schema.parameters) == 1
        assert schema.parameters[0].name == "limit"
        assert schema.parameters[0].default == 10

    def test_action_result_fields(self):
        result = ActionResult(
            action_name="send_email",
            success=True,
            output="sent",
            cost_usd=0.001,
            duration_ms=12.5,
            confidence=0.9,
        )
        assert result.success is True
        assert result.error is None
        assert result.cost_usd == pytest.approx(0.001)

    def test_action_result_failure(self):
        result = ActionResult(
            action_name="broken_action",
            success=False,
            error="timeout",
        )
        assert result.success is False
        assert "timeout" in result.error


# ---------------------------------------------------------------------------
# TestActionRegistry
# ---------------------------------------------------------------------------

class TestActionRegistry:
    def test_register_and_get(self):
        registry = ActionRegistry()
        schema = _make_schema("greet")
        registry.register(schema, _noop)
        retrieved = registry.get("greet")
        assert retrieved is not None
        assert retrieved.name == "greet"

    def test_get_missing_returns_none(self):
        registry = ActionRegistry()
        assert registry.get("nonexistent_xyz") is None

    def test_list_all_empty(self):
        registry = ActionRegistry()
        assert registry.list_all() == []

    def test_list_all_returns_registered(self):
        registry = ActionRegistry()
        names = [f"act_{uuid.uuid4().hex[:6]}" for _ in range(3)]
        for n in names:
            registry.register(_make_schema(n), _noop)
        all_names = [s.name for s in registry.list_all()]
        for n in names:
            assert n in all_names

    def test_validate_call_passes_with_no_required(self):
        registry = ActionRegistry()
        schema = _make_schema("no_params")
        registry.register(schema, _noop)
        assert registry.validate_call("no_params", {}) is True

    def test_validate_call_fails_missing_required(self):
        registry = ActionRegistry()
        schema = _make_schema("search_action", with_required_param=True)
        registry.register(schema, _noop)
        assert registry.validate_call("search_action", {}) is False

    def test_validate_call_passes_with_required_present(self):
        registry = ActionRegistry()
        schema = _make_schema("search_action2", with_required_param=True)
        registry.register(schema, _noop)
        assert registry.validate_call("search_action2", {"query": "hello"}) is True

    def test_validate_call_unknown_action(self):
        registry = ActionRegistry()
        assert registry.validate_call("ghost_action", {"x": 1}) is False

    def test_overwrite_registration(self):
        registry = ActionRegistry()
        schema = _make_schema("dup_action")
        registry.register(schema, _noop)
        registry.register(schema, _failing)
        fn = registry.get_callable("dup_action")
        assert fn is _failing


# ---------------------------------------------------------------------------
# TestActionPlanner
# ---------------------------------------------------------------------------

class TestActionPlanner:
    def test_plan_returns_list(self):
        planner = ActionPlanner()
        schema = _make_schema("search_items")
        result = planner.plan("search for data", [schema])
        assert isinstance(result, list)

    def test_plan_each_step_has_required_keys(self):
        planner = ActionPlanner()
        schema = _make_schema("send_email")
        steps = planner.plan("send an email notification", [schema])
        for step in steps:
            assert "action_name" in step
            assert "args" in step
            assert "confidence" in step

    def test_plan_no_actions_returns_empty(self):
        planner = ActionPlanner()
        steps = planner.plan("do something", [])
        assert steps == []

    def test_plan_defaults_to_first_when_no_match(self):
        planner = ActionPlanner()
        schema = _make_schema("xyzzy_action")
        steps = planner.plan("completely unrelated request zzz", [schema])
        assert len(steps) >= 1
        assert steps[0]["action_name"] == "xyzzy_action"

    def test_plan_confidence_between_0_and_1(self):
        planner = ActionPlanner()
        schema = _make_schema("fetch_data")
        steps = planner.plan("fetch some data", [schema])
        for step in steps:
            assert 0.0 <= step["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# TestActionExecutor
# ---------------------------------------------------------------------------

class TestActionExecutor:
    def test_execute_returns_list_of_action_results(self):
        registry = ActionRegistry()
        schema = _make_schema("do_thing")
        registry.register(schema, _noop)
        executor = ActionExecutor()
        plan = [{"action_name": "do_thing", "args": {}, "confidence": 1.0}]
        results = executor.execute(plan, registry, timeout_s=5.0)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], ActionResult)

    def test_execute_success_result(self):
        registry = ActionRegistry()
        schema = _make_schema("success_action")
        registry.register(schema, lambda **kw: "done")
        executor = ActionExecutor()
        plan = [{"action_name": "success_action", "args": {}, "confidence": 0.9}]
        results = executor.execute(plan, registry)
        assert results[0].success is True

    def test_execute_unregistered_action_records_failure(self):
        registry = ActionRegistry()
        executor = ActionExecutor()
        plan = [{"action_name": "ghost_xyz", "args": {}, "confidence": 0.5}]
        results = executor.execute(plan, registry)
        assert len(results) == 1
        assert results[0].success is False

    def test_execute_multiple_steps(self):
        registry = ActionRegistry()
        for name in ("step_a", "step_b", "step_c"):
            registry.register(_make_schema(name), _noop)
        executor = ActionExecutor()
        plan = [
            {"action_name": "step_a", "args": {}, "confidence": 1.0},
            {"action_name": "step_b", "args": {}, "confidence": 1.0},
            {"action_name": "step_c", "args": {}, "confidence": 1.0},
        ]
        results = executor.execute(plan, registry)
        assert len(results) == 3

    def test_execute_empty_plan(self):
        registry = ActionRegistry()
        executor = ActionExecutor()
        results = executor.execute([], registry)
        assert results == []


# ---------------------------------------------------------------------------
# TestGlobalRegistry
# ---------------------------------------------------------------------------

class TestGlobalRegistry:
    def test_get_global_registry_returns_action_registry(self):
        reg = get_global_registry()
        assert isinstance(reg, ActionRegistry)

    def test_global_registry_is_stable(self):
        reg1 = get_global_registry()
        reg2 = get_global_registry()
        assert reg1 is reg2

    def test_global_registry_accepts_registration(self):
        reg = get_global_registry()
        name = f"global_test_{uuid.uuid4().hex[:6]}"
        reg.register(_make_schema(name), _noop)
        assert reg.get(name) is not None
