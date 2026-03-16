# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for knowledge_graph_builder — KGB-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable KGBRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from knowledge_graph_builder import (  # noqa: E402
    EdgeKind,
    GraphEdge,
    GraphNode,
    GraphStats,
    GraphStatus,
    KnowledgeGraphEngine,
    NodeKind,
    QueryResult,
    SubgraphResult,
    TraversalMode,
    TraversalResult,
    create_knowledge_graph_api,
    gate_kgb_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class KGBRecord:
    """One KGB check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[KGBRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    *,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> None:
    passed = expected == actual
    _RESULTS.append(
        KGBRecord(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    assert passed, (
        f"[{check_id}] {description}: expected={expected!r}, got={actual!r}"
    )


# -- Helpers ---------------------------------------------------------------


def _make_engine() -> KnowledgeGraphEngine:
    return KnowledgeGraphEngine(max_history=500)


def _make_triangle(eng: KnowledgeGraphEngine) -> tuple:
    """Create a triangle graph: A -> B -> C -> A."""
    a = eng.add_node("Alpha", kind="entity", tags=["core"])
    b = eng.add_node("Beta", kind="concept", tags=["core"])
    c = eng.add_node("Gamma", kind="event", tags=["aux"])
    e1 = eng.add_edge(a.node_id, b.node_id, "knows", kind="relates_to")
    e2 = eng.add_edge(b.node_id, c.node_id, "causes", kind="causes")
    e3 = eng.add_edge(c.node_id, a.node_id, "triggers", kind="triggers")
    return a, b, c, e1, e2, e3


# ==========================================================================
# Tests
# ==========================================================================


class TestNodeCRUD:
    """Node create / read / update / delete."""

    def test_add_node(self) -> None:
        eng = _make_engine()
        n = eng.add_node("Server-1", kind="resource", tags=["infra"])
        record(
            "KGB-001", "add_node returns GraphNode",
            True, isinstance(n, GraphNode),
            cause="add_node called",
            effect="GraphNode returned",
            lesson="Factory must return typed node",
        )
        assert n.label == "Server-1"
        assert n.kind == "resource"

    def test_add_node_defaults(self) -> None:
        eng = _make_engine()
        n = eng.add_node("Default")
        record(
            "KGB-002", "add_node uses default kind=entity",
            "entity", n.kind,
            cause="no kind specified",
            effect="defaults to entity",
            lesson="Defaults must be sensible",
        )

    def test_get_node(self) -> None:
        eng = _make_engine()
        n = eng.add_node("Lookup")
        got = eng.get_node(n.node_id)
        record(
            "KGB-003", "get_node returns correct node",
            n.node_id, got.node_id if got else None,
            cause="get by ID",
            effect="returns same node",
            lesson="Lookup must return existing nodes",
        )

    def test_get_node_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_node("nonexistent")
        record(
            "KGB-004", "get_node returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing nodes return None gracefully",
        )

    def test_update_node(self) -> None:
        eng = _make_engine()
        n = eng.add_node("Original")
        updated = eng.update_node(n.node_id, label="Updated", kind="concept")
        record(
            "KGB-005", "update_node changes fields",
            "Updated", updated.label if updated else None,
            cause="label changed via update",
            effect="node label updated",
            lesson="Updates must persist",
        )
        assert updated.kind == "concept"

    def test_update_node_tags(self) -> None:
        eng = _make_engine()
        n = eng.add_node("Tagged", tags=["old"])
        updated = eng.update_node(n.node_id, tags=["new", "fresh"])
        record(
            "KGB-006", "update_node replaces tags",
            ["new", "fresh"], updated.tags if updated else [],
            cause="tags replaced",
            effect="new tags stored",
            lesson="Tag updates replace entirely",
        )

    def test_update_node_missing(self) -> None:
        eng = _make_engine()
        result = eng.update_node("missing", label="nope")
        record(
            "KGB-007", "update_node returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing nodes cannot be updated",
        )

    def test_delete_node(self) -> None:
        eng = _make_engine()
        n = eng.add_node("ToDelete")
        ok = eng.delete_node(n.node_id)
        record(
            "KGB-008", "delete_node returns True",
            True, ok,
            cause="node deleted",
            effect="returns True",
            lesson="Deletion returns success bool",
        )
        assert eng.get_node(n.node_id) is None

    def test_delete_node_cascades_edges(self) -> None:
        eng = _make_engine()
        a, b, _, e1, _, _ = _make_triangle(eng)
        eng.delete_node(a.node_id)
        record(
            "KGB-009", "delete_node removes connected edges",
            True, eng.get_edge(e1.edge_id) is None,
            cause="node with edges deleted",
            effect="connected edges removed",
            lesson="Node deletion must cascade to edges",
        )

    def test_delete_node_missing(self) -> None:
        eng = _make_engine()
        ok = eng.delete_node("nonexistent")
        record(
            "KGB-010", "delete_node returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="returns False",
            lesson="Missing node deletion is idempotent",
        )

    def test_node_to_dict(self) -> None:
        eng = _make_engine()
        n = eng.add_node("Serialise", kind="metric", tags=["test"])
        d = n.to_dict()
        record(
            "KGB-011", "node to_dict contains label",
            "Serialise", d["label"],
            cause="to_dict called",
            effect="dict returned with label",
            lesson="Serialisation must include all fields",
        )
        assert "node_id" in d
        assert "created_at" in d

    def test_add_node_with_properties(self) -> None:
        eng = _make_engine()
        n = eng.add_node("Props", properties={"cpu": 4, "ram": "16GB"})
        record(
            "KGB-012", "add_node stores properties",
            4, n.properties.get("cpu"),
            cause="properties provided",
            effect="properties stored",
            lesson="Properties must be preserved",
        )


class TestEdgeCRUD:
    """Edge create / read / delete."""

    def test_add_edge(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(a.node_id, b.node_id, "connects")
        record(
            "KGB-013", "add_edge returns GraphEdge",
            True, isinstance(e, GraphEdge),
            cause="add_edge called",
            effect="GraphEdge returned",
            lesson="Factory must return typed edge",
        )
        assert e.label == "connects"

    def test_add_edge_missing_source(self) -> None:
        eng = _make_engine()
        b = eng.add_node("B")
        e = eng.add_edge("missing", b.node_id, "broken")
        record(
            "KGB-014", "add_edge returns None for missing source",
            True, e is None,
            cause="source node missing",
            effect="None returned",
            lesson="Edges require valid endpoints",
        )

    def test_add_edge_missing_target(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        e = eng.add_edge(a.node_id, "missing", "broken")
        record(
            "KGB-015", "add_edge returns None for missing target",
            True, e is None,
            cause="target node missing",
            effect="None returned",
            lesson="Edges require valid endpoints",
        )

    def test_add_edge_with_weight(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(a.node_id, b.node_id, "heavy", weight=9.5)
        record(
            "KGB-016", "add_edge stores weight",
            9.5, e.weight if e else 0,
            cause="weight provided",
            effect="weight stored",
            lesson="Edge weights must be preserved",
        )

    def test_add_edge_with_kind_enum(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(a.node_id, b.node_id, "dep", kind=EdgeKind.depends_on)
        record(
            "KGB-017", "add_edge accepts EdgeKind enum",
            "depends_on", e.kind if e else None,
            cause="enum kind provided",
            effect="stored as string value",
            lesson="Enum coercion must work",
        )

    def test_get_edge(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(a.node_id, b.node_id, "link")
        got = eng.get_edge(e.edge_id)
        record(
            "KGB-018", "get_edge returns correct edge",
            e.edge_id, got.edge_id if got else None,
            cause="get by ID",
            effect="returns same edge",
            lesson="Edge lookup must work",
        )

    def test_get_edge_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_edge("nonexistent")
        record(
            "KGB-019", "get_edge returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing edges return None",
        )

    def test_delete_edge(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(a.node_id, b.node_id, "temp")
        ok = eng.delete_edge(e.edge_id)
        record(
            "KGB-020", "delete_edge returns True",
            True, ok,
            cause="edge deleted",
            effect="returns True",
            lesson="Edge deletion returns success bool",
        )
        assert eng.get_edge(e.edge_id) is None

    def test_delete_edge_missing(self) -> None:
        eng = _make_engine()
        ok = eng.delete_edge("nonexistent")
        record(
            "KGB-021", "delete_edge returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="returns False",
            lesson="Missing edge deletion is idempotent",
        )

    def test_edge_to_dict(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(a.node_id, b.node_id, "ser")
        d = e.to_dict()
        record(
            "KGB-022", "edge to_dict contains label",
            "ser", d["label"],
            cause="to_dict called",
            effect="dict returned with label",
            lesson="Edge serialisation must include all fields",
        )

    def test_add_edge_bidirectional(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(
            a.node_id, b.node_id, "both", bidirectional=True)
        record(
            "KGB-023", "bidirectional edge flag stored",
            True, e.bidirectional if e else False,
            cause="bidirectional=True",
            effect="flag stored",
            lesson="Bidirectional edges are supported",
        )

    def test_add_edge_with_properties(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        e = eng.add_edge(
            a.node_id, b.node_id, "rich",
            properties={"since": "2024"})
        record(
            "KGB-024", "edge properties stored",
            "2024", e.properties.get("since") if e else None,
            cause="properties provided",
            effect="properties stored",
            lesson="Edge properties must be preserved",
        )


class TestListFiltering:
    """Node and edge listing with filters."""

    def test_list_nodes_all(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        nodes = eng.list_nodes()
        record(
            "KGB-025", "list_nodes returns all nodes",
            3, len(nodes),
            cause="three nodes created",
            effect="three returned",
            lesson="List returns all by default",
        )

    def test_list_nodes_by_kind(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        nodes = eng.list_nodes(kind="entity")
        record(
            "KGB-026", "list_nodes filters by kind",
            1, len(nodes),
            cause="kind=entity filter",
            effect="one entity node",
            lesson="Kind filter must work",
        )

    def test_list_nodes_by_kind_enum(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        nodes = eng.list_nodes(kind=NodeKind.concept)
        record(
            "KGB-027", "list_nodes accepts NodeKind enum",
            1, len(nodes),
            cause="NodeKind.concept filter",
            effect="one concept node",
            lesson="Enum coercion in filters",
        )

    def test_list_nodes_by_tag(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        nodes = eng.list_nodes(tag="core")
        record(
            "KGB-028", "list_nodes filters by tag",
            2, len(nodes),
            cause="tag=core filter",
            effect="two core-tagged nodes",
            lesson="Tag filter must work",
        )

    def test_list_nodes_label_contains(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        nodes = eng.list_nodes(label_contains="lpha")
        record(
            "KGB-029", "list_nodes filters by label_contains",
            1, len(nodes),
            cause="label_contains='lpha'",
            effect="one match (Alpha)",
            lesson="Substring label filter",
        )

    def test_list_nodes_limit(self) -> None:
        eng = _make_engine()
        for i in range(10):
            eng.add_node(f"Node-{i}")
        nodes = eng.list_nodes(limit=3)
        record(
            "KGB-030", "list_nodes respects limit",
            3, len(nodes),
            cause="limit=3",
            effect="three returned",
            lesson="Limit must cap results",
        )

    def test_list_edges_all(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        edges = eng.list_edges()
        record(
            "KGB-031", "list_edges returns all edges",
            3, len(edges),
            cause="three edges created",
            effect="three returned",
            lesson="List returns all by default",
        )

    def test_list_edges_by_kind(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        edges = eng.list_edges(kind="causes")
        record(
            "KGB-032", "list_edges filters by kind",
            1, len(edges),
            cause="kind=causes filter",
            effect="one causes edge",
            lesson="Edge kind filter must work",
        )

    def test_list_edges_by_source(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        edges = eng.list_edges(source_id=a.node_id)
        record(
            "KGB-033", "list_edges filters by source_id",
            1, len(edges),
            cause="source_id=Alpha",
            effect="one outgoing edge",
            lesson="Source filter must work",
        )


class TestNeighbors:
    """Neighbor lookup."""

    def test_outgoing_neighbors(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        nb = eng.get_neighbors(a.node_id, direction="outgoing")
        record(
            "KGB-034", "outgoing neighbors of Alpha",
            1, len(nb),
            cause="one outgoing edge from Alpha",
            effect="one neighbor",
            lesson="Outgoing direction filter",
        )
        assert nb[0].label == "Beta"

    def test_incoming_neighbors(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        nb = eng.get_neighbors(a.node_id, direction="incoming")
        record(
            "KGB-035", "incoming neighbors of Alpha",
            1, len(nb),
            cause="one incoming edge to Alpha",
            effect="one neighbor",
            lesson="Incoming direction filter",
        )
        assert nb[0].label == "Gamma"

    def test_both_neighbors(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        nb = eng.get_neighbors(a.node_id, direction="both")
        record(
            "KGB-036", "both neighbors of Alpha",
            2, len(nb),
            cause="one in + one out edge",
            effect="two neighbors",
            lesson="Both direction returns union",
        )

    def test_neighbors_with_kind_filter(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        # kind filter on get_neighbors filters by NODE kind, not edge kind
        nb = eng.get_neighbors(a.node_id, direction="both", kind="event")
        record(
            "KGB-037", "neighbors filtered by node kind",
            1, len(nb),
            cause="only Gamma (event) is neighbor matching kind=event",
            effect="one neighbor (Gamma)",
            lesson="Node kind filter on neighbors",
        )

    def test_neighbors_missing_node(self) -> None:
        eng = _make_engine()
        nb = eng.get_neighbors("missing")
        record(
            "KGB-038", "neighbors of missing node is empty",
            0, len(nb),
            cause="invalid node ID",
            effect="empty list",
            lesson="Missing node returns empty neighbors",
        )


class TestTraversal:
    """Graph traversal and path-finding."""

    def test_bfs_traversal(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        tr = eng.traverse(a.node_id, mode="bfs", max_depth=5)
        record(
            "KGB-039", "BFS visits all reachable nodes",
            3, len(tr.visited_ids),
            cause="triangle graph BFS from Alpha",
            effect="all 3 nodes visited",
            lesson="BFS must reach all connected nodes",
        )

    def test_dfs_traversal(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        tr = eng.traverse(a.node_id, mode="dfs", max_depth=5)
        record(
            "KGB-040", "DFS visits all reachable nodes",
            3, len(tr.visited_ids),
            cause="triangle graph DFS from Alpha",
            effect="all 3 nodes visited",
            lesson="DFS must reach all connected nodes",
        )

    def test_traversal_max_depth(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        tr = eng.traverse(a.node_id, mode="bfs", max_depth=1)
        record(
            "KGB-041", "traversal respects max_depth=1",
            True, len(tr.visited_ids) <= 2,
            cause="max_depth=1",
            effect="at most 2 nodes (start + 1 hop)",
            lesson="Depth limit must be enforced",
        )

    def test_traversal_missing_start(self) -> None:
        eng = _make_engine()
        tr = eng.traverse("missing")
        record(
            "KGB-042", "traversal from missing node returns empty",
            0, len(tr.visited_ids),
            cause="invalid start node",
            effect="empty traversal",
            lesson="Missing start node handled gracefully",
        )

    def test_shortest_path_exists(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        path = eng.find_shortest_path(a.node_id, c.node_id)
        record(
            "KGB-043", "shortest path found",
            True, path is not None and len(path) >= 2,
            cause="path exists A->B->C",
            effect="path returned",
            lesson="Shortest path via BFS",
        )

    def test_shortest_path_direct(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        eng.add_edge(a.node_id, b.node_id, "direct")
        path = eng.find_shortest_path(a.node_id, b.node_id)
        record(
            "KGB-044", "shortest path for direct edge",
            2, len(path) if path else 0,
            cause="direct edge A->B",
            effect="path=[A,B]",
            lesson="Direct edge is shortest path",
        )

    def test_shortest_path_none(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        # No edge between them
        path = eng.find_shortest_path(a.node_id, b.node_id)
        record(
            "KGB-045", "shortest path returns None when disconnected",
            True, path is None,
            cause="no edge between A and B",
            effect="None returned",
            lesson="Disconnected nodes have no path",
        )

    def test_shortest_path_to_self(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        path = eng.find_shortest_path(a.node_id, a.node_id)
        record(
            "KGB-046", "shortest path to self",
            True, path is not None and len(path) == 1,
            cause="same source and target",
            effect="path is [A]",
            lesson="Self-path is trivial",
        )

    def test_traversal_enum_mode(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        tr = eng.traverse(a.node_id, mode=TraversalMode.bfs)
        record(
            "KGB-047", "traverse accepts TraversalMode enum",
            1, len(tr.visited_ids),
            cause="enum mode used",
            effect="single node visited",
            lesson="Enum coercion in traverse",
        )


class TestSubgraphAndSearch:
    """Subgraph extraction and search."""

    def test_extract_subgraph(self) -> None:
        eng = _make_engine()
        a, b, c, e1, e2, e3 = _make_triangle(eng)
        sg = eng.extract_subgraph([a.node_id, b.node_id])
        record(
            "KGB-048", "subgraph contains requested nodes",
            2, len(sg.node_ids),
            cause="two node IDs provided",
            effect="subgraph has 2 nodes",
            lesson="Subgraph includes requested nodes",
        )

    def test_extract_subgraph_includes_edges(self) -> None:
        eng = _make_engine()
        a, b, c, e1, e2, e3 = _make_triangle(eng)
        sg = eng.extract_subgraph(
            [a.node_id, b.node_id], include_internal_edges=True)
        record(
            "KGB-049", "subgraph includes internal edges",
            True, len(sg.edge_ids) >= 1,
            cause="include_internal_edges=True",
            effect="A->B edge included",
            lesson="Internal edges must be captured",
        )

    def test_extract_subgraph_no_edges(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        sg = eng.extract_subgraph(
            [a.node_id, b.node_id], include_internal_edges=False)
        record(
            "KGB-050", "subgraph without internal edges",
            0, len(sg.edge_ids),
            cause="include_internal_edges=False",
            effect="no edges in subgraph",
            lesson="Edge inclusion is optional",
        )

    def test_search_by_label(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        qr = eng.search_nodes("alpha")
        record(
            "KGB-051", "search finds node by label (case-insensitive)",
            1, qr.count,
            cause="search 'alpha' matches 'Alpha'",
            effect="one match",
            lesson="Search must be case-insensitive",
        )

    def test_search_by_tag(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        qr = eng.search_nodes("core")
        record(
            "KGB-052", "search finds nodes by tag",
            True, qr.count >= 2,
            cause="search 'core' matches tag on A and B",
            effect="at least 2 matches",
            lesson="Search covers tags",
        )

    def test_search_no_results(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        qr = eng.search_nodes("zzzzz_nonexistent")
        record(
            "KGB-053", "search with no matches returns 0",
            0, qr.count,
            cause="no matching text",
            effect="zero results",
            lesson="Empty search is graceful",
        )

    def test_search_limit(self) -> None:
        eng = _make_engine()
        for i in range(10):
            eng.add_node(f"Item-{i}", tags=["batch"])
        qr = eng.search_nodes("item", limit=3)
        record(
            "KGB-054", "search respects limit",
            3, len(qr.matched_nodes),
            cause="limit=3",
            effect="three matched_nodes returned",
            lesson="Search limit must cap results",
        )


class TestStats:
    """Graph statistics."""

    def test_empty_stats(self) -> None:
        eng = _make_engine()
        st = eng.get_stats()
        record(
            "KGB-055", "empty graph stats",
            0, st.total_nodes,
            cause="no nodes",
            effect="total_nodes=0",
            lesson="Empty graph stats are valid",
        )
        assert st.total_edges == 0
        assert st.density == 0.0

    def test_triangle_stats(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        st = eng.get_stats()
        record(
            "KGB-056", "triangle graph stats",
            3, st.total_nodes,
            cause="triangle graph",
            effect="3 nodes",
            lesson="Stats reflect graph state",
        )
        assert st.total_edges == 3
        assert st.density == 1.0  # 2*3/(3*2) = 1.0

    def test_stats_node_kinds(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        st = eng.get_stats()
        record(
            "KGB-057", "stats contain node kind counts",
            True, "entity" in st.node_kinds,
            cause="entity node exists",
            effect="entity in node_kinds",
            lesson="Kind counts must be computed",
        )

    def test_stats_connected_components(self) -> None:
        eng = _make_engine()
        a = eng.add_node("A")
        b = eng.add_node("B")
        eng.add_edge(a.node_id, b.node_id, "link")
        c = eng.add_node("Isolated")
        st = eng.get_stats()
        record(
            "KGB-058", "stats count connected components",
            2, st.connected_components,
            cause="one connected pair + one isolated node",
            effect="2 components",
            lesson="Component counting must work",
        )

    def test_stats_avg_degree(self) -> None:
        eng = _make_engine()
        a, b, c, _, _, _ = _make_triangle(eng)
        st = eng.get_stats()
        record(
            "KGB-059", "stats compute avg_degree",
            True, st.avg_degree > 0,
            cause="edges exist",
            effect="positive avg degree",
            lesson="Average degree must be computed",
        )

    def test_stats_to_dict(self) -> None:
        eng = _make_engine()
        st = eng.get_stats()
        d = st.to_dict()
        record(
            "KGB-060", "stats to_dict has total_nodes key",
            True, "total_nodes" in d,
            cause="to_dict called",
            effect="dict contains expected keys",
            lesson="Stats serialise correctly",
        )


class TestImportExport:
    """Graph import/export."""

    def test_export(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        data = eng.export_graph()
        record(
            "KGB-061", "export returns dict with nodes and edges",
            True, "nodes" in data and "edges" in data,
            cause="export_graph called",
            effect="dict with nodes/edges",
            lesson="Export must include all data",
        )
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 3

    def test_import_roundtrip(self) -> None:
        eng1 = _make_engine()
        _make_triangle(eng1)
        data = eng1.export_graph()
        eng2 = _make_engine()
        count = eng2.import_graph(data)
        record(
            "KGB-062", "import restores nodes and edges",
            6, count,  # 3 nodes + 3 edges
            cause="import_graph from exported data",
            effect="6 items imported",
            lesson="Round-trip must preserve graph",
        )
        assert eng2.get_stats().total_nodes == 3
        assert eng2.get_stats().total_edges == 3

    def test_merge_graph(self) -> None:
        eng1 = _make_engine()
        eng1.add_node("A")
        eng2 = _make_engine()
        eng2.add_node("B")
        merged = eng1.merge_graph(eng2)
        record(
            "KGB-063", "merge_graph adds nodes from other engine",
            True, merged >= 1,
            cause="merge_graph called",
            effect="at least 1 node added",
            lesson="Merge must combine graphs",
        )
        assert eng1.get_stats().total_nodes == 2

    def test_clear(self) -> None:
        eng = _make_engine()
        _make_triangle(eng)
        eng.clear()
        record(
            "KGB-064", "clear removes all nodes and edges",
            0, eng.get_stats().total_nodes,
            cause="clear called",
            effect="empty graph",
            lesson="Clear must reset everything",
        )
        assert eng.get_stats().total_edges == 0


class TestThreadSafety:
    """Concurrent access."""

    def test_concurrent_add_nodes(self) -> None:
        eng = _make_engine()
        errors: list = []

        def add_batch(start: int) -> None:
            try:
                for i in range(20):
                    eng.add_node(f"N-{start}-{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_batch, args=(t,))
                   for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record(
            "KGB-065", "concurrent add_node is safe",
            100, eng.get_stats().total_nodes,
            cause="5 threads × 20 nodes",
            effect="100 nodes total",
            lesson="Thread safety under concurrent writes",
        )
        assert not errors

    def test_concurrent_add_edges(self) -> None:
        eng = _make_engine()
        nodes = [eng.add_node(f"N-{i}") for i in range(10)]
        errors: list = []

        def add_edges(start: int) -> None:
            try:
                for i in range(5):
                    s = nodes[(start + i) % 10]
                    t = nodes[(start + i + 1) % 10]
                    eng.add_edge(s.node_id, t.node_id, f"e-{start}-{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_edges, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        record(
            "KGB-066", "concurrent add_edge is safe",
            True, eng.get_stats().total_edges > 0,
            cause="4 threads adding edges",
            effect="edges added without errors",
            lesson="Edge creation is thread-safe",
        )
        assert not errors


class TestWingmanProtocol:
    """Wingman pair validation."""

    def test_wingman_pass(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "b"])
        record(
            "KGB-067", "wingman pair passes when matched",
            True, result["passed"],
            cause="matching lists",
            effect="passed=True",
            lesson="Exact match passes wingman",
        )

    def test_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        record(
            "KGB-068", "wingman fails on empty storyline",
            False, result["passed"],
            cause="empty storyline",
            effect="passed=False",
            lesson="Empty storyline is invalid",
        )

    def test_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        record(
            "KGB-069", "wingman fails on empty actuals",
            False, result["passed"],
            cause="empty actuals",
            effect="passed=False",
            lesson="Empty actuals is invalid",
        )

    def test_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        record(
            "KGB-070", "wingman fails on length mismatch",
            False, result["passed"],
            cause="different lengths",
            effect="passed=False",
            lesson="Length mismatch detected",
        )

    def test_wingman_value_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "c"])
        record(
            "KGB-071", "wingman fails on value mismatch",
            False, result["passed"],
            cause="value mismatch at index 1",
            effect="passed=False",
            lesson="Value mismatches detected",
        )


class TestSandboxGating:
    """Causality Sandbox gating."""

    def test_sandbox_pass(self) -> None:
        result = gate_kgb_in_sandbox({"graph_id": "abc123"})
        record(
            "KGB-072", "sandbox gate passes with valid context",
            True, result["passed"],
            cause="valid graph_id",
            effect="passed=True",
            lesson="Valid context passes gate",
        )

    def test_sandbox_missing_key(self) -> None:
        result = gate_kgb_in_sandbox({})
        record(
            "KGB-073", "sandbox gate fails on missing key",
            False, result["passed"],
            cause="empty context",
            effect="passed=False",
            lesson="Required keys must be present",
        )

    def test_sandbox_empty_value(self) -> None:
        result = gate_kgb_in_sandbox({"graph_id": ""})
        record(
            "KGB-074", "sandbox gate fails on empty value",
            False, result["passed"],
            cause="empty graph_id",
            effect="passed=False",
            lesson="Values must be non-empty",
        )


class TestFlaskAPI:
    """Flask Blueprint API endpoints."""

    def _client(self):
        """Create a Flask test client."""
        try:
            from flask import Flask
        except ImportError:
            return None
        eng = _make_engine()
        app = Flask(__name__)
        bp = create_knowledge_graph_api(eng)
        app.register_blueprint(bp)
        return app.test_client(), eng

    def test_create_node_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        resp = client.post("/api/kg/nodes", json={
            "label": "API-Node", "kind": "entity"})
        record(
            "KGB-075", "POST /kg/nodes creates node",
            201, resp.status_code,
            cause="POST with label",
            effect="201 Created",
            lesson="API node creation works",
        )

    def test_list_nodes_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        eng.add_node("Listed")
        resp = client.get("/api/kg/nodes")
        record(
            "KGB-076", "GET /kg/nodes returns list",
            200, resp.status_code,
            cause="GET request",
            effect="200 OK",
            lesson="API listing works",
        )
        data = resp.get_json()
        assert len(data) >= 1

    def test_get_node_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        n = eng.add_node("Fetched")
        resp = client.get(f"/api/kg/nodes/{n.node_id}")
        record(
            "KGB-077", "GET /kg/nodes/<id> returns node",
            200, resp.status_code,
            cause="GET by ID",
            effect="200 OK",
            lesson="API get by ID works",
        )

    def test_get_node_404(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        resp = client.get("/api/kg/nodes/nonexistent")
        record(
            "KGB-078", "GET /kg/nodes/<bad_id> returns 404",
            404, resp.status_code,
            cause="invalid ID",
            effect="404 Not Found",
            lesson="API returns proper error codes",
        )

    def test_create_edge_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        a = eng.add_node("A")
        b = eng.add_node("B")
        resp = client.post("/api/kg/edges", json={
            "source_id": a.node_id,
            "target_id": b.node_id,
            "label": "links"})
        record(
            "KGB-079", "POST /kg/edges creates edge",
            201, resp.status_code,
            cause="POST with valid endpoints",
            effect="201 Created",
            lesson="API edge creation works",
        )

    def test_search_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        eng.add_node("Searchable")
        resp = client.get("/api/kg/search?q=search")
        record(
            "KGB-080", "GET /kg/search returns results",
            200, resp.status_code,
            cause="search query",
            effect="200 OK",
            lesson="API search works",
        )

    def test_stats_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        resp = client.get("/api/kg/stats")
        record(
            "KGB-081", "GET /kg/stats returns stats",
            200, resp.status_code,
            cause="stats request",
            effect="200 OK",
            lesson="API stats work",
        )

    def test_health_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        resp = client.get("/api/kg/health")
        data = resp.get_json()
        record(
            "KGB-082", "GET /kg/health returns healthy",
            "healthy", data.get("status"),
            cause="health check",
            effect="healthy status",
            lesson="Health endpoint works",
        )

    def test_traverse_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        a = eng.add_node("Start")
        b = eng.add_node("End")
        eng.add_edge(a.node_id, b.node_id, "to")
        resp = client.post("/api/kg/traverse", json={
            "start_node_id": a.node_id, "mode": "bfs"})
        record(
            "KGB-083", "POST /kg/traverse returns traversal",
            200, resp.status_code,
            cause="BFS traverse request",
            effect="200 OK",
            lesson="API traversal works",
        )

    def test_export_import_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        eng.add_node("Exportable")
        resp = client.post("/api/kg/export")
        record(
            "KGB-084", "POST /kg/export returns graph data",
            200, resp.status_code,
            cause="export request",
            effect="200 OK with data",
            lesson="API export works",
        )

    def test_delete_node_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        n = eng.add_node("Deletable")
        resp = client.delete(f"/api/kg/nodes/{n.node_id}")
        record(
            "KGB-085", "DELETE /kg/nodes/<id> removes node",
            200, resp.status_code,
            cause="DELETE request",
            effect="200 OK",
            lesson="API deletion works",
        )

    def test_update_node_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        n = eng.add_node("Original")
        resp = client.put(f"/api/kg/nodes/{n.node_id}",
                          json={"label": "Updated"})
        record(
            "KGB-086", "PUT /kg/nodes/<id> updates node",
            200, resp.status_code,
            cause="PUT with new label",
            effect="200 OK",
            lesson="API update works",
        )

    def test_shortest_path_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        a = eng.add_node("A")
        b = eng.add_node("B")
        eng.add_edge(a.node_id, b.node_id, "link")
        resp = client.post("/api/kg/shortest-path", json={
            "source_id": a.node_id, "target_id": b.node_id})
        record(
            "KGB-087", "POST /kg/shortest-path finds path",
            200, resp.status_code,
            cause="path exists",
            effect="200 OK with path",
            lesson="API shortest path works",
        )

    def test_subgraph_api(self) -> None:
        result = self._client()
        if result is None:
            return
        client, eng = result
        a = eng.add_node("A")
        b = eng.add_node("B")
        resp = client.post("/api/kg/subgraph", json={
            "node_ids": [a.node_id, b.node_id]})
        record(
            "KGB-088", "POST /kg/subgraph extracts subgraph",
            200, resp.status_code,
            cause="subgraph request",
            effect="200 OK",
            lesson="API subgraph extraction works",
        )
