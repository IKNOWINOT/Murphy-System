# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Team & Manager Views
=======================================

Composite views for managers: team dashboards, member detail,
utilization reports, and side-by-side team comparisons.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from .models import EntryStatus, TimeEntry
from .summary_statistics import _REPORTABLE_STATUSES, SummaryStatisticsService, _parse_dt

_UTC = timezone.utc


class TeamViewService:
    """Composite views for managers built over a shared entries dictionary."""

    def __init__(
        self,
        entries: Dict[str, "TimeEntry"],
        lock: threading.Lock,
        active_timers: Optional[Dict[str, str]] = None,
        manager_teams: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self._entries = entries
        self._lock = lock
        self._active_timers: Dict[str, str] = active_timers or {}
        # manager_id → list of member_ids they manage
        self._manager_teams: Dict[str, List[str]] = manager_teams or {}
        self._stats = SummaryStatisticsService(entries, lock, active_timers)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    def _check_access(self, manager_id: str, member_ids: List[str]) -> None:
        """Raise PermissionError if manager_id does not manage all member_ids."""
        managed = set(self._manager_teams.get(manager_id, []))
        # If no team mapping is defined for manager, allow access (open default)
        if not managed:
            return
        unauthorized = [m for m in member_ids if m not in managed]
        if unauthorized:
            raise PermissionError(
                f"Manager {manager_id!r} does not have access to members: {unauthorized}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _snapshot(self) -> List[TimeEntry]:
        with self._lock:
            return list(self._entries.values())

    def _reportable(self, entries: List[TimeEntry]) -> List[TimeEntry]:
        return [e for e in entries if e.status in _REPORTABLE_STATUSES]

    def _week_start(self, ref: Optional[datetime] = None) -> datetime:
        now = ref or datetime.now(tz=_UTC)
        return (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    # ------------------------------------------------------------------
    # Public views
    # ------------------------------------------------------------------

    def get_team_dashboard(
        self,
        manager_id: str,
        team_member_ids: List[str],
    ) -> Dict[str, Any]:
        """Composite team dashboard: summary, per-member hours, overdue timers."""
        self._check_access(manager_id, team_member_ids)

        # Team summary
        team_summary = self._stats.get_team_summary(team_member_ids)

        # Per-member weekly hours
        now = datetime.now(tz=_UTC)
        week_start = self._week_start(now)
        dr_start = week_start.isoformat()
        dr_end = now.isoformat()

        all_entries = self._snapshot()
        member_set = set(team_member_ids)
        member_weekly: Dict[str, float] = {m: 0.0 for m in team_member_ids}

        for e in self._reportable(all_entries):
            if e.user_id not in member_set:
                continue
            dt = _parse_dt(e.started_at)
            if dt and dt >= week_start:
                member_weekly[e.user_id] = (
                    member_weekly.get(e.user_id, 0.0) + e.duration_seconds / 3600.0
                )

        # Entries pending approval
        pending = [
            e.to_dict()
            for e in all_entries
            if e.user_id in member_set and e.status == EntryStatus.SUBMITTED
        ]

        # Overdue timers (running > 8 hours)
        overdue_threshold = 8.0 * 3600.0
        overdue = []
        with self._lock:
            running_ids = dict(self._active_timers)
            entries_snap = dict(self._entries)

        for uid, eid in running_ids.items():
            if uid not in member_set:
                continue
            entry = entries_snap.get(eid)
            if entry is None:
                continue
            start_dt = _parse_dt(entry.started_at)
            if start_dt is None:
                continue
            elapsed = (now - start_dt).total_seconds()
            if elapsed >= overdue_threshold:
                overdue.append(
                    {
                        "user_id": uid,
                        "entry_id": eid,
                        "elapsed_hours": round(elapsed / 3600.0, 2),
                        "started_at": entry.started_at,
                    }
                )

        return {
            "manager_id": manager_id,
            "team_member_ids": team_member_ids,
            "team_summary": team_summary,
            "member_weekly_hours": {
                uid: round(h, 2) for uid, h in member_weekly.items()
            },
            "pending_approvals": pending,
            "overdue_timers": overdue,
        }

    def get_member_detail(
        self,
        manager_id: str,
        member_id: str,
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Detailed view of a specific team member."""
        self._check_access(manager_id, [member_id])

        all_entries = self._snapshot()
        member_entries = [e for e in all_entries if e.user_id == member_id]

        # Apply optional date range filter
        if date_range:
            start = _parse_dt(date_range.get("start", ""))
            end = _parse_dt(date_range.get("end", ""))
            filtered = []
            for e in member_entries:
                dt = _parse_dt(e.started_at)
                if dt is None:
                    filtered.append(e)
                    continue
                if start and dt < start:
                    continue
                if end and dt > end:
                    continue
                filtered.append(e)
            member_entries = filtered

        reportable = self._reportable(member_entries)

        total_secs = sum(e.duration_seconds for e in reportable)
        billable_secs = sum(e.duration_seconds for e in reportable if e.billable)

        # Hours breakdown by project
        by_project: Dict[str, float] = {}
        for e in reportable:
            key = e.board_id or "_none"
            by_project[key] = by_project.get(key, 0.0) + e.duration_seconds / 3600.0

        # Approval status distribution
        status_dist: Dict[str, int] = {}
        for e in member_entries:
            key = e.status.value
            status_dist[key] = status_dist.get(key, 0) + 1

        return {
            "manager_id": manager_id,
            "member_id": member_id,
            "entries": [e.to_dict() for e in member_entries],
            "total_hours": round(total_secs / 3600.0, 2),
            "billable_hours": round(billable_secs / 3600.0, 2),
            "hours_by_project": {k: round(v, 2) for k, v in by_project.items()},
            "approval_status_distribution": status_dist,
            "date_range": date_range,
        }

    def get_utilization_report(
        self,
        team_member_ids: List[str],
        target_hours: float = 40.0,
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Per-member utilization: actual vs target hours."""
        now = datetime.now(tz=_UTC)
        if date_range is None:
            week_start = self._week_start(now)
            date_range = {
                "start": week_start.isoformat(),
                "end": now.isoformat(),
            }

        start = _parse_dt(date_range.get("start", ""))
        end = _parse_dt(date_range.get("end", ""))
        all_entries = self._snapshot()
        member_set = set(team_member_ids)

        member_secs: Dict[str, float] = {m: 0.0 for m in team_member_ids}
        for e in self._reportable(all_entries):
            if e.user_id not in member_set:
                continue
            dt = _parse_dt(e.started_at)
            if dt is None:
                member_secs[e.user_id] = (
                    member_secs.get(e.user_id, 0.0) + e.duration_seconds
                )
                continue
            if start and dt < start:
                continue
            if end and dt > end:
                continue
            member_secs[e.user_id] = (
                member_secs.get(e.user_id, 0.0) + e.duration_seconds
            )

        utilization = []
        for member_id in team_member_ids:
            actual_hours = round(member_secs.get(member_id, 0.0) / 3600.0, 2)
            utilization_pct = (
                round(actual_hours / target_hours * 100.0, 1) if target_hours else 0.0
            )
            over_under = (
                "over" if actual_hours > target_hours
                else "on_target" if actual_hours == target_hours
                else "under"
            )
            utilization.append(
                {
                    "member_id": member_id,
                    "actual_hours": actual_hours,
                    "target_hours": target_hours,
                    "utilization_percentage": utilization_pct,
                    "over_under": over_under,
                }
            )

        return {
            "utilization": utilization,
            "target_hours": target_hours,
            "date_range": date_range,
        }

    def get_team_comparison(
        self,
        team_member_ids: List[str],
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Side-by-side comparison: hours, billable %, projects, entries count."""
        now = datetime.now(tz=_UTC)
        if date_range is None:
            week_start = self._week_start(now)
            date_range = {
                "start": week_start.isoformat(),
                "end": now.isoformat(),
            }

        start = _parse_dt(date_range.get("start", ""))
        end = _parse_dt(date_range.get("end", ""))
        all_entries = self._snapshot()
        member_set = set(team_member_ids)

        # Collect per-member stats
        member_data: Dict[str, Dict[str, Any]] = {
            m: {
                "total_secs": 0,
                "billable_secs": 0,
                "entries_count": 0,
                "projects": set(),
            }
            for m in team_member_ids
        }

        for e in self._reportable(all_entries):
            if e.user_id not in member_set:
                continue
            dt = _parse_dt(e.started_at)
            if dt is not None:
                if start and dt < start:
                    continue
                if end and dt > end:
                    continue
            d = member_data[e.user_id]
            d["total_secs"] += e.duration_seconds
            if e.billable:
                d["billable_secs"] += e.duration_seconds
            d["entries_count"] += 1
            d["projects"].add(e.board_id or "_none")

        comparison = []
        for member_id in team_member_ids:
            d = member_data[member_id]
            total = d["total_secs"]
            billable = d["billable_secs"]
            billable_pct = round(billable / total * 100.0, 1) if total else 0.0
            comparison.append(
                {
                    "member_id": member_id,
                    "total_hours": round(total / 3600.0, 2),
                    "billable_percentage": billable_pct,
                    "projects_worked_on": sorted(d["projects"]),
                    "entries_count": d["entries_count"],
                }
            )

        return {
            "comparison": comparison,
            "date_range": date_range,
        }
