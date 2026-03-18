from __future__ import annotations

from typing import Dict, List, Optional

from .config import CoreConfig
from .contracts import CoreRequest, InferenceEnvelope
from .provider_adapters import (
    InferenceProviderAdapter,
    LegacyMurphyInferenceAdapter,
    LocalRulesAdapter,
    ProviderHealth,
)


class AdapterBackedProviderService:
    """Central provider selector for Murphy Core.

    Chooses a preferred adapter when healthy and falls back to other adapters
    without changing the typed inference contract.
    """

    def __init__(self, config: CoreConfig | None = None) -> None:
        self.config = config or CoreConfig.from_env()
        self.adapters: Dict[str, InferenceProviderAdapter] = {
            "local_rules": LocalRulesAdapter(),
            "legacy_murphy": LegacyMurphyInferenceAdapter(),
        }

    def health(self) -> Dict[str, object]:
        reports: List[ProviderHealth] = [adapter.health() for adapter in self.adapters.values()]
        preferred = self.config.default_provider
        return {
            "preferred_provider": preferred,
            "providers": [
                {
                    "provider_name": report.provider_name,
                    "available": report.available,
                    "reason": report.reason,
                    "metadata": report.metadata,
                }
                for report in reports
            ],
        }

    def infer(self, request: CoreRequest) -> InferenceEnvelope:
        ordered_names = self._ordered_adapter_names()
        last_error: Optional[Exception] = None
        for name in ordered_names:
            adapter = self.adapters.get(name)
            if adapter is None:
                continue
            health = adapter.health()
            if not health.available:
                continue
            try:
                inference = adapter.infer(request)
                inference.provider_metadata = {
                    **inference.provider_metadata,
                    "selected_provider": name,
                    "fallback_order": ordered_names,
                }
                return inference
            except Exception as exc:
                last_error = exc
                continue

        fallback = self.adapters["local_rules"].infer(request)
        fallback.provider_metadata = {
            **fallback.provider_metadata,
            "selected_provider": "local_rules",
            "fallback_order": ordered_names,
            "degraded": True,
            "last_error": str(last_error) if last_error else None,
        }
        return fallback

    def _ordered_adapter_names(self) -> List[str]:
        preferred = self.config.default_provider
        names = list(self.adapters.keys())
        if preferred in names:
            names.remove(preferred)
            names.insert(0, preferred)
        return names
