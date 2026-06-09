"""
dispatch_graph_snapshots.py — Path A v1=b snapshot addendum

Founder directive (locked 2026-06-09):
  v1=b — snapshot every graph mutation (full timeline replayable)
  v2=a — fork preserves history (parent_dispatch_id pointer)

Persists ArtifactGraph snapshots so /canvas can load any past dispatch
and reconstruct what it actually did, node-by-node.

STORAGE:
  Table dispatch_graph_snapshots in murphy_audit.db (already 470 MB,
  already live). Idempotent schema.

CALLERS:
  - PCR-040b graph executor → snapshot(dispatch_id, graph) after
    each agent fires (one row per mutation)
  - Future fork action → snapshot(dispatch_id, graph,
                                  parent_dispatch_id=N)

CANVAS-03 (future round) reads list_snapshots() to render the
historical timeline. This round only ships the writer + reader; the
PCR-040b wire-in is queued as EXEC-03 (small in-place edit of app.py).

ALL OPERATIONS ARE FAIL-SOFT:
  Snapshot failures never break dispatch. They log and move on.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("murphy.graph_snapshots")

AUDIT_DB_PATH = "/var/lib/murphy-production/murphy_audit.db"


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dispatch_graph_snapshots (
    snapshot_id        TEXT PRIMARY KEY,
    dispatch_id        TEXT NOT NULL,
    parent_dispatch_id TEXT,
    snapshot_at_ns     INTEGER NOT NULL,
    mutation_seq       INTEGER NOT NULL,
    graph_json         TEXT NOT NULL,
    node_count         INTEGER NOT NULL,
    trigger_role       TEXT,
    trigger_agent_id   TEXT,
    success            INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_snap_dispatch_seq
    ON dispatch_graph_snapshots(dispatch_id, mutation_seq);
CREATE INDEX IF NOT EXISTS idx_snap_parent
    ON dispatch_graph_snapshots(parent_dispatch_id);
CREATE INDEX IF NOT EXISTS idx_snap_dispatch_time
    ON dispatch_graph_snapshots(dispatch_id, snapshot_at_ns DESC);
"""


def _graph_to_json(graph: Any) -> str:
    """Best-effort serialization. ArtifactGraph has .to_dict() (PCR-040b)."""
    try:
        if hasattr(graph, "to_dict") and callable(graph.to_dict):
            return json.dumps(graph.to_dict(), default=str)
        if is_dataclass(graph):
            return json.dumps(asdict(graph), default=str)
        if isinstance(graph, dict):
            return json.dumps(graph, default=str)
        return json.dumps({"repr": repr(graph)[:2000]}, default=str)
    except Exception as e:
        LOG.warning("graph_to_json failed: %s", e)
        return json.dumps({"error": str(e)})


def _count_nodes(graph: Any) -> int:
    """Best-effort node count for the index. Doesn't have to be perfect."""
    try:
        if hasattr(graph, "nodes"):
            nodes_attr = graph.nodes
            return len(nodes_attr) if hasattr(nodes_attr, "__len__") else 0
        if isinstance(graph, dict):
            n = graph.get("nodes")
            return len(n) if hasattr(n, "__len__") else 0
        return 0
    except Exception:
        return 0


