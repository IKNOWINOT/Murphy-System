"""
Human-in-the-Loop Monitor

Manages human intervention checkpoints and approval workflows.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .hitl_models import (
    InterventionRequest,
    InterventionResponse,
    InterventionStatus,
    InterventionType,
    InterventionUrgency,
)

logger = logging.getLogger(__name__)


class HumanInTheLoopMonitor:
    """
    Manages human-in-the-loop checkpoints

    Responsibilities:
    - Detect when human intervention is needed
    - Create intervention requests
    - Track pending interventions
    - Process intervention responses
    - Notify humans of pending requests
    """

    def __init__(self):
        self.pending_interventions: Dict[str, InterventionRequest] = {}
        self.completed_interventions: Dict[str, InterventionResponse] = {}

        # Checkpoint configuration
        self.checkpoint_types = {
            'before_execution': self._checkpoint_before_execution,
            'after_each_phase': self._checkpoint_after_phase,
            'on_high_risk': self._checkpoint_high_risk,
            'on_low_confidence': self._checkpoint_low_confidence,
            'on_assumption_invalidation': self._checkpoint_invalidation,
            'final_review': self._checkpoint_final_review
        }

        # Notification callbacks
        self.notification_callbacks: List[Callable] = []

    def check_intervention_needed(
        self,
        context: Any,
        checkpoint_config: List[str]
    ) -> Optional[InterventionRequest]:
        """
        Check if human intervention is needed

        Args:
            context: Execution context
            checkpoint_config: List of checkpoint types to check

        Returns:
            InterventionRequest if intervention needed, None otherwise
        """
        for checkpoint_type in checkpoint_config:
            if checkpoint_type in self.checkpoint_types:
                checkpoint_fn = self.checkpoint_types[checkpoint_type]
                intervention = checkpoint_fn(context)

                if intervention:
                    # Store pending intervention
                    self.pending_interventions[intervention.request_id] = intervention

                    # Notify humans
                    self._notify_intervention_needed(intervention)

                    logger.info(
                        f"Intervention requested: {intervention.request_id}, "
                        f"type={intervention.intervention_type.value}, "
                        f"urgency={intervention.urgency.value}"
                    )

                    return intervention

        return None

    def respond_to_intervention(
        self,
        request_id: str,
        approved: bool,
        decision: str,
        responded_by: str,
        feedback: Optional[str] = None,
        corrections: Optional[Dict[str, Any]] = None,
        modifications: Optional[Dict[str, Any]] = None
    ) -> InterventionResponse:
        """
        Process human response to intervention request

        Args:
            request_id: Request being responded to
            approved: Whether approved
            decision: Decision made
            responded_by: User who responded
            feedback: Optional feedback
            corrections: Optional corrections
            modifications: Optional modifications

        Returns:
            InterventionResponse
        """
        # Check if request exists
        if request_id not in self.pending_interventions:
            raise ValueError(f"Intervention request not found: {request_id}")

        request = self.pending_interventions[request_id]

        # Create response
        response = InterventionResponse(
            response_id=self._generate_response_id(),
            request_id=request_id,
            approved=approved,
            decision=decision,
            feedback=feedback,
            corrections=corrections,
            modifications=modifications,
            responded_by=responded_by
        )

        # Update request status
        request.status = InterventionStatus.COMPLETED

        # Move to completed
        self.completed_interventions[request_id] = response
        del self.pending_interventions[request_id]

        logger.info(
            f"Intervention responded: {request_id}, "
            f"approved={approved}, "
            f"by={responded_by}"
        )

        return response

    def get_pending_interventions(
        self,
        task_id: Optional[str] = None,
        urgency: Optional[InterventionUrgency] = None
    ) -> List[InterventionRequest]:
        """Get pending intervention requests"""
        interventions = list(self.pending_interventions.values())

        # Filter by task_id
        if task_id:
            interventions = [i for i in interventions if i.task_id == task_id]

        # Filter by urgency
        if urgency:
            interventions = [i for i in interventions if i.urgency == urgency]

        return interventions

    def cancel_intervention(self, request_id: str, reason: str):
        """Cancel a pending intervention request"""
        if request_id in self.pending_interventions:
            request = self.pending_interventions[request_id]
            request.status = InterventionStatus.CANCELLED
            request.metadata['cancellation_reason'] = reason

            del self.pending_interventions[request_id]

            logger.info(f"Intervention cancelled: {request_id}, reason={reason}")

    def register_notification_callback(self, callback: Callable):
        """Register callback for intervention notifications"""
        self.notification_callbacks.append(callback)

    def _notify_intervention_needed(self, intervention: InterventionRequest):
        """Notify humans that intervention is needed"""
        for callback in self.notification_callbacks:
            try:
                callback(intervention)
            except Exception as exc:
                logger.error(f"Notification callback failed: {exc}")

    # ========================================================================
    # CHECKPOINT IMPLEMENTATIONS
    # ========================================================================

    def _checkpoint_before_execution(
        self,
        context: Any
    ) -> Optional[InterventionRequest]:
        """Check before any execution"""
        phase = getattr(context, 'current_phase', None)

        if phase == 'execute' and not getattr(context, 'human_approved', False):
            return InterventionRequest(
                request_id=self._generate_request_id(),
                intervention_type=InterventionType.APPROVAL,
                urgency=InterventionUrgency.HIGH,
                task_id=getattr(context, 'task_id', 'unknown'),
                phase=phase,
                reason='Execution requires human approval before proceeding',
                context=context.to_dict() if hasattr(context, 'to_dict') else {},
                blocking=True
            )

        return None

    def _checkpoint_after_phase(
        self,
        context: Any
    ) -> Optional[InterventionRequest]:
        """Check after each phase completion"""
        if getattr(context, 'phase_completed', False):
            phase = getattr(context, 'current_phase', 'unknown')

            return InterventionRequest(
                request_id=self._generate_request_id(),
                intervention_type=InterventionType.REVIEW,
                urgency=InterventionUrgency.MEDIUM,
                task_id=getattr(context, 'task_id', 'unknown'),
                phase=phase,
                reason=f'Phase {phase} completed, review requested',
                context=context.to_dict() if hasattr(context, 'to_dict') else {},
                blocking=False
            )

        return None

    def _checkpoint_high_risk(
        self,
        context: Any
    ) -> Optional[InterventionRequest]:
        """Check for high-risk operations"""
        risk_score = getattr(context, 'risk_score', 0.0)

        if risk_score > 0.7:
            return InterventionRequest(
                request_id=self._generate_request_id(),
                intervention_type=InterventionType.APPROVAL,
                urgency=InterventionUrgency.HIGH,
                task_id=getattr(context, 'task_id', 'unknown'),
                phase=getattr(context, 'current_phase', None),
                reason=f'High risk operation detected (risk: {risk_score:.2f})',
                context={
                    'risk_score': risk_score,
                    'context': context.to_dict() if hasattr(context, 'to_dict') else {}
                },
                blocking=True
            )

        return None

    def _checkpoint_low_confidence(
        self,
        context: Any
    ) -> Optional[InterventionRequest]:
        """Check for low confidence"""
        confidence = getattr(context, 'confidence', 1.0)
        threshold = getattr(context, 'confidence_threshold', 0.7)

        if confidence < threshold:
            return InterventionRequest(
                request_id=self._generate_request_id(),
                intervention_type=InterventionType.REVIEW,
                urgency=InterventionUrgency.MEDIUM,
                task_id=getattr(context, 'task_id', 'unknown'),
                phase=getattr(context, 'current_phase', None),
                reason=f'Low confidence detected (confidence: {confidence:.2f}, threshold: {threshold:.2f})',
                context={
                    'confidence': confidence,
                    'threshold': threshold,
                    'context': context.to_dict() if hasattr(context, 'to_dict') else {}
                },
                blocking=True
            )

        return None

    def _checkpoint_invalidation(
        self,
        context: Any
    ) -> Optional[InterventionRequest]:
        """Check for assumption invalidations"""
        invalidated = getattr(context, 'invalidated_assumptions', [])

        if invalidated:
            return InterventionRequest(
                request_id=self._generate_request_id(),
                intervention_type=InterventionType.CORRECTION,
                urgency=InterventionUrgency.HIGH,
                task_id=getattr(context, 'task_id', 'unknown'),
                phase=getattr(context, 'current_phase', None),
                reason=f'{len(invalidated)} assumptions invalidated',
                context={
                    'invalidated_assumptions': invalidated,
                    'context': context.to_dict() if hasattr(context, 'to_dict') else {}
                },
                blocking=True
            )

        return None

    def _checkpoint_final_review(
        self,
        context: Any
    ) -> Optional[InterventionRequest]:
        """Final review before completion"""
        phase = getattr(context, 'current_phase', None)
        phase_completed = getattr(context, 'phase_completed', False)

        if phase == 'execute' and phase_completed:
            return InterventionRequest(
                request_id=self._generate_request_id(),
                intervention_type=InterventionType.VALIDATION,
                urgency=InterventionUrgency.MEDIUM,
                task_id=getattr(context, 'task_id', 'unknown'),
                phase=phase,
                reason='Final review before marking task complete',
                context=context.to_dict() if hasattr(context, 'to_dict') else {},
                blocking=True
            )

        return None

    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        return f"req_{uuid.uuid4().hex[:8]}"

    def _generate_response_id(self) -> str:
        """Generate unique response ID"""
        return f"resp_{uuid.uuid4().hex[:8]}"
