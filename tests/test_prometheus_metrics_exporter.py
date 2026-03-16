# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Test Suite: Prometheus / OpenTelemetry Metrics Exporter — PME-001

Comprehensive tests for the prometheus_metrics_exporter module:
  - Data model correctness (MetricType, LabelSet, Sample, MetricFamily)
  - Counter inc / error on negative
  - Gauge inc / dec / set_value
  - Histogram observe / bucket + sum + count collection
  - Summary observe / quantile + sum + count collection
  - CollectorRegistry register / unregister / collect_all / clear
  - PrometheusRenderer text exposition format
  - JsonRenderer structured output
  - Built-in system metrics helpers
  - Flask API endpoints (/metrics, /api/metrics/json, /families, /register, /health)
  - Input validation (missing fields, invalid type)
  - Thread safety under concurrent mutation
  - Wingman pair validation gate
  - Causality Sandbox gating simulation
  - User-agent operation testing (non-technical user workflows)

Tests use the storyline-actuals record() pattern.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import pytest

# ── path setup ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from prometheus_metrics_exporter import (
    EMPTY_LABELS,
    CollectorRegistry,
    JsonRenderer,
    MetricFamily,
    MetricType,
    PrometheusRenderer,
    Sample,
    _label_set,
    create_metrics_blueprint,
    register_builtin_metrics,
    set_sandbox_enabled,
    set_wingman_enabled,
)

# ── storyline-actuals helper ──────────────────────────────────────────

@dataclass
class CheckResult:
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str
    effect: str
    lesson: str


_results: List[CheckResult] = []


def record(check_id: str, description: str, expected: Any, actual: Any,
           cause: str, effect: str, lesson: str) -> bool:
    passed = expected == actual
    _results.append(CheckResult(
        check_id=check_id, description=description,
        expected=expected, actual=actual, passed=passed,
        cause=cause, effect=effect, lesson=lesson))
    return passed


# ── fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_gates():
    set_wingman_enabled(True)
    set_sandbox_enabled(True)
    yield
    set_wingman_enabled(True)
    set_sandbox_enabled(True)


@pytest.fixture()
def registry():
    return CollectorRegistry()


@pytest.fixture()
def flask_app(registry):
    try:
        from flask import Flask
    except ImportError:
        pytest.skip("Flask not installed")
    app = Flask(__name__)
    app.register_blueprint(create_metrics_blueprint(registry))
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


# ═══════════════════════════════════════════════════════════════════════
# PME-001  Data model: MetricType enum
# ═══════════════════════════════════════════════════════════════════════

def test_pme001_metric_type_values():
    ok = record("PME-001", "MetricType enum has four members",
                {"counter", "gauge", "histogram", "summary"},
                {m.value for m in MetricType},
                cause="Enum defined with four standard Prometheus types",
                effect="All metric kinds are representable",
                lesson="Stick to the standard four types")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-002  LabelSet creation
# ═══════════════════════════════════════════════════════════════════════

def test_pme002_label_set():
    ls = _label_set(method="GET", status="200")
    ok = record("PME-002", "LabelSet from kwargs is a frozenset of tuples",
                True,
                isinstance(ls, frozenset) and ("method", "GET") in ls,
                cause="_label_set builds frozenset from kwargs",
                effect="Labels are hashable and can key dicts",
                lesson="Frozen sets make ideal label keys")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-003  Sample dataclass
# ═══════════════════════════════════════════════════════════════════════

def test_pme003_sample_creation():
    s = Sample(name="test_metric", labels=EMPTY_LABELS, value=42.0)
    ok = record("PME-003", "Sample stores name/labels/value",
                ("test_metric", 42.0),
                (s.name, s.value),
                cause="Sample is a frozen dataclass",
                effect="Immutable observation record",
                lesson="Frozen dataclasses ensure sample integrity")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-004  Counter inc
# ═══════════════════════════════════════════════════════════════════════

def test_pme004_counter_inc(registry):
    c = registry.register("req_total", "Total requests", MetricType.COUNTER)
    c.inc(1)
    c.inc(3)
    samples = c.collect()
    ok = record("PME-004", "Counter increments accumulate",
                4.0,
                samples[0].value,
                cause="Two inc() calls: 1+3",
                effect="Collected value is 4",
                lesson="Counters only go up")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-005  Counter rejects negative inc
