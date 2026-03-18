from __future__ import annotations

from typing import List

from .contracts import GateDecision, GateEvaluation, InferenceEnvelope, RosettaEnvelope


class GatePipeline:
    """Centralized gate evaluation for Murphy Core."""

    def evaluate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> List[GateEvaluation]:
        results: List[GateEvaluation] = []
        results.append(self._security_gate(inference, rosetta))
        results.append(self._compliance_gate(inference, rosetta))
        results.append(self._authority_gate(inference, rosetta))
        results.append(self._confidence_gate(inference, rosetta))
        results.append(self._hitl_gate(inference, rosetta))
        results.append(self._budget_gate(inference, rosetta))
        return results

    def _security_gate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale = []
        decision = GateDecision.ALLOW
        if inference.risk_score >= 0.8:
            decision = GateDecision.REVIEW
            rationale.append("High-risk request requires security review")
        return GateEvaluation("security", decision, rationale)

    def _compliance_gate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale = []
        decision = GateDecision.ALLOW
        if "domain.compliance" in rosetta.canonical_domain_tags:
            rationale.append("Compliance domain detected")
            if inference.risk_score >= 0.4:
                decision = GateDecision.REVIEW
                rationale.append("Compliance-sensitive request requires review")
        return GateEvaluation("compliance", decision, rationale)

    def _authority_gate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale = []
        decision = GateDecision.ALLOW
        if inference.constraints.get("production"):
            rationale.append("Production path requested")
        return GateEvaluation("authority", decision, rationale)

    def _confidence_gate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale = []
        if inference.confidence < 0.35:
            return GateEvaluation("confidence", GateDecision.REVIEW, ["Low inference confidence"])
        rationale.append(f"confidence={inference.confidence:.2f}")
        return GateEvaluation("confidence", GateDecision.ALLOW, rationale)

    def _hitl_gate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        if "hitl" in inference.required_approvals:
            return GateEvaluation("hitl", GateDecision.REQUIRES_HITL, ["HITL approval required by request risk"]) 
        return GateEvaluation("hitl", GateDecision.ALLOW, ["No HITL requirement triggered"]) 

    def _budget_gate(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope) -> GateEvaluation:
        rationale = []
        decision = GateDecision.ALLOW
        if "budget_review" in inference.required_approvals:
            decision = GateDecision.REVIEW
            rationale.append("Budget review required")
        return GateEvaluation("budget", decision, rationale)
