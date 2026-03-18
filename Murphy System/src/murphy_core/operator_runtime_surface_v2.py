from __future__ import annotations

from typing import Dict

from .operator_status_runtime import ConfigurableOperatorStatusService
from .runtime_deployment_modes import RuntimeDeploymentModes
from .runtime_lineage import RuntimeLineage


class OperatorRuntimeSurfaceV2:
    """Unified runtime/operator surface including deployment modes.

    This combines live operator status, lineage, and deployment choices so UI
    and operators can see the canonical direct path and the transitional shell
    path in one place.
    """

    def __init__(
        self,
        operator_status: ConfigurableOperatorStatusService,
        lineage: RuntimeLineage | None = None,
        deployment_modes: RuntimeDeploymentModes | None = None,
    ) -> None:
        self.operator_status = operator_status
        self.lineage = lineage or RuntimeLineage()
        self.deployment_modes = deployment_modes or RuntimeDeploymentModes()

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
            "transitional_deployment": deployment_snapshot["compat_shell"],
        }

    def ui_summary(self) -> Dict[str, object]:
        operator_summary = self.operator_status.ui_summary()
        lineage_snapshot = self.lineage.to_dict()
        deployment_snapshot = self.deployment_modes.to_dict()
        layers = lineage_snapshot["layers"]
        rollback_layers = [layer["name"] for layer in layers if layer["status"] == "rollback"]
        compatibility_layers = [layer["name"] for layer in layers if layer["role"] == "compatibility"]
        return {
            **operator_summary,
            "preferred_runtime_name": lineage_snapshot["preferred"]["name"],
            "preferred_runtime_startup": lineage_snapshot["preferred"]["startup"],
            "preferred_deployment_mode": deployment_snapshot["preferred_direct"]["name"],
            "preferred_deployment_startup": deployment_snapshot["preferred_direct"]["startup"],
            "transitional_deployment_mode": deployment_snapshot["compat_shell"]["name"],
            "transitional_deployment_startup": deployment_snapshot["compat_shell"]["startup"],
            "rollback_layer_count": len(rollback_layers),
            "rollback_layers": rollback_layers,
            "compatibility_layer_count": len(compatibility_layers),
            "compatibility_layers": compatibility_layers,
        }
