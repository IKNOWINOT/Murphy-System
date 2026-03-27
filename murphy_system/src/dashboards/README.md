# `src/dashboards` — Dashboards & Reporting

Widget-based customizable dashboard system for the Murphy System.
Provides dashboard CRUD, a rich widget library, cross-board aggregations, and a REST API.

## Public API

```python
from dashboards import (
    DashboardManager, Dashboard, Widget, WidgetType,
    DataSource, ChartType, AggregationType,
)
```

## Quick Start

```python
from dashboards import DashboardManager, WidgetType, DataSource

mgr = DashboardManager(board_accessor=lambda bid: board_service.get(bid))

# Create dashboard
dash = mgr.create_dashboard("Sprint Overview", owner_id="user-1")

# Add a number widget (count of open tasks)
widget = mgr.add_widget(
    dash.id,
    WidgetType.NUMBER,
    "Open Tasks",
    data_sources=[DataSource(board_id="b1", column_id="status", filter_value="open")],
    settings={"aggregation": "count"},
)

# Render (returns populated widget values)
rendered = mgr.render_dashboard(dash.id)
```

## Widget Types

| Type | Description |
|------|-------------|
| `NUMBER` | Single metric with optional trend |
| `CHART` | Bar, line, pie, donut, stacked bar, area |
| `TABLE` | Tabular data with sorting |
| `TIMELINE` | Gantt-style timeline |
| `BATTERY` | Progress/capacity visualization |
| `TEXT` | Markdown content block |

## REST API

Base path: `/api/dashboards`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/dashboards` | List all dashboards |
| `POST` | `/api/dashboards` | Create dashboard |
| `GET` | `/api/dashboards/{id}` | Get dashboard |
| `PUT` | `/api/dashboards/{id}` | Update dashboard |
| `DELETE` | `/api/dashboards/{id}` | Delete dashboard |
| `GET` | `/api/dashboards/live-metrics/snapshot` | Live metrics JSON snapshot |
| `GET` | `/api/dashboards/live-metrics` | Live metrics SSE stream |

## Tests

`tests/test_dashboard*.py`, `tests/test_dashboard_live_metrics.py` (11 tests).
