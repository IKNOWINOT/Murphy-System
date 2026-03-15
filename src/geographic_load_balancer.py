# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Geographic Load Balancing and Edge Deployment — GLB-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Manage geographic regions, edge nodes, routing policies, and deployments.
Route incoming requests to optimal regions via latency, proximity, weight,
failover, or capacity strategies.  Track edge-node health and orchestrate
rolling / blue-green / canary deployments across regions.

Classes: RegionStatus/NodeStatus/RoutingStrategy/DeploymentStrategy/
DeploymentStatus (enums), Region/EdgeNode/RoutingPolicy/RoutingDecision/
HealthCheckResult/DeploymentSpec (dataclasses), GeographicLoadBalancer (thread-safe).
``create_glb_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via capped_append;
no external dependencies beyond stdlib + Flask.
"""
from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from flask import Blueprint, jsonify, request

    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]

    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}

    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}

        @staticmethod
        def get_json(silent: bool = True) -> dict:
            return {}

    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:

    def capped_append(target_list: list, item: Any, max_size: int = 50_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class RegionStatus(str, Enum):
    """RegionStatus enumeration."""
    active = "active"; degraded = "degraded"
    offline = "offline"; maintenance = "maintenance"

class NodeStatus(str, Enum):
    """NodeStatus enumeration."""
    healthy = "healthy"; degraded = "degraded"
    offline = "offline"; draining = "draining"

class RoutingStrategy(str, Enum):
    """RoutingStrategy enumeration."""
    latency_based = "latency_based"; geo_proximity = "geo_proximity"
    weighted_round_robin = "weighted_round_robin"; failover = "failover"
    capacity_based = "capacity_based"

class DeploymentStrategy(str, Enum):
    """DeploymentStrategy enumeration."""
    rolling = "rolling"; blue_green = "blue_green"; canary = "canary"

class DeploymentStatus(str, Enum):
    """DeploymentStatus enumeration."""
    pending = "pending"; deploying = "deploying"; active = "active"
    failed = "failed"; rolled_back = "rolled_back"

@dataclass
class Region:
    """A geographic region that can serve traffic."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    status: RegionStatus = RegionStatus.active
    capacity_weight: float = 1.0
    current_load: float = 0.0
    max_connections: int = 1000
    active_connections: int = 0
    avg_latency_ms: float = 0.0
    health_score: float = 1.0
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self); d["status"] = self.status.value; return d

@dataclass
class EdgeNode:
    """An edge node within a region."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    region_id: str = ""
    name: str = ""
    endpoint_url: str = ""
    status: NodeStatus = NodeStatus.healthy
    weight: float = 1.0
    current_rps: float = 0.0
    max_rps: float = 1000.0
    health_check_url: str = ""
    last_health_check: str = field(default_factory=_now)
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self); d["status"] = self.status.value; return d

@dataclass
class RoutingPolicy:
    """Defines how traffic should be routed."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    strategy: RoutingStrategy = RoutingStrategy.latency_based
    fallback_region_id: Optional[str] = None
    sticky_sessions: bool = False
    health_threshold: float = 0.5
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self); d["strategy"] = self.strategy.value; return d

