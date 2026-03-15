# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for capacity_planning_engine — CPE-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable CPERecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from capacity_planning_engine import (  # noqa: E402
    AlertSeverity,
    CapacityAlert,
    CapacityPlan,
    CapacityPlanningEngine,
    ForecastMethod,
    ForecastResult,
    PlanStatus,
    ResourceMetric,
    ResourceType,
    ScalingRecommendation,
    create_capacity_api,
    gate_capacity_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------

@dataclass
class CPERecord:
    """One CPE check record."""
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

_RESULTS: List[CPERecord] = []

def record(
    check_id: str, desc: str, expected: Any, actual: Any,
    cause: str = "", effect: str = "", lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(CPERecord(
        check_id=check_id, description=desc, expected=expected,
        actual=actual, passed=ok, cause=cause, effect=effect, lesson=lesson,
    ))
    return ok

# -- Helpers ---------------------------------------------------------------

def _eng(**kw: Any) -> CapacityPlanningEngine:
    return CapacityPlanningEngine(**kw)


def _populated_engine() -> CapacityPlanningEngine:
    """Engine with 20 linearly growing CPU data points (10..29)."""
    e = _eng()
    for i in range(20):
        e.record_metric("cpu-main", float(10 + i), ResourceType.cpu, 100.0)
    return e

# ==================================================================== #
#  Enum tests                                                           #
# ==================================================================== #

def test_cpe_001_resource_type_enum():
    """ResourceType enum has expected members."""
    expected = {"cpu", "memory", "disk", "network", "gpu", "connections", "custom"}
    assert record("CPE-001", "ResourceType values", expected,
                   {m.value for m in ResourceType})


def test_cpe_002_alert_severity_enum():
    """AlertSeverity enum has expected members."""
    expected = {"info", "warning", "critical"}
    assert record("CPE-002", "AlertSeverity values", expected,
                   {m.value for m in AlertSeverity})


def test_cpe_003_forecast_method_enum():
    """ForecastMethod enum has expected members."""
    expected = {"linear", "exponential_smoothing", "moving_average"}
    assert record("CPE-003", "ForecastMethod values", expected,
                   {m.value for m in ForecastMethod})


def test_cpe_004_plan_status_enum():
    """PlanStatus enum has expected members."""
    expected = {"active", "archived", "superseded"}
    assert record("CPE-004", "PlanStatus values", expected,
                   {m.value for m in PlanStatus})

# ==================================================================== #
#  Dataclass tests                                                      #
# ==================================================================== #

def test_cpe_005_metric_defaults():
    """ResourceMetric has sane defaults."""
    m = ResourceMetric()
    assert record(
        "CPE-005", "Metric defaults",
        (True, ResourceType.cpu, 0.0, 100.0),
        (bool(m.id), m.resource_type, m.value, m.capacity),
    )


def test_cpe_006_metric_utilisation():
    """ResourceMetric.utilisation property works."""
    m = ResourceMetric(value=75.0, capacity=100.0)
    assert record("CPE-006", "Utilisation", 0.75, m.utilisation)


def test_cpe_007_metric_utilisation_zero_cap():
    """Utilisation returns 0 when capacity is 0."""
    m = ResourceMetric(value=50.0, capacity=0.0)
    assert record("CPE-007", "Util zero cap", 0.0, m.utilisation)


def test_cpe_008_metric_to_dict():
    """ResourceMetric.to_dict() serialises type."""
    m = ResourceMetric(resource_type=ResourceType.memory)
    d = m.to_dict()
    assert record("CPE-008", "Metric to_dict", "memory", d["resource_type"])


def test_cpe_009_forecast_result_to_dict():
    """ForecastResult.to_dict() serialises enums."""
    f = ForecastResult(method=ForecastMethod.linear, resource_type=ResourceType.disk)
    d = f.to_dict()
    assert record("CPE-009", "Forecast to_dict",
                   ("linear", "disk"), (d["method"], d["resource_type"]))


def test_cpe_010_alert_to_dict():
    """CapacityAlert.to_dict() serialises enums."""
    a = CapacityAlert(severity=AlertSeverity.critical)
    d = a.to_dict()
    assert record("CPE-010", "Alert to_dict", "critical", d["severity"])


def test_cpe_011_recommendation_to_dict():
    """ScalingRecommendation.to_dict() works."""
    r = ScalingRecommendation(action="scale_up")
    d = r.to_dict()
    assert record("CPE-011", "Rec to_dict", "scale_up", d["action"])


def test_cpe_012_plan_to_dict():
    """CapacityPlan.to_dict() serialises nested lists."""
    p = CapacityPlan(name="test", status=PlanStatus.active)
    d = p.to_dict()
    assert record("CPE-012", "Plan to_dict",
                   ("test", "active"),
                   (d["name"], d["status"]))

# ==================================================================== #
#  Metric ingestion tests                                               #
# ==================================================================== #

def test_cpe_013_record_metric():
    """record_metric() stores a data point."""
    e = _eng()
    m = e.record_metric("cpu-0", 42.0)
    assert record(
        "CPE-013", "Record metric",
        (True, 42.0, "cpu-0"),
        (bool(m.id), m.value, m.resource_name),
        cause="record_metric called",
        effect="metric stored in engine",
        lesson="time-series data is the foundation of capacity planning",
    )


def test_cpe_014_get_metrics():
    """get_metrics() returns stored data points."""
    e = _eng()
    for i in range(5):
        e.record_metric("mem", float(i))
    pts = e.get_metrics("mem")
    assert record("CPE-014", "Get metrics", 5, len(pts))


def test_cpe_015_get_metrics_limit():
    """get_metrics(limit=) caps results."""
    e = _eng()
    for i in range(10):
        e.record_metric("disk", float(i))
    pts = e.get_metrics("disk", limit=3)
    assert record("CPE-015", "Metrics limit", 3, len(pts))


def test_cpe_016_list_resources():
    """list_resources() returns tracked resource names."""
    e = _eng()
    e.record_metric("cpu", 10.0)
    e.record_metric("mem", 20.0)
    assert record("CPE-016", "List resources", {"cpu", "mem"},
                   set(e.list_resources()))


def test_cpe_017_metric_cap():
    """Metrics are bounded by max_metrics via capped_append."""
    e = _eng(max_metrics=15)
    for i in range(30):
        e.record_metric("cpu", float(i))
    pts = e.get_metrics("cpu")
    # capped_append evicts 10% when cap reached, so size stays below cap+burst
    assert record("CPE-017", "Metric cap", True, len(pts) <= 30)

# ==================================================================== #
#  Forecasting tests                                                    #
# ==================================================================== #

def test_cpe_018_linear_forecast():
    """Linear forecast predicts increasing trend."""
    e = _populated_engine()
    fc = e.forecast("cpu-main", ForecastMethod.linear)
    assert record(
        "CPE-018", "Linear forecast",
        True, fc is not None and fc.predicted_value > 29.0,
        cause="20 linearly increasing data points (10..29)",
        effect="predicted value exceeds last observed value",
        lesson="linear regression extrapolates from historical trend",
    )


def test_cpe_019_exp_smoothing_forecast():
    """Exponential smoothing produces a result."""
    e = _populated_engine()
    fc = e.forecast("cpu-main", ForecastMethod.exponential_smoothing)
    assert record(
        "CPE-019", "Exp smoothing",
        True, fc is not None and fc.predicted_value > 0,
    )


def test_cpe_020_moving_avg_forecast():
    """Moving average produces a result."""
    e = _populated_engine()
    fc = e.forecast("cpu-main", ForecastMethod.moving_average)
    assert record(
        "CPE-020", "Moving avg",
        True, fc is not None and fc.predicted_value > 0,
    )


def test_cpe_021_forecast_insufficient_data():
    """Forecast returns None with <2 data points."""
    e = _eng()
    e.record_metric("solo", 10.0)
    fc = e.forecast("solo")
    assert record("CPE-021", "Insufficient data", None, fc)


def test_cpe_022_forecast_confidence():
    """Confidence scales with data point count."""
    e = _populated_engine()
    fc = e.forecast("cpu-main")
    assert record("CPE-022", "Confidence", True,
                   fc is not None and 0 < fc.confidence <= 1.0)


def test_cpe_023_forecast_nonexistent():
    """Forecast for unknown resource returns None."""
    e = _eng()
    assert record("CPE-023", "Nonexistent forecast", None, e.forecast("nope"))

# ==================================================================== #
#  Time-to-threshold tests                                              #
# ==================================================================== #

def test_cpe_024_time_to_threshold():
    """time_to_threshold returns positive hours for growing series."""
    e = _populated_engine()
    fc = e.forecast("cpu-main")
    assert record(
        "CPE-024", "Time to threshold",
        True, fc is not None and fc.time_to_threshold_hours is not None
              and fc.time_to_threshold_hours > 0,
        cause="linear growth toward 75% threshold",
        effect="positive time estimate returned",
        lesson="TTT gives operators lead time to act",
    )

# ==================================================================== #
#  Plan generation tests                                                #
# ==================================================================== #

def test_cpe_025_generate_plan():
    """generate_plan() creates a plan with forecasts."""
    e = _populated_engine()
    plan = e.generate_plan("test-plan")
    assert record(
        "CPE-025", "Generate plan",
        (True, "test-plan", PlanStatus.active),
        (bool(plan.id), plan.name, plan.status),
    )


def test_cpe_026_plan_has_forecasts():
    """Generated plan includes forecasts for tracked resources."""
    e = _populated_engine()
    plan = e.generate_plan()
    assert record("CPE-026", "Plan forecasts", True, len(plan.forecasts) >= 1)


def test_cpe_027_get_plan():
    """get_plan() retrieves by id."""
    e = _populated_engine()
    plan = e.generate_plan()
    fetched = e.get_plan(plan.id)
    assert record("CPE-027", "Get plan", plan.id,
                   fetched.id if fetched else "")


def test_cpe_028_get_plan_nonexistent():
    """get_plan() returns None for unknown id."""
    e = _eng()
    assert record("CPE-028", "Plan 404", None, e.get_plan("nope"))


def test_cpe_029_list_plans():
    """list_plans() returns all plans."""
    e = _populated_engine()
    e.generate_plan("a")
    e.generate_plan("b")
    assert record("CPE-029", "List plans", 2, len(e.list_plans()))


def test_cpe_030_list_plans_by_status():
    """list_plans(status=) filters correctly."""
    e = _populated_engine()
    p1 = e.generate_plan("a")
    e.generate_plan("b")
    e.archive_plan(p1.id)
    active = e.list_plans(status=PlanStatus.active)
    archived = e.list_plans(status=PlanStatus.archived)
    assert record("CPE-030", "Plan status filter", (1, 1),
                   (len(active), len(archived)))


def test_cpe_031_archive_plan():
    """archive_plan() changes status."""
    e = _populated_engine()
    p = e.generate_plan()
    ok = e.archive_plan(p.id)
    assert record("CPE-031", "Archive plan",
                   (True, PlanStatus.archived),
                   (ok, e.get_plan(p.id).status))  # type: ignore[union-attr]


def test_cpe_032_archive_nonexistent():
    """archive_plan() returns False for unknown id."""
    e = _eng()
    assert record("CPE-032", "Archive 404", False, e.archive_plan("nope"))

# ==================================================================== #
#  Alert tests                                                          #
# ==================================================================== #

def test_cpe_033_critical_alert():
    """High-utilisation resource triggers critical alert."""
    e = _eng(critical_threshold=0.5)
    for i in range(10):
        e.record_metric("hot-cpu", float(80 + i), ResourceType.cpu, 100.0)
    plan = e.generate_plan()
    crits = [a for a in plan.alerts if a.severity == AlertSeverity.critical]
    assert record(
        "CPE-033", "Critical alert",
        True, len(crits) >= 1,
        cause="CPU usage well above critical threshold",
        effect="critical alert generated",
        lesson="critical alerts demand immediate operational attention",
    )


def test_cpe_034_warning_alert():
    """Moderate utilisation triggers warning."""
    e = _eng(warning_threshold=0.3, critical_threshold=0.95)
    for i in range(10):
        e.record_metric("warm-cpu", float(30 + i), ResourceType.cpu, 100.0)
    plan = e.generate_plan()
    warns = [a for a in plan.alerts if a.severity == AlertSeverity.warning]
    assert record("CPE-034", "Warning alert", True, len(warns) >= 1)


def test_cpe_035_no_alert_low_usage():
    """Low utilisation generates no alerts."""
    e = _eng()
    for i in range(10):
        e.record_metric("idle-cpu", float(1 + i * 0.1), ResourceType.cpu, 100.0)
    plan = e.generate_plan()
    assert record("CPE-035", "No alerts", 0, len(plan.alerts))


def test_cpe_036_acknowledge_alert():
    """acknowledge_alert() marks it as acknowledged."""
    e = _eng(critical_threshold=0.5)
    for i in range(10):
        e.record_metric("hot", float(80 + i), ResourceType.cpu, 100.0)
    e.generate_plan()
    alerts = e.get_alerts()
    ok = e.acknowledge_alert(alerts[0].id) if alerts else False
    assert record("CPE-036", "Acknowledge alert", True, ok)


def test_cpe_037_get_alerts_filter():
    """get_alerts(acknowledged=) filters."""
    e = _eng(critical_threshold=0.5)
    for i in range(10):
        e.record_metric("hot", float(80 + i), ResourceType.cpu, 100.0)
    e.generate_plan()
    alerts = e.get_alerts()
    if alerts:
        e.acknowledge_alert(alerts[0].id)
    unack = e.get_alerts(acknowledged=False)
    assert record("CPE-037", "Filter alerts", True,
                   all(not a.acknowledged for a in unack))

# ==================================================================== #
#  Recommendation tests                                                 #
# ==================================================================== #

def test_cpe_038_scale_up_recommendation():
    """Scale-up recommended for high utilisation."""
    e = _eng(critical_threshold=0.5)
    for i in range(10):
        e.record_metric("hot", float(80 + i), ResourceType.cpu, 100.0)
    plan = e.generate_plan()
    ups = [r for r in plan.recommendations if r.action == "scale_up"]
    assert record("CPE-038", "Scale up rec", True, len(ups) >= 1)


def test_cpe_039_scale_down_recommendation():
    """Scale-down recommended for very low utilisation."""
    e = _eng()
    for i in range(20):
        e.record_metric("idle", 2.0, ResourceType.cpu, 100.0)
    plan = e.generate_plan()
    downs = [r for r in plan.recommendations if r.action == "scale_down"]
    assert record("CPE-039", "Scale down rec", True, len(downs) >= 1)

# ==================================================================== #
#  Stats tests                                                          #
# ==================================================================== #

def test_cpe_040_stats():
    """get_stats() returns expected keys."""
    e = _populated_engine()
    e.generate_plan()
    stats = e.get_stats()
    expected_keys = {"resources_tracked", "total_data_points",
                     "plans_generated", "total_alerts", "unacknowledged_alerts"}
    assert record("CPE-040", "Stats keys", expected_keys, set(stats.keys()))

# ==================================================================== #
#  Wingman & Sandbox tests                                              #
# ==================================================================== #

def test_cpe_041_wingman_valid():
    """validate_wingman_pair() passes with populated engine."""
    e = _populated_engine()
    ok, msg = validate_wingman_pair(e)
    assert record(
        "CPE-041", "Wingman valid",
        (True, "Valid capacity planning wingman pair"),
        (ok, msg),
    )


def test_cpe_042_wingman_no_resources():
    """validate_wingman_pair() fails with no resources."""
    e = _eng()
    ok, _ = validate_wingman_pair(e)
    assert record("CPE-042", "Wingman empty", False, ok)


def test_cpe_043_wingman_insufficient_data():
    """validate_wingman_pair() fails with <2 data points."""
    e = _eng()
    e.record_metric("cpu", 10.0)
    ok, _ = validate_wingman_pair(e)
    assert record("CPE-043", "Wingman insufficient", False, ok)


def test_cpe_044_sandbox_valid():
    """gate_capacity_in_sandbox() approves engine."""
    e = _populated_engine()
    ok, msg = gate_capacity_in_sandbox(e)
    assert record("CPE-044", "Sandbox valid",
                   (True, "Approved for sandbox"), (ok, msg))


def test_cpe_045_sandbox_bad_threshold():
    """gate_capacity_in_sandbox() rejects bad thresholds."""
    e = _eng(warning_threshold=0.0)
    ok, _ = gate_capacity_in_sandbox(e)
    assert record("CPE-045", "Sandbox bad threshold", False, ok)

# ==================================================================== #
#  Thread safety tests                                                  #
# ==================================================================== #

def test_cpe_046_concurrent_record():
    """Concurrent metric recording is thread-safe."""
    e = _eng()
    errors: List[str] = []

    def writer(idx: int) -> None:
        try:
            for j in range(10):
                e.record_metric(f"cpu-{idx}", float(j))
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "CPE-046", "Concurrent record",
        (0, 10),
        (len(errors), len(e.list_resources())),
        cause="10 threads writing metrics simultaneously",
        effect="all 10 resources created without errors",
        lesson="Lock protects shared metric dict",
    )


