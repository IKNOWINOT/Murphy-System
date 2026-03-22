"""Tests for grant session management with tenant isolation."""

import pytest

from src.billing.grants import sessions
from src.billing.grants.models import GrantSession, GrantTrack


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store before each test."""
    sessions._SESSIONS.clear()
    yield
    sessions._SESSIONS.clear()


class TestCreateSession:
    def test_creates_session(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        assert isinstance(s, GrantSession)
        assert s.tenant_id == "tenant-a"
        assert s.track == GrantTrack.track_b_customer

    def test_session_has_unique_id(self):
        s1 = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        s2 = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        assert s1.session_id != s2.session_id

    def test_session_stored_in_memory(self):
        s = sessions.create_session("tenant-x", GrantTrack.track_a_murphy)
        assert s.session_id in sessions._SESSIONS

    def test_track_a(self):
        s = sessions.create_session("murphy", GrantTrack.track_a_murphy)
        assert s.track == GrantTrack.track_a_murphy


class TestGetSession:
    def test_retrieves_existing_session(self):
        created = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        retrieved = sessions.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    def test_returns_none_for_unknown(self):
        assert sessions.get_session("nonexistent-session") is None

    def test_tenant_isolation_correct_tenant(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        result = sessions.get_session(s.session_id, tenant_id="tenant-a")
        assert result is not None

    def test_tenant_isolation_wrong_tenant(self):
        """Tenant B must not be able to read Tenant A's session."""
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        result = sessions.get_session(s.session_id, tenant_id="tenant-b")
        assert result is None

    def test_no_tenant_id_returns_session(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        result = sessions.get_session(s.session_id)
        assert result is not None


class TestUpdateSession:
    def test_updates_profile_data(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        updated = sessions.update_session(s.session_id, {"state": "OR"})
        assert updated is not None
        assert updated.profile_data["state"] == "OR"

    def test_merges_profile_data(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        sessions.update_session(s.session_id, {"state": "OR"})
        sessions.update_session(s.session_id, {"entity_type": "small_business"})
        result = sessions.get_session(s.session_id)
        assert result.profile_data["state"] == "OR"
        assert result.profile_data["entity_type"] == "small_business"

    def test_returns_none_for_missing_session(self):
        result = sessions.update_session("nonexistent", {"state": "OR"})
        assert result is None

    def test_raises_on_tenant_mismatch(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        with pytest.raises(ValueError, match="tenant"):
            sessions.update_session(s.session_id, {"x": 1}, tenant_id="tenant-b")

    def test_valid_tenant_can_update(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        updated = sessions.update_session(s.session_id, {"key": "val"}, tenant_id="tenant-a")
        assert updated is not None


class TestDestroySession:
    def test_destroys_existing_session(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        result = sessions.destroy_session(s.session_id)
        assert result is True
        assert sessions.get_session(s.session_id) is None

    def test_returns_false_for_missing_session(self):
        result = sessions.destroy_session("nonexistent-session")
        assert result is False

    def test_raises_on_tenant_mismatch(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        with pytest.raises(ValueError):
            sessions.destroy_session(s.session_id, tenant_id="tenant-b")

    def test_valid_tenant_can_destroy(self):
        s = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        result = sessions.destroy_session(s.session_id, tenant_id="tenant-a")
        assert result is True


class TestListSessions:
    def test_lists_sessions_for_tenant(self):
        s1 = sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        s2 = sessions.create_session("tenant-a", GrantTrack.track_a_murphy)
        sessions.create_session("tenant-b", GrantTrack.track_b_customer)

        tenant_a_sessions = sessions.list_sessions("tenant-a")
        assert len(tenant_a_sessions) == 2
        ids = {s.session_id for s in tenant_a_sessions}
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_no_cross_tenant_leakage(self):
        sessions.create_session("tenant-a", GrantTrack.track_b_customer)
        tenant_b_sessions = sessions.list_sessions("tenant-b")
        assert tenant_b_sessions == []

    def test_empty_for_unknown_tenant(self):
        assert sessions.list_sessions("unknown-tenant-xyz") == []
