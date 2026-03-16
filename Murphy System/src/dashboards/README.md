# Dashboards

The `dashboards` package provides live operational dashboards for the Murphy
System.  It exposes REST and SSE endpoints for real-time metrics, aggregates
data from all subsystems, and renders configurable widgets.

## Key Modules

| Module | Purpose |
|--------|---------|
| `api.py` | FastAPI router: `GET /api/dashboards/live-metrics`, `/snapshot`, `/{id}` |
| `dashboard_manager.py` | CRUD for dashboard definitions |
| `aggregation.py` | Pulls and merges metrics from subsystem telemetry |
| `models.py` | `Dashboard`, `Widget`, `MetricSnapshot` models |
| `widgets.py` | Built-in widget types: sparkline, gauge, table, map |

## Live Metrics

- `GET /api/dashboards/live-metrics/snapshot` — one-shot JSON poll
- `GET /api/dashboards/live-metrics?interval=5` — SSE stream (1–60 s)
