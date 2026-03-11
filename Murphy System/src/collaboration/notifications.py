"""
Collaboration System – Notification Engine
============================================

In-memory notification engine that creates, delivers, and manages
notifications for users.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .models import (
    Notification,
    NotificationStatus,
    NotificationType,
    _new_id,
    _now,
)

logger = logging.getLogger(__name__)


class NotificationEngine:
    """In-memory notification management engine.

    Stores notifications per user and supports read/archive/list operations.
    """

    def __init__(self) -> None:
        self._notifications: Dict[str, List[Notification]] = {}  # user_id → list

    def send(
        self,
        *,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str = "",
        board_id: str = "",
        entity_type: str = "",
        entity_id: str = "",
        triggered_by: str = "",
    ) -> Notification:
        """Create and store a notification for *user_id*."""
        notif = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            board_id=board_id,
            entity_type=entity_type,
            entity_id=entity_id,
            triggered_by=triggered_by,
        )
        self._notifications.setdefault(user_id, []).append(notif)
        logger.debug("Notification sent to %s: %s", user_id, title)
        return notif

    def send_to_many(
        self,
        user_ids: List[str],
        *,
        notification_type: NotificationType,
        title: str,
        body: str = "",
        board_id: str = "",
        entity_type: str = "",
        entity_id: str = "",
        triggered_by: str = "",
    ) -> List[Notification]:
        """Send the same notification to multiple users."""
        return [
            self.send(
                user_id=uid,
                notification_type=notification_type,
                title=title,
                body=body,
                board_id=board_id,
                entity_type=entity_type,
                entity_id=entity_id,
                triggered_by=triggered_by,
            )
            for uid in user_ids
        ]

    def list_notifications(
        self,
        user_id: str,
        *,
        status: Optional[NotificationStatus] = None,
        limit: int = 50,
    ) -> List[Notification]:
        """Return notifications for *user_id*, newest first."""
        notifs = self._notifications.get(user_id, [])
        if status is not None:
            notifs = [n for n in notifs if n.status == status]
        notifs = sorted(notifs, key=lambda n: n.created_at, reverse=True)
        return notifs[:limit]

    def unread_count(self, user_id: str) -> int:
        """Return the number of unread notifications."""
        return sum(
            1 for n in self._notifications.get(user_id, [])
            if n.status == NotificationStatus.UNREAD
        )

    def mark_read(self, user_id: str, notification_id: str) -> bool:
        """Mark a single notification as read."""
        for n in self._notifications.get(user_id, []):
            if n.id == notification_id:
                n.mark_read()
                return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        """Mark all unread notifications as read. Returns count marked."""
        count = 0
        for n in self._notifications.get(user_id, []):
            if n.status == NotificationStatus.UNREAD:
                n.mark_read()
                count += 1
        return count

    def archive(self, user_id: str, notification_id: str) -> bool:
        """Archive a single notification."""
        for n in self._notifications.get(user_id, []):
            if n.id == notification_id:
                n.mark_archived()
                return True
        return False

    def delete(self, user_id: str, notification_id: str) -> bool:
        """Delete a notification permanently."""
        notifs = self._notifications.get(user_id, [])
        for i, n in enumerate(notifs):
            if n.id == notification_id:
                notifs.pop(i)
                return True
        return False
