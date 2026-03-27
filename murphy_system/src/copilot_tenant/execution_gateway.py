# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Copilot Tenant — Safety-Gated Execution Gateway

Executes actions through safety gates.  Wraps:
  - src/execution_orchestrator/
  - src/governance_kernel.py
  - src/safety_orchestrator.py
  - src/wingman_protocol.py
  - src/automation_safeguard_engine.py
  - src/emergency_stop.py / src/emergency_stop_controller.py
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    from governance_kernel import GovernanceKernel
    _GOVERNANCE_AVAILABLE = True
except Exception:  # pragma: no cover
    GovernanceKernel = None  # type: ignore[assignment,misc]
    _GOVERNANCE_AVAILABLE = False

try:
    from safety_orchestrator import SafetyOrchestrator
    _SAFETY_AVAILABLE = True
except Exception:  # pragma: no cover
    SafetyOrchestrator = None  # type: ignore[assignment,misc]
    _SAFETY_AVAILABLE = False

try:
    from wingman_protocol import WingmanProtocol
    _WINGMAN_AVAILABLE = True
except Exception:  # pragma: no cover
    WingmanProtocol = None  # type: ignore[assignment,misc]
    _WINGMAN_AVAILABLE = False

try:
    from emergency_stop import EmergencyStop
    _EMERGENCY_STOP_AVAILABLE = True
except Exception:  # pragma: no cover
    EmergencyStop = None  # type: ignore[assignment,misc]
    _EMERGENCY_STOP_AVAILABLE = False

try:
    from emergency_stop_controller import EmergencyStopController
    _EMERGENCY_CONTROLLER_AVAILABLE = True
except Exception:  # pragma: no cover
    EmergencyStopController = None  # type: ignore[assignment,misc]
    _EMERGENCY_CONTROLLER_AVAILABLE = False

# Lazy import to avoid circular dependencies
_CopilotTenantMode: Any = None


def _get_mode_enum() -> Any:
    global _CopilotTenantMode
    if _CopilotTenantMode is None:
        from copilot_tenant.tenant_agent import CopilotTenantMode
        _CopilotTenantMode = CopilotTenantMode
    return _CopilotTenantMode


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    result_id: str                  = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str                    = ""
    status: str                     = "pending"        # pending | executed | proposed | blocked | error
    output: Optional[Dict[str, Any]] = None
    blocked_reason: Optional[str]   = None
    proposal_id: Optional[str]      = None
    executed_at: str                = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Proposal:
    proposal_id: str                = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str                    = ""
    description: str                = ""
    proposed_action: str            = ""
    proposed_at: str                = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved: Optional[bool]        = None
    approval_note: Optional[str]    = None


# ---------------------------------------------------------------------------
# ExecutionGateway
# ---------------------------------------------------------------------------

