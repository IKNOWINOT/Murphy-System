# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: FDD-004
"""Alarm management — deduplication, prioritisation, maintenance suppression."""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class AlarmPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    INFO = 5


class AlarmManager:
    """Deduplicate, prioritise, and suppress alarms."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_alarms: Dict[str, Dict] = {}  # alarm_key → alarm dict
        self._alarm_history: list = []
        self._maintenance_windows: Dict[str, Dict] = {}  # equipment_id → {start, end}
        self._suppressed_equipment: Set[str] = set()

    # ── alarm ingestion ──────────────────────────────────────────

    def raise_alarm(
        self,
        alarm_key: str,
        equipment_id: str,
        message: str,
        priority: AlarmPriority = AlarmPriority.MEDIUM,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Raise or deduplicate an alarm."""
        with self._lock:
            # suppression check
            if equipment_id in self._suppressed_equipment:
                return {"status": "suppressed", "alarm_key": alarm_key}
            if self._is_in_maintenance(equipment_id):
                return {"status": "suppressed_maintenance", "alarm_key": alarm_key}

            if alarm_key in self._active_alarms:
                # dedup: update count
                existing = self._active_alarms[alarm_key]
                existing["occurrence_count"] = existing.get("occurrence_count", 1) + 1
                existing["last_seen"] = time.time()
                return {"status": "deduplicated", "alarm_key": alarm_key, "count": existing["occurrence_count"]}

            alarm = {
                "alarm_key": alarm_key,
                "equipment_id": equipment_id,
                "message": message,
                "priority": priority.value,
                "priority_name": priority.name,
                "raised_at": time.time(),
                "last_seen": time.time(),
                "occurrence_count": 1,
                "context": context or {},
            }
            self._active_alarms[alarm_key] = alarm
            capped_append(self._alarm_history, alarm)
            return {"status": "raised", "alarm_key": alarm_key}

    def clear_alarm(self, alarm_key: str) -> bool:
        with self._lock:
            return self._active_alarms.pop(alarm_key, None) is not None

    # ── queries ──────────────────────────────────────────────────

    def get_active_alarms(
        self,
        equipment_id: Optional[str] = None,
        max_priority: Optional[AlarmPriority] = None,
    ) -> List[Dict]:
        with self._lock:
            alarms = list(self._active_alarms.values())
        if equipment_id:
            alarms = [a for a in alarms if a["equipment_id"] == equipment_id]
        if max_priority:
            alarms = [a for a in alarms if a["priority"] <= max_priority.value]
        # sort by priority (1=critical first)
        alarms.sort(key=lambda a: a["priority"])
        return alarms

    def get_alarm_history(self, limit: int = 200) -> List[Dict]:
        with self._lock:
            return list(self._alarm_history[-limit:])

    # ── maintenance suppression ──────────────────────────────────

    def set_maintenance_window(
        self, equipment_id: str, start_time: float, end_time: float,
    ) -> None:
        with self._lock:
            self._maintenance_windows[equipment_id] = {
                "start": start_time, "end": end_time,
            }

    def suppress_equipment(self, equipment_id: str) -> None:
        with self._lock:
            self._suppressed_equipment.add(equipment_id)

    def unsuppress_equipment(self, equipment_id: str) -> None:
        with self._lock:
            self._suppressed_equipment.discard(equipment_id)

    def _is_in_maintenance(self, equipment_id: str) -> bool:
        window = self._maintenance_windows.get(equipment_id)
        if window is None:
            return False
        now = time.time()
        return window["start"] <= now <= window["end"]
