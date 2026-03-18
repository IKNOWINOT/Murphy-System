from __future__ import annotations

from typing import Dict, List

from .config import CoreConfig
from .gate_service import AdapterBackedGateService
from .provider_service import AdapterBackedProviderService
from .registry import ModuleRegistry
from .system_map import SystemMapService


class ConfigurableOperatorStatusService:
    """Operator-facing truth snapshot with configurable runtime identity.

    This avoids stale hardcoded runtime labels and lets each app factory report
    its actual preferred factory truthfully.
    """

    def __init__(
        self,
        config: CoreConfig,
        registry: ModuleRegistry,
        providers: AdapterBackedProviderService,
        gates: AdapterBackedGateService,
        system_map: SystemMapService,
        preferred_factory: str,
    ) -> None:
        self.config = config
        self.registry = registry
        self.providers = providers
        self.gates = gates
        self.system_map = system_map
        self.preferred_factory = preferred_factory

    def snapshot(self) -> Dict[str, object]:
        provider_health = self.providers.health()
        gate_health = self.gates.health()
        map_data = self.system_map.build_map()
        records = self.registry.list()

        core_modules = [r.module_name for r in records if r.status.value == "core"]
        adapter_modules = [r.module_name for r in records if r.status.value == "adapter"]
        drifted_modules = [r.module_name for r in records if r.effective_capability.value == "drifted"]

        return {
            "runtime": {
                "preferred_factory": self.preferred_factory,
                "environment": self.config.environment,
                "default_provider": self.config.default_provider,
                "prefer_legacy_adapters": self.config.prefer_legacy_adapters,
            },
            "providers": provider_health,
            "gates": gate_health,
            "registry": {
                "total_modules": len(records),
                "core_modules": core_modules,
                "adapter_modules": adapter_modules,
                "drifted_modules": drifted_modules,
            },
            "system_map": map_data,
        }

    def ui_summary(self) -> Dict[str, object]:
        snapshot = self.snapshot()
        provider_reports: List[dict] = snapshot["providers"].get("providers", [])
        live_gate_reports: List[dict] = snapshot["gates"].get("gates", [])
        return {
            "preferred_factory": snapshot["runtime"]["preferred_factory"],
            "preferred_provider": snapshot["runtime"]["default_provider"],
            "provider_count": len(provider_reports),
            "gate_count": len(live_gate_reports),
            "core_module_count": len(snapshot["registry"]["core_modules"]),
            "adapter_module_count": len(snapshot["registry"]["adapter_modules"]),
            "drifted_module_count": len(snapshot["registry"]["drifted_modules"]),
        }
