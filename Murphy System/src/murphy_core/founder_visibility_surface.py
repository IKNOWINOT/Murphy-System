from __future__ import annotations

from typing import Dict, List

from .operations_status import OperationsStatus
from .operator_runtime_surface_v8 import OperatorRuntimeSurfaceV8
from .production_inventory import ProductionInventory
from .ui_runtime_dashboard import UIRuntimeDashboard


class FounderVisibilitySurface:
    """Unified founder/admin visibility payload.

    This combines runtime truth, preserved-family inventory, UI dashboard data,
    and operations guidance into one machine-readable control surface.
    """

    def __init__(
        self,
        runtime_surface: OperatorRuntimeSurfaceV8,
        production_inventory: ProductionInventory,
        ui_dashboard: UIRuntimeDashboard,
        ops_status: OperationsStatus,
    ) -> None:
        self.runtime_surface = runtime_surface
        self.production_inventory = production_inventory
        self.ui_dashboard = ui_dashboard
        self.ops_status = ops_status

    def snapshot(self) -> Dict[str, object]:
        inventory = self.production_inventory.to_dict()
        dashboard = self.ui_dashboard.build()
        ops = self.ops_status.snapshot()
        return {
            "runtime": self.runtime_surface.snapshot(),
            "runtime_summary": self.runtime_surface.ui_summary(),
            "inventory": inventory,
            "inventory_summary": {
                "runtime_order": inventory["runtime_order"],
                "family_count": inventory["validation"]["family_count"],
                "by_layer": inventory["by_layer"],
                "validation": inventory["validation"],
            },
            "recent_execution_outcomes": ops["recent_execution_outcomes"],
            "ui_dashboard": dashboard,
            "ops": ops,
            "ops_runbook": self.ops_status.runbook(),
        }

    def summary(self) -> Dict[str, object]:
        runtime_summary = self.runtime_surface.ui_summary()
        inventory = self.production_inventory.to_dict()
        dashboard = self.ui_dashboard.build()
        ops = self.ops_status.snapshot()
        recent_outcomes = ops["recent_execution_outcomes"]
        return {
            "preferred_factory": runtime_summary["preferred_factory"],
            "preferred_runtime_name": runtime_summary["preferred_runtime_name"],
            "preferred_deployment_mode": runtime_summary["preferred_deployment_mode"],
            "transitional_deployment_mode": runtime_summary["transitional_deployment_mode"],
            "family_count": inventory["validation"]["family_count"],
            "inventory_ok": inventory["validation"]["ok"],
            "rollback_layer_count": runtime_summary["rollback_layer_count"],
            "compatibility_layer_count": runtime_summary["compatibility_layer_count"],
            "dashboard_card_count": len(dashboard["cards"]),
            "dashboard_action_count": len(dashboard["actions"]),
            "ops_status": ops["status"],
            "runbook_step_count": len(ops["runbook"]),
            "recent_execution_total": recent_outcomes["total"],
            "recent_approval_pending": recent_outcomes["approval_pending"],
            "recent_fallback_engaged": recent_outcomes["fallback_engaged"],
            "recent_blocked": recent_outcomes["blocked"],
            "latest_execution_status": recent_outcomes["latest_status"],
        }

    def layer_index(self) -> Dict[str, List[str]]:
        return self.production_inventory.grouped_by_layer()
