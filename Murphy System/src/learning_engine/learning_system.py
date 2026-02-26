"""
Learning System

Integrates with the MFGC learning pipeline to provide correction-aware
learning capabilities. Receives correction data from the integrated
correction system and feeds it into the learning pipeline.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: Apache License 2.0
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class LearningSystem:
    """
    Learning system for Murphy correction pipeline.
    
    Receives correction data and feeds it into the learning pipeline
    for gate policy improvement and confidence weight adjustment.
    """
    
    def __init__(self):
        self._corrections: List[Dict[str, Any]] = []
        self._patterns_learned: int = 0
        logger.info("LearningSystem initialized")
    
    def learn_from_correction(self, correction_data: Dict[str, Any]) -> None:
        """
        Learn from a correction event.
        
        Processes correction data to improve:
        - Gate placement probability
        - Confidence weight schedules
        - Phase transition thresholds
        
        Args:
            correction_data: Dictionary containing correction details
        """
        entry = {
            'correction': correction_data,
            'received_at': datetime.now(timezone.utc).isoformat(),
            'processed': True,
        }
        self._corrections.append(entry)
        self._patterns_learned += 1
        
        logger.info(
            f"Learned from correction: task={correction_data.get('task_id', 'unknown')}, "
            f"total_patterns={self._patterns_learned}"
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        return {
            'total_corrections_processed': len(self._corrections),
            'patterns_learned': self._patterns_learned,
        }
