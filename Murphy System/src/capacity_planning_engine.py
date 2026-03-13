# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Automated Capacity Planning Engine — CPE-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Predict resource needs from historical usage patterns.  Collects
time-series resource metrics (CPU, memory, disk, network, custom),
fits simple forecasting models (linear regression, exponential
smoothing), emits capacity alerts when projected usage crosses
thresholds, and suggests scaling actions.

Classes: ResourceType/AlertSeverity/ForecastMethod/PlanStatus (enums),
ResourceMetric/ForecastResult/CapacityAlert/ScalingRecommendation/
CapacityPlan (dataclasses), CapacityPlanningEngine (thread-safe
orchestrator).
``create_capacity_api(engine)`` returns a Flask Blueprint (JSON error
envelope).

Safety: all mutable state guarded by threading.Lock; metric history
bounded via capped_append (CWE-770); no external network calls; no
PII stored.
"""
from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional Flask
# ---------------------------------------------------------------------------
try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:  # pragma: no cover
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]
    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}
    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}
        @staticmethod
        def get_json(silent: bool = True) -> dict: return {}
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

# ── Enums ─────────────────────────────────────────────────────────────────

class ResourceType(str, Enum):
    """Type of resource being monitored."""
    cpu = "cpu"
    memory = "memory"
    disk = "disk"
    network = "network"
    gpu = "gpu"
    connections = "connections"
    custom = "custom"

class AlertSeverity(str, Enum):
    """Severity of a capacity alert."""
    info = "info"
    warning = "warning"
    critical = "critical"

class ForecastMethod(str, Enum):
    """Forecasting algorithm."""
    linear = "linear"
    exponential_smoothing = "exponential_smoothing"
    moving_average = "moving_average"

class PlanStatus(str, Enum):
    """Status of a capacity plan."""
    active = "active"
    archived = "archived"
    superseded = "superseded"

# ── Dataclasses ───────────────────────────────────────────────────────────

@dataclass
class ResourceMetric:
    """A single time-series data point for a resource."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    resource_type: ResourceType = ResourceType.cpu
    resource_name: str = ""
    value: float = 0.0
    capacity: float = 100.0
    unit: str = "%"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["resource_type"] = self.resource_type.value
        return d

    @property
    def utilisation(self) -> float:
        """Return utilisation as fraction 0..1."""
        return self.value / self.capacity if self.capacity > 0 else 0.0

@dataclass
class ForecastResult:
    """Predicted future resource usage."""
    resource_name: str = ""
    resource_type: ResourceType = ResourceType.cpu
    method: ForecastMethod = ForecastMethod.linear
    current_value: float = 0.0
    predicted_value: float = 0.0
    capacity: float = 100.0
    predicted_utilisation: float = 0.0
    time_to_threshold_hours: Optional[float] = None
    confidence: float = 0.0
    data_points_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["resource_type"] = self.resource_type.value
        d["method"] = self.method.value
        return d

@dataclass
class CapacityAlert:
    """An alert raised when projected usage crosses a threshold."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    resource_name: str = ""
    resource_type: ResourceType = ResourceType.cpu
    severity: AlertSeverity = AlertSeverity.warning
    message: str = ""
    current_utilisation: float = 0.0
    predicted_utilisation: float = 0.0
    threshold: float = 0.8
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["resource_type"] = self.resource_type.value
        d["severity"] = self.severity.value
        return d

@dataclass
class ScalingRecommendation:
    """A recommended scaling action."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    resource_name: str = ""
    resource_type: ResourceType = ResourceType.cpu
    action: str = ""
    reason: str = ""
    priority: int = 0
    estimated_headroom_hours: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        d = asdict(self)
        d["resource_type"] = self.resource_type.value
        return d

