# Unified Observability Engine

**Design Label:** OBS-010 — Unified Observability Dashboard Engine  
**Owner:** Platform Engineering / DevOps Team  
**License:** BSL 1.1  
**Source:** `Murphy System/src/unified_observability_engine.py`  
**Tests:** `Murphy System/tests/test_unified_observability_engine.py`

---

## Overview

The Unified Observability Engine aggregates metrics from **all Murphy subsystems**
into a single, queryable time-series store.  It computes real-time system health
scores, provides trend analysis and anomaly detection, and generates human-readable
health reports — all with bounded memory, thread-safety, and a non-blocking
ingestion path.

Inspired by the Kubernetes metrics-server + Prometheus pattern, adapted for
Murphy's Python-based architecture and integrated with the existing `EventBackbone`
pub/sub system.

---

## Architecture — Metric Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Murphy Subsystems                              │
│                                                                      │
│  SelfFixLoop  HeartbeatMonitor  SupervisionTree  CircuitBreakers     │
│       │              │                │                │             │
│       └──────────────┴────────────────┴────────────────┘            │
│                              │                                       │
│                       EventBackbone                                  │
│                    (pub/sub lifecycle events)                        │
│                              │                                       │
│                 ┌────────────▼────────────┐                         │
│                 │  record_event(event)    │   ◄── auto-extraction   │
│                 │  record_metric(name, v) │   ◄── direct API        │
│                 └────────────┬────────────┘                         │
│                              │                                       │
│               UnifiedObservabilityEngine                            │
│                              │                                       │
│     ┌────────────────────────┼────────────────────────┐             │
│     │                        │                        │             │
│ MetricStore            AlertManager             MetricWindows       │
│ (List[MetricPoint])   (rules + active)     (Dict[str, MetricWindow]) │
│     │                        │                        │             │
│     └────────────────────────┼────────────────────────┘             │
│                              │                                       │
│         ┌────────────────────┼────────────────────────┐             │
│         │                    │                         │             │
│  compute_health_score()  detect_anomalies()    generate_report()   │
│  get_dashboard_data()    query(...)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### `MetricPoint` (dataclass)

A single observed measurement.

| Field         | Type              | Description |
|---------------|-------------------|-------------|
| `metric_name` | `str`             | Dot-separated name (e.g. `"heartbeat.bots_healthy"`) |
| `value`       | `float`           | Numeric observation |
| `timestamp`   | `float`           | Unix epoch seconds |
| `tags`        | `Dict[str, str]`  | Dimensions: `component`, `severity`, `category`, etc. |
| `metric_type` | `MetricType`      | `COUNTER`, `GAUGE`, or `HISTOGRAM` |

---

### `MetricWindow`

A fixed-size circular buffer for a single metric series.  All statistical
operations are O(n) where n ≤ `window_size` (default 1 000).

```python
w = MetricWindow(window_size=500)
w.add(42.0)
w.add(43.0, timestamp=time.time())

w.mean()          # arithmetic mean
w.p50()           # 50th percentile (median)
w.p95()           # 95th percentile
w.p99()           # 99th percentile
w.rate()          # change-per-second over the whole window
w.trend()         # TrendDirection.RISING | FALLING | STABLE
w.anomaly_score() # float 0.0–1.0  (z-score normalised)
```

**Trend algorithm** — ordinary least-squares linear regression over
`(timestamp, value)` pairs.  Returns `RISING` when slope > 1% of |mean|,
`FALLING` when slope < −1% of |mean|, `STABLE` otherwise.

**Anomaly score** — z-score of the most recent value, normalised so that
z ≥ 3σ → score = 1.0.

---

### `SystemHealthScore` (dataclass)

| Field          | Type                 | Description |
|----------------|----------------------|-------------|
| `overall`      | `float`              | Weighted average; range [0.0, 1.0] |
| `components`   | `Dict[str, float]`   | Per-component scores |
| `alerts`       | `List[str]`          | Active alert messages |
| `computed_at`  | `float`              | Unix epoch of computation |

---

### `UnifiedObservabilityEngine`

The main façade.

```python
from unified_observability_engine import UnifiedObservabilityEngine
from event_backbone import EventBackbone

bb = EventBackbone()
engine = UnifiedObservabilityEngine(event_backbone=bb)

# Direct ingestion
engine.record_metric("heartbeat.bots_healthy", 9.0, tags={"component": "heartbeat"})

# Query
pts = engine.query("heartbeat.bots_healthy", time_range=(t_start, t_end))

# Health score
score = engine.compute_health_score()  # → SystemHealthScore

# Anomaly detection
alerts = engine.detect_anomalies(threshold=0.7)

# Human-readable report
print(engine.generate_report())

# Dashboard JSON
data = engine.get_dashboard_data()
```

