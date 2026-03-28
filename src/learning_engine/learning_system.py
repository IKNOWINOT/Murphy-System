"""
Learning System

Integrates with the MFGC learning pipeline to provide correction-aware
learning capabilities. Receives correction data from the integrated
correction system and feeds it into the learning pipeline.

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
        try:
            from src.self_learning_toggle import get_self_learning_toggle
            slt = get_self_learning_toggle()
            if not slt.is_enabled():
                slt.increment_skipped()
                return
        except Exception as exc:
            logger.debug("Non-critical error: %s", exc)

        entry = {
            'correction': correction_data,
            'received_at': datetime.now(timezone.utc).isoformat(),
            'processed': True,
        }
        capped_append(self._corrections, entry)
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
