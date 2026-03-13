# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Predictive Maintenance Engine — PME-001

Owner: Operations · Dep: threading, uuid, dataclasses, statistics

Anomaly detection on hardware telemetry, predict failures before they
happen.  Ingest sensor readings, compute rolling statistics, apply
configurable threshold rules, raise alerts with severity levels, and
track asset health scores over time.
``create_predictive_maintenance_api(engine)`` → Flask Blueprint.
Safety: every mutation under ``threading.Lock``; bounded via capped_append.
"""
from __future__ import annotations

import logging
import statistics
import threading
import uuid
from collections import defaultdict
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
    from thread_safe_operations import capped_append
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

class SensorKind(str, Enum):
    """Kind of telemetry sensor."""
    temperature = "temperature"; vibration = "vibration"; pressure = "pressure"
    humidity = "humidity"; voltage = "voltage"; current = "current"
    rpm = "rpm"; flow_rate = "flow_rate"; noise = "noise"; custom = "custom"

class AlertSeverity(str, Enum):
    """Severity of a maintenance alert."""
    info = "info"; warning = "warning"; critical = "critical"; emergency = "emergency"

class AssetStatus(str, Enum):
    """Operational status of an asset."""
    healthy = "healthy"; degraded = "degraded"; at_risk = "at_risk"
    failed = "failed"; maintenance = "maintenance"; offline = "offline"

class AggregationWindow(str, Enum):
    """Time window for rolling statistics."""
    last_10 = "last_10"; last_50 = "last_50"; last_100 = "last_100"; last_500 = "last_500"
# -- Dataclass models ------------------------------------------------------

@dataclass
class SensorReading:
    """A single telemetry reading from a sensor."""
    reading_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_id: str = ""
    sensor_kind: str = "temperature"
    value: float = 0.0
    unit: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class ThresholdRule:
    """A configurable alerting rule for a sensor kind."""
    rule_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_id: str = ""
    sensor_kind: str = "temperature"
    warn_above: Optional[float] = None
    warn_below: Optional[float] = None
    critical_above: Optional[float] = None
    critical_below: Optional[float] = None
    emergency_above: Optional[float] = None
    emergency_below: Optional[float] = None
    enabled: bool = True
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class AnomalyAlert:
    """An alert raised when a reading breaches a threshold."""
    alert_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_id: str = ""
    sensor_kind: str = ""
    severity: str = "warning"
    value: float = 0.0
    threshold: float = 0.0
    direction: str = "above"
    rule_id: str = ""
    message: str = ""
    acknowledged: bool = False
    timestamp: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class AssetHealth:
    """Aggregated health snapshot for an asset."""
    asset_id: str = ""
    status: str = "healthy"
    health_score: float = 100.0
    reading_count: int = 0
    alert_count: int = 0
    last_reading_at: str = ""
    sensor_summary: Dict[str, Dict[str, float]] = field(default_factory=dict)
    updated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class MaintenancePrediction:
    """A predicted maintenance event for an asset."""
    prediction_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    asset_id: str = ""
    predicted_failure_kind: str = ""
    confidence: float = 0.0
    estimated_days_to_failure: float = 0.0
    recommendation: str = ""
    based_on_readings: int = 0
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class TelemetrySummary:
    """Statistical summary of telemetry for an asset+sensor pair."""
    asset_id: str = ""
    sensor_kind: str = ""
    count: int = 0
    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    trend_slope: float = 0.0
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)
# -- Helpers: linear-regression slope & safe stdev -------------------------

def _compute_slope(values: List[float]) -> float:
    """Compute simple linear regression slope for trend detection."""
    n = len(values)
    if n < 2:
        return 0.0
    x_vals = list(range(n))
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, values))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)
    if denominator == 0:
        return 0.0
    return numerator / denominator

def _safe_stdev(values: List[float]) -> float:
    """Standard deviation that handles <2 values."""
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)
# -- Engine ----------------------------------------------------------------

class PredictiveMaintenanceEngine:
    """Thread-safe predictive maintenance engine."""

    def __init__(self, max_readings_per_asset: int = 10_000,
                 max_alerts: int = 50_000) -> None:
        self._lock = threading.Lock()
        self._readings: Dict[str, List[SensorReading]] = defaultdict(list)
        self._rules: Dict[str, ThresholdRule] = {}
        self._alerts: List[AnomalyAlert] = []
        self._predictions: Dict[str, List[MaintenancePrediction]] = defaultdict(list)
        self._assets: Dict[str, AssetHealth] = {}
        self._history: List[dict] = []
        self._max_readings = max_readings_per_asset
        self._max_alerts = max_alerts
    # -- Readings -----------------------------------------------------------

    def ingest_reading(self, asset_id: str,
                       sensor_kind: Union[str, SensorKind] = "temperature",
                       value: float = 0.0, unit: str = "",
                       metadata: Optional[Dict[str, Any]] = None) -> SensorReading:
        """Record a telemetry reading and evaluate threshold rules."""
        reading = SensorReading(
            asset_id=asset_id, sensor_kind=_enum_val(sensor_kind),
            value=value, unit=unit, metadata=metadata or {},
        )
        with self._lock:
            lst = self._readings[asset_id]
            capped_append(lst, reading, self._max_readings)
            self._ensure_asset(asset_id)
            self._assets[asset_id].reading_count = len(lst)
            self._assets[asset_id].last_reading_at = reading.timestamp
            capped_append(self._history, {"action": "ingest",
                          "asset": asset_id, "ts": _now()}, 50_000)
        self._evaluate_rules(reading)
        return reading

    def get_readings(self, asset_id: str,
                     sensor_kind: Optional[str] = None,
                     limit: int = 100) -> List[SensorReading]:
        """Return recent readings for an asset, optionally filtered."""
        with self._lock:
            readings = list(self._readings.get(asset_id, []))
        if sensor_kind:
            sk = _enum_val(sensor_kind)
            readings = [r for r in readings if r.sensor_kind == sk]
        return readings[-limit:]
    # -- Rules --------------------------------------------------------------

    def add_rule(self, asset_id: str,
                 sensor_kind: Union[str, SensorKind] = "temperature",
                 warn_above: Optional[float] = None,
                 warn_below: Optional[float] = None,
                 critical_above: Optional[float] = None,
                 critical_below: Optional[float] = None,
                 emergency_above: Optional[float] = None,
                 emergency_below: Optional[float] = None) -> ThresholdRule:
        """Create a threshold alerting rule."""
        rule = ThresholdRule(
            asset_id=asset_id, sensor_kind=_enum_val(sensor_kind),
            warn_above=warn_above, warn_below=warn_below,
            critical_above=critical_above, critical_below=critical_below,
            emergency_above=emergency_above, emergency_below=emergency_below,
        )
        with self._lock:
            self._rules[rule.rule_id] = rule
        return rule

    def get_rule(self, rule_id: str) -> Optional[ThresholdRule]:
        """Look up a rule by ID."""
        with self._lock:
            return self._rules.get(rule_id)

    def list_rules(self, asset_id: Optional[str] = None,
                   sensor_kind: Optional[str] = None,
                   limit: int = 100) -> List[ThresholdRule]:
        """List threshold rules with optional filters."""
        with self._lock:
            rules = list(self._rules.values())
        if asset_id:
            rules = [r for r in rules if r.asset_id == asset_id]
        if sensor_kind:
            sk = _enum_val(sensor_kind)
            rules = [r for r in rules if r.sensor_kind == sk]
        return rules[:limit]

    def update_rule(self, rule_id: str, enabled: Optional[bool] = None,
                    warn_above: Optional[float] = None,
                    critical_above: Optional[float] = None,
                    emergency_above: Optional[float] = None) -> Optional[ThresholdRule]:
        """Update mutable fields on a rule."""
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule is None:
                return None
            if enabled is not None:
                rule.enabled = enabled
            if warn_above is not None:
                rule.warn_above = warn_above
            if critical_above is not None:
                rule.critical_above = critical_above
            if emergency_above is not None:
                rule.emergency_above = emergency_above
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Remove a threshold rule."""
        with self._lock:
            return self._rules.pop(rule_id, None) is not None
    # -- Rule evaluation ----------------------------------------------------

    def _evaluate_rules(self, reading: SensorReading) -> None:
        """Check reading against all matching rules and raise alerts."""
        with self._lock:
            matching = [r for r in self._rules.values()
                        if r.enabled and r.asset_id == reading.asset_id
                        and r.sensor_kind == reading.sensor_kind]
        for rule in matching:
            self._check_thresholds(reading, rule)

    def _check_thresholds(self, reading: SensorReading,
                          rule: ThresholdRule) -> None:
        """Evaluate a single rule against a reading."""
        checks = [
            (rule.emergency_above, "above", "emergency"),
            (rule.emergency_below, "below", "emergency"),
            (rule.critical_above, "above", "critical"),
            (rule.critical_below, "below", "critical"),
            (rule.warn_above, "above", "warning"),
            (rule.warn_below, "below", "warning"),
        ]
        for threshold, direction, severity in checks:
            if threshold is None:
                continue
            breached = (reading.value > threshold if direction == "above"
                        else reading.value < threshold)
            if breached:
                self._raise_alert(reading, rule, threshold, direction, severity)
                return  # highest severity wins

    def _raise_alert(self, reading: SensorReading, rule: ThresholdRule,
                     threshold: float, direction: str, severity: str) -> None:
        """Create and store an anomaly alert."""
        alert = AnomalyAlert(
            asset_id=reading.asset_id, sensor_kind=reading.sensor_kind,
            severity=severity, value=reading.value, threshold=threshold,
            direction=direction, rule_id=rule.rule_id,
            message=f"{reading.sensor_kind} {direction} {threshold} "
                    f"(got {reading.value})",
        )
        with self._lock:
            capped_append(self._alerts, alert, self._max_alerts)
            self._ensure_asset(reading.asset_id)
            ah = self._assets[reading.asset_id]
            ah.alert_count += 1
            self._update_health_status(ah)
    # -- Alerts -------------------------------------------------------------

    def get_alerts(self, asset_id: Optional[str] = None,
                   severity: Optional[str] = None,
                   acknowledged: Optional[bool] = None,
                   limit: int = 100) -> List[AnomalyAlert]:
        """List alerts with optional filters."""
        with self._lock:
            alerts = list(self._alerts)
        if asset_id:
            alerts = [a for a in alerts if a.asset_id == asset_id]
        if severity:
            sv = _enum_val(severity)
            alerts = [a for a in alerts if a.severity == sv]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        return alerts[-limit:]

    def acknowledge_alert(self, alert_id: str) -> Optional[AnomalyAlert]:
        """Mark an alert as acknowledged."""
        with self._lock:
            for alert in self._alerts:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    return alert
        return None
    # -- Asset health -------------------------------------------------------

    def _ensure_asset(self, asset_id: str) -> None:
        """Create asset health record if it doesn't exist (caller holds lock)."""
        if asset_id not in self._assets:
            self._assets[asset_id] = AssetHealth(asset_id=asset_id)

    def _update_health_status(self, ah: AssetHealth) -> None:
        """Recompute health status based on alert counts (caller holds lock)."""
        ratio = ah.alert_count / max(ah.reading_count, 1)
        if ratio > 0.3:
            ah.status = "at_risk"
            ah.health_score = max(0.0, 100.0 - ratio * 200)
        elif ratio > 0.1:
            ah.status = "degraded"
            ah.health_score = max(30.0, 100.0 - ratio * 150)
        else:
            ah.status = "healthy"
            ah.health_score = max(60.0, 100.0 - ratio * 100)
        ah.updated_at = _now()

    def get_asset_health(self, asset_id: str) -> Optional[AssetHealth]:
        """Return the current health snapshot for an asset."""
        with self._lock:
            ah = self._assets.get(asset_id)
            if ah is None:
                return None
            ah.sensor_summary = self._compute_sensor_summary(asset_id)
        return ah

    def _compute_sensor_summary(self, asset_id: str) -> Dict[str, Dict[str, float]]:
        """Build per-sensor-kind summary stats (caller holds lock)."""
        readings = self._readings.get(asset_id, [])
        by_kind: Dict[str, List[float]] = defaultdict(list)
        for r in readings[-500:]:
            by_kind[r.sensor_kind].append(r.value)
        summary: Dict[str, Dict[str, float]] = {}
        for kind, vals in by_kind.items():
            summary[kind] = {
                "mean": round(statistics.mean(vals), 4),
                "std_dev": round(_safe_stdev(vals), 4),
                "min": min(vals),
                "max": max(vals),
                "count": float(len(vals)),
            }
        return summary

    def list_assets(self, status: Optional[str] = None,
                    limit: int = 100) -> List[AssetHealth]:
        """List all tracked assets."""
        with self._lock:
            assets = list(self._assets.values())
        if status:
            sv = _enum_val(status)
            assets = [a for a in assets if a.status == sv]
        return assets[:limit]

    def set_asset_status(self, asset_id: str,
                         status: Union[str, AssetStatus]) -> Optional[AssetHealth]:
        """Manually override asset status (e.g., mark as maintenance)."""
        with self._lock:
            ah = self._assets.get(asset_id)
            if ah is None:
                return None
            ah.status = _enum_val(status)
            ah.updated_at = _now()
        return ah
    # -- Telemetry summary --------------------------------------------------

    def get_telemetry_summary(self, asset_id: str,
                              sensor_kind: Union[str, SensorKind] = "temperature",
                              window: Union[str, AggregationWindow] = "last_100",
                              ) -> TelemetrySummary:
        """Compute rolling statistics for a sensor on an asset."""
        sk = _enum_val(sensor_kind)
        win_map = {"last_10": 10, "last_50": 50, "last_100": 100, "last_500": 500}
        win_size = win_map.get(_enum_val(window), 100)
        with self._lock:
            readings = self._readings.get(asset_id, [])
            vals = [r.value for r in readings if r.sensor_kind == sk]
        vals = vals[-win_size:]
        if not vals:
            return TelemetrySummary(asset_id=asset_id, sensor_kind=sk)
        return TelemetrySummary(
            asset_id=asset_id, sensor_kind=sk, count=len(vals),
            mean=round(statistics.mean(vals), 4),
            median=round(statistics.median(vals), 4),
            std_dev=round(_safe_stdev(vals), 4),
            min_val=min(vals), max_val=max(vals),
            trend_slope=round(_compute_slope(vals), 6),
        )
    # -- Predictions --------------------------------------------------------

    def predict_maintenance(self, asset_id: str,
                            sensor_kind: Union[str, SensorKind] = "temperature",
                            ) -> MaintenancePrediction:
        """Generate a maintenance prediction based on trend analysis."""
        sk = _enum_val(sensor_kind)
        summary = self.get_telemetry_summary(asset_id, sk)
        prediction = self._build_prediction(asset_id, sk, summary)
        with self._lock:
            capped_append(self._predictions[asset_id], prediction, 1_000)
        return prediction

    def _build_prediction(self, asset_id: str, sensor_kind: str,
                          summary: TelemetrySummary) -> MaintenancePrediction:
        """Build a prediction from telemetry summary (pure computation)."""
        if summary.count < 5:
            return MaintenancePrediction(
                asset_id=asset_id, predicted_failure_kind="insufficient_data",
                confidence=0.0, estimated_days_to_failure=-1,
                recommendation="Collect more telemetry data",
                based_on_readings=summary.count,
            )
        confidence = self._compute_confidence(summary)
        days = self._estimate_days_to_failure(summary)
        rec = self._generate_recommendation(confidence, days, sensor_kind)
        failure_kind = self._classify_failure(summary, sensor_kind)
        return MaintenancePrediction(
            asset_id=asset_id, predicted_failure_kind=failure_kind,
            confidence=round(confidence, 4),
            estimated_days_to_failure=round(days, 1),
            recommendation=rec, based_on_readings=summary.count,
        )

    @staticmethod
    def _compute_confidence(summary: TelemetrySummary) -> float:
        """Heuristic confidence based on data quality and trend strength."""
        data_quality = min(1.0, summary.count / 100.0)
        trend_strength = min(1.0, abs(summary.trend_slope) * 10)
        variability = 1.0 - min(1.0, summary.std_dev / max(abs(summary.mean), 1e-9))
        return max(0.0, min(1.0, (data_quality * 0.3 + trend_strength * 0.4
                                   + max(0.0, variability) * 0.3)))

    @staticmethod
    def _estimate_days_to_failure(summary: TelemetrySummary) -> float:
        """Rough estimate of days until threshold breach based on slope."""
        if abs(summary.trend_slope) < 1e-9:
            return 365.0
        headroom = max(0.0, summary.max_val - summary.mean)
        if summary.trend_slope > 0:
            readings_to_breach = headroom / summary.trend_slope
        else:
            readings_to_breach = abs(summary.min_val - summary.mean) / abs(summary.trend_slope)
        readings_per_day = max(1.0, summary.count / 30.0)
        return max(0.1, readings_to_breach / readings_per_day)

    @staticmethod
    def _classify_failure(summary: TelemetrySummary,
                          sensor_kind: str) -> str:
        """Classify the predicted failure type from sensor+trend."""
        if summary.trend_slope > 0.5:
            return f"{sensor_kind}_rising_trend"
        if summary.trend_slope < -0.5:
            return f"{sensor_kind}_falling_trend"
        if summary.std_dev > abs(summary.mean) * 0.5:
            return f"{sensor_kind}_high_variance"
        return f"{sensor_kind}_gradual_degradation"

    @staticmethod
    def _generate_recommendation(confidence: float, days: float,
                                 sensor_kind: str) -> str:
        """Generate a human-readable maintenance recommendation."""
        if confidence < 0.2:
            return f"Low confidence — continue monitoring {sensor_kind}"
        if days < 7:
            return f"Schedule urgent {sensor_kind} maintenance within 7 days"
        if days < 30:
            return f"Plan {sensor_kind} maintenance within 30 days"
        return f"Monitor {sensor_kind} — no immediate action required"

    def get_predictions(self, asset_id: str,
                        limit: int = 20) -> List[MaintenancePrediction]:
        """Return recent predictions for an asset."""
        with self._lock:
            preds = list(self._predictions.get(asset_id, []))
        return preds[-limit:]
    # -- Bulk / export ------------------------------------------------------

    def export_state(self) -> dict:
        """Serialise engine state to a plain dict."""
        with self._lock:
            return {
                "readings": {aid: [r.to_dict() for r in rs]
                             for aid, rs in self._readings.items()},
                "rules": {rid: r.to_dict() for rid, r in self._rules.items()},
                "alerts": [a.to_dict() for a in self._alerts],
                "assets": {aid: a.to_dict() for aid, a in self._assets.items()},
                "exported_at": _now(),
            }

    def clear(self) -> None:
        """Remove all state."""
        with self._lock:
            self._readings.clear()
            self._rules.clear()
            self._alerts.clear()
            self._predictions.clear()
            self._assets.clear()
            capped_append(self._history, {"action": "clear", "ts": _now()}, 50_000)