---

### `AlertRule` (dataclass)

Declarative rule: fire when the **maximum observed value** inside a rolling
`window_seconds` exceeds `threshold`.

| Field            | Type            | Default | Description |
|------------------|-----------------|---------|-------------|
| `rule_id`        | `str`           | —       | Unique identifier |
| `name`           | `str`           | —       | Human label |
| `metric_name`    | `str`           | —       | Metric to watch |
| `threshold`      | `float`         | —       | Trigger level |
| `window_seconds` | `float`         | `300`   | Rolling window size |
| `severity`       | `AlertSeverity` | `WARNING` | `CRITICAL`, `WARNING`, `INFO` |
| `description`    | `str`           | `""`    | Human description |
| `enabled`        | `bool`          | `True`  | Toggle rule |

---

### `AlertManager`

Evaluates `AlertRule` objects against current `MetricWindow` state.
Publishes `ALERT_FIRED` and `ALERT_RESOLVED` events to the `EventBackbone`.

```python
from unified_observability_engine import AlertManager, AlertRule, AlertSeverity

rule = AlertRule(
    rule_id="cb-trips-high",
    name="Circuit Breaker Trip Storm",
    metric_name="circuit_breaker.trips",
    threshold=3.0,
    window_seconds=300.0,
    severity=AlertSeverity.CRITICAL,
    description="More than 3 circuit-breaker trips in 5 min",
)
manager = AlertManager(rules=[rule], event_backbone=bb)
newly_fired = manager.evaluate_rules(windows)
active = manager.get_active_alerts()
```

---

## Metric Naming Convention

Following OpenTelemetry semantic conventions where applicable:

```
<subsystem>.<measurement>[.<unit>]
```

| Metric | Type | Description |
|--------|------|-------------|
| `self_fix_loop.gaps_fixed` | COUNTER | Total gaps fixed in current run |
| `self_fix_loop.gaps_remaining` | GAUGE | Unresolved gaps |
| `self_fix_loop.runs_started` | COUNTER | Loop invocations |
| `self_fix_loop.rollbacks` | COUNTER | Rollback events |
| `heartbeat.bots_healthy` | GAUGE | Count of healthy bots |
| `heartbeat.bots_total` | GAUGE | Total registered bots |
| `heartbeat.bots_failed` | COUNTER | Failed heartbeat events |
| `supervision_tree.running_components` | GAUGE | Live supervised children |
| `supervision_tree.total_components` | GAUGE | Total declared children |
| `supervision_tree.child_restarts` | COUNTER | Restart events |
| `supervision_tree.child_failures` | COUNTER | Unrecovered failure events |
| `circuit_breaker.closed_breakers` | GAUGE | Breakers in CLOSED state |
| `circuit_breaker.total_breakers` | GAUGE | Total registered breakers |
| `circuit_breaker.trips` | COUNTER | Circuit-breaker trip events |

---

## Health Score Computation

```
health("self_fix_loop") = 1.0                    if gaps_remaining == 0
                        = max(0, 1 − gaps_remaining / total_gaps)

health("heartbeat")     = healthy_bots / total_bots

health("supervision_tree") = running_components / total_components

health("circuit_breaker")  = closed_breakers / total_breakers

overall = Σ  weight[component] × health[component]
          ─────────────────────────────────────────
                 Σ weight[component]
```

Default weights (configurable via `component_weights` parameter):

| Component | Weight |
|-----------|--------|
| `self_fix_loop` | 0.25 |
| `heartbeat` | 0.25 |
| `supervision_tree` | 0.25 |
| `circuit_breaker` | 0.25 |

Components with **no data** default to a health score of **1.0** (assume healthy
until proven otherwise).

---

## Alert Rule Configuration

### Built-in Rules

| Rule ID | Metric | Threshold | Window | Severity |
|---------|--------|-----------|--------|----------|
| `obs-cb-trips` | `circuit_breaker.trips` | > 3.0 | 300 s | CRITICAL |
| `obs-heartbeat-failed` | `heartbeat.bots_failed` | > 0.0 | 60 s | WARNING |
| `obs-self-fix-gaps` | `self_fix_loop.gaps_remaining` | > 10.0 | 600 s | WARNING |
| `obs-supervision-failures` | `supervision_tree.child_failures` | > 5.0 | 300 s | CRITICAL |

### Adding Custom Rules

```python
from unified_observability_engine import AlertRule, AlertSeverity

engine = UnifiedObservabilityEngine(
    event_backbone=bb,
    alert_rules=[
        AlertRule(
            rule_id="my-rule",
            name="Custom Metric High",
            metric_name="my.service.latency_ms",
            threshold=1000.0,
            window_seconds=120.0,
            severity=AlertSeverity.WARNING,
            description="Latency exceeded 1 s over 2 min",
        )
    ],
)
```

