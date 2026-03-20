from __future__ import annotations

from typing import Dict, List

from .founder_privilege_overlay import FounderPrivilegeOverlay
from .operations_status import OperationsStatus
from .operator_runtime_surface_v8 import OperatorRuntimeSurfaceV8
from .production_inventory import ProductionInventory
from .ui_runtime_dashboard import UIRuntimeDashboard


class FounderVisibilitySurface:
    """Unified founder/admin visibility payload.

    This combines runtime truth, preserved-family inventory, UI dashboard data,
    operations guidance, and founder privilege policy into one machine-readable
    control surface.
    """

    def __init__(
        self,
        runtime_surface: OperatorRuntimeSurfaceV8,
        production_inventory: ProductionInventory,
        ui_dashboard: UIRuntimeDashboard,
        ops_status: OperationsStatus,
        privilege_overlay: FounderPrivilegeOverlay | None = None,
    ) -> None:
        self.runtime_surface = runtime_surface
        self.production_inventory = production_inventory
        self.ui_dashboard = ui_dashboard
        self.ops_status = ops_status
        self.privilege_overlay = privilege_overlay or FounderPrivilegeOverlay()

    def snapshot(self) -> Dict[str, object]:
        inventory = self.production_inventory.to_dict()
        dashboard = self.ui_dashboard.build()
        ops = self.ops_status.snapshot()
        privilege_summary = self.privilege_overlay.summary()
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
            "founder_privileges": {
                "summary": privilege_summary,
                "workstation": self.privilege_overlay.workstation_policy(),
                "automation": self.privilege_overlay.automation_policy(),
                "account_policy_matrix": self.privilege_overlay.account_policy_matrix(),
            },
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
        privilege_summary = self.privilege_overlay.summary()
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
            "latest_hitl_scope": recent_outcomes["latest_hitl_scope"],
            "founder_hitl_pending": recent_outcomes["hitl_scope_counts"]["founder"],
            "organization_hitl_pending": recent_outcomes["hitl_scope_counts"]["organization"],
            "generic_hitl_pending": recent_outcomes["hitl_scope_counts"]["generic"],
            "founder_overlay_enabled": privilege_summary["founder_overlay_enabled"],
            "founder_direct_platform_changes": privilege_summary["direct_platform_changes"],
            "founder_direct_code_additions": privilege_summary["direct_code_additions"],
            "founder_full_automation_features": privilege_summary["full_automation_features"],
            "standard_accounts_constrained": privilege_summary["standard_accounts_constrained"],
        }

    def layer_index(self) -> Dict[str, List[str]]:
        return self.production_inventory.grouped_by_layer()
