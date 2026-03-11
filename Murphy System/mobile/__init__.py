"""
Mobile App Backend
====================

Phase 12 of Monday.com feature parity for the Murphy System.

Provides mobile app backend services including:

- **Device registration** for iOS and Android
- **Push notifications** with multiple types
- **Offline sync** with conflict resolution
- **Mobile configuration** per user
- **REST API** at ``/api/mobile``

Quick start::

    from mobile import MobileManager, Platform, NotificationType

    mgr = MobileManager()
    device = mgr.register_device("u1", Platform.IOS, "apns-token-xxx")
    mgr.send_notification("u1", "New Update", "Item #42 was updated",
                          notification_type=NotificationType.ITEM_UPDATE)
    mgr.update_config("u1", theme="dark", offline_boards=["board1"])

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "Mobile"

from .models import (
    DeviceRegistration,
    MobileConfig,
    NotificationType,
    Platform,
    PushNotification,
    SyncState,
    SyncStatus,
)
from .mobile_manager import MobileManager

try:
    from .api import create_mobile_router
except Exception:  # pragma: no cover
    create_mobile_router = None  # type: ignore[assignment]

__all__ = [
    "DeviceRegistration",
    "MobileConfig",
    "NotificationType",
    "Platform",
    "PushNotification",
    "SyncState",
    "SyncStatus",
    "MobileManager",
    "create_mobile_router",
]
