"""
Tests for the SupervisionTree.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from supervision_tree import (
    ChildSpec,
    SupervisionStrategy,
    SupervisionTree,
    SupervisorNode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_restart_counter():
    """Return a list and a start_fn that appends to it on each call."""
    calls: list = []

    def start_fn() -> None:
        calls.append(1)

    return calls, start_fn


# ---------------------------------------------------------------------------
# ONE_FOR_ONE tests
# ---------------------------------------------------------------------------

class TestOneForOne:
    def test_one_for_one_restarts_only_failed(self):
        """ONE_FOR_ONE should restart the failed child only."""
        calls_a, fn_a = _make_restart_counter()
        calls_b, fn_b = _make_restart_counter()

        spec_a = ChildSpec("child_a", fn_a, max_restarts=3)
        spec_b = ChildSpec("child_b", fn_b, max_restarts=3)

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
        """After exceeding max_restarts, the restart should fail."""
        calls, fn = _make_restart_counter()
        spec = ChildSpec("child_x", fn, max_restarts=2, max_restart_window_sec=60.0)
        supervisor = SupervisorNode(
            supervisor_id=str(uuid.uuid4()),
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[spec],
        )
        tree = SupervisionTree()
        tree.register_supervisor(supervisor)

        # Exhaust the restart budget
        tree.handle_failure("child_x", RuntimeError("fail1"))
        tree.handle_failure("child_x", RuntimeError("fail2"))

        # Third failure should result in failed restart
        result = tree.handle_failure("child_x", RuntimeError("fail3"))
        assert result["restarts"].get("child_x") is False


# ---------------------------------------------------------------------------
# ONE_FOR_ALL tests
# ---------------------------------------------------------------------------

class TestOneForAll:
    def test_one_for_all_restarts_all_children(self):
        """ONE_FOR_ALL should restart every child when one fails."""
        calls_a, fn_a = _make_restart_counter()
        calls_b, fn_b = _make_restart_counter()
        calls_c, fn_c = _make_restart_counter()

        supervisor = SupervisorNode(
            supervisor_id=str(uuid.uuid4()),
            strategy=SupervisionStrategy.ONE_FOR_ALL,
            children=[
                ChildSpec("child_a", fn_a, max_restarts=5),
                ChildSpec("child_b", fn_b, max_restarts=5),
                ChildSpec("child_c", fn_c, max_restarts=5),
            ],
        )
        tree = SupervisionTree()
        tree.register_supervisor(supervisor)

        result = tree.handle_failure("child_b", ValueError("oops"))

        assert result["strategy"] == "one_for_all"
        assert result["restarts"].get("child_a") is True
        assert result["restarts"].get("child_b") is True
        assert result["restarts"].get("child_c") is True
        assert calls_a == [1]
        assert calls_b == [1]
        assert calls_c == [1]


# ---------------------------------------------------------------------------
# REST_FOR_ONE tests
# ---------------------------------------------------------------------------

class TestRestForOne:
    def test_rest_for_one_restarts_failed_and_later_children(self):
        """REST_FOR_ONE should restart the failed child and all subsequent ones."""
        calls_a, fn_a = _make_restart_counter()
        calls_b, fn_b = _make_restart_counter()
        calls_c, fn_c = _make_restart_counter()

        supervisor = SupervisorNode(
            supervisor_id=str(uuid.uuid4()),
            strategy=SupervisionStrategy.REST_FOR_ONE,
            children=[
                ChildSpec("child_a", fn_a, max_restarts=5),
                ChildSpec("child_b", fn_b, max_restarts=5),
                ChildSpec("child_c", fn_c, max_restarts=5),
            ],
        )
        tree = SupervisionTree()
        tree.register_supervisor(supervisor)

        result = tree.handle_failure("child_b", RuntimeError("crash"))

        assert result["strategy"] == "rest_for_one"
        # child_a comes before child_b → should NOT be restarted
        assert "child_a" not in result["restarts"]
        # child_b and child_c (after child_b) → should be restarted
        assert result["restarts"].get("child_b") is True
        assert result["restarts"].get("child_c") is True
        assert calls_a == []
        assert calls_b == [1]
        assert calls_c == [1]


# ---------------------------------------------------------------------------
# Unknown child / supervisor tests
# ---------------------------------------------------------------------------

class TestUnknownFailures:
    def test_handle_failure_unknown_child_escalates(self):
        """Failure of an unregistered child should be escalated."""
        tree = SupervisionTree()
        result = tree.handle_failure("unknown_child", RuntimeError("???"))
        assert result["escalated"] is True
        assert result["supervisor_id"] is None


# ---------------------------------------------------------------------------
# Tree status tests
# ---------------------------------------------------------------------------

class TestTreeStatus:
    def test_get_tree_status_includes_all_supervisors(self):
        """get_tree_status should include every registered supervisor."""
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
        """Children that have not been restarted should be reported as healthy."""
        _, fn = _make_restart_counter()
        sup = SupervisorNode(
            supervisor_id="sup_health",
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[ChildSpec("healthy_child", fn, max_restarts=3)],
        )
        tree = SupervisionTree()
        tree.register_supervisor(sup)

        status = tree.get_tree_status()
        children = status["sup_health"]["children"]
        assert len(children) == 1
        assert children[0]["child_id"] == "healthy_child"
        assert children[0]["healthy"] is True


# ---------------------------------------------------------------------------
# Hierarchy tests
# ---------------------------------------------------------------------------

class TestTreeHierarchy:
    def test_multi_level_supervision(self):
        """A two-level hierarchy should correctly route failures to the right supervisor."""
        calls_leaf, fn_leaf = _make_restart_counter()
        leaf_spec = ChildSpec("leaf_child", fn_leaf, max_restarts=5)

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
        """Adding then removing a child should update the supervisor's child list."""
        _, fn = _make_restart_counter()
        sup = SupervisorNode(
            supervisor_id="dynamic_sup",
            strategy=SupervisionStrategy.ONE_FOR_ONE,
            children=[],
        )
        tree = SupervisionTree()
        tree.register_supervisor(sup)

        spec = ChildSpec("dynamic_child", fn, max_restarts=3)
        sup.add_child(spec)
        assert any(c.child_id == "dynamic_child" for c in sup.children)

        sup.remove_child("dynamic_child")
        assert not any(c.child_id == "dynamic_child" for c in sup.children)
