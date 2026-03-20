from __future__ import annotations

from typing import List

from .contracts import ControlExpansion, GatedExecutionPlan, GateDecision, GateEvaluation, InferenceEnvelope, RosettaEnvelope, RouteType


class CorePlanner:
    """Compile normalized inference into typed control and execution plans."""

    def __init__(self) -> None:
        self._workflow_generator = None
        try:
            from src.ai_workflow_generator import AIWorkflowGenerator
            self._workflow_generator = AIWorkflowGenerator()
        except Exception:
            self._workflow_generator = None

    def expand(
        self,
        inference: InferenceEnvelope,
        rosetta: RosettaEnvelope,
        route: RouteType,
    ) -> ControlExpansion:
        module_families = list(rosetta.allowed_module_classes)
        allowed_actions = self._allowed_actions(inference, rosetta, route)
        return ControlExpansion(
            request_id=inference.request_id,
            selected_route=route,
            selected_module_families=module_families,
            execution_constraints=dict(rosetta.canonical_constraints),
            allowed_actions=allowed_actions,
            fallback_policy={"fallback_route": RouteType.LEGACY_ADAPTER.value},
            approval_requirements=list(inference.required_approvals),
            expected_outputs=["response", "trace"],
        )

    def compile_plan(
        self,
        expansion: ControlExpansion,
        gate_results: List[GateEvaluation],
        source_message: str,
    ) -> GatedExecutionPlan:
        gate_enforcement_summary = self._gate_enforcement_summary(gate_results, expansion)
        blocked = gate_enforcement_summary["blocked"]
        enforcement_summary = self._enforcement_summary(expansion)
        blocked = blocked or enforcement_summary["blocked"]
        steps = self._steps_from_route(expansion, source_message)
        return GatedExecutionPlan(
            request_id=expansion.request_id,
            route=expansion.selected_route,
            steps=steps,
            gate_results=gate_results,
            selected_module_families=list(expansion.selected_module_families),
            execution_constraints=dict(expansion.execution_constraints),
            allowed_actions=[dict(action) for action in expansion.allowed_actions],
            fallback_policy=dict(expansion.fallback_policy),
            enforcement_summary=enforcement_summary,
            gate_enforcement_summary=gate_enforcement_summary,
            blocked=blocked,
        )

    def _allowed_actions(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope, route: RouteType) -> List[dict]:
        actions = [
            {"action": "respond", "type": "ui_response"},
            {"action": "trace", "type": "audit"},
        ]
        if route in {RouteType.DETERMINISTIC, RouteType.HYBRID, RouteType.SPECIALIST, RouteType.LEGACY_ADAPTER}:
            actions.append({"action": "execute", "type": "typed_execution"})
        if route == RouteType.SWARM:
            actions.append({"action": "swarm_execute", "type": "typed_swarm"})
        return actions

    def _gate_enforcement_summary(self, gate_results: List[GateEvaluation], expansion: ControlExpansion) -> dict:
        blocking_reasons: List[str] = []
        review_reasons: List[str] = []
        hitl_reasons: List[str] = []

        for gate in gate_results:
            if gate.decision == GateDecision.BLOCK:
                blocking_reasons.append(gate.gate_name)
            elif gate.decision == GateDecision.REVIEW:
                review_reasons.append(gate.gate_name)
            elif gate.decision == GateDecision.REQUIRES_HITL:
                hitl_reasons.append(gate.gate_name)

        fallback_route = expansion.fallback_policy.get("fallback_route") or RouteType.LEGACY_ADAPTER.value
        return {
            "checked": True,
            "blocked": bool(blocking_reasons or review_reasons or hitl_reasons),
            "blocking_gates": blocking_reasons,
            "review_gates": review_reasons,
            "hitl_gates": hitl_reasons,
            "requires_review": bool(review_reasons),
            "requires_hitl": bool(hitl_reasons),
            "fallback_route": fallback_route,
            "fallback_available": fallback_route == RouteType.LEGACY_ADAPTER.value,
        }

    def _enforcement_summary(self, expansion: ControlExpansion) -> dict:
        primary_family = expansion.execution_constraints.get("primary_family")
        selected_families = list(expansion.selected_module_families)
        selected_actions = {action.get("action") for action in expansion.allowed_actions}
        reasons: List[str] = []

        if primary_family and selected_families and primary_family not in selected_families:
            reasons.append("primary_family_missing_from_selected_module_families")

        if expansion.selected_route == RouteType.SWARM and "swarm_execute" not in selected_actions:
            reasons.append("swarm_route_missing_swarm_execute_action")

        if expansion.selected_route != RouteType.SWARM and "execute" not in selected_actions:
            reasons.append("non_swarm_route_missing_execute_action")

        return {
            "checked": True,
            "blocked": bool(reasons),
            "reasons": reasons,
            "primary_family": primary_family,
            "selected_module_families": selected_families,
            "selected_actions": sorted(action for action in selected_actions if action),
        }

    def _steps_from_route(self, expansion: ControlExpansion, source_message: str) -> List[dict]:
        if self._workflow_generator is not None and expansion.selected_route in {RouteType.HYBRID, RouteType.SPECIALIST}:
            try:
                workflow = self._workflow_generator.generate_workflow(source_message)
                return [
                    {
                        "step_name": step["name"],
                        "step_type": step["type"],
                        "description": step.get("description", ""),
                        "depends_on": step.get("depends_on", []),
                    }
                    for step in workflow.get("steps", [])
                ]
            except Exception:
                pass

        if expansion.selected_route == RouteType.SWARM:
            return [
                {"step_name": "prepare_swarm", "step_type": "swarm.prepare", "description": "Prepare swarm execution envelope", "depends_on": []},
                {"step_name": "execute_swarm", "step_type": "swarm.execute", "description": "Execute through swarm adapter", "depends_on": ["prepare_swarm"]},
            ]

        return [
            {"step_name": "prepare_request", "step_type": "core.prepare", "description": "Prepare typed execution payload", "depends_on": []},
            {"step_name": "execute_route", "step_type": f"route.{expansion.selected_route.value}", "description": "Execute selected route", "depends_on": ["prepare_request"]},
        ]
