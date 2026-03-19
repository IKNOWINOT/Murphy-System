from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


VALID_LAYERS = {
    "substrate",
    "generation",
    "guidance",
    "orchestration",
    "production",
    "gate_review",
    "delivery",
    "learning",
    "hybrid",
}

VALID_STATES = {
    "preserve_active",
    "preserve_wrap",
    "preserve_shell",
    "replace_equivalent",
    "needs_rebuild",
}


@dataclass
class SubsystemFamily:
    name: str
    layers: List[str]
    state: str
    purpose: str
    examples: List[str] = field(default_factory=list)
    refactor_rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "layers": list(self.layers),
            "state": self.state,
            "purpose": self.purpose,
            "examples": list(self.examples),
            "refactor_rule": self.refactor_rule,
        }


class ProductionInventory:
    """Machine-readable preservation and runtime-order inventory.

    This inventory mirrors the production runtime separation plan and endpoint
    preservation map so UI/operator/admin/runtime surfaces can inspect the
    subsystem families directly.
    """

    def __init__(self) -> None:
        self.runtime_order = [
            "substrate",
            "generation",
            "guidance",
            "orchestration",
            "production",
            "gate_review",
            "delivery",
            "learning",
        ]
        self.families: List[SubsystemFamily] = [
            SubsystemFamily(
                name="survival_control_substrate",
                layers=["substrate"],
                state="preserve_active",
                purpose="Keep the platform alive, secure, routable, durable, and observable.",
                examples=[
                    "security plane",
                    "governance kernel",
                    "event backbone",
                    "database",
                    "cache",
                    "integration bus",
                    "health/readiness/metrics",
                ],
                refactor_rule="Keep foundational and early in startup order; do not bury under business or production abstractions.",
            ),
            SubsystemFamily(
                name="aionmind",
                layers=["generation", "hybrid"],
                state="preserve_wrap",
                purpose="Cognitive enrichment, interpretation, and contextual execution support.",
                examples=["task interpretation", "form interpretation", "cognitive execution context"],
                refactor_rule="Preserve explicitly as enrichment and interpretation; do not force it to remain top-level orchestration owner.",
            ),
            SubsystemFamily(
                name="librarian_taskrouter",
                layers=["generation"],
                state="preserve_active",
                purpose="Capability discovery, ranking, and knowledge-guided route hints.",
                examples=["capability lookup", "route hints", "ranked matches"],
                refactor_rule="Preserve as first-class discovery and selection infrastructure before execution.",
            ),
            SubsystemFamily(
                name="mss",
                layers=["generation", "production"],
                state="preserve_wrap",
                purpose="Specialized transformation toolkit for magnify/simplify/solidify and structured content shaping.",
                examples=["magnify", "simplify", "solidify", "document/context transformation"],
                refactor_rule="Preserve as intentionally selectable transform semantics, not a generic text helper.",
            ),
            SubsystemFamily(
                name="ucp",
                layers=["orchestration", "generation"],
                state="preserve_wrap",
                purpose="Unified execution and control-plane behavior for specialized execution paths.",
                examples=["UCP execute", "control-plane execution support"],
                refactor_rule="Preserve as explicit execution/control subsystem, not dead compatibility code.",
            ),
            SubsystemFamily(
                name="mfgc",
                layers=["gate_review"],
                state="preserve_active",
                purpose="Gate state, gate config, gate setup, and progression control decisions.",
                examples=["MFGC state", "MFGC config", "MFGC setup"],
                refactor_rule="Preserve as first-class governance/gating family between orchestration and production progression.",
            ),
            SubsystemFamily(
                name="compliance",
                layers=["gate_review"],
                state="preserve_active",
                purpose="Compliance toggles, reports, scans, and policy gate behavior.",
                examples=["compliance scan", "compliance report", "policy gating"],
                refactor_rule="Preserve as a hard gate layer close to MFGC and HITL.",
            ),
            SubsystemFamily(
                name="hitl_qc_acceptance",
                layers=["gate_review", "delivery"],
                state="preserve_active",
                purpose="Human approval, QC, acceptance, revision, and release gating.",
                examples=["HITL queue", "QC", "acceptance", "revision loop"],
                refactor_rule="Preserve as explicit review bridge between production and release, not hidden status flags.",
            ),
            SubsystemFamily(
                name="swarms_bots_agents",
                layers=["orchestration", "hybrid"],
                state="preserve_active",
                purpose="Execution-plane worker systems for swarm crews, bots, durable runs, and agent orchestration.",
                examples=["swarm crew", "durable swarm", "bot inventory", "agent dashboard"],
                refactor_rule="Preserve as execution-plane worker families under orchestration and assignment.",
            ),
            SubsystemFamily(
                name="business_automation",
                layers=["guidance", "hybrid"],
                state="preserve_active",
                purpose="Direction-setting systems for marketing, sales, CRM, billing, org guidance, and operating priorities.",
                examples=["CRM", "campaigns", "marketing", "sales", "org chart", "billing", "reviews/referrals"],
                refactor_rule="Preserve as business-guidance systems that influence priorities and allocation rather than directly producing deliverables.",
            ),
            SubsystemFamily(
                name="onboarding_configuration_generation",
                layers=["generation", "hybrid"],
                state="preserve_wrap",
                purpose="Generate configuration, select modules/integrations, and create initial workflow intent.",
                examples=["onboarding wizard", "config generation", "integration selection"],
                refactor_rule="Preserve as configuration generation, not runtime identity.",
            ),
            SubsystemFamily(
                name="workflow_compiler_storage",
                layers=["orchestration", "generation"],
                state="preserve_active",
                purpose="Compile workflows, store workflow state, and bridge generated plans into executable graphs.",
                examples=["workflow terminal", "workflow compiler", "workflow storage"],
                refactor_rule="Preserve as orchestration infrastructure bridging generated plans to execution.",
            ),
            SubsystemFamily(
                name="production_proposals_work_orders",
                layers=["production", "orchestration"],
                state="preserve_active",
                purpose="Generate production proposals, work orders, routing, and production scheduling handoff.",
                examples=["production proposal", "work order", "production queue", "production routing"],
                refactor_rule="Preserve as the top of the production layer and visible handoff from orchestration into product creation.",
            ),
            SubsystemFamily(
                name="forms_validation_correction",
                layers=["production", "gate_review"],
                state="preserve_active",
                purpose="Structured execution, validation, correction, and result shaping for task/form workflows.",
                examples=["form execution", "validation", "correction loop"],
                refactor_rule="Preserve as production execution with integrated correction loop; do not collapse into generic chat execution.",
            ),
            SubsystemFamily(
                name="artifact_generation",
                layers=["production", "delivery"],
                state="preserve_active",
                purpose="Build deliverables such as documents, artifacts, images, and report-like outputs.",
                examples=["document generation", "image generation", "artifact creation"],
                refactor_rule="Preserve as direct output producers and keep visible as deliverable-building systems.",
            ),
            SubsystemFamily(
                name="delivery_verification",
                layers=["delivery"],
                state="preserve_active",
                purpose="Package, send, verify, and close approved outputs.",
                examples=["deliverables", "verification", "packaging", "release state"],
                refactor_rule="Preserve as distinct layer after review/acceptance, not merged into production transformation.",
            ),
            SubsystemFamily(
                name="self_healing_learning",
                layers=["learning"],
                state="preserve_wrap",
                purpose="Improve future behavior through corrections, healing, training, readiness diagnostics, and repair loops.",
                examples=["MurphyCodeHealer", "trainer", "self-learning", "readiness diagnostics"],
                refactor_rule="Preserve as downstream improvement infrastructure, not as customer-facing production flow.",
            ),
            SubsystemFamily(
                name="cost_budget_assignment",
                layers=["guidance", "gate_review"],
                state="preserve_active",
                purpose="Cost visibility, budget constraints, and assignment guidance with policy implications.",
                examples=["cost summary", "budget", "assignment visibility"],
                refactor_rule="Preserve as business-guidance family influencing allocation and approval rather than directly owning execution.",
            ),
            SubsystemFamily(
                name="integrations_connectors",
                layers=["substrate", "hybrid"],
                state="preserve_active",
                purpose="Reusable external service access and cross-system workflow dependencies.",
                examples=["integrations", "external connectors", "cross-system actions"],
                refactor_rule="Preserve as reusable substrate access for higher layers rather than duplicated logic inside families.",
            ),
            SubsystemFamily(
                name="hybrid_translators",
                layers=["hybrid"],
                state="preserve_wrap",
                purpose="Translate between business guidance and production execution where a family spans both roles.",
                examples=["marketing content pipelines", "self-marketing orchestrator", "production scheduling", "review-response automation"],
                refactor_rule="Preserve as translators; do not force into false guidance-only or production-only classification.",
            ),
        ]

    def validate(self) -> Dict[str, object]:
        invalid_layers = []
        invalid_states = []
        duplicate_names = []
        seen = set()

        for family in self.families:
            if family.name in seen:
                duplicate_names.append(family.name)
            seen.add(family.name)
            bad_layers = [layer for layer in family.layers if layer not in VALID_LAYERS]
            if bad_layers:
                invalid_layers.append({"family": family.name, "layers": bad_layers})
            if family.state not in VALID_STATES:
                invalid_states.append({"family": family.name, "state": family.state})

        return {
            "ok": not invalid_layers and not invalid_states and not duplicate_names,
            "invalid_layers": invalid_layers,
            "invalid_states": invalid_states,
            "duplicate_names": duplicate_names,
            "family_count": len(self.families),
        }

    def grouped_by_layer(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {layer: [] for layer in VALID_LAYERS}
        for family in self.families:
            for layer in family.layers:
                result[layer].append(family.name)
        for layer in result:
            result[layer].sort()
        return result

    def to_dict(self) -> Dict[str, object]:
        return {
            "runtime_order": list(self.runtime_order),
            "families": [family.to_dict() for family in self.families],
            "by_layer": self.grouped_by_layer(),
            "validation": self.validate(),
        }
