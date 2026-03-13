"""
Board System – View Engine
============================

Transforms board data into view-specific representations
(Table, Kanban, Calendar, Timeline, Chart).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from .models import Board, ColumnType, Item, ViewConfig, ViewType

# ---------------------------------------------------------------------------
# Filtering & Sorting helpers
# ---------------------------------------------------------------------------

def _matches_filter(item: Item, filt: Dict[str, Any]) -> bool:
    """Evaluate a single filter condition against an *item*."""
    col_id = filt.get("column_id", "")
    operator = filt.get("operator", "eq")
    target = filt.get("value")

    cell = item.get_cell(col_id)
    actual = cell.value if cell else None

    if operator == "eq":
        return actual == target
    if operator == "neq":
        return actual != target
    if operator == "gt":
        return actual is not None and actual > target
    if operator == "lt":
        return actual is not None and actual < target
    if operator == "gte":
        return actual is not None and actual >= target
    if operator == "lte":
        return actual is not None and actual <= target
    if operator == "contains":
        return target is not None and str(target) in str(actual or "")
    if operator == "not_contains":
        return target is not None and str(target) not in str(actual or "")
    if operator == "is_empty":
        return actual is None or actual == "" or actual == []
    if operator == "is_not_empty":
        return actual is not None and actual != "" and actual != []
    return True


def apply_filters(items: List[Item], filters: List[Dict[str, Any]]) -> List[Item]:
    """Return items that satisfy *all* filter conditions."""
    if not filters:
        return items
    return [it for it in items if all(_matches_filter(it, f) for f in filters)]


def apply_sort(items: List[Item], sort_rules: List[Dict[str, str]]) -> List[Item]:
    """Sort items according to *sort_rules* (list of ``{column_id, direction}``)."""
    if not sort_rules:
        return items

    def _sort_key(item: Item) -> tuple:
        keys: list = []
        for rule in sort_rules:
            col_id = rule.get("column_id", "")
            cell = item.get_cell(col_id)
            val = cell.value if cell else None
            # Normalise None for consistent comparison
            keys.append((0 if val is not None else 1, val if val is not None else ""))
        return tuple(keys)

    descending = any(r.get("direction", "asc") == "desc" for r in sort_rules)
    return sorted(items, key=_sort_key, reverse=descending)


# ---------------------------------------------------------------------------
# View renderers
# ---------------------------------------------------------------------------

def render_table_view(board: Board, view: ViewConfig) -> Dict[str, Any]:
    """Render the board as a flat table grouped by group."""
    visible_cols = [
        c for c in board.columns if c.id not in view.hidden_columns
    ]
    items = apply_filters(board.all_items(), view.filters)
    items = apply_sort(items, view.sort_by)

    groups_data = []
    for grp in board.groups:
        grp_items = [it for it in items if it.group_id == grp.id]
        groups_data.append({
            "group_id": grp.id,
            "title": grp.title,
            "color": grp.color,
            "collapsed": grp.collapsed,
            "items": [it.to_dict() for it in grp_items],
        })

    return {
        "view_type": ViewType.TABLE.value,
        "columns": [c.to_dict() for c in visible_cols],
        "groups": groups_data,
        "total_items": len(items),
    }


def render_kanban_view(board: Board, view: ViewConfig) -> Dict[str, Any]:
    """Render the board as Kanban lanes grouped by a status column."""
    group_by = view.settings.get("kanban_column_id", "")
    items = apply_filters(board.all_items(), view.filters)
    items = apply_sort(items, view.sort_by)

    lanes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for it in items:
        cell = it.get_cell(group_by) if group_by else None
        lane_key = cell.display_value if cell else "Unassigned"
        lanes[lane_key].append(it.to_dict())

    return {
        "view_type": ViewType.KANBAN.value,
        "group_by_column": group_by,
        "lanes": dict(lanes),
        "total_items": len(items),
    }


def render_calendar_view(board: Board, view: ViewConfig) -> Dict[str, Any]:
    """Render the board as calendar events keyed by a date column."""
    date_col = view.settings.get("calendar_date_column_id", "")
    items = apply_filters(board.all_items(), view.filters)

    events: List[Dict[str, Any]] = []
    for it in items:
        cell = it.get_cell(date_col) if date_col else None
        if cell and cell.value:
            events.append({
                "item": it.to_dict(),
                "date": cell.value,
            })

    return {
        "view_type": ViewType.CALENDAR.value,
        "date_column": date_col,
        "events": events,
        "total_items": len(events),
    }


def render_timeline_view(board: Board, view: ViewConfig) -> Dict[str, Any]:
    """Render the board as a timeline (Gantt-like) using a timeline column."""
    timeline_col = view.settings.get("timeline_column_id", "")
    items = apply_filters(board.all_items(), view.filters)

    bars: List[Dict[str, Any]] = []
    for it in items:
        cell = it.get_cell(timeline_col) if timeline_col else None
        if cell and isinstance(cell.value, dict):
            bars.append({
                "item": it.to_dict(),
                "start": cell.value.get("start"),
                "end": cell.value.get("end"),
            })

    return {
        "view_type": ViewType.TIMELINE.value,
        "timeline_column": timeline_col,
        "bars": bars,
        "total_items": len(bars),
    }


def render_chart_view(board: Board, view: ViewConfig) -> Dict[str, Any]:
    """Aggregate item counts per status/group for chart rendering."""
    group_by = view.settings.get("chart_column_id", "")
    chart_type = view.settings.get("chart_type", "bar")
    items = apply_filters(board.all_items(), view.filters)

    buckets: Dict[str, int] = defaultdict(int)
    for it in items:
        cell = it.get_cell(group_by) if group_by else None
        key = cell.display_value if cell else "Other"
        buckets[key] += 1

    return {
        "view_type": ViewType.CHART.value,
        "chart_type": chart_type,
        "group_by_column": group_by,
        "data": dict(buckets),
        "total_items": len(items),
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_RENDERERS: Dict[ViewType, Callable[..., Dict[str, Any]]] = {
    ViewType.TABLE: render_table_view,
    ViewType.KANBAN: render_kanban_view,
    ViewType.CALENDAR: render_calendar_view,
    ViewType.TIMELINE: render_timeline_view,
    ViewType.CHART: render_chart_view,
}


def render_view(board: Board, view: ViewConfig) -> Dict[str, Any]:
    """Dispatch to the appropriate renderer for *view.view_type*."""
    renderer = _RENDERERS.get(view.view_type)
    if renderer is None:
        return {"error": f"Unsupported view type: {view.view_type.value}"}
    return renderer(board, view)
