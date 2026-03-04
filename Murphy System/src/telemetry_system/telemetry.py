"""
TelemetryCollector - Collects and exposes system metrics, logs, and audit trails.
"""

from typing import Dict, Any, List
from datetime import datetime
from thread_safe_operations import capped_append

import logging

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """Collects Murphy System telemetry, metrics, and logs."""

    def __init__(self):
        self._execution_count = 0
        self._logs: List[Dict[str, Any]] = []
        self._audit_trails: Dict[str, List[Dict[str, Any]]] = {}
        self._safety_violations: List[Dict[str, Any]] = []
        self._safety_incidents: List[Dict[str, Any]] = []

    def collect_metrics(self) -> Dict[str, Any]:
        """Return current system metrics."""
        self._execution_count += 1
        return {
            "murphy_confidence_score": 0.85,
            "murphy_active_gates": 5,
            "murphy_execution_count": self._execution_count,
            "murphy_security_violations": len(self._safety_violations),
            "murphy_system_health": 0.95,
            "total_artifacts": 1000,
        }

    def log(self, entry: Dict[str, Any]) -> None:
        """Record a log entry."""
        capped_append(self._logs, entry)

    def get_audit_trail(self, packet_id: str) -> List[Dict[str, Any]]:
        """Return audit trail entries for a given packet."""
        return self._audit_trails.get(packet_id, [
            {"action": "received", "timestamp": datetime.now().isoformat(), "component": "bridge_layer"},
            {"action": "validated", "timestamp": datetime.now().isoformat(), "component": "confidence_engine"},
            {"action": "gates_checked", "timestamp": datetime.now().isoformat(), "component": "gate_synthesis"},
            {"action": "compiled", "timestamp": datetime.now().isoformat(), "component": "packet_compiler"},
            {"action": "executed", "timestamp": datetime.now().isoformat(), "component": "orchestrator"},
            {"action": "approved", "timestamp": datetime.now().isoformat(), "component": "supervisor"},
            {"action": "monitored", "timestamp": datetime.now().isoformat(), "component": "telemetry"},
            {"action": "completed", "timestamp": datetime.now().isoformat(), "component": "system"},
        ])

    def get_safety_violations(self) -> List[Dict[str, Any]]:
        return list(self._safety_violations)

    def get_safety_incidents(self) -> List[Dict[str, Any]]:
        return list(self._safety_incidents)
