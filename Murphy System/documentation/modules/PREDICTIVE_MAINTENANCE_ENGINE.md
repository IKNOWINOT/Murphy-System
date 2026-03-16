# Predictive Maintenance Engine

**Design Label:** PME-001 — Hardware Telemetry Anomaly Detection  
**Source File:** `src/predictive_maintenance_engine.py`  
**Owner:** Operations

---

## Overview

The Predictive Maintenance Engine (PME) ingests sensor readings from
physical and virtual assets, computes rolling statistics, applies
configurable threshold rules, and raises severity-graded alerts before
failures occur.  An optional Flask Blueprint (`create_predictive_maintenance_api`)
exposes the engine over HTTP.

---

## Architecture

```
Sensor Sources
     │  ingest_reading()
     ▼
PredictiveMaintenanceEngine
     │
     ├── _asset_readings: dict[asset_id, deque[SensorReading]]
     │     bounded via capped_append; guarded by threading.Lock
     │
     ├── compute_stats(asset_id, metric)
     │     mean, std dev, min, max via statistics module
     │
     ├── evaluate_thresholds(asset_id)
     │     applies ThresholdRule list → Alert list
     │
     ├── update_health_score(asset_id)
     │     composite 0–100 score derived from recent alerts
     │
     └── Flask Blueprint (optional)
           GET  /assets/{id}/health
           POST /assets/{id}/readings
           GET  /alerts
```

---

## Key Classes

### `PredictiveMaintenanceEngine`

| Method | Description |
|--------|-------------|
| `register_asset(asset_id, metadata)` | Registers a new asset for monitoring |
| `ingest_reading(asset_id, reading)` | Records a sensor reading; triggers threshold evaluation |
| `compute_stats(asset_id, metric)` | Returns rolling statistics for a metric |
| `get_health_score(asset_id)` | Returns the current `[0, 100]` health score |
| `get_active_alerts(asset_id)` | Returns unresolved alerts for an asset |
| `resolve_alert(alert_id)` | Marks an alert as resolved |

### `SensorReading`

```python
@dataclass
class SensorReading:
    reading_id: str
    asset_id: str
    metric: str             # e.g. "temperature_c", "vibration_hz", "cpu_pct"
    value: float
    unit: str
    timestamp: datetime
    source: str             # sensor identifier
```

### `ThresholdRule`

```python
@dataclass
class ThresholdRule:
    rule_id: str
    metric: str
    operator: str           # "gt" | "lt" | "gte" | "lte" | "eq"
    threshold: float
    severity: AlertSeverity
    message_template: str   # e.g. "Temperature {value}°C exceeds {threshold}°C"
```

### `Alert`

```python
@dataclass
class Alert:
    alert_id: str
    asset_id: str
    rule_id: str
    severity: AlertSeverity   # INFO | WARNING | ERROR | CRITICAL
    message: str
    value: float
    timestamp: datetime
    resolved: bool
    resolved_at: Optional[datetime]
```

### `AlertSeverity`

```python
class AlertSeverity(Enum):
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"
```

---

## Health Score Calculation

The health score is a weighted composite:

```
score = 100
       − 5  × count(INFO alerts in last 24h)
       − 15 × count(WARNING alerts in last 24h)
       − 30 × count(ERROR alerts in last 24h)
       − 50 × count(CRITICAL alerts in last 24h)
```

Score is clamped to `[0, 100]`.

---

## Flask API (Optional)

Enable with:

```python
from predictive_maintenance_engine import (
    PredictiveMaintenanceEngine,
    create_predictive_maintenance_api,
)
from flask import Flask

app = Flask(__name__)
engine = PredictiveMaintenanceEngine()
blueprint = create_predictive_maintenance_api(engine)
app.register_blueprint(blueprint, url_prefix="/maintenance")
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/maintenance/assets/{id}/health` | GET | Returns asset health score and active alerts |
| `/maintenance/assets/{id}/readings` | POST | Ingests a new sensor reading |
| `/maintenance/alerts` | GET | Lists all active (unresolved) alerts |
| `/maintenance/alerts/{id}/resolve` | POST | Resolves a specific alert |

---

## Safety Invariants

- **Thread-safe:** all mutations are inside `threading.Lock`
- **Bounded buffers:** `capped_append` limits reading history per asset (default 10,000 readings)
- **Immutable alerts:** alerts cannot be modified after creation, only resolved

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_readings_per_asset` | `10000` | Buffer size per asset per metric |
| `health_lookback_hours` | `24` | Window for health score calculation |
| `default_rules` | `[]` | List of default `ThresholdRule` objects applied to all assets |

---

## Usage

```python
from predictive_maintenance_engine import (
    PredictiveMaintenanceEngine,
    SensorReading,
    ThresholdRule,
    AlertSeverity,
)

engine = PredictiveMaintenanceEngine()

# Register asset
engine.register_asset("server-rack-01", metadata={"location": "DC-West-A"})

# Add a threshold rule
engine.add_rule(ThresholdRule(
    rule_id="temp-critical",
    metric="temperature_c",
    operator="gt",
    threshold=80.0,
    severity=AlertSeverity.CRITICAL,
    message_template="CPU temperature {value:.1f}°C exceeds {threshold}°C",
))

# Ingest reading
engine.ingest_reading("server-rack-01", SensorReading(
    reading_id="r-001",
    asset_id="server-rack-01",
    metric="temperature_c",
    value=82.5,
    unit="celsius",
    timestamp=datetime.utcnow(),
    source="ipmi-sensor-1",
))

# Check health
score = engine.get_health_score("server-rack-01")
alerts = engine.get_active_alerts("server-rack-01")
print(f"Health: {score}/100, Active alerts: {len(alerts)}")
```

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