# ═══════════════════════════════════════════════════════════════════════

def test_pme005_counter_negative_rejected(registry):
    c = registry.register("bad_ctr", "Bad counter", MetricType.COUNTER)
    with pytest.raises(ValueError, match="non-negative"):
        c.inc(-1)
    ok = record("PME-005", "Counter rejects negative increment",
                True, True,
                cause="inc(-1) on counter",
                effect="ValueError raised",
                lesson="Counters must be monotonic")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-006  Gauge inc / dec / set
# ═══════════════════════════════════════════════════════════════════════

def test_pme006_gauge_operations(registry):
    g = registry.register("connections", "Active conns", MetricType.GAUGE)
    g.set_value(10)
    g.inc(5)
    g.dec(3)
    val = g.collect()[0].value
    ok = record("PME-006", "Gauge set/inc/dec gives 12",
                12.0, val,
                cause="set(10)+inc(5)-dec(3)",
                effect="Gauge reads 12",
                lesson="Gauges can go up and down")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-007  Gauge dec rejects counter
# ═══════════════════════════════════════════════════════════════════════

def test_pme007_dec_on_counter_rejected(registry):
    c = registry.register("c", "Counter", MetricType.COUNTER)
    with pytest.raises(TypeError, match="Only gauges"):
        c.dec()
    ok = record("PME-007", "dec() rejected for counter",
                True, True,
                cause="dec() on counter metric",
                effect="TypeError raised",
                lesson="Type enforcement prevents misuse")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-008  Histogram observe + buckets
# ═══════════════════════════════════════════════════════════════════════

def test_pme008_histogram_observe(registry):
    h = registry.register("latency", "Request latency", MetricType.HISTOGRAM,
                          bucket_bounds=(0.1, 0.5, 1.0))
    h.observe(0.05)
    h.observe(0.3)
    h.observe(0.8)
    samples = h.collect()
    bucket_names = [s.name for s in samples if s.name.endswith("_bucket")]
    ok = record("PME-008", "Histogram produces bucket samples",
                True, len(bucket_names) > 0,
                cause="Three observations with three bucket bounds",
                effect="Bucket, sum, and count samples produced",
                lesson="Histograms partition observations into buckets")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-009  Histogram sum + count
# ═══════════════════════════════════════════════════════════════════════

def test_pme009_histogram_sum_count(registry):
    h = registry.register("h", "H", MetricType.HISTOGRAM,
                          bucket_bounds=(1.0, 5.0))
    h.observe(2.0)
    h.observe(3.0)
    samples = {s.name: s.value for s in h.collect() if "_bucket" not in s.name}
    ok = record("PME-009", "Histogram sum=5 count=2",
                (5.0, 2.0),
                (samples.get("h_sum", -1), samples.get("h_count", -1)),
                cause="Observed 2.0 + 3.0",
                effect="Sum and count match",
                lesson="Sum and count are essential for rate calculations")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-010  Summary quantiles
# ═══════════════════════════════════════════════════════════════════════

def test_pme010_summary_quantiles(registry):
    s = registry.register("resp_size", "Response size", MetricType.SUMMARY)
    for v in range(1, 101):
        s.observe(float(v))
    samples = s.collect()
    quantile_samples = [x for x in samples
                        if any(k == "quantile" for k, _ in x.labels)]
    ok = record("PME-010", "Summary produces quantile samples",
                True, len(quantile_samples) >= 3,
                cause="100 observations",
                effect="At least 3 quantile samples (0.5, 0.9, 0.99)",
                lesson="Summaries compute quantiles from raw observations")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-011  Registry register / unregister
# ═══════════════════════════════════════════════════════════════════════

def test_pme011_registry_lifecycle(registry):
    registry.register("a", "A", MetricType.COUNTER)
    registry.register("b", "B", MetricType.GAUGE)
    assert registry.family_count() == 2
    removed = registry.unregister("a")
    ok = record("PME-011", "Register 2, unregister 1 → count=1",
                (True, 1),
                (removed, registry.family_count()),
                cause="Register a,b then unregister a",
                effect="Only b remains",
                lesson="Unregister returns True on success")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-012  Registry idempotent re-register
# ═══════════════════════════════════════════════════════════════════════

