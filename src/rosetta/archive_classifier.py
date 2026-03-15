"""
Archive Classifier for Rosetta State Management.

Classifies items for archival and manages the archive log within
a RosettaAgentState document.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from .rosetta_models import ArchiveEntry, RosettaAgentState

logger = logging.getLogger(__name__)


class ArchiveClassifier:
    """Rule-based classifier that decides archive category and eligibility."""

    CATEGORIES = ["completed_goal", "failed_task", "stale_data", "superseded", "manual"]

    def classify(self, item: Dict[str, Any]) -> str:
        """Classify an item into an archive category based on its status."""
        status = str(item.get("status", "")).lower()
        if status == "completed":
            return "completed_goal"
        if status == "failed":
            return "failed_task"
        if self._is_stale(item):
            return "stale_data"
        return "manual"

    def should_archive(self, item: Dict[str, Any], max_age_days: int = 30) -> bool:
        """Return True if the item should be archived."""
        status = str(item.get("status", "")).lower()
        if status in ("completed", "failed"):
            return True
        return self._is_stale(item, max_age_days=max_age_days)

    def archive_item(
        self,
        state: RosettaAgentState,
        item: Dict[str, Any],
        reason: str,
    ) -> RosettaAgentState:
        """Append an item to the state's archive log and return updated state."""
        category = self.classify(item)
        entry = ArchiveEntry(
            entry_id=str(uuid.uuid4()),
            archived_at=datetime.now(timezone.utc),
            reason=reason,
            category=category,
            data=item,
        )
        state.archive_log.entries.append(entry)
        state.archive_log.total_archived = len(state.archive_log.entries)
        return state

    # ---- internal ----

    @staticmethod
    def _is_stale(item: Dict[str, Any], max_age_days: int = 30) -> bool:
        """Check if the item is older than *max_age_days*."""
        raw = item.get("updated_at") or item.get("created_at")
        if raw is None:
            return False
        try:
            if isinstance(raw, datetime):
                ts = raw
            else:
                ts = datetime.fromisoformat(str(raw))
            return datetime.now(timezone.utc) - ts > timedelta(days=max_age_days)
        except (ValueError, TypeError):
            return False
