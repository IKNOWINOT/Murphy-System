"""
Dashboards – Customizable Dashboards & Reporting
==================================================

Phase 3 of management systems feature parity for the Murphy System.

Provides a widget-based dashboard builder including:

- **Dashboard CRUD** – create, update, delete, share dashboards
- **Widget library** – Chart, Number, Table, Timeline, Battery, Text
- **Aggregation engine** – cross-board data roll-ups (count, sum, avg, min, max, median)
- **Chart types** – bar, line, pie, stacked bar, donut, area
- **Permissions** – private, workspace, public sharing
- **REST API** at ``/api/dashboards``

Quick start::

    from dashboards import DashboardManager, WidgetType, DataSource

    mgr = DashboardManager(board_accessor=lambda bid: some_board.to_dict())
    dash = mgr.create_dashboard("Sprint Overview", owner_id="u1")
    widget = mgr.add_widget(
        dash.id, WidgetType.NUMBER, "Total Tasks",
        data_sources=[DataSource(board_id="b1", column_id="status")],
        settings={"aggregation": "count"},
    )
    rendered = mgr.render_dashboard(dash.id)

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "Dashboards"

# -- Models -----------------------------------------------------------------
# -- Aggregation ------------------------------------------------------------
from .aggregation import AggregationEngine

# -- Dashboard manager ------------------------------------------------------
from .dashboard_manager import DashboardManager
from .models import (
    AggregationFunction,
    ChartKind,
    Dashboard,
    DashboardPermission,
    DataSource,
    WidgetConfig,
    WidgetType,
)

# -- Widgets ----------------------------------------------------------------
from .widgets import (
    render_battery_widget,
    render_chart_widget,
    render_number_widget,
    render_table_widget,
    render_text_widget,
    render_timeline_widget,
    render_widget,
)

# -- API (optional – requires fastapi) -------------------------------------
try:
    from .api import create_dashboard_router
except Exception as exc:  # pragma: no cover
    create_dashboard_router = None  # type: ignore[assignment]

__all__ = [
    # Models
    "AggregationFunction",
    "ChartKind",
    "Dashboard",
    "DashboardPermission",
    "DataSource",
    "WidgetConfig",
    "WidgetType",
    # Aggregation
    "AggregationEngine",
    # Widgets
    "render_battery_widget",
    "render_chart_widget",
    "render_number_widget",
    "render_table_widget",
    "render_text_widget",
    "render_timeline_widget",
    "render_widget",
    # Manager
    "DashboardManager",
    # API
    "create_dashboard_router",
]
