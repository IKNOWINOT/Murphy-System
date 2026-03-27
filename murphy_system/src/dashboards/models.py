"""
Dashboards – Data Models
=========================

Core data structures for the Customizable Dashboards & Reporting system
(Phase 3 of management systems parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_UTC = timezone.utc


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class WidgetType(Enum):
    """Supported dashboard widget types."""
    CHART = "chart"
    NUMBER = "number"
    TABLE = "table"
    TIMELINE = "timeline"
    BATTERY = "battery"
    TEXT = "text"
    CRM_SUMMARY = "crm_summary"   # Phase 8 – CRM pipeline / deal summary widget


class ChartKind(Enum):
    """Chart sub-types for CHART widgets."""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    STACKED_BAR = "stacked_bar"
    DONUT = "donut"
    AREA = "area"


class AggregationFunction(Enum):
    """Aggregation functions for data roll-ups."""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"


class DashboardPermission(Enum):
    """Dashboard sharing levels."""
    PRIVATE = "private"
    WORKSPACE = "workspace"
    PUBLIC = "public"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

@dataclass
class DataSource:
    """Pointer to a board + optional column for data aggregation."""
    board_id: str = ""
    column_id: str = ""
    group_id: str = ""
    filters: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "board_id": self.board_id,
            "column_id": self.column_id,
            "group_id": self.group_id,
            "filters": self.filters,
        }


@dataclass
class WidgetConfig:
    """Configuration for a single dashboard widget."""
    id: str = field(default_factory=_new_id)
    widget_type: WidgetType = WidgetType.CHART
    title: str = ""
    data_sources: List[DataSource] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "w": 6, "h": 4})
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "widget_type": self.widget_type.value,
            "title": self.title,
            "data_sources": [ds.to_dict() for ds in self.data_sources],
            "settings": self.settings,
            "position": self.position,
            "created_at": self.created_at,
        }


@dataclass
class Dashboard:
    """Top-level dashboard entity."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    owner_id: str = ""
    workspace_id: str = ""
    permission: DashboardPermission = DashboardPermission.PRIVATE
    widgets: List[WidgetConfig] = field(default_factory=list)
    date_range: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def add_widget(self, widget: WidgetConfig) -> WidgetConfig:
        self.widgets.append(widget)
        self.updated_at = _now()
        return widget

    def get_widget(self, widget_id: str) -> Optional[WidgetConfig]:
        for w in self.widgets:
            if w.id == widget_id:
                return w
        return None

    def remove_widget(self, widget_id: str) -> Optional[WidgetConfig]:
        for i, w in enumerate(self.widgets):
            if w.id == widget_id:
                self.updated_at = _now()
                return self.widgets.pop(i)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "workspace_id": self.workspace_id,
            "permission": self.permission.value,
            "widgets": [w.to_dict() for w in self.widgets],
            "date_range": self.date_range,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