@dataclass
class RoutingDecision:
    """Records a single routing decision."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    policy_id: str = ""
    source_lat: float = 0.0
    source_lon: float = 0.0
    selected_region_id: str = ""
    selected_node_id: str = ""
    latency_estimate_ms: float = 0.0
    reason: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)

@dataclass
class HealthCheckResult:
    """Result of an edge-node health check."""
    node_id: str = ""
    region_id: str = ""
    status: str = "healthy"
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=_now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)

@dataclass
class DeploymentSpec:
    """Specification for an edge deployment."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    target_regions: List[str] = field(default_factory=list)
    replicas_per_region: int = 1
    strategy: DeploymentStrategy = DeploymentStrategy.rolling
    status: DeploymentStatus = DeploymentStatus.pending
    progress_pct: float = 0.0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self); d["strategy"] = self.strategy.value; d["status"] = self.status.value
        return d

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in km between two lat/lon points."""
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _capped(lst: list, item: Any, cap: int = 500) -> None:
    """Local bounded append — delegates to imported capped_append."""
    capped_append(lst, item, cap)

class GeographicLoadBalancer:
    """Thread-safe geographic load-balancing engine."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._regions: Dict[str, Region] = {}
        self._nodes: Dict[str, EdgeNode] = {}
        self._policies: Dict[str, RoutingPolicy] = {}
        self._deployments: Dict[str, DeploymentSpec] = {}
        self._decisions: List[RoutingDecision] = []
        self._health_log: List[HealthCheckResult] = []
        self._rr_index = 0

    def add_region(
        self, name: str, latitude: float, longitude: float,
        capacity_weight: float = 1.0, max_connections: int = 1000,
        tags: Optional[Dict[str, str]] = None,
    ) -> Region:
        """Create and register a new region."""
        region = Region(
            name=name, latitude=latitude, longitude=longitude,
            capacity_weight=capacity_weight, max_connections=max_connections,
            tags=tags or {},
        )
        with self._lock:
            self._regions[region.id] = region
        logger.info("Region added: %s (%s)", region.id, name)
        return region

    def get_region(self, region_id: str) -> Optional[Region]:
        """Return a region by id, or None."""
        with self._lock: return self._regions.get(region_id)

    def list_regions(self, status_filter: Optional[str] = None) -> List[Region]:
        """Return regions, optionally filtered by status."""
        with self._lock:
            regions = list(self._regions.values())
        if status_filter:
            regions = [r for r in regions if r.status.value == status_filter]
        return regions

    def update_region_load(
        self, region_id: str, current_load: float,
        active_connections: int, avg_latency_ms: float,
    ) -> Optional[Region]:
        """Update live load metrics for a region."""
        with self._lock:
            region = self._regions.get(region_id)
            if not region:
                return None
            region.current_load = current_load
            region.active_connections = active_connections
            region.avg_latency_ms = avg_latency_ms
            region.health_score = max(0.0, 1.0 - current_load)
            region.updated_at = _now()
            self._maybe_degrade_region(region)
            return region

    @staticmethod
    def _maybe_degrade_region(region: Region) -> None:
        """Auto-set region status based on load."""
        if region.current_load >= 0.95:
            region.status = RegionStatus.degraded
        elif region.status == RegionStatus.degraded and region.current_load < 0.85:
            region.status = RegionStatus.active

    def remove_region(self, region_id: str) -> bool:
        """Remove a region and its edge nodes."""
        with self._lock:
            if region_id not in self._regions:
                return False
            del self._regions[region_id]
            to_del = [n for n in self._nodes if self._nodes[n].region_id == region_id]
            for nid in to_del:
                del self._nodes[nid]
        return True

    def add_edge_node(
        self, region_id: str, name: str, endpoint_url: str,
        weight: float = 1.0, max_rps: float = 1000.0,
        health_check_url: Optional[str] = None,
    ) -> Optional[EdgeNode]:
        """Add an edge node to a region."""
        with self._lock:
            if region_id not in self._regions:
                return None
            node = EdgeNode(
                region_id=region_id, name=name, endpoint_url=endpoint_url,
                weight=weight, max_rps=max_rps,
                health_check_url=health_check_url or endpoint_url + "/health",
            )
            self._nodes[node.id] = node
        logger.info("Edge node added: %s (%s)", node.id, name)
        return node

    def get_edge_node(self, node_id: str) -> Optional[EdgeNode]:
        """Return an edge node by id, or None."""
        with self._lock: return self._nodes.get(node_id)

    def list_edge_nodes(self, region_id: Optional[str] = None) -> List[EdgeNode]:
        """Return edge nodes, optionally filtered by region."""
        with self._lock:
            nodes = list(self._nodes.values())
        if region_id:
            nodes = [n for n in nodes if n.region_id == region_id]
        return nodes

    def remove_edge_node(self, node_id: str) -> bool:
        """Remove an edge node."""
        with self._lock:
            if node_id not in self._nodes:
                return False
            del self._nodes[node_id]
        return True

    def record_health_check(
        self, node_id: str, status: str, latency_ms: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[HealthCheckResult]:
        """Record a health-check result and update node status."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return None
            result = HealthCheckResult(
                node_id=node_id, region_id=node.region_id,
                status=status, latency_ms=latency_ms, details=details or {},
            )
            _capped(self._health_log, result)
            node.last_health_check = _now()
            self._apply_health_status(node, status)
            return result

    @staticmethod
    def _apply_health_status(node: EdgeNode, check_status: str) -> None:
        """Derive node status from consecutive failures."""
        if check_status == "healthy":
            node.consecutive_failures = 0
            node.status = NodeStatus.healthy
        else:
            node.consecutive_failures += 1
            if node.consecutive_failures >= 3:
                node.status = NodeStatus.offline
            else:
                node.status = NodeStatus.degraded

    def create_routing_policy(
        self, name: str, strategy: str,
        fallback_region_id: Optional[str] = None,
        sticky_sessions: bool = False, health_threshold: float = 0.5,
    ) -> RoutingPolicy:
        """Create a routing policy."""
        policy = RoutingPolicy(
            name=name, strategy=RoutingStrategy(strategy),
            fallback_region_id=fallback_region_id,
            sticky_sessions=sticky_sessions,
            health_threshold=health_threshold,
        )
        with self._lock:
            self._policies[policy.id] = policy
        return policy

    def get_routing_policy(self, policy_id: str) -> Optional[RoutingPolicy]:
        """Return a routing policy by id, or None."""
        with self._lock: return self._policies.get(policy_id)

    def list_routing_policies(self) -> List[RoutingPolicy]:
        """Return all routing policies."""
        with self._lock: return list(self._policies.values())

    def route_request(self, policy_id: str, source_lat: float, source_lon: float) -> Optional[RoutingDecision]:
        """Route a request according to the given policy."""
        with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                return None
            healthy = self._healthy_regions(policy.health_threshold)
            if not healthy:
                return self._fallback_decision(policy, source_lat, source_lon)
            region, reason = self._select_region(
                policy, healthy, source_lat, source_lon,
            )
            node = self._pick_node(region.id)
            decision = RoutingDecision(
                policy_id=policy_id, source_lat=source_lat,
                source_lon=source_lon, selected_region_id=region.id,
                selected_node_id=node.id if node else "",
                latency_estimate_ms=region.avg_latency_ms, reason=reason,
            )
            _capped(self._decisions, decision)
            return decision

    def _healthy_regions(self, threshold: float) -> List[Region]:
        """Return regions with health_score >= threshold and active status."""
        return [
            r for r in self._regions.values()
            if r.health_score >= threshold
            and r.status in (RegionStatus.active, RegionStatus.degraded)
        ]

    def _select_region(
        self, policy: RoutingPolicy, regions: List[Region],
        src_lat: float, src_lon: float,
    ) -> tuple[Region, str]:
        """Dispatch to the correct strategy."""
        strat = policy.strategy
        if strat == RoutingStrategy.latency_based:
            return self._strat_latency(regions)
        if strat == RoutingStrategy.geo_proximity:
            return self._strat_proximity(regions, src_lat, src_lon)
        if strat == RoutingStrategy.weighted_round_robin:
            return self._strat_wrr(regions)
        if strat == RoutingStrategy.failover:
            return self._strat_failover(regions, policy)
        return self._strat_capacity(regions)

    @staticmethod
    def _strat_latency(regions: List[Region]) -> tuple[Region, str]:
        best = min(regions, key=lambda r: r.avg_latency_ms)
        return best, "latency_based: lowest avg_latency_ms"

    @staticmethod
    def _strat_proximity(regions: List[Region], lat: float, lon: float) -> tuple[Region, str]:
        best = min(regions, key=lambda r: _haversine(lat, lon, r.latitude, r.longitude))
        return best, "geo_proximity: nearest region"

    def _strat_wrr(self, regions: List[Region]) -> tuple[Region, str]:
        regions.sort(key=lambda r: r.capacity_weight, reverse=True)
        # _rr_index is protected by the caller's self._lock
        self._rr_index += 1
        idx = self._rr_index % len(regions)
        return regions[idx], "weighted_round_robin"

    @staticmethod
    def _strat_failover(regions: List[Region], policy: RoutingPolicy) -> tuple[Region, str]:
        active = [r for r in regions if r.status == RegionStatus.active]
        if active:
            return active[0], "failover: first active region"
        if policy.fallback_region_id:
            fb = [r for r in regions if r.id == policy.fallback_region_id]
            if fb:
                return fb[0], "failover: fallback region"
        return regions[0], "failover: best available"

    @staticmethod
    def _strat_capacity(regions: List[Region]) -> tuple[Region, str]:
        best = max(regions, key=lambda r: (1 - r.current_load) * r.capacity_weight)
        return best, "capacity_based: most remaining capacity"

    def _fallback_decision(self, policy: RoutingPolicy, lat: float, lon: float) -> Optional[RoutingDecision]:
        """Return a fallback decision when no healthy regions exist."""
        fb_id = policy.fallback_region_id
        region = self._regions.get(fb_id) if fb_id else None
        if not region:
            return None
        return RoutingDecision(
            policy_id=policy.id, source_lat=lat, source_lon=lon,
            selected_region_id=region.id, reason="fallback: no healthy regions",
        )

    def _pick_node(self, region_id: str) -> Optional[EdgeNode]:
        """Pick the best healthy node in a region."""
        nodes = [
            n for n in self._nodes.values()
            if n.region_id == region_id and n.status == NodeStatus.healthy
        ]
        if not nodes:
            return None
        return max(nodes, key=lambda n: n.weight)

    def create_deployment(
        self, name: str, target_regions: List[str],
        replicas_per_region: int = 1, strategy: str = "rolling",
    ) -> Optional[DeploymentSpec]:
        """Create a new deployment spec."""
        with self._lock:
            valid = [r for r in target_regions if r in self._regions]
            if not valid:
                return None
            dep = DeploymentSpec(
                name=name, target_regions=valid,
                replicas_per_region=replicas_per_region,
                strategy=DeploymentStrategy(strategy),
            )
            self._deployments[dep.id] = dep
        logger.info("Deployment created: %s", dep.id)
        return dep

    def get_deployment(self, deployment_id: str) -> Optional[DeploymentSpec]:
        """Return a deployment by id, or None."""
        with self._lock: return self._deployments.get(deployment_id)

    def list_deployments(self, status_filter: Optional[str] = None) -> List[DeploymentSpec]:
        """Return deployments, optionally filtered by status."""
        with self._lock:
            deps = list(self._deployments.values())
        if status_filter:
            deps = [d for d in deps if d.status.value == status_filter]
        return deps

    def advance_deployment(self, deployment_id: str) -> Optional[DeploymentSpec]:
        """Advance deployment progress by 25 %."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if not dep or dep.status in (
                DeploymentStatus.active, DeploymentStatus.failed,
                DeploymentStatus.rolled_back,
            ):
                return None
            dep.progress_pct = min(dep.progress_pct + 25.0, 100.0)
            dep.status = (
                DeploymentStatus.active
                if dep.progress_pct >= 100.0
                else DeploymentStatus.deploying
            )
            dep.updated_at = _now()
        return dep

    def rollback_deployment(self, deployment_id: str) -> Optional[DeploymentSpec]:
        """Roll back a deployment."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if not dep:
                return None
            dep.status = DeploymentStatus.rolled_back
            dep.progress_pct = 0.0
            dep.updated_at = _now()
        return dep

    # -- ML feedback loop (G-004) ------------------------------------------

    def record_outcome(
        self, region_id: str, latency_ms: float,
        success: bool = True, learning_rate: float = 0.05,
    ) -> Optional[Region]:
        """Record a request outcome and adjust routing weights via feedback.

        The learning loop nudges ``capacity_weight`` up for good outcomes
        (low latency + success) and down for bad outcomes.  This wires the
        ML feedback signal directly into the routing weights — closing G-004.
        """
        with self._lock:
            region = self._regions.get(region_id)
            if region is None:
                return None
            signal = self._compute_feedback(
                latency_ms, success, region.avg_latency_ms,
            )
            region.capacity_weight = max(
                0.1, region.capacity_weight + learning_rate * signal,
            )
            region.updated_at = _now()
            return region

    @staticmethod
    def _compute_feedback(
        latency_ms: float, success: bool, baseline_ms: float,
    ) -> float:
        """Pure function: compute a feedback signal in [-1, 1]."""
        if not success:
            return -1.0
        if baseline_ms <= 0:
            return 0.5
        ratio = latency_ms / max(baseline_ms, 1.0)
        if ratio < 0.8:
            return 1.0
        if ratio < 1.2:
            return 0.2
        return -0.5

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics."""
        with self._lock:
            return {
                "regions": len(self._regions),
                "nodes": len(self._nodes),
                "policies": len(self._policies),
                "deployments": len(self._deployments),
                "decisions_logged": len(self._decisions),
                "health_checks_logged": len(self._health_log),
            }

