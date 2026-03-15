"""
Tests for Layer 1 — ContextObject, ContextGraph, and ContextEngine.
"""

import pytest
from pydantic import ValidationError

from aionmind.models.context_object import ContextObject, Priority, RiskLevel
from aionmind.models.context_graph import (
    ContextGraph,
    ContextNode,
    ContextEdge,
    NodeType,
    EdgeType,
)
from aionmind.context_engine import ContextEngine


class TestContextObject:
    """ContextObject creation and validation."""

    def test_minimal_creation(self):
        ctx = ContextObject(source="test")
        assert ctx.source == "test"
        assert ctx.context_id  # auto-generated UUID
        assert ctx.priority == Priority.MEDIUM
        assert ctx.risk_level == RiskLevel.LOW
        assert ctx.related_tasks == []
        assert ctx.metadata == {}

    def test_full_creation(self):
        ctx = ContextObject(
            source="user_query",
            intent="deploy",
            priority=Priority.HIGH,
            risk_level=RiskLevel.CRITICAL,
            related_tasks=["t1", "t2"],
            workflow_refs=["wf1"],
            memory_refs=["mem1"],
            constraints=["no downtime"],
            evidence_refs=["ev1"],
            assumptions=["a1"],
            risks=["r1"],
            raw_input="Deploy v2 to production",
            metadata={"region": "us-east-1"},
        )
        assert ctx.intent == "deploy"
        assert len(ctx.related_tasks) == 2
        assert ctx.risk_level == RiskLevel.CRITICAL

    def test_source_is_required(self):
        with pytest.raises(ValidationError):
            ContextObject()  # missing 'source'

    def test_context_is_informational_only(self):
        """ContextObject is informational — it has no execute method."""
        ctx = ContextObject(source="test")
        assert not hasattr(ctx, "execute")
        assert not hasattr(ctx, "run")


class TestContextGraph:
    """ContextGraph creation and query helpers."""

    def test_empty_graph(self):
        g = ContextGraph(context_id="ctx-1")
        assert len(g.nodes) == 0
        assert len(g.edges) == 0

    def test_add_nodes_and_edges(self):
        g = ContextGraph(context_id="ctx-1")
        n1 = ContextNode(node_id="n1", node_type=NodeType.TASK, label="task-a")
        n2 = ContextNode(node_id="n2", node_type=NodeType.WORKFLOW, label="wf-a")
        g.add_node(n1)
        g.add_node(n2)
        e = ContextEdge(source_id="n1", target_id="n2", edge_type=EdgeType.DEPENDS_ON)
        g.add_edge(e)
        assert len(g.nodes) == 2
        assert len(g.edges) == 1

    def test_get_node(self):
        g = ContextGraph(context_id="ctx-1")
        n = ContextNode(node_id="abc", node_type=NodeType.TASK)
        g.add_node(n)
        assert g.get_node("abc") is n
        assert g.get_node("missing") is None

    def test_get_edges_from_and_to(self):
        g = ContextGraph(context_id="ctx-1")
        g.add_node(ContextNode(node_id="a", node_type=NodeType.TASK))
        g.add_node(ContextNode(node_id="b", node_type=NodeType.TASK))
        g.add_edge(ContextEdge(source_id="a", target_id="b", edge_type=EdgeType.RELATED_TO))
        assert len(g.get_edges_from("a")) == 1
        assert len(g.get_edges_to("b")) == 1
        assert len(g.get_edges_from("b")) == 0


class TestContextEngine:
    """ContextEngine build_context and build_graph."""

    def test_build_context(self):
        engine = ContextEngine()
        ctx = engine.build_context(source="user", raw_input="hello", intent="greet")
        assert isinstance(ctx, ContextObject)
        assert ctx.source == "user"
        assert ctx.intent == "greet"

    def test_build_graph_creates_nodes_for_refs(self):
        engine = ContextEngine()
        ctx = engine.build_context(
            source="test",
            related_tasks=["t1"],
            workflow_refs=["wf1"],
            memory_refs=["m1"],
            evidence_refs=["e1"],
            constraints=["be safe"],
        )
        graph = engine.build_graph(ctx)
        assert isinstance(graph, ContextGraph)
        assert graph.context_id == ctx.context_id
        # 1 root + 1 task + 1 workflow + 1 memory + 1 evidence + 1 constraint = 6
        assert len(graph.nodes) == 6
        assert len(graph.edges) == 5  # edges linking them to root

    def test_build_graph_empty_context(self):
        engine = ContextEngine()
        ctx = engine.build_context(source="empty")
        graph = engine.build_graph(ctx)
        assert len(graph.nodes) == 1  # root only
        assert len(graph.edges) == 0
