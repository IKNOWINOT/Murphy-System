"""
Acceptance tests – Management Parity Phase 3: Dashboards
=========================================================

Validates the Dashboards module (``src/dashboards``):

- Widget rendering (chart, number, table, timeline, text, battery)
- Data binding via AggregationEngine
- Custom layout persistence (widget positions stored in DashboardManager)
- Dashboard CRUD, sharing, and permissions

Run selectively::

    pytest -m parity tests/test_mgmt_parity_phase3.py

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import sys
import os
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import dashboards
from dashboards import (
    AggregationEngine,
    DashboardManager,
    DashboardPermission,
    DataSource,
    WidgetConfig,
    WidgetType,
    AggregationFunction,
    ChartKind,
    Dashboard,
    render_widget,
    render_chart_widget,
    render_number_widget,
    render_table_widget,
    render_text_widget,
    render_timeline_widget,
    render_battery_widget,
)

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_board() -> Dict[str, Any]:
    """A minimal board dict with groups, items, and cells."""
    return {
        "id": "board-1",
        "name": "Sprint Board",
        "groups": [
            {
                "id": "g1",
                "name": "To Do",
                "items": [
                    {
                        "id": "i1",
                        "cells": {
                            "status": {"value": "done"},
                            "effort": {"value": 3},
                        },
                    },
                    {
                        "id": "i2",
                        "cells": {
                            "status": {"value": "in_progress"},
                            "effort": {"value": 5},
                        },
                    },
                ],
            },
            {
                "id": "g2",
                "name": "Done",
                "items": [
                    {
                        "id": "i3",
                        "cells": {
                            "status": {"value": "done"},
                            "effort": {"value": 8},
                        },
                    },
                ],
            },
        ],
    }


def _make_mgr(board: Optional[Dict[str, Any]] = None) -> DashboardManager:
    if board is None:
        board = _sample_board()

    def accessor(board_id: str) -> Optional[Dict[str, Any]]:
        if board_id == board["id"]:
            return board
        return None

    return DashboardManager(board_accessor=accessor)


# ---------------------------------------------------------------------------
# 1. Module structure
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_package_version_exists(self):
        assert hasattr(dashboards, "__version__")

    def test_dashboard_manager_importable(self):
        assert DashboardManager is not None

    def test_aggregation_engine_importable(self):
        assert AggregationEngine is not None

    def test_widget_types_defined(self):
        for wt in (
            WidgetType.CHART,
            WidgetType.NUMBER,
            WidgetType.TABLE,
            WidgetType.TIMELINE,
            WidgetType.TEXT,
            WidgetType.BATTERY,
        ):
            assert wt is not None

    def test_render_functions_callable(self):
        for fn in (
            render_widget,
            render_chart_widget,
            render_number_widget,
            render_table_widget,
            render_text_widget,
            render_timeline_widget,
            render_battery_widget,
        ):
            assert callable(fn)


# ---------------------------------------------------------------------------
# 2. Widget rendering
# ---------------------------------------------------------------------------


class TestWidgetRendering:
    """Verify each widget type renders without error."""

    def test_render_number_widget(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Test Dash", owner_id="u1")
        widget = mgr.add_widget(
            dash.id,
            WidgetType.NUMBER,
            "Total Effort",
            data_sources=[DataSource(board_id="board-1", column_id="effort")],
            settings={"aggregation": "sum"},
        )
        result = mgr.render_dashboard(dash.id)
        rendered_widgets = result.get("widgets", [])
        assert len(rendered_widgets) == 1
        w = rendered_widgets[0]
        assert w["widget_type"] == WidgetType.NUMBER.value

    def test_render_chart_widget(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Chart Dash", owner_id="u1")
        mgr.add_widget(
            dash.id,
            WidgetType.CHART,
            "Status Distribution",
            data_sources=[DataSource(board_id="board-1", column_id="status")],
            settings={"chart_kind": "bar", "group_by_column": "status"},
        )
        result = mgr.render_dashboard(dash.id)
        w = result["widgets"][0]
        assert w["widget_type"] == WidgetType.CHART.value

    def test_render_text_widget(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Text Dash", owner_id="u1")
        mgr.add_widget(
            dash.id,
            WidgetType.TEXT,
            "Sprint Notes",
            settings={"content": "## Sprint 1\nAll items on track."},
        )
        result = mgr.render_dashboard(dash.id)
        w = result["widgets"][0]
        assert w["widget_type"] == WidgetType.TEXT.value

    def test_render_table_widget(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Table Dash", owner_id="u1")
        mgr.add_widget(
            dash.id,
            WidgetType.TABLE,
            "Item Table",
            data_sources=[DataSource(board_id="board-1", column_id="status")],
        )
        result = mgr.render_dashboard(dash.id)
        w = result["widgets"][0]
        assert w["widget_type"] == WidgetType.TABLE.value

    def test_render_battery_widget(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Battery Dash", owner_id="u1")
        mgr.add_widget(
            dash.id,
            WidgetType.BATTERY,
            "Progress",
            data_sources=[DataSource(board_id="board-1", column_id="status")],
            settings={"done_value": "done"},
        )
        result = mgr.render_dashboard(dash.id)
        w = result["widgets"][0]
        assert w["widget_type"] == WidgetType.BATTERY.value


# ---------------------------------------------------------------------------
# 3. Data binding via aggregation
# ---------------------------------------------------------------------------


class TestDataBinding:
    """Verify the aggregation engine correctly binds board data to widgets."""

    def test_count_aggregation(self):
        engine = AggregationEngine(board_accessor=lambda bid: _sample_board())
        ds = DataSource(board_id="board-1", column_id="status")
        total = engine.aggregate(ds, AggregationFunction.COUNT)
        assert total == 3  # 3 items total

    def test_sum_aggregation(self):
        engine = AggregationEngine(board_accessor=lambda bid: _sample_board())
        ds = DataSource(board_id="board-1", column_id="effort")
        total = engine.aggregate(ds, AggregationFunction.SUM)
        assert total == 16  # 3 + 5 + 8

    def test_count_by_column(self):
        engine = AggregationEngine(board_accessor=lambda bid: _sample_board())
        ds = DataSource(board_id="board-1", column_id="status")
        counts = engine.count_by_column(ds)
        assert isinstance(counts, dict)
        assert counts.get("done", 0) == 2

    def test_no_board_returns_zero(self):
        engine = AggregationEngine(board_accessor=lambda bid: None)
        ds = DataSource(board_id="missing", column_id="status")
        total = engine.aggregate(ds, AggregationFunction.COUNT)
        assert total == 0


# ---------------------------------------------------------------------------
# 4. Custom layout persistence
# ---------------------------------------------------------------------------


class TestCustomLayoutPersistence:
    """Widget position and layout settings are stored and retrieved correctly."""

    def test_widget_position_stored(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Layout Dash", owner_id="u1")
        widget = mgr.add_widget(
            dash.id,
            WidgetType.NUMBER,
            "Count",
            position={"x": 2, "y": 3, "w": 4, "h": 2},
        )
        assert widget.position == {"x": 2, "y": 3, "w": 4, "h": 2}

    def test_widget_position_updated(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Layout Dash 2", owner_id="u1")
        widget = mgr.add_widget(
            dash.id, WidgetType.TEXT, "Note",
            position={"x": 0, "y": 0, "w": 6, "h": 2},
        )
        updated = mgr.update_widget(
            dash.id, widget.id, position={"x": 0, "y": 4, "w": 6, "h": 3}
        )
        assert updated.position == {"x": 0, "y": 4, "w": 6, "h": 3}

    def test_multiple_widgets_preserved(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Multi Dash", owner_id="u1")
        for i in range(4):
            mgr.add_widget(
                dash.id, WidgetType.NUMBER, f"Widget {i}",
                position={"x": i * 3, "y": 0, "w": 3, "h": 2},
            )
        retrieved = mgr.get_dashboard(dash.id)
        assert len(retrieved.widgets) == 4

    def test_remove_widget_from_layout(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Remove Dash", owner_id="u1")
        w1 = mgr.add_widget(dash.id, WidgetType.TEXT, "W1")
        w2 = mgr.add_widget(dash.id, WidgetType.TEXT, "W2")
        mgr.remove_widget(dash.id, w1.id)
        retrieved = mgr.get_dashboard(dash.id)
        ids = [w.id for w in retrieved.widgets]
        assert w1.id not in ids
        assert w2.id in ids


# ---------------------------------------------------------------------------
# 5. Dashboard CRUD and permissions
# ---------------------------------------------------------------------------


class TestDashboardCRUD:
    def test_create_and_retrieve_dashboard(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("My Dash", owner_id="u1", workspace_id="ws1")
        retrieved = mgr.get_dashboard(dash.id)
        assert retrieved is not None
        assert retrieved.name == "My Dash"

    def test_update_dashboard_name(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Old Name", owner_id="u1")
        mgr.update_dashboard(dash.id, name="New Name")
        retrieved = mgr.get_dashboard(dash.id)
        assert retrieved.name == "New Name"

    def test_delete_dashboard(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("To Delete", owner_id="u1")
        removed = mgr.delete_dashboard(dash.id)
        assert removed is True
        assert mgr.get_dashboard(dash.id) is None

    def test_list_dashboards_by_owner(self):
        mgr = _make_mgr()
        mgr.create_dashboard("D1", owner_id="alice")
        mgr.create_dashboard("D2", owner_id="alice")
        mgr.create_dashboard("D3", owner_id="bob")
        alice_dashes = mgr.list_dashboards(owner_id="alice")
        assert len(alice_dashes) == 2

    def test_dashboard_permission_default_private(self):
        mgr = _make_mgr()
        dash = mgr.create_dashboard("Private Dash", owner_id="u1")
        assert dash.permission == DashboardPermission.PRIVATE
