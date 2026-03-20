from __future__ import annotations

from typing import Dict

from .operator_status_runtime import ConfigurableOperatorStatusService
from .runtime_deployment_modes_v7 import RuntimeDeploymentModesV7
from .runtime_lineage_v7 import RuntimeLineageV7


class OperatorRuntimeSurfaceV8:
    """Unified runtime/operator surface aligned to canonical execution v5 defaults."""

    def __init__(
        self,
        operator_status: ConfigurableOperatorStatusService,
        lineage: RuntimeLineageV7 | None = None,
        deployment_modes: RuntimeDeploymentModesV7 | None = None,
    ) -> None:
        self.operator_status = operator_status
        self.lineage = lineage or RuntimeLineageV7()
        self.deployment_modes = deployment_modes or RuntimeDeploymentModesV7()

    def snapshot(self) -> Dict[str, object]:
        operator_snapshot = self.operator_status.snapshot()
        lineage_snapshot = self.lineage.to_dict()
        deployment_snapshot = self.deployment_modes.to_dict()
        return {
            "operator": operator_snapshot,
            "lineage": lineage_snapshot,
            "deployment_modes": deployment_snapshot,
            "preferred_runtime": lineage_snapshot["preferred"],
            "preferred_deployment": deployment_snapshot["preferred_direct"],
            "founder_overlay": deployment_snapshot["founder_overlay"],
            "transitional_deployment": deployment_snapshot["compat_shell"],
        }

    def ui_summary(self) -> Dict[str, object]:
        operator_summary = self.operator_status.ui_summary()
        lineage_snapshot = self.lineage.to_dict()
        deployment_snapshot = self.deployment_modes.to_dict()
        layers = lineage_snapshot["layers"]
        rollback_layers = [layer["name"] for layer in layers if layer["status"] == "rollback"]
        compatibility_layers = [layer["name"] for layer in layers if layer["role"] == "compatibility"]
        overlay_layers = [layer["name"] for layer in layers if layer["role"] == "privileged_visibility"]
        return {
            **operator_summary,
            "preferred_runtime_name": lineage_snapshot["preferred"]["name"],
            "preferred_runtime_startup": lineage_snapshot["preferred"]["startup"],
            "preferred_deployment_mode": deployment_snapshot["preferred_direct"]["name"],
            "preferred_deployment_startup": deployment_snapshot["preferred_direct"]["startup"],
            "founder_overlay_mode": deployment_snapshot["founder_overlay"]["name"],
            "founder_overlay_startup": deployment_snapshot["founder_overlay"]["startup"],
            "transitional_deployment_mode": deployment_snapshot["compat_shell"]["name"],
            "transitional_deployment_startup": deployment_snapshot["compat_shell"]["startup"],
            "rollback_layer_count": len(rollback_layers),
            "rollback_layers": rollback_layers,
            "compatibility_layer_count": len(compatibility_layers),
            "compatibility_layers": compatibility_layers,
            "overlay_layer_count": len(overlay_layers),
            "overlay_layers": overlay_layers,
        }
