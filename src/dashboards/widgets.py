"""
Dashboards – Widget Renderers
===============================

Render logic for each widget type (Chart, Number, Table, Timeline, Battery, Text).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .aggregation import AggregationEngine
from .models import (
    AggregationFunction,
    ChartKind,
    DataSource,
    WidgetConfig,
    WidgetType,
)


def render_chart_widget(
    widget: WidgetConfig,
    engine: AggregationEngine,
) -> Dict[str, Any]:
    """Render a chart widget (bar, line, pie, etc.)."""
    chart_kind = widget.settings.get("chart_kind", "bar")
    group_by_column = widget.settings.get("group_by_column", "")
    value_column = widget.settings.get("value_column", "")
    agg_fn_str = widget.settings.get("aggregation", "count")

    try:
        agg_fn = AggregationFunction(agg_fn_str)
    except ValueError:
        agg_fn = AggregationFunction.COUNT

    series: List[Dict[str, Any]] = []
    for ds in widget.data_sources:
        if group_by_column:
            # Use the group_by column for labels and value column for data
            group_ds = DataSource(
                board_id=ds.board_id,
                column_id=group_by_column,
                group_id=ds.group_id,
                filters=ds.filters,
            )
            counts = engine.count_by_column(group_ds)
            series.append({
                "board_id": ds.board_id,
                "data": counts,
            })
        else:
            counts = engine.count_by_column(ds)
            series.append({
                "board_id": ds.board_id,
                "data": counts,
            })

    return {
        "widget_type": WidgetType.CHART.value,
        "chart_kind": chart_kind,
        "title": widget.title,
        "series": series,
    }


def render_number_widget(
    widget: WidgetConfig,
    engine: AggregationEngine,
) -> Dict[str, Any]:
    """Render a number/summary widget with a single aggregated value."""
    agg_fn_str = widget.settings.get("aggregation", "count")
    try:
        agg_fn = AggregationFunction(agg_fn_str)
    except ValueError:
        agg_fn = AggregationFunction.COUNT

    total = 0
    for ds in widget.data_sources:
        total += engine.aggregate(ds, agg_fn)

    unit = widget.settings.get("unit", "")
    return {
        "widget_type": WidgetType.NUMBER.value,
        "title": widget.title,
        "value": total,
        "unit": unit,
    }


def render_table_widget(
    widget: WidgetConfig,
    engine: AggregationEngine,
) -> Dict[str, Any]:
    """Render a table widget showing raw board data."""
    columns = widget.settings.get("columns", [])
    rows: List[Dict[str, Any]] = []

    for ds in widget.data_sources:
        board = engine._get_board(ds.board_id)
        if board is None:
            continue
        for group in board.get("groups", []):
            for item in group.get("items", []):
                if not engine._matches_filters(item, ds.filters):
                    continue
                row: Dict[str, Any] = {"item_name": item.get("name", "")}
                for col_id in columns:
                    cell = item.get("cells", {}).get(col_id)
                    row[col_id] = cell.get("display_value", "") if isinstance(cell, dict) else ""
                rows.append(row)

    return {
        "widget_type": WidgetType.TABLE.value,
        "title": widget.title,
        "columns": columns,
        "rows": rows,
    }


def render_timeline_widget(
    widget: WidgetConfig,
    engine: AggregationEngine,
) -> Dict[str, Any]:
    """Render a timeline widget showing items across time."""
    timeline_column = widget.settings.get("timeline_column", "")
    bars: List[Dict[str, Any]] = []

    for ds in widget.data_sources:
        board = engine._get_board(ds.board_id)
        if board is None:
            continue
        for group in board.get("groups", []):
            for item in group.get("items", []):
                cell = item.get("cells", {}).get(timeline_column)
                if cell and isinstance(cell, dict):
                    val = cell.get("value")
                    if isinstance(val, dict) and "start" in val:
                        bars.append({
                            "item_name": item.get("name", ""),
                            "start": val.get("start"),
                            "end": val.get("end"),
                        })

    return {
        "widget_type": WidgetType.TIMELINE.value,
        "title": widget.title,
        "bars": bars,
    }


def render_battery_widget(
    widget: WidgetConfig,
    engine: AggregationEngine,
) -> Dict[str, Any]:
    """Render a battery/progress widget (percentage complete)."""
    done_value = widget.settings.get("done_value", "Done")
    status_column = widget.settings.get("status_column", "")

    total = 0
    done = 0
    for ds in widget.data_sources:
        ds_status = DataSource(
            board_id=ds.board_id,
            column_id=status_column,
            group_id=ds.group_id,
            filters=ds.filters,
        )
        counts = engine.count_by_column(ds_status)
        for label, count in counts.items():
            total += count
            if label == done_value:
                done += count

    percentage = round((done / total * 100) if total > 0 else 0, 1)
    return {
        "widget_type": WidgetType.BATTERY.value,
        "title": widget.title,
        "total": total,
        "done": done,
        "percentage": percentage,
    }


def render_text_widget(
    widget: WidgetConfig,
    engine: AggregationEngine,
) -> Dict[str, Any]:
    """Render a static text/markdown widget."""
    return {
        "widget_type": WidgetType.TEXT.value,
        "title": widget.title,
        "content": widget.settings.get("content", ""),
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_RENDERERS: Dict[WidgetType, Callable[..., Dict[str, Any]]] = {
    WidgetType.CHART: render_chart_widget,
    WidgetType.NUMBER: render_number_widget,
    WidgetType.TABLE: render_table_widget,
    WidgetType.TIMELINE: render_timeline_widget,
    WidgetType.BATTERY: render_battery_widget,
    WidgetType.TEXT: render_text_widget,
}


def render_widget(
    widget: WidgetConfig,
    engine: AggregationEngine,
) -> Dict[str, Any]:
    """Dispatch to the appropriate renderer for *widget.widget_type*."""
    renderer = _RENDERERS.get(widget.widget_type)
    if renderer is None:
        return {"error": f"Unsupported widget type: {widget.widget_type.value}"}
    return renderer(widget, engine)
