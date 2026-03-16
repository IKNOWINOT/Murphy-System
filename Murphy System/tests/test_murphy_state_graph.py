"""
Murphy System - Tests for Murphy State Graph
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""
import os

import uuid
from datetime import datetime, timezone

import pytest

from murphy_state_graph import (
    GraphState,
    NodeType,
    GraphNode,
    GraphEdge,
    Checkpoint,
    CheckpointStore,
    HumanInTheLoop,
    BranchRouter,
    StateGraph,
    GraphRunner,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_id() -> str:
    return uuid.uuid4().hex[:8]


def _make_node(node_id: str = None, node_type: NodeType = NodeType.ACTION, handler=None) -> GraphNode:
    nid = node_id or _node_id()
    return GraphNode(node_id=nid, name=f"Node {nid}", node_type=node_type, handler=handler)


def _make_edge(from_node: str, to_node: str, condition=None) -> GraphEdge:
    return GraphEdge(
        edge_id=uuid.uuid4().hex[:8],
        from_node=from_node,
        to_node=to_node,
        condition=condition,
    )


def _passthrough_handler(state: GraphState) -> GraphState:
    return state


def _build_simple_graph() -> StateGraph:
    """Build a minimal start->action->end graph."""
    graph = StateGraph(graph_id=uuid.uuid4().hex[:8])

    start = _make_node("start", NodeType.START, handler=_passthrough_handler)
    action = _make_node("action", NodeType.ACTION, handler=lambda s: s)
    end = _make_node("end", NodeType.END, handler=_passthrough_handler)

    graph.add_node(start)
    graph.add_node(action)
    graph.add_node(end)

    graph.add_edge(_make_edge("start", "action"))
    graph.add_edge(_make_edge("action", "end"))

    graph.set_entry_point("start")
    return graph


# ---------------------------------------------------------------------------
# TestGraphState
# ---------------------------------------------------------------------------

class TestGraphState:
    def test_init_empty(self):
        state = GraphState()
        assert state.to_dict() == {}

    def test_init_with_data(self):
        state = GraphState(data={"x": 1, "y": "hello"})
        assert state.get("x") == 1
        assert state.get("y") == "hello"

    def test_set_and_get(self):
        state = GraphState()
        state.set("key1", 42)
        assert state.get("key1") == 42

    def test_get_missing_returns_default(self):
        state = GraphState()
        assert state.get("missing") is None
        assert state.get("missing", "fallback") == "fallback"

    def test_to_dict_returns_copy(self):
        state = GraphState(data={"a": 1})
        d = state.to_dict()
        d["b"] = 2
        assert "b" not in state.data

    def test_from_dict(self):
        d = {"name": "murphy", "score": 99}
        state = GraphState.from_dict(d)
        assert state.get("name") == "murphy"
        assert state.get("score") == 99

    def test_overwrite_key(self):
        state = GraphState(data={"val": 10})
        state.set("val", 20)
        assert state.get("val") == 20


# ---------------------------------------------------------------------------
# TestStateGraph
# ---------------------------------------------------------------------------

class TestStateGraph:
    def test_add_node(self):
        graph = StateGraph(graph_id="g1")
        node = _make_node("n1", NodeType.ACTION)
        graph.add_node(node)
        assert graph.get_node("n1") is node

    def test_add_edge(self):
        graph = StateGraph(graph_id="g2")
        graph.add_node(_make_node("a", NodeType.START))
        graph.add_node(_make_node("b", NodeType.END))
        edge = _make_edge("a", "b")
        graph.add_edge(edge)
        edges = graph.get_edges_from("a")
        assert any(e.to_node == "b" for e in edges)

    def test_set_entry_point(self):
        graph = StateGraph(graph_id="g3")
        graph.add_node(_make_node("start_node", NodeType.START))
        graph.set_entry_point("start_node")
        assert graph.entry_point == "start_node"

    def test_validate_valid_graph(self):
        graph = _build_simple_graph()
        errors = graph.validate()
        assert errors == []

    def test_validate_missing_entry_point(self):
        graph = StateGraph(graph_id="g_bad")
        errors = graph.validate()
        assert len(errors) > 0

    def test_get_node_missing_returns_none(self):
        graph = StateGraph(graph_id="g4")
        assert graph.get_node("nonexistent") is None


# ---------------------------------------------------------------------------
# TestCheckpointStore
# ---------------------------------------------------------------------------

class TestCheckpointStore:
    def _make_checkpoint(self, graph_id: str = "graph1") -> Checkpoint:
        return Checkpoint(
            checkpoint_id=uuid.uuid4().hex[:8],
            graph_id=graph_id,
            current_node="node_a",
            state={"step": 1},
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="running",
        )

    def test_save_and_load_in_memory(self):
        store = CheckpointStore()
        cp = self._make_checkpoint()
        store.save(cp)
        loaded = store.load(cp.checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_id == cp.checkpoint_id

    def test_load_missing_returns_none(self):
        store = CheckpointStore()
        assert store.load("no_such_id") is None

    def test_list_checkpoints_for_graph(self):
        store = CheckpointStore()
        gid = uuid.uuid4().hex[:8]
        cp1 = self._make_checkpoint(gid)
        cp2 = self._make_checkpoint(gid)
        store.save(cp1)
        store.save(cp2)
        cps = store.list_checkpoints(gid)
        ids = [c.checkpoint_id for c in cps]
        assert cp1.checkpoint_id in ids
        assert cp2.checkpoint_id in ids

    def test_save_to_disk(self, tmp_path):
        store = CheckpointStore(persistence_dir=str(tmp_path))
        cp = self._make_checkpoint()
        store.save(cp)
        loaded = store.load(cp.checkpoint_id)
        assert loaded is not None
        assert loaded.graph_id == cp.graph_id

    def test_checkpoint_to_dict_roundtrip(self):
        cp = self._make_checkpoint()
        d = cp.to_dict()
        restored = Checkpoint.from_dict(d)
        assert restored.checkpoint_id == cp.checkpoint_id
        assert restored.status == cp.status


# ---------------------------------------------------------------------------
# TestHumanInTheLoop
# ---------------------------------------------------------------------------

class TestHumanInTheLoop:
    def test_request_approval_returns_id(self):
        hitl = HumanInTheLoop()
        state = GraphState(data={"x": 1})
        approval_id = hitl.request_approval("node_1", state, {"reason": "needs review"})
        assert isinstance(approval_id, str)
        assert len(approval_id) > 0

    def test_check_approval_pending_returns_none(self):
        hitl = HumanInTheLoop()
        state = GraphState()
        approval_id = hitl.request_approval("node_2", state, {})
        result = hitl.check_approval(approval_id)
        assert result is None

    def test_approve(self):
        hitl = HumanInTheLoop()
        state = GraphState()
        approval_id = hitl.request_approval("node_3", state, {})
        hitl.approve(approval_id)
        assert hitl.check_approval(approval_id) is True

    def test_reject(self):
        hitl = HumanInTheLoop()
        state = GraphState()
        approval_id = hitl.request_approval("node_4", state, {})
        hitl.reject(approval_id)
        assert hitl.check_approval(approval_id) is False

    def test_check_unknown_id_returns_none(self):
        hitl = HumanInTheLoop()
        assert hitl.check_approval("unknown_approval_id") is None


# ---------------------------------------------------------------------------
# TestBranchRouter
# ---------------------------------------------------------------------------

class TestBranchRouter:
    def test_route_unconditional_edge(self):
        router = BranchRouter()
        state = GraphState(data={"score": 5})
        edges = [_make_edge("a", "b")]
        result = router.route(state, edges)
        assert result == "b"

    def test_route_conditional_true(self):
        router = BranchRouter()
        state = GraphState(data={"score": 10})
        edge = _make_edge("a", "b", condition=lambda s: s.get("score", 0) > 5)
        result = router.route(state, [edge])
        assert result == "b"

    def test_route_conditional_false(self):
        router = BranchRouter()
        state = GraphState(data={"score": 2})
        edge = _make_edge("a", "b", condition=lambda s: s.get("score", 0) > 5)
        result = router.route(state, [edge])
        assert result is None

    def test_route_no_edges_returns_none(self):
        router = BranchRouter()
        state = GraphState()
        result = router.route(state, [])
        assert result is None


# ---------------------------------------------------------------------------
# TestGraphRunner
# ---------------------------------------------------------------------------

class TestGraphRunner:
    def test_run_simple_three_node_graph(self):
        graph = _build_simple_graph()
        runner = GraphRunner(graph=graph)
        final = runner.run({"input": "hello"})
        assert isinstance(final, dict)
        assert final.get("_status") == "completed"

    def test_run_passes_initial_state(self):
        graph = _build_simple_graph()
        runner = GraphRunner(graph=graph)
        final = runner.run({"user_id": "abc123", "step": 0})
        assert final.get("user_id") == "abc123"

    def test_run_invalid_graph_raises(self):
        graph = StateGraph(graph_id="bad_graph")
        runner = GraphRunner(graph=graph)
        with pytest.raises(ValueError, match="validation"):
            runner.run({})

    def test_run_with_checkpoint_store(self, tmp_path):
        graph = _build_simple_graph()
        store = CheckpointStore(persistence_dir=str(tmp_path))
        runner = GraphRunner(graph=graph, checkpoint_store=store)
        final = runner.run({"data": "test"})
        assert final.get("_status") == "completed"
