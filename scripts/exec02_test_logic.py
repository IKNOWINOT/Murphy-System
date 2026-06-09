#!/usr/bin/env python3
"""
Pure-logic tests for EXEC-02:
  - dispatch_graph_snapshots (write, list, fork lineage)
  - executive_wiring.register_executive (idempotency, error handling)
  - Route handler shape contracts (mock FastAPI app)

No service, no network, no LLM. Runs in milliseconds.
"""

from __future__ import annotations
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _check(name, cond, detail=""):
    icon = "✓" if cond else "✗"
    line = f"  {icon} {name}"
    if detail:
        line += f"   ({str(detail)[:140]})"
    print(line)
    return cond


# ──────────────────────────────────────────────────────────
# Fake objects for testing
# ──────────────────────────────────────────────────────────

@dataclass
class _FakeNode:
    output_type: str
    producer_role: str


@dataclass
class _FakeGraph:
    """Mimics ArtifactGraph for snapshot serialization tests."""
    nodes: List[_FakeNode] = field(default_factory=list)

    def to_dict(self):
        return {"nodes": [{"output_type": n.output_type,
                           "producer_role": n.producer_role}
                          for n in self.nodes]}


class _FakeAppState:
    """Just an attribute bag — like app.state."""
    pass


class _FakeApp:
    """Minimal FastAPI-shaped fake. Records added routes."""
    def __init__(self):
        self.state = _FakeAppState()
        self.routes: List[str] = []

    def get(self, path):
        def deco(fn):
            self.routes.append(f"GET {path}")
            return fn
        return deco

    def post(self, path):
        def deco(fn):
            self.routes.append(f"POST {path}")
            return fn
        return deco


# ──────────────────────────────────────────────────────────
# Snapshot writer tests
# ──────────────────────────────────────────────────────────

def test_snapshot_basic_write():
    print("\n── snapshots: basic write + list ──")
    from src.dispatch_graph_snapshots import GraphSnapshotWriter
    ok = True

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    w = GraphSnapshotWriter(db_path=tmp.name)

    g = _FakeGraph(nodes=[_FakeNode("design", "lead_eng")])
    snap_id = w.snapshot(
        dispatch_id="d_001", graph=g,
        trigger_role="lead_eng", trigger_agent_id="ag_42",
    )
    ok &= _check("snapshot returns id", snap_id is not None, snap_id)

    snaps = w.list_snapshots("d_001")
    ok &= _check("list returns 1", len(snaps) == 1)
    ok &= _check("node_count = 1", snaps[0]["node_count"] == 1)
    ok &= _check("mutation_seq = 1", snaps[0]["mutation_seq"] == 1)
    ok &= _check("trigger_role preserved", snaps[0]["trigger_role"] == "lead_eng")
    ok &= _check("graph reconstructed",
                 snaps[0]["graph"].get("nodes", [{}])[0].get("output_type") == "design",
                 snaps[0]["graph"])

    os.unlink(tmp.name)
    return ok


def test_snapshot_per_mutation_v1b():
    """v1=b — snapshot every graph mutation, monotonic mutation_seq."""
    print("\n── snapshots: v1=b per-mutation timeline ──")
    from src.dispatch_graph_snapshots import GraphSnapshotWriter
    ok = True

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    w = GraphSnapshotWriter(db_path=tmp.name)

    g = _FakeGraph()
    # Simulate 3 agents firing — each writes a snapshot
    for i, role in enumerate(["analyst", "lead_eng", "qa"]):
        g.nodes.append(_FakeNode(f"output_{i}", role))
        w.snapshot("d_002", g, trigger_role=role, trigger_agent_id=f"ag_{i}")

    snaps = w.list_snapshots("d_002")
    ok &= _check("3 snapshots persisted", len(snaps) == 3)
    seqs = [s["mutation_seq"] for s in snaps]
    ok &= _check("seqs monotonic 1,2,3", seqs == [1, 2, 3], seqs)
    counts = [s["node_count"] for s in snaps]
    ok &= _check("node counts grow 1,2,3", counts == [1, 2, 3], counts)
    roles = [s["trigger_role"] for s in snaps]
    ok &= _check("trigger sequence preserved",
                 roles == ["analyst", "lead_eng", "qa"], roles)

    os.unlink(tmp.name)
    return ok


