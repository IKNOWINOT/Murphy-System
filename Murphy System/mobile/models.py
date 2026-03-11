"""
Mobile App – Data Models
==========================

Core data structures for the Mobile App backend (Phase 12 of Monday.com parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_UTC = timezone.utc


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Platform(Enum):
    """Mobile platform."""
    IOS = "ios"
    ANDROID = "android"


class SyncStatus(Enum):
    """Data sync status."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    FAILED = "failed"


class NotificationType(Enum):
    """Push notification types."""
    ITEM_UPDATE = "item_update"
    MENTION = "mention"
    ASSIGNMENT = "assignment"
    DUE_DATE = "due_date"
    COMMENT = "comment"
    STATUS_CHANGE = "status_change"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DeviceRegistration:
    """A registered mobile device."""
    id: str = field(default_factory=_new_id)
    user_id: str = ""
    platform: Platform = Platform.IOS
    device_token: str = ""
    app_version: str = ""
    os_version: str = ""
    active: bool = True
    registered_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "platform": self.platform.value,
            "device_token": self.device_token,
            "app_version": self.app_version,
            "os_version": self.os_version,
            "active": self.active,
            "registered_at": self.registered_at,
        }


@dataclass
class PushNotification:
    """A push notification to be delivered."""
    id: str = field(default_factory=_new_id)
    user_id: str = ""
    device_id: str = ""
    notification_type: NotificationType = NotificationType.ITEM_UPDATE
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    read: bool = False
    delivered: bool = False
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "notification_type": self.notification_type.value,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "read": self.read,
            "delivered": self.delivered,
            "created_at": self.created_at,
        }


@dataclass
class SyncState:
    """Offline sync state for a device."""
    id: str = field(default_factory=_new_id)
    device_id: str = ""
    user_id: str = ""
    last_sync_at: str = ""
    pending_changes: List[Dict[str, Any]] = field(default_factory=list)
    sync_status: SyncStatus = SyncStatus.SYNCED
    conflict_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "last_sync_at": self.last_sync_at,
            "pending_count": len(self.pending_changes),
            "sync_status": self.sync_status.value,
            "conflict_items": self.conflict_items,
        }


@dataclass
class MobileConfig:
    """Mobile app configuration for a user."""
    id: str = field(default_factory=_new_id)
    user_id: str = ""
    notifications_enabled: bool = True
    notification_types: List[str] = field(
        default_factory=lambda: [t.value for t in NotificationType]
    )
    offline_boards: List[str] = field(default_factory=list)
    quick_add_board_id: str = ""
    theme: str = "system"
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "notifications_enabled": self.notifications_enabled,
            "notification_types": self.notification_types,
            "offline_boards": self.offline_boards,
            "quick_add_board_id": self.quick_add_board_id,
            "theme": self.theme,
            "created_at": self.created_at,
        }
