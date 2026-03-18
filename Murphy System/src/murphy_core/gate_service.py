from __future__ import annotations

from typing import Dict, List

from .contracts import GateEvaluation, InferenceEnvelope, RosettaEnvelope
from .gate_adapters import (
    DefaultAuthorityGateAdapter,
    DefaultBudgetGateAdapter,
    DefaultComplianceGateAdapter,
    DefaultConfidenceGateAdapter,
    DefaultHITLGateAdapter,
    DefaultSecurityGateAdapter,
    GateAdapter,
    GateAdapterHealth,
)


class AdapterBackedGateService:
    """Central gate selector/executor for Murphy Core."""

    def __init__(self) -> None:
        self.adapters: List[GateAdapter] = [
            DefaultSecurityGateAdapter(),
            DefaultComplianceGateAdapter(),
            DefaultAuthorityGateAdapter(),
            DefaultConfidenceGateAdapter(),
            DefaultHITLGateAdapter(),
            DefaultBudgetGateAdapter(),
        ]

    def health(self) -> Dict[str, object]:
        reports: List[GateAdapterHealth] = [adapter.health() for adapter in self.adapters]
        return {
            "gates": [
                {
                    "gate_name": report.gate_name,
                    "available": report.available,
                    "reason": report.reason,
                    "metadata": report.metadata,
                }
                for report in reports
            ]
        }

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> List[GateEvaluation]:
        results: List[GateEvaluation] = []
        for adapter in self.adapters:
            health = adapter.health()
            if not health.available:
                continue
            results.append(adapter.evaluate(inference, rosetta))
        return results
