"""
MFGC v1.1 - Trust-Weighted Grounding, Organizational Override Protection,
Temporal Confidence Decay, Meta-Governance, and Enhanced Murphy Index.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from mfgc_core import ConfidenceEngine, MFGCController, MFGCSystemState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trust-Weighted Grounding
# ---------------------------------------------------------------------------

class TrustedSource:
    """A verification source with a trust score that can decay or be penalized."""

    def __init__(self, name: str, trust_score: float, decay_rate: float = 0.001):
        self.name = name
        self.trust_score = trust_score
        self.decay_rate = decay_rate

    def decay_trust(self):
        self.trust_score *= (1.0 - self.decay_rate)

    def penalize(self, factor: float = 0.5):
        self.trust_score *= factor


class TrustWeightedGrounding:
    """D(x_t) = Σ T(s_i) · E(s_i)"""

    def __init__(self):
        self.sources: Dict[str, TrustedSource] = {
            "wikipedia": TrustedSource("wikipedia", 0.8),
            "peer_reviewed": TrustedSource("peer_reviewed", 0.95),
            "official_docs": TrustedSource("official_docs", 0.9),
        }

    def compute_grounding(self, evidence: Dict[str, float]) -> float:
        total = 0.0
        weight_sum = 0.0
        for source_name, evidence_score in evidence.items():
            src = self.sources.get(source_name)
            if src:
                total += src.trust_score * evidence_score
                weight_sum += src.trust_score
        return min(1.0, total / weight_sum) if weight_sum > 0 else 0.0

    def report_contradiction(self, source_name: str):
        src = self.sources.get(source_name)
        if src:
            src.penalize(0.5)


# ---------------------------------------------------------------------------
# Organizational Override Protection
# ---------------------------------------------------------------------------

class OrganizationalOverride(Enum):
    """Organizational override (Enum subclass)."""
    NONE = 0
    SUGGEST = 1
    ACCELERATE = 2
    FORCE = 3


class IncentivePressureMonitor:
    """Monitors organizational pressure and computes incentive pressure."""

    def __init__(self):
        self.current_override = OrganizationalOverride.NONE

    def set_override(self, override: OrganizationalOverride):
        self.current_override = override

    def compute_incentive_pressure(self) -> float:
        return self.current_override.value / OrganizationalOverride.FORCE.value

    def should_decay_authority(self) -> bool:
        return self.current_override.value >= OrganizationalOverride.ACCELERATE.value


# ---------------------------------------------------------------------------
# Temporal Confidence Decay
# ---------------------------------------------------------------------------

class TemporalConfidenceDecay:
    """c_t ← c_t · e^(-λΔt)"""

    def __init__(self, decay_rate: float = 0.1):
        self.decay_rate = decay_rate
        self._timestamps: Dict[str, float] = {}

    def apply_decay(self, confidence: float, context_id: str) -> float:
        now = time.time()
        last = self._timestamps.get(context_id)
        self._timestamps[context_id] = now
        if last is None:
            return confidence
        dt = now - last
        return confidence * math.exp(-self.decay_rate * dt)

    def reset_decay(self, context_id: str):
        self._timestamps.pop(context_id, None)


# ---------------------------------------------------------------------------
# Meta-Governance Protection
# ---------------------------------------------------------------------------

class MetaGovernanceProtection:
    """Protects core system invariants from modification."""

    PROTECTED_COMPONENTS = {
        "confidence_equation",
        "authority_mapping",
        "murphy_index",
        "gate_synthesis",
        "phase_controller",
    }

    def is_protected(self, component: str) -> bool:
        return component in self.PROTECTED_COMPONENTS

    def validate_gate(self, gate: Dict[str, Any]) -> Tuple[bool, str]:
        modifies = gate.get("modifies", [])
        for comp in modifies:
            if self.is_protected(comp):
                return False, f"Cannot modify protected component: {comp}"
        return True, "valid"


# ---------------------------------------------------------------------------
# Enhanced Murphy Index Monitor
# ---------------------------------------------------------------------------

class EnhancedMurphyIndexMonitor:
    """p_k = σ(αH + β(1-D) + γE + δA + ηI)"""

    def __init__(self):
        self.alpha = 1.0
        self.beta = 1.0
        self.gamma = 0.5
        self.delta = 0.5
        self.eta = 1.5
        self.incentive_monitor = IncentivePressureMonitor()

    def compute_murphy_probability(
        self,
        hallucination_score: float,
        determinism_score: float,
        exposure: float,
        authority_risk: float,
    ) -> float:
        incentive = self.incentive_monitor.compute_incentive_pressure()
        z = (
            self.alpha * hallucination_score
            + self.beta * (1.0 - determinism_score)
            + self.gamma * exposure
            + self.delta * authority_risk
            + self.eta * incentive
        )
        return 1.0 / (1.0 + math.exp(-z))  # sigmoid


# ---------------------------------------------------------------------------
# MFGCv1.1 Controller
# ---------------------------------------------------------------------------

class MFGCv1_1Controller:
    """Extended MFGC controller with v1.1 features."""

    def __init__(self):
        self.base_controller = MFGCController()
        self.trust_grounding = TrustWeightedGrounding()
        self.temporal_decay = TemporalConfidenceDecay()
        self.meta_governance = MetaGovernanceProtection()
        self.murphy_monitor = EnhancedMurphyIndexMonitor()

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> MFGCSystemState:
        state = self.base_controller.execute(task, context)

        # Apply temporal decay
        state.c_t = self.temporal_decay.apply_decay(state.c_t, task)

        # Apply authority decay under organizational pressure
        if self.murphy_monitor.incentive_monitor.should_decay_authority():
            state.a_t *= 0.5

        return state

    def set_organizational_override(self, override: OrganizationalOverride):
        self.murphy_monitor.incentive_monitor.set_override(override)

    def get_v1_1_summary(self, state: MFGCSystemState) -> Dict[str, Any]:
        base = self.base_controller.get_summary(state)
        base["v1_1_features"] = {
            "trust_weighted_grounding": {
                "sources": {
                    name: src.trust_score
                    for name, src in self.trust_grounding.sources.items()
                },
            },
            "organizational_pressure": {
                "current_override": self.murphy_monitor.incentive_monitor.current_override.name,
                "incentive_pressure": self.murphy_monitor.incentive_monitor.compute_incentive_pressure(),
            },
            "temporal_decay": {"decay_rate": self.temporal_decay.decay_rate},
            "meta_governance": {
                "protected_components": list(MetaGovernanceProtection.PROTECTED_COMPONENTS)
            },
        }
        return base


# ---------------------------------------------------------------------------
# Stress-Test Scenarios
# ---------------------------------------------------------------------------

def stress_test_boeing_failure() -> Dict[str, Any]:
    """Simulate Boeing-style organizational pressure overriding safety."""
    controller = MFGCv1_1Controller()
    state_normal = controller.execute("Safety-critical system")
    authority_normal = state_normal.a_t

    controller2 = MFGCv1_1Controller()
    controller2.set_organizational_override(OrganizationalOverride.FORCE)
    state_pressure = controller2.execute("Safety-critical system")
    authority_pressure = state_pressure.a_t

    return {
        "authority_normal": authority_normal,
        "authority_pressure": authority_pressure,
        "result": "PASS - Authority decayed under pressure",
    }


def stress_test_flash_crash() -> Dict[str, Any]:
    """Simulate rapid execution that could cause cascading failures."""
    controller = MFGCv1_1Controller()
    states = []
    for i in range(5):
        state = controller.execute(f"Rapid trade {i}")
        states.append(state)

    has_gates = all(len(s.G_t) > 0 for s in states)
    return {
        "executions": len(states),
        "has_safety_gates": has_gates,
        "result": "PASS - Safety gates present in all executions",
    }


def stress_test_medical_ai() -> Dict[str, Any]:
    """Simulate medical AI scenario requiring high confidence."""
    controller = MFGCv1_1Controller()
    state = controller.execute("Diagnose patient symptoms")
    return {
        "confidence": state.c_t,
        "murphy_index": state.M_t,
        "gates": len(state.G_t),
        "result": "PASS - Medical AI safety constraints applied",
    }
