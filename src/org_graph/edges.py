"""R615.4 — Multi-edge org graph edge writer.

The R615 canon non-negotiable: org chart is a typed multi-edge graph,
not a tree. Edges carry semantics:

  DEPARTMENT_MEMBER_OF       — constraint gate (halts work if violated)
  FUNCTIONAL_DELIVERABLE_OF  — output flow (drives what gets produced)
  SPAWNED_BY                 — lineage (cascade abort walks this)
  INHERITS_CAPABILITY        — reuse signal (DLF query hint)

This module is the canonical writer. It validates edge_type against
WEAVE_TYPES from dlf_r (the source of truth) and persists edges into
agent_substrate.db.org_graph_edges. Idempotent on
(from_node, to_node, edge_type).

Reads back via find_edges_from/find_edges_to/find_edges_by_type for
the constraint gate (R615.6) and the planner (R615.10).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "/var/lib/murphy-production/agent_substrate.db"

# The 4 R615 edge types (validated against dlf_r.WEAVE_TYPES at write time)
R615_EDGE_TYPES = frozenset({
    "DEPARTMENT_MEMBER_OF",
    "FUNCTIONAL_DELIVERABLE_OF",
    "SPAWNED_BY",
    "INHERITS_CAPABILITY",
})


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ensure_nodes_table(c: sqlite3.Connection) -> None:
    """R615 Round 5 — track known nodes so we can detect ghost references."""
    c.execute("""
        CREATE TABLE IF NOT EXISTS org_graph_nodes (
            node_id TEXT PRIMARY KEY,
            kind TEXT,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT DEFAULT '{}'
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_node_kind ON org_graph_nodes(kind)")


def _register_node(c: sqlite3.Connection, node_id: str, kind: str = "task") -> None:
    """Auto-register a node (idempotent). Lenient v1; strict mode is R6+."""
    _ensure_nodes_table(c)
    c.execute(
        "INSERT OR IGNORE INTO org_graph_nodes (node_id, kind) VALUES (?, ?)",
        (node_id, kind),
    )


def _ensure_table(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS org_graph_edges (
            edge_id TEXT PRIMARY KEY,
            from_node TEXT NOT NULL,
            to_node TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (from_node, to_node, edge_type)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_edge_from ON org_graph_edges(from_node)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_edge_to ON org_graph_edges(to_node)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_edge_type ON org_graph_edges(edge_type)")


def _validate_edge_type(edge_type: str) -> None:
    """Validate edge_type against dlf_r WEAVE_TYPES (source of truth).

    Raises ValueError if invalid. Accepts any WEAVE_TYPES member, but
    R615-specific types must be in R615_EDGE_TYPES.
    """
    try:
        import sys
        if "/opt/Murphy-System/src" not in sys.path:
            sys.path.insert(0, "/opt/Murphy-System/src")
        import dlf_r
        if edge_type not in dlf_r.WEAVE_TYPES:
            raise ValueError(
                f"edge_type {edge_type!r} not in dlf_r.WEAVE_TYPES "
                f"(allowed: {sorted(dlf_r.WEAVE_TYPES)})"
            )
    except ImportError:
        # If dlf_r unreachable, fall back to R615 set
        if edge_type not in R615_EDGE_TYPES:
            raise ValueError(
                f"edge_type {edge_type!r} not in R615_EDGE_TYPES "
                f"(allowed: {sorted(R615_EDGE_TYPES)})"
            )


def add_edge(
    from_node: str,
    to_node: str,
    edge_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Add a typed edge to the org graph. Idempotent on the 3-tuple key.

    Returns the edge_id (existing or newly created).
    Raises ValueError if edge_type is invalid.
    """
    _validate_edge_type(edge_type)
    meta_json = json.dumps(metadata or {}, sort_keys=True)
    edge_id = f"edge_{uuid.uuid4().hex[:16]}"
    with _conn() as c:
        _ensure_table(c)
        # R615 Round 5: auto-register nodes so we can detect ghosts later
        _register_node(c, from_node)
        _register_node(c, to_node)
        # Check existing
        existing = c.execute(
            "SELECT edge_id FROM org_graph_edges "
            "WHERE from_node=? AND to_node=? AND edge_type=?",
            (from_node, to_node, edge_type),
        ).fetchone()
        if existing:
            return existing["edge_id"]
        c.execute(
            "INSERT INTO org_graph_edges "
            "(edge_id, from_node, to_node, edge_type, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (edge_id, from_node, to_node, edge_type, meta_json),
        )
    return edge_id


def find_edges_from(node_id: str, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all edges with from_node=node_id (optionally filtered by type)."""
    with _conn() as c:
        _ensure_table(c)
        if edge_type:
            rows = c.execute(
                "SELECT * FROM org_graph_edges WHERE from_node=? AND edge_type=?",
                (node_id, edge_type),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM org_graph_edges WHERE from_node=?",
                (node_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def find_edges_to(node_id: str, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all edges with to_node=node_id (optionally filtered by type).

    This is the multi-parent lookup primitive: a node can have multiple
    incoming edges of the same type (multiple DEPARTMENT_MEMBER_OF edges,
    multiple SPAWNED_BY parents per R615 canon).
    """
    with _conn() as c:
        _ensure_table(c)
        if edge_type:
            rows = c.execute(
                "SELECT * FROM org_graph_edges WHERE to_node=? AND edge_type=?",
                (node_id, edge_type),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM org_graph_edges WHERE to_node=?",
                (node_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def find_edges_by_type(edge_type: str) -> List[Dict[str, Any]]:
    """Return all edges of a given type. Used by planner and constraint gate."""
    _validate_edge_type(edge_type)
    with _conn() as c:
        _ensure_table(c)
        rows = c.execute(
            "SELECT * FROM org_graph_edges WHERE edge_type=?",
            (edge_type,),
        ).fetchall()
    return [dict(r) for r in rows]


def parents_of(node_id: str) -> List[str]:
    """Return all parent node IDs via SPAWNED_BY edges (multi-parent capable)."""
    edges = find_edges_from(node_id, edge_type="SPAWNED_BY")
    return [e["to_node"] for e in edges]


__all__ = [
    "R615_EDGE_TYPES",
    "add_edge",
    "find_edges_from",
    "find_edges_to",
    "find_edges_by_type",
    "parents_of",
]


def known_nodes() -> int:
    """Return count of distinct nodes seen in the graph (sanity helper)."""
    with _conn() as c:
        _ensure_nodes_table(c)
        row = c.execute("SELECT COUNT(*) AS n FROM org_graph_nodes").fetchone()
    return row["n"] if row else 0