def test_pme012_idempotent_register(registry):
    mf1 = registry.register("x", "X", MetricType.COUNTER)
    mf2 = registry.register("x", "X", MetricType.COUNTER)
    ok = record("PME-012", "Re-registering same name returns same object",
                True, mf1 is mf2,
                cause="Register 'x' twice",
                effect="Same MetricFamily returned",
                lesson="Idempotent registration avoids duplicates")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-013  Registry clear
# ═══════════════════════════════════════════════════════════════════════

def test_pme013_registry_clear(registry):
    registry.register("z", "Z", MetricType.GAUGE)
    registry.clear()
    ok = record("PME-013", "clear() empties registry",
                0, registry.family_count(),
                cause="clear() called",
                effect="Registry is empty",
                lesson="Clear is useful for test teardown")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-014  Prometheus text renderer
# ═══════════════════════════════════════════════════════════════════════

def test_pme014_prometheus_render(registry):
    c = registry.register("http_requests", "Requests", MetricType.COUNTER)
    c.inc(5, labels=_label_set(method="GET"))
    text = PrometheusRenderer.render(registry)
    ok = record("PME-014", "Prometheus text includes HELP, TYPE, sample",
                True,
                "# HELP http_requests" in text
                and "# TYPE http_requests counter" in text
                and 'method="GET"' in text
                and "5.0" in text,
                cause="One counter with one label set",
                effect="Standard exposition format",
                lesson="HELP/TYPE lines must precede samples")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-015  JSON renderer
# ═══════════════════════════════════════════════════════════════════════

def test_pme015_json_render(registry):
    g = registry.register("cpu_pct", "CPU %", MetricType.GAUGE)
    g.set_value(42.5)
    data = JsonRenderer.render(registry)
    ok = record("PME-015", "JSON renderer includes metric data",
                True,
                "cpu_pct" in data
                and data["cpu_pct"]["type"] == "gauge"
                and data["cpu_pct"]["samples"][0]["value"] == 42.5,
                cause="One gauge set to 42.5",
                effect="JSON dict has correct structure",
                lesson="JSON format powers browser dashboards")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-016  Built-in metrics helper
# ═══════════════════════════════════════════════════════════════════════

def test_pme016_builtin_metrics(registry):
    metrics = register_builtin_metrics(registry)
    ok = record("PME-016", "Built-in metrics register 6 families",
                True,
                registry.family_count() >= 6
                and "murphy_requests_total" in metrics,
                cause="register_builtin_metrics() called",
                effect="Standard system metrics available",
                lesson="Built-ins provide zero-config monitoring")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-017  Flask /metrics endpoint
# ═══════════════════════════════════════════════════════════════════════

def test_pme017_prometheus_endpoint(client, registry):
    c = registry.register("test_counter", "Test", MetricType.COUNTER)
    c.inc(7)
    resp = client.get("/metrics")
    ok = record("PME-017", "/metrics returns 200 with text/plain",
                (200, True),
                (resp.status_code, b"test_counter" in resp.data),
                cause="GET /metrics",
                effect="Prometheus exposition body",
                lesson="/metrics is the standard scrape path")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-018  Flask /api/metrics/json endpoint
# ═══════════════════════════════════════════════════════════════════════

def test_pme018_json_endpoint(client, registry):
    g = registry.register("mem_mb", "Memory", MetricType.GAUGE)
    g.set_value(256)
    resp = client.get("/api/metrics/json")
    data = resp.get_json()
    ok = record("PME-018", "/api/metrics/json returns gauge data",
                (200, 256.0),
                (resp.status_code, data["mem_mb"]["samples"][0]["value"]),
                cause="GET /api/metrics/json",
                effect="JSON body with gauge",
                lesson="JSON endpoint powers custom UIs")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-019  Flask /api/metrics/families
# ═══════════════════════════════════════════════════════════════════════

def test_pme019_families_endpoint(client, registry):
    registry.register("f1", "F1", MetricType.COUNTER)
    registry.register("f2", "F2", MetricType.GAUGE)
    resp = client.get("/api/metrics/families")
    data = resp.get_json()
    ok = record("PME-019", "/api/metrics/families lists names",
                True,
                "f1" in data["families"] and data["count"] == 2,
                cause="GET /api/metrics/families",
                effect="Two families returned",
                lesson="Discovery endpoint for dynamic systems")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-020  Flask /api/metrics/register POST
