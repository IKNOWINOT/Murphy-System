from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .contracts import GateDecision, GateEvaluation, InferenceEnvelope, RosettaEnvelope


@dataclass
class GateAdapterHealth:
    gate_name: str
    available: bool
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class GateAdapter(Protocol):
    gate_name: str

    def health(self) -> GateAdapterHealth:
        ...

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        ...


class DefaultSecurityGateAdapter:
    gate_name = "security"

    def health(self) -> GateAdapterHealth:
        return GateAdapterHealth(gate_name=self.gate_name, available=True)

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale: List[str] = []
        decision = GateDecision.ALLOW
        if inference.risk_score >= 0.8:
            decision = GateDecision.REVIEW
            rationale.append("High-risk request requires security review")
        return GateEvaluation(self.gate_name, decision, rationale)


class DefaultComplianceGateAdapter:
    gate_name = "compliance"

    def health(self) -> GateAdapterHealth:
        return GateAdapterHealth(gate_name=self.gate_name, available=True)

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale: List[str] = []
        decision = GateDecision.ALLOW
        if "domain.compliance" in rosetta.canonical_domain_tags:
            rationale.append("Compliance domain detected")
            if inference.risk_score >= 0.4:
                decision = GateDecision.REVIEW
                rationale.append("Compliance-sensitive request requires review")
        return GateEvaluation(self.gate_name, decision, rationale)


class DefaultAuthorityGateAdapter:
    gate_name = "authority"

    def health(self) -> GateAdapterHealth:
        return GateAdapterHealth(gate_name=self.gate_name, available=True)

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale: List[str] = []
        if inference.constraints.get("production"):
            rationale.append("Production path requested")
        return GateEvaluation(self.gate_name, GateDecision.ALLOW, rationale)


class DefaultConfidenceGateAdapter:
    gate_name = "confidence"

    def health(self) -> GateAdapterHealth:
        return GateAdapterHealth(gate_name=self.gate_name, available=True)

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        if inference.confidence < 0.35:
            return GateEvaluation(self.gate_name, GateDecision.REVIEW, ["Low inference confidence"])
        return GateEvaluation(self.gate_name, GateDecision.ALLOW, [f"confidence={inference.confidence:.2f}"])


class DefaultHITLGateAdapter:
    gate_name = "hitl"

    def health(self) -> GateAdapterHealth:
        return GateAdapterHealth(gate_name=self.gate_name, available=True)

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        approvals = set(inference.required_approvals)
        if "founder_hitl" in approvals:
            return GateEvaluation(
                self.gate_name,
                GateDecision.REQUIRES_HITL,
                ["Founder HITL validation required for platform-changing request"],
                metadata={"hitl_scope": "founder", "target_scope": inference.constraints.get("target_scope", "user")},
            )
        if "org_hitl" in approvals:
            return GateEvaluation(
                self.gate_name,
                GateDecision.REQUIRES_HITL,
                ["Organization HITL validation required for organization-scoped request"],
                metadata={"hitl_scope": "organization", "target_scope": inference.constraints.get("target_scope", "user")},
            )
        if "hitl" in approvals:
            return GateEvaluation(
                self.gate_name,
                GateDecision.REQUIRES_HITL,
                ["HITL approval required by request risk"],
                metadata={"hitl_scope": "generic", "target_scope": inference.constraints.get("target_scope", "user")},
            )
        return GateEvaluation(
            self.gate_name,
            GateDecision.ALLOW,
            ["No HITL requirement triggered"],
            metadata={"hitl_scope": "none", "target_scope": inference.constraints.get("target_scope", "user")},
        )


class DefaultBudgetGateAdapter:
    gate_name = "budget"

    def health(self) -> GateAdapterHealth:
        return GateAdapterHealth(gate_name=self.gate_name, available=True)

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale: List[str] = []
        decision = GateDecision.ALLOW
        if "budget_review" in inference.required_approvals:
            decision = GateDecision.REVIEW
            rationale.append("Budget review required")
        return GateEvaluation(self.gate_name, decision, rationale)
