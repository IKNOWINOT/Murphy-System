"""
Dashboards – Dashboard Manager
================================

Central façade for dashboard CRUD and widget management.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .aggregation import AggregationEngine
from .models import (
    Dashboard,
    DashboardPermission,
    DataSource,
    WidgetConfig,
    WidgetType,
    _now,
)
from .widgets import render_widget

logger = logging.getLogger(__name__)


class DashboardManager:
    """In-memory dashboard management engine.

    Parameters
    ----------
    board_accessor : callable, optional
        ``(board_id) -> dict`` returning board data for aggregation.
    """

    def __init__(
        self,
        board_accessor: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ) -> None:
        self._dashboards: Dict[str, Dashboard] = {}
        self._engine = AggregationEngine(board_accessor)

    # -- Dashboard CRUD -----------------------------------------------------

    def create_dashboard(
        self,
        name: str,
        *,
        description: str = "",
        owner_id: str = "",
        workspace_id: str = "",
        permission: DashboardPermission = DashboardPermission.PRIVATE,
    ) -> Dashboard:
        dash = Dashboard(
            name=name,
            description=description,
            owner_id=owner_id,
            workspace_id=workspace_id,
            permission=permission,
        )
        self._dashboards[dash.id] = dash
        logger.info("Dashboard created: %s (%s)", dash.name, dash.id)
        return dash

    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        return self._dashboards.get(dashboard_id)

    def list_dashboards(
        self,
        *,
        owner_id: str = "",
        workspace_id: str = "",
    ) -> List[Dashboard]:
        dashboards = list(self._dashboards.values())
        if owner_id:
            dashboards = [d for d in dashboards if d.owner_id == owner_id]
        if workspace_id:
            dashboards = [d for d in dashboards if d.workspace_id == workspace_id]
        return dashboards

    def update_dashboard(
        self,
        dashboard_id: str,
        *,
        user_id: str = "",
        name: Optional[str] = None,
        description: Optional[str] = None,
        permission: Optional[DashboardPermission] = None,
    ) -> Dashboard:
        dash = self._dashboards.get(dashboard_id)
        if dash is None:
            raise KeyError(f"Dashboard not found: {dashboard_id!r}")
        if user_id and dash.owner_id != user_id:
            raise PermissionError("Only the owner can edit this dashboard")
        if name is not None:
            dash.name = name
        if description is not None:
            dash.description = description
        if permission is not None:
            dash.permission = permission
        dash.updated_at = _now()
        return dash

    def delete_dashboard(self, dashboard_id: str, *, user_id: str = "") -> bool:
        dash = self._dashboards.get(dashboard_id)
        if dash is None:
            return False
        if user_id and dash.owner_id != user_id:
            raise PermissionError("Only the owner can delete this dashboard")
        del self._dashboards[dashboard_id]
        return True

    # -- Widget management --------------------------------------------------

    def add_widget(
        self,
        dashboard_id: str,
        widget_type: WidgetType,
        title: str,
        *,
        data_sources: Optional[List[DataSource]] = None,
        settings: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, int]] = None,
    ) -> WidgetConfig:
        dash = self._dashboards.get(dashboard_id)
        if dash is None:
            raise KeyError(f"Dashboard not found: {dashboard_id!r}")
        widget = WidgetConfig(
            widget_type=widget_type,
            title=title,
            data_sources=data_sources or [],
            settings=settings or {},
        )
        if position:
            widget.position = position
        dash.add_widget(widget)
        return widget

    def update_widget(
        self,
        dashboard_id: str,
        widget_id: str,
        *,
        title: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, int]] = None,
    ) -> WidgetConfig:
        dash = self._dashboards.get(dashboard_id)
        if dash is None:
            raise KeyError(f"Dashboard not found: {dashboard_id!r}")
        widget = dash.get_widget(widget_id)
        if widget is None:
            raise KeyError(f"Widget not found: {widget_id!r}")
        if title is not None:
            widget.title = title
        if settings is not None:
            widget.settings.update(settings)
        if position is not None:
            widget.position = position
        dash.updated_at = _now()
        return widget

    def remove_widget(self, dashboard_id: str, widget_id: str) -> bool:
        dash = self._dashboards.get(dashboard_id)
        if dash is None:
            raise KeyError(f"Dashboard not found: {dashboard_id!r}")
        removed = dash.remove_widget(widget_id)
        return removed is not None

    # -- Rendering ----------------------------------------------------------

    def render_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Render all widgets in a dashboard."""
        dash = self._dashboards.get(dashboard_id)
        if dash is None:
            raise KeyError(f"Dashboard not found: {dashboard_id!r}")
        rendered_widgets = []
        for widget in dash.widgets:
            rendered_widgets.append(render_widget(widget, self._engine))
        return {
            "dashboard_id": dash.id,
            "name": dash.name,
            "widgets": rendered_widgets,
        }

    def render_widget(self, dashboard_id: str, widget_id: str) -> Dict[str, Any]:
        """Render a single widget."""
        dash = self._dashboards.get(dashboard_id)
        if dash is None:
            raise KeyError(f"Dashboard not found: {dashboard_id!r}")
        widget = dash.get_widget(widget_id)
        if widget is None:
            raise KeyError(f"Widget not found: {widget_id!r}")
        return render_widget(widget, self._engine)