def validate_wingman_pair(storyline: str, actuals: str) -> dict:
    """GLB-001 Wingman gate.

    Validate that a storyline and actuals pair is non-empty and coherent.
    Returns a pass/fail dict with diagnostics.
    """
    if not storyline or not storyline.strip():
        return {"passed": False, "message": "Storyline is empty"}
    if not actuals or not actuals.strip():
        return {"passed": False, "message": "Actuals data is empty"}
    sl, al = len(storyline.strip()), len(actuals.strip())
    ratio = max(sl, al) / max(min(sl, al), 1)  # guard against zero-length
    if ratio > 50:
        return {
            "passed": False,
            "message": f"Length mismatch ratio {ratio:.1f} exceeds threshold",
        }
    return {"passed": True, "message": "Wingman pair validated",
            "storyline_len": sl, "actuals_len": al}

def gate_glb_in_sandbox(action: str, metadata: dict) -> dict:
    """GLB-001 Causality Sandbox gate.

    Verify that a GLB action is permitted inside the sandbox and that
    required metadata keys are present.
    """
    forbidden = {"drop_region", "delete_all_nodes", "shutdown", "exec_raw"}
    if action in forbidden:
        return {"passed": False,
                "message": f"Action '{action}' is forbidden in sandbox"}
    required_keys = {"region_id", "triggered_by"}
    missing = required_keys - set(metadata.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing metadata keys: {sorted(missing)}"}
    if not metadata.get("region_id"):
        return {"passed": False, "message": "region_id must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed", "action": action}

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"{k} required", "code": "GLB_MISSING"}), 400
    return None