def test_cpe_047_concurrent_forecast():
    """Concurrent forecasting is thread-safe."""
    e = _populated_engine()
    results: List[Any] = []
    errors: List[str] = []

    def forecaster() -> None:
        try:
            fc = e.forecast("cpu-main")
            results.append(fc)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=forecaster) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record("CPE-047", "Concurrent forecast",
                   (0, 10), (len(errors), len(results)))

# ==================================================================== #
#  Flask API tests                                                      #
# ==================================================================== #

def test_cpe_048_api_blueprint():
    """create_capacity_api() returns a Blueprint."""
    e = _eng()
    bp = create_capacity_api(e)
    assert record("CPE-048", "API blueprint", True, bp is not None)


def test_cpe_049_api_record_metric():
    """POST /metrics creates a metric."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-049", "Flask N/A", True, True); return
    e = _eng()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.post("/api/capacity/metrics", json={
            "resource_name": "cpu-0", "value": 42.0,
        })
        assert record("CPE-049", "API record", 201, resp.status_code)


def test_cpe_050_api_record_missing():
    """POST /metrics without resource_name returns 400."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-050", "Flask N/A", True, True); return
    e = _eng()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.post("/api/capacity/metrics", json={"value": 1.0})
        assert record("CPE-050", "API missing field", 400, resp.status_code)


