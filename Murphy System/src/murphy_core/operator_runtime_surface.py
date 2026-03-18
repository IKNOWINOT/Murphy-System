from __future__ import annotations

from typing import Dict

from .operator_status_runtime import ConfigurableOperatorStatusService
from .runtime_lineage import RuntimeLineage


class OperatorRuntimeSurface:
    """Combine live operator status with runtime lineage truth.

    This gives operators and UI one place to inspect:
    - active preferred runtime identity
    - provider and gate health
    - registry and system map truth
    - preferred / rollback / compatibility lineage
    """

    def __init__(
        self,
        operator_status: ConfigurableOperatorStatusService,
        lineage: RuntimeLineage | None = None,
    ) -> None:
        self.operator_status = operator_status
        self.lineage = lineage or RuntimeLineage()

    def snapshot(self) -> Dict[str, object]:
        operator_snapshot = self.operator_status.snapshot()
        lineage_snapshot = self.lineage.to_dict()
        return {
            "operator": operator_snapshot,
            "lineage": lineage_snapshot,
            "preferred_runtime": lineage_snapshot["preferred"],
        }

    def ui_summary(self) -> Dict[str, object]:
        operator_summary = self.operator_status.ui_summary()
        lineage_snapshot = self.lineage.to_dict()
        layers = lineage_snapshot["layers"]
        rollback_layers = [layer["name"] for layer in layers if layer["status"] == "rollback"]
        compatibility_layers = [layer["name"] for layer in layers if layer["role"] == "compatibility"]
        return {
            **operator_summary,
            "preferred_runtime_name": lineage_snapshot["preferred"]["name"],
            "preferred_runtime_startup": lineage_snapshot["preferred"]["startup"],
            "rollback_layer_count": len(rollback_layers),
            "rollback_layers": rollback_layers,
            "compatibility_layer_count": len(compatibility_layers),
            "compatibility_layers": compatibility_layers,
        }