# ═══════════════════════════════════════════════════════════════════════

def test_pme020_register_endpoint(client):
    resp = client.post("/api/metrics/register",
                       json={"name": "new_m", "help": "New metric",
                             "type": "counter"})
    ok = record("PME-020", "POST /api/metrics/register creates family",
                201, resp.status_code,
                cause="POST with valid name/help/type",
                effect="201 Created",
                lesson="Runtime metric registration for plugins")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-021  Register endpoint validation — missing fields
# ═══════════════════════════════════════════════════════════════════════

def test_pme021_register_missing_fields(client):
    resp = client.post("/api/metrics/register", json={"name": "only_name"})
    ok = record("PME-021", "Missing fields return 400",
                400, resp.status_code,
                cause="POST with missing help & type",
                effect="400 Bad Request",
                lesson="Always validate API input")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-022  Register endpoint — invalid type
# ═══════════════════════════════════════════════════════════════════════

def test_pme022_register_invalid_type(client):
    resp = client.post("/api/metrics/register",
                       json={"name": "m", "help": "h", "type": "bogus"})
    ok = record("PME-022", "Invalid metric type returns 400",
                400, resp.status_code,
                cause="type=bogus",
                effect="400 with INVALID_TYPE code",
                lesson="Enum validation catches bad input")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-023  Health endpoint
# ═══════════════════════════════════════════════════════════════════════

def test_pme023_health_endpoint(client):
    resp = client.get("/api/metrics/health")
    data = resp.get_json()
    ok = record("PME-023", "/api/metrics/health returns healthy",
                (200, "healthy"),
                (resp.status_code, data["status"]),
                cause="GET /api/metrics/health",
                effect="Status healthy",
                lesson="Health checks confirm subsystem is alive")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-024  Labels in Prometheus output
# ═══════════════════════════════════════════════════════════════════════

def test_pme024_labels_in_output(registry):
    c = registry.register("labeled", "With labels", MetricType.COUNTER)
    c.inc(1, labels=_label_set(env="prod", region="us"))
    text = PrometheusRenderer.render(registry)
    ok = record("PME-024", "Multiple labels rendered correctly",
                True,
                'env="prod"' in text and 'region="us"' in text,
                cause="Counter with env+region labels",
                effect="Both labels in output",
                lesson="Label ordering is sorted alphabetically")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-025  Thread safety — concurrent inc
# ═══════════════════════════════════════════════════════════════════════

def test_pme025_thread_safety(registry):
    c = registry.register("concurrent", "Thread test", MetricType.COUNTER)
    threads = []
    for _ in range(10):
        t = threading.Thread(target=lambda: [c.inc(1) for _ in range(100)])
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    val = c.collect()[0].value
    ok = record("PME-025", "10 threads × 100 inc = 1000",
                1000.0, val,
                cause="Concurrent increments",
                effect="No lost updates",
                lesson="Lock-protected mutations are thread-safe")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-026  Wingman gate — registration blocked
# ═══════════════════════════════════════════════════════════════════════

def test_pme026_wingman_gate_blocked(registry):
    set_wingman_enabled(True)
    # Wingman blocks empty names
    with pytest.raises(PermissionError):
        registry.register("", "No name", MetricType.COUNTER)
    ok = record("PME-026", "Wingman rejects registration with empty name",
                True, True,
                cause="register() with empty name",
                effect="PermissionError raised",
                lesson="Wingman validates all gated operations")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-027  Sandbox gate — registration blocked
# ═══════════════════════════════════════════════════════════════════════

def test_pme027_sandbox_gate_blocked(registry):
    set_wingman_enabled(False)
    set_sandbox_enabled(True)
    # Sandbox blocks empty names too
    with pytest.raises(RuntimeError):
        registry.register("", "No name", MetricType.COUNTER)
    ok = record("PME-027", "Sandbox rejects registration with empty name",
                True, True,
                cause="register() with empty name when wingman off",
                effect="RuntimeError raised",
                lesson="Sandbox is second line of defense")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-028  Wingman disabled — registration proceeds
# ═══════════════════════════════════════════════════════════════════════

