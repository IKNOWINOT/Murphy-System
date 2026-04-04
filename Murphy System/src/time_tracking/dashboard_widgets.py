# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Dashboard Widgets
====================================

Pre-built widget configurations for time tracking data.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .models import EntryStatus, TimeEntry

_UTC = timezone.utc

# Statuses that count as completed work
_REPORTABLE_STATUSES = {
    EntryStatus.COMPLETED,
    EntryStatus.STOPPED,
    EntryStatus.SUBMITTED,
    EntryStatus.APPROVED,
    EntryStatus.REJECTED,
}


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=_UTC)
    except (ValueError, TypeError):
        return None


def _week_start(ref: Optional[datetime] = None) -> datetime:
    now = ref or datetime.now(tz=_UTC)
    return (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


class TimeTrackingWidgetFactory:
    """Factory that produces pre-built widget configuration dicts."""

    def __init__(
        self,
        entries: Dict[str, "TimeEntry"],
        lock: threading.Lock,
        active_timers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._entries = entries
        self._lock = lock
        self._active_timers: Dict[str, str] = active_timers or {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_entries(
        self,
        *,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
        statuses: Optional[set] = None,
    ) -> List[TimeEntry]:
        statuses = statuses or _REPORTABLE_STATUSES
        with self._lock:
            entries = list(self._entries.values())

        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if project_id:
            entries = [e for e in entries if e.board_id == project_id]
        if date_range:
            start = _parse_dt(date_range.get("start", ""))
            end = _parse_dt(date_range.get("end", ""))
            filtered = []
            for e in entries:
                dt = _parse_dt(e.started_at)
                if dt is None:
                    filtered.append(exc)
                    continue
                if start and dt < start:
                    continue
                if end and dt > end:
                    continue
                filtered.append(exc)
            entries = filtered

        return [e for e in entries if e.status in statuses]

    # ------------------------------------------------------------------
    # Public widget builders
    # ------------------------------------------------------------------

    def hours_by_project_widget(
        self,
        user_id: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Bar chart showing total hours per project."""
        entries = self._get_entries(user_id=user_id, date_range=date_range)
        totals: Dict[str, float] = {}
        for e in entries:
            key = e.board_id or "_none"
            totals[key] = totals.get(key, 0.0) + e.duration_seconds / 3600.0

        return {
            "widget_type": "bar_chart",
            "title": "Hours by Project",
            "description": "Total hours logged per project",
            "data": {
                "labels": list(totals.keys()),
                "values": [round(v, 2) for v in totals.values()],
            },
            "settings": {
                "x_axis": "Project",
                "y_axis": "Hours",
                "user_id": user_id,
                "date_range": date_range,
            },
        }

    def hours_by_user_widget(
        self,
        project_id: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Bar chart showing hours per team member."""
        entries = self._get_entries(project_id=project_id, date_range=date_range)
        totals: Dict[str, float] = {}
        for e in entries:
            key = e.user_id or "_unknown"
            totals[key] = totals.get(key, 0.0) + e.duration_seconds / 3600.0

        return {
            "widget_type": "bar_chart",
            "title": "Hours by Team Member",
            "description": "Total hours logged per team member",
            "data": {
                "labels": list(totals.keys()),
                "values": [round(v, 2) for v in totals.values()],
            },
            "settings": {
                "x_axis": "Member",
                "y_axis": "Hours",
                "project_id": project_id,
                "date_range": date_range,
            },
        }

    def daily_hours_widget(
        self,
        user_id: Optional[str] = None,
        days: int = 14,
    ) -> Dict[str, Any]:
        """Line chart showing daily hours over time."""
        now = datetime.now(tz=_UTC)
        daily: Dict[str, float] = {}
        for i in range(days - 1, -1, -1):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            daily[day] = 0.0

        dr = {
            "start": (now - timedelta(days=days - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat(),
            "end": now.isoformat(),
        }
        entries = self._get_entries(user_id=user_id, date_range=dr)
        for e in entries:
            dt = _parse_dt(e.started_at)
            if dt:
                day_key = dt.strftime("%Y-%m-%d")
                if day_key in daily:
                    daily[day_key] += e.duration_seconds / 3600.0

        return {
            "widget_type": "line_chart",
            "title": "Daily Hours",
            "description": f"Hours logged per day over last {days} days",
            "data": {
                "labels": list(daily.keys()),
                "values": [round(v, 2) for v in daily.values()],
            },
            "settings": {
                "x_axis": "Date",
                "y_axis": "Hours",
                "user_id": user_id,
                "days": days,
            },
        }

    def billable_ratio_widget(
        self,
        user_id: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Pie chart showing billable vs non-billable split."""
        entries = self._get_entries(user_id=user_id, date_range=date_range)
        billable = sum(e.duration_seconds for e in entries if e.billable)
        non_billable = sum(e.duration_seconds for e in entries if not e.billable)
        total = billable + non_billable
        billable_h = round(billable / 3600.0, 2)
        non_billable_h = round(non_billable / 3600.0, 2)
        billable_pct = round(billable / total * 100, 1) if total else 0.0

        return {
            "widget_type": "pie_chart",
            "title": "Billable vs Non-Billable",
            "description": "Split of billable and non-billable hours",
            "data": {
                "labels": ["Billable", "Non-Billable"],
                "values": [billable_h, non_billable_h],
                "billable_percentage": billable_pct,
            },
            "settings": {
                "user_id": user_id,
                "date_range": date_range,
            },
        }

    def weekly_summary_widget(
        self,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """KPI widget with this week's key metrics."""
        week_start = _week_start()
        dr = {"start": week_start.isoformat(), "end": datetime.now(tz=_UTC).isoformat()}
        entries = self._get_entries(user_id=user_id, date_range=dr)

        total_secs = sum(e.duration_seconds for e in entries)
        billable_secs = sum(e.duration_seconds for e in entries if e.billable)
        entries_count = len(entries)
        now = datetime.now(tz=_UTC)
        days_elapsed = max(1, (now - week_start).days + 1)
        avg_hours_per_day = round((total_secs / 3600.0) / days_elapsed, 2)

        return {
            "widget_type": "kpi",
            "title": "Weekly Summary",
            "description": "Key time tracking metrics for the current week",
            "data": {
                "total_hours": round(total_secs / 3600.0, 2),
                "billable_hours": round(billable_secs / 3600.0, 2),
                "entries_count": entries_count,
                "average_hours_per_day": avg_hours_per_day,
            },
            "settings": {
                "user_id": user_id,
                "week_start": week_start.isoformat(),
            },
        }

    def overdue_timers_widget(self, threshold_hours: float = 8.0) -> Dict[str, Any]:
        """List widget showing timers running longer than threshold_hours."""
        now = datetime.now(tz=_UTC)
        threshold_secs = threshold_hours * 3600.0
        overdue = []

        with self._lock:
            running_ids = dict(self._active_timers)
            entries_snapshot = dict(self._entries)

        for user_id, entry_id in running_ids.items():
            entry = entries_snapshot.get(entry_id)
            if entry is None:
                continue
            start_dt = _parse_dt(entry.started_at)
            if start_dt is None:
                continue
            elapsed = (now - start_dt).total_seconds()
            if elapsed >= threshold_secs:
                overdue.append(
                    {
                        "user_id": user_id,
                        "entry_id": entry_id,
                        "started_at": entry.started_at,
                        "elapsed_hours": round(elapsed / 3600.0, 2),
                        "board_id": entry.board_id,
                        "item_id": entry.item_id,
                        "note": entry.note,
                    }
                )

        overdue.sort(key=lambda x: x["elapsed_hours"], reverse=True)

        return {
            "widget_type": "list",
            "title": "Overdue Timers",
            "description": f"Timers running longer than {threshold_hours} hours (likely forgotten)",
            "data": {
                "overdue_timers": overdue,
                "count": len(overdue),
            },
            "settings": {
                "threshold_hours": threshold_hours,
            },
        }

    def team_capacity_widget(
        self,
        team_members: List[str],
        target_hours_per_week: float = 40.0,
    ) -> Dict[str, Any]:
        """Gauge widget showing each member's utilization vs target."""
        week_start = _week_start()
        dr = {"start": week_start.isoformat(), "end": datetime.now(tz=_UTC).isoformat()}

        members_data = []
        for member_id in team_members:
            entries = self._get_entries(user_id=member_id, date_range=dr)
            actual_hours = round(
                sum(e.duration_seconds for e in entries) / 3600.0, 2
            )
            utilization = round(
                actual_hours / target_hours_per_week * 100.0, 1
            ) if target_hours_per_week else 0.0
            members_data.append(
                {
                    "user_id": member_id,
                    "actual_hours": actual_hours,
                    "target_hours": target_hours_per_week,
                    "utilization_percentage": utilization,
                }
            )

        return {
            "widget_type": "gauge",
            "title": "Team Capacity",
            "description": "Weekly utilization vs target hours per team member",
            "data": {
                "members": members_data,
                "target_hours_per_week": target_hours_per_week,
            },
            "settings": {
                "team_members": team_members,
                "target_hours_per_week": target_hours_per_week,
            },
        }
