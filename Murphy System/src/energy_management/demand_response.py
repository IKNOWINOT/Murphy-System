# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: EMS-003
"""Native demand response — load-shedding policy engine with OpenADR integration."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class LoadPriority(Enum):
    """Load shedding priority — CRITICAL loads are never shed."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DISCRETIONARY = "discretionary"


class ShedStatus(Enum):
    NORMAL = "normal"
    SHED_REQUESTED = "shed_requested"
    SHEDDING = "shedding"
    RESTORING = "restoring"
    VERIFIED = "verified"


@dataclass
class LoadDefinition:
    load_id: str
    name: str
    zone_id: str
    priority: LoadPriority
    rated_kw: float
    min_shed_duration_minutes: int = 15
    is_sheddable: bool = True


@dataclass
class DREvent:
    event_id: str
    signal_level: str  # NORMAL / MODERATE / HIGH / SPECIAL / CRITICAL
    target_reduction_kw: float
    start_time: float
    duration_minutes: int
    status: str = "pending"
    shed_plan: List[Dict] = field(default_factory=list)
    actual_reduction_kw: float = 0.0


class DemandResponseEngine:
    """Priority-ranked load shedding with DR event lifecycle management."""

    _SHED_ORDER = [
        LoadPriority.DISCRETIONARY,
        LoadPriority.LOW,
        LoadPriority.MEDIUM,
        LoadPriority.HIGH,
    ]  # CRITICAL is never shed

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loads: Dict[str, LoadDefinition] = {}
        self._events: Dict[str, DREvent] = {}
        self._shed_state: Dict[str, ShedStatus] = {}  # load_id → status
        self._audit_log: list = []

    # ── load management ──────────────────────────────────────────

    def register_load(self, load: LoadDefinition) -> None:
        with self._lock:
            self._loads[load.load_id] = load
            self._shed_state[load.load_id] = ShedStatus.NORMAL

    def list_loads(self) -> List[LoadDefinition]:
        with self._lock:
            return list(self._loads.values())

    # ── DR event lifecycle ───────────────────────────────────────

    def receive_dr_event(self, event: Dict) -> Dict:
        """Ingest a DR event (e.g. from OpenADR VEN or manual trigger)."""
        with self._lock:
            event_id = event.get("event_id", f"dr-{uuid.uuid4().hex[:8]}")
            dr = DREvent(
                event_id=event_id,
                signal_level=event.get("signal_level", "HIGH"),
                target_reduction_kw=float(event.get("target_reduction_kw", 0)),
                start_time=event.get("start_time", time.time()),
                duration_minutes=int(event.get("duration_minutes", 60)),
                status="pending",
            )
            self._events[event_id] = dr
            capped_append(self._audit_log, {
                "action": "event_received", "event_id": event_id,
                "ts": time.time(),
            })
            return {"event_id": event_id, "status": "pending"}

    def get_active_events(self) -> List[Dict]:
        with self._lock:
            return [
                {
                    "event_id": e.event_id,
                    "signal_level": e.signal_level,
                    "target_reduction_kw": e.target_reduction_kw,
                    "status": e.status,
                    "actual_reduction_kw": e.actual_reduction_kw,
                }
                for e in self._events.values()
                if e.status in ("pending", "shedding")
            ]

    # ── shed planning & execution ────────────────────────────────

    def compute_shed_plan(self, target_reduction_kw: float) -> List[Dict]:
        """Build priority-ordered shed list to meet target kW reduction."""
        with self._lock:
            sheddable = [
                ld for ld in self._loads.values()
                if ld.is_sheddable and ld.priority != LoadPriority.CRITICAL
            ]
        # sort by shed order index (discretionary first, high last)
        order_map = {p: i for i, p in enumerate(self._SHED_ORDER)}
        sheddable.sort(key=lambda ld: order_map.get(ld.priority, 99))

        plan: List[Dict] = []
        cumulative = 0.0
        for ld in sheddable:
            if cumulative >= target_reduction_kw:
                break
            plan.append({
                "load_id": ld.load_id,
                "name": ld.name,
                "rated_kw": ld.rated_kw,
                "priority": ld.priority.value,
            })
            cumulative += ld.rated_kw
        return plan

    def execute_shed(self, shed_plan: List[Dict], event_id: Optional[str] = None) -> Dict:
        """Mark loads as shedding per plan."""
        with self._lock:
            total_shed = 0.0
            for item in shed_plan:
                lid = item["load_id"]
                if lid in self._shed_state:
                    self._shed_state[lid] = ShedStatus.SHEDDING
                    total_shed += item.get("rated_kw", 0)
            if event_id and event_id in self._events:
                evt = self._events[event_id]
                evt.status = "shedding"
                evt.shed_plan = shed_plan
                evt.actual_reduction_kw = total_shed
            capped_append(self._audit_log, {
                "action": "shed_executed", "event_id": event_id,
                "total_shed_kw": total_shed, "ts": time.time(),
            })
            return {"total_shed_kw": total_shed, "loads_shed": len(shed_plan)}

    def restore_loads(self, event_id: str) -> Dict:
        """Restore loads in reverse priority order (high-priority first)."""
        with self._lock:
            evt = self._events.get(event_id)
            if evt is None:
                return {"error": f"Event {event_id} not found"}
            restored = 0
            for item in reversed(evt.shed_plan):
                lid = item["load_id"]
                if lid in self._shed_state:
                    self._shed_state[lid] = ShedStatus.NORMAL
                    restored += 1
            evt.status = "completed"
            capped_append(self._audit_log, {
                "action": "loads_restored", "event_id": event_id,
                "restored_count": restored, "ts": time.time(),
            })
            return {"event_id": event_id, "restored_count": restored}

    def verify_reduction(
        self,
        meter_reading_before: float,
        meter_reading_after: float,
        target_kw: float,
    ) -> Dict:
        """Check actual reduction against target using meter rebound."""
        actual = meter_reading_before - meter_reading_after
        return {
            "verified": actual >= target_kw * 0.8,  # 80 % threshold
            "actual_reduction_kw": round(actual, 2),
            "target_kw": target_kw,
            "pct_achieved": round((actual / target_kw * 100) if target_kw else 0, 1),
        }

    def get_shed_status(self) -> Dict:
        with self._lock:
            per_load = {
                lid: st.value for lid, st in self._shed_state.items()
            }
            any_shedding = any(
                s == ShedStatus.SHEDDING for s in self._shed_state.values()
            )
            return {
                "overall": "shedding" if any_shedding else "normal",
                "per_load": per_load,
            }

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            return list(self._audit_log[-limit:])