def test_pme028_wingman_disabled(registry):
    set_wingman_enabled(False)
    set_sandbox_enabled(False)
    mf = registry.register("no_gate", "Ungated", MetricType.GAUGE)
    ok = record("PME-028", "Gates disabled allows registration",
                True, mf is not None,
                cause="Both gates disabled",
                effect="Metric registered",
                lesson="Gates are toggleable for testing")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-029  observe() rejected on counter
# ═══════════════════════════════════════════════════════════════════════

def test_pme029_observe_rejected_on_counter(registry):
    c = registry.register("cnt", "Counter", MetricType.COUNTER)
    with pytest.raises(TypeError, match="histograms/summaries"):
        c.observe(1.0)
    ok = record("PME-029", "observe() rejected for counter",
                True, True,
                cause="observe() on counter",
                effect="TypeError",
                lesson="Type checks prevent misuse")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-030  set_value() rejected on counter
# ═══════════════════════════════════════════════════════════════════════

def test_pme030_set_value_on_counter(registry):
    c = registry.register("cnt2", "Counter2", MetricType.COUNTER)
    with pytest.raises(TypeError, match="Only gauges"):
        c.set_value(10)
    ok = record("PME-030", "set_value() rejected for counter",
                True, True,
                cause="set_value on counter",
                effect="TypeError raised",
                lesson="Enforce metric type semantics")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-031  collect_all returns all families
# ═══════════════════════════════════════════════════════════════════════

def test_pme031_collect_all(registry):
    c = registry.register("a", "A", MetricType.COUNTER)
    g = registry.register("b", "B", MetricType.GAUGE)
    c.inc(1)
    g.set_value(2)
    all_data = registry.collect_all()
    ok = record("PME-031", "collect_all returns both families",
                True, "a" in all_data and "b" in all_data,
                cause="Two families registered",
                effect="Both in collect_all output",
                lesson="collect_all is the central collection method")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-032  Unregister returns False for unknown
# ═══════════════════════════════════════════════════════════════════════

def test_pme032_unregister_unknown(registry):
    ok = record("PME-032", "Unregister unknown returns False",
                False, registry.unregister("does_not_exist"),
                cause="unregister() with unknown name",
                effect="Returns False",
                lesson="Graceful no-op on missing names")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-033  User-agent workflow: operator creates + monitors metric
# ═══════════════════════════════════════════════════════════════════════

def test_pme033_user_agent_workflow(client, registry):
    # Step 1: operator creates a metric via API
    resp1 = client.post("/api/metrics/register",
                        json={"name": "user_logins", "help": "Login count",
                              "type": "counter"})
    assert resp1.status_code == 201

    # Step 2: simulate login events
    mf = registry.get("user_logins")
    assert mf is not None
    mf.inc(10)

    # Step 3: operator checks dashboard
    resp2 = client.get("/api/metrics/json")
    data = resp2.get_json()
    val = data["user_logins"]["samples"][0]["value"]

    ok = record("PME-033", "User-agent: create → increment → read",
                10.0, val,
                cause="Non-technical operator uses register + json endpoints",
                effect="Metric correctly shows 10",
                lesson="API-driven metric lifecycle is user-friendly")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-034  Histogram +Inf bucket
# ═══════════════════════════════════════════════════════════════════════

def test_pme034_histogram_inf_bucket(registry):
    h = registry.register("hh", "H", MetricType.HISTOGRAM,
                          bucket_bounds=(1.0,))
    h.observe(0.5)
    h.observe(100.0)
    samples = h.collect()
    inf_sample = [s for s in samples
                  if any(v == "+Inf" for _, v in s.labels)]
    ok = record("PME-034", "Histogram has +Inf bucket",
                True, len(inf_sample) == 1,
                cause="Bucket bounds=(1.0) with obs 0.5 and 100",
                effect="+Inf bucket contains total count",
                lesson="Inf bucket is required by Prometheus spec")
    assert ok


# ═══════════════════════════════════════════════════════════════════════
# PME-035  Empty registry renders empty text
# ═══════════════════════════════════════════════════════════════════════

def test_pme035_empty_render(registry):
    text = PrometheusRenderer.render(registry)
    ok = record("PME-035", "Empty registry renders empty string",
                True, text == "" or text == "\n",
                cause="No metrics registered",
                effect="Empty or minimal output",
                lesson="Empty exposition is valid Prometheus format")
    assert ok
