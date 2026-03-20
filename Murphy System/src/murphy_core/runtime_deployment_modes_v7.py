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


class RuntimeDeploymentModesV7:
    """Deployment choices with canonical execution v5 as the default mode."""

    def __init__(self) -> None:
        self.modes: List[DeploymentMode] = [
            DeploymentMode(
                name="canonical_execution_surface_v5",
                app_target="src/murphy_core/app_v3_canonical_execution_surface_v5.py",
                startup="src/runtime/main_core_v3_canonical_execution_surface_v5.py",
                category="canonical",
                preferred_for=[
                    "production_deployments",
                    "all_runtime_users",
                    "automation_execution",
                    "operator_ui",
                    "default_testing_target",
                ],
                notes=[
                    "Preferred default runtime for users and automations",
                    "Founder visibility remains an additive privileged overlay",
                    "Aligned to runtime truth v7",
                ],
            ),
            DeploymentMode(
                name="founder_visibility_overlay",
                app_target="src/murphy_core/app_v3_canonical_execution_surface_v5.py",
                startup="src/runtime/main_core_v3_canonical_execution_surface_v5.py",
                category="overlay",
                preferred_for=[
                    "founder_admin_visibility",
                    "privileged_runtime_control",
                ],
                notes=[
                    "Uses the same canonical runtime while exposing founder/admin-only surfaces",
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
        return next(mode for mode in self.modes if mode.name == "canonical_execution_surface_v5")

    def founder_overlay(self) -> DeploymentMode:
        return next(mode for mode in self.modes if mode.name == "founder_visibility_overlay")

    def compat_shell(self) -> DeploymentMode:
        return next(mode for mode in self.modes if mode.name == "legacy_compat_shell")

    def to_dict(self) -> Dict[str, object]:
        return {
            "preferred_direct": self.preferred_direct().to_dict(),
            "founder_overlay": self.founder_overlay().to_dict(),
            "compat_shell": self.compat_shell().to_dict(),
            "modes": [mode.to_dict() for mode in self.modes],
        }
