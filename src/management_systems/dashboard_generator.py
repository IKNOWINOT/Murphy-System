"""
Management Systems – Dashboard Generator
========================================

Generate formatted Matrix reports from board data.

Provides:
- ASCII table rendering for board views in chat
- Periodic summary messages (daily standups, weekly reports)
- Widget types: numbers, chart/bar, battery (progress), timeline
- Dashboard templates (Project Overview, Sprint Health, Team Workload)
- Markdown-formatted output optimised for Matrix clients
- Scheduled report generation with cron-like scheduling

Integration points:
    - Board data comes from ``board_engine.py``
    - Status data comes from ``status_engine.py``
    - Reports are sent via ``message_router.py`` (PR 3)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_UTC = timezone.utc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BAR_WIDTH: int = 20
DEFAULT_TABLE_COL_WIDTH: int = 18
SCHEDULE_CHECK_TOLERANCE_SEC: int = 60

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class WidgetType(Enum):
    """Dashboard widget types."""

    NUMBERS = "numbers"       # Single numeric KPI
    BAR_CHART = "bar_chart"   # Horizontal bar chart
    BATTERY = "battery"       # Progress / completion indicator
    TIMELINE = "timeline"     # Mini timeline summary
    STATUS_SUMMARY = "status_summary"   # Status distribution
    TABLE = "table"           # Full ASCII table
    TEXT = "text"             # Free-form text / notes


class ScheduleInterval(Enum):
    """Pre-defined scheduling intervals."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class DashboardTemplateType(Enum):
    """Pre-built dashboard templates."""

    PROJECT_OVERVIEW = "project_overview"
    SPRINT_HEALTH = "sprint_health"
    TEAM_WORKLOAD = "team_workload"
    EXECUTIVE_SUMMARY = "executive_summary"
    BUG_TRACKER_SUMMARY = "bug_tracker_summary"
    DEPLOYMENT_STATUS = "deployment_status"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


def _now_dt() -> datetime:
    return datetime.now(tz=_UTC)


# ---------------------------------------------------------------------------
# Widget rendering helpers
# ---------------------------------------------------------------------------


def _render_bar(value: float, max_value: float, width: int = DEFAULT_BAR_WIDTH) -> str:
    """Render a horizontal bar representing *value* / *max_value*.

    Returns:
        String like ``████████░░░░  60%``.
    """
    if max_value <= 0:
        return "░" * width + "   0%"
    ratio = min(1.0, value / max_value)
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = ratio * 100
    return f"{bar} {pct:5.1f}%"