def create_glb_api(engine: GeographicLoadBalancer) -> Any:
    """Create a Flask Blueprint exposing geographic load-balancing endpoints.

    All routes live under ``/api`` and return JSON with an error envelope
    ``{"error": "…", "code": "GLB_*"}`` on failure.
    """
    if not _HAS_FLASK:
        return Blueprint("glb_api", __name__)  # type: ignore[call-arg]
    bp = Blueprint("glb_api", __name__, url_prefix="/api")
    _register_region_routes(bp, engine)
    _register_node_routes(bp, engine)
    _register_policy_routes(bp, engine)
    _register_deployment_routes(bp, engine)
    _register_misc_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp

def _register_region_routes(bp: Any, eng: GeographicLoadBalancer) -> None:
    """Register region CRUD endpoints."""
    @bp.route("/glb/regions", methods=["POST"])
    def add_region() -> Any:
        b = _api_body()
        err = _api_need(b, "name", "latitude", "longitude")
        if err:
            return err
        r = eng.add_region(
            b["name"], float(b["latitude"]), float(b["longitude"]),
            capacity_weight=float(b.get("capacity_weight", 1.0)),
            max_connections=int(b.get("max_connections", 1000)),
            tags=b.get("tags"),
        )
        return jsonify(r.to_dict()), 201

    @bp.route("/glb/regions", methods=["GET"])
    def list_regions() -> Any:
        status = request.args.get("status")
        return jsonify([r.to_dict() for r in eng.list_regions(status)])

    @bp.route("/glb/regions/<region_id>", methods=["GET"])
    def get_region(region_id: str) -> Any:
        r = eng.get_region(region_id)
        if not r:
            return jsonify({"error": "Not found", "code": "GLB_404"}), 404
        return jsonify(r.to_dict())

    @bp.route("/glb/regions/<region_id>/load", methods=["PUT"])
    def update_load(region_id: str) -> Any:
        b = _api_body()
        err = _api_need(b, "current_load", "active_connections", "avg_latency_ms")
        if err:
            return err
        r = eng.update_region_load(
            region_id, float(b["current_load"]),
            int(b["active_connections"]), float(b["avg_latency_ms"]),
        )
        if not r:
            return jsonify({"error": "Not found", "code": "GLB_404"}), 404
        return jsonify(r.to_dict())

    @bp.route("/glb/regions/<region_id>", methods=["DELETE"])
    def remove_region(region_id: str) -> Any:
        if not eng.remove_region(region_id):
            return jsonify({"error": "Not found", "code": "GLB_404"}), 404
        return jsonify({"deleted": region_id})

