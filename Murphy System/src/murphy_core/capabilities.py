from __future__ import annotations

from typing import Dict, List

from .contracts import EffectiveCapability
from .registry import ModuleRegistry


class CapabilityService:
    def __init__(self, registry: ModuleRegistry) -> None:
        self.registry = registry

    def effective_capabilities(self) -> Dict[str, object]:
        records = self.registry.list()
        live = [r.module_name for r in records if r.effective_capability == EffectiveCapability.LIVE]
        available = [r.module_name for r in records if r.effective_capability == EffectiveCapability.AVAILABLE]
        drifted = [r.module_name for r in records if r.effective_capability == EffectiveCapability.DRIFTED]
        not_wired = [r.module_name for r in records if r.effective_capability == EffectiveCapability.NOT_WIRED]
        return {
            "summary": {
                "live": len(live),
                "available": len(available),
                "drifted": len(drifted),
                "not_wired": len(not_wired),
                "total": len(records),
            },
            "live_modules": live,
            "available_modules": available,
            "drifted_modules": drifted,
            "not_wired_modules": not_wired,
        }