def _render_battery(percentage: float, width: int = 10) -> str:
    """Render a battery-style progress indicator.

    Returns:
        String like ``[███░░░░░░░] 30%``.
    """
    filled = max(0, min(width, int(percentage / 100 * width)))
    bar = "█" * filled + "░" * (width - filled)
    symbol = "🔋" if percentage >= 80 else ("⚡" if percentage >= 40 else "🪫")
    return f"{symbol}[{bar}] {percentage:.0f}%"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DashboardWidget:
    """A single widget in a dashboard.

    Args:
        title: Widget display title.
        widget_type: Rendering type.
        data: Type-specific data payload.
          - NUMBERS: ``{"value": 42, "label": "Open Items", "unit": ""}``
          - BAR_CHART: ``{"bars": [{"label": "A", "value": 5, "max": 10}]}``
          - BATTERY: ``{"percentage": 75, "label": "Sprint Progress"}``
          - STATUS_SUMMARY: ``{"counts": {"Done": 5, "In Progress": 3, "Stuck": 1}}``
          - TEXT: ``{"content": "Freeform markdown text"}``
          - TABLE: ``{"headers": [...], "rows": [[...]]}``
    """

    title: str
    widget_type: WidgetType
    data: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_uid)

    def render(self) -> str:
        """Render the widget as a Markdown-compatible string."""
        header = f"**{self.title}**"
        if self.widget_type == WidgetType.NUMBERS:
            value = self.data.get("value", 0)
            label = self.data.get("label", "")
            unit = self.data.get("unit", "")
            return f"{header}\n> **{value}{unit}** {label}"

        if self.widget_type == WidgetType.BAR_CHART:
            bars = self.data.get("bars", [])
            if not bars:
                return f"{header}\n> No data."
            max_v = max((b.get("max", b.get("value", 1)) for b in bars), default=1)
            lines = [header, "```"]
            label_w = max((len(b.get("label", "")) for b in bars), default=8)
            for b in bars:
                lbl = b.get("label", "")[:label_w].ljust(label_w)
                bar = _render_bar(b.get("value", 0), max_v)
                lines.append(f"{lbl} │ {bar}")
            lines.append("```")
            return "\n".join(lines)

        if self.widget_type == WidgetType.BATTERY:
            pct = self.data.get("percentage", 0)
            label = self.data.get("label", "")
            return f"{header}\n> {_render_battery(pct)} {label}"

        if self.widget_type == WidgetType.STATUS_SUMMARY:
            counts = self.data.get("counts", {})
            if not counts:
                return f"{header}\n> No status data."
            lines = [header, "```"]
            max_count = max(counts.values(), default=1)
            for status, count in sorted(counts.items(), key=lambda x: -x[1]):
                bar = _render_bar(count, max_count, width=15)
                lines.append(f"{status:<20} {bar}  ({count})")
            lines.append("```")
            return "\n".join(lines)

        if self.widget_type == WidgetType.TEXT:
            content = self.data.get("content", "")
            return f"{header}\n{content}"

        if self.widget_type == WidgetType.TABLE:
            headers = self.data.get("headers", [])
            rows = self.data.get("rows", [])
            if not headers:
                return f"{header}\n> No data."
            w = DEFAULT_TABLE_COL_WIDTH
            sep = "+-" + "-+-".join("-" * w for _ in headers) + "-+"
            def row_str(cells: List[Any]) -> str:
                return "| " + " | ".join(str(c)[:w].ljust(w) for c in cells) + " |"
            lines = [header, "```", sep, row_str(headers), sep]
            for row in rows:
                lines.append(row_str([str(c) for c in row]))
            lines += [sep, "```"]
            return "\n".join(lines)

        if self.widget_type == WidgetType.TIMELINE:
            items = self.data.get("items", [])
            lines = [header, "```"]
            for it in items:
                name = it.get("name", "")[:20]
                start = it.get("start_date", "")
                end = it.get("end_date", "")
                pct = it.get("progress", 0)
                lines.append(f"  {name:<20}  {start} → {end}  ({pct:.0f}%)")
            lines.append("```")
            return "\n".join(lines)

        return f"{header}\n> (widget type not rendered)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "widget_type": self.widget_type.value,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardWidget":
        obj = cls(
            title=data["title"],
            widget_type=WidgetType(data["widget_type"]),
            data=data.get("data", {}),
        )
        obj.id = data.get("id", obj.id)
        return obj


@dataclass
class ScheduledReport:
    """A report that fires on a recurring schedule.

    Args:
        name: Report name.
        dashboard_template: Template type to use.
        interval: Scheduling interval.
        matrix_room_id: Target Matrix room.
        custom_interval_seconds: Used when interval is CUSTOM.
    """

    name: str
    dashboard_template: DashboardTemplateType
    interval: ScheduleInterval
    matrix_room_id: str = ""
    custom_interval_seconds: int = 3600
    enabled: bool = True
    last_sent_at: str = ""
    next_due_at: str = field(default_factory=_now)
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def is_due(self) -> bool:
        """Return *True* if the report is due to run now."""
        if not self.enabled:
            return False
        if not self.next_due_at:
            return True
        try:
            due = datetime.fromisoformat(self.next_due_at)
        except ValueError:
            return True
        return _now_dt() >= due

    def advance_schedule(self) -> None:
        """Update *next_due_at* based on the interval setting."""
        now = _now_dt()
        if self.interval == ScheduleInterval.HOURLY:
            delta = timedelta(hours=1)
        elif self.interval == ScheduleInterval.DAILY:
            delta = timedelta(days=1)
        elif self.interval == ScheduleInterval.WEEKLY:
            delta = timedelta(weeks=1)
        elif self.interval == ScheduleInterval.MONTHLY:
            delta = timedelta(days=30)
        else:
            delta = timedelta(seconds=self.custom_interval_seconds)
        self.last_sent_at = now.isoformat()
        self.next_due_at = (now + delta).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "dashboard_template": self.dashboard_template.value,
            "interval": self.interval.value,
            "matrix_room_id": self.matrix_room_id,
            "custom_interval_seconds": self.custom_interval_seconds,
            "enabled": self.enabled,
            "last_sent_at": self.last_sent_at,
            "next_due_at": self.next_due_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledReport":
        obj = cls(
            name=data["name"],
            dashboard_template=DashboardTemplateType(data["dashboard_template"]),
            interval=ScheduleInterval(data["interval"]),
            matrix_room_id=data.get("matrix_room_id", ""),
            custom_interval_seconds=data.get("custom_interval_seconds", 3600),
            enabled=data.get("enabled", True),
        )
        obj.id = data.get("id", obj.id)
        obj.last_sent_at = data.get("last_sent_at", "")
        obj.next_due_at = data.get("next_due_at", obj.next_due_at)
        obj.created_at = data.get("created_at", obj.created_at)
        return obj