def _register_node_routes(bp: Any, eng: GeographicLoadBalancer) -> None:
    """Register edge-node endpoints."""
    @bp.route("/glb/nodes", methods=["POST"])
    def add_node() -> Any:
        b = _api_body()
        err = _api_need(b, "region_id", "name", "endpoint_url")
        if err:
            return err
        n = eng.add_edge_node(
            b["region_id"], b["name"], b["endpoint_url"],
            weight=float(b.get("weight", 1.0)),
            max_rps=float(b.get("max_rps", 1000.0)),
            health_check_url=b.get("health_check_url"),
        )
        if not n:
            return jsonify({"error": "Region not found", "code": "GLB_404"}), 404
        return jsonify(n.to_dict()), 201

    @bp.route("/glb/nodes", methods=["GET"])
    def list_nodes() -> Any:
        rid = request.args.get("region_id")
        return jsonify([n.to_dict() for n in eng.list_edge_nodes(rid)])

    @bp.route("/glb/nodes/<node_id>", methods=["GET"])
    def get_node(node_id: str) -> Any:
        n = eng.get_edge_node(node_id)
        if not n:
            return jsonify({"error": "Not found", "code": "GLB_404"}), 404
        return jsonify(n.to_dict())

    @bp.route("/glb/nodes/<node_id>", methods=["DELETE"])
    def remove_node(node_id: str) -> Any:
        if not eng.remove_edge_node(node_id):
            return jsonify({"error": "Not found", "code": "GLB_404"}), 404
        return jsonify({"deleted": node_id})

    @bp.route("/glb/nodes/<node_id>/health", methods=["POST"])
    def health_check(node_id: str) -> Any:
        b = _api_body()
        err = _api_need(b, "status", "latency_ms")
        if err:
            return err
        hc = eng.record_health_check(
            node_id, b["status"], float(b["latency_ms"]), b.get("details"),
        )
        if not hc:
            return jsonify({"error": "Node not found", "code": "GLB_404"}), 404
        return jsonify(hc.to_dict()), 201

