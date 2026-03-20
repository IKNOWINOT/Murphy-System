from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RuntimeLayer:
    name: str
    app_factory: str
    bridge: str
    startup: str
    status: str
    role: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "app_factory": self.app_factory,
            "bridge": self.bridge,
            "startup": self.startup,
            "status": self.status,
            "role": self.role,
            "notes": list(self.notes),
        }


class RuntimeLineageV7:
    """Runtime lineage with canonical execution v5 as the preferred default path."""

    def __init__(self) -> None:
        self.layers: List[RuntimeLayer] = [
            RuntimeLayer("legacy_runtime", "src/runtime/app.py", "n/a", "legacy deployment path", "legacy_until_replaced", "compatibility", ["Large monolithic runtime; compatibility shell target only"]),
            RuntimeLayer("murphy_core_v1", "src/murphy_core/app.py", "src/runtime/murphy_core_bridge.py", "src/runtime/main_core.py", "rollback", "compatibility", ["First typed core path; superseded"]),
            RuntimeLayer("murphy_core_v2", "src/murphy_core/app_v2.py", "src/runtime/murphy_core_bridge_v2.py", "src/runtime/main_core_v2.py", "rollback", "compatibility", ["Service-wired core path; superseded"]),
            RuntimeLayer("murphy_core_v3_runtime_correct", "src/murphy_core/app_v3_runtime.py", "src/runtime/murphy_core_bridge_v3_runtime_correct.py", "src/runtime/main_core_v3_runtime_correct.py", "rollback", "compatibility", ["Runtime-correct fallback core path"]),
            RuntimeLayer("legacy_compat_shell", "src/runtime/legacy_runtime_compat_shell.py", "n/a", "src/runtime/main_legacy_compat_shell.py", "transitional", "compatibility", ["Legacy route/UI coverage with core-owned chat/execute"]),
            RuntimeLayer("murphy_core_v3_founder_execution_surface_v3", "src/murphy_core/app_v3_founder_execution_surface_v3.py", "src/runtime/murphy_core_bridge_v3_founder_execution_surface_v3.py", "src/runtime/main_core_v3_founder_execution_surface_v3.py", "overlay", "privileged_visibility", ["Founder/admin visibility overlay retained on the same runtime stack"]),
            RuntimeLayer("murphy_core_v3_canonical_execution_surface", "src/murphy_core/app_v3_canonical_execution_surface.py", "src/runtime/murphy_core_bridge_v3_canonical_execution_surface.py", "src/runtime/main_core_v3_canonical_execution_surface.py", "rollback", "compatibility", ["Canonical execution correction step superseded"]),
            RuntimeLayer("murphy_core_v3_canonical_execution_surface_v2", "src/murphy_core/app_v3_canonical_execution_surface_v2.py", "src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v2.py", "src/runtime/main_core_v3_canonical_execution_surface_v2.py", "rollback", "compatibility", ["Canonical execution v2 superseded"]),
            RuntimeLayer("murphy_core_v3_canonical_execution_surface_v3", "src/murphy_core/app_v3_canonical_execution_surface_v3.py", "src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v3.py", "src/runtime/main_core_v3_canonical_execution_surface_v3.py", "rollback", "compatibility", ["Canonical execution v3 superseded"]),
            RuntimeLayer("murphy_core_v3_canonical_execution_surface_v4", "src/murphy_core/app_v3_canonical_execution_surface_v4.py", "src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v4.py", "src/runtime/main_core_v3_canonical_execution_surface_v4.py", "rollback", "compatibility", ["Canonical execution v4 retained as rollback path"]),
            RuntimeLayer("murphy_core_v3_canonical_execution_surface_v5", "src/murphy_core/app_v3_canonical_execution_surface_v5.py", "src/runtime/murphy_core_bridge_v3_canonical_execution_surface_v5.py", "src/runtime/main_core_v3_canonical_execution_surface_v5.py", "preferred", "canonical", ["Current preferred default runtime for users and automations with founder visibility as a privileged overlay", "Aligned to runtime truth v7"]),
        ]

    def preferred(self) -> RuntimeLayer:
        return next(layer for layer in self.layers if layer.status == "preferred")

    def to_dict(self) -> Dict[str, object]:
        return {"preferred": self.preferred().to_dict(), "layers": [layer.to_dict() for layer in self.layers]}
