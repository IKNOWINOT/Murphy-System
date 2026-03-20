from __future__ import annotations

from typing import Any, Dict

from .contracts import CoreRequest, GatedExecutionPlan, RouteType


class CoreExecutor:
    """Execute typed plans through Murphy Core adapters.

    Preserves existing runtime by delegating into legacy MurphySystem when possible.
    """

    def __init__(self) -> None:
        self._murphy = None
        self._swarm = None
        try:
            from src.runtime.murphy_system_core import MurphySystem
            self._murphy = MurphySystem()
        except Exception:
            self._murphy = None
        try:
            from src.self_codebase_swarm import SelfCodebaseSwarm
            self._swarm = SelfCodebaseSwarm()
        except Exception:
            self._swarm = None

    async def execute(self, request: CoreRequest, plan: GatedExecutionPlan) -> Dict[str, Any]:
        validation = self._validate_plan(request, plan)
        gate_summary = dict(plan.gate_enforcement_summary)

        if validation["blocked"]:
            return {
                "success": False,
                "status": "blocked",
                "message": "Execution blocked by plan enforcement",
                "route": plan.route.value,
                "steps": plan.steps,
                "selected_module_families": plan.selected_module_families,
                "execution_constraints": plan.execution_constraints,
                "fallback_policy": plan.fallback_policy,
                "enforcement_summary": validation,
                "gate_enforcement_summary": gate_summary,
            }

        if gate_summary.get("requires_hitl"):
            return {
                "success": False,
                "status": "hitl_required",
                "message": "Execution paused pending HITL approval",
                "route": plan.route.value,
                "steps": plan.steps,
                "selected_module_families": plan.selected_module_families,
                "execution_constraints": plan.execution_constraints,
                "fallback_policy": plan.fallback_policy,
                "enforcement_summary": validation,
                "gate_enforcement_summary": gate_summary,
            }

        if gate_summary.get("requires_review"):
            return {
                "success": False,
                "status": "review_required",
                "message": "Execution paused pending review",
                "route": plan.route.value,
                "steps": plan.steps,
                "selected_module_families": plan.selected_module_families,
                "execution_constraints": plan.execution_constraints,
                "fallback_policy": plan.fallback_policy,
                "enforcement_summary": validation,
                "gate_enforcement_summary": gate_summary,
            }

        if plan.blocked:
            fallback_result = await self._attempt_fallback(request, plan, validation, gate_summary)
            if fallback_result is not None:
                return fallback_result
            return {
                "success": False,
                "status": "blocked",
                "message": "Execution blocked by gate pipeline",
                "route": plan.route.value,
                "steps": plan.steps,
                "selected_module_families": plan.selected_module_families,
                "execution_constraints": plan.execution_constraints,
                "fallback_policy": plan.fallback_policy,
                "enforcement_summary": validation,
                "gate_enforcement_summary": gate_summary,
            }

        if plan.route == RouteType.SWARM and self._swarm is not None:
            proposal = self._swarm.propose_change(request.message)
            return {
                "success": True,
                "status": "swarm_planned",
                "route": plan.route.value,
                "proposal": proposal.to_dict(),
                "steps": plan.steps,
                "selected_module_families": plan.selected_module_families,
                "execution_constraints": plan.execution_constraints,
                "fallback_policy": plan.fallback_policy,
                "enforcement_summary": validation,
                "gate_enforcement_summary": gate_summary,
            }

        if self._murphy is not None:
            if request.mode == "chat":
                result = self._murphy.handle_chat(
                    message=request.message,
                    session_id=request.session_id,
                    use_mfgc=True,
                )
                return {
                    "success": True,
                    "status": "completed",
                    "route": plan.route.value,
                    "result": result,
                    "steps": plan.steps,
                    "selected_module_families": plan.selected_module_families,
                    "execution_constraints": plan.execution_constraints,
                    "fallback_policy": plan.fallback_policy,
                    "enforcement_summary": validation,
                    "gate_enforcement_summary": gate_summary,
                }
            result = await self._murphy.execute_task(
                task_description=request.message,
                task_type="general",
                parameters=request.context,
                session_id=request.session_id,
            )
            return {
                "success": True,
                "status": "completed",
                "route": plan.route.value,
                "result": result,
                "steps": plan.steps,
                "selected_module_families": plan.selected_module_families,
                "execution_constraints": plan.execution_constraints,
                "fallback_policy": plan.fallback_policy,
                "enforcement_summary": validation,
                "gate_enforcement_summary": gate_summary,
            }

        return {
            "success": True,
            "status": "simulated",
            "route": plan.route.value,
            "message": request.message,
            "steps": plan.steps,
            "selected_module_families": plan.selected_module_families,
            "execution_constraints": plan.execution_constraints,
            "fallback_policy": plan.fallback_policy,
            "enforcement_summary": validation,
            "gate_enforcement_summary": gate_summary,
        }

    async def _attempt_fallback(
        self,
        request: CoreRequest,
        plan: GatedExecutionPlan,
        validation: Dict[str, Any],
        gate_summary: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        fallback_policy = dict(plan.fallback_policy)
        fallback_route = fallback_policy.get("fallback_route")
        allow_automatic_fallback = bool(fallback_policy.get("allow_automatic_fallback"))
        fallback_on_block = bool(fallback_policy.get("fallback_on_block", True))
        fallback_on_review = bool(fallback_policy.get("fallback_on_review", False))
        fallback_on_hitl = bool(fallback_policy.get("fallback_on_hitl", False))

        if fallback_route != RouteType.LEGACY_ADAPTER.value:
            return None
        if not allow_automatic_fallback:
            return None
        if gate_summary.get("requires_review") and not fallback_on_review:
            return None
        if gate_summary.get("requires_hitl") and not fallback_on_hitl:
            return None
        if not gate_summary.get("blocking_gates") and not fallback_on_block:
            return None

        fallback_result = await self._execute_legacy_adapter_fallback(request)
        return {
            "success": True,
            "status": "fallback_completed",
            "route": plan.route.value,
            "fallback_route": fallback_route,
            "steps": plan.steps,
            "selected_module_families": plan.selected_module_families,
            "execution_constraints": plan.execution_constraints,
            "fallback_policy": fallback_policy,
            "enforcement_summary": validation,
            "gate_enforcement_summary": gate_summary,
            "fallback_result": fallback_result,
        }

    async def _execute_legacy_adapter_fallback(self, request: CoreRequest) -> Dict[str, Any]:
        if self._murphy is not None:
            if request.mode == "chat":
                result = self._murphy.handle_chat(
                    message=request.message,
                    session_id=request.session_id,
                    use_mfgc=False,
                )
                return {"adapter": RouteType.LEGACY_ADAPTER.value, "result": result}
            result = await self._murphy.execute_task(
                task_description=request.message,
                task_type="general",
                parameters=request.context,
                session_id=request.session_id,
            )
            return {"adapter": RouteType.LEGACY_ADAPTER.value, "result": result}

        return {
            "adapter": RouteType.LEGACY_ADAPTER.value,
            "status": "simulated",
            "message": request.message,
        }

    def _validate_plan(self, request: CoreRequest, plan: GatedExecutionPlan) -> Dict[str, Any]:
        reasons = list(plan.enforcement_summary.get("reasons", []))
        allowed_actions = {action.get("action") for action in plan.allowed_actions}
        primary_family = plan.execution_constraints.get("primary_family")
        selected_families = list(plan.selected_module_families)

        if primary_family and selected_families and primary_family not in selected_families:
            reasons.append("executor_primary_family_missing_from_selected_module_families")

        if plan.route == RouteType.SWARM:
            if "swarm_execute" not in allowed_actions:
                reasons.append("executor_swarm_route_missing_swarm_execute_action")
            if primary_family and primary_family != "swarm":
                reasons.append("executor_swarm_route_primary_family_mismatch")
        else:
            if "execute" not in allowed_actions:
                reasons.append("executor_non_swarm_route_missing_execute_action")

        return {
            "checked": True,
            "blocked": bool(reasons),
            "reasons": reasons,
            "request_mode": request.mode,
            "route": plan.route.value,
            "primary_family": primary_family,
            "selected_module_families": selected_families,
            "allowed_actions": sorted(action for action in allowed_actions if action),
        }
