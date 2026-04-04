# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for geographic_load_balancer — GLB-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable GLBRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from geographic_load_balancer import (  # noqa: E402
    DeploymentSpec,
    DeploymentStatus,
    DeploymentStrategy,
    EdgeNode,
    GeographicLoadBalancer,
    HealthCheckResult,
    NodeStatus,
    Region,
    RegionStatus,
    RoutingDecision,
    RoutingPolicy,
    RoutingStrategy,
    create_glb_api,
    gate_glb_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class GLBRecord:
    """One GLB check record."""

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


_RESULTS: List[GLBRecord] = []


def record(
    check_id: str,
    desc: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(
        GLBRecord(
            check_id=check_id,
            description=desc,
            expected=expected,
            actual=actual,
            passed=ok,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    return ok


# -- Helpers ---------------------------------------------------------------


def _glb() -> GeographicLoadBalancer:
    return GeographicLoadBalancer()


def _glb_with_regions(n: int = 3) -> tuple:
    """Return engine + list of region objects."""
    glb = _glb()
    regions = []
    coords = [
        ("US-East", 40.7, -74.0),
        ("EU-West", 51.5, -0.1),
        ("AP-Tokyo", 35.7, 139.7),
    ]
    for name, lat, lon in coords[:n]:
        r = glb.add_region(name, lat, lon)
        regions.append(r)
    return glb, regions


def _glb_with_nodes() -> tuple:
    """Return engine, regions, nodes."""
    glb, regions = _glb_with_regions(2)
    nodes = []
    for r in regions:
        n = glb.add_edge_node(r.id, f"edge-{r.name}", f"http://{r.name}.example.com")
        nodes.append(n)
    return glb, regions, nodes


# =========================================================================
# REGION MANAGEMENT TESTS
# =========================================================================


def test_glb_001_add_region():
    """Add a region and verify it returns a Region object."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    ok = record(
        "GLB-001", "add_region returns Region",
        True, isinstance(r, Region),
        cause="add_region called", effect="Region created",
        lesson="Region creation returns proper type",
    )
    assert ok


def test_glb_002_region_fields():
    """Verify region fields are correctly set."""
    glb = _glb()
    r = glb.add_region("EU-West", 51.5, -0.1, capacity_weight=0.8, max_connections=500)
    ok1 = record("GLB-002a", "name correct", "EU-West", r.name)
    ok2 = record("GLB-002b", "latitude correct", 51.5, r.latitude)
    ok3 = record("GLB-002c", "longitude correct", -0.1, r.longitude)
    ok4 = record("GLB-002d", "capacity_weight correct", 0.8, r.capacity_weight)
    ok5 = record("GLB-002e", "max_connections correct", 500, r.max_connections)
    ok6 = record("GLB-002f", "status is active", RegionStatus.active, r.status)
    assert all([ok1, ok2, ok3, ok4, ok5, ok6])


def test_glb_003_get_region():
    """Retrieve an existing region by ID."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    fetched = glb.get_region(r.id)
    ok = record("GLB-003", "get_region returns same", r.id, fetched.id if fetched else None)
    assert ok


def test_glb_004_get_nonexistent_region():
    """Get region with bad ID returns None."""
    glb = _glb()
    ok = record("GLB-004", "get nonexistent returns None", None, glb.get_region("bad"))
    assert ok


def test_glb_005_list_regions():
    """List all regions."""
    glb, regions = _glb_with_regions(3)
    listed = glb.list_regions()
    ok = record("GLB-005", "list returns 3", 3, len(listed))
    assert ok


def test_glb_006_list_regions_status_filter():
    """List regions filtered by status."""
    glb, regions = _glb_with_regions(2)
    listed = glb.list_regions(status_filter="active")
    ok = record("GLB-006", "all active", 2, len(listed))
    assert ok


def test_glb_007_update_region_load():
    """Update region load metrics."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    updated = glb.update_region_load(r.id, current_load=0.75, active_connections=500, avg_latency_ms=15.0)
    ok1 = record("GLB-007a", "current_load updated", 0.75, updated.current_load)
    ok2 = record("GLB-007b", "active_connections updated", 500, updated.active_connections)
    ok3 = record("GLB-007c", "avg_latency_ms updated", 15.0, updated.avg_latency_ms)
    assert all([ok1, ok2, ok3])


def test_glb_008_update_nonexistent_region():
    """Update load on missing region returns None."""
    glb = _glb()
    ok = record("GLB-008", "update nonexistent", None, glb.update_region_load("bad", 0.5, 10, 5.0))
    assert ok


def test_glb_009_remove_region():
    """Remove a region."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    ok1 = record("GLB-009a", "remove returns True", True, glb.remove_region(r.id))
    ok2 = record("GLB-009b", "region gone", None, glb.get_region(r.id))
    assert ok1 and ok2


def test_glb_010_remove_nonexistent_region():
    """Remove missing region returns False."""
    glb = _glb()
    ok = record("GLB-010", "remove nonexistent", False, glb.remove_region("bad"))
    assert ok


# =========================================================================
# EDGE NODE TESTS
# =========================================================================


def test_glb_011_add_edge_node():
    """Add an edge node to a region."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    n = glb.add_edge_node(r.id, "edge-1", "http://edge1.example.com")
    ok = record("GLB-011", "add_edge_node returns EdgeNode", True, isinstance(n, EdgeNode))
    assert ok


def test_glb_012_add_node_bad_region():
    """Add edge node to nonexistent region returns None."""
    glb = _glb()
    ok = record("GLB-012", "bad region returns None", None, glb.add_edge_node("bad", "e1", "http://x"))
    assert ok


def test_glb_013_list_edge_nodes():
    """List all edge nodes."""
    glb, regions, nodes = _glb_with_nodes()
    listed = glb.list_edge_nodes()
    ok = record("GLB-013", "list all nodes", 2, len(listed))
    assert ok


def test_glb_014_list_nodes_by_region():
    """Filter nodes by region_id."""
    glb, regions, nodes = _glb_with_nodes()
    listed = glb.list_edge_nodes(region_id=regions[0].id)
    ok = record("GLB-014", "filter by region", 1, len(listed))
    assert ok


def test_glb_015_get_edge_node():
    """Retrieve a specific edge node."""
    glb, regions, nodes = _glb_with_nodes()
    fetched = glb.get_edge_node(nodes[0].id)
    ok = record("GLB-015", "get node", nodes[0].id, fetched.id if fetched else None)
    assert ok


def test_glb_016_remove_edge_node():
    """Remove an edge node."""
    glb, regions, nodes = _glb_with_nodes()
    ok1 = record("GLB-016a", "remove ok", True, glb.remove_edge_node(nodes[0].id))
    ok2 = record("GLB-016b", "node gone", None, glb.get_edge_node(nodes[0].id))
    assert ok1 and ok2


# =========================================================================
# HEALTH CHECK TESTS
# =========================================================================


def test_glb_017_record_health_check_healthy():
    """Record a healthy health check."""
    glb, regions, nodes = _glb_with_nodes()
    hc = glb.record_health_check(nodes[0].id, "healthy", 5.0)
    ok = record("GLB-017", "health check returns result", True, isinstance(hc, HealthCheckResult))
    assert ok


def test_glb_018_health_check_degrades_node():
    """Consecutive unhealthy checks degrade node status."""
    glb, regions, nodes = _glb_with_nodes()
    nid = nodes[0].id
    glb.record_health_check(nid, "unhealthy", 100.0)
    glb.record_health_check(nid, "unhealthy", 100.0)
    n = glb.get_edge_node(nid)
    ok = record("GLB-018", "2 failures -> degraded", NodeStatus.degraded, n.status)
    assert ok


def test_glb_019_health_check_offlines_node():
    """3+ consecutive failures set node offline."""
    glb, regions, nodes = _glb_with_nodes()
    nid = nodes[0].id
    for _ in range(3):
        glb.record_health_check(nid, "unhealthy", 200.0)
    n = glb.get_edge_node(nid)
    ok = record("GLB-019", "3 failures -> offline", NodeStatus.offline, n.status)
    assert ok


def test_glb_020_health_check_recovery():
    """A healthy check after failures resets node to healthy."""
    glb, regions, nodes = _glb_with_nodes()
    nid = nodes[0].id
    glb.record_health_check(nid, "unhealthy", 200.0)
    glb.record_health_check(nid, "unhealthy", 200.0)
    glb.record_health_check(nid, "healthy", 5.0)
    n = glb.get_edge_node(nid)
    ok = record("GLB-020", "recovery to healthy", NodeStatus.healthy, n.status)
    assert ok


def test_glb_021_health_check_bad_node():
    """Health check on nonexistent node returns None."""
    glb = _glb()
    ok = record("GLB-021", "bad node hc", None, glb.record_health_check("bad", "healthy", 1.0))
    assert ok


# =========================================================================
# ROUTING POLICY TESTS
# =========================================================================


def test_glb_022_create_routing_policy():
    """Create a routing policy."""
    glb = _glb()
    p = glb.create_routing_policy("latency-first", "latency_based")
    ok = record("GLB-022", "policy created", True, isinstance(p, RoutingPolicy))
    assert ok


def test_glb_023_get_routing_policy():
    """Retrieve routing policy."""
    glb = _glb()
    p = glb.create_routing_policy("geo", "geo_proximity")
    fetched = glb.get_routing_policy(p.id)
    ok = record("GLB-023", "get policy", p.id, fetched.id if fetched else None)
    assert ok


def test_glb_024_list_routing_policies():
    """List all routing policies."""
    glb = _glb()
    glb.create_routing_policy("p1", "latency_based")
    glb.create_routing_policy("p2", "failover")
    listed = glb.list_routing_policies()
    ok = record("GLB-024", "list policies", 2, len(listed))
    assert ok


# =========================================================================
# ROUTING DECISION TESTS (all 5 strategies)
# =========================================================================


def test_glb_025_route_latency_based():
    """Route using latency_based strategy picks lowest latency."""
    glb, regions = _glb_with_regions(2)
    glb.update_region_load(regions[0].id, 0.3, 100, 50.0)
    glb.update_region_load(regions[1].id, 0.3, 100, 10.0)
    p = glb.create_routing_policy("lat", "latency_based")
    d = glb.route_request(p.id, 45.0, 0.0)
    ok = record(
        "GLB-025", "latency picks lower ms region",
        regions[1].id, d.selected_region_id if d else None,
        cause="region1 has 10ms vs region0 50ms",
        effect="region1 selected",
        lesson="Latency-based routing prefers lowest avg_latency_ms",
    )
    assert ok


def test_glb_026_route_geo_proximity():
    """Route using geo_proximity strategy picks closest."""
    glb, regions = _glb_with_regions(3)
    p = glb.create_routing_policy("geo", "geo_proximity")
    # Source near New York (40.7, -74.0) -> US-East closest
    d = glb.route_request(p.id, 41.0, -73.0)
    ok = record(
        "GLB-026", "geo proximity picks closest",
        regions[0].id, d.selected_region_id if d else None,
        cause="source is near US-East",
        effect="US-East selected",
        lesson="Geo-proximity uses haversine distance",
    )
    assert ok


def test_glb_027_route_weighted_round_robin():
    """Route using weighted_round_robin returns a valid region."""
    glb, regions = _glb_with_regions(2)
    p = glb.create_routing_policy("wrr", "weighted_round_robin")
    d = glb.route_request(p.id, 0.0, 0.0)
    ok = record(
        "GLB-027", "wrr returns valid region",
        True, d is not None and d.selected_region_id in {r.id for r in regions},
    )
    assert ok


def test_glb_028_route_failover():
    """Route using failover picks first healthy region."""
    glb, regions = _glb_with_regions(2)
    p = glb.create_routing_policy("fo", "failover")
    d = glb.route_request(p.id, 0.0, 0.0)
    ok = record(
        "GLB-028", "failover picks a healthy region",
        True, d is not None and d.selected_region_id in {r.id for r in regions},
    )
    assert ok


def test_glb_029_route_capacity_based():
    """Route using capacity_based picks region with most remaining capacity."""
    glb, regions = _glb_with_regions(2)
    glb.update_region_load(regions[0].id, 0.9, 900, 10.0)
    glb.update_region_load(regions[1].id, 0.1, 50, 10.0)
    p = glb.create_routing_policy("cap", "capacity_based")
    d = glb.route_request(p.id, 0.0, 0.0)
    ok = record(
        "GLB-029", "capacity picks least loaded",
        regions[1].id, d.selected_region_id if d else None,
        cause="region1 load=0.1 vs region0 load=0.9",
    )
    assert ok


def test_glb_030_route_nonexistent_policy():
    """Route with bad policy ID returns None."""
    glb = _glb()
    ok = record("GLB-030", "bad policy", None, glb.route_request("bad", 0.0, 0.0))
    assert ok


def test_glb_031_route_no_healthy_regions():
    """Route with no healthy regions returns None."""
    glb = _glb()
    r = glb.add_region("offline-region", 40.0, -74.0)
    # Make region offline by directly updating status
    with glb._lock:
        glb._regions[r.id].status = RegionStatus.offline
    p = glb.create_routing_policy("lat", "latency_based")
    d = glb.route_request(p.id, 0.0, 0.0)
    ok = record("GLB-031", "no healthy -> None", None, d)
    assert ok


# =========================================================================
# DEPLOYMENT TESTS
# =========================================================================


def test_glb_032_create_deployment():
    """Create a deployment spec."""
    glb, regions = _glb_with_regions(2)
    dep = glb.create_deployment("deploy-1", [r.id for r in regions])
    ok = record("GLB-032", "deployment created", True, isinstance(dep, DeploymentSpec))
    assert ok


def test_glb_033_create_deployment_bad_regions():
    """Deployment with nonexistent regions returns None."""
    glb = _glb()
    dep = glb.create_deployment("bad", ["nonexistent"])
    ok = record("GLB-033", "bad regions -> None", None, dep)
    assert ok


def test_glb_034_get_deployment():
    """Get existing deployment."""
    glb, regions = _glb_with_regions(1)
    dep = glb.create_deployment("d1", [regions[0].id])
    fetched = glb.get_deployment(dep.id)
    ok = record("GLB-034", "get deployment", dep.id, fetched.id if fetched else None)
    assert ok


def test_glb_035_list_deployments():
    """List all deployments."""
    glb, regions = _glb_with_regions(1)
    glb.create_deployment("d1", [regions[0].id])
    glb.create_deployment("d2", [regions[0].id])
    listed = glb.list_deployments()
    ok = record("GLB-035", "list deployments", 2, len(listed))
    assert ok


def test_glb_036_advance_deployment():
    """Advance deployment progress."""
    glb, regions = _glb_with_regions(1)
    dep = glb.create_deployment("d1", [regions[0].id])
    advanced = glb.advance_deployment(dep.id)
    ok = record(
        "GLB-036", "advance increases progress",
        True, advanced is not None and advanced.progress_pct > 0.0,
    )
    assert ok


def test_glb_037_advance_to_completion():
    """Advance deployment to 100% sets status to active."""
    glb, regions = _glb_with_regions(1)
    dep = glb.create_deployment("d1", [regions[0].id])
    for _ in range(10):
        dep = glb.advance_deployment(dep.id)
        if dep and dep.status == DeploymentStatus.active:
            break
    ok = record("GLB-037", "deployment becomes active", DeploymentStatus.active, dep.status)
    assert ok


def test_glb_038_rollback_deployment():
    """Rollback a deployment."""
    glb, regions = _glb_with_regions(1)
    dep = glb.create_deployment("d1", [regions[0].id])
    glb.advance_deployment(dep.id)
    rolled = glb.rollback_deployment(dep.id)
    ok = record("GLB-038", "rollback sets rolled_back", DeploymentStatus.rolled_back, rolled.status)
    assert ok


def test_glb_039_rollback_nonexistent():
    """Rollback nonexistent deployment returns None."""
    glb = _glb()
    ok = record("GLB-039", "rollback bad id", None, glb.rollback_deployment("bad"))
    assert ok


# =========================================================================
# STATS TEST
# =========================================================================


def test_glb_040_stats():
    """Get stats returns correct counts."""
    glb, regions = _glb_with_regions(2)
    for r in regions:
        glb.add_edge_node(r.id, f"n-{r.name}", f"http://{r.name}.test")
    p = glb.create_routing_policy("lat", "latency_based")
    glb.route_request(p.id, 0.0, 0.0)
    stats = glb.get_stats()
    ok1 = record("GLB-040a", "regions count", 2, stats["regions"])
    ok2 = record("GLB-040b", "nodes count", 2, stats["nodes"])
    ok3 = record("GLB-040c", "policies count", 1, stats["policies"])
    assert ok1 and ok2 and ok3


# =========================================================================
# WINGMAN + SANDBOX GATE TESTS
# =========================================================================


def test_glb_041_wingman_valid():
    """Wingman pair validation passes for valid data."""
    r = validate_wingman_pair("storyline text", "actuals data")
    ok = record("GLB-041", "wingman valid", True, r["passed"])
    assert ok


def test_glb_042_wingman_empty_storyline():
    """Wingman rejects empty storyline."""
    r = validate_wingman_pair("", "actuals")
    ok = record("GLB-042", "empty storyline fails", False, r["passed"])
    assert ok


def test_glb_043_wingman_empty_actuals():
    """Wingman rejects empty actuals."""
    r = validate_wingman_pair("storyline", "")
    ok = record("GLB-043", "empty actuals fails", False, r["passed"])
    assert ok


def test_glb_044_wingman_length_mismatch():
    """Wingman rejects extreme length mismatch."""
    r = validate_wingman_pair("x" * 1000, "y")
    ok = record("GLB-044", "length mismatch fails", False, r["passed"])
    assert ok


def test_glb_045_sandbox_valid():
    """Sandbox gate passes for valid action."""
    r = gate_glb_in_sandbox("route", {"region_id": "r1", "triggered_by": "test"})
    ok = record("GLB-045", "sandbox valid", True, r["passed"])
    assert ok


def test_glb_046_sandbox_forbidden():
    """Sandbox gate rejects forbidden actions."""
    r = gate_glb_in_sandbox("delete_all_nodes", {"region_id": "r1", "triggered_by": "x"})
    ok = record("GLB-046", "forbidden blocked", False, r["passed"])
    assert ok


def test_glb_047_sandbox_missing_keys():
    """Sandbox gate rejects missing metadata keys."""
    r = gate_glb_in_sandbox("route", {"region_id": "r1"})
    ok = record("GLB-047", "missing triggered_by", False, r["passed"])
    assert ok


def test_glb_048_sandbox_empty_region_id():
    """Sandbox gate rejects empty region_id."""
    r = gate_glb_in_sandbox("route", {"region_id": "", "triggered_by": "x"})
    ok = record("GLB-048", "empty region_id", False, r["passed"])
    assert ok


# =========================================================================
# FLASK API TESTS
# =========================================================================


def test_glb_049_api_health():
    """API /health returns 200."""
    glb = _glb()
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.get("/api/glb/health")
        ok = record("GLB-049", "health 200", 200, resp.status_code)
        assert ok


def test_glb_050_api_add_region():
    """API POST /regions creates region."""
    glb = _glb()
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.post("/api/glb/regions", json={
            "name": "US-East", "latitude": 40.7, "longitude": -74.0,
        })
        ok = record("GLB-050", "add region 201", 201, resp.status_code)
        assert ok


def test_glb_051_api_list_regions():
    """API GET /regions returns list."""
    glb = _glb()
    glb.add_region("US-East", 40.7, -74.0)
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.get("/api/glb/regions")
        data = resp.get_json()
        ok = record("GLB-051", "list regions", True, isinstance(data, list) and len(data) == 1)
        assert ok


def test_glb_052_api_get_region():
    """API GET /regions/<id> returns single region."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.get(f"/api/glb/regions/{r.id}")
        ok = record("GLB-052", "get region 200", 200, resp.status_code)
        assert ok


def test_glb_053_api_get_region_404():
    """API GET /regions/<bad> returns 404."""
    glb = _glb()
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.get("/api/glb/regions/nonexistent")
        ok = record("GLB-053", "not found 404", 404, resp.status_code)
        assert ok


def test_glb_054_api_add_node():
    """API POST /nodes creates node."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.post("/api/glb/nodes", json={
            "region_id": r.id, "name": "e1", "endpoint_url": "http://e1.test",
        })
        ok = record("GLB-054", "add node 201", 201, resp.status_code)
        assert ok


def test_glb_055_api_route_request():
    """API POST /route returns routing decision."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    p = glb.create_routing_policy("lat", "latency_based")
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.post("/api/glb/route", json={
            "policy_id": p.id, "source_lat": 41.0, "source_lon": -73.0,
        })
        ok = record("GLB-055", "route 200", 200, resp.status_code)
        assert ok


def test_glb_056_api_create_policy():
    """API POST /policies creates policy."""
    glb = _glb()
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.post("/api/glb/policies", json={
            "name": "geo", "strategy": "geo_proximity",
        })
        ok = record("GLB-056", "create policy 201", 201, resp.status_code)
        assert ok


def test_glb_057_api_stats():
    """API GET /stats returns stats dict."""
    glb = _glb()
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.get("/api/glb/stats")
        data = resp.get_json()
        ok = record("GLB-057", "stats has regions key", True, "regions" in data)
        assert ok


def test_glb_058_api_create_deployment():
    """API POST /deployments creates deployment."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.post("/api/glb/deployments", json={
            "name": "dep1", "target_regions": [r.id],
        })
        ok = record("GLB-058", "create deployment 201", 201, resp.status_code)
        assert ok


# =========================================================================
# THREAD SAFETY TEST
# =========================================================================


def test_glb_059_thread_safety():
    """Concurrent region additions don't corrupt state."""
    glb = _glb()
    errors = []

    def add_regions(prefix: str, count: int) -> None:
        try:
            for i in range(count):
                glb.add_region(f"{prefix}-{i}", float(i), float(i))
        except Exception as exc:
            errors.append(str(exc))

    threads = [
        threading.Thread(target=add_regions, args=(f"t{t}", 20))
        for t in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok1 = record("GLB-059a", "no errors", 0, len(errors))
    ok2 = record("GLB-059b", "100 regions created", 100, len(glb.list_regions()))
    assert ok1 and ok2


# =========================================================================
# EDGE CASES
# =========================================================================


def test_glb_060_region_with_tags():
    """Region can be created with tags."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0, tags={"env": "prod", "tier": "1"})
    ok = record("GLB-060", "tags set", {"env": "prod", "tier": "1"}, r.tags)
    assert ok


def test_glb_061_haversine_same_point():
    """Geo-proximity routing with source at exact region coords."""
    glb = _glb()
    r = glb.add_region("exact", 40.7, -74.0)
    p = glb.create_routing_policy("geo", "geo_proximity")
    d = glb.route_request(p.id, 40.7, -74.0)
    ok = record("GLB-061", "exact match selects region", r.id, d.selected_region_id if d else None)
    assert ok


def test_glb_062_deployment_list_filter():
    """List deployments with status filter."""
    glb, regions = _glb_with_regions(1)
    dep = glb.create_deployment("d1", [regions[0].id])
    listed = glb.list_deployments(status_filter="pending")
    ok = record("GLB-062", "filter by pending", True, len(listed) >= 1)
    assert ok


def test_glb_063_api_missing_fields():
    """API POST /regions with missing fields returns 400."""
    glb = _glb()
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.post("/api/glb/regions", json={"name": "x"})
        ok = record("GLB-063", "missing lat/lon -> 400", 400, resp.status_code)
        assert ok


def test_glb_064_api_delete_region():
    """API DELETE /regions/<id> removes region."""
    glb = _glb()
    r = glb.add_region("US-East", 40.7, -74.0)
    bp = create_glb_api(glb)
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    with app.test_client() as c:
        resp = c.delete(f"/api/glb/regions/{r.id}")
        ok = record("GLB-064", "delete 200", 200, resp.status_code)
        assert ok


# =========================================================================
# RECORD SUMMARY
# =========================================================================


def test_glb_999_summary():
    """Print audit summary of all GLB checks."""
    total = len(_RESULTS)
    passed = sum(1 for r in _RESULTS if r.passed)
    print(f"\n=== GLB-001 Audit: {passed}/{total} passed ===")
    for r in _RESULTS:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.check_id}: {r.description}")
    ok = record("GLB-999", "all checks passed", total, passed)
    assert ok
