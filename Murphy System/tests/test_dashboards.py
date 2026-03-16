"""
Tests for the Dashboards module (Phase 3 of management systems parity).

Covers:
  1. Models & serialization
  2. Aggregation engine
  3. Widget renderers
  4. Dashboard manager (CRUD, widgets, rendering)
  5. API router
"""

import os


import pytest

from dashboards.models import (
    AggregationFunction,
    ChartKind,
    Dashboard,
    DashboardPermission,
    DataSource,
    WidgetConfig,
    WidgetType,
)
from dashboards.aggregation import AggregationEngine
from dashboards.widgets import (
    render_battery_widget,
    render_chart_widget,
    render_number_widget,
    render_table_widget,
    render_text_widget,
    render_widget,
)
from dashboards.dashboard_manager import DashboardManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_board():
    """Return a board dict matching Board.to_dict() shape."""
    return {
        "id": "b1",
        "groups": [
            {
                "id": "g1",
                "items": [
                    {"name": "Task A", "cells": {
                        "status": {"value": "Done", "display_value": "Done"},
                        "points": {"value": 5, "display_value": "5"},
                    }},
                    {"name": "Task B", "cells": {
                        "status": {"value": "Working", "display_value": "Working"},
                        "points": {"value": 3, "display_value": "3"},
                    }},
                    {"name": "Task C", "cells": {
                        "status": {"value": "Done", "display_value": "Done"},
                        "points": {"value": 8, "display_value": "8"},
                    }},
                ],
            },
        ],
    }


def _board_accessor(board_id):
    if board_id == "b1":
        return _mock_board()
    return None


# ===================================================================
# 1. Models & serialization
# ===================================================================

class TestModels:
    def test_dashboard_to_dict(self):
        d = Dashboard(name="Overview", owner_id="u1")
        result = d.to_dict()
        assert result["name"] == "Overview"
        assert result["permission"] == "private"

    def test_widget_config_to_dict(self):
        w = WidgetConfig(widget_type=WidgetType.NUMBER, title="Total")
        result = w.to_dict()
        assert result["widget_type"] == "number"

    def test_data_source_to_dict(self):
        ds = DataSource(board_id="b1", column_id="status")
        result = ds.to_dict()
        assert result["board_id"] == "b1"

    def test_dashboard_add_widget(self):
        d = Dashboard(name="D")
        w = WidgetConfig(title="W1")
        d.add_widget(w)
        assert len(d.widgets) == 1

    def test_dashboard_get_widget(self):
        d = Dashboard(name="D")
        w = WidgetConfig(title="W1")
        d.add_widget(w)
        assert d.get_widget(w.id) is w
        assert d.get_widget("nope") is None

    def test_dashboard_remove_widget(self):
        d = Dashboard(name="D")
        w = WidgetConfig(title="W1")
        d.add_widget(w)
        removed = d.remove_widget(w.id)
        assert removed is w
        assert len(d.widgets) == 0

    def test_dashboard_remove_widget_missing(self):
        d = Dashboard(name="D")
        assert d.remove_widget("nope") is None


# ===================================================================
# 2. Aggregation engine
# ===================================================================

