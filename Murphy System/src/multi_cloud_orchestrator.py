# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Multi-cloud Orchestrator — MCO-001

Owner: Infrastructure · Dep: threading, uuid, dataclasses
Deploy and manage Murphy across AWS, GCP, Azure simultaneously.
Register cloud accounts, track managed resources across providers,
coordinate multi-region deployments, execute cross-cloud operations,
monitor health, and aggregate cost allocations per platform.
``create_multi_cloud_api(orchestrator)`` → Flask Blueprint.
Safety: every mutation under ``threading.Lock``; bounded via capped_append.
"""
from __future__ import annotations

import logging
import random
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

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
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 50_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)
# -- Enums -----------------------------------------------------------------

class CloudPlatform(str, Enum):
    """Supported cloud platforms."""
    aws = "aws"; gcp = "gcp"; azure = "azure"
    oracle = "oracle"; ibm = "ibm"; other = "other"

class DeploymentStatus(str, Enum):
    """Lifecycle status of a deployment."""
    pending = "pending"; provisioning = "provisioning"; running = "running"
    degraded = "degraded"; stopped = "stopped"; failed = "failed"
    terminated = "terminated"

class ResourceType(str, Enum):
    """Kind of managed cloud resource."""
    compute = "compute"; storage = "storage"; network = "network"
    database = "database"; container = "container"; function = "function"
    queue = "queue"; cache = "cache"; other = "other"

class RegionStatus(str, Enum):
    """Availability status of a cloud region."""
    available = "available"; degraded = "degraded"; unavailable = "unavailable"

class OperationType(str, Enum):
    """Type of orchestration operation."""
    deploy = "deploy"; scale = "scale"; migrate = "migrate"
    failover = "failover"; terminate = "terminate"; update = "update"
    rollback = "rollback"
# -- Dataclass models ------------------------------------------------------

@dataclass
class CloudAccount:
    """A registered cloud provider account."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    platform: str = "aws"
    account_id: str = ""
    alias: str = ""
    region: str = ""
    credentials_ref: str = ""
    enabled: bool = True
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class ManagedResource:
    """A cloud resource tracked by the orchestrator."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    account_id: str = ""
    platform: str = "aws"
    resource_type: str = "compute"
    name: str = ""
    region: str = ""
    status: str = "running"
    config: Dict[str, Any] = field(default_factory=dict)
    cost_per_hour: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class Deployment:
    """A multi-cloud deployment spanning one or more platforms."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    description: str = ""
    platforms: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    resource_ids: List[str] = field(default_factory=list)
    status: str = "pending"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class CloudOperation:
    """A recorded orchestration operation."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    deployment_id: str = ""
    operation_type: str = "deploy"
    platform: str = "aws"
    region: str = ""
    status: str = "pending"
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=_now)
    completed_at: str = ""
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class HealthCheck:
    """A health-check probe result for a cloud account."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    account_id: str = ""
    platform: str = "aws"
    region: str = ""
    status: str = "available"
    latency_ms: float = 0.0
    message: str = ""
    checked_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class CostAllocation:
    """A cost allocation entry for a deployment."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    deployment_id: str = ""
    platform: str = "aws"
    amount: float = 0.0
    currency: str = "USD"
    period: str = ""
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)
# -- Engine ----------------------------------------------------------------

class MultiCloudOrchestrator:
    """Thread-safe multi-cloud orchestration engine."""

    def __init__(self, max_accounts: int = 10_000,
                 max_resources: int = 50_000) -> None:
        self._lock = threading.Lock()
        self._accounts: Dict[str, CloudAccount] = {}
        self._resources: Dict[str, ManagedResource] = {}
        self._deployments: Dict[str, Deployment] = {}
        self._operations: List[CloudOperation] = []
        self._health_checks: List[HealthCheck] = []
        self._costs: List[CostAllocation] = []
        self._history: List[dict] = []
        self._max_accounts = max_accounts
        self._max_resources = max_resources
    # -- Account management -------------------------------------------------

    def register_account(
        self, platform: Union[str, CloudPlatform],
        account_id: str, alias: str = "",
        region: str = "", credentials_ref: str = "",
        enabled: bool = True,
    ) -> CloudAccount:
        """Register a cloud provider account for orchestration."""
        acct = CloudAccount(
            platform=_enum_val(platform), account_id=account_id,
            alias=alias or account_id, region=region,
            credentials_ref=credentials_ref, enabled=enabled,
        )
        with self._lock:
            if len(self._accounts) >= self._max_accounts:
                oldest = next(iter(self._accounts))
                del self._accounts[oldest]
            self._accounts[acct.id] = acct
            capped_append(self._history, {"action": "register_account",
                          "account": acct.id, "ts": _now()}, 50_000)
        return acct

    def get_account(self, account_id: str) -> Optional[CloudAccount]:
        """Look up an account by internal ID."""
        with self._lock:
            return self._accounts.get(account_id)

    def list_accounts(
        self, platform: Optional[str] = None,
        enabled: Optional[bool] = None,
        limit: int = 100,
    ) -> List[CloudAccount]:
        """List accounts with optional filters."""
        with self._lock:
            accounts = list(self._accounts.values())
        if platform:
            pv = _enum_val(platform)
            accounts = [a for a in accounts if a.platform == pv]
        if enabled is not None:
            accounts = [a for a in accounts if a.enabled is enabled]
        return accounts[:limit]

    def delete_account(self, account_id: str) -> bool:
        """Remove an account from the orchestrator."""
        with self._lock:
            return self._accounts.pop(account_id, None) is not None
    # -- Resource management ------------------------------------------------

    def register_resource(
        self, account_id: str, name: str,
        resource_type: Union[str, ResourceType] = "compute",
        region: str = "", status: Union[str, DeploymentStatus] = "running",
        config: Optional[Dict[str, Any]] = None,
        cost_per_hour: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ManagedResource:
        """Register a managed resource under a cloud account."""
        with self._lock:
            acct = self._accounts.get(account_id)
            plat = acct.platform if acct else "other"
        res = ManagedResource(
            account_id=account_id, platform=plat,
            resource_type=_enum_val(resource_type),
            name=name, region=region, status=_enum_val(status),
            config=config or {}, cost_per_hour=max(0.0, cost_per_hour),
            metadata=metadata or {},
        )
        with self._lock:
            if len(self._resources) >= self._max_resources:
                oldest = next(iter(self._resources))
                del self._resources[oldest]
            self._resources[res.id] = res
            capped_append(self._history, {"action": "register_resource",
                          "resource": res.id, "ts": _now()}, 50_000)
        return res

    def get_resource(self, resource_id: str) -> Optional[ManagedResource]:
        """Look up a resource by ID."""
        with self._lock:
            return self._resources.get(resource_id)

    def list_resources(
        self, platform: Optional[str] = None,
        status: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ManagedResource]:
        """List resources with optional platform/status/type filters."""
        with self._lock:
            resources = list(self._resources.values())
        if platform:
            pv = _enum_val(platform)
            resources = [r for r in resources if r.platform == pv]
        if status:
            sv = _enum_val(status)
            resources = [r for r in resources if r.status == sv]
        if resource_type:
            rt = _enum_val(resource_type)
            resources = [r for r in resources if r.resource_type == rt]
        return resources[:limit]

    def update_resource_status(
        self, resource_id: str,
        status: Union[str, DeploymentStatus],
    ) -> Optional[ManagedResource]:
        """Update the status of a managed resource."""
        sv = _enum_val(status)
        with self._lock:
            res = self._resources.get(resource_id)
            if res is None:
                return None
            res.status = sv
        return res

    def delete_resource(self, resource_id: str) -> bool:
        """Remove a managed resource."""
        with self._lock:
            return self._resources.pop(resource_id, None) is not None
    # -- Deployments --------------------------------------------------------

    def create_deployment(
        self, name: str, description: str = "",
        platforms: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
    ) -> Deployment:
        """Create a new multi-cloud deployment."""
        dep = Deployment(
            name=name, description=description,
            platforms=[_enum_val(p) for p in (platforms or [])],
            regions=list(regions or []),
            resource_ids=list(resource_ids or []),
            status="pending",
        )
        with self._lock:
            self._deployments[dep.id] = dep
            capped_append(self._history, {"action": "create_deployment",
                          "deployment": dep.id, "ts": _now()}, 50_000)
        return dep

    def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Look up a deployment by ID."""
        with self._lock:
            return self._deployments.get(deployment_id)

    def list_deployments(
        self, status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Deployment]:
        """List deployments with optional status filter."""
        with self._lock:
            deployments = list(self._deployments.values())
        if status:
            sv = _enum_val(status)
            deployments = [d for d in deployments if d.status == sv]
        return deployments[:limit]

    def update_deployment_status(
        self, deployment_id: str,
        status: Union[str, DeploymentStatus],
    ) -> Optional[Deployment]:
        """Update the status of a deployment."""
        sv = _enum_val(status)
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return None
            dep.status = sv
            dep.updated_at = _now()
        return dep
    # -- Operations ---------------------------------------------------------

    def execute_operation(
        self, deployment_id: str,
        operation_type: Union[str, OperationType],
        platform: Union[str, CloudPlatform] = "aws",
        region: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> CloudOperation:
        """Record and execute a cloud orchestration operation."""
        op = CloudOperation(
            deployment_id=deployment_id,
            operation_type=_enum_val(operation_type),
            platform=_enum_val(platform),
            region=region, status="running",
            parameters=parameters or {},
        )
        # Simulate execution outcome
        op.result = self._simulate_operation(op)
        op.status = op.result.get("outcome", "completed")
        op.completed_at = _now()
        with self._lock:
            capped_append(self._operations, op, self._max_resources)
            capped_append(self._history, {"action": "execute_operation",
                          "operation": op.id, "ts": _now()}, 50_000)
        return op

    @staticmethod
    def _simulate_operation(op: CloudOperation) -> Dict[str, Any]:
        """Simulate an operation result (deterministic for tests)."""
        return {"outcome": "completed", "operation_type": op.operation_type,
                "platform": op.platform, "region": op.region or "us-east-1",
                "message": f"{op.operation_type} on {op.platform} succeeded"}

    def list_operations(
        self, deployment_id: Optional[str] = None,
        platform: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[CloudOperation]:
        """List operations with optional filters."""
        with self._lock:
            ops = list(self._operations)
        if deployment_id:
            ops = [o for o in ops if o.deployment_id == deployment_id]
        if platform:
            pv = _enum_val(platform)
            ops = [o for o in ops if o.platform == pv]
        if operation_type:
            ot = _enum_val(operation_type)
            ops = [o for o in ops if o.operation_type == ot]
        return ops[-limit:]
    # -- Health checks ------------------------------------------------------

    def run_health_check(self, account_id: str) -> HealthCheck:
        """Simulate a health-check probe against a cloud account."""
        with self._lock:
            acct = self._accounts.get(account_id)
        if acct is None:
            return HealthCheck(
                account_id=account_id, platform="unknown",
                status="unavailable", latency_ms=0.0,
                message="Account not found",
            )
        latency = round(random.uniform(5.0, 150.0), 2)  # noqa: S311
        if latency > 120.0:
            status_val = "degraded"
            msg = f"High latency detected: {latency}ms"
        else:
            status_val = "available"
            msg = f"Account {acct.alias} reachable ({latency}ms)"
        hc = HealthCheck(
            account_id=account_id, platform=acct.platform,
            region=acct.region, status=status_val,
            latency_ms=latency, message=msg,
        )
        with self._lock:
            capped_append(self._health_checks, hc, self._max_resources)
        return hc

    def list_health_checks(
        self, account_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[HealthCheck]:
        """List health-check results with optional account filter."""
        with self._lock:
            checks = list(self._health_checks)
        if account_id:
            checks = [c for c in checks if c.account_id == account_id]
        return checks[-limit:]
    # -- Cost allocation ----------------------------------------------------

    def record_cost(
        self, deployment_id: str,
        platform: Union[str, CloudPlatform],
        amount: float, period: str,
        currency: str = "USD",
    ) -> CostAllocation:
        """Record a cost allocation against a deployment."""
        entry = CostAllocation(
            deployment_id=deployment_id,
            platform=_enum_val(platform),
            amount=round(amount, 2),
            currency=currency, period=period,
        )
        with self._lock:
            capped_append(self._costs, entry, self._max_resources)
            capped_append(self._history, {"action": "record_cost",
                          "deployment": deployment_id, "ts": _now()}, 50_000)
        return entry

    def get_cost_summary(self) -> Dict[str, Any]:
        """Aggregate cost allocations by platform."""
        with self._lock:
            costs = list(self._costs)
        by_platform: Dict[str, float] = {}
        total = 0.0
        for c in costs:
            by_platform[c.platform] = by_platform.get(c.platform, 0.0) + c.amount
            total += c.amount
        return {"total": round(total, 2),
                "by_platform": {k: round(v, 2) for k, v in by_platform.items()},
                "entry_count": len(costs), "generated_at": _now()}

    def list_costs(
        self, deployment_id: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 100,
    ) -> List[CostAllocation]:
        """List cost allocations with optional filters."""
        with self._lock:
            costs = list(self._costs)
        if deployment_id:
            costs = [c for c in costs if c.deployment_id == deployment_id]
        if platform:
            pv = _enum_val(platform)
            costs = [c for c in costs if c.platform == pv]
        return costs[-limit:]
    # -- Export / clear -----------------------------------------------------

    def export_state(self) -> dict:
        """Serialise orchestrator state to a plain dict."""
        with self._lock:
            return {"accounts": {aid: a.to_dict()
                                 for aid, a in self._accounts.items()},
                    "resources": {rid: r.to_dict()
                                  for rid, r in self._resources.items()},
                    "deployments": {did: d.to_dict()
                                    for did, d in self._deployments.items()},
                    "operations": [o.to_dict() for o in self._operations],
                    "health_checks": [h.to_dict() for h in self._health_checks],
                    "costs": [c.to_dict() for c in self._costs],
                    "exported_at": _now()}

    def clear(self) -> None:
        """Remove all state."""
        with self._lock:
            self._accounts.clear()
            self._resources.clear()
            self._deployments.clear()
            self._operations.clear()
            self._health_checks.clear()
            self._costs.clear()
            capped_append(self._history, {"action": "clear", "ts": _now()},
                          50_000)
# -- Wingman & Sandbox gates -----------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """MCO-001 Wingman gate."""
    if not storyline:
        return {"passed": False, "message": "Storyline list is empty"}
    if not actuals:
        return {"passed": False, "message": "Actuals list is empty"}
    if len(storyline) != len(actuals):
        return {"passed": False,
                "message": f"Length mismatch: storyline={len(storyline)} "
                           f"actuals={len(actuals)}"}
    mismatches: List[int] = [
        i for i, (s, a) in enumerate(zip(storyline, actuals)) if s != a
    ]
    if mismatches:
        return {"passed": False,
                "message": f"Pair mismatches at indices {mismatches}"}
    return {"passed": True, "message": "Wingman pair validated",
            "pair_count": len(storyline)}


def gate_mco_in_sandbox(context: dict) -> dict:
    """MCO-001 Causality Sandbox gate."""
    required_keys = {"platform"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("platform"):
        return {"passed": False, "message": "platform must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "platform": context["platform"]}
# -- Flask Blueprint factory -----------------------------------------------

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k) and body.get(k) != 0:
            return jsonify({"error": f"Missing required field: {k}",
                            "code": "MISSING_FIELD"}), 400
    return None

def _not_found(msg: str) -> Any:
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404

def create_multi_cloud_api(
    orchestrator: MultiCloudOrchestrator,
) -> Any:
    """Create a Flask Blueprint with multi-cloud orchestration endpoints."""
    bp = Blueprint("mco", __name__, url_prefix="/api")
    eng = orchestrator

    @bp.route("/mco/accounts", methods=["POST"])
    def register_account() -> Any:
        body = _api_body()
        err = _api_need(body, "platform", "account_id")
        if err:
            return err
        acct = eng.register_account(
            platform=body["platform"], account_id=body["account_id"],
            alias=body.get("alias", ""), region=body.get("region", ""),
            credentials_ref=body.get("credentials_ref", ""),
            enabled=body.get("enabled", True))
        return jsonify(acct.to_dict()), 201

    @bp.route("/mco/accounts", methods=["GET"])
    def list_accounts() -> Any:
        a = request.args
        enabled = None
        if "enabled" in a:
            enabled = a.get("enabled", "").lower() == "true"
        accounts = eng.list_accounts(
            platform=a.get("platform"),
            enabled=enabled,
            limit=int(a.get("limit", 100)),
        )
        return jsonify([ac.to_dict() for ac in accounts]), 200

    @bp.route("/mco/accounts/<account_id>", methods=["GET"])
    def get_account(account_id: str) -> Any:
        acct = eng.get_account(account_id)
        if acct is None:
            return _not_found("Account not found")
        return jsonify(acct.to_dict()), 200

    @bp.route("/mco/accounts/<account_id>", methods=["DELETE"])
    def delete_account(account_id: str) -> Any:
        if not eng.delete_account(account_id):
            return _not_found("Account not found")
        return jsonify({"deleted": True}), 200

    @bp.route("/mco/resources", methods=["POST"])
    def register_resource() -> Any:
        body = _api_body()
        err = _api_need(body, "account_id", "name")
        if err:
            return err
        res = eng.register_resource(
            account_id=body["account_id"], name=body["name"],
            resource_type=body.get("resource_type", "compute"),
            region=body.get("region", ""), status=body.get("status", "running"),
            config=body.get("config", {}),
            cost_per_hour=float(body.get("cost_per_hour", 0)),
            metadata=body.get("metadata", {}))
        return jsonify(res.to_dict()), 201

    @bp.route("/mco/resources", methods=["GET"])
    def list_resources() -> Any:
        a = request.args
        resources = eng.list_resources(
            platform=a.get("platform"),
            status=a.get("status"),
            resource_type=a.get("resource_type"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in resources]), 200

    @bp.route("/mco/resources/<resource_id>", methods=["GET"])
    def get_resource(resource_id: str) -> Any:
        res = eng.get_resource(resource_id)
        if res is None:
            return _not_found("Resource not found")
        return jsonify(res.to_dict()), 200

    @bp.route("/mco/resources/<resource_id>", methods=["PUT"])
    def update_resource_status(resource_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "status")
        if err:
            return err
        res = eng.update_resource_status(resource_id, body["status"])
        if res is None:
            return _not_found("Resource not found")
        return jsonify(res.to_dict()), 200

    @bp.route("/mco/resources/<resource_id>", methods=["DELETE"])
    def delete_resource(resource_id: str) -> Any:
        if not eng.delete_resource(resource_id):
            return _not_found("Resource not found")
        return jsonify({"deleted": True}), 200

    @bp.route("/mco/deployments", methods=["POST"])
    def create_deployment() -> Any:
        body = _api_body()
        err = _api_need(body, "name")
        if err:
            return err
        dep = eng.create_deployment(
            name=body["name"], description=body.get("description", ""),
            platforms=body.get("platforms", []),
            regions=body.get("regions", []),
            resource_ids=body.get("resource_ids", []))
        return jsonify(dep.to_dict()), 201

    @bp.route("/mco/deployments", methods=["GET"])
    def list_deployments() -> Any:
        a = request.args
        deployments = eng.list_deployments(
            status=a.get("status"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([d.to_dict() for d in deployments]), 200

    @bp.route("/mco/deployments/<deployment_id>", methods=["GET"])
    def get_deployment(deployment_id: str) -> Any:
        dep = eng.get_deployment(deployment_id)
        if dep is None:
            return _not_found("Deployment not found")
        return jsonify(dep.to_dict()), 200

    @bp.route("/mco/deployments/<deployment_id>", methods=["PUT"])
    def update_deployment_status(deployment_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "status")
        if err:
            return err
        dep = eng.update_deployment_status(deployment_id, body["status"])
        if dep is None:
            return _not_found("Deployment not found")
        return jsonify(dep.to_dict()), 200

    @bp.route("/mco/operations", methods=["POST"])
    def execute_operation() -> Any:
        body = _api_body()
        err = _api_need(body, "deployment_id", "operation_type")
        if err:
            return err
        op = eng.execute_operation(
            deployment_id=body["deployment_id"],
            operation_type=body["operation_type"],
            platform=body.get("platform", "aws"),
            region=body.get("region", ""), parameters=body.get("parameters", {}))
        return jsonify(op.to_dict()), 201

    @bp.route("/mco/operations", methods=["GET"])
    def list_operations() -> Any:
        a = request.args
        ops = eng.list_operations(
            deployment_id=a.get("deployment_id"),
            platform=a.get("platform"),
            operation_type=a.get("operation_type"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([o.to_dict() for o in ops]), 200

    @bp.route("/mco/health/<account_id>", methods=["POST"])
    def run_health_check(account_id: str) -> Any:
        hc = eng.run_health_check(account_id)
        return jsonify(hc.to_dict()), 200

    @bp.route("/mco/health", methods=["GET"])
    def list_health_checks() -> Any:
        a = request.args
        checks = eng.list_health_checks(
            account_id=a.get("account_id"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([c.to_dict() for c in checks]), 200

    @bp.route("/mco/costs", methods=["POST"])
    def record_cost() -> Any:
        body = _api_body()
        err = _api_need(body, "deployment_id", "platform", "amount", "period")
        if err:
            return err
        entry = eng.record_cost(
            deployment_id=body["deployment_id"], platform=body["platform"],
            amount=float(body["amount"]), period=body["period"],
            currency=body.get("currency", "USD"))
        return jsonify(entry.to_dict()), 201

    @bp.route("/mco/costs", methods=["GET"])
    def list_costs() -> Any:
        a = request.args
        costs = eng.list_costs(
            deployment_id=a.get("deployment_id"),
            platform=a.get("platform"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([c.to_dict() for c in costs]), 200

    @bp.route("/mco/costs/summary", methods=["GET"])
    def cost_summary() -> Any:
        return jsonify(eng.get_cost_summary()), 200

    @bp.route("/mco/export", methods=["POST"])
    def export_state() -> Any:
        return jsonify(eng.export_state()), 200

    @bp.route("/mco/health/status", methods=["GET"])
    def module_health() -> Any:
        return jsonify({"status": "healthy", "module": "MCO-001",
                        "registered_accounts": len(eng.list_accounts()),
                        "managed_resources": len(eng.list_resources()),
                        "active_deployments": len(eng.list_deployments())}), 200

    return bp
