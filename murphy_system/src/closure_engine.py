"""
Closure Engine for Murphy System Runtime

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

This module manages the lifecycle of winding down any Murphy-managed
process, project, or automation. It provides structured phase progression,
WingmanProtocol validation at each transition, cost settlement, resource
release, archival, and full audit trail.

Key capabilities:
- Eight-phase closure lifecycle (INITIATED → CLOSED)
- WingmanProtocol validation at every phase transition
- Cost settlement and budget reconciliation
- Resource release tracking
- State archival
- Auto-generated closure checklists
- Thread-safe operation
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase ordering used by advance_phase()
# ---------------------------------------------------------------------------
_PHASE_ORDER = [
    "initiated",
    "draining",
    "validating",
    "archiving",
    "settling",
    "releasing",
    "closed",
]

# ---------------------------------------------------------------------------
# Checklist templates keyed by target_type
# ---------------------------------------------------------------------------
_CHECKLIST_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "project": [
        {"description": "All in-progress work items drained", "required": True},
        {"description": "Final outputs validated", "required": True},
        {"description": "Archive created for project artifacts", "required": True},
        {"description": "Costs settled and final invoice generated", "required": True},
        {"description": "All project resources released", "required": True},
        {"description": "Stakeholders notified of closure", "required": False},
    ],
    "automation": [
        {"description": "Automation queue fully drained", "required": True},
        {"description": "Output validation completed", "required": True},
        {"description": "Run logs archived", "required": True},
        {"description": "API keys and tokens revoked", "required": True},
        {"description": "Scheduler entries removed", "required": True},
    ],
    "orchestrator": [
        {"description": "All child tasks completed or cancelled", "required": True},
        {"description": "Orchestrator state validated", "required": True},
        {"description": "Execution history archived", "required": True},
        {"description": "Budget settled", "required": True},
        {"description": "Compute resources released", "required": True},
    ],
    "pipeline": [
        {"description": "Pipeline queue drained", "required": True},
        {"description": "Final stage outputs validated", "required": True},
        {"description": "Pipeline logs archived", "required": True},
        {"description": "Costs reconciled", "required": True},
        {"description": "Pipeline connections closed", "required": True},
    ],
    "integration": [
        {"description": "In-flight messages drained", "required": True},
        {"description": "Integration outputs validated", "required": True},
        {"description": "Event logs archived", "required": True},
        {"description": "Budget settled", "required": True},
        {"description": "Webhooks and subscriptions cancelled", "required": True},
        {"description": "OAuth tokens revoked", "required": True},
    ],
    "subscription": [
        {"description": "Active subscription period completed", "required": True},
        {"description": "Final deliverables validated", "required": True},
        {"description": "Subscription history archived", "required": True},
        {"description": "Final billing settled", "required": True},
        {"description": "Access credentials revoked", "required": True},
    ],
}

_DEFAULT_CHECKLIST: List[Dict[str, Any]] = [
    {"description": "All work drained", "required": True},
    {"description": "Outputs validated", "required": True},
    {"description": "State archived", "required": True},
    {"description": "Costs settled", "required": True},
    {"description": "Resources released", "required": True},
]


def _utcnow() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums and dataclasses
# ---------------------------------------------------------------------------

class ClosurePhase(str, Enum):
    """Ordered phases of a closure lifecycle."""

    INITIATED = "initiated"
    DRAINING = "draining"
    VALIDATING = "validating"
    ARCHIVING = "archiving"
    SETTLING = "settling"
    RELEASING = "releasing"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass
class ClosureTarget:
    """Represents a single entity being closed."""

    target_id: str
    target_type: str
    name: str
    status: ClosurePhase
    created_at: str
    initiated_at: str
    completed_at: str = ""
    phases_completed: List[str] = field(default_factory=list)
    phase_timestamps: Dict[str, str] = field(default_factory=dict)
    final_cost: float = 0.0
    resources_released: List[str] = field(default_factory=list)
    archive_location: str = ""
    closure_report: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class ClosureChecklist:
    """Auto-generated checklist of tasks required to close a target."""

    checklist_id: str
    target_id: str
    items: List[Dict[str, Any]]
    all_required_complete: bool = False
    created_at: str = ""


# ---------------------------------------------------------------------------
# ClosureEngine
# ---------------------------------------------------------------------------

class ClosureEngine:
    """Manages the full lifecycle of closing Murphy-managed targets.

    Zero-config usage::

        engine = ClosureEngine()
        target = engine.initiate_closure("proj-1", "project", "My Project")
        engine.drain("proj-1")
        engine.validate_outputs("proj-1")
        engine.archive("proj-1")
        engine.settle_costs("proj-1")
        engine.release_resources("proj-1")
        closed = engine.complete_closure("proj-1")
    """

    def __init__(self, wingman_protocol=None) -> None:
        from wingman_protocol import (
            ExecutionRunbook,
            ValidationRule,
            ValidationSeverity,
            WingmanProtocol,
        )

        self._lock = threading.Lock()
        self._targets: Dict[str, ClosureTarget] = {}
        self._checklists: Dict[str, ClosureChecklist] = {}
        # checklist_id → checklist
        self._checklists_by_id: Dict[str, ClosureChecklist] = {}

        if wingman_protocol is None:
            self._wingman = WingmanProtocol()
        else:
            self._wingman = wingman_protocol

        # Register closure-specific runbook
        closure_runbook = ExecutionRunbook(
            runbook_id="closure_engine_runbook",
            name="Closure Engine Validation Runbook",
            domain="closure",
            validation_rules=[
                ValidationRule(
                    rule_id="check_all_work_drained",
                    description="Ensure all in-progress work has been drained",
                    check_fn_name="check_has_output",
                    severity=ValidationSeverity.BLOCK,
                    applicable_domains=["closure"],
                ),
                ValidationRule(
                    rule_id="check_outputs_validated",
                    description="Ensure all outputs have been validated",
                    check_fn_name="check_has_output",
                    severity=ValidationSeverity.BLOCK,
                    applicable_domains=["closure"],
                ),
                ValidationRule(
                    rule_id="check_costs_settled",
                    description="Ensure all costs have been reconciled",
                    check_fn_name="check_budget_limit",
                    severity=ValidationSeverity.WARN,
                    applicable_domains=["closure"],
                ),
                ValidationRule(
                    rule_id="check_resources_released",
                    description="Ensure all resources have been released",
                    check_fn_name="check_has_output",
                    severity=ValidationSeverity.BLOCK,
                    applicable_domains=["closure"],
                ),
                ValidationRule(
                    rule_id="check_archive_created",
                    description="Ensure an archive has been created",
                    check_fn_name="check_has_output",
                    severity=ValidationSeverity.WARN,
                    applicable_domains=["closure"],
                ),
            ],
        )
        self._wingman.register_runbook(closure_runbook)
        self._closure_runbook_id = closure_runbook.runbook_id
        logger.info("ClosureEngine initialised with runbook '%s'", self._closure_runbook_id)

    # ------------------------------------------------------------------
    # Core lifecycle
    # ------------------------------------------------------------------

    def initiate_closure(self, target_id: str, target_type: str, name: str) -> ClosureTarget:
        """Create a closure target and start the closure process.

        Returns the target in INITIATED phase.
        """
        now = _utcnow()
        target = ClosureTarget(
            target_id=target_id,
            target_type=target_type,
            name=name,
            status=ClosurePhase.INITIATED,
            created_at=now,
            initiated_at=now,
            phase_timestamps={"initiated": now},
            phases_completed=["initiated"],
        )
        with self._lock:
            self._targets[target_id] = target
        logger.info("Closure initiated for target '%s' (%s)", target_id, target_type)
        return target

    def advance_phase(self, target_id: str) -> ClosureTarget:
        """Advance to the next phase in the closure sequence.

        Runs a WingmanProtocol validation before transitioning.
        If validation fails the target stays in the current phase with
        errors recorded. The FAILED and CLOSED phases cannot be advanced.
        """
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            raise KeyError(f"No closure target found for id '{target_id}'")

        current = target.status.value
        if current in ("closed", "failed"):
            return target

        try:
            current_index = _PHASE_ORDER.index(current)
        except ValueError:
            return target

        if current_index >= len(_PHASE_ORDER) - 1:
            return target

        next_phase_name = _PHASE_ORDER[current_index + 1]

        # Run WingmanProtocol validation for the transition
        pair = self._wingman.create_pair(
            subject=f"closure:{target_id}:advance_to:{next_phase_name}",
            executor_id="closure_engine",
            validator_id="closure_validator",
            runbook_id=self._closure_runbook_id,
        )
        validation = self._wingman.validate_output(
            pair.pair_id,
            {"result": f"advancing to {next_phase_name}", "target_id": target_id},
        )

        now = _utcnow()
        with self._lock:
            if validation.get("approved"):
                target.status = ClosurePhase(next_phase_name)
                if next_phase_name not in target.phases_completed:
                    target.phases_completed.append(next_phase_name)
                target.phase_timestamps[next_phase_name] = now
            else:
                blocking = [r.get("message", "") for r in validation.get("blocking_failures", [])]
                for msg in blocking:
                    if msg and msg not in target.errors:
                        target.errors.append(msg)
                logger.warning(
                    "Phase advance blocked for target '%s': %s",
                    target_id, blocking,
                )
        return target

    # ------------------------------------------------------------------
    # Phase-specific operations
    # ------------------------------------------------------------------

    def drain(
        self,
        target_id: str,
        in_progress_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Mark items as draining and track completion.

        Returns ``{drained_count, remaining, estimated_drain_time_ms}``.
        """
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            return {"drained_count": 0, "remaining": 0, "estimated_drain_time_ms": 0}

        items = in_progress_items or []
        drained = len(items)
        remaining = 0

        with self._lock:
            if target.status == ClosurePhase.INITIATED:
                target.status = ClosurePhase.DRAINING
                target.phase_timestamps["draining"] = _utcnow()
                if "draining" not in target.phases_completed:
                    target.phases_completed.append("draining")

        logger.info("Drain called for target '%s': %d items drained", target_id, drained)
        return {
            "drained_count": drained,
            "remaining": remaining,
            "estimated_drain_time_ms": drained * 10,
        }

    def validate_outputs(
        self,
        target_id: str,
        outputs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run final validation on all outputs using WingmanProtocol.

        Returns ``{validated, failed, warnings, approved}``.
        """
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            return {"validated": 0, "failed": 0, "warnings": 0, "approved": False}

        output_list = outputs or [{"result": "no_outputs_provided"}]
        validated = 0
        failed = 0
        warnings = 0

        pair = self._wingman.create_pair(
            subject=f"closure:{target_id}:validate_outputs",
            executor_id="closure_engine",
            validator_id="closure_validator",
            runbook_id=self._closure_runbook_id,
        )

        for output in output_list:
            result = self._wingman.validate_output(pair.pair_id, output)
            if result.get("approved"):
                validated += 1
            else:
                failed += 1
            warnings += sum(
                1 for r in result.get("results", [])
                if r.get("severity") == "warn" and not r.get("passed")
            )

        approved = failed == 0

        with self._lock:
            if target.status in (ClosurePhase.DRAINING, ClosurePhase.INITIATED):
                target.status = ClosurePhase.VALIDATING
                target.phase_timestamps["validating"] = _utcnow()
                if "validating" not in target.phases_completed:
                    target.phases_completed.append("validating")

        return {
            "validated": validated,
            "failed": failed,
            "warnings": warnings,
            "approved": approved,
        }

    def settle_costs(
        self,
        target_id: str,
        final_costs: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Reconcile all costs and generate a final cost summary.

        Returns ``{total_cost, cost_breakdown, budget_remaining, settlement_status}``.
        """
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            return {
                "total_cost": 0.0,
                "cost_breakdown": {},
                "budget_remaining": 0.0,
                "settlement_status": "no_target",
            }

        costs = final_costs or {}
        total = sum(costs.values())

        with self._lock:
            target.final_cost = total
            if target.status in (
                ClosurePhase.ARCHIVING,
                ClosurePhase.VALIDATING,
                ClosurePhase.DRAINING,
                ClosurePhase.INITIATED,
            ):
                target.status = ClosurePhase.SETTLING
                target.phase_timestamps["settling"] = _utcnow()
                if "settling" not in target.phases_completed:
                    target.phases_completed.append("settling")

        logger.info("Costs settled for target '%s': total=%.4f", target_id, total)
        return {
            "total_cost": total,
            "cost_breakdown": costs,
            "budget_remaining": 0.0,
            "settlement_status": "settled",
        }

    def release_resources(
        self,
        target_id: str,
        resources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Release connections, API keys, and compute resources.

        Returns ``{released, failed_to_release, warnings}``.
        """
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            return {"released": [], "failed_to_release": [], "warnings": []}

        resource_list = resources or []
        released = list(resource_list)
        failed_to_release: List[str] = []
        release_warnings: List[str] = []

        with self._lock:
            target.resources_released.extend(released)
            if target.status in (
                ClosurePhase.SETTLING,
                ClosurePhase.ARCHIVING,
                ClosurePhase.VALIDATING,
                ClosurePhase.DRAINING,
                ClosurePhase.INITIATED,
            ):
                target.status = ClosurePhase.RELEASING
                target.phase_timestamps["releasing"] = _utcnow()
                if "releasing" not in target.phases_completed:
                    target.phases_completed.append("releasing")

        logger.info(
            "Resources released for target '%s': %d released",
            target_id, len(released),
        )
        return {
            "released": released,
            "failed_to_release": failed_to_release,
            "warnings": release_warnings,
        }

    def archive(
        self,
        target_id: str,
        archive_path: str = "",
    ) -> Dict[str, Any]:
        """Archive all state, logs, and outputs.

        Returns ``{archive_id, archive_location, size_bytes, archived_items}``.
        """
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            return {
                "archive_id": "",
                "archive_location": "",
                "size_bytes": 0,
                "archived_items": [],
            }

        archive_id = f"archive-{uuid.uuid4().hex[:8]}"
        location = archive_path or f"archives/{target_id}/{archive_id}"

        with self._lock:
            target.archive_location = location
            if target.status in (
                ClosurePhase.VALIDATING,
                ClosurePhase.DRAINING,
                ClosurePhase.INITIATED,
            ):
                target.status = ClosurePhase.ARCHIVING
                target.phase_timestamps["archiving"] = _utcnow()
                if "archiving" not in target.phases_completed:
                    target.phases_completed.append("archiving")

        logger.info("Archive created for target '%s' at '%s'", target_id, location)
        return {
            "archive_id": archive_id,
            "archive_location": location,
            "size_bytes": 0,
            "archived_items": [target_id],
        }

    def complete_closure(self, target_id: str) -> ClosureTarget:
        """Mark the target as CLOSED if all phases are complete.

        Generates the final closure report.
        """
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            raise KeyError(f"No closure target found for id '{target_id}'")

        required_phases = {"draining", "validating", "archiving", "settling", "releasing"}
        completed_set = set(target.phases_completed)
        missing = required_phases - completed_set

        now = _utcnow()
        report = self.get_closure_report(target_id)

        with self._lock:
            if missing:
                target.errors.append(
                    f"Cannot close: missing phases {sorted(missing)}"
                )
                target.status = ClosurePhase.FAILED
            else:
                target.status = ClosurePhase.CLOSED
                target.completed_at = now
                target.phase_timestamps["closed"] = now
                if "closed" not in target.phases_completed:
                    target.phases_completed.append("closed")
                target.closure_report = report

        logger.info(
            "Closure complete for target '%s': status=%s",
            target_id, target.status.value,
        )
        return target

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_closure_report(self, target_id: str) -> Dict[str, Any]:
        """Return a full closure report: timeline, costs, validations, resources."""
        with self._lock:
            target = self._targets.get(target_id)
        if target is None:
            return {"error": f"Target '{target_id}' not found"}

        return {
            "target_id": target.target_id,
            "target_type": target.target_type,
            "name": target.name,
            "status": target.status.value,
            "initiated_at": target.initiated_at,
            "completed_at": target.completed_at,
            "phases_completed": list(target.phases_completed),
            "phase_timestamps": dict(target.phase_timestamps),
            "final_cost": target.final_cost,
            "resources_released": list(target.resources_released),
            "archive_location": target.archive_location,
            "errors": list(target.errors),
        }

    # ------------------------------------------------------------------
    # Checklists
    # ------------------------------------------------------------------

    def create_checklist(self, target_id: str) -> ClosureChecklist:
        """Auto-generate a closure checklist based on the target's type."""
        with self._lock:
            target = self._targets.get(target_id)

        target_type = target.target_type if target else "unknown"
        template = _CHECKLIST_TEMPLATES.get(target_type, _DEFAULT_CHECKLIST)

        checklist_id = f"cl-{uuid.uuid4().hex[:8]}"
        now = _utcnow()

        items = []
        for idx, tmpl in enumerate(template):
            items.append({
                "item_id": f"item-{idx + 1:03d}",
                "description": tmpl["description"],
                "required": tmpl["required"],
                "completed": False,
                "completed_at": "",
                "completed_by": "",
            })

        checklist = ClosureChecklist(
            checklist_id=checklist_id,
            target_id=target_id,
            items=items,
            all_required_complete=False,
            created_at=now,
        )

        with self._lock:
            self._checklists[target_id] = checklist
            self._checklists_by_id[checklist_id] = checklist

        logger.info(
            "Checklist '%s' created for target '%s' (%d items)",
            checklist_id, target_id, len(items),
        )
        return checklist

    def complete_checklist_item(
        self,
        checklist_id: str,
        item_id: str,
        completed_by: str = "system",
    ) -> bool:
        """Mark a checklist item as complete.

        Returns True if the item was found and marked complete, False otherwise.
        """
        with self._lock:
            checklist = self._checklists_by_id.get(checklist_id)
        if checklist is None:
            return False

        now = _utcnow()
        found = False
        with self._lock:
            for item in checklist.items:
                if item.get("item_id") == item_id:
                    item["completed"] = True
                    item["completed_at"] = now
                    item["completed_by"] = completed_by
                    found = True
                    break

            if found:
                required_done = all(
                    i["completed"]
                    for i in checklist.items
                    if i.get("required")
                )
                checklist.all_required_complete = required_done

        return found

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def list_closures(
        self,
        status: Optional[str] = None,
        target_type: Optional[str] = None,
    ) -> List[ClosureTarget]:
        """List closure targets, optionally filtered by status and/or type."""
        with self._lock:
            targets = list(self._targets.values())
        if status is not None:
            targets = [t for t in targets if t.status.value == status]
        if target_type is not None:
            targets = [t for t in targets if t.target_type == target_type]
        return targets

    def get_dashboard(self) -> Dict[str, Any]:
        """Return a summary dashboard of all closure activity."""
        with self._lock:
            all_targets = list(self._targets.values())

        active = [t for t in all_targets if t.status not in (ClosurePhase.CLOSED, ClosurePhase.FAILED)]
        completed = [t for t in all_targets if t.status == ClosurePhase.CLOSED]
        failed = [t for t in all_targets if t.status == ClosurePhase.FAILED]

        total_cost_settled = sum(t.final_cost for t in completed)
        total_resources_released = sum(len(t.resources_released) for t in all_targets)

        return {
            "total_closures": len(all_targets),
            "active_closures": len(active),
            "completed_closures": len(completed),
            "failed_closures": len(failed),
            "costs_settled": total_cost_settled,
            "resources_released": total_resources_released,
        }
