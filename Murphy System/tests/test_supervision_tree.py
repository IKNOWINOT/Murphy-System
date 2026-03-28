"""
Tests for supervision_tree.py — ARCH-013.

Covers:
- ONE_FOR_ONE: only failed child restarts
- ONE_FOR_ALL: all siblings restart
- REST_FOR_ONE: failed + later siblings restart
- Max restart threshold triggers escalation
- Nested supervisor escalation chain
- Exponential backoff between restarts
- Thread safety (concurrent failures)
- Event publishing via EventBackbone
- SupervisionTreeBuilder fluent API
- Backward-compatible SupervisionTree / SupervisorNode / ChildSpec API

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest


from supervision_tree import (
    # New API
    ComponentStatus,
    RestartStrategy,
    Supervisor,
    SupervisedComponent,
    SupervisionPolicy,
    SupervisionTreeBuilder,
    # Legacy API (backward compat)
    ChildSpec,
    SupervisionStrategy,
    SupervisionTree,
    SupervisorNode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_component(
    component_id: str,
    fail_on_start: bool = False,
    component_type: str = "service",
) -> tuple[SupervisedComponent, list]:
    calls: list = []

    def start_fn() -> None:
        if fail_on_start:
            raise RuntimeError(f"{component_id} refused to start")
        calls.append("start")

    def stop_fn() -> None:
        calls.append("stop")

    def health_fn() -> bool:
        return True

    comp = SupervisedComponent(
        component_id=component_id,
        component_type=component_type,
        start_fn=start_fn,
        stop_fn=stop_fn,
        health_check_fn=health_fn,
    )
    return comp, calls


def _default_policy(**kwargs: Any) -> SupervisionPolicy:
    defaults = dict(
        strategy=RestartStrategy.ONE_FOR_ONE,
        max_restarts=3,
        time_window_sec=60.0,
        backoff_base_sec=0.0,  # no sleep in tests
        backoff_max_sec=0.0,
        escalate_after=5,
    )
    defaults.update(kwargs)
    return SupervisionPolicy(**defaults)


# ---------------------------------------------------------------------------
# ONE_FOR_ONE
# ---------------------------------------------------------------------------

class TestOneForOne:
    def test_one_for_one_restarts_only_failed(self):
        """ONE_FOR_ONE must restart the failing component only."""
        comp_a, calls_a = _make_component("a")
        comp_b, calls_b = _make_component("b")

        sup = Supervisor("sup1", _default_policy(strategy=RestartStrategy.ONE_FOR_ONE))
        sup.add_child(comp_a)
        sup.add_child(comp_b)

        result = sup.handle_failure("a", RuntimeError("boom"))

        assert result["strategy"] == "one_for_one"
        assert result["restarts"].get("a") is True
        assert "b" not in result["restarts"]
        assert calls_a == ["start"]
        assert calls_b == []

    def test_one_for_one_increments_restart_count(self):
        comp, _ = _make_component("c")
        sup = Supervisor("sup_cnt", _default_policy())
        sup.add_child(comp)

        sup.handle_failure("c", RuntimeError("x"))
        assert comp.restart_count == 1
        sup.handle_failure("c", RuntimeError("x"))
        assert comp.restart_count == 2

    def test_one_for_one_sets_status_running_on_success(self):
        comp, _ = _make_component("d")
        sup = Supervisor("sup_status", _default_policy())
        sup.add_child(comp)

        sup.handle_failure("d", RuntimeError("x"))
        assert comp.status == ComponentStatus.RUNNING


# ---------------------------------------------------------------------------
# ONE_FOR_ALL
# ---------------------------------------------------------------------------

class TestOneForAll:
    def test_one_for_all_restarts_every_sibling(self):
        """ONE_FOR_ALL must restart every component when one fails."""
        comp_a, calls_a = _make_component("a")
        comp_b, calls_b = _make_component("b")
        comp_c, calls_c = _make_component("c")

        policy = _default_policy(strategy=RestartStrategy.ONE_FOR_ALL)
        sup = Supervisor("sup_all", policy)
        for comp in (comp_a, comp_b, comp_c):
            sup.add_child(comp)

        result = sup.handle_failure("b", ValueError("oops"))

        assert result["strategy"] == "one_for_all"
        for cid in ("a", "b", "c"):
            assert result["restarts"].get(cid) is True
        assert calls_a == ["start"]
        assert calls_b == ["start"]
        assert calls_c == ["start"]


# ---------------------------------------------------------------------------
# REST_FOR_ONE
# ---------------------------------------------------------------------------

class TestRestForOne:
    def test_rest_for_one_restarts_failed_and_later(self):
        """REST_FOR_ONE must restart the failed component and all registered after it."""
        comp_a, calls_a = _make_component("a")
        comp_b, calls_b = _make_component("b")
        comp_c, calls_c = _make_component("c")

        policy = _default_policy(strategy=RestartStrategy.REST_FOR_ONE)
        sup = Supervisor("sup_rest", policy)
        for comp in (comp_a, comp_b, comp_c):
            sup.add_child(comp)

        result = sup.handle_failure("b", RuntimeError("crash"))

        assert result["strategy"] == "rest_for_one"
        assert "a" not in result["restarts"]
        assert result["restarts"].get("b") is True
        assert result["restarts"].get("c") is True
        assert calls_a == []
        assert calls_b == ["start"]
        assert calls_c == ["start"]

    def test_rest_for_one_first_component_fails(self):
        """If the first component fails, ALL must be restarted."""
        comps = [_make_component(str(i)) for i in range(4)]
        policy = _default_policy(strategy=RestartStrategy.REST_FOR_ONE)
        sup = Supervisor("sup_rest2", policy)
        for comp, _ in comps:
            sup.add_child(comp)

        result = sup.handle_failure("0", RuntimeError("first"))
        for i in range(4):
            assert result["restarts"].get(str(i)) is True


# ---------------------------------------------------------------------------
# Max restarts / escalation
# ---------------------------------------------------------------------------

class TestEscalation:
    def test_max_restarts_exceeded_escalates(self):
        """After max_restarts within the time window, the failure is escalated."""
        comp, _ = _make_component("e")
        policy = _default_policy(
            max_restarts=2,
            escalate_after=100,  # keep high so only budget triggers escalation
        )
        sup = Supervisor("sup_esc", policy)
        sup.add_child(comp)

        # Exhaust the budget
        sup.handle_failure("e", RuntimeError("f1"))
        sup.handle_failure("e", RuntimeError("f2"))

        # Third — budget exceeded
        result = sup.handle_failure("e", RuntimeError("f3"))
        assert result["escalated"] is True

    def test_escalate_after_consecutive_triggers_escalation(self):
        """When consecutive failures reach escalate_after, escalate even within budget."""
        comp, _ = _make_component("f")
        policy = _default_policy(
            max_restarts=100,  # budget never exhausted
            escalate_after=2,
        )
        sup = Supervisor("sup_consec", policy)
        sup.add_child(comp)

        sup.handle_failure("f", RuntimeError("f1"))
        result = sup.handle_failure("f", RuntimeError("f2"))
        assert result["escalated"] is True

    def test_escalation_to_parent_supervisor(self):
        """When a child supervisor exhausts its restarts, the failure escalates to parent."""
        comp, calls = _make_component("g")

        parent_policy = _default_policy(
            strategy=RestartStrategy.ONE_FOR_ONE,
            max_restarts=5,
            escalate_after=10,
        )
        parent = Supervisor("parent", parent_policy)
        parent.add_child(comp)

        child_policy = _default_policy(
            max_restarts=1,
            escalate_after=10,
        )
        child = Supervisor("child", child_policy, parent=parent)
        # Register the component also in child so the child can find it
        comp2, calls2 = _make_component("g2")
        child.add_child(comp2)

        # Exhaust child's budget for g2
        child.handle_failure("g2", RuntimeError("c1"))

        # Second failure: budget exhausted, escalates to parent
        # Parent doesn't know about g2, so escalation returns escalated=True from parent
        result = child.handle_failure("g2", RuntimeError("c2"))
        assert result["escalated"] is True

    def test_critical_state_set_when_no_parent(self):
        """With no parent, a supervisor must enter CRITICAL state."""
        comp, _ = _make_component("h")
        policy = _default_policy(max_restarts=1, escalate_after=10)
        sup = Supervisor("sup_crit", policy)
        sup.add_child(comp)

        sup.handle_failure("h", RuntimeError("c1"))  # uses budget
        sup.handle_failure("h", RuntimeError("c2"))  # exceeds budget
        assert sup._critical is True

    def test_unknown_component_escalates(self):
        """Failure of an unregistered component must be marked as escalated."""
        sup = Supervisor("sup_unk", _default_policy())
        result = sup.handle_failure("unknown", RuntimeError("???"))
        assert result["escalated"] is True


# ---------------------------------------------------------------------------
# Exponential backoff
# ---------------------------------------------------------------------------

class TestBackoff:
    def test_backoff_increases_with_restart_count(self):
        """_compute_backoff should return increasing values as restart history grows."""
        policy = SupervisionPolicy(
            strategy=RestartStrategy.ONE_FOR_ONE,
            max_restarts=10,
            time_window_sec=60.0,
            backoff_base_sec=1.0,
            backoff_max_sec=30.0,
            escalate_after=20,
        )
        sup = Supervisor("sup_back", policy)
        comp, _ = _make_component("back")
        sup.add_child(comp)

        # 0 restarts → backoff 0
        assert sup._compute_backoff("back") == 0.0

        # Inject fake history entries
        now = time.monotonic()
        sup._restart_history["back"] = [now - 1]
        assert sup._compute_backoff("back") == 1.0  # base * 2^0

        sup._restart_history["back"] = [now - 2, now - 1]
        assert sup._compute_backoff("back") == 2.0  # base * 2^1

    def test_backoff_capped_at_max(self):
        """Backoff must never exceed backoff_max_sec."""
        policy = SupervisionPolicy(
            strategy=RestartStrategy.ONE_FOR_ONE,
            max_restarts=100,
            time_window_sec=3600.0,
            backoff_base_sec=1.0,
            backoff_max_sec=5.0,
            escalate_after=200,
        )
        sup = Supervisor("sup_cap", policy)
        comp, _ = _make_component("cap")
        sup.add_child(comp)

        now = time.monotonic()
        # 10 recent restarts → raw = 1 * 2^9 = 512 → capped at 5
        sup._restart_history["cap"] = [now - i for i in range(10)]
        assert sup._compute_backoff("cap") == 5.0

    def test_backoff_sleep_is_called(self):
        """handle_failure should sleep for the computed backoff."""
        policy = SupervisionPolicy(
            strategy=RestartStrategy.ONE_FOR_ONE,
            max_restarts=10,
            time_window_sec=60.0,
            backoff_base_sec=1.0,
            backoff_max_sec=30.0,
            escalate_after=20,
        )
        sup = Supervisor("sup_sleep", policy)
        comp, _ = _make_component("sl")
        sup.add_child(comp)

        # Pre-populate history so backoff > 0
        now = time.monotonic()
        sup._restart_history["sl"] = [now - 0.5]

        with patch("supervision_tree.time.sleep") as mock_sleep:
            sup.handle_failure("sl", RuntimeError("x"))
            mock_sleep.assert_called_once()
            args = mock_sleep.call_args[0]
            assert args[0] > 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_failures_do_not_corrupt_state(self):
        """Multiple threads reporting failures concurrently must not corrupt state."""
        comp, _ = _make_component("thread_comp")
        policy = _default_policy(
            strategy=RestartStrategy.ONE_FOR_ONE,
            max_restarts=50,
            escalate_after=100,
        )
        sup = Supervisor("sup_thread", policy)
        sup.add_child(comp)

        errors: list = []

        def fail_and_handle():
            try:
                sup.handle_failure("thread_comp", RuntimeError("concurrent"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=fail_and_handle) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert comp.restart_count > 0


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------

class TestEventPublishing:
    def _make_backbone(self) -> tuple[Any, list]:
        events: list = []
        backbone = MagicMock()
        backbone.publish_event.side_effect = lambda e: events.append(e)
        return backbone, events

    def test_restarted_event_published(self):
        """SUPERVISOR_CHILD_RESTARTED event must be published on each restart."""
        backbone, events = self._make_backbone()
        comp, _ = _make_component("ev_comp")
        policy = _default_policy()
        sup = Supervisor("sup_ev", policy, event_backbone=backbone)
        sup.add_child(comp)

        sup.handle_failure("ev_comp", RuntimeError("x"))
        backbone.publish_event.assert_called()

    def test_started_event_published_on_start_all(self):
        """SUPERVISOR_CHILD_STARTED event must be published when start_all is called."""
        backbone, events = self._make_backbone()
        comp, _ = _make_component("ev_start")
        policy = _default_policy()
        sup = Supervisor("sup_ev_start", policy, event_backbone=backbone)
        sup.add_child(comp)

        sup.start_all()
        backbone.publish_event.assert_called()

    def test_stopped_event_published_on_stop_all(self):
        """SUPERVISOR_CHILD_STOPPED event must be published when stop_all is called."""
        backbone, events = self._make_backbone()
        comp, _ = _make_component("ev_stop")
        comp.status = ComponentStatus.RUNNING

        policy = _default_policy()
        sup = Supervisor("sup_ev_stop", policy, event_backbone=backbone)
        sup.add_child(comp)

        sup.stop_all()
        backbone.publish_event.assert_called()

    def test_critical_event_published(self):
        """SUPERVISOR_CRITICAL event must be published when entering critical state."""
        backbone, events = self._make_backbone()
        comp, _ = _make_component("ev_crit")
        policy = _default_policy(max_restarts=1, escalate_after=100)
        sup = Supervisor("sup_ev_crit", policy, event_backbone=backbone)
        sup.add_child(comp)

        sup.handle_failure("ev_crit", RuntimeError("c1"))
        sup.handle_failure("ev_crit", RuntimeError("c2"))
        # Should have triggered SUPERVISOR_CRITICAL
        assert backbone.publish_event.called


# ---------------------------------------------------------------------------
# SupervisionTreeBuilder fluent API
# ---------------------------------------------------------------------------

class TestSupervisionTreeBuilder:
    def test_builder_creates_supervisor_with_strategy(self):
        """Builder must create a root Supervisor with the configured strategy."""
        root = (
            SupervisionTreeBuilder("root")
            .with_strategy(RestartStrategy.ONE_FOR_ALL)
            .build()
        )
        assert root.supervisor_id == "root"
        assert root.policy.strategy == RestartStrategy.ONE_FOR_ALL

    def test_builder_add_child(self):
        """Builder.add_child must register a SupervisedComponent."""
        root = (
            SupervisionTreeBuilder("root")
            .with_strategy(RestartStrategy.ONE_FOR_ONE)
            .add_child(
                "svc",
                start_fn=lambda: None,
                stop_fn=lambda: None,
                health_fn=lambda: True,
            )
            .build()
        )
        assert len(root._components) == 1
        assert root._components[0].component_id == "svc"

    def test_builder_add_supervisor_creates_child(self):
        """Builder.add_supervisor must attach a nested Supervisor."""
        root = (
            SupervisionTreeBuilder("root")
            .with_strategy(RestartStrategy.ONE_FOR_ONE)
            .add_supervisor(
                "child_sup",
                strategy=RestartStrategy.REST_FOR_ONE,
            )
            .build()
        )
        assert len(root._child_supervisors) == 1
        assert root._child_supervisors[0].supervisor_id == "child_sup"
        assert root._child_supervisors[0].policy.strategy == RestartStrategy.REST_FOR_ONE

    def test_builder_child_supervisor_parent_is_root(self):
        """Child supervisor built via builder must have root as its parent."""
        root = (
            SupervisionTreeBuilder("root")
            .add_supervisor("child_sup")
            .build()
        )
        assert root._child_supervisors[0].parent is root

    def test_builder_with_policy(self):
        """Builder.with_policy must apply all policy fields."""
        policy = SupervisionPolicy(
            strategy=RestartStrategy.REST_FOR_ONE,
            max_restarts=7,
            time_window_sec=120.0,
            backoff_base_sec=2.0,
            backoff_max_sec=60.0,
            escalate_after=4,
        )
        root = SupervisionTreeBuilder("root").with_policy(policy).build()
        assert root.policy.max_restarts == 7
        assert root.policy.backoff_base_sec == 2.0

    def test_builder_full_tree(self):
        """A full multi-level tree can be built and start_all succeeds."""
        comp_a, calls_a = _make_component("a")
        comp_b, calls_b = _make_component("b")

        root = (
            SupervisionTreeBuilder("root")
            .with_strategy(RestartStrategy.ONE_FOR_ONE)
            .add_child(
                "a",
                start_fn=comp_a.start_fn,
                stop_fn=comp_a.stop_fn,
                health_fn=comp_a.health_check_fn,
            )
            .add_supervisor(
                "child_sup",
                strategy=RestartStrategy.ONE_FOR_ALL,
                children=[comp_b],
            )
            .build()
        )
        root.start_all()
        assert calls_a == ["start"]
        assert calls_b == ["start"]

    def test_builder_get_tree_status(self):
        """get_tree_status must include all components and child supervisors."""
        root = (
            SupervisionTreeBuilder("root")
            .with_strategy(RestartStrategy.ONE_FOR_ONE)
            .add_child("svc", lambda: None, lambda: None, lambda: True)
            .add_supervisor("child_sup", strategy=RestartStrategy.REST_FOR_ONE)
            .build()
        )
        status = root.get_tree_status()
        assert status["supervisor_id"] == "root"
        assert len(status["components"]) == 1
        assert status["components"][0]["component_id"] == "svc"
        assert len(status["child_supervisors"]) == 1
        assert status["child_supervisors"][0]["supervisor_id"] == "child_sup"


# ---------------------------------------------------------------------------
# Nested supervisor escalation chain
# ---------------------------------------------------------------------------

class TestNestedEscalation:
    def test_two_level_escalation_chain(self):
        """
        When a child supervisor exhausts its budget, the failure should
        escalate to the grandparent (root).
        """
        grandparent_calls: list = []

        def gp_start():
            grandparent_calls.append("start")

        gp_comp = SupervisedComponent(
            component_id="gp_comp",
            component_type="service",
            start_fn=gp_start,
            stop_fn=lambda: None,
            health_check_fn=lambda: True,
        )

        root_policy = _default_policy(max_restarts=5, escalate_after=10)
        root = Supervisor("root", root_policy)
        root.add_child(gp_comp)

        child_policy = _default_policy(max_restarts=1, escalate_after=10)
        child_comp, _ = _make_component("child_comp")
        child = Supervisor("child", child_policy, parent=root)
        child.add_child(child_comp)

        # First failure — within budget
        result1 = child.handle_failure("child_comp", RuntimeError("f1"))
        assert not result1["escalated"]

        # Second failure — budget exhausted, escalates to root
        # Root doesn't know child_comp, so it returns escalated
        result2 = child.handle_failure("child_comp", RuntimeError("f2"))
        assert result2["escalated"] is True


# ---------------------------------------------------------------------------
# Start/stop lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_start_all_calls_start_fn_for_each_component(self):
        comps = [_make_component(str(i)) for i in range(3)]
        sup = Supervisor("sup_lc", _default_policy())
        for comp, _ in comps:
            sup.add_child(comp)

        sup.start_all()
        for comp, calls in comps:
            assert calls == ["start"]
            assert comp.status == ComponentStatus.RUNNING

    def test_stop_all_calls_stop_fn_in_reverse_order(self):
        stop_order: list = []
        comps = []
        for i in range(3):
            cid = str(i)
            captured_id = cid

            def make_stop(cid=captured_id):
                def stop_fn():
                    stop_order.append(cid)
                return stop_fn

            comp = SupervisedComponent(
                component_id=cid,
                component_type="service",
                start_fn=lambda: None,
                stop_fn=make_stop(),
                health_check_fn=lambda: True,
            )
            comps.append(comp)

        sup = Supervisor("sup_stop", _default_policy())
        for comp in comps:
            sup.add_child(comp)

        sup.stop_all()
        assert stop_order == ["2", "1", "0"]

    def test_start_fn_failure_sets_failed_status(self):
        comp, _ = _make_component("fail_start", fail_on_start=True)
        sup = Supervisor("sup_fail_start", _default_policy())
        sup.add_child(comp)

        sup.start_all()
        assert comp.status == ComponentStatus.FAILED


# ---------------------------------------------------------------------------
# Backward-compatible SupervisionTree / SupervisorNode / ChildSpec tests
# ---------------------------------------------------------------------------

class TestLegacyOneForOne:
    def test_one_for_one_restarts_only_failed(self):
        calls_a: list = []
        calls_b: list = []
        spec_a = ChildSpec("child_a", lambda: calls_a.append(1), max_restarts=3)
        spec_b = ChildSpec("child_b", lambda: calls_b.append(1), max_restarts=3)
        supervisor = SupervisorNode(
            supervisor_id=str(uuid.uuid4()),
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[spec_a, spec_b],
        )
        tree = SupervisionTree()
        tree.register_supervisor(supervisor)
        result = tree.handle_failure("child_a", RuntimeError("boom"))
        assert result["strategy"] == "one_for_one"
        assert result["restarts"]["child_a"] is True
        assert "child_b" not in result["restarts"]
        assert calls_a == [1]
        assert calls_b == []

    def test_one_for_one_max_restarts_exceeded(self):
        calls: list = []
        spec = ChildSpec("child_x", lambda: calls.append(1), max_restarts=2,
                         max_restart_window_sec=60.0)
        supervisor = SupervisorNode(
            supervisor_id=str(uuid.uuid4()),
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[spec],
        )
        tree = SupervisionTree()
        tree.register_supervisor(supervisor)
        tree.handle_failure("child_x", RuntimeError("fail1"))
        tree.handle_failure("child_x", RuntimeError("fail2"))
        result = tree.handle_failure("child_x", RuntimeError("fail3"))
        assert result["restarts"].get("child_x") is False


class TestLegacyOneForAll:
    def test_one_for_all_restarts_all_children(self):
        calls: dict = {"a": [], "b": [], "c": []}
        supervisor = SupervisorNode(
            supervisor_id=str(uuid.uuid4()),
            strategy=SupervisionStrategy.ONE_FOR_ALL,
            children=[
                ChildSpec("child_a", lambda: calls["a"].append(1), max_restarts=5),
                ChildSpec("child_b", lambda: calls["b"].append(1), max_restarts=5),
                ChildSpec("child_c", lambda: calls["c"].append(1), max_restarts=5),
            ],
        )
        tree = SupervisionTree()
        tree.register_supervisor(supervisor)
        result = tree.handle_failure("child_b", ValueError("oops"))
        assert result["strategy"] == "one_for_all"
        for key in ("child_a", "child_b", "child_c"):
            assert result["restarts"].get(key) is True


class TestLegacyRestForOne:
    def test_rest_for_one_restarts_failed_and_later_children(self):
        calls: dict = {"a": [], "b": [], "c": []}
        supervisor = SupervisorNode(
            supervisor_id=str(uuid.uuid4()),
            strategy=SupervisionStrategy.REST_FOR_ONE,
            children=[
                ChildSpec("child_a", lambda: calls["a"].append(1), max_restarts=5),
                ChildSpec("child_b", lambda: calls["b"].append(1), max_restarts=5),
                ChildSpec("child_c", lambda: calls["c"].append(1), max_restarts=5),
            ],
        )
        tree = SupervisionTree()
        tree.register_supervisor(supervisor)
        result = tree.handle_failure("child_b", RuntimeError("crash"))
        assert result["strategy"] == "rest_for_one"
        assert "child_a" not in result["restarts"]
        assert result["restarts"].get("child_b") is True
        assert result["restarts"].get("child_c") is True


class TestLegacyUnknown:
    def test_handle_failure_unknown_child_escalates(self):
        tree = SupervisionTree()
        result = tree.handle_failure("unknown_child", RuntimeError("???"))
        assert result["escalated"] is True
        assert result["supervisor_id"] is None


class TestLegacyTreeStatus:
    def test_get_tree_status_includes_all_supervisors(self):
        sup1 = SupervisorNode(
            supervisor_id="sup1",
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[ChildSpec("c1", lambda: None, max_restarts=3)],
        )
        sup2 = SupervisorNode(
            supervisor_id="sup2",
            strategy=SupervisionStrategy.ONE_FOR_ALL,
            children=[ChildSpec("c2", lambda: None, max_restarts=3)],
            parent_id="sup1",
        )
        tree = SupervisionTree()
        tree.register_supervisor(sup1)
        tree.register_supervisor(sup2)
        status = tree.get_tree_status()
        assert "sup1" in status
        assert "sup2" in status
        assert status["sup1"]["strategy"] == "one_for_one"
        assert status["sup2"]["parent_id"] == "sup1"

    def test_get_tree_status_children_healthy(self):
        sup = SupervisorNode(
            supervisor_id="sup_health",
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[ChildSpec("healthy_child", lambda: None, max_restarts=3)],
        )
        tree = SupervisionTree()
        tree.register_supervisor(sup)
        status = tree.get_tree_status()
        children = status["sup_health"]["children"]
        assert len(children) == 1
        assert children[0]["child_id"] == "healthy_child"
        assert children[0]["healthy"] is True


class TestLegacyHierarchy:
    def test_multi_level_supervision(self):
        calls_leaf: list = []
        leaf_spec = ChildSpec("leaf_child", lambda: calls_leaf.append(1), max_restarts=5)
        child_supervisor = SupervisorNode(
            supervisor_id="child_sup",
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[leaf_spec],
            parent_id="root_sup",
        )
        root_supervisor = SupervisorNode(
            supervisor_id="root_sup",
            strategy=SupervisionStrategy.ONE_FOR_ALL,
            children=[],
        )
        tree = SupervisionTree()
        tree.register_supervisor(root_supervisor)
        tree.register_supervisor(child_supervisor)
        result = tree.handle_failure("leaf_child", RuntimeError("leaf crashed"))
        assert result["supervisor_id"] == "child_sup"
        assert result["restarts"]["leaf_child"] is True
        assert calls_leaf == [1]

    def test_add_and_remove_child(self):
        sup = SupervisorNode(
            supervisor_id="dynamic_sup",
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[],
        )
        tree = SupervisionTree()
        tree.register_supervisor(sup)
        spec = ChildSpec("dynamic_child", lambda: None, max_restarts=3)
        sup.add_child(spec)
        assert any(c.child_id == "dynamic_child" for c in sup.children)
        sup.remove_child("dynamic_child")
        assert not any(c.child_id == "dynamic_child" for c in sup.children)
