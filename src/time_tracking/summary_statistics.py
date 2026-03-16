# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Summary Statistics Service
============================================

Aggregated statistics for users, teams, projects, and the whole system.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations
import logging

import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .models import EntryStatus, TimeEntry

_UTC = timezone.utc

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


def _day_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


class SummaryStatisticsService:
    """Aggregated statistics built over a shared entries dictionary."""

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

    def _snapshot(self) -> List[TimeEntry]:
        with self._lock:
            return list(self._entries.values())

    def _reportable(self, entries: List[TimeEntry]) -> List[TimeEntry]:
        return [e for e in entries if e.status in _REPORTABLE_STATUSES]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """Return key statistics for a single user."""
        now = datetime.now(tz=_UTC)
        today_str = _day_key(now)
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = now - timedelta(days=30)

        all_entries = self._snapshot()
        user_entries = self._reportable(
            [e for e in all_entries if e.user_id == user_id]
        )

        today_secs = 0
        week_secs = 0
        month_secs = 0
        billable_secs = 0
        total_secs = 0
        last30_day_set: set = set()
        project_secs: Dict[str, int] = {}

        for e in user_entries:
            dt = _parse_dt(e.started_at)
            total_secs += e.duration_seconds
            if e.billable:
                billable_secs += e.duration_seconds

            if dt:
                if _day_key(dt) == today_str:
                    today_secs += e.duration_seconds
                if dt >= week_start:
                    week_secs += e.duration_seconds
                if dt >= month_start:
                    month_secs += e.duration_seconds
                if dt >= thirty_days_ago:
                    last30_day_set.add(_day_key(dt))

            project_secs[e.board_id or "_none"] = (
                project_secs.get(e.board_id or "_none", 0) + e.duration_seconds
            )

        avg_daily_hours = (
            round(total_secs / 3600.0 / 30.0, 2) if user_entries else 0.0
        )
        billable_pct = (
            round(billable_secs / total_secs * 100.0, 1) if total_secs else 0.0
        )
        most_active_project = (
            max(project_secs, key=lambda k: project_secs[k])
            if project_secs
            else None
        )

        # Streak: consecutive days with entries ending today/yesterday
        streak_days = self._calc_streak(last30_day_set, now)

        # Count active timers for this user
        with self._lock:
            active_count = sum(
                1 for uid in self._active_timers if uid == user_id
            )

        return {
            "user_id": user_id,
            "today_hours": round(today_secs / 3600.0, 2),
            "this_week_hours": round(week_secs / 3600.0, 2),
            "this_month_hours": round(month_secs / 3600.0, 2),
            "active_timers_count": active_count,
            "billable_percentage": billable_pct,
            "average_daily_hours": avg_daily_hours,
            "most_active_project": most_active_project,
            "streak_days": streak_days,
        }

    @staticmethod
    def _calc_streak(day_set: set, now: datetime) -> int:
        """Count consecutive days (backwards from today/yesterday) with entries."""
        streak = 0
        check = now
        for _ in range(365):  # cap to prevent unbounded iteration
            key = _day_key(check)
            if key in day_set:
                streak += 1
                check -= timedelta(days=1)
            else:
                break
        return streak

    def get_team_summary(self, team_member_ids: List[str]) -> Dict[str, Any]:
        """Return aggregated statistics for a team."""
        now = datetime.now(tz=_UTC)
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        all_entries = self._snapshot()
        member_set = set(team_member_ids)

        week_entries = self._reportable(
            [
                e
                for e in all_entries
                if e.user_id in member_set
                and (_parse_dt(e.started_at) or datetime.min.replace(tzinfo=_UTC))
                >= week_start
            ]
        )

        member_hours: Dict[str, float] = {m: 0.0 for m in team_member_ids}
        billable_secs = 0
        total_secs = 0

        for e in week_entries:
            member_hours[e.user_id] = (
                member_hours.get(e.user_id, 0.0) + e.duration_seconds / 3600.0
            )
            total_secs += e.duration_seconds
            if e.billable:
                billable_secs += e.duration_seconds

        avg_per_member = (
            round(total_secs / 3600.0 / len(team_member_ids), 2)
            if team_member_ids
            else 0.0
        )
        top = max(member_hours, key=lambda k: member_hours[k]) if member_hours else None
        least = (
            min(member_hours, key=lambda k: member_hours[k]) if member_hours else None
        )
        billable_pct = (
            round(billable_secs / total_secs * 100.0, 1) if total_secs else 0.0
        )

        with self._lock:
            active_timer_users = set(self._active_timers.keys())
        members_with_active = [m for m in team_member_ids if m in active_timer_users]

        return {
            "total_hours_this_week": round(total_secs / 3600.0, 2),
            "average_per_member": avg_per_member,
            "top_contributor": top,
            "least_active": least,
            "team_billable_percentage": billable_pct,
            "members_with_active_timers": members_with_active,
        }

    def get_project_summary(self, project_id: str) -> Dict[str, Any]:
        """Return statistics for a single project."""
        now = datetime.now(tz=_UTC)
        all_entries = self._snapshot()
        proj_entries = self._reportable(
            [e for e in all_entries if e.board_id == project_id]
        )

        total_secs = sum(e.duration_seconds for e in proj_entries)
        billable_secs = sum(e.duration_seconds for e in proj_entries if e.billable)
        contributors = set(e.user_id for e in proj_entries if e.user_id)
        avg_duration = (
            round(total_secs / len(proj_entries), 0) if proj_entries else 0.0
        )

        # Busiest day
        day_secs: Dict[str, int] = {}
        for e in proj_entries:
            dt = _parse_dt(e.started_at)
            if dt:
                key = _day_key(dt)
                day_secs[key] = day_secs.get(key, 0) + e.duration_seconds
        busiest_day = max(day_secs, key=lambda k: day_secs[k]) if day_secs else None

        # Weekly totals for last 4 weeks
        hours_trend = []
        for week_offset in range(3, -1, -1):
            wk_start = (now - timedelta(weeks=week_offset)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            wk_start = wk_start - timedelta(days=wk_start.weekday())
            wk_end = wk_start + timedelta(days=7)
            wk_secs = sum(
                e.duration_seconds
                for e in proj_entries
                if (
                    (dt := _parse_dt(e.started_at)) is not None
                    and wk_start <= dt < wk_end
                )
            )
            hours_trend.append(
                {
                    "week_start": wk_start.strftime("%Y-%m-%d"),
                    "hours": round(wk_secs / 3600.0, 2),
                }
            )

        return {
            "project_id": project_id,
            "total_hours": round(total_secs / 3600.0, 2),
            "total_billable_hours": round(billable_secs / 3600.0, 2),
            "unique_contributors": len(contributors),
            "average_entry_duration": avg_duration,
            "busiest_day": busiest_day,
            "hours_trend": hours_trend,
        }

    def get_system_overview(self) -> Dict[str, Any]:
        """Return global statistics across all users/projects."""
        now = datetime.now(tz=_UTC)
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        all_entries = self._snapshot()
        reportable = self._reportable(all_entries)

        total_entries = len(reportable)
        total_secs = sum(e.duration_seconds for e in reportable)
        billable_secs = sum(e.duration_seconds for e in reportable if e.billable)
        billable_pct = (
            round(billable_secs / total_secs * 100.0, 1) if total_secs else 0.0
        )

        active_users: set = set()
        active_projects: set = set()
        for e in reportable:
            dt = _parse_dt(e.started_at)
            if dt and dt >= week_start:
                active_users.add(e.user_id)
                active_projects.add(e.board_id)

        return {
            "total_entries": total_entries,
            "total_hours_all_time": round(total_secs / 3600.0, 2),
            "active_users_this_week": len(active_users),
            "active_projects_this_week": len(active_projects),
            "global_billable_percentage": billable_pct,
        }
