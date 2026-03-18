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
        if plan.blocked:
            return {
                "success": False,
                "status": "blocked",
                "message": "Execution blocked by gate pipeline",
                "route": plan.route.value,
                "steps": plan.steps,
            }

        if plan.route == RouteType.SWARM and self._swarm is not None:
            proposal = self._swarm.propose_change(request.message)
            return {
                "success": True,
                "status": "swarm_planned",
                "route": plan.route.value,
                "proposal": proposal.to_dict(),
                "steps": plan.steps,
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
            }

        return {
            "success": True,
            "status": "simulated",
            "route": plan.route.value,
            "message": request.message,
            "steps": plan.steps,
        }
