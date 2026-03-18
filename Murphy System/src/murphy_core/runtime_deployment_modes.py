from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DeploymentMode:
    name: str
    app_target: str
    startup: str
    category: str
    preferred_for: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "app_target": self.app_target,
            "startup": self.startup,
            "category": self.category,
            "preferred_for": list(self.preferred_for),
            "notes": list(self.notes),
        }


class RuntimeDeploymentModes:
    """Machine-readable deployment choices for Murphy runtime adoption."""

    def __init__(self) -> None:
        self.modes: List[DeploymentMode] = [
            DeploymentMode(
                name="direct_core_runtime_correct",
                app_target="src/murphy_core/app_v3_runtime.py",
                startup="src/runtime/main_core_v3_runtime_correct.py",
                category="canonical",
                preferred_for=[
                    "canonical_backend_validation",
                    "operator_ui",
                    "core_first_deployments",
                ],
                notes=[
                    "Preferred direct Murphy Core runtime-correct path",
                    "Does not depend on broad legacy route coverage",
                ],
            ),
            DeploymentMode(
                name="legacy_compat_shell",
                app_target="src/runtime/legacy_runtime_compat_shell.py",
                startup="src/runtime/main_legacy_compat_shell.py",
                category="transitional",
                preferred_for=[
                    "legacy_ui_coverage",
                    "incremental_migration",
                    "core_owned_chat_execute_with_legacy_passthrough",
                ],
                notes=[
                    "Delegates /api/chat and /api/execute into Murphy Core",
                    "Mounts legacy runtime for all other routes",
                ],
            ),
        ]

    def preferred_direct(self) -> DeploymentMode:
        return next(mode for mode in self.modes if mode.name == "direct_core_runtime_correct")

    def compat_shell(self) -> DeploymentMode:
        return next(mode for mode in self.modes if mode.name == "legacy_compat_shell")

    def to_dict(self) -> Dict[str, object]:
        return {
            "preferred_direct": self.preferred_direct().to_dict(),
            "compat_shell": self.compat_shell().to_dict(),
            "modes": [mode.to_dict() for mode in self.modes],
        }
