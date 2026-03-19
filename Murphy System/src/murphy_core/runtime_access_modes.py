from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AccessMode:
    name: str
    audience: str
    app_target: str
    startup: str
    role: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "audience": self.audience,
            "app_target": self.app_target,
            "startup": self.startup,
            "role": self.role,
            "notes": list(self.notes),
        }


class RuntimeAccessModes:
    """Separate canonical execution runtime from privileged visibility overlays."""

    def __init__(self) -> None:
        self.modes: List[AccessMode] = [
            AccessMode(
                name="canonical_execution",
                audience="all_runtime_users",
                app_target="src/murphy_core/app_v3_founder_execution_surface_v3.py",
                startup="src/runtime/main_core_v3_founder_execution_surface_v3.py",
                role="default_execution_runtime",
                notes=[
                    "Canonical execution runtime for normal users and automation",
                    "Includes subsystem-family selection and capability-aware execution",
                    "Founder visibility endpoints are additive privileged surfaces, not the audience identity",
                ],
            ),
            AccessMode(
                name="founder_visibility_overlay",
                audience="founder_admin_only",
                app_target="src/murphy_core/app_v3_founder_execution_surface_v3.py",
                startup="src/runtime/main_core_v3_founder_execution_surface_v3.py",
                role="privileged_visibility_overlay",
                notes=[
                    "Privileged founder/admin visibility available on the same runtime",
                    "Should not redefine the runtime as founder-only for normal users",
                ],
            ),
            AccessMode(
                name="legacy_compatibility",
                audience="migration_and_legacy_users",
                app_target="src/runtime/legacy_runtime_compat_shell.py",
                startup="src/runtime/main_legacy_compat_shell.py",
                role="transitional_runtime",
                notes=[
                    "Legacy route/UI coverage during migration",
                ],
            ),
        ]

    def canonical(self) -> AccessMode:
        return next(mode for mode in self.modes if mode.name == "canonical_execution")

    def founder_overlay(self) -> AccessMode:
        return next(mode for mode in self.modes if mode.name == "founder_visibility_overlay")

    def to_dict(self) -> Dict[str, object]:
        return {
            "canonical": self.canonical().to_dict(),
            "founder_overlay": self.founder_overlay().to_dict(),
            "modes": [mode.to_dict() for mode in self.modes],
        }
