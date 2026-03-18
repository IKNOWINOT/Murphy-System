from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .contracts import CoreRequest, InferenceEnvelope, RouteType


class CoreProviderService:
    """Centralized inference provider abstraction for Murphy Core.

    This intentionally starts with rule-based inference and can later wrap
    existing LLM integrations as adapters without changing the contract.
    """

    def __init__(self, preferred_provider: str = "local_rules") -> None:
        self.preferred_provider = preferred_provider
        self.available_providers = ["local_rules"]

    def infer(self, request: CoreRequest) -> InferenceEnvelope:
        text = request.message.strip()
        lower = text.lower()
        intent = self._infer_intent(lower)
        goals = self._infer_goals(lower)
        entities = self._infer_entities(text)
        constraints = self._infer_constraints(lower)
        domain_tags = self._infer_domain_tags(lower)
        confidence = self._infer_confidence(lower, intent)
        risk_score = self._infer_risk(lower)
        proposed_routes = self._propose_routes(lower, intent, domain_tags)
        required_approvals = self._required_approvals(lower, risk_score)

        return InferenceEnvelope(
            request_id=request.request_id,
            raw_message=text,
            intent=intent,
            goals=goals,
            entities=entities,
            constraints=constraints,
            domain_tags=domain_tags,
            confidence=confidence,
            risk_score=risk_score,
            proposed_routes=proposed_routes,
            required_approvals=required_approvals,
            provider=self.preferred_provider,
            provider_metadata={"available_providers": list(self.available_providers)},
        )

    def _infer_intent(self, lower: str) -> str:
        if any(k in lower for k in ["workflow", "automation", "pipeline"]):
            return "build_workflow"
        if any(k in lower for k in ["review", "approve", "gate", "compliance"]):
            return "review_or_gate"
        if any(k in lower for k in ["swarm", "agent", "crew"]):
            return "swarm_operation"
        if any(k in lower for k in ["execute", "run", "do "]):
            return "execute_task"
        return "chat_assistance"

    def _infer_goals(self, lower: str) -> List[str]:
        goals: List[str] = []
        if "build" in lower or "create" in lower:
            goals.append("construct_solution")
        if "fix" in lower or "repair" in lower:
            goals.append("repair_issue")
        if "deploy" in lower or "production" in lower:
            goals.append("productionize")
        if "review" in lower or "check" in lower:
            goals.append("review_output")
        return goals or ["respond_to_request"]

    def _infer_entities(self, text: str) -> Dict[str, Any]:
        quoted = re.findall(r'"([^"]+)"', text)
        repo_like = re.findall(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text)
        return {
            "quoted_terms": quoted,
            "repository_refs": repo_like,
        }

    def _infer_constraints(self, lower: str) -> Dict[str, Any]:
        return {
            "production": "production" in lower,
            "ui_required": any(k in lower for k in ["ui", "webapp", "frontend"]),
            "preserve_legacy": any(k in lower for k in ["preserve", "keep", "adapter", "legacy"]),
        }

    def _infer_domain_tags(self, lower: str) -> List[str]:
        tags: List[str] = []
        for key, tag in [
            ("billing", "finance"),
            ("invoice", "finance"),
            ("workflow", "automation"),
            ("automation", "automation"),
            ("swarm", "swarm"),
            ("voice", "voice"),
            ("meeting", "collaboration"),
            ("security", "security"),
            ("compliance", "compliance"),
            ("dashboard", "ui"),
            ("webapp", "ui"),
        ]:
            if key in lower and tag not in tags:
                tags.append(tag)
        return tags or ["general"]

    def _infer_confidence(self, lower: str, intent: str) -> float:
        score = 0.55
        if intent != "chat_assistance":
            score += 0.1
        if any(k in lower for k in ["exact", "strict", "canonical"]):
            score += 0.1
        if any(k in lower for k in ["maybe", "kinda", "sort of"]):
            score -= 0.15
        return max(0.05, min(score, 0.98))

    def _infer_risk(self, lower: str) -> float:
        risk = 0.1
        if any(k in lower for k in ["delete", "overwrite", "production", "deploy", "payment", "security"]):
            risk += 0.35
        if any(k in lower for k in ["customer", "billing", "wallet", "auth"]):
            risk += 0.2
        return min(risk, 0.95)

    def _propose_routes(self, lower: str, intent: str, domain_tags: List[str]) -> List[RouteType]:
        routes: List[RouteType] = []
        if "swarm" in lower or intent == "swarm_operation":
            routes.append(RouteType.SWARM)
        if any(tag in domain_tags for tag in ["automation", "security", "finance"]):
            routes.append(RouteType.SPECIALIST)
        if intent in ["build_workflow", "review_or_gate"]:
            routes.append(RouteType.HYBRID)
        routes.append(RouteType.DETERMINISTIC)
        return routes

    def _required_approvals(self, lower: str, risk_score: float) -> List[str]:
        approvals: List[str] = []
        if risk_score >= 0.4:
            approvals.append("hitl")
        if "compliance" in lower or "regulatory" in lower:
            approvals.append("compliance_review")
        if "budget" in lower or "billing" in lower:
            approvals.append("budget_review")
        return approvals
