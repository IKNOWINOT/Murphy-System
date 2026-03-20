from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .contracts import CoreRequest, InferenceEnvelope, RouteType


@dataclass
class ProviderHealth:
    provider_name: str
    available: bool
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class InferenceProviderAdapter(Protocol):
    provider_name: str

    def health(self) -> ProviderHealth:
        ...

    def infer(self, request: CoreRequest) -> InferenceEnvelope:
        ...


class LocalRulesAdapter:
    provider_name = "local_rules"

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider_name=self.provider_name, available=True)

    def infer(self, request: CoreRequest) -> InferenceEnvelope:
        text = request.message.strip()
        lower = text.lower()
        intent = "chat_assistance"
        if any(k in lower for k in ["workflow", "automation", "pipeline"]):
            intent = "build_workflow"
        elif any(k in lower for k in ["review", "approve", "gate", "compliance"]):
            intent = "review_or_gate"
        elif any(k in lower for k in ["swarm", "agent", "crew"]):
            intent = "swarm_operation"
        elif any(k in lower for k in ["execute", "run", "do "]):
            intent = "execute_task"

        goals: List[str] = []
        if "build" in lower or "create" in lower:
            goals.append("construct_solution")
        if "fix" in lower or "repair" in lower:
            goals.append("repair_issue")
        if "deploy" in lower or "production" in lower:
            goals.append("productionize")
        if "review" in lower or "check" in lower:
            goals.append("review_output")
        if not goals:
            goals = ["respond_to_request"]

        domain_tags: List[str] = []
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
            if key in lower and tag not in domain_tags:
                domain_tags.append(tag)
        if not domain_tags:
            domain_tags = ["general"]

        confidence = 0.55 + (0.1 if intent != "chat_assistance" else 0.0)
        if any(k in lower for k in ["exact", "strict", "canonical"]):
            confidence += 0.1
        if any(k in lower for k in ["maybe", "kinda", "sort of"]):
            confidence -= 0.15
        confidence = max(0.05, min(confidence, 0.98))

        risk = 0.1
        if any(k in lower for k in ["delete", "overwrite", "production", "deploy", "payment", "security"]):
            risk += 0.35
        if any(k in lower for k in ["customer", "billing", "wallet", "auth"]):
            risk += 0.2
        risk = min(risk, 0.95)

        proposed_routes: List[RouteType] = []
        if "swarm" in lower or intent == "swarm_operation":
            proposed_routes.append(RouteType.SWARM)
        if any(tag in domain_tags for tag in ["automation", "security", "finance"]):
            proposed_routes.append(RouteType.SPECIALIST)
        if intent in ["build_workflow", "review_or_gate"]:
            proposed_routes.append(RouteType.HYBRID)
        proposed_routes.append(RouteType.DETERMINISTIC)

        scope_info = self._scope_info(request, lower)
        required_approvals: List[str] = []
        if scope_info["platform_change"]:
            required_approvals.append("founder_hitl")
        elif scope_info["organization_change"]:
            required_approvals.append("org_hitl")
        elif risk >= 0.4:
            required_approvals.append("hitl")
        if "compliance" in lower or "regulatory" in lower:
            required_approvals.append("compliance_review")
        if "budget" in lower or "billing" in lower:
            required_approvals.append("budget_review")

        return InferenceEnvelope(
            request_id=request.request_id,
            raw_message=text,
            intent=intent,
            goals=goals,
            entities={"raw_length": len(text)},
            constraints={
                "production": "production" in lower,
                "ui_required": any(k in lower for k in ["ui", "webapp", "frontend"]),
                "preserve_legacy": any(k in lower for k in ["preserve", "keep", "adapter", "legacy"]),
                "target_scope": scope_info["target_scope"],
                "platform_change": scope_info["platform_change"],
                "organization_change": scope_info["organization_change"],
            },
            domain_tags=domain_tags,
            confidence=confidence,
            risk_score=risk,
            proposed_routes=proposed_routes,
            required_approvals=required_approvals,
            provider=self.provider_name,
            provider_metadata={"adapter": self.provider_name, **scope_info},
        )

    def _scope_info(self, request: CoreRequest, lower: str) -> Dict[str, Any]:
        context = request.context or {}
        explicit_scope = str(context.get("target_scope") or context.get("change_scope") or "").lower()
        platform_change = bool(context.get("platform_change"))
        organization_change = bool(context.get("organization_change"))

        platform_keywords = [
            "platform",
            "runtime",
            "boot path",
            "startup",
            "core system",
            "system-wide",
            "founder workstation",
            "codebase",
            "module",
            "repo",
            "repository",
            "patch platform",
            "change the platform",
            "add code",
            "coding addition",
        ]
        organization_keywords = [
            "organization",
            "org ",
            "workspace",
            "team",
            "tenant",
            "company settings",
            "department",
        ]

        if explicit_scope == "platform":
            platform_change = True
        elif explicit_scope in {"organization", "org"}:
            organization_change = True

        if any(keyword in lower for keyword in platform_keywords):
            platform_change = True
        if any(keyword in lower for keyword in organization_keywords):
            organization_change = True

        if platform_change:
            target_scope = "platform"
            organization_change = False
        elif organization_change:
            target_scope = "organization"
        else:
            target_scope = "user"

        return {
            "target_scope": target_scope,
            "platform_change": platform_change,
            "organization_change": organization_change,
        }


class LegacyMurphyInferenceAdapter:
    provider_name = "legacy_murphy"

    def __init__(self) -> None:
        self._murphy = None
        try:
            from src.runtime.murphy_system_core import MurphySystem
            self._murphy = MurphySystem()
        except Exception:
            self._murphy = None

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.provider_name,
            available=self._murphy is not None,
            reason=None if self._murphy is not None else "MurphySystem unavailable",
        )

    def infer(self, request: CoreRequest) -> InferenceEnvelope:
        lower = request.message.lower()
        return InferenceEnvelope(
            request_id=request.request_id,
            raw_message=request.message,
            intent="execute_task" if any(k in lower for k in ["execute", "run"]) else "chat_assistance",
            goals=["legacy_assisted_inference"],
            entities={"source": "legacy_murphy"},
            constraints={"production": "production" in lower, "target_scope": "user", "platform_change": False, "organization_change": False},
            domain_tags=["general"],
            confidence=0.6 if self._murphy is not None else 0.2,
            risk_score=0.2,
            proposed_routes=[RouteType.HYBRID, RouteType.DETERMINISTIC],
            required_approvals=[],
            provider=self.provider_name,
            provider_metadata={"adapter": self.provider_name, "available": self._murphy is not None, "target_scope": "user", "platform_change": False, "organization_change": False},
        )
