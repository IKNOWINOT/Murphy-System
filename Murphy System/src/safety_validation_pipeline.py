"""
Safety Validation Pipeline for Murphy System.

Design Label: SAF-001 — Pre/During/Post Execution Safety Validation
Owner: Security Team / AI Safety Team
Dependencies:
  - PersistenceManager (for durable validation records)
  - EventBackbone (publishes SYSTEM_HEALTH on validation outcomes)
  - EmergencyStopController (OPS-004, optional, for stop-on-critical)
  - AutomationModeController (OPS-003, optional, for mode-aware checks)

Implements Plan §6.1 — Safety Validation Pipeline:
  Three-stage validation for every autonomous action:
    PRE_EXECUTION  → authorization, input, risk, rate-limit, budget
    EXECUTION      → progress, anomaly, resource usage
    POST_EXECUTION → output correctness, side-effects, metrics, audit

Flow:
  1. Submit a validation request with action metadata
  2. Run pre-execution checks (authorization, input validation, risk assessment, rate limit, budget)
  3. Record execution-phase observations (progress, anomaly, resource)
  4. Run post-execution checks (output correctness, side-effects, metrics)
  5. Produce ValidationResult (PASSED / FAILED / WARNING) with per-check details
  6. Persist result and publish event

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Fail-closed: any check failure → overall FAILED
  - Bounded: configurable max result history
  - Audit trail: every validation is logged with full detail

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RESULTS = 5_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ValidationStage(str, Enum):
    """Validation stage (str subclass)."""
    PRE_EXECUTION = "pre_execution"
    EXECUTION = "execution"
    POST_EXECUTION = "post_execution"


class CheckOutcome(str, Enum):
    """Check outcome (str subclass)."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class OverallVerdict(str, Enum):
    """Overall verdict (str subclass)."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class CheckResult:
    """Result of a single validation check."""
    check_id: str
    stage: ValidationStage
    name: str
    outcome: CheckOutcome
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "stage": self.stage.value,
            "name": self.name,
            "outcome": self.outcome.value,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at,
        }


@dataclass
class ValidationResult:
    """Aggregate result of all checks for one action."""
    result_id: str
    action_id: str
    action_type: str
    verdict: OverallVerdict
    checks: List[CheckResult] = field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    skipped_count: int = 0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "verdict": self.verdict.value,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "warning_count": self.warning_count,
            "skipped_count": self.skipped_count,
            "checks": [c.to_dict() for c in self.checks],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Default check registry
# ---------------------------------------------------------------------------

PRE_EXECUTION_CHECKS = [
    "authorization",
    "input_validation",
    "risk_assessment",
    "rate_limit",
    "budget_check",
]

POST_EXECUTION_CHECKS = [
    "output_correctness",
    "side_effect_detection",
    "metrics_update",
    "audit_trail",
]


# ---------------------------------------------------------------------------
# SafetyValidationPipeline
# ---------------------------------------------------------------------------

class SafetyValidationPipeline:
    """Three-stage safety validation for autonomous actions.

    Design Label: SAF-001
    Owner: Security Team / AI Safety Team

    Usage::

        pipeline = SafetyValidationPipeline()
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "authorization",
                                lambda ctx: (True, "authorized"))
        result = pipeline.validate("action-1", "deploy", {"user": "admin"})
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        # stage -> name -> callable(context) -> (bool_pass, message)
        self._checks: Dict[ValidationStage, Dict[str, Callable]] = {
            ValidationStage.PRE_EXECUTION: {},
            ValidationStage.EXECUTION: {},
            ValidationStage.POST_EXECUTION: {},
        }
        self._results: List[ValidationResult] = []

    # ------------------------------------------------------------------
    # Check registration
    # ------------------------------------------------------------------

    def register_check(
        self,
        stage: ValidationStage,
        name: str,
        check_fn: Callable[[Dict[str, Any]], tuple],
    ) -> None:
        """Register a validation check.

        check_fn(context) -> (passed: bool, message: str)
        """
        with self._lock:
            self._checks[stage][name] = check_fn
        logger.debug("Registered check %s in stage %s", name, stage.value)

    def unregister_check(self, stage: ValidationStage, name: str) -> bool:
        with self._lock:
            return self._checks[stage].pop(name, None) is not None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self,
        action_id: str,
        action_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Run all registered checks across all stages."""
        ctx = context or {}
        all_checks: List[CheckResult] = []
        passed = failed = warning = skipped = 0

        for stage in (ValidationStage.PRE_EXECUTION,
                      ValidationStage.EXECUTION,
                      ValidationStage.POST_EXECUTION):
            with self._lock:
                stage_checks = dict(self._checks[stage])

            for name, fn in stage_checks.items():
                cr = self._run_check(stage, name, fn, ctx)
                all_checks.append(cr)
                if cr.outcome == CheckOutcome.PASSED:
                    passed += 1
                elif cr.outcome == CheckOutcome.FAILED:
                    failed += 1
                elif cr.outcome == CheckOutcome.WARNING:
                    warning += 1
                else:
                    skipped += 1

        # Determine verdict: fail-closed
        if failed > 0:
            verdict = OverallVerdict.FAILED
        elif warning > 0:
            verdict = OverallVerdict.WARNING
        else:
            verdict = OverallVerdict.PASSED

        result = ValidationResult(
            result_id=f"vr-{uuid.uuid4().hex[:8]}",
            action_id=action_id,
            action_type=action_type,
            verdict=verdict,
            checks=all_checks,
            passed_count=passed,
            failed_count=failed,
            warning_count=warning,
            skipped_count=skipped,
        )

        with self._lock:
            if len(self._results) >= _MAX_RESULTS:
                self._results = self._results[_MAX_RESULTS // 10:]
            self._results.append(result)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=result.result_id, document=result.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(result)

        logger.info(
            "Validation %s for action %s: %s (%d passed, %d failed, %d warning)",
            result.result_id, action_id, verdict.value, passed, failed, warning,
        )
        return result

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._results[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            check_counts = {
                stage.value: len(checks) for stage, checks in self._checks.items()
            }
            return {
                "registered_checks": check_counts,
                "total_results": len(self._results),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_check(
        self,
        stage: ValidationStage,
        name: str,
        fn: Callable,
        ctx: Dict[str, Any],
    ) -> CheckResult:
        try:
            result = fn(ctx)
            if isinstance(result, tuple) and len(result) >= 2:
                ok, msg = result[0], str(result[1])
            else:
                ok, msg = bool(result), ""
            outcome = CheckOutcome.PASSED if ok else CheckOutcome.FAILED
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            outcome = CheckOutcome.FAILED
            msg = str(exc)[:200]
        return CheckResult(
            check_id=f"ck-{uuid.uuid4().hex[:8]}",
            stage=stage,
            name=name,
            outcome=outcome,
            message=msg,
        )

    def _publish_event(self, result: ValidationResult) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "safety_validation_pipeline",
                    "action": "validation_completed",
                    "result_id": result.result_id,
                    "action_id": result.action_id,
                    "verdict": result.verdict.value,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="safety_validation_pipeline",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
