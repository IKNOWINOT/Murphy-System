from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class OperationsPhase:
    phase: str
    goal: str
    operator_tasks: List[str] = field(default_factory=list)
    required_surfaces: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "goal": self.goal,
            "operator_tasks": list(self.operator_tasks),
            "required_surfaces": list(self.required_surfaces),
            "notes": list(self.notes),
        }


class OperationsPhaseMap:
    """Machine-readable operations rollout plan aligned to Murphy Core."""

    def __init__(self) -> None:
        self.phases: List[OperationsPhase] = [
            OperationsPhase(
                phase="phase_1_boot_path_control",
                goal="Standardize boot path and deployment mode selection",
                operator_tasks=[
                    "choose direct core runtime-correct vs legacy compat shell",
                    "verify startup entrypoint in deployment config",
                    "confirm preferred path in runtime summary",
                ],
                required_surfaces=[
                    "/api/operator/runtime-summary",
                    "/api/readiness",
                ],
                notes=[
                    "Do not let deployment choose a path implicitly",
                    "Record whether deployment is canonical or transitional",
                ],
            ),
            OperationsPhase(
                phase="phase_2_health_and_trace_observability",
                goal="Make runtime health and request behavior observable",
                operator_tasks=[
                    "monitor provider health",
                    "monitor gate health",
                    "inspect recent traces for blocked or HITL-heavy flows",
                ],
                required_surfaces=[
                    "/api/readiness",
                    "/api/traces/recent",
                    "/api/operator/status",
                ],
                notes=[
                    "Use traces to identify unstable routes or gate bottlenecks",
                ],
            ),
            OperationsPhase(
                phase="phase_3_drift_and_registry_control",
                goal="Track what is live, drifted, compatibility-only, or rollback-only",
                operator_tasks=[
                    "review registry truth",
                    "review drifted module set",
                    "review runtime lineage before promoting a new path",
                ],
                required_surfaces=[
                    "/api/registry/modules",
                    "/api/capabilities/effective",
                    "/api/operator/runtime",
                ],
                notes=[
                    "Prefer honest rollback labeling over silent ambiguity",
                ],
            ),
            OperationsPhase(
                phase="phase_4_legacy_decommissioning",
                goal="Reduce monolith dependence while preserving safe rollback",
                operator_tasks=[
                    "run through legacy compat shell only where required",
                    "promote direct core runtime-correct path when safe",
                    "track which legacy endpoint families remain in passthrough",
                ],
                required_surfaces=[
                    "/api/operator/runtime",
                    "/api/system/map",
                    "/api/operator/runtime-summary",
                ],
                notes=[
                    "Legacy decommissioning should be incremental and traceable",
                ],
            ),
        ]

    def to_dict(self) -> Dict[str, object]:
        return {"phases": [phase.to_dict() for phase in self.phases]}
