"""
Collaboration System – Activity Feed
======================================

Board-level and global activity feed aggregation.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from .models import ActivityFeedEntry, FeedEventType, _now

try:
    from thread_safe_operations import capped_append
except ImportError:

    def capped_append(target_list: list, item: object, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)


logger = logging.getLogger(__name__)


class ActivityFeed:
    """In-memory activity feed aggregation engine."""

    def __init__(self) -> None:
        self._entries: List[ActivityFeedEntry] = []
        self._lock = threading.Lock()

    def record(
        self,
        event_type: FeedEventType,
        *,
        board_id: str = "",
        item_id: str = "",
        user_id: str = "",
        user_name: str = "",
        summary: str = "",
        details: Optional[Dict] = None,
    ) -> ActivityFeedEntry:
        """Record a new activity feed entry."""
        entry = ActivityFeedEntry(
            event_type=event_type,
            board_id=board_id,
            item_id=item_id,
            user_id=user_id,
            user_name=user_name,
            summary=summary,
            details=details or {},
        )
        with self._lock:
            capped_append(self._entries, entry)
        logger.debug("Feed entry: %s by %s", event_type.value, user_id)
        return entry

    def get_board_feed(
        self,
        board_id: str,
        *,
        limit: int = 50,
        event_type: Optional[FeedEventType] = None,
    ) -> List[ActivityFeedEntry]:
        """Return feed entries for a specific board, newest first."""
        with self._lock:
            entries = [e for e in self._entries if e.board_id == board_id]
        if event_type is not None:
            entries = [e for e in entries if e.event_type == event_type]
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    def get_user_feed(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> List[ActivityFeedEntry]:
        """Return feed entries triggered by or relevant to a user."""
        with self._lock:
            entries = [e for e in self._entries if e.user_id == user_id]
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    def get_global_feed(self, *, limit: int = 50) -> List[ActivityFeedEntry]:
        """Return the most recent feed entries across all boards."""
        with self._lock:
            entries = sorted(self._entries, key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    def get_item_feed(
        self,
        item_id: str,
        *,
        limit: int = 50,
    ) -> List[ActivityFeedEntry]:
        """Return feed entries for a specific item."""
        with self._lock:
            entries = [e for e in self._entries if e.item_id == item_id]
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]
