# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Multi-Cloud Orchestrator — MCO-001

Owner: Infrastructure · Dep: threading, uuid, dataclasses

Deploy and manage Murphy across AWS, GCP, Azure simultaneously.
Register cloud providers, manage deployments across regions, configure
failover strategies, synchronise resources, and track costs.
``create_multi_cloud_api(orchestrator)`` → Flask Blueprint.
Safety: every mutation under ``threading.Lock``; bounded via capped_append.
"""
from __future__ import annotations

import logging
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
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append, capped_append_paired
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
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

class CloudProvider(str, Enum):
    """Supported cloud providers."""
    aws = "aws"; gcp = "gcp"; azure = "azure"; custom = "custom"

class DeploymentStatus(str, Enum):
    """Lifecycle status of a cloud deployment."""
    pending = "pending"; deploying = "deploying"; running = "running"
    failed = "failed"; stopped = "stopped"; draining = "draining"

class HealthState(str, Enum):
    """Health state of a deployment."""
    healthy = "healthy"; degraded = "degraded"
    unhealthy = "unhealthy"; unknown = "unknown"

class FailoverStrategy(str, Enum):
    """Failover routing strategy."""
    active_passive = "active_passive"; active_active = "active_active"
    round_robin = "round_robin"; cost_based = "cost_based"
    latency_based = "latency_based"
# -- Dataclass models ------------------------------------------------------

@dataclass
class ProviderConfig:
    """Cloud provider configuration. credentials_ref is a SecureKeyManager reference, NOT an actual secret."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    provider: str = "aws"
    region: str = ""
    credentials_ref: str = ""  # SecureKeyManager key reference only
    endpoint: str = ""
    enabled: bool = True
    priority: int = 0
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # noqa: D102

@dataclass
class CloudDeployment:
    """Deployment across a cloud provider. env_vars must NOT contain secrets."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    provider: str = "aws"
    region: str = ""
    status: str = "pending"
    config_id: str = ""
    replicas: int = 1
    cpu_limit: str = "1000m"
    memory_limit: str = "512Mi"
    image: str = ""
    env_vars: Dict[str, str] = field(default_factory=dict)
    health_state: str = "unknown"
    last_health_check: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # noqa: D102

@dataclass
class FailoverRule:
    """Failover rule between two cloud providers."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    primary_provider: str = ""
    secondary_provider: str = ""
    strategy: str = "active_passive"
    threshold_ms: int = 5000
    max_retries: int = 3
    cooldown_sec: int = 60
    enabled: bool = True
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # noqa: D102

@dataclass
class SyncTask:
    """Resource synchronisation task between providers."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_provider: str = ""
    target_provider: str = ""
    resource_type: str = ""
    status: str = "pending"
    started_at: str = field(default_factory=_now)
    completed_at: str = ""
    items_synced: int = 0
    errors: List[str] = field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # noqa: D102

@dataclass
class CostRecord:
    """Cloud cost record for a service in a region."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    provider: str = ""
    region: str = ""
    service: str = ""
    amount: float = 0.0
    currency: str = "USD"
    period_start: str = ""
    period_end: str = ""
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # noqa: D102
# -- Engine ----------------------------------------------------------------

