"""
Integrated HITL Monitor

Integrates human-in-the-loop monitoring with the original
murphy_runtime_analysis supervisor system.

This provides enhanced human oversight with checkpoints while
maintaining compatibility with the existing supervisor.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import original supervisor system
try:
    from .supervisor import Supervisor
    HAS_SUPERVISOR = True
except ImportError:
    HAS_SUPERVISOR = False
    logging.warning("Original Supervisor not found")

# Import new HITL system
from .hitl_models import (
    InterventionRequest,
    InterventionResponse,
    InterventionStatus,
    InterventionType,
    InterventionUrgency,
)
from .hitl_monitor import HumanInTheLoopMonitor

logger = logging.getLogger(__name__)


class IntegratedHITLMonitor:
    """
    Integrated HITL Monitor

    Combines:
    1. New HITL checkpoint system
    2. Original supervisor oversight
    3. Unified intervention requests

    This provides comprehensive human oversight that works with
    both the new checkpoint system and original supervisor.
    """

    def __init__(self):
        """Initialize integrated HITL monitor"""

        # Original supervisor
        if HAS_SUPERVISOR:
            self.supervisor = Supervisor()
            logger.info("Loaded original Supervisor")
        else:
            self.supervisor = None
            logger.warning("Original Supervisor not available")

        # New HITL monitor
        self.hitl_monitor = HumanInTheLoopMonitor()

        logger.info("IntegratedHITLMonitor initialized")

    def check_intervention_needed(
        self,
        task: Dict[str, Any],
        phase: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if human intervention is needed

        Args:
            task: Task being executed
            phase: Current execution phase
            context: Additional context

        Returns:
            True if intervention needed, False otherwise
        """

        # Check with original supervisor if available
        supervisor_needs_intervention = False
        if self.supervisor:
            try:
                supervisor_needs_intervention = self.supervisor.should_intervene(
                    task, phase
                )
            except Exception as exc:
                logger.error(f"Error checking supervisor: {exc}")

        # Check with HITL monitor
        hitl_result = self.hitl_monitor.check_intervention_needed(
            context=task, checkpoint_config=['on_high_risk', 'on_low_confidence']
        )
        hitl_needs_intervention = hitl_result is not None

        # Intervention needed if either system requests it
        needs_intervention = supervisor_needs_intervention or hitl_needs_intervention

        if needs_intervention:
            logger.info(
                f"Intervention needed for task {task.get('id')} at phase {phase} "
                f"(supervisor: {supervisor_needs_intervention}, "
                f"hitl: {hitl_needs_intervention})"
            )

        return needs_intervention

    def request_intervention(
        self,
        task: Dict[str, Any],
        intervention_type: str,
        reason: str
    ) -> InterventionRequest:
        """
        Request human intervention

        Args:
            task: Task requiring intervention
            checkpoint: Checkpoint that triggered request
            reason: Reason for intervention

        Returns:
            Intervention request
        """

        import uuid as _uuid

        intervention_type_map = {t.value: t for t in InterventionType}
        itype = intervention_type_map.get(intervention_type, InterventionType.REVIEW)

        request = InterventionRequest(
            request_id=f"req_{_uuid.uuid4().hex[:8]}",
            intervention_type=itype,
            task_id=task.get('id', 'unknown'),
            reason=reason,
            context=task
        )
        self.hitl_monitor.pending_interventions[request.request_id] = request

        logger.info(
            f"Intervention requested for task {task.get('id')}: {reason}"
        )

        # Notify original supervisor if available
        if self.supervisor:
            try:
                self.supervisor.notify_intervention_requested(
                    task_id=task.get('id'),
                    reason=reason
                )
            except Exception as exc:
                logger.error(f"Error notifying supervisor: {exc}")

        return request

    def submit_intervention_response(
        self,
        request_id: str,
        response_data: Dict[str, Any]
    ) -> InterventionResponse:
        """
        Submit human response to intervention request

        Args:
            request_id: Intervention request ID
            response_data: Response data

        Returns:
            Intervention response
        """

        response = self.hitl_monitor.respond_to_intervention(
            request_id=request_id,
            approved=response_data.get('approved', True),
            decision=response_data.get('decision', 'approve'),
            responded_by=response_data.get('responded_by', 'system'),
            feedback=response_data.get('feedback')
        )

        logger.info(
            f"Intervention response submitted for request {request_id}: "
            f"{response.decision}"
        )

        # Notify original supervisor if available
        if self.supervisor:
            try:
                self.supervisor.notify_intervention_completed(
                    request_id=request_id,
                    decision=response.decision
                )
            except Exception as exc:
                logger.error(f"Error notifying supervisor: {exc}")

        return response

    def get_pending_interventions(self) -> List[InterventionRequest]:
        """
        Get all pending intervention requests

        Returns:
            List of pending requests
        """

        return self.hitl_monitor.get_pending_interventions()

    def get_checkpoint_statistics(self) -> Dict[str, Any]:
        """
        Get checkpoint statistics

        Returns:
            Statistics dictionary
        """

        stats = {
            'total_pending': len(self.hitl_monitor.pending_interventions),
            'total_completed': len(self.hitl_monitor.completed_interventions),
            'total_interventions': (
                len(self.hitl_monitor.pending_interventions) +
                len(self.hitl_monitor.completed_interventions)
            )
        }

        # Add supervisor statistics if available
        if self.supervisor:
            try:
                supervisor_stats = self.supervisor.get_statistics()
                stats['supervisor'] = supervisor_stats
            except Exception as exc:
                logger.error(f"Error getting supervisor statistics: {exc}")

        return stats