class GraphSnapshotWriter:
    """Idempotent, fail-soft snapshot writer."""

    def __init__(self, db_path: str = AUDIT_DB_PATH) -> None:
        self.db_path = db_path
        self._mutation_seqs: Dict[str, int] = {}   # in-process counter per dispatch
        self._bootstrap_attempted = False

    # ─────────────────────────────────────────────────────────────
    # Schema bootstrap (idempotent)
    # ─────────────────────────────────────────────────────────────

    def _bootstrap_schema(self) -> bool:
        try:
            conn = sqlite3.connect(self.db_path, timeout=3)
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            LOG.warning("snapshot schema bootstrap failed: %s", e)
            return False

    def _ensure_ready(self) -> bool:
        if not self._bootstrap_attempted:
            self._bootstrap_attempted = True
            return self._bootstrap_schema()
        return True

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def snapshot(
        self,
        dispatch_id: str,
        graph: Any,
        *,
        trigger_role: Optional[str] = None,
        trigger_agent_id: Optional[str] = None,
        success: bool = True,
        parent_dispatch_id: Optional[str] = None,
    ) -> Optional[str]:
        """Persist a single graph snapshot. Returns snapshot_id or None on failure.

        FAIL-SOFT — never raises.
        """
        if not self._ensure_ready():
            return None

        seq = self._mutation_seqs.get(dispatch_id, 0) + 1
        self._mutation_seqs[dispatch_id] = seq

        snapshot_id   = str(uuid.uuid4())
        graph_json    = _graph_to_json(graph)
        node_count    = _count_nodes(graph)
        snapshot_at   = time.time_ns()

        try:
            conn = sqlite3.connect(self.db_path, timeout=3)
            conn.execute(
                "INSERT INTO dispatch_graph_snapshots "
                "(snapshot_id, dispatch_id, parent_dispatch_id, snapshot_at_ns, "
                " mutation_seq, graph_json, node_count, trigger_role, "
                " trigger_agent_id, success) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id, dispatch_id, parent_dispatch_id, snapshot_at,
                    seq, graph_json, node_count, trigger_role,
                    trigger_agent_id, int(success),
                ),
            )
            conn.commit()
            conn.close()
            return snapshot_id
        except sqlite3.Error as e:
            LOG.warning("snapshot insert failed (non-fatal): %s", e)
            return None

    def list_snapshots(self, dispatch_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return all snapshots for a dispatch, oldest first (replay order)."""
        if not self._ensure_ready():
            return []
        try:
            conn = sqlite3.connect(self.db_path, timeout=3)
            rows = conn.execute(
                "SELECT snapshot_id, dispatch_id, parent_dispatch_id, "
                "       snapshot_at_ns, mutation_seq, node_count, "
                "       trigger_role, trigger_agent_id, success, graph_json "
                "FROM dispatch_graph_snapshots "
                "WHERE dispatch_id = ? "
                "ORDER BY mutation_seq ASC "
                "LIMIT ?",
                (dispatch_id, limit),
            ).fetchall()
            conn.close()
        except sqlite3.Error as e:
            LOG.warning("snapshot list failed: %s", e)
            return []

        out = []
        for r in rows:
            try:
                graph = json.loads(r[9]) if r[9] else {}
            except Exception:
                graph = {"_parse_error": True}
            out.append({
                "snapshot_id":        r[0],
                "dispatch_id":        r[1],
                "parent_dispatch_id": r[2],
                "snapshot_at_ns":     r[3],
                "mutation_seq":       r[4],
                "node_count":         r[5],
                "trigger_role":       r[6],
                "trigger_agent_id":   r[7],
                "success":            bool(r[8]),
                "graph":              graph,
            })
        return out

    def latest_snapshot(self, dispatch_id: str) -> Optional[Dict[str, Any]]:
        """Return the most recent snapshot for a dispatch, or None."""
        snaps = self.list_snapshots(dispatch_id, limit=1)
        # list_snapshots returns oldest first; we want newest — sort here
        if not snaps:
            return None
        return max(snaps, key=lambda s: s["mutation_seq"])

    def fork_lineage(self, dispatch_id: str) -> List[str]:
        """Walk parent_dispatch_id pointers backward. Returns list oldest→newest."""
        if not self._ensure_ready():
            return [dispatch_id]
        chain = [dispatch_id]
        try:
            conn = sqlite3.connect(self.db_path, timeout=3)
            current = dispatch_id
            for _ in range(20):  # bounded walk — no infinite loops on cycles
                row = conn.execute(
                    "SELECT parent_dispatch_id FROM dispatch_graph_snapshots "
                    "WHERE dispatch_id = ? AND parent_dispatch_id IS NOT NULL "
                    "LIMIT 1",
                    (current,),
                ).fetchone()
                if not row or not row[0]:
                    break
                if row[0] in chain:   # cycle guard
                    break
                chain.append(row[0])
                current = row[0]
            conn.close()
        except sqlite3.Error as e:
            LOG.warning("fork_lineage failed: %s", e)
        chain.reverse()  # oldest first
        return chain
