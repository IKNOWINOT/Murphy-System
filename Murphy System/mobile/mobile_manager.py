"""
Mobile App – Mobile Manager
==============================

Device registration, push notifications, offline sync, mobile configuration.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import (
    DeviceRegistration,
    MobileConfig,
    NotificationType,
    Platform,
    PushNotification,
    SyncState,
    SyncStatus,
    _now,
)

logger = logging.getLogger(__name__)


class MobileManager:
    """In-memory mobile backend manager."""

    def __init__(self) -> None:
        self._devices: Dict[str, DeviceRegistration] = {}
        self._notifications: Dict[str, PushNotification] = {}
        self._sync_states: Dict[str, SyncState] = {}  # device_id → state
        self._configs: Dict[str, MobileConfig] = {}  # user_id → config

    # -- Device registration ------------------------------------------------

    def register_device(
        self,
        user_id: str,
        platform: Platform,
        device_token: str,
        *,
        app_version: str = "",
        os_version: str = "",
    ) -> DeviceRegistration:
        device = DeviceRegistration(
            user_id=user_id,
            platform=platform,
            device_token=device_token,
            app_version=app_version,
            os_version=os_version,
        )
        self._devices[device.id] = device
        logger.info("Device registered: %s (%s)", user_id, device.id)
        return device

    def get_device(self, device_id: str) -> Optional[DeviceRegistration]:
        return self._devices.get(device_id)

    def list_devices(self, user_id: str = "") -> List[DeviceRegistration]:
        devices = [d for d in self._devices.values() if d.active]
        if user_id:
            devices = [d for d in devices if d.user_id == user_id]
        return devices

    def deactivate_device(self, device_id: str) -> bool:
        device = self._devices.get(device_id)
        if device is None:
            return False
        device.active = False
        return True

    # -- Push notifications -------------------------------------------------

    def send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        *,
        notification_type: NotificationType = NotificationType.ITEM_UPDATE,
        data: Optional[Dict[str, Any]] = None,
    ) -> List[PushNotification]:
        """Send a notification to all of a user's active devices."""
        devices = self.list_devices(user_id=user_id)
        notifications = []
        for device in devices:
            notif = PushNotification(
                user_id=user_id,
                device_id=device.id,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data or {},
            )
            self._notifications[notif.id] = notif
            notifications.append(notif)
        return notifications

    def get_notification(self, notif_id: str) -> Optional[PushNotification]:
        return self._notifications.get(notif_id)

    def list_notifications(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
    ) -> List[PushNotification]:
        notifs = [n for n in self._notifications.values() if n.user_id == user_id]
        if unread_only:
            notifs = [n for n in notifs if not n.read]
        return sorted(notifs, key=lambda n: n.created_at, reverse=True)

    def mark_read(self, notif_id: str) -> bool:
        notif = self._notifications.get(notif_id)
        if notif is None:
            return False
        notif.read = True
        return True

    def mark_delivered(self, notif_id: str) -> bool:
        notif = self._notifications.get(notif_id)
        if notif is None:
            return False
        notif.delivered = True
        return True

    # -- Offline sync -------------------------------------------------------

    def get_sync_state(self, device_id: str) -> SyncState:
        if device_id not in self._sync_states:
            device = self._devices.get(device_id)
            user_id = device.user_id if device else ""
            self._sync_states[device_id] = SyncState(
                device_id=device_id,
                user_id=user_id,
            )
        return self._sync_states[device_id]

    def push_changes(
        self,
        device_id: str,
        changes: List[Dict[str, Any]],
    ) -> SyncState:
        state = self.get_sync_state(device_id)
        state.pending_changes.extend(changes)
        state.sync_status = SyncStatus.PENDING
        return state

    def sync_complete(self, device_id: str) -> SyncState:
        state = self.get_sync_state(device_id)
        state.pending_changes.clear()
        state.sync_status = SyncStatus.SYNCED
        state.last_sync_at = _now()
        return state

    def report_conflict(self, device_id: str, item_ids: List[str]) -> SyncState:
        state = self.get_sync_state(device_id)
        state.conflict_items.extend(item_ids)
        state.sync_status = SyncStatus.CONFLICT
        return state

    def resolve_conflicts(self, device_id: str) -> SyncState:
        state = self.get_sync_state(device_id)
        state.conflict_items.clear()
        if not state.pending_changes:
            state.sync_status = SyncStatus.SYNCED
        else:
            state.sync_status = SyncStatus.PENDING
        return state

    # -- Mobile config ------------------------------------------------------

    def get_config(self, user_id: str) -> MobileConfig:
        if user_id not in self._configs:
            self._configs[user_id] = MobileConfig(user_id=user_id)
        return self._configs[user_id]

    def update_config(
        self,
        user_id: str,
        *,
        notifications_enabled: Optional[bool] = None,
        notification_types: Optional[List[str]] = None,
        offline_boards: Optional[List[str]] = None,
        quick_add_board_id: Optional[str] = None,
        theme: Optional[str] = None,
    ) -> MobileConfig:
        config = self.get_config(user_id)
        if notifications_enabled is not None:
            config.notifications_enabled = notifications_enabled
        if notification_types is not None:
            config.notification_types = notification_types
        if offline_boards is not None:
            config.offline_boards = offline_boards
        if quick_add_board_id is not None:
            config.quick_add_board_id = quick_add_board_id
        if theme is not None:
            config.theme = theme
        return config
