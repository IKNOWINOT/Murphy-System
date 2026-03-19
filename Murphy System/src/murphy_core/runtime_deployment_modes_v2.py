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


class RuntimeDeploymentModesV2:
    """Deployment choices with founder execution surface as canonical mode."""

    def __init__(self) -> None:
        self.modes: List[DeploymentMode] = [
            DeploymentMode(
                name="founder_execution_surface",
                app_target="src/murphy_core/app_v3_founder_execution_surface.py",
                startup="src/runtime/main_core_v3_founder_execution_surface.py",
                category="canonical",
                preferred_for=[
                    "production_deployments",
                    "founder_admin_visibility",
                    "capability_aware_execution",
                    "operator_ui",
                ],
                notes=[
                    "Preferred production path with unified founder/admin visibility",
                    "Includes capability-aware gating in live execution",
                ],
            ),
            DeploymentMode(
                name="direct_core_runtime_correct",
                app_target="src/murphy_core/app_v3_runtime.py",
                startup="src/runtime/main_core_v3_runtime_correct.py",
                category="rollback",
                preferred_for=[
                    "fallback_core_path",
                    "minimal_runtime_boot",
                ],
                notes=[
                    "Retained as fallback runtime-correct core path",
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
        return next(mode for mode in self.modes if mode.name == "founder_execution_surface")

    def compat_shell(self) -> DeploymentMode:
        return next(mode for mode in self.modes if mode.name == "legacy_compat_shell")

    def to_dict(self) -> Dict[str, object]:
        return {
            "preferred_direct": self.preferred_direct().to_dict(),
            "compat_shell": self.compat_shell().to_dict(),
            "modes": [mode.to_dict() for mode in self.modes],
        }
