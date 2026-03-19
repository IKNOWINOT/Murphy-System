from __future__ import annotations

from typing import Dict, List

from .contracts import GateEvaluation, InferenceEnvelope, RosettaEnvelope, RouteType
from .production_inventory import ProductionInventory


class SubsystemFamilySelector:
    """Select preserved subsystem families for execution.

    This turns inventory truth plus capability-gating metadata into concrete
    selected subsystem families so execution planning preserves the intended
    families instead of flattening everything to raw module-class hints.
    """

    def __init__(self, inventory: ProductionInventory | None = None) -> None:
        self.inventory = inventory or ProductionInventory()

    def select(
        self,
        inference: InferenceEnvelope,
        rosetta: RosettaEnvelope,
        gate_results: List[GateEvaluation],
        route: RouteType,
    ) -> Dict[str, object]:
        route_tokens = {route.value}
        hint_tokens = {token.lower() for token in rosetta.allowed_module_classes}
        domain_tokens = {token.lower() for token in rosetta.canonical_domain_tags}
        goal_tokens = {token.lower() for token in inference.goals}
        message_tokens = set(inference.raw_message.lower().replace('_', ' ').replace('-', ' ').split())

        capability_meta: Dict[str, object] = {}
        for gate in gate_results:
            if gate.gate_name == "capability_selection":
                capability_meta = dict(gate.metadata)
                break

        selected: List[str] = []
        review: List[str] = []
        blocked: List[str] = []
        notes: List[str] = []

        eligible_modules = {m.lower() for m in capability_meta.get("eligible_modules", [])}
        review_modules = {m.lower() for m in capability_meta.get("review_required_modules", [])}
        blocked_modules = {m.lower() for m in capability_meta.get("blocked_modules", [])}

        for family in self.inventory.families:
            family_tokens = set(family.name.lower().split('_'))
            example_tokens = set()
            for example in family.examples:
                example_tokens.update(example.lower().replace('/', ' ').replace('-', ' ').split())

            token_match = bool(
                family_tokens & hint_tokens
                or family_tokens & domain_tokens
                or family_tokens & goal_tokens
                or family_tokens & message_tokens
                or example_tokens & hint_tokens
                or example_tokens & domain_tokens
                or example_tokens & message_tokens
                or route_tokens & set(family.layers)
            )

            if not token_match:
                continue

            family_name_l = family.name.lower()
            if family_name_l in blocked_modules:
                blocked.append(family.name)
                continue
            if family_name_l in review_modules or family.state in {"preserve_wrap", "preserve_shell"} and inference.risk_score >= 0.4:
                review.append(family.name)
                continue
            if eligible_modules and family_name_l not in eligible_modules:
                # keep family if the textual signals are strong enough for preserved-family visibility
                if not (family_tokens & message_tokens or example_tokens & message_tokens):
                    continue
            selected.append(family.name)

        if route == RouteType.SWARM and "swarms_bots_agents" not in selected:
            selected.append("swarms_bots_agents")
        if inference.required_approvals and "mfgc" not in selected:
            selected.append("mfgc")
        if any("compliance" in token for token in message_tokens | domain_tokens) and "compliance" not in selected:
            selected.append("compliance")
        if any("document" in token or "artifact" in token or "image" in token for token in message_tokens | domain_tokens):
            if "artifact_generation" not in selected:
                selected.append("artifact_generation")
        if any("workflow" in token or "plan" in token for token in message_tokens | goal_tokens):
            if "workflow_compiler_storage" not in selected:
                selected.append("workflow_compiler_storage")

        selected = list(dict.fromkeys(selected))
        review = list(dict.fromkeys(review))
        blocked = list(dict.fromkeys(blocked))

        if not selected:
            notes.append("No subsystem families selected from preserved inventory; using Rosetta module-class fallback")
        if capability_meta.get("notes"):
            notes.extend(str(note) for note in capability_meta.get("notes", []))

        primary_family = selected[0] if selected else "rosetta_fallback"
        return {
            "primary_family": primary_family,
            "selected_families": selected,
            "review_families": review,
            "blocked_families": blocked,
            "notes": notes,
        }