class MultiCloudOrchestrator:
    """Thread-safe multi-cloud orchestrator."""
    def __init__(self, max_providers: int = 100,
                 max_deployments: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._providers: Dict[str, ProviderConfig] = {}
        self._deployments: Dict[str, CloudDeployment] = {}
        self._failover_rules: Dict[str, FailoverRule] = {}
        self._syncs: Dict[str, SyncTask] = {}
        self._costs: List[CostRecord] = []
        self._history: List[dict] = []
        self._max_providers = max_providers
        self._max_deployments = max_deployments
    # -- Provider CRUD ------------------------------------------------------

    def register_provider(
        self, name: str, provider: Union[str, CloudProvider],
        region: str, credentials_ref: str = "", endpoint: str = "",
        enabled: bool = True, priority: int = 0,
        tags: Optional[Dict[str, str]] = None,
    ) -> ProviderConfig:
        """Register a new cloud provider configuration."""
        cfg = ProviderConfig(
            name=name, provider=_enum_val(provider), region=region,
            credentials_ref=credentials_ref, endpoint=endpoint,
            enabled=enabled, priority=priority, tags=tags or {},)
        with self._lock:
            self._providers[cfg.id] = cfg
            capped_append(self._history,
                          {"action": "register_provider", "provider_id": cfg.id,
                           "ts": _now()}, 50_000)
        return cfg
    def get_provider(self, provider_id: str) -> Optional[ProviderConfig]:
        """Return a provider by id, or None."""
        with self._lock:
            return self._providers.get(provider_id)
    def list_providers(
        self, provider: Optional[str] = None,
        enabled: Optional[bool] = None, limit: int = 100,
    ) -> List[ProviderConfig]:
        """Return providers filtered by optional criteria."""
        with self._lock:
            out = list(self._providers.values())
        if provider:
            out = [p for p in out if p.provider == provider]
        if enabled is not None:
            out = [p for p in out if p.enabled is enabled]
        return out[:limit]
    def update_provider(
        self, provider_id: str,
        enabled: Optional[bool] = None, region: Optional[str] = None,
        priority: Optional[int] = None, endpoint: Optional[str] = None,
    ) -> Optional[ProviderConfig]:
        """Update mutable fields of a provider."""
        with self._lock:
            cfg = self._providers.get(provider_id)
            if cfg is None:
                return None
            if enabled is not None:
                cfg.enabled = enabled
            if region is not None:
                cfg.region = region
            if priority is not None:
                cfg.priority = priority
            if endpoint is not None:
                cfg.endpoint = endpoint
            cfg.updated_at = _now()
            capped_append(self._history,
                          {"action": "update_provider",
                           "provider_id": provider_id, "ts": _now()}, 50_000)
        return cfg
    def remove_provider(self, provider_id: str) -> bool:
        """Remove a provider by id. Return True if found."""
        with self._lock:
            if provider_id not in self._providers:
                return False
            del self._providers[provider_id]
            capped_append(self._history,
                          {"action": "remove_provider",
                           "provider_id": provider_id, "ts": _now()}, 50_000)
        return True
    # -- Deployment CRUD ----------------------------------------------------

    def create_deployment(
        self, name: str, provider: Union[str, CloudProvider],
        region: str, config_id: str = "", replicas: int = 1,
        cpu_limit: str = "1000m", memory_limit: str = "512Mi",
        image: str = "", env_vars: Optional[Dict[str, str]] = None,
    ) -> CloudDeployment:
        """Create a new cloud deployment."""
        dep = CloudDeployment(
            name=name, provider=_enum_val(provider), region=region,
            config_id=config_id, replicas=replicas, cpu_limit=cpu_limit,
            memory_limit=memory_limit, image=image, env_vars=env_vars or {},)
        with self._lock:
            self._deployments[dep.id] = dep
            capped_append(self._history,
                          {"action": "create_deployment",
                           "deployment_id": dep.id, "ts": _now()}, 50_000)
        return dep
    def get_deployment(self, deployment_id: str) -> Optional[CloudDeployment]:
        """Return a deployment by id, or None."""
        with self._lock:
            return self._deployments.get(deployment_id)
    def list_deployments(
        self, provider: Optional[str] = None,
        status: Optional[str] = None, limit: int = 100,
    ) -> List[CloudDeployment]:
        """Return deployments filtered by optional criteria."""
        with self._lock:
            out = list(self._deployments.values())
        if provider:
            out = [d for d in out if d.provider == provider]
        if status:
            out = [d for d in out if d.status == status]
        return out[:limit]
    def update_deployment_status(
        self, deployment_id: str, status: Union[str, DeploymentStatus],
    ) -> Optional[CloudDeployment]:
        """Update the status of a deployment."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return None
            dep.status = _enum_val(status)
            dep.updated_at = _now()
            capped_append(self._history,
                          {"action": "update_deployment_status",
                           "deployment_id": deployment_id, "ts": _now()},
                          50_000)
        return dep
    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment by id. Return True if found."""
        with self._lock:
            if deployment_id not in self._deployments:
                return False
            del self._deployments[deployment_id]
            capped_append(self._history,
                          {"action": "delete_deployment",
                           "deployment_id": deployment_id, "ts": _now()},
                          50_000)
        return True
    # -- Failover -----------------------------------------------------------

    def create_failover_rule(
        self, name: str, primary_provider: str,
        secondary_provider: str,
        strategy: Union[str, FailoverStrategy] = "active_passive",
        threshold_ms: int = 5000, max_retries: int = 3,
        cooldown_sec: int = 60, enabled: bool = True,
    ) -> FailoverRule:
        """Create a failover rule between two providers."""
        rule = FailoverRule(
            name=name, primary_provider=primary_provider,
            secondary_provider=secondary_provider,
            strategy=_enum_val(strategy), threshold_ms=threshold_ms,
            max_retries=max_retries, cooldown_sec=cooldown_sec, enabled=enabled,)
        with self._lock:
            self._failover_rules[rule.id] = rule
            capped_append(self._history,
                          {"action": "create_failover_rule",
                           "rule_id": rule.id, "ts": _now()}, 50_000)
        return rule
    def list_failover_rules(
        self, primary_provider: Optional[str] = None,
        enabled: Optional[bool] = None, limit: int = 100,
    ) -> List[FailoverRule]:
        """Return failover rules filtered by optional criteria."""
        with self._lock:
            out = list(self._failover_rules.values())
        if primary_provider:
            out = [r for r in out if r.primary_provider == primary_provider]
        if enabled is not None:
            out = [r for r in out if r.enabled is enabled]
        return out[:limit]
    def evaluate_failover(
        self, deployment_id: str,
    ) -> Dict[str, Any]:
        """Evaluate whether a failover should be triggered for a deployment."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return {"triggered": False, "reason": "Deployment not found"}
            if dep.health_state in ("healthy", "unknown"):
                return {"triggered": False,
                        "reason": "Deployment is healthy"}
            rules = list(self._failover_rules.values())
        for rule in rules:
            if rule.enabled and rule.primary_provider == dep.provider:
                return {
                    "triggered": True, "deployment_id": deployment_id,
                    "from_provider": rule.primary_provider,
                    "to_provider": rule.secondary_provider,
                    "strategy": rule.strategy, "rule_id": rule.id,
                }
        return {"triggered": False,
                "reason": "No matching failover rule"}
    # -- Sync ---------------------------------------------------------------

    def start_sync(
        self, source_provider: str, target_provider: str,
        resource_type: str, item_count: int = 0,
    ) -> SyncTask:
        """Start a resource synchronisation task."""
        task = SyncTask(
            source_provider=source_provider,
            target_provider=target_provider,
            resource_type=resource_type, status="in_progress",
            items_synced=item_count,
        )
        with self._lock:
            self._syncs[task.id] = task
            capped_append(self._history,
                          {"action": "start_sync", "sync_id": task.id,
                           "ts": _now()}, 50_000)
        return task
    def complete_sync(
        self, sync_id: str, items_synced: int = 0,
        errors: Optional[List[str]] = None,
    ) -> Optional[SyncTask]:
        """Complete a sync task, recording results."""
        with self._lock:
            task = self._syncs.get(sync_id)
            if task is None:
                return None
            task.status = "failed" if errors else "completed"
            task.completed_at = _now()
            task.items_synced = items_synced
            task.errors = errors or []
            capped_append(self._history,
                          {"action": "complete_sync", "sync_id": sync_id,
                           "ts": _now()}, 50_000)
        return task
    def list_syncs(
        self, source_provider: Optional[str] = None,
        status: Optional[str] = None, limit: int = 100,
    ) -> List[SyncTask]:
        """Return sync tasks filtered by optional criteria."""
        with self._lock:
            out = list(self._syncs.values())
        if source_provider:
            out = [s for s in out if s.source_provider == source_provider]
        if status:
            out = [s for s in out if s.status == status]
        return out[:limit]
    # -- Cost tracking ------------------------------------------------------

    def record_cost(
        self, provider: str, region: str, service: str,
        amount: float, currency: str = "USD",
        period_start: str = "", period_end: str = "",
    ) -> CostRecord:
        """Record a cloud cost entry."""
        rec = CostRecord(
            provider=provider, region=region, service=service,
            amount=amount, currency=currency,
            period_start=period_start, period_end=period_end,)
        with self._lock:
            capped_append_paired(
                self._costs, rec,
                self._history, {"action": "record_cost", "cost_id": rec.id,
                                "ts": _now()},
                max_size=50_000,
            )
        return rec
    def get_cost_summary(
        self, provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return aggregated cost summary, optionally filtered by provider."""
        with self._lock:
            costs = list(self._costs)
        if provider:
            costs = [c for c in costs if c.provider == provider]
        by_provider: Dict[str, float] = {}
        total = 0.0
        for c in costs:
            by_provider[c.provider] = by_provider.get(c.provider, 0.0) + c.amount
            total += c.amount
        return {"total": round(total, 2), "currency": "USD",
                "by_provider": {k: round(v, 2) for k, v in by_provider.items()},
                "record_count": len(costs)}
    def list_costs(
        self, provider: Optional[str] = None, limit: int = 100,
    ) -> List[CostRecord]:
        """Return cost records filtered by optional criteria."""
        with self._lock:
            out = list(self._costs)
        if provider:
            out = [c for c in out if c.provider == provider]
        return out[:limit]
    # -- Health -------------------------------------------------------------

    def update_health(
        self, deployment_id: str,
        state: Union[str, HealthState],
    ) -> Optional[CloudDeployment]:
        """Update the health state of a deployment."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return None
            dep.health_state = _enum_val(state)
            dep.last_health_check = _now()
            capped_append(self._history,
                          {"action": "update_health",
                           "deployment_id": deployment_id, "ts": _now()},
                          50_000)
        return dep
    def get_health_overview(self) -> Dict[str, Any]:
        """Return deployment health counts across all providers."""
        with self._lock:
            deps = list(self._deployments.values())
        counts: Dict[str, int] = {
            "healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0,
        }
        for d in deps:
            counts[d.health_state] = counts.get(d.health_state, 0) + 1
        return {"total_deployments": len(deps), **counts}
    # -- Summary & export ---------------------------------------------------

    def export_state(self) -> dict:
        """Serialise full orchestrator state."""
        with self._lock:
            return {
                "providers": {pid: p.to_dict()
                              for pid, p in self._providers.items()},
                "deployments": {did: d.to_dict()
                                for did, d in self._deployments.items()},
                "failover_rules": {rid: r.to_dict()
                                   for rid, r in self._failover_rules.items()},
                "syncs": {sid: s.to_dict()
                          for sid, s in self._syncs.items()},
                "costs": [c.to_dict() for c in self._costs],
                "exported_at": _now(),
            }
    def clear(self) -> None:
        """Remove all state."""
        with self._lock:
            self._providers.clear()
            self._deployments.clear()
            self._failover_rules.clear()
            self._syncs.clear()
            self._costs.clear()
            capped_append(self._history, {"action": "clear", "ts": _now()},
                          50_000)
    def get_multi_cloud_summary(self) -> Dict[str, Any]:
        """Return a high-level multi-cloud summary."""
        with self._lock:
            providers = len(self._providers)
            deployments = len(self._deployments)
            active = sum(1 for d in self._deployments.values()
                         if d.status == "running")
            rules = len(self._failover_rules)
            syncs = len(self._syncs)
            costs = len(self._costs)
        return {
            "providers": providers, "deployments": deployments,
            "active_deployments": active, "failover_rules": rules,
            "sync_tasks": syncs, "cost_records": costs,
        }
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
    required_keys = {"provider"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("provider"):
        return {"passed": False, "message": "provider must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "provider": context["provider"]}
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
    """Create a Flask Blueprint with multi-cloud orchestrator REST endpoints."""
    bp = Blueprint("mco", __name__, url_prefix="/api")
    orch = orchestrator
    @bp.route("/mco/providers", methods=["POST"])
    def create_provider() -> Any:
        body = _api_body()
        err = _api_need(body, "name", "provider", "region")
        if err:
            return err
        cfg = orch.register_provider(
            name=body["name"], provider=body["provider"],
            region=body["region"], credentials_ref=body.get("credentials_ref", ""),
            endpoint=body.get("endpoint", ""), enabled=body.get("enabled", True),
            priority=body.get("priority", 0), tags=body.get("tags", {}),
        )
        return jsonify(cfg.to_dict()), 201
    @bp.route("/mco/providers", methods=["GET"])
    def list_providers() -> Any:
        a = request.args
        enabled = None
        if a.get("enabled") is not None:
            enabled = a.get("enabled", "").lower() == "true"
        providers = orch.list_providers(
            provider=a.get("provider"), enabled=enabled,
            limit=int(a.get("limit", 100)),
        )
        return jsonify([p.to_dict() for p in providers]), 200
    @bp.route("/mco/providers/<provider_id>", methods=["GET"])
    def get_provider(provider_id: str) -> Any:
        cfg = orch.get_provider(provider_id)
        if cfg is None:
            return _not_found("Provider not found")
        return jsonify(cfg.to_dict()), 200
    @bp.route("/mco/providers/<provider_id>", methods=["PUT"])
    def update_provider(provider_id: str) -> Any:
        body = _api_body()
        cfg = orch.update_provider(
            provider_id,
            enabled=body.get("enabled"),
            region=body.get("region"),
            priority=body.get("priority"),
            endpoint=body.get("endpoint"),
        )
        if cfg is None:
            return _not_found("Provider not found")
        return jsonify(cfg.to_dict()), 200
    @bp.route("/mco/providers/<provider_id>", methods=["DELETE"])
    def remove_provider(provider_id: str) -> Any:
        if not orch.remove_provider(provider_id):
            return _not_found("Provider not found")
        return jsonify({"deleted": True}), 200
    @bp.route("/mco/deployments", methods=["POST"])
    def create_deployment() -> Any:
        body = _api_body()
        err = _api_need(body, "name", "provider", "region")
        if err:
            return err
        dep = orch.create_deployment(
            name=body["name"], provider=body["provider"],
            region=body["region"], config_id=body.get("config_id", ""),
            replicas=body.get("replicas", 1), cpu_limit=body.get("cpu_limit", "1000m"),
            memory_limit=body.get("memory_limit", "512Mi"),
            image=body.get("image", ""), env_vars=body.get("env_vars", {}),
        )
        return jsonify(dep.to_dict()), 201
    @bp.route("/mco/deployments", methods=["GET"])
    def list_deployments() -> Any:
        a = request.args
        deps = orch.list_deployments(
            provider=a.get("provider"), status=a.get("status"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([d.to_dict() for d in deps]), 200
    @bp.route("/mco/deployments/<deployment_id>", methods=["GET"])
    def get_deployment(deployment_id: str) -> Any:
        dep = orch.get_deployment(deployment_id)
        if dep is None:
            return _not_found("Deployment not found")
        return jsonify(dep.to_dict()), 200
    @bp.route("/mco/deployments/<deployment_id>/status", methods=["PUT"])
    def update_deployment_status(deployment_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "status")
        if err:
            return err
        dep = orch.update_deployment_status(deployment_id, body["status"])
        if dep is None:
            return _not_found("Deployment not found")
        return jsonify(dep.to_dict()), 200
    @bp.route("/mco/deployments/<deployment_id>", methods=["DELETE"])
    def delete_deployment(deployment_id: str) -> Any:
        if not orch.delete_deployment(deployment_id):
            return _not_found("Deployment not found")
        return jsonify({"deleted": True}), 200
    @bp.route("/mco/failover-rules", methods=["POST"])
    def create_failover_rule() -> Any:
        body = _api_body()
        err = _api_need(body, "name", "primary_provider",
                        "secondary_provider")
        if err:
            return err
        rule = orch.create_failover_rule(
            name=body["name"], primary_provider=body["primary_provider"],
            secondary_provider=body["secondary_provider"],
            strategy=body.get("strategy", "active_passive"),
            threshold_ms=body.get("threshold_ms", 5000),
            max_retries=body.get("max_retries", 3),
            cooldown_sec=body.get("cooldown_sec", 60),
            enabled=body.get("enabled", True),
        )
        return jsonify(rule.to_dict()), 201
    @bp.route("/mco/failover-rules", methods=["GET"])
    def list_failover_rules() -> Any:
        a = request.args
        enabled = None
        if a.get("enabled") is not None:
            enabled = a.get("enabled", "").lower() == "true"
        rules = orch.list_failover_rules(
            primary_provider=a.get("primary_provider"),
            enabled=enabled,
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in rules]), 200
    @bp.route("/mco/failover/<deployment_id>/evaluate", methods=["POST"])
    def evaluate_failover(deployment_id: str) -> Any:
        result = orch.evaluate_failover(deployment_id)
        return jsonify(result), 200
    @bp.route("/mco/syncs", methods=["POST"])
    def start_sync() -> Any:
        body = _api_body()
        err = _api_need(body, "source_provider", "target_provider",
                        "resource_type")
        if err:
            return err
        task = orch.start_sync(
            source_provider=body["source_provider"],
            target_provider=body["target_provider"],
            resource_type=body["resource_type"],
            item_count=body.get("item_count", 0),
        )
        return jsonify(task.to_dict()), 201
    @bp.route("/mco/syncs", methods=["GET"])
    def list_syncs() -> Any:
        a = request.args
        syncs = orch.list_syncs(
            source_provider=a.get("source_provider"),
            status=a.get("status"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([s.to_dict() for s in syncs]), 200
    @bp.route("/mco/syncs/<sync_id>/complete", methods=["POST"])
    def complete_sync(sync_id: str) -> Any:
        body = _api_body()
        task = orch.complete_sync(
            sync_id, items_synced=body.get("items_synced", 0),
            errors=body.get("errors"),
        )
        if task is None:
            return _not_found("Sync task not found")
        return jsonify(task.to_dict()), 200
    @bp.route("/mco/costs", methods=["POST"])
    def record_cost() -> Any:
        body = _api_body()
        err = _api_need(body, "provider", "service", "amount")
        if err:
            return err
        rec = orch.record_cost(
            provider=body["provider"], region=body.get("region", ""),
            service=body["service"], amount=float(body["amount"]),
            currency=body.get("currency", "USD"),
            period_start=body.get("period_start", ""),
            period_end=body.get("period_end", ""),
        )
        return jsonify(rec.to_dict()), 201
    @bp.route("/mco/costs", methods=["GET"])
    def list_costs() -> Any:
        a = request.args
        costs = orch.list_costs(
            provider=a.get("provider"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([c.to_dict() for c in costs]), 200
    @bp.route("/mco/costs/summary", methods=["GET"])
    def cost_summary() -> Any:
        a = request.args
        summary = orch.get_cost_summary(provider=a.get("provider"))
        return jsonify(summary), 200
    @bp.route("/mco/deployments/<deployment_id>/health", methods=["POST"])
    def update_health(deployment_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "state")
        if err:
            return err
        dep = orch.update_health(deployment_id, body["state"])
        if dep is None:
            return _not_found("Deployment not found")
        return jsonify(dep.to_dict()), 200
    @bp.route("/mco/health/overview", methods=["GET"])
    def health_overview() -> Any:
        return jsonify(orch.get_health_overview()), 200
    @bp.route("/mco/health", methods=["GET"])
    def health() -> Any:
        providers = orch.list_providers()
        return jsonify({
            "status": "healthy", "module": "MCO-001",
            "tracked_providers": len(providers),
        }), 200
    @bp.route("/mco/export", methods=["POST"])
    def export_state() -> Any:
        return jsonify(orch.export_state()), 200
    @bp.route("/mco/summary", methods=["GET"])
    def get_summary() -> Any:
        return jsonify(orch.get_multi_cloud_summary()), 200

    require_blueprint_auth(bp)
    return bp