def _register_policy_routes(bp: Any, eng: GeographicLoadBalancer) -> None:
    """Register routing-policy and routing endpoints."""
    @bp.route("/glb/policies", methods=["POST"])
    def create_policy() -> Any:
        b = _api_body()
        err = _api_need(b, "name", "strategy")
        if err:
            return err
        p = eng.create_routing_policy(
            b["name"], b["strategy"],
            fallback_region_id=b.get("fallback_region_id"),
            sticky_sessions=bool(b.get("sticky_sessions", False)),
            health_threshold=float(b.get("health_threshold", 0.5)),
        )
        return jsonify(p.to_dict()), 201

    @bp.route("/glb/policies", methods=["GET"])
    def list_policies() -> Any:
        return jsonify([p.to_dict() for p in eng.list_routing_policies()])

    @bp.route("/glb/route", methods=["POST"])
    def route_req() -> Any:
        b = _api_body()
        err = _api_need(b, "policy_id", "source_lat", "source_lon")
        if err:
            return err
        d = eng.route_request(
            b["policy_id"], float(b["source_lat"]), float(b["source_lon"]),
        )
        if not d:
            return jsonify({"error": "Routing failed", "code": "GLB_ROUTE"}), 404
        return jsonify(d.to_dict())

def _register_deployment_routes(bp: Any, eng: GeographicLoadBalancer) -> None:
    """Register deployment endpoints."""
    @bp.route("/glb/deployments", methods=["POST"])
    def create_deploy() -> Any:
        b = _api_body()
        err = _api_need(b, "name", "target_regions")
        if err:
            return err
        d = eng.create_deployment(
            b["name"], b["target_regions"],
            replicas_per_region=int(b.get("replicas_per_region", 1)),
            strategy=b.get("strategy", "rolling"),
        )
        if not d:
            return jsonify({"error": "No valid regions", "code": "GLB_DEPLOY"}), 400
        return jsonify(d.to_dict()), 201

    @bp.route("/glb/deployments", methods=["GET"])
    def list_deploys() -> Any:
        sf = request.args.get("status")
        return jsonify([d.to_dict() for d in eng.list_deployments(sf)])

    @bp.route("/glb/deployments/<dep_id>", methods=["GET"])
    def get_deploy(dep_id: str) -> Any:
        d = eng.get_deployment(dep_id)
        if not d:
            return jsonify({"error": "Not found", "code": "GLB_404"}), 404
        return jsonify(d.to_dict())

    @bp.route("/glb/deployments/<dep_id>/advance", methods=["POST"])
    def advance(dep_id: str) -> Any:
        d = eng.advance_deployment(dep_id)
        if not d:
            return jsonify({"error": "Cannot advance", "code": "GLB_STATE"}), 409
        return jsonify(d.to_dict())

    @bp.route("/glb/deployments/<dep_id>/rollback", methods=["POST"])
    def rollback(dep_id: str) -> Any:
        d = eng.rollback_deployment(dep_id)
        if not d:
            return jsonify({"error": "Not found", "code": "GLB_404"}), 404
        return jsonify(d.to_dict())

def _register_misc_routes(bp: Any, eng: GeographicLoadBalancer) -> None:
    """Register stats and health endpoints."""
    @bp.route("/glb/stats", methods=["GET"])
    def stats() -> Any:
        return jsonify(eng.get_stats())

    @bp.route("/glb/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"status": "healthy", "module": "GLB-001"})
