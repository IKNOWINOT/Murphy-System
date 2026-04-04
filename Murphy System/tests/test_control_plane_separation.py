"""Tests for control_plane_separation module."""

import sys
import os
import threading
import pytest

# Ensure the src package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.control_plane_separation import (
    ControlPlaneSeparation,
    PlaneType,
    RuntimeMode,
    PlaneHandler,
    PlaneRoutingResult,
    PLANNING_TASK_TYPES,
)


# ------------------------------------------------------------------
# Mode switching
# ------------------------------------------------------------------

class TestModeSwitching:
    def test_default_mode_is_balanced(self):
        cps = ControlPlaneSeparation()
        assert cps.get_mode() == RuntimeMode.BALANCED

    def test_init_with_strict(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.STRICT)
        assert cps.get_mode() == RuntimeMode.STRICT

    def test_set_mode_to_dynamic(self):
        cps = ControlPlaneSeparation()
        cps.set_mode(RuntimeMode.DYNAMIC)
        assert cps.get_mode() == RuntimeMode.DYNAMIC

    def test_set_mode_to_strict(self):
        cps = ControlPlaneSeparation()
        cps.set_mode(RuntimeMode.STRICT)
        assert cps.get_mode() == RuntimeMode.STRICT

    def test_mode_cycle(self):
        cps = ControlPlaneSeparation()
        for mode in (RuntimeMode.STRICT, RuntimeMode.DYNAMIC, RuntimeMode.BALANCED):
            cps.set_mode(mode)
            assert cps.get_mode() == mode


# ------------------------------------------------------------------
# Handler registration
# ------------------------------------------------------------------

class TestHandlerRegistration:
    def test_default_handlers_registered(self):
        cps = ControlPlaneSeparation()
        planning = cps.get_handlers(PlaneType.PLANNING)
        execution = cps.get_handlers(PlaneType.EXECUTION)
        assert len(planning) >= 1
        assert len(execution) >= 1
        assert planning[0].name == "default_planning_handler"
        assert execution[0].name == "default_execution_handler"

    def test_register_custom_handler(self):
        cps = ControlPlaneSeparation()
        hid = cps.register_handler(PlaneType.PLANNING, "custom", ["cap_a"])
        assert hid.startswith("planning-")
        handlers = cps.get_handlers(PlaneType.PLANNING)
        names = [h.name for h in handlers]
        assert "custom" in names

    def test_register_execution_handler(self):
        cps = ControlPlaneSeparation()
        hid = cps.register_handler(PlaneType.EXECUTION, "exec_custom", ["cap_x"])
        assert hid.startswith("execution-")

    def test_get_all_handlers(self):
        cps = ControlPlaneSeparation()
        all_h = cps.get_handlers()
        assert len(all_h) >= 2

    def test_handler_has_correct_fields(self):
        cps = ControlPlaneSeparation()
        h = cps.get_handlers(PlaneType.PLANNING)[0]
        assert isinstance(h, PlaneHandler)
        assert isinstance(h.handler_id, str)
        assert h.plane == PlaneType.PLANNING
        assert isinstance(h.capabilities, list)
        assert h.registered_at is not None


# ------------------------------------------------------------------
# Task routing — BALANCED mode
# ------------------------------------------------------------------

class TestBalancedRouting:
    def test_planning_task_types(self):
        cps = ControlPlaneSeparation()
        for tt in PLANNING_TASK_TYPES:
            result = cps.route_task(f"t-{tt}", tt)
            assert result.routed_to == PlaneType.PLANNING
            assert result.reason == "balanced_planning_type"

    def test_execution_task_type(self):
        cps = ControlPlaneSeparation()
        result = cps.route_task("t-exec", "policy_enforcement")
        assert result.routed_to == PlaneType.EXECUTION
        assert result.reason == "balanced_execution_type"

    def test_unknown_type_goes_to_execution(self):
        cps = ControlPlaneSeparation()
        result = cps.route_task("t-unk", "unknown_type")
        assert result.routed_to == PlaneType.EXECUTION


# ------------------------------------------------------------------
# Task routing — STRICT mode
# ------------------------------------------------------------------

class TestStrictRouting:
    def test_unapproved_goes_to_planning(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.STRICT)
        result = cps.route_task("t1", "policy_enforcement")
        assert result.routed_to == PlaneType.PLANNING
        assert result.reason == "strict_requires_approval"

    def test_approved_goes_to_execution(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.STRICT)
        result = cps.route_task("t2", "policy_enforcement", {"approved": True})
        assert result.routed_to == PlaneType.EXECUTION
        assert result.reason == "strict_approved"

    def test_approved_false_goes_to_planning(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.STRICT)
        result = cps.route_task("t3", "reasoning", {"approved": False})
        assert result.routed_to == PlaneType.PLANNING


# ------------------------------------------------------------------
# Task routing — DYNAMIC mode
# ------------------------------------------------------------------