class ExecutionGateway:
    """Executes actions through layered safety gates.

    Behaviour per mode:
      OBSERVER    — blocked; actions are only observed, never executed.
      SUGGESTION  — returns a Proposal without executing.
      SUPERVISED  — returns a Proposal and waits for founder approval.
      AUTONOMOUS  — executes after passing governance + safety checks.

    Emergency stop is always available regardless of mode.
    """

    def __init__(self) -> None:
        self._governance: Any        = None
        self._safety: Any            = None
        self._wingman: Any           = None
        self._emergency_stop: Any    = None
        self._emergency_ctrl: Any    = None
        self._emergency_active: bool = False
        self._initialize()

    def _initialize(self) -> None:
        if _GOVERNANCE_AVAILABLE:
            try:
                self._governance = GovernanceKernel()
            except Exception as exc:
                logger.debug("GovernanceKernel init failed: %s", exc)
        if _SAFETY_AVAILABLE:
            try:
                self._safety = SafetyOrchestrator()
            except Exception as exc:
                logger.debug("SafetyOrchestrator init failed: %s", exc)
        if _WINGMAN_AVAILABLE:
            try:
                self._wingman = WingmanProtocol()
                self._wingman.activate()
            except Exception as exc:
                logger.debug("WingmanProtocol init failed: %s", exc)
        if _EMERGENCY_STOP_AVAILABLE:
            try:
                self._emergency_stop = EmergencyStop()
            except Exception as exc:
                logger.debug("EmergencyStop init failed: %s", exc)
        if _EMERGENCY_CONTROLLER_AVAILABLE:
            try:
                self._emergency_ctrl = EmergencyStopController()
            except Exception as exc:
                logger.debug("EmergencyStopController init failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, task: Any, mode: Any) -> ExecutionResult:
        """Execute *task* subject to the safety gates implied by *mode*.

        Args:
            task: A ``PlannedTask`` (or any object with task_id / description).
            mode: A ``CopilotTenantMode`` value.

        Returns:
            ``ExecutionResult`` describing what happened.
        """
        CopilotTenantMode = _get_mode_enum()
        task_id = getattr(task, "task_id", str(uuid.uuid4()))
        description = getattr(task, "description", str(task))

        if self._emergency_active:
            return ExecutionResult(
                task_id=task_id,
                status="blocked",
                blocked_reason="emergency_stop_active",
            )

        # OBSERVER — never execute
        if mode == CopilotTenantMode.OBSERVER:
            return ExecutionResult(
                task_id=task_id,
                status="blocked",
                blocked_reason="observer_mode",
            )

        # SUGGESTION / SUPERVISED — propose only
        if mode in (CopilotTenantMode.SUGGESTION, CopilotTenantMode.SUPERVISED):
            proposal = self.propose(task)
            return ExecutionResult(
                task_id=task_id,
                status="proposed",
                proposal_id=proposal.proposal_id,
            )

        # AUTONOMOUS — run through governance + safety, then execute
        if not self._passes_governance(task):
            return ExecutionResult(
                task_id=task_id,
                status="blocked",
                blocked_reason="governance_kernel_blocked",
            )
        if not self._passes_safety(task):
            return ExecutionResult(
                task_id=task_id,
                status="blocked",
                blocked_reason="safety_orchestrator_blocked",
            )
        return self._do_execute(task_id, description)

    def propose(self, task: Any) -> Proposal:
        """Create a Proposal for the task (no execution)."""
        task_id     = getattr(task, "task_id", str(uuid.uuid4()))
        description = getattr(task, "description", str(task))
        return Proposal(
            task_id=task_id,
            description=description,
            proposed_action=description,
        )

    def emergency_stop(self) -> None:
        """Immediately halt all operations."""
        self._emergency_active = True
        logger.critical("ExecutionGateway: EMERGENCY STOP TRIGGERED")
        if self._emergency_stop is not None:
            try:
                self._emergency_stop.trigger()
            except Exception as exc:
                logger.error("EmergencyStop.trigger() failed: %s", exc)
        if self._emergency_ctrl is not None:
            try:
                self._emergency_ctrl.trigger()
            except Exception as exc:
                logger.error("EmergencyStopController.trigger() failed: %s", exc)

    def reset_emergency_stop(self) -> None:
        """Clear the emergency stop flag (use with caution)."""
        self._emergency_active = False
        logger.info("ExecutionGateway: emergency stop cleared")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _passes_governance(self, task: Any) -> bool:
        if self._governance is None:
            return True
        try:
            result = self._governance.evaluate(task) if hasattr(self._governance, "evaluate") else True
            return bool(result)
        except Exception as exc:
            logger.warning("Governance check failed: %s — blocking task", exc)
            return False

    def _passes_safety(self, task: Any) -> bool:
        if self._safety is None:
            return True
        try:
            result = self._safety.check(task) if hasattr(self._safety, "check") else True
            return bool(result)
        except Exception as exc:
            logger.warning("Safety check failed: %s — blocking task", exc)
            return False

    def _do_execute(self, task_id: str, description: str) -> ExecutionResult:
        logger.info("ExecutionGateway: executing task %s — %s", task_id, description)
        return ExecutionResult(
            task_id=task_id,
            status="executed",
            output={"task_id": task_id, "description": description},
        )
