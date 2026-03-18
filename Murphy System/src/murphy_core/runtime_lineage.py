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


class RuntimeLineage:
    """Describe Murphy Core runtime evolution and current preferred path."""

    def __init__(self) -> None:
        self.layers: List[RuntimeLayer] = [
            RuntimeLayer(
                name="legacy_runtime",
                app_factory="src/runtime/app.py",
                bridge="n/a",
                startup="legacy deployment path",
                status="legacy_until_replaced",
                role="compatibility",
                notes=["Large monolithic runtime; not preferred for new orchestration"],
            ),
            RuntimeLayer(
                name="murphy_core_v1",
                app_factory="src/murphy_core/app.py",
                bridge="src/runtime/murphy_core_bridge.py",
                startup="src/runtime/main_core.py",
                status="rollback",
                role="compatibility",
                notes=["First typed core path; superseded by later versions"],
            ),
            RuntimeLayer(
                name="murphy_core_v2",
                app_factory="src/murphy_core/app_v2.py",
                bridge="src/runtime/murphy_core_bridge_v2.py",
                startup="src/runtime/main_core_v2.py",
                status="rollback",
                role="compatibility",
                notes=["Service-wired core path; superseded by operator-aware versions"],
            ),
            RuntimeLayer(
                name="murphy_core_v3",
                app_factory="src/murphy_core/app_v3.py",
                bridge="src/runtime/murphy_core_bridge_v3.py",
                startup="src/runtime/main_core_v3.py",
                status="rollback",
                role="compatibility",
                notes=["Operator-aware core path; superseded by runtime-correct variant"],
            ),
            RuntimeLayer(
                name="murphy_core_v3_runtime_correct",
                app_factory="src/murphy_core/app_v3_runtime.py",
                bridge="src/runtime/murphy_core_bridge_v3_runtime_correct.py",
                startup="src/runtime/main_core_v3_runtime_correct.py",
                status="preferred",
                role="canonical",
                notes=["Current preferred backend path with truthful operator runtime identity"],
            ),
        ]

    def preferred(self) -> RuntimeLayer:
        return next(layer for layer in self.layers if layer.status == "preferred")

    def to_dict(self) -> Dict[str, object]:
        return {
            "preferred": self.preferred().to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
        }