@dataclass
class CapacityPlan:
    """A complete capacity plan with forecasts, alerts, recommendations."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    status: PlanStatus = PlanStatus.active
    forecasts: List[ForecastResult] = field(default_factory=list)
    alerts: List[CapacityAlert] = field(default_factory=list)
    recommendations: List[ScalingRecommendation] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    horizon_hours: float = 24.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return {
            "id": self.id, "name": self.name,
            "status": self.status.value,
            "forecasts": [f.to_dict() for f in self.forecasts],
            "alerts": [a.to_dict() for a in self.alerts],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "created_at": self.created_at,
            "horizon_hours": self.horizon_hours,
        }

# ── CapacityPlanningEngine ────────────────────────────────────────────────

class CapacityPlanningEngine:
    """Thread-safe capacity planning orchestrator.

    Parameters
    ----------
    max_metrics : int
        Maximum metric data points retained per resource.
    warning_threshold : float
        Utilisation fraction triggering a warning alert.
    critical_threshold : float
        Utilisation fraction triggering a critical alert.
    """

    def __init__(
        self,
        max_metrics: int = 10_000,
        warning_threshold: float = 0.75,
        critical_threshold: float = 0.90,
    ) -> None:
        self._lock = threading.Lock()
        self._metrics: Dict[str, List[ResourceMetric]] = {}
        self._plans: Dict[str, CapacityPlan] = {}
        self._alerts: List[CapacityAlert] = []
        self._max_metrics = max_metrics
        self._warning = warning_threshold
        self._critical = critical_threshold

    # ── Metric ingestion ─────────────────────────────────────────────────

    def record_metric(
        self, resource_name: str, value: float,
        resource_type: ResourceType = ResourceType.cpu,
        capacity: float = 100.0, unit: str = "%",
    ) -> ResourceMetric:
        """Record a resource metric data point."""
        metric = ResourceMetric(
            resource_type=resource_type, resource_name=resource_name,
            value=value, capacity=capacity, unit=unit,
        )
        with self._lock:
            lst = self._metrics.setdefault(resource_name, [])
            capped_append(lst, metric, self._max_metrics)
        return metric

    def get_metrics(
        self, resource_name: str, limit: int = 100,
    ) -> List[ResourceMetric]:
        """Return recent metrics for a resource."""
        with self._lock:
            return list(self._metrics.get(resource_name, []))[-limit:]

    def list_resources(self) -> List[str]:
        """Return names of all tracked resources."""
        with self._lock:
            return list(self._metrics.keys())

    # ── Forecasting ──────────────────────────────────────────────────────

    def forecast(
        self, resource_name: str,
        method: ForecastMethod = ForecastMethod.linear,
        horizon_hours: float = 24.0,
    ) -> Optional[ForecastResult]:
        """Forecast future usage for a resource."""
        with self._lock:
            data = list(self._metrics.get(resource_name, []))
        if len(data) < 2:
            return None
        values = [m.value for m in data]
        capacity = data[-1].capacity
        rtype = data[-1].resource_type
        predicted = self._predict(values, method, horizon_hours)
        current = values[-1]
        pred_util = predicted / capacity if capacity > 0 else 0.0
        tth = self._time_to_threshold(values, capacity, self._warning)
        return ForecastResult(
            resource_name=resource_name, resource_type=rtype,
            method=method, current_value=current,
            predicted_value=round(predicted, 4),
            capacity=capacity,
            predicted_utilisation=round(pred_util, 4),
            time_to_threshold_hours=tth,
            confidence=min(0.95, len(data) / 100.0),
            data_points_used=len(data),
        )

    # ── Plan generation ──────────────────────────────────────────────────

    def generate_plan(
        self, name: str = "", horizon_hours: float = 24.0,
        method: ForecastMethod = ForecastMethod.linear,
    ) -> CapacityPlan:
        """Generate a capacity plan across all tracked resources."""
        resources = self.list_resources()
        forecasts: List[ForecastResult] = []
        alerts: List[CapacityAlert] = []
        recs: List[ScalingRecommendation] = []
        for rname in resources:
            fc = self.forecast(rname, method, horizon_hours)
            if fc:
                forecasts.append(fc)
                self._check_alerts(fc, alerts)
                self._check_recommendations(fc, recs)
        plan = CapacityPlan(
            name=name or f"plan-{len(self._plans)+1}",
            forecasts=forecasts, alerts=alerts,
            recommendations=recs, horizon_hours=horizon_hours,
        )
        with self._lock:
            self._plans[plan.id] = plan
            for a in alerts:
                capped_append(self._alerts, a, 10_000)
        logger.info("Generated plan %s with %d forecasts", plan.id, len(forecasts))
        return plan

    def get_plan(self, plan_id: str) -> Optional[CapacityPlan]:
        """Retrieve a plan by id."""
        with self._lock:
            return self._plans.get(plan_id)

    def list_plans(self, status: Optional[PlanStatus] = None) -> List[CapacityPlan]:
        """List plans, optionally filtered by status."""
        with self._lock:
            plans = list(self._plans.values())
        if status is not None:
            plans = [p for p in plans if p.status == status]
        return plans

    def archive_plan(self, plan_id: str) -> bool:
        """Archive a plan."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return False
            plan.status = PlanStatus.archived
        return True

    # ── Alerts ───────────────────────────────────────────────────────────

    def get_alerts(
        self, severity: Optional[AlertSeverity] = None,
        acknowledged: Optional[bool] = None,
    ) -> List[CapacityAlert]:
        """Return alerts, optionally filtered."""
        with self._lock:
            alerts = list(self._alerts)
        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert by id."""
        with self._lock:
            for a in self._alerts:
                if a.id == alert_id:
                    a.acknowledged = True
                    return True
        return False

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return engine statistics."""
        with self._lock:
            n_resources = len(self._metrics)
            total_pts = sum(len(v) for v in self._metrics.values())
            n_plans = len(self._plans)
            n_alerts = len(self._alerts)
            unack = sum(1 for a in self._alerts if not a.acknowledged)
        return {
            "resources_tracked": n_resources,
            "total_data_points": total_pts,
            "plans_generated": n_plans,
            "total_alerts": n_alerts,
            "unacknowledged_alerts": unack,
        }

    # ── Private: prediction algorithms ───────────────────────────────────

    @staticmethod
    def _predict(
        values: List[float], method: ForecastMethod, horizon: float,
    ) -> float:
        """Predict next value using the chosen method."""
        if method == ForecastMethod.exponential_smoothing:
            return CapacityPlanningEngine._exp_smooth(values)
        if method == ForecastMethod.moving_average:
            return CapacityPlanningEngine._moving_avg(values)
        return CapacityPlanningEngine._linear_predict(values, horizon)

    @staticmethod
    def _linear_predict(values: List[float], horizon: float) -> float:
        """Simple linear regression forecast."""
        n = len(values)
        if n < 2:
            return values[-1] if values else 0.0
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(values) / n
        num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0
        intercept = y_mean - slope * x_mean
        future_x = n - 1 + max(horizon, 1.0)
        return max(0.0, slope * future_x + intercept)

    @staticmethod
    def _exp_smooth(values: List[float], alpha: float = 0.3) -> float:
        """Single exponential smoothing."""
        result = values[0]
        for v in values[1:]:
            result = alpha * v + (1 - alpha) * result
        return max(0.0, result)

    @staticmethod
    def _moving_avg(values: List[float], window: int = 5) -> float:
        """Moving average of the last *window* values."""
        tail = values[-window:]
        return sum(tail) / (len(tail) or 1) if tail else 0.0

    @staticmethod
    def _time_to_threshold(
        values: List[float], capacity: float, threshold: float,
    ) -> Optional[float]:
        """Estimate hours until utilisation reaches threshold."""
        if len(values) < 2 or capacity <= 0:
            return None
        target = threshold * capacity
        current = values[-1]
        if current >= target:
            return 0.0
        n = len(values)
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(values) / n
        num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0
        if slope <= 0:
            return None
        steps = (target - current) / slope
        return round(max(0.0, steps), 2)

    # ── Private: alerts / recommendations ────────────────────────────────

    def _check_alerts(
        self, fc: ForecastResult, alerts: List[CapacityAlert],
    ) -> None:
        """Generate alerts for a forecast."""
        cur_util = fc.current_value / fc.capacity if fc.capacity else 0.0
        if fc.predicted_utilisation >= self._critical or cur_util >= self._critical:
            alerts.append(CapacityAlert(
                resource_name=fc.resource_name, resource_type=fc.resource_type,
                severity=AlertSeverity.critical,
                message=f"{fc.resource_name}: predicted {fc.predicted_utilisation:.0%} utilisation",
                current_utilisation=round(cur_util, 4),
                predicted_utilisation=fc.predicted_utilisation,
                threshold=self._critical,
            ))
        elif fc.predicted_utilisation >= self._warning or cur_util >= self._warning:
            alerts.append(CapacityAlert(
                resource_name=fc.resource_name, resource_type=fc.resource_type,
                severity=AlertSeverity.warning,
                message=f"{fc.resource_name}: predicted {fc.predicted_utilisation:.0%} utilisation",
                current_utilisation=round(cur_util, 4),
                predicted_utilisation=fc.predicted_utilisation,
                threshold=self._warning,
            ))

    @staticmethod
    def _check_recommendations(
        fc: ForecastResult, recs: List[ScalingRecommendation],
    ) -> None:
        """Generate scaling recommendations."""
        if fc.predicted_utilisation >= 0.9:
            recs.append(ScalingRecommendation(
                resource_name=fc.resource_name, resource_type=fc.resource_type,
                action="scale_up",
                reason=f"Predicted utilisation {fc.predicted_utilisation:.0%} exceeds 90%",
                priority=2,
                estimated_headroom_hours=fc.time_to_threshold_hours or 0.0,
            ))
        elif fc.predicted_utilisation >= 0.75:
            recs.append(ScalingRecommendation(
                resource_name=fc.resource_name, resource_type=fc.resource_type,
                action="plan_scaling",
                reason=f"Predicted utilisation {fc.predicted_utilisation:.0%} approaching threshold",
                priority=1,
                estimated_headroom_hours=fc.time_to_threshold_hours or 0.0,
            ))
        elif fc.predicted_utilisation < 0.2 and fc.data_points_used >= 10:
            recs.append(ScalingRecommendation(
                resource_name=fc.resource_name, resource_type=fc.resource_type,
                action="scale_down",
                reason=f"Predicted utilisation {fc.predicted_utilisation:.0%} — over-provisioned",
                priority=0,
            ))