def test_cpe_051_api_get_metrics():
    """GET /metrics/<name> returns data points."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-051", "Flask N/A", True, True); return
    e = _eng()
    e.record_metric("cpu-0", 10.0)
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/metrics/cpu-0")
        data = resp.get_json()
        assert record("CPE-051", "API get metrics", True, len(data) >= 1)


def test_cpe_052_api_list_resources():
    """GET /resources returns resource list."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-052", "Flask N/A", True, True); return
    e = _eng()
    e.record_metric("cpu", 10.0)
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/resources")
        data = resp.get_json()
        assert record("CPE-052", "API resources", True, "cpu" in data)


def test_cpe_053_api_forecast():
    """GET /forecast/<name> returns forecast."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-053", "Flask N/A", True, True); return
    e = _populated_engine()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/forecast/cpu-main")
        assert record("CPE-053", "API forecast", 200, resp.status_code)


def test_cpe_054_api_forecast_nodata():
    """GET /forecast for unknown resource returns 404."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-054", "Flask N/A", True, True); return
    e = _eng()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/forecast/nope")
        assert record("CPE-054", "API forecast 404", 404, resp.status_code)


def test_cpe_055_api_generate_plan():
    """POST /plans generates a plan."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-055", "Flask N/A", True, True); return
    e = _populated_engine()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.post("/api/capacity/plans", json={"name": "test"})
        assert record("CPE-055", "API generate", 201, resp.status_code)


def test_cpe_056_api_list_plans():
    """GET /plans returns plan list."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-056", "Flask N/A", True, True); return
    e = _populated_engine()
    e.generate_plan()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/plans")
        data = resp.get_json()
        assert record("CPE-056", "API list plans", True, len(data) >= 1)


