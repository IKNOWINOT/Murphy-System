from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class RouteType(str, Enum):
    DETERMINISTIC = "deterministic"
    HYBRID = "hybrid"
    SPECIALIST = "specialist"
    SWARM = "swarm"
    LEGACY_ADAPTER = "legacy_adapter"


class GateDecision(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"
    REQUIRES_HITL = "requires_hitl"


class ModuleStatus(str, Enum):
    CORE = "core"
    ADAPTER = "adapter"
    OPTIONAL = "optional"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"
    DECLARED_ONLY = "declared_only"


class EffectiveCapability(str, Enum):
    LIVE = "live"
    AVAILABLE = "available"
    DISABLED = "disabled"
    MISSING_DEPENDENCY = "missing_dependency"
    NOT_WIRED = "not_wired"
    DRIFTED = "drifted"


@dataclass
class CoreRequest:
    request_id: str
    message: str
    session_id: Optional[str] = None
    mode: str = "chat"
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def new(cls, message: str, session_id: Optional[str] = None, mode: str = "chat",
            context: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None) -> "CoreRequest":
        return cls(
            request_id=f"req-{uuid4().hex[:12]}",
            message=message,
            session_id=session_id,
            mode=mode,
            context=context or {},
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InferenceEnvelope:
    request_id: str
    raw_message: str
    intent: str
    goals: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    domain_tags: List[str] = field(default_factory=list)
    confidence: float = 0.0
    risk_score: float = 0.0
    proposed_routes: List[RouteType] = field(default_factory=list)
    required_approvals: List[str] = field(default_factory=list)
    provider: str = "local_rules"
    provider_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["proposed_routes"] = [r.value for r in self.proposed_routes]
        return data


@dataclass
class RosettaEnvelope:
    request_id: str
    canonical_intent: str
    canonical_entities: Dict[str, Any] = field(default_factory=dict)
    canonical_constraints: Dict[str, Any] = field(default_factory=dict)
    canonical_domain_tags: List[str] = field(default_factory=list)
    allowed_module_classes: List[str] = field(default_factory=list)
    route_hints: List[RouteType] = field(default_factory=list)
    normalization_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["route_hints"] = [r.value for r in self.route_hints]
        return data


@dataclass
class GateEvaluation:
    gate_name: str
    decision: GateDecision
    rationale: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        return data


@dataclass
class ControlExpansion:
    request_id: str
    selected_route: RouteType
    selected_module_families: List[str] = field(default_factory=list)
    execution_constraints: Dict[str, Any] = field(default_factory=dict)
    allowed_actions: List[Dict[str, Any]] = field(default_factory=list)
    fallback_policy: Dict[str, Any] = field(default_factory=dict)
    approval_requirements: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["selected_route"] = self.selected_route.value
        return data


@dataclass
class GatedExecutionPlan:
    request_id: str
    route: RouteType
    steps: List[Dict[str, Any]] = field(default_factory=list)
    gate_results: List[GateEvaluation] = field(default_factory=list)
    selected_module_families: List[str] = field(default_factory=list)
    execution_constraints: Dict[str, Any] = field(default_factory=dict)
    allowed_actions: List[Dict[str, Any]] = field(default_factory=list)
    fallback_policy: Dict[str, Any] = field(default_factory=dict)
    enforcement_summary: Dict[str, Any] = field(default_factory=dict)
    gate_enforcement_summary: Dict[str, Any] = field(default_factory=dict)
    blocked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "route": self.route.value,
            "steps": self.steps,
            "gate_results": [g.to_dict() for g in self.gate_results],
            "selected_module_families": list(self.selected_module_families),
            "execution_constraints": dict(self.execution_constraints),
            "allowed_actions": [dict(action) for action in self.allowed_actions],
            "fallback_policy": dict(self.fallback_policy),
            "enforcement_summary": dict(self.enforcement_summary),
            "gate_enforcement_summary": dict(self.gate_enforcement_summary),
            "blocked": self.blocked,
        }


@dataclass
class ModuleRecord:
    module_name: str
    source_path: Optional[str] = None
    present_in_baseline: bool = False
    present_in_manifest: bool = False
    source_exists: bool = False
    category: str = "unknown"
    runtime_role: str = "unknown"
    status: ModuleStatus = ModuleStatus.DECLARED_ONLY
    effective_capability: EffectiveCapability = EffectiveCapability.NOT_WIRED
    commands: List[str] = field(default_factory=list)
    persona: Optional[str] = None
    emits: List[str] = field(default_factory=list)
    consumes: List[str] = field(default_factory=list)
    used_by_runtime: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["effective_capability"] = self.effective_capability.value
        return data


@dataclass
class ControlTrace:
    trace_id: str
    request_id: str
    request_summary: Dict[str, Any]
    inference_summary: Dict[str, Any] = field(default_factory=dict)
    rosetta_summary: Dict[str, Any] = field(default_factory=dict)
    gate_summaries: List[Dict[str, Any]] = field(default_factory=list)
    route: Optional[str] = None
    selected_modules: List[str] = field(default_factory=list)
    execution_status: str = "created"
    outcome: Dict[str, Any] = field(default_factory=dict)
    recovery: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def new(cls, request: CoreRequest) -> "ControlTrace":
        return cls(
            trace_id=f"trace-{uuid4().hex[:12]}",
            request_id=request.request_id,
            request_summary=request.to_dict(),
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
