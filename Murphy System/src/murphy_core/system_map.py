from __future__ import annotations

from typing import Dict

from .compatibility import LegacyCompatibilityMap
from .registry import ModuleRegistry
from .routing import CoreRouter


class SystemMapService:
    """Expose canonical request path and migration ownership metadata."""

    def __init__(self, registry: ModuleRegistry, router: CoreRouter) -> None:
        self.registry = registry
        self.router = router
        self.compatibility = LegacyCompatibilityMap()

    def build_map(self) -> Dict[str, object]:
        return {
            "canonical_path": [
                "request",
                "inference",
                "rosetta",
                "gates",
                "routing",
                "planner",
                "execution",
                "trace",
                "delivery",
            ],
            "runtime_hints": self.router.runtime_hints(),
            "compatibility_routes": self.compatibility.to_dicts(),
            "registry_summary": {
                "total_modules": len(self.registry.list()),
                "core_or_adapter": len([
                    r for r in self.registry.list() if r.status.value in {"core", "adapter"}
                ]),
            },
        }
