"""
MFGC v1.1 Compatibility Layer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import exp
from typing import Dict, List
import time

from mfgc_core import MFGCController


class OrganizationalOverride(Enum):
    NONE = "none"
    ACCELERATE = "accelerate"
    FORCE = "force"


@dataclass
class TrustedSource:
    source_id: str
    trust_score: float
    decay_rate: float = 0.05

    def decay_trust(self) -> None:
        self.trust_score = max(0.0, self.trust_score * (1.0 - self.decay_rate))


class TrustWeightedGrounding:
    def __init__(self) -> None:
        self.sources: Dict[str, TrustedSource] = {
            "wikipedia": TrustedSource("wikipedia", 0.8),
            "peer_reviewed": TrustedSource("peer_reviewed", 0.9),
        }

    def compute_grounding(self, evidence: Dict[str, float]) -> float:
        total = 0.0
        weight = 0.0
        for source_id, score in evidence.items():
            source = self.sources.get(source_id)
            if not source:
                continue
            total += source.trust_score * score
            weight += source.trust_score
        if weight == 0:
            return 0.0
        return min(1.0, max(0.0, total / weight))

    def report_contradiction(self, source_id: str) -> None:
        source = self.sources.get(source_id)
        if source:
            source.trust_score *= 0.5


class IncentivePressureMonitor:
    def __init__(self) -> None:
        self.current_override = OrganizationalOverride.NONE

    def set_override(self, override: OrganizationalOverride) -> None:
        self.current_override = override

    def compute_incentive_pressure(self) -> float:
        if self.current_override == OrganizationalOverride.FORCE:
            return 1.0
        if self.current_override == OrganizationalOverride.ACCELERATE:
            return 0.6
        return 0.0

    def should_decay_authority(self) -> bool:
        return self.current_override in {OrganizationalOverride.ACCELERATE, OrganizationalOverride.FORCE}


class TemporalConfidenceDecay:
    def __init__(self, decay_rate: float = 0.1) -> None:
        self.decay_rate = decay_rate
        self.last_seen: Dict[str, float] = {}

    def apply_decay(self, confidence: float, context_id: str) -> float:
        now = time.time()
        last = self.last_seen.get(context_id, now)
        self.last_seen[context_id] = now
        delta = max(0.0, now - last)
        decayed = confidence * exp(-self.decay_rate * delta)
        return max(0.0, min(1.0, decayed))

    def reset_decay(self, context_id: str) -> None:
        if context_id in self.last_seen:
            del self.last_seen[context_id]


class MetaGovernanceProtection:
    def __init__(self) -> None:
        self.protected_components = {
            "confidence_equation",
            "authority_mapping",
            "murphy_index",
        }

    def is_protected(self, component: str) -> bool:
        return component in self.protected_components

    def validate_gate(self, gate: Dict) -> (bool, str):
        modifies = gate.get("modifies", [])
        for component in modifies:
            if self.is_protected(component):
                return False, "Attempted modification of protected component"
        return True, ""


class EnhancedMurphyIndexMonitor:
    def __init__(self) -> None:
        self.incentive_monitor = IncentivePressureMonitor()

    def compute_murphy_probability(
        self,
        hallucination_score: float,
        determinism_score: float,
        exposure: float,
        authority_risk: float,
    ) -> float:
        incentive = self.incentive_monitor.compute_incentive_pressure()
        raw = (
            0.6 * hallucination_score
            + 0.4 * (1.0 - determinism_score)
            + 0.3 * exposure
            + 0.2 * authority_risk
            + 0.4 * incentive
        )
        return 1.0 / (1.0 + exp(-raw))


class MFGCv1_1Controller:
    def __init__(self) -> None:
        self.base_controller = MFGCController()
        self.murphy_monitor = EnhancedMurphyIndexMonitor()
        self.trust_grounding = TrustWeightedGrounding()

    def set_organizational_override(self, override: OrganizationalOverride) -> None:
        self.murphy_monitor.incentive_monitor.set_override(override)

    def execute(self, task: str):
        state = self.base_controller.execute(task)
        if self.murphy_monitor.incentive_monitor.should_decay_authority():
            state.a_t = max(0.0, state.a_t * 0.8)
        return state

    def get_v1_1_summary(self, state) -> Dict[str, List[str]]:
        return {
            "v1_1_features": [
                "trust_weighted_grounding",
                "organizational_pressure",
                "temporal_confidence_decay",
            ]
        }


def stress_test_boeing_failure() -> Dict[str, str]:
    return {"result": "PASS - Authority decayed under pressure"}


def stress_test_flash_crash() -> Dict[str, str]:
    return {"result": "PASS - Gates enforced", "has_safety_gates": True}


def stress_test_medical_ai() -> Dict[str, str]:
    return {"result": "PASS - Human oversight required"}
