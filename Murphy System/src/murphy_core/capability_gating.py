from __future__ import annotations

from typing import Dict, List

from .contracts import GateDecision, GateEvaluation, InferenceEnvelope, ModuleRecord, RosettaEnvelope
from .registry import ModuleRegistry


class CapabilityGatingService:
    """Capability-aware gating overlay for Murphy Core.

    This layer answers a more specific question than the generic gate service:
    which declared capabilities and module families are actually eligible for
    the current request, and which should be preserved, reviewed, or blocked.
    """

    def __init__(self, registry: ModuleRegistry) -> None:
        self.registry = registry

    def evaluate_capabilities(
        self,
        inference: InferenceEnvelope,
        rosetta: RosettaEnvelope,
    ) -> Dict[str, object]:
        eligible: List[ModuleRecord] = []
        review_required: List[ModuleRecord] = []
        blocked: List[ModuleRecord] = []
        notes: List[str] = []

        class_hints = set(rosetta.allowed_module_classes)
        records = self.registry.list()

        for record in records:
            lowered_name = record.module_name.lower()
            lowered_category = record.category.lower() if record.category else ""
            match = any(hint in lowered_name or hint in lowered_category for hint in class_hints)
            if not match:
                continue

            if record.effective_capability.value in {"drifted", "missing_dependency"}:
                blocked.append(record)
                continue

            if inference.risk_score >= 0.4 and record.status.value in {"adapter", "experimental"}:
                review_required.append(record)
                continue

            eligible.append(record)

        if not eligible and not review_required:
            notes.append("No eligible registered capabilities matched the normalized module classes")

        if inference.required_approvals:
            notes.append("Request has approval requirements: " + ",".join(inference.required_approvals))

        return {
            "eligible_modules": [r.module_name for r in eligible],
            "review_required_modules": [r.module_name for r in review_required],
            "blocked_modules": [r.module_name for r in blocked],
            "notes": notes,
        }

    def to_gate_evaluation(
        self,
        inference: InferenceEnvelope,
        rosetta: RosettaEnvelope,
    ) -> GateEvaluation:
        result = self.evaluate_capabilities(inference, rosetta)
        decision = GateDecision.ALLOW
        rationale: List[str] = []

        if result["blocked_modules"] and not result["eligible_modules"]:
            decision = GateDecision.REVIEW
            rationale.append("Matched capabilities are blocked or drifted")
        if result["review_required_modules"]:
            decision = GateDecision.REVIEW
            rationale.append("Some matched capabilities require review before execution")
        if not result["eligible_modules"] and not result["review_required_modules"]:
            decision = GateDecision.REVIEW
            rationale.append("No verified eligible capabilities matched request")

        rationale.extend(result["notes"])
        return GateEvaluation(
            gate_name="capability_selection",
            decision=decision,
            rationale=rationale,
            metadata=result,
        )