# ── Wingman pair validation ───────────────────────────────────────────────

def validate_wingman_pair(engine: CapacityPlanningEngine) -> Tuple[bool, str]:
    """Validate the engine meets Wingman requirements.

    Checks: at least one resource tracked, at least 2 data points per
    resource, thresholds are sane.
    """
    resources = engine.list_resources()
    if not resources:
        return False, "No resources are being tracked"
    for rname in resources:
        pts = engine.get_metrics(rname)
        if len(pts) < 2:
            return False, f"Resource '{rname}' has <2 data points"
    if engine._warning >= engine._critical:
        return False, "Warning threshold must be < critical threshold"
    return True, "Valid capacity planning wingman pair"

# ── Causality Sandbox gate ────────────────────────────────────────────────

def gate_capacity_in_sandbox(engine: CapacityPlanningEngine) -> Tuple[bool, str]:
    """Gate the engine for the Causality Sandbox.

    Approved if: ≤1000 resources tracked, thresholds in (0, 1).
    """
    n = len(engine.list_resources())
    if n > 1000:
        return False, "Too many resources tracked (max 1000)"
    if not (0.0 < engine._warning < 1.0):
        return False, "Warning threshold must be in (0, 1)"
    if not (0.0 < engine._critical < 1.0):
        return False, "Critical threshold must be in (0, 1)"
    return True, "Approved for sandbox"