def test_snapshot_fork_v2a():
    """v2=a — fork preserves history via parent_dispatch_id."""
    print("\n── snapshots: v2=a fork lineage ──")
    from src.dispatch_graph_snapshots import GraphSnapshotWriter
    ok = True

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    w = GraphSnapshotWriter(db_path=tmp.name)

    # Original dispatch
    g1 = _FakeGraph(nodes=[_FakeNode("design", "lead")])
    w.snapshot("d_orig", g1, trigger_role="lead")

    # Fork: child dispatch with parent pointer
    g2 = _FakeGraph(nodes=[_FakeNode("design_v2", "lead")])
    w.snapshot("d_fork", g2, trigger_role="lead",
               parent_dispatch_id="d_orig")

    lineage = w.fork_lineage("d_fork")
    ok &= _check("lineage contains both", set(lineage) == {"d_orig", "d_fork"}, lineage)
    ok &= _check("lineage ordered oldest→newest",
                 lineage[0] == "d_orig" and lineage[-1] == "d_fork", lineage)

    os.unlink(tmp.name)
    return ok


def test_snapshot_failsoft():
    """Writes never raise even with bad DB path or bad graph."""
    print("\n── snapshots: fail-soft ──")
    from src.dispatch_graph_snapshots import GraphSnapshotWriter
    ok = True

    # Bad DB path → returns None, doesn't raise
    w = GraphSnapshotWriter(db_path="/nonexistent/path/db.sqlite")
    result = w.snapshot("d_x", _FakeGraph())
    ok &= _check("bad db path: no raise, returns None", result is None)

    snaps = w.list_snapshots("d_x")
    ok &= _check("bad db list: returns []", snaps == [])

    # Bad graph object → still doesn't raise
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    w2 = GraphSnapshotWriter(db_path=tmp.name)

    class BadGraph:
        def to_dict(self):
            raise RuntimeError("simulated explosion")

    result = w2.snapshot("d_y", BadGraph())
    ok &= _check("bad graph: still produces snapshot row",
                 result is not None, result)
    snaps = w2.list_snapshots("d_y")
    ok &= _check("bad graph snapshot has error marker in graph_json",
                 "error" in snaps[0]["graph"] if snaps else False)

    os.unlink(tmp.name)
    return ok


# ──────────────────────────────────────────────────────────
# Wiring tests
# ──────────────────────────────────────────────────────────

def test_register_executive_idempotent():
    print("\n── wiring: register_executive idempotency ──")
    from src.executive_wiring import register_executive
    ok = True

    app = _FakeApp()

    s1 = register_executive(app)
    ok &= _check("first register: engine attached", s1["engine"] is True)
    ok &= _check("first register: slot_controller attached",
                 s1["slot_controller"] is True)
    ok &= _check("first register: snapshot_writer attached",
                 s1["snapshot_writer"] is True)
    ok &= _check("first register: 4 routes added",
                 len(s1["routes_added"]) == 4, s1["routes_added"])
    ok &= _check("app.routes has 4 entries", len(app.routes) == 4, app.routes)

    # Second call — should be idempotent (no double-register)
    s2 = register_executive(app)
    ok &= _check("second register: still ok",
                 s2["engine"] is True)
    ok &= _check("second register: no new routes added",
                 len(app.routes) == 4, app.routes)

    return ok


def test_register_routes_listed():
    print("\n── wiring: all 4 expected routes registered ──")
    from src.executive_wiring import register_executive
    ok = True

    app = _FakeApp()
    register_executive(app)

    expected = [
        "GET /api/executive/status",
        "POST /api/executive/cta/{cta_id}/commit",
        "POST /api/executive/cta/{cta_id}/dismiss",
        "GET /api/executive/snapshots/{dispatch_id}",
    ]
    for path in expected:
        ok &= _check(f"route present: {path}", path in app.routes,
                     app.routes if path not in app.routes else "")

    return ok


# ──────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────

def main():
    print("EXEC-02 pure-logic test harness")

    suites = [
        ("snapshot basic write",         test_snapshot_basic_write),
        ("snapshot v1=b per-mutation",   test_snapshot_per_mutation_v1b),
        ("snapshot v2=a fork lineage",   test_snapshot_fork_v2a),
        ("snapshot fail-soft",           test_snapshot_failsoft),
        ("wiring register idempotent",   test_register_executive_idempotent),
        ("wiring routes registered",     test_register_routes_listed),
    ]

    results = {}
    for name, fn in suites:
        try:
            results[name] = fn()
        except Exception as e:
            import traceback
            print(f"  ✗ SUITE EXCEPTION: {name}: {e}")
            traceback.print_exc()
            results[name] = False

    print("\n── SUMMARY ──")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}")
    print(f"\n  {passed}/{total} suites passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
