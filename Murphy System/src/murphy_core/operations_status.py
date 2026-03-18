from __future__ import annotations

from typing import Dict, List

from .operator_runtime_surface_v2 import OperatorRuntimeSurfaceV2


class OperationsStatus:
    """Build operations-focused status and runbook hints from runtime truth."""

    def __init__(self, runtime_surface: OperatorRuntimeSurfaceV2) -> None:
        self.runtime_surface = runtime_surface

    def snapshot(self) -> Dict[str, object]:
        summary = self.runtime_surface.ui_summary()
        return {
            "status": "operational",
            "preferred_runtime": summary["preferred_runtime_name"],
            "preferred_startup": summary["preferred_runtime_startup"],
            "preferred_deployment_mode": summary["preferred_deployment_mode"],
            "transitional_deployment_mode": summary["transitional_deployment_mode"],
            "rollback_layers": summary["rollback_layers"],
            "compatibility_layers": summary["compatibility_layers"],
            "runbook": self.runbook(),
        }

    def runbook(self) -> List[Dict[str, str]]:
        summary = self.runtime_surface.ui_summary()
        return [
            {
                "step": "direct-core-start",
                "title": "Start direct canonical backend",
                "command": summary["preferred_deployment_startup"],
            },
            {
                "step": "compat-shell-start",
                "title": "Start transitional compatibility shell",
                "command": summary["transitional_deployment_startup"],
            },
            {
                "step": "verify-runtime",
                "title": "Verify runtime summary endpoints",
                "command": "GET /api/operator/runtime and GET /api/operator/runtime-summary",
            },
        ]