class TestAggregation:
    def test_count(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="b1", column_id="points")
        assert engine.aggregate(ds, AggregationFunction.COUNT) == 3

    def test_sum(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="b1", column_id="points")
        assert engine.aggregate(ds, AggregationFunction.SUM) == 16.0

    def test_avg(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="b1", column_id="points")
        result = engine.aggregate(ds, AggregationFunction.AVG)
        assert abs(result - 16 / 3) < 0.01

    def test_min(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="b1", column_id="points")
        assert engine.aggregate(ds, AggregationFunction.MIN) == 3.0

    def test_max(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="b1", column_id="points")
        assert engine.aggregate(ds, AggregationFunction.MAX) == 8.0

    def test_median(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="b1", column_id="points")
        assert engine.aggregate(ds, AggregationFunction.MEDIAN) == 5.0

    def test_count_by_column(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="b1", column_id="status")
        counts = engine.count_by_column(ds)
        assert counts["Done"] == 2
        assert counts["Working"] == 1

    def test_missing_board(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(board_id="missing", column_id="points")
        assert engine.aggregate(ds, AggregationFunction.COUNT) == 0

    def test_no_accessor(self):
        engine = AggregationEngine()
        ds = DataSource(board_id="b1", column_id="points")
        assert engine.aggregate(ds, AggregationFunction.COUNT) == 0

    def test_filter(self):
        engine = AggregationEngine(_board_accessor)
        ds = DataSource(
            board_id="b1", column_id="points",
            filters=[{"column_id": "status", "operator": "eq", "value": "Done"}],
        )
        assert engine.aggregate(ds, AggregationFunction.COUNT) == 2
        assert engine.aggregate(ds, AggregationFunction.SUM) == 13.0


# ===================================================================
# 3. Widget renderers
# ===================================================================

class TestWidgets:
    def test_render_chart_widget(self):
        engine = AggregationEngine(_board_accessor)
        w = WidgetConfig(widget_type=WidgetType.CHART, title="Status",
                         data_sources=[DataSource(board_id="b1", column_id="status")],
                         settings={"chart_kind": "pie"})
        result = render_chart_widget(w, engine)
        assert result["widget_type"] == "chart"
        assert result["chart_kind"] == "pie"
        assert len(result["series"]) == 1

    def test_render_number_widget(self):
        engine = AggregationEngine(_board_accessor)
        w = WidgetConfig(widget_type=WidgetType.NUMBER, title="Total Points",
                         data_sources=[DataSource(board_id="b1", column_id="points")],
                         settings={"aggregation": "sum", "unit": "pts"})
        result = render_number_widget(w, engine)
        assert result["value"] == 16.0
        assert result["unit"] == "pts"

    def test_render_table_widget(self):
        engine = AggregationEngine(_board_accessor)
        w = WidgetConfig(widget_type=WidgetType.TABLE, title="Items",
                         data_sources=[DataSource(board_id="b1")],
                         settings={"columns": ["status", "points"]})
        result = render_table_widget(w, engine)
        assert len(result["rows"]) == 3

    def test_render_text_widget(self):
        engine = AggregationEngine(_board_accessor)
        w = WidgetConfig(widget_type=WidgetType.TEXT, title="Notes",
                         settings={"content": "Sprint retrospective notes"})
        result = render_text_widget(w, engine)
        assert result["content"] == "Sprint retrospective notes"

    def test_render_battery_widget(self):
        engine = AggregationEngine(_board_accessor)
        w = WidgetConfig(widget_type=WidgetType.BATTERY, title="Progress",
                         data_sources=[DataSource(board_id="b1", column_id="status")],
                         settings={"done_value": "Done", "status_column": "status"})
        result = render_battery_widget(w, engine)
        assert result["total"] == 3
        assert result["done"] == 2
        assert abs(result["percentage"] - 66.7) < 0.1

    def test_render_widget_dispatcher(self):
        engine = AggregationEngine(_board_accessor)
        w = WidgetConfig(widget_type=WidgetType.TEXT, title="T",
                         settings={"content": "Hello"})
        result = render_widget(w, engine)
        assert result["widget_type"] == "text"


# ===================================================================
# 4. Dashboard manager
# ===================================================================

class TestDashboardManager:
    def test_create_dashboard(self):
        mgr = DashboardManager(_board_accessor)
        d = mgr.create_dashboard("Overview", owner_id="u1")
        assert d.name == "Overview"

    def test_get_dashboard(self):
        mgr = DashboardManager()
        d = mgr.create_dashboard("D")
        assert mgr.get_dashboard(d.id) is d
        assert mgr.get_dashboard("nope") is None

    def test_list_dashboards(self):
        mgr = DashboardManager()
        mgr.create_dashboard("A", owner_id="u1")
        mgr.create_dashboard("B", owner_id="u2")
        assert len(mgr.list_dashboards()) == 2
        assert len(mgr.list_dashboards(owner_id="u1")) == 1

    def test_update_dashboard(self):
        mgr = DashboardManager()
        d = mgr.create_dashboard("Old", owner_id="u1")
        updated = mgr.update_dashboard(d.id, user_id="u1", name="New")
        assert updated.name == "New"

    def test_update_dashboard_not_found(self):
        mgr = DashboardManager()
        with pytest.raises(KeyError):
            mgr.update_dashboard("nope", name="X")

    def test_update_dashboard_permission(self):
        mgr = DashboardManager()
        d = mgr.create_dashboard("D", owner_id="u1")
        with pytest.raises(PermissionError):
            mgr.update_dashboard(d.id, user_id="u2", name="Hacked")

    def test_delete_dashboard(self):
        mgr = DashboardManager()
        d = mgr.create_dashboard("D", owner_id="u1")
        assert mgr.delete_dashboard(d.id, user_id="u1")
        assert mgr.get_dashboard(d.id) is None

    def test_delete_dashboard_not_found(self):
        mgr = DashboardManager()
        assert not mgr.delete_dashboard("nope")

    def test_add_widget(self):
        mgr = DashboardManager(_board_accessor)
        d = mgr.create_dashboard("D")
        w = mgr.add_widget(d.id, WidgetType.NUMBER, "Total",
                           data_sources=[DataSource(board_id="b1", column_id="points")],
                           settings={"aggregation": "sum"})
        assert w.title == "Total"
        assert len(d.widgets) == 1

    def test_update_widget(self):
        mgr = DashboardManager()
        d = mgr.create_dashboard("D")
        w = mgr.add_widget(d.id, WidgetType.TEXT, "Old")
        updated = mgr.update_widget(d.id, w.id, title="New")
        assert updated.title == "New"

    def test_remove_widget(self):
        mgr = DashboardManager()
        d = mgr.create_dashboard("D")
        w = mgr.add_widget(d.id, WidgetType.TEXT, "X")
        assert mgr.remove_widget(d.id, w.id)
        assert len(d.widgets) == 0

    def test_render_dashboard(self):
        mgr = DashboardManager(_board_accessor)
        d = mgr.create_dashboard("D")
        mgr.add_widget(d.id, WidgetType.NUMBER, "Total",
                       data_sources=[DataSource(board_id="b1", column_id="points")],
                       settings={"aggregation": "count"})
        result = mgr.render_dashboard(d.id)
        assert result["name"] == "D"
        assert len(result["widgets"]) == 1
        assert result["widgets"][0]["value"] == 3

    def test_render_widget(self):
        mgr = DashboardManager(_board_accessor)
        d = mgr.create_dashboard("D")
        w = mgr.add_widget(d.id, WidgetType.TEXT, "Notes",
                           settings={"content": "Hello"})
        result = mgr.render_widget(d.id, w.id)
        assert result["content"] == "Hello"


# ===================================================================
# 5. API router
# ===================================================================

class TestAPIRouter:
    def test_create_dashboard_router(self):
        try:
            from dashboards.api import create_dashboard_router
            router = create_dashboard_router()
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not available")

    def test_router_with_custom_manager(self):
        try:
            from dashboards.api import create_dashboard_router
            mgr = DashboardManager()
            router = create_dashboard_router(mgr)
            assert router is not None
        except ImportError:
            pytest.skip("FastAPI not available")
