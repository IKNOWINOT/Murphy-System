from __future__ import annotations

from typing import Dict, List

from .operator_runtime_surface_v2 import OperatorRuntimeSurfaceV2


class UIRuntimeDashboard:
    """Build frontend-friendly runtime dashboard data from the unified surface."""

    def __init__(self, runtime_surface: OperatorRuntimeSurfaceV2) -> None:
        self.runtime_surface = runtime_surface

    def build(self) -> Dict[str, object]:
        snapshot = self.runtime_surface.snapshot()
        summary = self.runtime_surface.ui_summary()
        preferred_runtime = snapshot["preferred_runtime"]
        preferred_deployment = snapshot["preferred_deployment"]
        transitional_deployment = snapshot["transitional_deployment"]

        cards: List[Dict[str, object]] = [
            {
                "id": "preferred-runtime",
                "title": "Preferred Runtime",
                "value": preferred_runtime["name"],
                "detail": preferred_runtime["startup"],
            },
            {
                "id": "preferred-deployment",
                "title": "Preferred Deployment",
                "value": preferred_deployment["name"],
                "detail": preferred_deployment["startup"],
            },
            {
                "id": "transitional-deployment",
                "title": "Transitional Deployment",
                "value": transitional_deployment["name"],
                "detail": transitional_deployment["startup"],
            },
            {
                "id": "provider",
                "title": "Preferred Provider",
                "value": summary["preferred_provider"],
                "detail": f"providers={summary['provider_count']}",
            },
        ]

        return {
            "cards": cards,
            "summary": summary,
            "actions": [
                {
                    "id": "boot-direct-core",
                    "label": "Boot Direct Core",
                    "target": preferred_deployment["startup"],
                },
                {
                    "id": "boot-compat-shell",
                    "label": "Boot Compat Shell",
                    "target": transitional_deployment["startup"],
                },
            ],
            "tables": {
                "rollback_layers": summary["rollback_layers"],
                "compatibility_layers": summary["compatibility_layers"],
            },
        }
