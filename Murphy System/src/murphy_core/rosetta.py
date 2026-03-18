from __future__ import annotations

from typing import Dict, List

from .contracts import InferenceEnvelope, RosettaEnvelope, RouteType


class RosettaCore:
    """Canonical semantic normalization layer for Murphy Core."""

    def normalize(self, inference: InferenceEnvelope) -> RosettaEnvelope:
        canonical_intent = self._canonical_intent(inference.intent)
        canonical_entities = dict(inference.entities)
        canonical_constraints = dict(inference.constraints)
        canonical_domain_tags = self._canonical_domain_tags(inference.domain_tags)
        allowed_module_classes = self._allowed_module_classes(canonical_intent, canonical_domain_tags)
        route_hints = self._route_hints(inference.proposed_routes, canonical_intent, canonical_domain_tags)
        normalization_notes = self._notes(inference, canonical_intent)

        return RosettaEnvelope(
            request_id=inference.request_id,
            canonical_intent=canonical_intent,
            canonical_entities=canonical_entities,
            canonical_constraints=canonical_constraints,
            canonical_domain_tags=canonical_domain_tags,
            allowed_module_classes=allowed_module_classes,
            route_hints=route_hints,
            normalization_notes=normalization_notes,
        )

    def _canonical_intent(self, intent: str) -> str:
        mapping = {
            "build_workflow": "workflow.build",
            "review_or_gate": "control.review",
            "swarm_operation": "swarm.execute",
            "execute_task": "task.execute",
            "chat_assistance": "chat.respond",
        }
        return mapping.get(intent, intent)

    def _canonical_domain_tags(self, tags: List[str]) -> List[str]:
        canonical: List[str] = []
        mapping = {
            "automation": "domain.automation",
            "finance": "domain.finance",
            "swarm": "domain.swarm",
            "security": "domain.security",
            "compliance": "domain.compliance",
            "ui": "domain.ui",
            "voice": "domain.voice",
            "collaboration": "domain.collaboration",
            "general": "domain.general",
        }
        for tag in tags:
            ct = mapping.get(tag, f"domain.{tag}")
            if ct not in canonical:
                canonical.append(ct)
        return canonical

    def _allowed_module_classes(self, canonical_intent: str, domain_tags: List[str]) -> List[str]:
        classes: List[str] = ["registry", "tracing"]
        if canonical_intent.startswith("workflow"):
            classes.extend(["planner", "workflow_generator", "routing"])
        if canonical_intent.startswith("control"):
            classes.extend(["gates", "routing", "control_plane"])
        if canonical_intent.startswith("swarm"):
            classes.extend(["swarm", "visual_swarm", "hitl"])
        if canonical_intent.startswith("task"):
            classes.extend(["executor", "routing", "legacy_runtime"])
        if "domain.security" in domain_tags:
            classes.append("security_plane")
        if "domain.compliance" in domain_tags:
            classes.append("compliance")
        if "domain.ui" in domain_tags:
            classes.append("ui_api")
        return list(dict.fromkeys(classes))

    def _route_hints(self, proposed: List[RouteType], canonical_intent: str, domain_tags: List[str]) -> List[RouteType]:
        hints = list(proposed)
        if canonical_intent == "swarm.execute" and RouteType.SWARM not in hints:
            hints.insert(0, RouteType.SWARM)
        if "domain.security" in domain_tags and RouteType.SPECIALIST not in hints:
            hints.insert(0, RouteType.SPECIALIST)
        if not hints:
            hints = [RouteType.DETERMINISTIC]
        return hints

    def _notes(self, inference: InferenceEnvelope, canonical_intent: str) -> List[str]:
        notes = [f"intent:{inference.intent}->{canonical_intent}"]
        if inference.required_approvals:
            notes.append("approvals:" + ",".join(inference.required_approvals))
        if inference.risk_score >= 0.4:
            notes.append("elevated_risk")
        return notes