---

## Example Dashboard Data Structure

```json
{
  "generated_at": "2026-03-08T12:00:00+00:00",
  "health_score": {
    "overall": 0.9125,
    "components": {
      "self_fix_loop": 1.0,
      "heartbeat": 0.9,
      "supervision_tree": 0.85,
      "circuit_breaker": 0.9
    },
    "alerts": [],
    "computed_at": 1741435200.0
  },
  "metrics": {
    "heartbeat.bots_healthy": {
      "count": 42,
      "mean": 9.0,
      "p50": 9.0,
      "p95": 10.0,
      "p99": 10.0,
      "rate": 0.0,
      "trend": "stable",
      "anomaly_score": 0.0
    },
    "circuit_breaker.trips": {
      "count": 3,
      "mean": 0.33,
      "p50": 0.0,
      "p95": 1.0,
      "p99": 1.0,
      "rate": 0.001,
      "trend": "rising",
      "anomaly_score": 0.42
    }
  },
  "active_alerts": [],
  "anomalies": [],
  "alert_manager_status": {
    "total_rules": 4,
    "active_alerts": 0,
    "total_fired_ever": 0
  }
}
```

---

## Integration with EventBackbone

The engine subscribes to the following `EventType` values at construction time
(when `event_backbone` is provided):

| EventType | Metrics Extracted |
|-----------|-------------------|
| `SELF_FIX_COMPLETED` | `self_fix_loop.gaps_fixed`, `self_fix_loop.gaps_remaining` |
| `SELF_FIX_STARTED` | `self_fix_loop.runs_started` |
| `SELF_FIX_ROLLED_BACK` | `self_fix_loop.rollbacks` |
| `BOT_HEARTBEAT_OK` | `heartbeat.bots_healthy`, `heartbeat.bots_total` |
| `BOT_HEARTBEAT_FAILED` | `heartbeat.bots_failed` |
| `SUPERVISOR_CHILD_RESTARTED` | `supervision_tree.child_restarts`, `running_components`, `total_components` |
| `SUPERVISOR_CHILD_FAILED` | `supervision_tree.child_failures` |
| `SYSTEM_HEALTH` | `circuit_breaker.closed_breakers`, `total_breakers`, `circuit_breaker.trips` |

The `AlertManager` publishes:

| EventType | When |
|-----------|------|
| `ALERT_FIRED` | Rule condition first triggers |
| `ALERT_RESOLVED` | Condition clears (metric drops below threshold) |

---

## Example Generated Health Report

```markdown
# Murphy System — Health Report

**Generated:** 2026-03-08T12:00:00+00:00
**Overall Health:** 91.3%

## Component Health Scores

- **circuit_breaker**: 90.0% [█████████░]
- **heartbeat**: 90.0% [█████████░]
- **self_fix_loop**: 100.0% [██████████]
- **supervision_tree**: 85.0% [████████░░]

## Active Alerts

- ✅ No active alerts

## Anomaly Detection

- ✅ No anomalies detected

## Metric Summary

| `circuit_breaker.closed_breakers` | n=1 | mean=9 | p95=9 | trend=stable |
| `circuit_breaker.total_breakers` | n=1 | mean=10 | p95=10 | trend=stable |
| `heartbeat.bots_healthy` | n=42 | mean=9 | p95=10 | trend=stable |
| `heartbeat.bots_total` | n=42 | mean=10 | p95=10 | trend=stable |
| `self_fix_loop.gaps_fixed` | n=5 | mean=5 | p95=5 | trend=stable |
| `self_fix_loop.gaps_remaining` | n=5 | mean=0 | p95=0 | trend=stable |
| `supervision_tree.running_components` | n=8 | mean=8.5 | p95=10 | trend=stable |
| `supervision_tree.total_components` | n=8 | mean=10 | p95=10 | trend=stable |
```

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Bounded memory** | Circular buffers (`deque(maxlen=window_size)`); global cap of 50 000 points across all metrics |
| **Non-blocking** | `record_metric` is a lock-guarded list append — no background threads |
| **Full audit trail** | All events flow through `EventBackbone` and can be persisted via `PersistenceManager` |
| **Thread-safe** | All shared state (`_windows`, `_store`, `_active`) is guarded by `threading.Lock` |
| **OpenTelemetry-compatible** | Metric names and `MetricType` (COUNTER / GAUGE / HISTOGRAM) follow OTel naming |
| **ELK-compatible logging** | All log output uses structured Python `logging` — compatible with JSON log formatters |
| **Graceful degradation** | Missing metrics default to healthy; subscription failures are logged at DEBUG level |
