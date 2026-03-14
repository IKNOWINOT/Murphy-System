"""
Supervisor

Core supervisor module for human oversight and intervention management.
Works with the integrated HITL monitor to provide comprehensive
human-in-the-loop supervision.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class Supervisor:
    """
    Core supervisor for Murphy System execution oversight.

    Manages:
    - Intervention decision logic
    - Notification routing for intervention events
    - Supervision statistics tracking
    """

    def __init__(self):
        self._interventions: List[Dict[str, Any]] = []
        self._completed: List[Dict[str, Any]] = []
        logger.info("Supervisor initialized")

    def should_intervene(self, task: Dict[str, Any], phase: str) -> bool:
        """
        Determine if human intervention is needed for a task.

        Args:
            task: Task being executed
            phase: Current execution phase

        Returns:
            True if intervention is recommended
        """
        risk_level = task.get('risk_level', 'low')
        confidence = task.get('confidence', 1.0)

        if risk_level in ('critical', 'high'):
            return True
        if confidence < 0.3:
            return True
        if phase in ('commitment', 'execution') and risk_level == 'medium':
            return True

        return False

    def notify_intervention_requested(
        self,
        task_id: str,
        reason: str
    ) -> None:
        """
        Notify supervisor that an intervention has been requested.

        Args:
            task_id: ID of the task requiring intervention
            reason: Reason for the intervention request
        """
        intervention = {
            'task_id': task_id,
            'reason': reason,
            'requested_at': datetime.now(timezone.utc).isoformat(),
            'status': 'pending',
        }
        capped_append(self._interventions, intervention)
        logger.info(f"Intervention requested for task {task_id}: {reason}")

    def notify_intervention_completed(
        self,
        request_id: str,
        decision: str
    ) -> None:
        """
        Notify supervisor that an intervention has been completed.

        Args:
            request_id: ID of the intervention request
            decision: Decision made during intervention
        """
        completion = {
            'request_id': request_id,
            'decision': decision,
            'completed_at': datetime.now(timezone.utc).isoformat(),
        }
        capped_append(self._completed, completion)
        logger.info(f"Intervention {request_id} completed: {decision}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get supervisor statistics.

        Returns:
            Statistics dictionary
        """
        return {
            'total_interventions': len(self._interventions),
            'completed_interventions': len(self._completed),
            'pending_interventions': len(self._interventions) - len(self._completed),
        }
