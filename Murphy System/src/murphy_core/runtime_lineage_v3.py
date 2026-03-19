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


class RuntimeLineageV3:
    """Runtime lineage with canonical execution as the preferred default path."""

    def __init__(self) -> None:
        self.layers: List[RuntimeLayer] = [
            RuntimeLayer(
                name="legacy_runtime",
                app_factory="src/runtime/app.py",
                bridge="n/a",
                startup="legacy deployment path",
                status="legacy_until_replaced",
                role="compatibility",
                notes=["Large monolithic runtime; compatibility shell target only"],
            ),
            RuntimeLayer(
                name="murphy_core_v1",
                app_factory="src/murphy_core/app.py",
                bridge="src/runtime/murphy_core_bridge.py",
                startup="src/runtime/main_core.py",
                status="rollback",
                role="compatibility",
                notes=["First typed core path; superseded"],
            ),
            RuntimeLayer(
                name="murphy_core_v2",
                app_factory="src/murphy_core/app_v2.py",
                bridge="src/runtime/murphy_core_bridge_v2.py",
                startup="src/runtime/main_core_v2.py",
                status="rollback",
                role="compatibility",
                notes=["Service-wired core path; superseded"],
            ),
            RuntimeLayer(
                name="murphy_core_v3_runtime_correct",
                app_factory="src/murphy_core/app_v3_runtime.py",
                bridge="src/runtime/murphy_core_bridge_v3_runtime_correct.py",
                startup="src/runtime/main_core_v3_runtime_correct.py",
                status="rollback",
                role="compatibility",
                notes=["Runtime-correct fallback core path"],
            ),
            RuntimeLayer(
                name="legacy_compat_shell",
                app_factory="src/runtime/legacy_runtime_compat_shell.py",
                bridge="n/a",
                startup="src/runtime/main_legacy_compat_shell.py",
                status="transitional",
                role="compatibility",
                notes=["Legacy route/UI coverage with core-owned chat/execute"],
            ),
            RuntimeLayer(
                name="murphy_core_v3_founder_execution_surface_v3",
                app_factory="src/murphy_core/app_v3_founder_execution_surface_v3.py",
                bridge="src/runtime/murphy_core_bridge_v3_founder_execution_surface_v3.py",
                startup="src/runtime/main_core_v3_founder_execution_surface_v3.py",
                status="overlay",
                role="privileged_visibility",
                notes=["Founder/admin visibility overlay retained on the same runtime stack"],
            ),
            RuntimeLayer(
                name="murphy_core_v3_canonical_execution_surface",
                app_factory="src/murphy_core/app_v3_canonical_execution_surface.py",
                bridge="src/runtime/murphy_core_bridge_v3_canonical_execution_surface.py",
                startup="src/runtime/main_core_v3_canonical_execution_surface.py",
                status="preferred",
                role="canonical",
                notes=["Current preferred default runtime for users and automations with founder overlay available"],
            ),
        ]

    def preferred(self) -> RuntimeLayer:
        return next(layer for layer in self.layers if layer.status == "preferred")

    def to_dict(self) -> Dict[str, object]:
        return {
            "preferred": self.preferred().to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
        }