# ── Flask Blueprint ───────────────────────────────────────────────────────

def _body() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}

def _err(msg: str, code: str, status: int = 400) -> Any:
    return jsonify({"error": msg, "code": code}), status

def _register_metric_routes(bp: Any, eng: CapacityPlanningEngine) -> None:
    @bp.route("/metrics", methods=["POST"])
    def record_metric() -> Any:
        """Record a resource metric."""
        b = _body()
        name = b.get("resource_name", "").strip()
        if not name:
            return _err("resource_name required", "CPE_MISSING")
        value = b.get("value")
        if value is None:
            return _err("value required", "CPE_MISSING")
        m = eng.record_metric(
            resource_name=name, value=float(value),
            resource_type=ResourceType(b.get("resource_type", "cpu")),
            capacity=float(b.get("capacity", 100.0)),
            unit=b.get("unit", "%"),
        )
        return jsonify(m.to_dict()), 201

    @bp.route("/metrics/<resource_name>", methods=["GET"])
    def get_metrics(resource_name: str) -> Any:
        """Get metrics for a resource."""
        limit = int(request.args.get("limit", "100"))
        return jsonify([m.to_dict() for m in eng.get_metrics(resource_name, limit)])

    @bp.route("/resources", methods=["GET"])
    def list_resources() -> Any:
        """List all tracked resources."""
        return jsonify(eng.list_resources())

