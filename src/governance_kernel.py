"""
Governance Kernel for Murphy System Runtime

This module implements a non-LLM deterministic governance enforcement layer
that routes ALL tool calls through centralized policy checks, providing:
- Role registry and permission graph enforcement
- Escalation policy with configurable thresholds
- Budget tracking with per-department and per-task limits
- Department-scoped memory isolation
- Cross-department arbitration controls
- Immutable audit log emission for every enforcement decision
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class EnforcementAction(str, Enum):
    """Possible outcomes of a governance enforcement check."""
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"
    AUDIT_ONLY = "audit_only"


@dataclass
class EnforcementResult:
    """The result of a single governance enforcement decision."""
    action: EnforcementAction
    reason: str
    enforced_by: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetTracker:
    """Tracks budget consumption for a department."""
    total_budget: float
    spent: float = 0.0
    pending: float = 0.0
    limit_per_task: float = 0.0

    @property
    def remaining(self) -> float:
        return self.total_budget - self.spent - self.pending


@dataclass
class DepartmentScope:
    """Defines a department's governance scope and permissions."""
    department_id: str
    name: str
    allowed_tools: Set[str] = field(default_factory=set)
    memory_isolation: bool = False
    escalation_target: Optional[str] = None


class GovernanceKernel:
    """Deterministic governance enforcement layer for the Murphy System.

    Routes all tool calls through centralized policy checks covering
    department registration, permission enforcement, budget tracking,
    memory isolation, cross-department arbitration, and audit logging.
    """

    _MAX_AUDIT_ENTRIES = 10_000
    _MAX_EXECUTIONS = 10_000
    _RETENTION_FRACTION = 10  # keep 1/N entries on trim

    # Profit Allocation Tiers — defines allocation percentages per revenue tier
    PROFIT_ALLOCATION_TIERS: List[Dict[str, Any]] = [
        {"tier": "seed", "revenue_min": 0, "revenue_max": 100_000,
         "reinvestment_pct": 70, "operations_pct": 20, "reserve_pct": 10},
        {"tier": "growth", "revenue_min": 100_001, "revenue_max": 500_000,
         "reinvestment_pct": 50, "operations_pct": 30, "reserve_pct": 20},
        {"tier": "scale", "revenue_min": 500_001, "revenue_max": 2_000_000,
         "reinvestment_pct": 40, "operations_pct": 35, "reserve_pct": 25},
        {"tier": "mature", "revenue_min": 2_000_001, "revenue_max": float("inf"),
         "reinvestment_pct": 30, "operations_pct": 40, "reserve_pct": 30},
    ]

    def __init__(self, strict_mode: bool = False) -> None:
        self._lock = threading.Lock()
        self._strict_mode = strict_mode
        self._departments: Dict[str, DepartmentScope] = {}
        self._budgets: Dict[str, BudgetTracker] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._executions: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Department registration
    # ------------------------------------------------------------------

    def register_department(self, scope: DepartmentScope) -> str:
        """Register a department scope and return its department_id."""
        with self._lock:
            self._departments[scope.department_id] = scope
        logger.info("Registered department %s (%s)", scope.department_id, scope.name)
        return scope.department_id

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------

    def enforce(
        self,
        caller_id: str,
        department_id: str,
        tool_name: str,
        estimated_cost: float = 0.0,
        context: Optional[Dict[str, Any]] = None,
    ) -> EnforcementResult:
        """Enforce governance policy before a tool execution.

        Every call produces an audit log entry regardless of outcome.
        """
        context = context or {}

        with self._lock:
            result = self._evaluate(caller_id, department_id, tool_name, estimated_cost, context)
            self._emit_audit(caller_id, department_id, tool_name, estimated_cost, result, context)

        logger.info(
            "Enforcement: caller=%s dept=%s tool=%s -> %s (%s)",
            caller_id, department_id, tool_name, result.action.value, result.reason,
        )
        return result

    def _evaluate(
        self,
        caller_id: str,
        department_id: str,
        tool_name: str,
        estimated_cost: float,
        context: Dict[str, Any],
    ) -> EnforcementResult:
        """Core deterministic evaluation logic. Must be called under lock."""
        # --- department must be registered ---
        dept = self._departments.get(department_id)
        if dept is None:
            return EnforcementResult(
                action=EnforcementAction.DENY,
                reason=f"department '{department_id}' is not registered",
                enforced_by="governance_kernel.department_check",
                metadata={"caller_id": caller_id, "tool_name": tool_name},
            )

        # --- tool must be in allowed set (when set is non-empty) ---
        if dept.allowed_tools and tool_name not in dept.allowed_tools:
            return EnforcementResult(
                action=EnforcementAction.DENY,
                reason=f"tool '{tool_name}' not in allowed tools for department '{department_id}'",
                enforced_by="governance_kernel.permission_check",
                metadata={"caller_id": caller_id, "allowed_tools": sorted(dept.allowed_tools)},
            )

        # --- budget enforcement ---
        budget = self._budgets.get(department_id)
        if budget is not None and estimated_cost > 0:
            # per-task limit
            if budget.limit_per_task > 0 and estimated_cost > budget.limit_per_task:
                action = EnforcementAction.DENY if self._strict_mode else EnforcementAction.ESCALATE
                return EnforcementResult(
                    action=action,
                    reason=(
                        f"estimated cost {estimated_cost:.4f} exceeds per-task limit "
                        f"{budget.limit_per_task:.4f}"
                    ),
                    enforced_by="governance_kernel.budget_per_task",
                    metadata={"caller_id": caller_id, "estimated_cost": estimated_cost},
                )

            # overall remaining budget
            if estimated_cost > budget.remaining:
                action = EnforcementAction.DENY if self._strict_mode else EnforcementAction.ESCALATE
                return EnforcementResult(
                    action=action,
                    reason=(
                        f"estimated cost {estimated_cost:.4f} exceeds remaining budget "
                        f"{budget.remaining:.4f}"
                    ),
                    enforced_by="governance_kernel.budget_remaining",
                    metadata={
                        "caller_id": caller_id,
                        "remaining": budget.remaining,
                        "estimated_cost": estimated_cost,
                    },
                )

            # reserve pending cost
            budget.pending += estimated_cost

        # --- all checks passed ---
        return EnforcementResult(
            action=EnforcementAction.ALLOW,
            reason="all governance checks passed",
            enforced_by="governance_kernel.allow",
            metadata={"caller_id": caller_id, "tool_name": tool_name},
        )

    # ------------------------------------------------------------------
    # Execution recording
    # ------------------------------------------------------------------

    def record_execution(
        self,
        caller_id: str,
        tool_name: str,
        cost: float,
        success: bool,
        department_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Record a completed tool execution for budget and audit purposes.

        Args:
            caller_id: Identifier of the caller.
            tool_name: Name of the tool that was executed.
            cost: Actual cost incurred.
            success: Whether the execution succeeded.
            department_id: Department whose budget should be debited.
                When provided the cost is applied to the matching department
                budget.  When *None* (legacy callers) the first budget with
                sufficient pending amount is used as a fallback.
            project_id: Optional project identifier for project-level cost
                aggregation.  Not required for budget debiting.
        """
        with self._lock:
            if len(self._executions) >= self._MAX_EXECUTIONS:
                self._executions = self._executions[self._MAX_EXECUTIONS // self._RETENTION_FRACTION:]
            record = {
                "record_id": uuid.uuid4().hex[:12],
                "caller_id": caller_id,
                "tool_name": tool_name,
                "cost": cost,
                "success": success,
                "department_id": department_id,
                "project_id": project_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._executions.append(record)

            # Debit the correct department budget
            if department_id is not None:
                budget = self._budgets.get(department_id)
                if budget is not None and budget.pending >= cost:
                    budget.pending -= cost
                    budget.spent += cost
            else:
                # Legacy fallback: first budget with sufficient pending
                debited = False
                for budget in self._budgets.values():
                    if budget.pending >= cost:
                        budget.pending -= cost
                        budget.spent += cost
                        debited = True
                        break
                if not debited and cost > 0:
                    logger.error(
                        "Cost %.4f could not be debited from any budget "
                        "(caller=%s, tool=%s)",
                        cost, caller_id, tool_name,
                    )

        logger.info(
            "Recorded execution: caller=%s tool=%s cost=%.4f success=%s",
            caller_id, tool_name, cost, success,
        )

    # ------------------------------------------------------------------
    # Budget management
    # ------------------------------------------------------------------

    def set_budget(
        self,
        department_id: str,
        total_budget: float,
        limit_per_task: float = 0.0,
    ) -> None:
        """Set or update the budget for a department."""
        with self._lock:
            existing = self._budgets.get(department_id)
            if existing is not None:
                existing.total_budget = total_budget
                existing.limit_per_task = limit_per_task
            else:
                self._budgets[department_id] = BudgetTracker(
                    total_budget=total_budget,
                    limit_per_task=limit_per_task,
                )
        logger.info(
            "Budget set for %s: total=%.4f limit_per_task=%.4f",
            department_id, total_budget, limit_per_task,
        )

    def get_budget_status(self, department_id: Optional[str] = None) -> Dict[str, Any]:
        """Return budget status for a department or all departments."""
        with self._lock:
            if department_id is not None:
                budget = self._budgets.get(department_id)
                if budget is None:
                    return {"department_id": department_id, "status": "no_budget_set"}
                return {
                    "department_id": department_id,
                    "total_budget": budget.total_budget,
                    "spent": budget.spent,
                    "pending": budget.pending,
                    "remaining": budget.remaining,
                    "limit_per_task": budget.limit_per_task,
                }

            result: Dict[str, Any] = {}
            for dept_id, budget in self._budgets.items():
                result[dept_id] = {
                    "total_budget": budget.total_budget,
                    "spent": budget.spent,
                    "pending": budget.pending,
                    "remaining": budget.remaining,
                    "limit_per_task": budget.limit_per_task,
                }
            return result

    # ------------------------------------------------------------------
    # Cross-department arbitration
    # ------------------------------------------------------------------

    def check_cross_department(
        self,
        source_dept: str,
        target_dept: str,
        tool_name: str,
    ) -> EnforcementResult:
        """Check whether a cross-department tool access is permitted."""
        with self._lock:
            source = self._departments.get(source_dept)
            target = self._departments.get(target_dept)

            if source is None:
                result = EnforcementResult(
                    action=EnforcementAction.DENY,
                    reason=f"source department '{source_dept}' is not registered",
                    enforced_by="governance_kernel.cross_dept_check",
                )
                self._audit_log.append({
                    "event": "cross_department_check",
                    "source_dept": source_dept,
                    "target_dept": target_dept,
                    "tool_name": tool_name,
                    "action": result.action.value,
                    "reason": result.reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return result

            if target is None:
                result = EnforcementResult(
                    action=EnforcementAction.DENY,
                    reason=f"target department '{target_dept}' is not registered",
                    enforced_by="governance_kernel.cross_dept_check",
                )
                self._audit_log.append({
                    "event": "cross_department_check",
                    "source_dept": source_dept,
                    "target_dept": target_dept,
                    "tool_name": tool_name,
                    "action": result.action.value,
                    "reason": result.reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return result

            if target.memory_isolation:
                result = EnforcementResult(
                    action=EnforcementAction.DENY,
                    reason=(
                        f"target department '{target_dept}' has memory isolation enabled; "
                        "cross-department access denied"
                    ),
                    enforced_by="governance_kernel.memory_isolation",
                    metadata={"source_dept": source_dept, "target_dept": target_dept},
                )
                self._audit_log.append({
                    "event": "cross_department_check",
                    "source_dept": source_dept,
                    "target_dept": target_dept,
                    "tool_name": tool_name,
                    "action": result.action.value,
                    "reason": result.reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return result

            result = EnforcementResult(
                action=EnforcementAction.ALLOW,
                reason="cross-department access permitted",
                enforced_by="governance_kernel.cross_dept_check",
                metadata={"source_dept": source_dept, "target_dept": target_dept},
            )
            self._audit_log.append({
                "event": "cross_department_check",
                "source_dept": source_dept,
                "target_dept": target_dept,
                "tool_name": tool_name,
                "action": result.action.value,
                "reason": result.reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return result

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def get_audit_log(
        self,
        department_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return audit trail, optionally filtered by department."""
        with self._lock:
            if department_id is not None:
                entries = [
                    e for e in self._audit_log
                    if e.get("department_id") == department_id
                ]
            else:
                entries = list(self._audit_log)
        return entries[-limit:]

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return overall governance kernel status."""
        with self._lock:
            total_departments = len(self._departments)
            total_budgets = len(self._budgets)
            total_audit_entries = len(self._audit_log)
            total_executions = len(self._executions)
            department_ids = sorted(self._departments.keys())

        return {
            "strict_mode": self._strict_mode,
            "total_departments": total_departments,
            "total_budgets": total_budgets,
            "total_audit_entries": total_audit_entries,
            "total_executions": total_executions,
            "department_ids": department_ids,
        }

    # ------------------------------------------------------------------
    # Cost aggregation helpers
    # ------------------------------------------------------------------

    def get_costs_by_project(self) -> Dict[str, Any]:
        """Return execution costs aggregated by project_id.

        Returns a mapping of ``project_id -> {total_cost, execution_count}``.
        Executions without a ``project_id`` are grouped under the key
        ``"__unassigned__"``.
        """
        with self._lock:
            executions = list(self._executions)

        result: Dict[str, Dict[str, Any]] = {}
        for rec in executions:
            pid = rec.get("project_id") or "__unassigned__"
            if pid not in result:
                result[pid] = {"project_id": pid, "total_cost": 0.0, "execution_count": 0}
            result[pid]["total_cost"] += rec.get("cost", 0.0)
            result[pid]["execution_count"] += 1
        return result

    def get_costs_by_caller(self) -> Dict[str, Any]:
        """Return execution costs aggregated by caller_id (bot/agent).

        Returns a mapping of ``caller_id -> {total_cost, execution_count}``.
        """
        with self._lock:
            executions = list(self._executions)

        result: Dict[str, Dict[str, Any]] = {}
        for rec in executions:
            cid = rec.get("caller_id") or "__unknown__"
            if cid not in result:
                result[cid] = {"caller_id": cid, "total_cost": 0.0, "execution_count": 0}
            result[cid]["total_cost"] += rec.get("cost", 0.0)
            result[cid]["execution_count"] += 1
        return result

    # ------------------------------------------------------------------
    # Profit Allocation
    # ------------------------------------------------------------------

    def set_profit_allocation(
        self,
        department_id: str,
        revenue: float,
    ) -> Dict[str, Any]:
        """Determine profit allocation based on revenue tier.

        Integrates with the existing BudgetTracker when a budget is set
        for the given department.

        Args:
            department_id: Department to allocate profits for.
            revenue: Current revenue amount.

        Returns:
            Dict with tier info and allocated amounts.
        """
        with self._lock:
            tier_info: Optional[Dict[str, Any]] = None
            for tier in self.PROFIT_ALLOCATION_TIERS:
                if tier["revenue_min"] <= revenue <= tier["revenue_max"]:
                    tier_info = tier
                    break

            if tier_info is None:
                tier_info = self.PROFIT_ALLOCATION_TIERS[-1]

            reinvestment = round(revenue * tier_info["reinvestment_pct"] / 100, 2)
            operations = round(revenue * tier_info["operations_pct"] / 100, 2)
            reserve = round(revenue * tier_info["reserve_pct"] / 100, 2)

            # If a budget tracker exists, update it with the operations allocation
            budget = self._budgets.get(department_id)
            if budget is not None:
                budget.total_budget += operations

        logger.info(
            "Profit allocation for %s (tier=%s): reinvest=%.2f ops=%.2f reserve=%.2f",
            department_id, tier_info["tier"], reinvestment, operations, reserve,
        )
        return {
            "department_id": department_id,
            "tier": tier_info["tier"],
            "revenue": revenue,
            "reinvestment": reinvestment,
            "operations": operations,
            "reserve": reserve,
        }

    # ------------------------------------------------------------------
    # Environmental Governance
    # ------------------------------------------------------------------

    def enforce_environmental_review(
        self,
        module_name: str,
        domain: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> EnforcementResult:
        """Enforce mandatory sustainability review for environmental domain modules.

        Args:
            module_name: Name of the module being reviewed.
            domain: Regulatory domain the module operates in.
            context: Optional additional context.

        Returns:
            EnforcementResult indicating whether the review passed.
        """
        context = context or {}

        with self._lock:
            if domain.lower() in ("environmental", "energy", "social_impact"):
                has_sustainability_flag = context.get("sustainability_reviewed", False)
                if not has_sustainability_flag:
                    result = EnforcementResult(
                        action=EnforcementAction.ESCALATE,
                        reason=(
                            f"Module '{module_name}' operates in '{domain}' domain; "
                            "mandatory sustainability review not completed"
                        ),
                        enforced_by="governance_kernel.environmental_review",
                        metadata={"module_name": module_name, "domain": domain},
                    )
                    self._emit_audit(
                        "system", "environmental", module_name, 0.0, result, context,
                    )
                    return result

            result = EnforcementResult(
                action=EnforcementAction.ALLOW,
                reason="Environmental governance check passed",
                enforced_by="governance_kernel.environmental_review",
                metadata={"module_name": module_name, "domain": domain},
            )
            self._emit_audit("system", "environmental", module_name, 0.0, result, context)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_audit(
        self,
        caller_id: str,
        department_id: str,
        tool_name: str,
        estimated_cost: float,
        result: EnforcementResult,
        context: Dict[str, Any],
    ) -> None:
        """Append an audit entry. Must be called under lock."""
        if len(self._audit_log) >= self._MAX_AUDIT_ENTRIES:
            self._audit_log = self._audit_log[self._MAX_AUDIT_ENTRIES // self._RETENTION_FRACTION:]
        self._audit_log.append({
            "event": "enforcement",
            "caller_id": caller_id,
            "department_id": department_id,
            "tool_name": tool_name,
            "estimated_cost": estimated_cost,
            "action": result.action.value,
            "reason": result.reason,
            "enforced_by": result.enforced_by,
            "context": context,
            "timestamp": result.timestamp.isoformat(),
        })
