"""
Deterministic Compute Plane — dispatch layer.

Routes tasks through the DeterministicRoutingEngine to determine whether they
require deterministic (math/logic) or LLM processing, then dispatches
deterministic tasks to the ComputeService for verified execution.

This is the real dispatch layer — not a pass-through alias.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeterministicComputePlane:
    """Dispatch layer that wires DeterministicRoutingEngine → ComputeService.

    For *deterministic* tasks the routing engine decides the route and the
    compute service executes the mathematical workload.  LLM and hybrid tasks
    are returned to the caller with routing metadata so the higher-level
    orchestrator can forward them to the appropriate inference backend.
    """

    def __init__(self):
        from src.compute_plane.models.compute_request import ComputeRequest
        from src.compute_plane.service import ComputeService
        from src.deterministic_routing_engine import DeterministicRoutingEngine

        self._router = DeterministicRoutingEngine()
        self._compute = ComputeService()
        self._ComputeRequest = ComputeRequest

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(
        self,
        task_type: str,
        expression: str,
        language: str = "sympy",
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
        runtime_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Route and execute a task.

        1. Asks the routing engine to classify the task.
        2. For *deterministic* tasks: submits expression to ComputeService
           and waits for a verified result.
        3. For *llm* / *hybrid* tasks: returns the routing decision so the
           caller can forward the task to the appropriate backend.

        Returns a dict that always contains:
          - ``route_type``: "deterministic" | "llm" | "hybrid"
          - ``routing_decision``: the full routing decision dict
          - ``status``: "computed" | "deferred_to_llm" | "deferred_to_hybrid"
          - For deterministic routes: ``compute_result`` with the verified answer
        """
        routing = self._router.route_task(
            task_type=task_type,
            tags=tags,
            confidence=confidence,
            context=context,
            runtime_config=runtime_config,
        )
        route_type = routing.get("route_type", "deterministic")

        if route_type == "deterministic":
            return self._execute_deterministic(expression, language, routing)

        # Non-deterministic: return routing metadata for the caller to forward
        status = "deferred_to_llm" if route_type == "llm" else "deferred_to_hybrid"
        return {
            "route_type": route_type,
            "routing_decision": routing,
            "status": status,
            "expression": expression,
            "language": language,
        }

    def validate(self, expression: str, language: str = "sympy") -> Dict[str, Any]:
        """Validate a mathematical expression without executing it."""
        return self._compute.validate_expression(expression, language)

    def get_routing_stats(self) -> Dict[str, Any]:
        """Return aggregate routing statistics from the routing engine."""
        return self._router.get_routing_stats()

    def get_status(self) -> Dict[str, Any]:
        """Return combined status of the routing engine and compute service."""
        router_status = self._router.get_status()
        compute_stats = self._compute.get_statistics()
        return {
            "routing_engine": router_status,
            "compute_service": compute_stats,
            "status": "active",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_deterministic(
        self, expression: str, language: str, routing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit expression to ComputeService and return unified result."""
        try:
            request_id = self._compute.submit_request(
                self._ComputeRequest(
                    expression=expression,
                    language=language,
                )
            )
            result = self._compute.get_result(request_id)
            if result is None:
                return {
                    "route_type": "deterministic",
                    "routing_decision": routing,
                    "status": "error",
                    "error": "Compute service returned no result",
                }
            return {
                "route_type": "deterministic",
                "routing_decision": routing,
                "status": "computed",
                "compute_result": {
                    "request_id": result.request_id,
                    "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                    "result": result.result,
                    "is_deterministic": result.is_deterministic,
                    "confidence": result.confidence,
                    "computation_time": result.computation_time,
                    "language": result.language,
                },
            }
        except Exception as exc:
            logger.warning("Deterministic dispatch error: %s", exc)
            return {
                "route_type": "deterministic",
                "routing_decision": routing,
                "status": "error",
                "error": str(exc),
            }


__all__ = ["DeterministicComputePlane"]
