"""
Finish Line Controller for Murphy System Runtime

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

This module orchestrates multiple closures and manages system-wide
wind-down scenarios. It builds prioritised wind-down plans across many
targets, estimates cost savings, and makes AI-style recommendations on
what to close to hit a budget target.

Key capabilities:
- Four wind-down strategies (immediate, graceful, phased, budget_driven)
- Multi-target closure orchestration via ClosureEngine
- Cost-savings estimation and recommendation generation
- Wind-down plan lifecycle (plan → execute → status)
- Thread-safe operation
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Wind-down strategy
# ---------------------------------------------------------------------------

class WindDownStrategy(str, Enum):
    """Strategy used when closing multiple targets."""

    IMMEDIATE = "immediate"
    GRACEFUL = "graceful"
    PHASED = "phased"
    BUDGET_DRIVEN = "budget_driven"


# ---------------------------------------------------------------------------
# FinishLineController
# ---------------------------------------------------------------------------

class FinishLineController:
    """Orchestrates multi-target wind-downs for Murphy System.

    Zero-config usage::

        controller = FinishLineController()
        plan = controller.plan_wind_down(targets, strategy="graceful")
        result = controller.execute_wind_down(plan["plan_id"])
    """

    def __init__(
        self,
        closure_engine=None,
        wingman_protocol=None,
    ) -> None:
        from closure_engine import ClosureEngine

        self._lock = threading.Lock()
        self._plans: Dict[str, Dict[str, Any]] = {}

        if closure_engine is None:
            if wingman_protocol is not None:
                self._engine = ClosureEngine(wingman_protocol=wingman_protocol)
            else:
                self._engine = ClosureEngine()
        else:
            self._engine = closure_engine

        logger.info("FinishLineController initialised")

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def plan_wind_down(
        self,
        targets: List[Dict[str, Any]],
        strategy: str = "graceful",
    ) -> Dict[str, Any]:
        """Create a wind-down plan for multiple targets.

        Targets are ordered by priority, dependencies, and budget status
        according to the chosen strategy.

        Returns ``{plan_id, strategy, phases, estimated_duration, estimated_savings}``.
        """
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        now = _utcnow()

        try:
            resolved_strategy = WindDownStrategy(strategy)
        except ValueError:
            resolved_strategy = WindDownStrategy.GRACEFUL

        ordered = self._order_targets(targets, resolved_strategy)

        phases: List[Dict[str, Any]] = []
        if resolved_strategy == WindDownStrategy.PHASED:
            # Group into priority buckets: high → medium → low
            high = [t for t in ordered if t.get("priority", "medium") == "high"]
            medium = [t for t in ordered if t.get("priority", "medium") == "medium"]
            low = [t for t in ordered if t.get("priority", "medium") == "low"]
            for idx, bucket in enumerate([high, medium, low], start=1):
                if bucket:
                    phases.append({
                        "phase_number": idx,
                        "label": ["high_priority", "medium_priority", "low_priority"][idx - 1],
                        "targets": [t.get("target_id") for t in bucket],
                    })
        else:
            phases.append({
                "phase_number": 1,
                "label": resolved_strategy.value,
                "targets": [t.get("target_id") for t in ordered],
            })

        savings_estimate = self.estimate_savings(targets)
        per_target_ms = 500 if resolved_strategy == WindDownStrategy.IMMEDIATE else 2000
        estimated_duration = len(targets) * per_target_ms

        plan: Dict[str, Any] = {
            "plan_id": plan_id,
            "strategy": resolved_strategy.value,
            "targets": ordered,
            "phases": phases,
            "estimated_duration_ms": estimated_duration,
            "estimated_savings": savings_estimate,
            "status": "planned",
            "created_at": now,
            "executed_at": "",
            "completed_at": "",
            "target_results": {},
        }

        with self._lock:
            self._plans[plan_id] = plan

        logger.info(
            "Wind-down plan '%s' created: strategy=%s, targets=%d",
            plan_id, resolved_strategy.value, len(targets),
        )
        return plan

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_wind_down(self, plan_id: str) -> Dict[str, Any]:
        """Execute a wind-down plan across all targets.

        Returns a results dict with per-target outcome.
        """
        with self._lock:
            plan = self._plans.get(plan_id)
        if plan is None:
            return {"error": f"Plan '{plan_id}' not found"}

        now = _utcnow()
        with self._lock:
            plan["status"] = "executing"
            plan["executed_at"] = now

        targets = plan.get("targets", [])
        strategy = WindDownStrategy(plan.get("strategy", "graceful"))
        results: Dict[str, Any] = {}

        for target_spec in targets:
            tid = target_spec.get("target_id", f"t-{uuid.uuid4().hex[:6]}")
            ttype = target_spec.get("target_type", "unknown")
            tname = target_spec.get("name", tid)
            monthly_cost = float(target_spec.get("monthly_cost", 0.0))

            try:
                self._engine.initiate_closure(tid, ttype, tname)

                if strategy == WindDownStrategy.IMMEDIATE:
                    self._engine.drain(tid)
                    self._engine.validate_outputs(tid)
                    self._engine.archive(tid)
                    self._engine.settle_costs(tid, {"total": monthly_cost})
                    self._engine.release_resources(tid, target_spec.get("resources", []))
                    closed = self._engine.complete_closure(tid)
                    results[tid] = {
                        "status": closed.status.value,
                        "errors": list(closed.errors),
                    }
                else:
                    # graceful / phased / budget_driven: run all phases
                    self._engine.drain(tid)
                    self._engine.validate_outputs(tid)
                    self._engine.archive(tid)
                    self._engine.settle_costs(tid, {"total": monthly_cost})
                    self._engine.release_resources(tid, target_spec.get("resources", []))
                    closed = self._engine.complete_closure(tid)
                    results[tid] = {
                        "status": closed.status.value,
                        "errors": list(closed.errors),
                    }
            except Exception as exc:
                logger.error(
                    "Error closing target '%s' in plan '%s': %s",
                    tid, plan_id, exc,
                )
                results[tid] = {"status": "failed", "errors": [str(exc)]}

        completed_at = _utcnow()
        with self._lock:
            plan["target_results"] = results
            plan["status"] = "completed"
            plan["completed_at"] = completed_at

        logger.info("Wind-down plan '%s' completed: %d targets processed", plan_id, len(targets))
        return {
            "plan_id": plan_id,
            "status": "completed",
            "target_results": results,
            "completed_at": completed_at,
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_wind_down_status(self, plan_id: str) -> Dict[str, Any]:
        """Return the current status of a wind-down plan."""
        with self._lock:
            plan = self._plans.get(plan_id)
        if plan is None:
            return {"error": f"Plan '{plan_id}' not found"}

        target_ids = [t.get("target_id") for t in plan.get("targets", [])]
        closed_targets = []
        for tid in target_ids:
            closures = self._engine.list_closures()
            for c in closures:
                if c.target_id == tid:
                    closed_targets.append({
                        "target_id": tid,
                        "status": c.status.value,
                    })

        return {
            "plan_id": plan_id,
            "strategy": plan.get("strategy"),
            "status": plan.get("status"),
            "created_at": plan.get("created_at"),
            "executed_at": plan.get("executed_at"),
            "completed_at": plan.get("completed_at"),
            "target_statuses": closed_targets,
        }

    # ------------------------------------------------------------------
    # Estimation and recommendations
    # ------------------------------------------------------------------

    def estimate_savings(self, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Estimate cost savings from closing the given targets.

        Returns ``{monthly_savings, annual_savings, one_time_recovery, breakdown}``.
        """
        breakdown: Dict[str, Any] = {}
        total_monthly = 0.0
        total_one_time = 0.0

        for target in targets:
            tid = target.get("target_id", "unknown")
            monthly = float(target.get("monthly_cost", 0.0))
            one_time = float(target.get("one_time_recovery", 0.0))
            breakdown[tid] = {
                "monthly_savings": monthly,
                "annual_savings": monthly * 12,
                "one_time_recovery": one_time,
            }
            total_monthly += monthly
            total_one_time += one_time

        return {
            "monthly_savings": total_monthly,
            "annual_savings": total_monthly * 12,
            "one_time_recovery": total_one_time,
            "breakdown": breakdown,
        }

    def recommend_closures(
        self,
        budget_target: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Recommend targets to close in order to hit a budget target.

        Each recommendation includes target info, estimated savings, risk
        level, and reasoning.

        Returns a list of recommendation dicts, sorted by estimated monthly
        savings descending.
        """
        closures = self._engine.list_closures()
        recommendations: List[Dict[str, Any]] = []
        accumulated = 0.0

        # Sort by final_cost desc (highest cost → close first)
        sorted_closures = sorted(closures, key=lambda c: c.final_cost, reverse=True)

        for closure in sorted_closures:
            if closure.status.value in ("closed", "failed"):
                continue

            monthly_savings = closure.final_cost
            risk = "low" if closure.target_type in ("subscription", "integration") else "medium"

            rec: Dict[str, Any] = {
                "target_id": closure.target_id,
                "target_type": closure.target_type,
                "name": closure.name,
                "estimated_monthly_savings": monthly_savings,
                "estimated_annual_savings": monthly_savings * 12,
                "risk": risk,
                "reasoning": (
                    f"Closing '{closure.name}' would save "
                    f"${monthly_savings:.2f}/month. "
                    f"Current phase: {closure.status.value}."
                ),
                "current_phase": closure.status.value,
            }
            recommendations.append(rec)
            accumulated += monthly_savings

            if budget_target is not None and accumulated >= budget_target:
                break

        return recommendations

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard(self) -> Dict[str, Any]:
        """Return a wind-down dashboard: active plans, savings, targets closed."""
        with self._lock:
            all_plans = list(self._plans.values())

        active_plans = [p for p in all_plans if p.get("status") not in ("completed", "failed")]
        completed_plans = [p for p in all_plans if p.get("status") == "completed"]

        engine_dashboard = self._engine.get_dashboard()

        total_savings_achieved = sum(
            p.get("estimated_savings", {}).get("monthly_savings", 0.0)
            for p in completed_plans
        )

        return {
            "total_plans": len(all_plans),
            "active_plans": len(active_plans),
            "completed_plans": len(completed_plans),
            "targets_closed": engine_dashboard.get("completed_closures", 0),
            "savings_achieved_monthly": total_savings_achieved,
            "savings_achieved_annual": total_savings_achieved * 12,
            "engine_dashboard": engine_dashboard,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _order_targets(
        self,
        targets: List[Dict[str, Any]],
        strategy: WindDownStrategy,
    ) -> List[Dict[str, Any]]:
        """Return targets ordered according to the chosen strategy."""
        if strategy == WindDownStrategy.BUDGET_DRIVEN:
            return sorted(targets, key=lambda t: float(t.get("monthly_cost", 0.0)), reverse=True)
        if strategy == WindDownStrategy.PHASED:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            return sorted(
                targets,
                key=lambda t: priority_order.get(t.get("priority", "medium"), 1),
            )
        # IMMEDIATE and GRACEFUL: preserve caller order
        return list(targets)
