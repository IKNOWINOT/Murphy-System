from __future__ import annotations

from typing import List, Optional

from .contracts import ControlExpansion, GateDecision, GateEvaluation, InferenceEnvelope, RosettaEnvelope, RouteType


class CoreRouter:
    """Murphy Core router.

    Uses Rosetta route hints first, then falls back to legacy routing engines where useful.
    """

    def __init__(self) -> None:
        self._deterministic_engine = None
        self._control_plane = None
        try:
            from src.deterministic_routing_engine import DeterministicRoutingEngine
            self._deterministic_engine = DeterministicRoutingEngine()
        except Exception:
            self._deterministic_engine = None
        try:
            from src.control_plane_separation import ControlPlaneSeparation
            self._control_plane = ControlPlaneSeparation()
        except Exception:
            self._control_plane = None

    def select_route(
        self,
        inference: InferenceEnvelope,
        rosetta: RosettaEnvelope,
        gate_results: List[GateEvaluation],
    ) -> RouteType:
        if any(g.decision == GateDecision.BLOCK for g in gate_results):
            return RouteType.LEGACY_ADAPTER

        if rosetta.route_hints:
            hint = rosetta.route_hints[0]
            if hint in {RouteType.SWARM, RouteType.SPECIALIST, RouteType.HYBRID, RouteType.DETERMINISTIC}:
                return hint

        if self._deterministic_engine is not None:
            try:
                decision = self._deterministic_engine.route_task(
                    task_type=inference.intent,
                    tags=inference.domain_tags,
                    confidence=inference.confidence,
                    context={"production": inference.constraints.get("production", False)},
                )
                route_type = decision.get("route_type", "deterministic")
                if route_type == "llm":
                    return RouteType.HYBRID
                if route_type == "hybrid":
                    return RouteType.HYBRID
                return RouteType.DETERMINISTIC
            except Exception:
                pass

        return RouteType.DETERMINISTIC

    def runtime_hints(self) -> dict:
        return {
            "deterministic_engine": self._deterministic_engine is not None,
            "control_plane": self._control_plane is not None,
        }
