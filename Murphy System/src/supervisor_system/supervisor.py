"""
Supervisor

Core supervisor module for human oversight and intervention management.
Works with the integrated HITL monitor to provide comprehensive
human-in-the-loop supervision.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: Apache License 2.0
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

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
        self._interventions.append(intervention)
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
        self._completed.append(completion)
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