def _register_forecast_routes(bp: Any, eng: CapacityPlanningEngine) -> None:
    @bp.route("/forecast/<resource_name>", methods=["GET"])
    def forecast(resource_name: str) -> Any:
        """Forecast resource usage."""
        method = ForecastMethod(request.args.get("method", "linear"))
        horizon = float(request.args.get("horizon_hours", "24"))
        fc = eng.forecast(resource_name, method, horizon)
        if not fc:
            return _err("Insufficient data", "CPE_NODATA", 404)
        return jsonify(fc.to_dict())

def _register_plan_routes(bp: Any, eng: CapacityPlanningEngine) -> None:
    @bp.route("/plans", methods=["POST"])
    def generate_plan() -> Any:
        """Generate a capacity plan."""
        b = _body()
        plan = eng.generate_plan(
            name=b.get("name", ""),
            horizon_hours=float(b.get("horizon_hours", 24)),
        )
        return jsonify(plan.to_dict()), 201

    @bp.route("/plans", methods=["GET"])
    def list_plans() -> Any:
        """List plans."""
        s = request.args.get("status")
        status = PlanStatus(s) if s else None
        return jsonify([p.to_dict() for p in eng.list_plans(status)])

    @bp.route("/plans/<plan_id>", methods=["GET"])
    def get_plan(plan_id: str) -> Any:
        """Get a plan."""
        p = eng.get_plan(plan_id)
        if not p:
            return _err("Not found", "CPE_404", 404)
        return jsonify(p.to_dict())

    @bp.route("/plans/<plan_id>/archive", methods=["POST"])
    def archive_plan(plan_id: str) -> Any:
        """Archive a plan."""
        if eng.archive_plan(plan_id):
            return jsonify({"archived": True})
        return _err("Not found", "CPE_404", 404)

def _register_alert_routes(bp: Any, eng: CapacityPlanningEngine) -> None:
    @bp.route("/alerts", methods=["GET"])
    def get_alerts() -> Any:
        """Get alerts."""
        sev = request.args.get("severity")
        severity = AlertSeverity(sev) if sev else None
        return jsonify([a.to_dict() for a in eng.get_alerts(severity=severity)])

    @bp.route("/alerts/<alert_id>/acknowledge", methods=["POST"])
    def ack_alert(alert_id: str) -> Any:
        """Acknowledge an alert."""
        if eng.acknowledge_alert(alert_id):
            return jsonify({"acknowledged": True})
        return _err("Not found", "CPE_404", 404)

    @bp.route("/stats", methods=["GET"])
    def get_stats() -> Any:
        """Engine statistics."""
        return jsonify(eng.get_stats())

def create_capacity_api(engine: CapacityPlanningEngine) -> Any:
    """Create a Flask Blueprint exposing capacity planning endpoints."""
    if not _HAS_FLASK:
        return Blueprint("capacity", __name__)
    bp = Blueprint("capacity", __name__, url_prefix="/api/capacity")
    _register_metric_routes(bp, engine)
    _register_forecast_routes(bp, engine)
    _register_plan_routes(bp, engine)
    _register_alert_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp
