from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class UIPhase:
    phase: str
    goal: str
    views: List[str] = field(default_factory=list)
    backend_dependencies: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "goal": self.goal,
            "views": list(self.views),
            "backend_dependencies": list(self.backend_dependencies),
            "notes": list(self.notes),
        }


class UIPhaseMap:
    """Machine-readable UI/admin rollout plan aligned to Murphy Core surfaces."""

    def __init__(self) -> None:
        self.phases: List[UIPhase] = [
            UIPhase(
                phase="phase_1_runtime_visibility",
                goal="Make runtime truth visible to operators and admin UI",
                views=[
                    "runtime_overview",
                    "deployment_mode_panel",
                    "provider_gate_health_panel",
                ],
                backend_dependencies=[
                    "/api/operator/runtime",
                    "/api/operator/runtime-summary",
                    "/api/readiness",
                ],
                notes=[
                    "Use unified runtime/operator surface first",
                    "Do not guess preferred boot path in UI",
                ],
            ),
            UIPhase(
                phase="phase_2_trace_and_gate_inspection",
                goal="Expose request traces, route choice, and gate rationale",
                views=[
                    "recent_traces",
                    "trace_detail",
                    "gate_decision_panel",
                ],
                backend_dependencies=[
                    "/api/traces/recent",
                    "/api/traces/{trace_id}",
                    "/api/chat",
                    "/api/execute",
                ],
                notes=[
                    "Show route and gate rationale alongside outcome",
                    "Highlight requires_hitl and blocked states",
                ],
            ),
            UIPhase(
                phase="phase_3_registry_and_capability_truth",
                goal="Expose what modules/capabilities are actually live or drifted",
                views=[
                    "module_registry",
                    "capability_truth",
                    "drift_panel",
                ],
                backend_dependencies=[
                    "/api/registry/modules",
                    "/api/capabilities/effective",
                    "/api/system/map",
                ],
                notes=[
                    "Prefer truthful status over pretty labels",
                    "Surface rollback and compatibility layers explicitly",
                ],
            ),
            UIPhase(
                phase="phase_4_legacy_migration_console",
                goal="Support operators during legacy-to-core migration",
                views=[
                    "legacy_compat_shell_status",
                    "migration_decision_panel",
                    "deployment_mode_switch_guidance",
                ],
                backend_dependencies=[
                    "/api/operator/runtime",
                    "/api/operator/runtime-summary",
                    "/api/system/map",
                ],
                notes=[
                    "Use when legacy compat shell remains in service",
                    "Show when direct core path is safe to prefer",
                ],
            ),
        ]

    def to_dict(self) -> Dict[str, object]:
        return {"phases": [phase.to_dict() for phase in self.phases]}
