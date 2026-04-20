# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: FDD-002
"""Rule-based Fault Detection & Diagnostics for HVAC and BAS equipment."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class FaultSeverity(Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FaultStatus(Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class FaultRule:
    rule_id: str
    name: str
    description: str
    severity: FaultSeverity
    condition: Callable[[Dict], bool]
    message_template: str = ""
    equipment_type: str = "generic"


@dataclass
class Fault:
    fault_id: str
    rule_id: str
    equipment_id: str
    severity: FaultSeverity
    message: str
    status: FaultStatus = FaultStatus.ACTIVE
    detected_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    context: Dict = field(default_factory=dict)


# ── built-in fault rules ────────────────────────────────────────

def _simultaneous_heat_cool(data: Dict) -> bool:
    """AHU heating and cooling both active simultaneously."""
    return bool(data.get("heating_active") and data.get("cooling_active"))


def _stuck_damper(data: Dict) -> bool:
    """Damper position unchanged despite command changes."""
    cmd = data.get("damper_command")
    pos = data.get("damper_position")
    if cmd is None or pos is None:
        return False
    return abs(cmd - pos) > 20  # >20 % deviation


def _sensor_freeze(data: Dict) -> bool:
    """Sensor value unchanged for extended period."""
    values = data.get("recent_values", [])
    if len(values) < 5:
        return False
    return len(set(values)) == 1  # all identical


def _sensor_drift(data: Dict) -> bool:
    """Sensor reading drifts beyond plausible range."""
    value = data.get("value")
    low = data.get("plausible_low", -1e9)
    high = data.get("plausible_high", 1e9)
    if value is None:
        return False
    return value < low or value > high


def _chiller_degradation(data: Dict) -> bool:
    """Chiller COP below threshold indicates performance degradation."""
    cop = data.get("cop")
    threshold = data.get("cop_threshold", 3.0)
    if cop is None:
        return False
    return cop < threshold


BUILTIN_RULES: List[FaultRule] = [
    FaultRule(
        rule_id="FDD-AHU-001",
        name="Simultaneous Heating and Cooling",
        description="AHU heating and cooling valves both active",
        severity=FaultSeverity.HIGH,
        condition=_simultaneous_heat_cool,
        message_template="AHU {equipment_id}: simultaneous heating and cooling detected",
        equipment_type="ahu",
    ),
    FaultRule(
        rule_id="FDD-AHU-002",
        name="Stuck Damper",
        description="Damper position does not follow command",
        severity=FaultSeverity.MEDIUM,
        condition=_stuck_damper,
        message_template="AHU {equipment_id}: damper stuck — cmd={damper_command}%, pos={damper_position}%",
        equipment_type="ahu",
    ),
    FaultRule(
        rule_id="FDD-SENSOR-001",
        name="Sensor Freeze",
        description="Sensor output unchanged for extended period",
        severity=FaultSeverity.MEDIUM,
        condition=_sensor_freeze,
        message_template="Sensor {equipment_id}: frozen at {value}",
        equipment_type="sensor",
    ),
    FaultRule(
        rule_id="FDD-SENSOR-002",
        name="Sensor Drift",
        description="Sensor reading outside plausible range",
        severity=FaultSeverity.HIGH,
        condition=_sensor_drift,
        message_template="Sensor {equipment_id}: value {value} outside range [{plausible_low},{plausible_high}]",
        equipment_type="sensor",
    ),
    FaultRule(
        rule_id="FDD-CHILLER-001",
        name="Chiller Performance Degradation",
        description="Chiller COP below expected baseline",
        severity=FaultSeverity.HIGH,
        condition=_chiller_degradation,
        message_template="Chiller {equipment_id}: COP={cop} below threshold {cop_threshold}",
        equipment_type="chiller",
    ),
]


class RuleBasedFDD:
    """Murphy-native rule-based fault detection engine."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rules: Dict[str, FaultRule] = {r.rule_id: r for r in BUILTIN_RULES}
        self._active_faults: Dict[str, Fault] = {}
        self._fault_history: list = []

    # ── rule management ──────────────────────────────────────────

    def register_rule(self, rule: FaultRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule

    def list_rules(self) -> List[FaultRule]:
        with self._lock:
            return list(self._rules.values())

    # ── evaluation ───────────────────────────────────────────────

    def evaluate(self, equipment_id: str, data: Dict) -> List[Fault]:
        """Run all applicable rules against data snapshot, return new faults."""
        new_faults: List[Fault] = []
        with self._lock:
            for rule in self._rules.values():
                try:
                    if rule.condition(data):
                        fault_key = f"{rule.rule_id}:{equipment_id}"
                        if fault_key not in self._active_faults:
                            msg = rule.message_template.format(
                                equipment_id=equipment_id, **data,
                            ) if rule.message_template else rule.description
                            fault = Fault(
                                fault_id=f"F-{uuid.uuid4().hex[:8]}",
                                rule_id=rule.rule_id,
                                equipment_id=equipment_id,
                                severity=rule.severity,
                                message=msg,
                                context=dict(data),
                            )
                            self._active_faults[fault_key] = fault
                            capped_append(self._fault_history, fault)
                            new_faults.append(fault)
                    else:
                        # auto-resolve if condition clears
                        fault_key = f"{rule.rule_id}:{equipment_id}"
                        if fault_key in self._active_faults:
                            f = self._active_faults.pop(fault_key)
                            f.status = FaultStatus.RESOLVED
                            f.resolved_at = time.time()
                except Exception:
                    logger.debug("Suppressed exception in fdd_rule_engine")
        return new_faults

    # ── queries ──────────────────────────────────────────────────

    def get_active_faults(
        self, equipment_id: Optional[str] = None, severity: Optional[FaultSeverity] = None,
    ) -> List[Fault]:
        with self._lock:
            faults = list(self._active_faults.values())
        if equipment_id:
            faults = [f for f in faults if f.equipment_id == equipment_id]
        if severity:
            faults = [f for f in faults if f.severity == severity]
        return faults

    def acknowledge_fault(self, fault_id: str) -> bool:
        with self._lock:
            for f in self._active_faults.values():
                if f.fault_id == fault_id:
                    f.status = FaultStatus.ACKNOWLEDGED
                    return True
        return False

    def get_fault_history(self, limit: int = 100) -> List[Fault]:
        with self._lock:
            return list(self._fault_history[-limit:])
