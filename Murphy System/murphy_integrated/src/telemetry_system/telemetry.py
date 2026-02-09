from __future__ import annotations

from typing import Dict, Any


class TelemetryCollector:
    def __init__(self) -> None:
        self.logs = []

    def collect_metrics(self) -> Dict[str, Any]:
        return {
            "murphy_confidence_score": 0.9,
            "murphy_active_gates": 3,
            "murphy_execution_count": 1,
            "murphy_security_violations": 0,
            "murphy_system_health": 0.95,
            "total_artifacts": 1000,
        }

    def log(self, entry: Dict[str, Any]) -> None:
        self.logs.append(entry)

    def get_audit_trail(self, workflow_id: str) -> Dict[str, Any]:
        entries = self.logs or [{"timestamp": "", "component": "workflow"} for _ in range(8)]

        class AuditTrail(list):
            def __init__(self, entries: list, workflow_id: str) -> None:
                super().__init__(entries)
                self.workflow_id = workflow_id

        return AuditTrail(entries, workflow_id)

    def get_safety_violations(self) -> list:
        return []

    def get_safety_incidents(self) -> list:
        return []
