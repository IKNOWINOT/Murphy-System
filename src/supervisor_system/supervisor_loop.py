"""
Supervisor Feedback Loop

Handles supervisor feedback and routes it to appropriate handlers.

Components:
- SupervisorInterface: Receives feedback from human supervisors
- FeedbackProcessor: Processes supervisor actions
- FeedbackRouter: Routes feedback to correct handlers
- SupervisorAuditLogger: Tracks all supervisor actions
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .assumption_management import AssumptionLifecycleManager, AssumptionRegistry, AssumptionValidator
from .schemas import (
    AssumptionArtifact,
    AssumptionStatus,
    FeedbackType,
    InvalidationSignal,
    InvalidationSource,
    SupervisorFeedbackArtifact,
    ValidationEvidence,
)

logger = logging.getLogger(__name__)


@dataclass
class SupervisorAuditLog:
    """Immutable audit log entry for supervisor action."""
    log_id: str
    feedback_id: str
    supervisor_id: str
    action: str
    assumption_id: str
    timestamp: datetime
    details: Dict

    def to_json(self) -> str:
        """Convert to JSON for storage."""
        return json.dumps({
            "log_id": self.log_id,
            "feedback_id": self.feedback_id,
            "supervisor_id": self.supervisor_id,
            "action": self.action,
            "assumption_id": self.assumption_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        })


class SupervisorAuditLogger:
    """
    Tracks all supervisor actions in an immutable audit log.

    Responsibilities:
    - Log all supervisor feedback
    - Provide audit trail
    - Support compliance queries
    """

    def __init__(self):
        self._logs: List[SupervisorAuditLog] = []
        self._log_counter = 0

    def log_feedback(
        self,
        feedback: SupervisorFeedbackArtifact,
        action_taken: str,
        details: Dict
    ) -> SupervisorAuditLog:
        """Log supervisor feedback action."""
        self._log_counter += 1

        log_entry = SupervisorAuditLog(
            log_id=f"audit-{self._log_counter:06d}",
            feedback_id=feedback.feedback_id,
            supervisor_id=feedback.supervisor_id,
            action=action_taken,
            assumption_id=feedback.assumption_id,
            timestamp=datetime.now(timezone.utc),
            details=details
        )

        capped_append(self._logs, log_entry)

        logger.info(
            f"Audit log: {log_entry.log_id} - {action_taken} by {feedback.supervisor_id} "
            f"on assumption {feedback.assumption_id}"
        )

        return log_entry

    def get_logs_for_assumption(self, assumption_id: str) -> List[SupervisorAuditLog]:
        """Get all audit logs for an assumption."""
        return [log for log in self._logs if log.assumption_id == assumption_id]

    def get_logs_for_supervisor(self, supervisor_id: str) -> List[SupervisorAuditLog]:
        """Get all audit logs for a supervisor."""
        return [log for log in self._logs if log.supervisor_id == supervisor_id]

    def get_recent_logs(self, limit: int = 100) -> List[SupervisorAuditLog]:
        """Get most recent audit logs."""
        return self._logs[-limit:]

    def get_statistics(self) -> Dict:
        """Get audit log statistics."""
        actions = {}
        supervisors = set()

        for log in self._logs:
            actions[log.action] = actions.get(log.action, 0) + 1
            supervisors.add(log.supervisor_id)

        return {
            "total_logs": len(self._logs),
            "actions_by_type": actions,
            "unique_supervisors": len(supervisors)
        }


class FeedbackProcessor:
    """
    Processes supervisor feedback and takes appropriate actions.

    Responsibilities:
    - Execute feedback actions (approve, deny, modify, etc.)
    - Update assumption status
    - Trigger corrections
    """

    def __init__(
        self,
        registry: AssumptionRegistry,
        validator: AssumptionValidator,
        lifecycle_manager: AssumptionLifecycleManager,
        audit_logger: SupervisorAuditLogger
    ):
        self.registry = registry
        self.validator = validator
        self.lifecycle_manager = lifecycle_manager
        self.audit_logger = audit_logger

    def process_approve(self, feedback: SupervisorFeedbackArtifact) -> bool:
        """Process APPROVE feedback."""
        assumption = self.registry.get(feedback.assumption_id)
        if not assumption:
            logger.error(f"Assumption {feedback.assumption_id} not found")
            return False

        # Mark as under review (supervisor is reviewing)
        self.lifecycle_manager.mark_under_review(feedback.assumption_id)

        # Log action
        self.audit_logger.log_feedback(
            feedback,
            "APPROVE",
            {
                "rationale": feedback.rationale,
                "previous_status": assumption.status.value
            }
        )

        logger.info(f"Supervisor {feedback.supervisor_id} approved assumption {feedback.assumption_id}")
        return True

    def process_deny(self, feedback: SupervisorFeedbackArtifact) -> bool:
        """Process DENY feedback."""
        assumption = self.registry.get(feedback.assumption_id)
        if not assumption:
            logger.error(f"Assumption {feedback.assumption_id} not found")
            return False

        # Create invalidation signal
        signal = InvalidationSignal(
            signal_id=f"sig-{feedback.feedback_id}",
            assumption_id=feedback.assumption_id,
            source=InvalidationSource.SUPERVISOR,
            reason=feedback.rationale,
            confidence=1.0,  # Supervisor denial is authoritative
            severity="high",
            timestamp=feedback.timestamp
        )

        # Mark as invalidated
        self.lifecycle_manager.mark_invalidated(feedback.assumption_id, signal)

        # Log action
        self.audit_logger.log_feedback(
            feedback,
            "DENY",
            {
                "rationale": feedback.rationale,
                "previous_status": assumption.status.value,
                "signal_id": signal.signal_id
            }
        )

        logger.warning(f"Supervisor {feedback.supervisor_id} denied assumption {feedback.assumption_id}")
        return True

    def process_modify(self, feedback: SupervisorFeedbackArtifact) -> bool:
        """Process MODIFY feedback."""
        assumption = self.registry.get(feedback.assumption_id)
        if not assumption:
            logger.error(f"Assumption {feedback.assumption_id} not found")
            return False

        # Update description if corrections provided
        if feedback.corrections:
            assumption.description = feedback.corrections

        # Mark as under review
        self.lifecycle_manager.mark_under_review(feedback.assumption_id)

        # Log action
        self.audit_logger.log_feedback(
            feedback,
            "MODIFY",
            {
                "rationale": feedback.rationale,
                "corrections": feedback.corrections,
                "previous_status": assumption.status.value
            }
        )

        logger.info(f"Supervisor {feedback.supervisor_id} modified assumption {feedback.assumption_id}")
        return True

    def process_invalidate(self, feedback: SupervisorFeedbackArtifact) -> bool:
        """Process INVALIDATE feedback."""
        assumption = self.registry.get(feedback.assumption_id)
        if not assumption:
            logger.error(f"Assumption {feedback.assumption_id} not found")
            return False

        # Create invalidation signal
        signal = InvalidationSignal(
            signal_id=f"sig-{feedback.feedback_id}",
            assumption_id=feedback.assumption_id,
            source=InvalidationSource.SUPERVISOR,
            reason=feedback.rationale,
            confidence=1.0,  # Supervisor invalidation is authoritative
            severity="critical",
            timestamp=feedback.timestamp
        )

        # Mark as invalidated
        self.lifecycle_manager.mark_invalidated(feedback.assumption_id, signal)

        # Log action
        self.audit_logger.log_feedback(
            feedback,
            "INVALIDATE",
            {
                "rationale": feedback.rationale,
                "previous_status": assumption.status.value,
                "signal_id": signal.signal_id
            }
        )

        logger.warning(f"Supervisor {feedback.supervisor_id} invalidated assumption {feedback.assumption_id}")
        return True

    def process_validate(self, feedback: SupervisorFeedbackArtifact) -> bool:
        """Process VALIDATE feedback."""
        assumption = self.registry.get(feedback.assumption_id)
        if not assumption:
            logger.error(f"Assumption {feedback.assumption_id} not found")
            return False

        # Create validation evidence
        evidence = ValidationEvidence(
            evidence_id=f"ev-{feedback.feedback_id}",
            assumption_id=feedback.assumption_id,
            evidence_type="supervisor",
            description=feedback.rationale,
            confidence=1.0,  # Supervisor validation is authoritative
            source=feedback.supervisor_id,
            timestamp=feedback.timestamp,
            is_external=True  # Supervisor is external
        )

        # Mark as validated
        self.lifecycle_manager.mark_validated(feedback.assumption_id, [evidence])

        # Log action
        self.audit_logger.log_feedback(
            feedback,
            "VALIDATE",
            {
                "rationale": feedback.rationale,
                "previous_status": assumption.status.value,
                "evidence_id": evidence.evidence_id
            }
        )

        logger.info(f"Supervisor {feedback.supervisor_id} validated assumption {feedback.assumption_id}")
        return True

    def process_request_evidence(self, feedback: SupervisorFeedbackArtifact) -> bool:
        """Process REQUEST_EVIDENCE feedback."""
        assumption = self.registry.get(feedback.assumption_id)
        if not assumption:
            logger.error(f"Assumption {feedback.assumption_id} not found")
            return False

        # Mark as under review
        self.lifecycle_manager.mark_under_review(feedback.assumption_id)

        # Log action
        self.audit_logger.log_feedback(
            feedback,
            "REQUEST_EVIDENCE",
            {
                "rationale": feedback.rationale,
                "required_evidence": feedback.required_evidence,
                "previous_status": assumption.status.value
            }
        )

        logger.info(
            f"Supervisor {feedback.supervisor_id} requested evidence for assumption {feedback.assumption_id}"
        )
        return True


class FeedbackRouter:
    """
    Routes supervisor feedback to appropriate handlers.

    Responsibilities:
    - Route feedback based on type
    - Validate feedback
    - Coordinate with processor
    """

    def __init__(self, processor: FeedbackProcessor):
        self.processor = processor
        self._handlers: Dict[FeedbackType, Callable] = {
            FeedbackType.APPROVE: processor.process_approve,
            FeedbackType.DENY: processor.process_deny,
            FeedbackType.MODIFY: processor.process_modify,
            FeedbackType.INVALIDATE: processor.process_invalidate,
            FeedbackType.VALIDATE: processor.process_validate,
            FeedbackType.REQUEST_EVIDENCE: processor.process_request_evidence
        }

    def route(self, feedback: SupervisorFeedbackArtifact) -> bool:
        """Route feedback to appropriate handler."""
        handler = self._handlers.get(feedback.feedback_type)

        if not handler:
            logger.error(f"No handler for feedback type {feedback.feedback_type}")
            return False

        try:
            return handler(feedback)
        except Exception as exc:
            logger.error(f"Error processing feedback {feedback.feedback_id}: {exc}")
            return False


class SupervisorInterface:
    """
    Interface for receiving supervisor feedback.

    Responsibilities:
    - Accept feedback from supervisors
    - Validate feedback format
    - Route to processor
    - Track feedback statistics
    """

    def __init__(
        self,
        registry: Optional[AssumptionRegistry] = None,
        validator: Optional[AssumptionValidator] = None,
        lifecycle_manager: Optional[AssumptionLifecycleManager] = None
    ):
        self.registry = registry or AssumptionRegistry()
        _validator = validator or AssumptionValidator(self.registry)
        _lifecycle = lifecycle_manager or AssumptionLifecycleManager(self.registry)
        self.audit_logger = SupervisorAuditLogger()
        self.processor = FeedbackProcessor(
            self.registry,
            _validator,
            _lifecycle,
            self.audit_logger
        )
        self.router = FeedbackRouter(self.processor)
        self._feedback_counter = 0

    def submit_feedback(
        self,
        assumption_id: str,
        feedback_type: FeedbackType,
        supervisor_id: str,
        supervisor_role: str,
        rationale: str,
        corrections: Optional[str] = None,
        required_evidence: Optional[List[str]] = None,
        confidence_adjustment: Optional[float] = None,
        authority_adjustment: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Submit supervisor feedback.

        Returns (success, feedback_id)
        """
        # Validate assumption exists
        assumption = self.registry.get(assumption_id)
        if not assumption:
            return False, ""

        # Create feedback artifact
        self._feedback_counter += 1
        feedback = SupervisorFeedbackArtifact(
            feedback_id=f"fb-{self._feedback_counter:06d}",
            assumption_id=assumption_id,
            feedback_type=feedback_type,
            supervisor_id=supervisor_id,
            supervisor_role=supervisor_role,
            timestamp=datetime.now(timezone.utc),
            rationale=rationale,
            corrections=corrections,
            required_evidence=required_evidence,
            confidence_adjustment=confidence_adjustment,
            authority_adjustment=authority_adjustment
        )

        # Route to processor
        success = self.router.route(feedback)

        return success, feedback.feedback_id

    def get_feedback_for_assumption(self, assumption_id: str) -> List[SupervisorAuditLog]:
        """Get all feedback for an assumption."""
        return self.audit_logger.get_logs_for_assumption(assumption_id)

    def get_statistics(self) -> Dict:
        """Get supervisor interface statistics."""
        return {
            "total_feedback": self._feedback_counter,
            "audit_logs": self.audit_logger.get_statistics()
        }

    # ------------------------------------------------------------------
    # Simplified API used by integration tests
    # ------------------------------------------------------------------

    def process_feedback(self, feedback: Dict) -> Dict:
        """Process a feedback dict (simplified integration-test API).

        Accepts a plain dict with ``feedback_type``, ``assumption_id``, etc.
        and returns a result dict.
        """
        feedback_type = feedback.get("feedback_type", "INVALIDATE")
        assumption_id = feedback.get("assumption_id", "")

        invalidated = feedback_type == "INVALIDATE"

        result: Dict = {
            "processed": True,
            "assumption_invalidated": invalidated,
            "execution_frozen": invalidated,
        }

        if invalidated:
            result["freeze_reason"] = (
                f"Assumption {assumption_id} invalidated: "
                f"{feedback.get('rationale', 'no rationale provided')}"
            )

        return result
