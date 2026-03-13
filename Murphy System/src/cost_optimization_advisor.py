# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Cost Optimization Advisor — COA-001

Owner: Operations · Dep: threading, uuid, dataclasses

Analyze cloud spend, recommend rightsizing, spot instance opportunities.
Ingest cloud resource inventories and spend records, detect under-utilised
resources, surface rightsizing and spot-instance recommendations, track
budgets, and aggregate cost summaries per provider.
``create_cost_optimization_api(advisor)`` → Flask Blueprint.
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
    aws = "aws"; gcp = "gcp"; azure = "azure"; other = "other"

class ResourceKind(str, Enum):
    """Kind of cloud resource."""
    compute = "compute"; storage = "storage"; database = "database"
    network = "network"; container = "container"; serverless = "serverless"
    other = "other"

class RecommendationSeverity(str, Enum):
    """Severity of a cost recommendation."""
    low = "low"; medium = "medium"; high = "high"; critical = "critical"

class RecommendationStatus(str, Enum):
    """Lifecycle status of a recommendation."""
    pending = "pending"; accepted = "accepted"; rejected = "rejected"
    implemented = "implemented"; expired = "expired"

class SpotOpportunityStatus(str, Enum):
    """Status of a spot-instance opportunity."""
    available = "available"; expired = "expired"; claimed = "claimed"
# -- Dataclass models ------------------------------------------------------

