"""Tests for Phase 12 – Mobile App Backend."""

import sys, os

import pytest
from mobile.models import (
    DeviceRegistration, MobileConfig, NotificationType,
    Platform, PushNotification, SyncState, SyncStatus,
)
from mobile.mobile_manager import MobileManager


class TestModels:
    def test_device_to_dict(self):
        d = DeviceRegistration(user_id="u1", platform=Platform.IOS)
        r = d.to_dict()
        assert r["platform"] == "ios"

    def test_notification_to_dict(self):
        n = PushNotification(title="Hello", body="World")
        r = n.to_dict()
        assert r["title"] == "Hello"
        assert r["read"] is False

    def test_sync_state_to_dict(self):
        s = SyncState(device_id="d1", pending_changes=[{"a": 1}])
        r = s.to_dict()
        assert r["pending_count"] == 1

    def test_config_to_dict(self):
        c = MobileConfig(user_id="u1", theme="dark")
        r = c.to_dict()
        assert r["theme"] == "dark"
        assert len(r["notification_types"]) == 6  # all types


class TestMobileManager:
    def test_register_device(self):
        mgr = MobileManager()
        d = mgr.register_device("u1", Platform.IOS, "token-xxx")
        assert d.platform == Platform.IOS
        assert mgr.get_device(d.id) is d

    def test_list_devices(self):
        mgr = MobileManager()
        mgr.register_device("u1", Platform.IOS, "t1")
        mgr.register_device("u1", Platform.ANDROID, "t2")
        mgr.register_device("u2", Platform.IOS, "t3")
        assert len(mgr.list_devices()) == 3
        assert len(mgr.list_devices("u1")) == 2

    def test_deactivate_device(self):
        mgr = MobileManager()
        d = mgr.register_device("u1", Platform.IOS, "t1")
        assert mgr.deactivate_device(d.id)
        assert len(mgr.list_devices("u1")) == 0  # inactive filtered
        assert not mgr.deactivate_device("bad")

    def test_send_notification(self):
        mgr = MobileManager()
        mgr.register_device("u1", Platform.IOS, "t1")
        mgr.register_device("u1", Platform.ANDROID, "t2")
        notifs = mgr.send_notification("u1", "Title", "Body")
        assert len(notifs) == 2

    def test_list_notifications(self):
        mgr = MobileManager()
        mgr.register_device("u1", Platform.IOS, "t1")
        mgr.send_notification("u1", "A", "body")
        mgr.send_notification("u1", "B", "body")
        assert len(mgr.list_notifications("u1")) == 2

    def test_list_notifications_unread_only(self):
        mgr = MobileManager()
        mgr.register_device("u1", Platform.IOS, "t1")
        notifs = mgr.send_notification("u1", "A", "body")
        mgr.mark_read(notifs[0].id)
        mgr.send_notification("u1", "B", "body")
        assert len(mgr.list_notifications("u1", unread_only=True)) == 1

    def test_mark_read(self):
        mgr = MobileManager()
        mgr.register_device("u1", Platform.IOS, "t1")
        notifs = mgr.send_notification("u1", "A", "body")
        assert mgr.mark_read(notifs[0].id)
        assert notifs[0].read is True
        assert not mgr.mark_read("bad")

    def test_mark_delivered(self):
        mgr = MobileManager()
        mgr.register_device("u1", Platform.IOS, "t1")
        notifs = mgr.send_notification("u1", "A", "body")
        assert mgr.mark_delivered(notifs[0].id)
        assert notifs[0].delivered is True

    def test_sync_state(self):
        mgr = MobileManager()
        d = mgr.register_device("u1", Platform.IOS, "t1")
        state = mgr.get_sync_state(d.id)
        assert state.sync_status == SyncStatus.SYNCED

    def test_push_changes(self):
        mgr = MobileManager()
        d = mgr.register_device("u1", Platform.IOS, "t1")
        state = mgr.push_changes(d.id, [{"action": "update", "item": "i1"}])
        assert state.sync_status == SyncStatus.PENDING
        assert len(state.pending_changes) == 1

    def test_sync_complete(self):
        mgr = MobileManager()
        d = mgr.register_device("u1", Platform.IOS, "t1")
        mgr.push_changes(d.id, [{"action": "update"}])
        state = mgr.sync_complete(d.id)
        assert state.sync_status == SyncStatus.SYNCED
        assert len(state.pending_changes) == 0

    def test_conflict_resolution(self):
        mgr = MobileManager()
        d = mgr.register_device("u1", Platform.IOS, "t1")
        mgr.report_conflict(d.id, ["item1", "item2"])
        state = mgr.get_sync_state(d.id)
        assert state.sync_status == SyncStatus.CONFLICT
        assert len(state.conflict_items) == 2
        state = mgr.resolve_conflicts(d.id)
        assert state.sync_status == SyncStatus.SYNCED
        assert len(state.conflict_items) == 0

    def test_get_config(self):
        mgr = MobileManager()
        c = mgr.get_config("u1")
        assert c.user_id == "u1"
        assert c.notifications_enabled is True

    def test_update_config(self):
        mgr = MobileManager()
        c = mgr.update_config("u1", theme="dark", offline_boards=["b1"])
        assert c.theme == "dark"
        assert c.offline_boards == ["b1"]


class TestAPIRouter:
    def test_create_router(self):
        from mobile.api import create_mobile_router
        router = create_mobile_router()
        assert router is not None
