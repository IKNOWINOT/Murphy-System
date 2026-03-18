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
        blocked = any(g.decision == GateDecision.BLOCK for g in gate_results)
        steps = self._steps_from_route(expansion, source_message)
        return GatedExecutionPlan(
            request_id=expansion.request_id,
            route=expansion.selected_route,
            steps=steps,
            gate_results=gate_results,
            blocked=blocked,
        )

    def _allowed_actions(self, inference: InferenceEnvelope, rosetta: RosettaEnvelope, route: RouteType) -> List[dict]:
        actions = [
            {"action": "respond", "type": "ui_response"},
            {"action": "trace", "type": "audit"},
        ]
        if route in {RouteType.DETERMINISTIC, RouteType.HYBRID, RouteType.SPECIALIST}:
            actions.append({"action": "execute", "type": "typed_execution"})
        if route == RouteType.SWARM:
            actions.append({"action": "swarm_execute", "type": "typed_swarm"})
        return actions

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