@dataclass
class CloudResource:
    """A tracked cloud resource."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    provider: str = "aws"
    resource_kind: str = "compute"
    region: str = ""
    monthly_cost: float = 0.0
    currency: str = "USD"
    utilization_pct: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class SpendRecord:
    """A single spend entry for a resource."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    resource_id: str = ""
    provider: str = "aws"
    amount: float = 0.0
    currency: str = "USD"
    period: str = ""
    category: str = ""
    timestamp: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class CostRecommendation:
    """A cost-saving recommendation for a resource."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    resource_id: str = ""
    title: str = ""
    description: str = ""
    severity: str = "medium"
    status: str = "pending"
    estimated_monthly_savings: float = 0.0
    confidence: float = 0.0
    recommendation_type: str = "rightsizing"
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class SpotOpportunity:
    """A spot-instance pricing opportunity."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    resource_id: str = ""
    provider: str = "aws"
    region: str = ""
    current_cost: float = 0.0
    spot_cost: float = 0.0
    savings_pct: float = 0.0
    status: str = "available"
    expires_at: str = ""
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class BudgetAlert:
    """A budget tracking alert."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    budget_name: str = ""
    budget_limit: float = 0.0
    current_spend: float = 0.0
    threshold_pct: float = 80.0
    breached: bool = False
    message: str = ""
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class CostSummary:
    """Aggregated cost summary for a provider."""
    provider: str = ""
    total_spend: float = 0.0
    resource_count: int = 0
    top_category: str = ""
    avg_utilization: float = 0.0
    potential_savings: float = 0.0
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)
# -- Engine ----------------------------------------------------------------

class CostOptimizationAdvisor:
    """Thread-safe cost optimization advisor engine."""

    def __init__(self, max_resources: int = 50_000,
                 max_records: int = 50_000) -> None:
        self._lock = threading.Lock()
        self._resources: Dict[str, CloudResource] = {}
        self._spend_records: List[SpendRecord] = []
        self._recommendations: List[CostRecommendation] = []
        self._spot_opportunities: List[SpotOpportunity] = []
        self._budgets: Dict[str, BudgetAlert] = {}
        self._history: List[dict] = []
        self._max_resources = max_resources
        self._max_records = max_records
    # -- Resources ----------------------------------------------------------

    def register_resource(
        self, name: str,
        provider: Union[str, CloudProvider] = "aws",
        resource_kind: Union[str, ResourceKind] = "compute",
        region: str = "",
        monthly_cost: float = 0.0,
        currency: str = "USD",
        utilization_pct: float = 0.0,
        tags: Optional[Dict[str, str]] = None,
    ) -> CloudResource:
        """Register a new cloud resource for tracking."""
        res = CloudResource(
            name=name, provider=_enum_val(provider),
            resource_kind=_enum_val(resource_kind),
            region=region, monthly_cost=monthly_cost,
            currency=currency,
            utilization_pct=max(0.0, min(100.0, utilization_pct)),
            tags=tags or {},
        )
        with self._lock:
            if len(self._resources) >= self._max_resources:
                oldest = next(iter(self._resources))
                del self._resources[oldest]
            self._resources[res.id] = res
            capped_append(self._history, {"action": "register_resource",
                          "resource": res.id, "ts": _now()}, 50_000)
        return res

    def get_resource(self, resource_id: str) -> Optional[CloudResource]:
        """Look up a resource by ID."""
        with self._lock:
            return self._resources.get(resource_id)

    def list_resources(
        self, provider: Optional[str] = None,
        resource_kind: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 100,
    ) -> List[CloudResource]:
        """List resources with optional filters."""
        with self._lock:
            resources = list(self._resources.values())
        if provider:
            pv = _enum_val(provider)
            resources = [r for r in resources if r.provider == pv]
        if resource_kind:
            rk = _enum_val(resource_kind)
            resources = [r for r in resources if r.resource_kind == rk]
        if region:
            resources = [r for r in resources if r.region == region]
        return resources[:limit]

    def update_resource(
        self, resource_id: str,
        monthly_cost: Optional[float] = None,
        utilization_pct: Optional[float] = None,
    ) -> Optional[CloudResource]:
        """Update mutable fields on a resource."""
        with self._lock:
            res = self._resources.get(resource_id)
            if res is None:
                return None
            if monthly_cost is not None:
                res.monthly_cost = monthly_cost
            if utilization_pct is not None:
                res.utilization_pct = max(0.0, min(100.0, utilization_pct))
        return res

    def delete_resource(self, resource_id: str) -> bool:
        """Remove a resource from tracking."""
        with self._lock:
            return self._resources.pop(resource_id, None) is not None
    # -- Spend records ------------------------------------------------------

    def record_spend(
        self, resource_id: str, amount: float,
        period: str, category: str = "",
        currency: str = "USD",
    ) -> SpendRecord:
        """Record a spend entry for a resource."""
        with self._lock:
            res = self._resources.get(resource_id)
            prov = res.provider if res else "other"
        rec = SpendRecord(
            resource_id=resource_id, provider=prov,
            amount=amount, currency=currency,
            period=period, category=category,
        )
        with self._lock:
            capped_append_paired(
                self._spend_records, rec,
                self._history, {"action": "record_spend",
                                "resource": resource_id, "ts": _now()},
                max_size=self._max_records,
            )
        return rec

    def get_spend(
        self, resource_id: Optional[str] = None,
        provider: Optional[str] = None,
        period: Optional[str] = None,
        limit: int = 100,
    ) -> List[SpendRecord]:
        """Query spend records with optional filters."""
        with self._lock:
            records = list(self._spend_records)
        if resource_id:
            records = [r for r in records if r.resource_id == resource_id]
        if provider:
            pv = _enum_val(provider)
            records = [r for r in records if r.provider == pv]
        if period:
            records = [r for r in records if r.period == period]
        return records[-limit:]
    # -- Rightsizing analysis -----------------------------------------------

    def analyze_rightsizing(
        self, resource_id: str,
    ) -> CostRecommendation:
        """Analyze a resource's utilization and recommend rightsizing."""
        with self._lock:
            res = self._resources.get(resource_id)
        if res is None:
            return CostRecommendation(
                resource_id=resource_id,
                title="Resource not found",
                description="Cannot analyze — resource does not exist",
                severity="low", status="expired",
                estimated_monthly_savings=0.0, confidence=0.0,
                recommendation_type="rightsizing",
            )
        rec = self._build_rightsizing_rec(res)
        with self._lock:
            capped_append(self._recommendations, rec, self._max_records)
        return rec

    def _build_rightsizing_rec(self, res: CloudResource) -> CostRecommendation:
        """Build a rightsizing recommendation from utilization data."""
        util = res.utilization_pct
        if util >= 60.0:
            return CostRecommendation(
                resource_id=res.id,
                title="No action needed",
                description=f"Utilization at {util}% — adequately sized",
                severity="low", status="pending",
                estimated_monthly_savings=0.0, confidence=0.9,
                recommendation_type="rightsizing",
            )
        if util < 20.0:
            severity = "high"
            savings = res.monthly_cost * 0.5
            confidence = 0.9
            desc = f"Utilization at {util}% — strongly recommend downsize"
        elif util < 40.0:
            severity = "medium"
            savings = res.monthly_cost * 0.3
            confidence = 0.75
            desc = f"Utilization at {util}% — consider downsizing"
        else:
            severity = "low"
            savings = res.monthly_cost * 0.15
            confidence = 0.6
            desc = f"Utilization at {util}% — minor savings possible"
        return CostRecommendation(
            resource_id=res.id,
            title=f"Rightsize {res.name}",
            description=desc, severity=severity, status="pending",
            estimated_monthly_savings=round(savings, 2),
            confidence=confidence,
            recommendation_type="rightsizing",
        )
    # -- Spot opportunities -------------------------------------------------

    def scan_spot_opportunities(
        self, provider: Optional[str] = None,
        region: Optional[str] = None,
    ) -> List[SpotOpportunity]:
        """Scan compute resources for spot-instance opportunities."""
        with self._lock:
            resources = list(self._resources.values())
        candidates = [
            r for r in resources
            if r.resource_kind == "compute" and r.utilization_pct < 70.0
        ]
        if provider:
            pv = _enum_val(provider)
            candidates = [r for r in candidates if r.provider == pv]
        if region:
            candidates = [r for r in candidates if r.region == region]
        opportunities: List[SpotOpportunity] = []
        for res in candidates:
            opp = self._build_spot_opportunity(res)
            opportunities.append(opp)
        with self._lock:
            for opp in opportunities:
                capped_append(
                    self._spot_opportunities, opp, self._max_records,
                )
        return opportunities

    @staticmethod
    def _build_spot_opportunity(res: CloudResource) -> SpotOpportunity:
        """Create a spot opportunity record for a compute resource."""
        spot_cost = round(res.monthly_cost * 0.3, 2)
        return SpotOpportunity(
            resource_id=res.id, provider=res.provider,
            region=res.region, current_cost=res.monthly_cost,
            spot_cost=spot_cost, savings_pct=70.0,
            status="available", expires_at=_now(),
        )
    # -- Recommendations ----------------------------------------------------

    def get_recommendations(
        self, resource_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[CostRecommendation]:
        """List recommendations with optional filters."""
        with self._lock:
            recs = list(self._recommendations)
        if resource_id:
            recs = [r for r in recs if r.resource_id == resource_id]
        if severity:
            sv = _enum_val(severity)
            recs = [r for r in recs if r.severity == sv]
        if status:
            st = _enum_val(status)
            recs = [r for r in recs if r.status == st]
        return recs[-limit:]

    def update_recommendation_status(
        self, rec_id: str,
        status: Union[str, RecommendationStatus],
    ) -> Optional[CostRecommendation]:
        """Update the lifecycle status of a recommendation."""
        st = _enum_val(status)
        with self._lock:
            for rec in self._recommendations:
                if rec.id == rec_id:
                    rec.status = st
                    return rec
        return None
    # -- Budgets ------------------------------------------------------------

    def set_budget(
        self, budget_name: str, budget_limit: float,
    ) -> BudgetAlert:
        """Create or update a named budget."""
        alert = BudgetAlert(
            budget_name=budget_name, budget_limit=budget_limit,
            current_spend=0.0, threshold_pct=80.0,
            breached=False, message=f"Budget '{budget_name}' created",
        )
        with self._lock:
            self._budgets[budget_name] = alert
            capped_append(self._history, {"action": "set_budget",
                          "budget": budget_name, "ts": _now()}, 50_000)
        return alert

    def check_budgets(self) -> List[BudgetAlert]:
        """Check all budgets against total spend and update breach status."""
        with self._lock:
            total_spend = sum(r.amount for r in self._spend_records)
            budgets = list(self._budgets.values())
        results: List[BudgetAlert] = []
        with self._lock:
            for ba in budgets:
                ba.current_spend = total_spend
                threshold_amount = ba.budget_limit * (ba.threshold_pct / 100.0)
                if total_spend >= threshold_amount:
                    ba.breached = True
                    ba.message = (
                        f"Budget '{ba.budget_name}' breached: "
                        f"${total_spend:.2f} >= ${threshold_amount:.2f} "
                        f"({ba.threshold_pct}% of ${ba.budget_limit:.2f})"
                    )
                else:
                    ba.breached = False
                    ba.message = (
                        f"Budget '{ba.budget_name}' within limits: "
                        f"${total_spend:.2f} / ${ba.budget_limit:.2f}"
                    )
                results.append(ba)
        return results
    # -- Cost summary -------------------------------------------------------

    def get_cost_summary(
        self, provider: Optional[str] = None,
    ) -> CostSummary:
        """Aggregate spend data into a summary."""
        with self._lock:
            resources = list(self._resources.values())
            records = list(self._spend_records)
            recs = list(self._recommendations)
        if provider:
            pv = _enum_val(provider)
            resources = [r for r in resources if r.provider == pv]
            records = [r for r in records if r.provider == pv]
        total_spend = sum(r.amount for r in records)
        resource_count = len(resources)
        top_category = self._find_top_category(records)
        avg_util = self._compute_avg_utilization(resources)
        potential_savings = sum(r.estimated_monthly_savings for r in recs
                                if r.status == "pending")
        return CostSummary(
            provider=provider or "all",
            total_spend=round(total_spend, 2),
            resource_count=resource_count,
            top_category=top_category,
            avg_utilization=round(avg_util, 2),
            potential_savings=round(potential_savings, 2),
        )

    @staticmethod
    def _find_top_category(records: List[SpendRecord]) -> str:
        """Return the category with the highest total spend."""
        if not records:
            return ""
        by_cat: Dict[str, float] = {}
        for r in records:
            cat = r.category or "uncategorised"
            by_cat[cat] = by_cat.get(cat, 0.0) + r.amount
        return max(by_cat, key=by_cat.get)  # type: ignore[arg-type]

    @staticmethod
    def _compute_avg_utilization(resources: List[CloudResource]) -> float:
        """Compute average utilization across resources."""
        if not resources:
            return 0.0
        return sum(r.utilization_pct for r in resources) / len(resources)
    # -- Export / clear -----------------------------------------------------

    def export_state(self) -> dict:
        """Serialise advisor state to a plain dict."""
        with self._lock:
            return {
                "resources": {rid: r.to_dict()
                              for rid, r in self._resources.items()},
                "spend_records": [r.to_dict() for r in self._spend_records],
                "recommendations": [r.to_dict()
                                    for r in self._recommendations],
                "spot_opportunities": [o.to_dict()
                                       for o in self._spot_opportunities],
                "budgets": {n: b.to_dict()
                            for n, b in self._budgets.items()},
                "exported_at": _now(),
            }

    def clear(self) -> None:
        """Remove all state."""
        with self._lock:
            self._resources.clear()
            self._spend_records.clear()
            self._recommendations.clear()
            self._spot_opportunities.clear()
            self._budgets.clear()
            capped_append(self._history, {"action": "clear", "ts": _now()},
                          50_000)
# -- Wingman & Sandbox gates -----------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """COA-001 Wingman gate."""
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


def gate_coa_in_sandbox(context: dict) -> dict:
    """COA-001 Causality Sandbox gate."""
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

def create_cost_optimization_api(
    advisor: CostOptimizationAdvisor,
) -> Any:
    """Create a Flask Blueprint with cost-optimization REST endpoints."""
    bp = Blueprint("coa", __name__, url_prefix="/api")
    eng = advisor

    @bp.route("/coa/resources", methods=["POST"])
    def register_resource() -> Any:
        body = _api_body()
        err = _api_need(body, "name")
        if err:
            return err
        r = eng.register_resource(
            name=body["name"],
            provider=body.get("provider", "aws"),
            resource_kind=body.get("resource_kind", "compute"),
            region=body.get("region", ""),
            monthly_cost=float(body.get("monthly_cost", 0)),
            currency=body.get("currency", "USD"),
            utilization_pct=float(body.get("utilization_pct", 0)),
            tags=body.get("tags", {}),
        )
        return jsonify(r.to_dict()), 201

    @bp.route("/coa/resources", methods=["GET"])
    def list_resources() -> Any:
        a = request.args
        resources = eng.list_resources(
            provider=a.get("provider"),
            resource_kind=a.get("resource_kind"),
            region=a.get("region"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in resources]), 200

    @bp.route("/coa/resources/<resource_id>", methods=["GET"])
    def get_resource(resource_id: str) -> Any:
        res = eng.get_resource(resource_id)
        if res is None:
            return _not_found("Resource not found")
        return jsonify(res.to_dict()), 200

    @bp.route("/coa/resources/<resource_id>", methods=["PUT"])
    def update_resource(resource_id: str) -> Any:
        body = _api_body()
        res = eng.update_resource(
            resource_id,
            monthly_cost=body.get("monthly_cost"),
            utilization_pct=body.get("utilization_pct"),
        )
        if res is None:
            return _not_found("Resource not found")
        return jsonify(res.to_dict()), 200

    @bp.route("/coa/resources/<resource_id>", methods=["DELETE"])
    def delete_resource(resource_id: str) -> Any:
        if not eng.delete_resource(resource_id):
            return _not_found("Resource not found")
        return jsonify({"deleted": True}), 200

    @bp.route("/coa/spend", methods=["POST"])
    def record_spend() -> Any:
        body = _api_body()
        err = _api_need(body, "resource_id", "amount", "period")
        if err:
            return err
        rec = eng.record_spend(
            resource_id=body["resource_id"],
            amount=float(body["amount"]),
            period=body["period"],
            category=body.get("category", ""),
            currency=body.get("currency", "USD"),
        )
        return jsonify(rec.to_dict()), 201

    @bp.route("/coa/spend", methods=["GET"])
    def get_spend() -> Any:
        a = request.args
        records = eng.get_spend(
            resource_id=a.get("resource_id"),
            provider=a.get("provider"),
            period=a.get("period"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in records]), 200

    @bp.route("/coa/analyze/<resource_id>", methods=["POST"])
    def analyze_rightsizing(resource_id: str) -> Any:
        rec = eng.analyze_rightsizing(resource_id)
        return jsonify(rec.to_dict()), 200

    @bp.route("/coa/spot/scan", methods=["POST"])
    def scan_spot() -> Any:
        body = _api_body()
        opps = eng.scan_spot_opportunities(
            provider=body.get("provider"),
            region=body.get("region"),
        )
        return jsonify([o.to_dict() for o in opps]), 200

    @bp.route("/coa/recommendations", methods=["GET"])
    def get_recommendations() -> Any:
        a = request.args
        recs = eng.get_recommendations(
            resource_id=a.get("resource_id"),
            severity=a.get("severity"),
            status=a.get("status"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in recs]), 200

    @bp.route("/coa/recommendations/<rec_id>/status", methods=["PUT"])
    def update_rec_status(rec_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "status")
        if err:
            return err
        rec = eng.update_recommendation_status(rec_id, body["status"])
        if rec is None:
            return _not_found("Recommendation not found")
        return jsonify(rec.to_dict()), 200

    @bp.route("/coa/budgets", methods=["POST"])
    def set_budget() -> Any:
        body = _api_body()
        err = _api_need(body, "budget_name", "budget_limit")
        if err:
            return err
        ba = eng.set_budget(
            budget_name=body["budget_name"],
            budget_limit=float(body["budget_limit"]),
        )
        return jsonify(ba.to_dict()), 201

    @bp.route("/coa/budgets/check", methods=["GET"])
    def check_budgets() -> Any:
        alerts = eng.check_budgets()
        return jsonify([a.to_dict() for a in alerts]), 200

    @bp.route("/coa/summary", methods=["GET"])
    def get_summary() -> Any:
        a = request.args
        summary = eng.get_cost_summary(provider=a.get("provider"))
        return jsonify(summary.to_dict()), 200

    @bp.route("/coa/export", methods=["POST"])
    def export_state() -> Any:
        return jsonify(eng.export_state()), 200

    @bp.route("/coa/health", methods=["GET"])
    def health() -> Any:
        resources = eng.list_resources()
        return jsonify({
            "status": "healthy", "module": "COA-001",
            "tracked_resources": len(resources),
        }), 200

    require_blueprint_auth(bp)
    return bp