class TestDynamicRouting:
    def test_high_confidence_to_execution(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.DYNAMIC)
        result = cps.route_task("t1", "reasoning", {"confidence": 0.99})
        assert result.routed_to == PlaneType.EXECUTION
        assert result.reason == "dynamic_high_confidence"

    def test_exact_threshold_to_execution(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.DYNAMIC)
        result = cps.route_task("t2", "reasoning", {"confidence": 0.95})
        assert result.routed_to == PlaneType.EXECUTION

    def test_low_confidence_to_planning(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.DYNAMIC)
        result = cps.route_task("t3", "reasoning", {"confidence": 0.5})
        assert result.routed_to == PlaneType.PLANNING
        assert result.reason == "dynamic_low_confidence"

    def test_no_confidence_to_planning(self):
        cps = ControlPlaneSeparation(mode=RuntimeMode.DYNAMIC)
        result = cps.route_task("t4", "reasoning")
        assert result.routed_to == PlaneType.PLANNING


# ------------------------------------------------------------------
# Routing history
# ------------------------------------------------------------------

class TestRoutingHistory:
    def test_history_recorded(self):
        cps = ControlPlaneSeparation()
        cps.route_task("t1", "reasoning")
        cps.route_task("t2", "policy_enforcement")
        history = cps.get_routing_history()
        assert len(history) == 2
        assert history[0]["task_id"] == "t1"
        assert history[1]["task_id"] == "t2"

    def test_history_limit(self):
        cps = ControlPlaneSeparation()
        for i in range(10):
            cps.route_task(f"t{i}", "reasoning")
        history = cps.get_routing_history(limit=3)
        assert len(history) == 3
        assert history[0]["task_id"] == "t7"

    def test_history_dict_keys(self):
        cps = ControlPlaneSeparation()
        cps.route_task("t1", "reasoning")
        entry = cps.get_routing_history()[0]
        assert set(entry.keys()) == {"task_id", "routed_to", "mode", "handler_id", "reason", "timestamp"}


# ------------------------------------------------------------------
# Fallback routing
# ------------------------------------------------------------------

class TestFallbackRouting:
    def test_fallback_when_no_planning_handlers(self):
        cps = ControlPlaneSeparation.__new__(ControlPlaneSeparation)
        cps._lock = threading.Lock()
        cps._mode = RuntimeMode.BALANCED
        cps._handlers = {}
        cps._routing_history = []
        # Register only an execution handler
        cps.register_handler(PlaneType.EXECUTION, "only_exec", ["audit_logging"])

        result = cps.route_task("t1", "reasoning")
        assert result.routed_to == PlaneType.EXECUTION
        assert result.reason == "fallback"

    def test_fallback_when_no_execution_handlers(self):
        cps = ControlPlaneSeparation.__new__(ControlPlaneSeparation)
        cps._lock = threading.Lock()
        cps._mode = RuntimeMode.BALANCED
        cps._handlers = {}
        cps._routing_history = []
        # Register only a planning handler
        cps.register_handler(PlaneType.PLANNING, "only_plan", ["reasoning"])

        result = cps.route_task("t1", "policy_enforcement")
        assert result.routed_to == PlaneType.PLANNING
        assert result.reason == "fallback"


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatus:
    def test_status_keys(self):
        cps = ControlPlaneSeparation()
        status = cps.get_status()
        assert set(status.keys()) == {
            "mode", "total_handlers", "planning_handlers",
            "execution_handlers", "total_routed_tasks",
        }

    def test_status_counts(self):
        cps = ControlPlaneSeparation()
        cps.route_task("t1", "reasoning")
        status = cps.get_status()
        assert status["mode"] == "balanced"
        assert status["total_handlers"] >= 2
        assert status["planning_handlers"] >= 1
        assert status["execution_handlers"] >= 1
        assert status["total_routed_tasks"] == 1


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_routing(self):
        cps = ControlPlaneSeparation()
        errors: list = []

        def route_batch(start: int):
            try:
                for i in range(50):
                    cps.route_task(f"t-{start + i}", "reasoning")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=route_batch, args=(i * 50,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        history = cps.get_routing_history(limit=200)
        assert len(history) == 200

    def test_concurrent_registration(self):
        cps = ControlPlaneSeparation()
        errors: list = []

        def register_batch(start: int):
            try:
                for i in range(20):
                    cps.register_handler(PlaneType.PLANNING, f"h-{start + i}", ["cap"])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_batch, args=(i * 20,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 2 defaults + 80 new
        assert len(cps.get_handlers()) == 82

    def test_concurrent_mode_switching(self):
        cps = ControlPlaneSeparation()
        errors: list = []

        def switch_modes():
            try:
                for mode in (RuntimeMode.STRICT, RuntimeMode.DYNAMIC, RuntimeMode.BALANCED):
                    cps.set_mode(mode)
                    cps.route_task("t", "reasoning")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=switch_modes) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