# -- Wingman & Sandbox gates -----------------------------------------------

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """PME-001 Wingman gate."""
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


def gate_pme_in_sandbox(context: dict) -> dict:
    """PME-001 Causality Sandbox gate."""
    required_keys = {"asset_id"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("asset_id"):
        return {"passed": False, "message": "asset_id must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "asset_id": context["asset_id"]}
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

def create_predictive_maintenance_api(
    engine: PredictiveMaintenanceEngine,
) -> Any:
    """Create a Flask Blueprint with predictive-maintenance REST endpoints."""
    bp = Blueprint("pme", __name__, url_prefix="/api")
    eng = engine

    @bp.route("/pme/readings", methods=["POST"])
    def ingest_reading() -> Any:
        body = _api_body()
        err = _api_need(body, "asset_id")
        if err:
            return err
        r = eng.ingest_reading(
            asset_id=body["asset_id"],
            sensor_kind=body.get("sensor_kind", "temperature"),
            value=float(body.get("value", 0)),
            unit=body.get("unit", ""),
            metadata=body.get("metadata", {}),
        )
        return jsonify(r.to_dict()), 201

    @bp.route("/pme/readings/<asset_id>", methods=["GET"])
    def get_readings(asset_id: str) -> Any:
        a = request.args
        readings = eng.get_readings(
            asset_id, sensor_kind=a.get("sensor_kind"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in readings]), 200

    @bp.route("/pme/rules", methods=["POST"])
    def add_rule() -> Any:
        body = _api_body()
        err = _api_need(body, "asset_id")
        if err:
            return err
        rule = eng.add_rule(
            asset_id=body["asset_id"],
            sensor_kind=body.get("sensor_kind", "temperature"),
            warn_above=body.get("warn_above"),
            warn_below=body.get("warn_below"),
            critical_above=body.get("critical_above"),
            critical_below=body.get("critical_below"),
            emergency_above=body.get("emergency_above"),
            emergency_below=body.get("emergency_below"),
        )
        return jsonify(rule.to_dict()), 201

    @bp.route("/pme/rules", methods=["GET"])
    def list_rules() -> Any:
        a = request.args
        rules = eng.list_rules(
            asset_id=a.get("asset_id"), sensor_kind=a.get("sensor_kind"),
            limit=int(a.get("limit", 100)),
        )
        return jsonify([r.to_dict() for r in rules]), 200

    @bp.route("/pme/rules/<rule_id>", methods=["GET"])
    def get_rule(rule_id: str) -> Any:
        rule = eng.get_rule(rule_id)
        if rule is None:
            return _not_found("Rule not found")
        return jsonify(rule.to_dict()), 200

    @bp.route("/pme/rules/<rule_id>", methods=["PUT"])
    def update_rule(rule_id: str) -> Any:
        body = _api_body()
        rule = eng.update_rule(
            rule_id, enabled=body.get("enabled"),
            warn_above=body.get("warn_above"),
            critical_above=body.get("critical_above"),
            emergency_above=body.get("emergency_above"),
        )
        if rule is None:
            return _not_found("Rule not found")
        return jsonify(rule.to_dict()), 200

    @bp.route("/pme/rules/<rule_id>", methods=["DELETE"])
    def delete_rule(rule_id: str) -> Any:
        if not eng.delete_rule(rule_id):
            return _not_found("Rule not found")
        return jsonify({"deleted": True}), 200

    @bp.route("/pme/alerts", methods=["GET"])
    def get_alerts() -> Any:
        a = request.args
        ack = None
        if "acknowledged" in a:
            ack = a["acknowledged"].lower() == "true"
        alerts = eng.get_alerts(
            asset_id=a.get("asset_id"), severity=a.get("severity"),
            acknowledged=ack, limit=int(a.get("limit", 100)),
        )
        return jsonify([al.to_dict() for al in alerts]), 200

    @bp.route("/pme/alerts/<alert_id>/ack", methods=["POST"])
    def acknowledge_alert(alert_id: str) -> Any:
        alert = eng.acknowledge_alert(alert_id)
        if alert is None:
            return _not_found("Alert not found")
        return jsonify(alert.to_dict()), 200

    @bp.route("/pme/assets", methods=["GET"])
    def list_assets() -> Any:
        a = request.args
        assets = eng.list_assets(
            status=a.get("status"), limit=int(a.get("limit", 100)),
        )
        return jsonify([ah.to_dict() for ah in assets]), 200

    @bp.route("/pme/assets/<asset_id>/health", methods=["GET"])
    def get_asset_health(asset_id: str) -> Any:
        ah = eng.get_asset_health(asset_id)
        if ah is None:
            return _not_found("Asset not found")
        return jsonify(ah.to_dict()), 200

    @bp.route("/pme/assets/<asset_id>/status", methods=["PUT"])
    def set_asset_status(asset_id: str) -> Any:
        body = _api_body()
        err = _api_need(body, "status")
        if err:
            return err
        ah = eng.set_asset_status(asset_id, body["status"])
        if ah is None:
            return _not_found("Asset not found")
        return jsonify(ah.to_dict()), 200

    @bp.route("/pme/telemetry/<asset_id>", methods=["GET"])
    def get_telemetry(asset_id: str) -> Any:
        a = request.args
        summary = eng.get_telemetry_summary(
            asset_id, sensor_kind=a.get("sensor_kind", "temperature"),
            window=a.get("window", "last_100"),
        )
        return jsonify(summary.to_dict()), 200

    @bp.route("/pme/predict/<asset_id>", methods=["POST"])
    def predict_maintenance(asset_id: str) -> Any:
        body = _api_body()
        pred = eng.predict_maintenance(
            asset_id, sensor_kind=body.get("sensor_kind", "temperature"),
        )
        return jsonify(pred.to_dict()), 200

    @bp.route("/pme/predictions/<asset_id>", methods=["GET"])
    def get_predictions(asset_id: str) -> Any:
        a = request.args
        preds = eng.get_predictions(
            asset_id, limit=int(a.get("limit", 20)),
        )
        return jsonify([p.to_dict() for p in preds]), 200

    @bp.route("/pme/export", methods=["POST"])
    def export_state() -> Any:
        return jsonify(eng.export_state()), 200

    @bp.route("/pme/health", methods=["GET"])
    def health() -> Any:
        assets = eng.list_assets()
        return jsonify({
            "status": "healthy", "module": "PME-001",
            "tracked_assets": len(assets),
        }), 200

    require_blueprint_auth(bp)
    return bp
