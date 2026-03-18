from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CompatibilityRoute:
    family: str
    owner: str
    strategy: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "owner": self.owner,
            "strategy": self.strategy,
            "notes": list(self.notes),
        }


class LegacyCompatibilityMap:
    """Defines how legacy endpoint families should migrate toward Murphy Core.

    This is additive: it documents and exposes intended delegation strategy
    without rewriting the giant legacy runtime in one pass.
    """

    def __init__(self) -> None:
        self._routes = [
            CompatibilityRoute(
                family="core_runtime",
                owner="murphy_core",
                strategy="canonical",
                notes=["Murphy Core owns health/readiness/capabilities/registry/system-map/chat/execute/traces"],
            ),
            CompatibilityRoute(
                family="legacy_chat_execute",
                owner="murphy_core",
                strategy="delegate_to_core",
                notes=["Legacy /api/chat and /api/execute should forward into Murphy Core orchestration"],
            ),
            CompatibilityRoute(
                family="document_workflows",
                owner="adapter",
                strategy="adapter_then_migrate",
                notes=["Keep document/workflow endpoints alive through adapters until typed core equivalents exist"],
            ),
            CompatibilityRoute(
                family="hitl_review",
                owner="adapter",
                strategy="adapter_then_unify",
                notes=["Expose HITL requirements and decisions through Murphy Core traces"],
            ),
            CompatibilityRoute(
                family="swarm_operations",
                owner="adapter",
                strategy="adapter_with_core_trace",
                notes=["Swarm execution remains specialized but should emit Murphy Core trace metadata"],
            ),
            CompatibilityRoute(
                family="domain_modules",
                owner="legacy_runtime",
                strategy="compatibility_only",
                notes=["Large domain surfaces remain legacy until registry and capability truth is established"],
            ),
        ]

    def list(self) -> List[CompatibilityRoute]:
        return list(self._routes)

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._routes]