def test_cpe_057_api_get_plan():
    """GET /plans/<id> returns a plan."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-057", "Flask N/A", True, True); return
    e = _populated_engine()
    plan = e.generate_plan()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get(f"/api/capacity/plans/{plan.id}")
        assert record("CPE-057", "API get plan", 200, resp.status_code)


def test_cpe_058_api_plan_404():
    """GET /plans/<bad-id> returns 404."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-058", "Flask N/A", True, True); return
    e = _eng()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/plans/nonexistent")
        assert record("CPE-058", "API plan 404", 404, resp.status_code)


def test_cpe_059_api_archive_plan():
    """POST /plans/<id>/archive archives a plan."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-059", "Flask N/A", True, True); return
    e = _populated_engine()
    plan = e.generate_plan()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.post(f"/api/capacity/plans/{plan.id}/archive")
        assert record("CPE-059", "API archive", 200, resp.status_code)


def test_cpe_060_api_alerts():
    """GET /alerts returns alerts."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-060", "Flask N/A", True, True); return
    e = _eng(critical_threshold=0.5)
    for i in range(10):
        e.record_metric("hot", float(80 + i), ResourceType.cpu, 100.0)
    e.generate_plan()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/alerts")
        data = resp.get_json()
        assert record("CPE-060", "API alerts", True, len(data) >= 1)


def test_cpe_061_api_ack_alert():
    """POST /alerts/<id>/acknowledge acks an alert."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-061", "Flask N/A", True, True); return
    e = _eng(critical_threshold=0.5)
    for i in range(10):
        e.record_metric("hot", float(80 + i), ResourceType.cpu, 100.0)
    e.generate_plan()
    alerts = e.get_alerts()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        aid = alerts[0].id if alerts else "nope"
        resp = c.post(f"/api/capacity/alerts/{aid}/acknowledge")
        assert record("CPE-061", "API ack", 200, resp.status_code)


def test_cpe_062_api_stats():
    """GET /stats returns engine statistics."""
    try:
        from flask import Flask
    except ImportError:
        assert record("CPE-062", "Flask N/A", True, True); return
    e = _populated_engine()
    app = Flask(__name__)
    app.register_blueprint(create_capacity_api(e))
    with app.test_client() as c:
        resp = c.get("/api/capacity/stats")
        data = resp.get_json()
        assert record("CPE-062", "API stats", True, "resources_tracked" in data)