@dataclass
class DashboardTemplate:
    """A named dashboard layout composed of multiple widgets.

    Args:
        name: Display name.
        template_type: Enum identifier.
        description: Brief description.
        widget_slots: Ordered widget type descriptors.
    """

    name: str
    template_type: DashboardTemplateType
    description: str = ""
    widget_slots: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "template_type": self.template_type.value,
            "description": self.description,
            "widget_slots": self.widget_slots,
        }


_DASHBOARD_TEMPLATES: Dict[DashboardTemplateType, DashboardTemplate] = {
    DashboardTemplateType.PROJECT_OVERVIEW: DashboardTemplate(
        name="Project Overview",
        template_type=DashboardTemplateType.PROJECT_OVERVIEW,
        description="High-level snapshot: status distribution, open items, and progress.",
        widget_slots=[
            {"type": "numbers", "title": "Open Items"},
            {"type": "battery", "title": "Overall Progress"},
            {"type": "status_summary", "title": "Status Distribution"},
            {"type": "timeline", "title": "Upcoming Milestones"},
        ],
    ),
    DashboardTemplateType.SPRINT_HEALTH: DashboardTemplate(
        name="Sprint Health",
        template_type=DashboardTemplateType.SPRINT_HEALTH,
        description="Sprint velocity, remaining work, and blocker count.",
        widget_slots=[
            {"type": "numbers", "title": "Story Points Done"},
            {"type": "numbers", "title": "Blockers"},
            {"type": "battery", "title": "Sprint Progress"},
            {"type": "status_summary", "title": "Status Breakdown"},
        ],
    ),
    DashboardTemplateType.TEAM_WORKLOAD: DashboardTemplate(
        name="Team Workload",
        template_type=DashboardTemplateType.TEAM_WORKLOAD,
        description="Items per assignee, overdue count, capacity vs load.",
        widget_slots=[
            {"type": "bar_chart", "title": "Items per Assignee"},
            {"type": "numbers", "title": "Overdue Items"},
            {"type": "battery", "title": "Team Capacity"},
        ],
    ),
    DashboardTemplateType.EXECUTIVE_SUMMARY: DashboardTemplate(
        name="Executive Summary",
        template_type=DashboardTemplateType.EXECUTIVE_SUMMARY,
        description="Top-level KPIs across all workspaces.",
        widget_slots=[
            {"type": "numbers", "title": "Total Active Boards"},
            {"type": "numbers", "title": "Completed This Week"},
            {"type": "battery", "title": "Portfolio Health"},
            {"type": "text", "title": "Highlights"},
        ],
    ),
}


# ---------------------------------------------------------------------------
# Dashboard Generator
# ---------------------------------------------------------------------------


class DashboardGenerator:
    """Generates and schedules formatted Matrix dashboard reports.

    Builds widget-based dashboards from board/status data, renders them as
    Markdown strings suitable for Matrix, and manages scheduled report jobs.

    Example::

        gen = DashboardGenerator()
        report = gen.generate_report(
            DashboardTemplateType.SPRINT_HEALTH,
            board_data={
                "open_items": 8,
                "completed": 12,
                "progress": 60.0,
                "status_counts": {"In Progress": 5, "Done": 12, "Stuck": 3},
            },
        )
        print(report)
    """

    def __init__(self) -> None:
        self._scheduled: Dict[str, ScheduledReport] = {}
        self._send_callback: Optional[Callable[[str, str], None]] = None

    # -- Templates ----------------------------------------------------------

    @staticmethod
    def list_templates() -> List[DashboardTemplate]:
        """Return all available dashboard templates."""
        return list(_DASHBOARD_TEMPLATES.values())

    @staticmethod
    def get_template(template_type: DashboardTemplateType) -> Optional[DashboardTemplate]:
        """Return a named template or *None*."""
        return _DASHBOARD_TEMPLATES.get(template_type)

    # -- Report generation --------------------------------------------------

    def generate_report(
        self,
        template_type: DashboardTemplateType,
        board_data: Dict[str, Any],
        *,
        title: Optional[str] = None,
    ) -> str:
        """Generate a formatted Markdown dashboard report.

        Args:
            template_type: Dashboard template to use.
            board_data: Flat dict of data values consumed by widget slots.
              Common keys:
                - ``open_items`` (int)
                - ``completed`` (int)
                - ``progress`` (float)
                - ``status_counts`` (Dict[str, int])
                - ``items_per_assignee`` (Dict[str, int])
                - ``overdue`` (int)
                - ``story_points_done`` (int)
                - ``blockers`` (int)
                - ``timeline_items`` (List[dict])
                - ``highlights`` (str)
            title: Optional override for the dashboard title.

        Returns:
            Multi-line Markdown string.
        """
        tpl = _DASHBOARD_TEMPLATES.get(template_type)
        if tpl is None:
            return f"Unknown dashboard template: {template_type.value}"

        report_title = title or tpl.name
        ts = _now_dt().strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"## 📊 {report_title}",
            f"*Generated: {ts}*",
            "",
        ]

        for slot in tpl.widget_slots:
            widget = self._build_widget(slot, board_data)
            lines.append(widget.render())
            lines.append("")

        return "\n".join(lines)

    def generate_standup(
        self,
        team_name: str,
        completed_items: List[str],
        in_progress_items: List[str],
        blocked_items: List[str],
    ) -> str:
        """Generate a daily standup report.

        Args:
            team_name: Name of the team.
            completed_items: Items completed since last standup.
            in_progress_items: Items currently in progress.
            blocked_items: Blocked items requiring attention.

        Returns:
            Markdown-formatted standup message.
        """
        ts = _now_dt().strftime("%A, %B %d %Y")
        lines = [
            f"## 🌅 Daily Standup – {team_name}",
            f"*{ts}*",
            "",
            "### ✅ Completed",
        ]
        if completed_items:
            lines += [f"- {item}" for item in completed_items]
        else:
            lines.append("- (none)")

        lines += ["", "### 🔄 In Progress"]
        if in_progress_items:
            lines += [f"- {item}" for item in in_progress_items]
        else:
            lines.append("- (none)")

        lines += ["", "### 🚨 Blocked"]
        if blocked_items:
            lines += [f"- {item}" for item in blocked_items]
        else:
            lines.append("- (none)")

        return "\n".join(lines)

    def generate_weekly_report(
        self,
        workspace_name: str,
        stats: Dict[str, Any],
    ) -> str:
        """Generate a weekly summary report.

        Args:
            workspace_name: Workspace being reported on.
            stats: Dict with keys like ``completed``, ``created``, ``overdue``,
              ``progress``, ``top_contributors`` (list of names).

        Returns:
            Markdown-formatted weekly report.
        """
        week_end = _now_dt().strftime("%B %d, %Y")
        completed = stats.get("completed", 0)
        created = stats.get("created", 0)
        overdue = stats.get("overdue", 0)
        progress = stats.get("progress", 0.0)
        contributors = stats.get("top_contributors", [])

        lines = [
            f"## 📅 Weekly Report – {workspace_name}",
            f"*Week ending {week_end}*",
            "",
            f"**Items Completed:** {completed}  |  **Items Created:** {created}  |  **Overdue:** {overdue}",
            "",
            f"**Overall Progress:** {_render_battery(progress)}",
            "",
        ]
        if contributors:
            lines.append("**Top Contributors:**")
            lines += [f"- {name}" for name in contributors[:5]]

        return "\n".join(lines)

    # -- Scheduled reports --------------------------------------------------

    def schedule_report(
        self,
        name: str,
        template_type: DashboardTemplateType,
        interval: ScheduleInterval,
        matrix_room_id: str,
        *,
        custom_interval_seconds: int = 3600,
    ) -> ScheduledReport:
        """Register a recurring scheduled report.

        Args:
            name: Human-readable name.
            template_type: Dashboard template to render.
            interval: Recurrence interval.
            matrix_room_id: Target Matrix room ID.
            custom_interval_seconds: Used when *interval* is CUSTOM.

        Returns:
            The :class:`ScheduledReport` entry.
        """
        report = ScheduledReport(
            name=name,
            dashboard_template=template_type,
            interval=interval,
            matrix_room_id=matrix_room_id,
            custom_interval_seconds=custom_interval_seconds,
        )
        self._scheduled[report.id] = report
        logger.info("Scheduled report: %s every %s", name, interval.value)
        return report

    def get_due_reports(self) -> List[ScheduledReport]:
        """Return all scheduled reports that are currently due."""
        return [r for r in self._scheduled.values() if r.is_due()]

    def mark_sent(self, report_id: str) -> bool:
        """Mark a scheduled report as sent and advance its schedule."""
        report = self._scheduled.get(report_id)
        if report is None:
            return False
        report.advance_schedule()
        return True

    def register_send_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """Register a callback invoked when a report is sent.

        Args:
            callback: ``(matrix_room_id, markdown_content) -> None``
        """
        self._send_callback = callback

    # -- Serialisation ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scheduled": {rid: r.to_dict() for rid, r in self._scheduled.items()}
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        self._scheduled = {
            rid: ScheduledReport.from_dict(rdata)
            for rid, rdata in data.get("scheduled", {}).items()
        }

    # -- Private helpers ----------------------------------------------------

    def _build_widget(
        self, slot: Dict[str, Any], board_data: Dict[str, Any]
    ) -> DashboardWidget:
        """Construct a widget from a template slot definition and board data."""
        slot_type = slot.get("type", "text")
        title = slot.get("title", "Widget")
        w_type = WidgetType(slot_type) if slot_type in {wt.value for wt in WidgetType} else WidgetType.TEXT

        payload: Dict[str, Any] = {}
        if w_type == WidgetType.NUMBERS:
            # Map slot title to board_data key heuristically
            key_map = {
                "Open Items": "open_items",
                "Completed": "completed",
                "Blockers": "blockers",
                "Overdue Items": "overdue",
                "Story Points Done": "story_points_done",
                "Total Active Boards": "total_boards",
                "Completed This Week": "completed_this_week",
            }
            data_key = key_map.get(title, title.lower().replace(" ", "_"))
            payload = {"value": board_data.get(data_key, 0), "label": title}

        elif w_type == WidgetType.BATTERY:
            payload = {
                "percentage": board_data.get("progress", 0.0),
                "label": title,
            }
            if title == "Team Capacity":
                payload["percentage"] = board_data.get("capacity", 0.0)
            elif title == "Portfolio Health":
                payload["percentage"] = board_data.get("portfolio_health", 0.0)

        elif w_type == WidgetType.STATUS_SUMMARY:
            payload = {"counts": board_data.get("status_counts", {})}

        elif w_type == WidgetType.BAR_CHART:
            if title == "Items per Assignee":
                ipa = board_data.get("items_per_assignee", {})
                max_v = max(ipa.values(), default=1)
                payload = {
                    "bars": [
                        {"label": name, "value": count, "max": max_v}
                        for name, count in sorted(ipa.items(), key=lambda x: -x[1])
                    ]
                }
            else:
                payload = {"bars": board_data.get("bars", [])}

        elif w_type == WidgetType.TIMELINE:
            payload = {"items": board_data.get("timeline_items", [])}

        elif w_type == WidgetType.TEXT:
            payload = {"content": board_data.get("highlights", "_No highlights this period._")}

        return DashboardWidget(title=title, widget_type=w_type, data=payload)
