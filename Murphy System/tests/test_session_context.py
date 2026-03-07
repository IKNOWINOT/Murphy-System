"""Tests for the Session Context Manager (SCM).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import threading
import time

import pytest

from session_context import SessionManager, SessionContext


@pytest.fixture
def manager():
    """Return a fresh SessionManager with default expiry."""
    return SessionManager(expiry_seconds=3600)


@pytest.fixture
def short_expiry_manager():
    """Return a SessionManager with a very short expiry for timeout tests."""
    return SessionManager(expiry_seconds=0.1)


# ------------------------------------------------------------------
# 1. Create / get / update session lifecycle
# ------------------------------------------------------------------

class TestSessionLifecycle:

    def test_create_and_get_session(self, manager):
        ctx = manager.create_session(user_input="hello", active_project="proj1")
        assert isinstance(ctx, SessionContext)
        assert ctx.user_input == "hello"
        assert ctx.active_project == "proj1"

        retrieved = manager.get_session(ctx.session_id)
        assert retrieved is not None
        assert retrieved.session_id == ctx.session_id

    def test_create_session_defaults(self, manager):
        ctx = manager.create_session()
        assert ctx.user_input == ""
        assert ctx.active_project == ""
        assert ctx.resolution_level == "RM0"
        assert ctx.previous_messages == []
        assert ctx.known_modules == []

    def test_update_context_returns_updated_session(self, manager):
        ctx = manager.create_session()
        updated = manager.update_context(
            ctx.session_id,
            user_input="updated",
            active_project="new_proj",
        )
        assert updated is not None
        assert updated.user_input == "updated"
        assert updated.active_project == "new_proj"

    def test_update_context_ignores_unknown_fields(self, manager):
        ctx = manager.create_session(user_input="orig")
        updated = manager.update_context(ctx.session_id, bogus_field="ignored")
        assert updated is not None
        assert updated.user_input == "orig"


# ------------------------------------------------------------------
# 2. Bounded message history caps at 100
# ------------------------------------------------------------------

class TestBoundedMessageHistory:

    def test_messages_capped_at_100(self, manager):
        ctx = manager.create_session()
        for i in range(120):
            assert manager.add_message(ctx.session_id, f"msg-{i}") is True

        retrieved = manager.get_session(ctx.session_id)
        assert len(retrieved.previous_messages) == 100
        # The oldest messages should have been dropped
        assert retrieved.previous_messages[-1] == "msg-119"


# ------------------------------------------------------------------
# 3. Session expiry after timeout
# ------------------------------------------------------------------

class TestSessionExpiry:

    def test_session_expires_after_timeout(self, short_expiry_manager):
        ctx = short_expiry_manager.create_session()
        sid = ctx.session_id
        time.sleep(0.2)
        assert short_expiry_manager.get_session(sid) is None

    def test_add_message_fails_on_expired_session(self, short_expiry_manager):
        ctx = short_expiry_manager.create_session()
        time.sleep(0.2)
        assert short_expiry_manager.add_message(ctx.session_id, "late") is False


# ------------------------------------------------------------------
# 4. Thread safety with concurrent session updates
# ------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_add_messages(self, manager):
        ctx = manager.create_session()
        sid = ctx.session_id
        errors = []

        def worker(thread_id):
            try:
                for i in range(10):
                    manager.add_message(sid, f"t{thread_id}-m{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        retrieved = manager.get_session(sid)
        assert len(retrieved.previous_messages) <= 100

    def test_concurrent_create_sessions(self, manager):
        results = []

        def creator():
            ctx = manager.create_session()
            if ctx:
                results.append(ctx.session_id)

        threads = [threading.Thread(target=creator) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        assert len(set(results)) == 20  # all unique IDs


# ------------------------------------------------------------------
# 5. Resolution level tracking (RM0–RM6)
# ------------------------------------------------------------------

class TestResolutionLevel:

    @pytest.mark.parametrize("level", [f"RM{i}" for i in range(7)])
    def test_valid_resolution_levels(self, manager, level):
        ctx = manager.create_session()
        assert manager.set_resolution_level(ctx.session_id, level) is True
        retrieved = manager.get_session(ctx.session_id)
        assert retrieved.resolution_level == level

    @pytest.mark.parametrize("level", ["RM7", "RM-1", "rm0", "invalid", ""])
    def test_invalid_resolution_levels_rejected(self, manager, level):
        ctx = manager.create_session()
        assert manager.set_resolution_level(ctx.session_id, level) is False
        retrieved = manager.get_session(ctx.session_id)
        assert retrieved.resolution_level == "RM0"  # unchanged


# ------------------------------------------------------------------
# 6. Delete session
# ------------------------------------------------------------------

class TestDeleteSession:

    def test_delete_existing_session(self, manager):
        ctx = manager.create_session()
        assert manager.delete_session(ctx.session_id) is True
        assert manager.get_session(ctx.session_id) is None

    def test_delete_nonexistent_session(self, manager):
        assert manager.delete_session("nonexistent-id") is False


# ------------------------------------------------------------------
# 7. List sessions
# ------------------------------------------------------------------

class TestListSessions:

    def test_list_sessions_returns_active_ids(self, manager):
        ctx1 = manager.create_session()
        ctx2 = manager.create_session()
        ids = manager.list_sessions()
        assert ctx1.session_id in ids
        assert ctx2.session_id in ids

    def test_list_sessions_excludes_expired(self, short_expiry_manager):
        ctx = short_expiry_manager.create_session()
        assert ctx.session_id in short_expiry_manager.list_sessions()
        time.sleep(0.2)
        assert ctx.session_id not in short_expiry_manager.list_sessions()


# ------------------------------------------------------------------
# 8. Get active modules
# ------------------------------------------------------------------

class TestGetActiveModules:

    def test_get_active_modules(self, manager):
        ctx = manager.create_session()
        manager.update_context(ctx.session_id, known_modules=["modA", "modB"])
        modules = manager.get_active_modules(ctx.session_id)
        assert modules == ["modA", "modB"]

    def test_get_active_modules_returns_copy(self, manager):
        ctx = manager.create_session()
        manager.update_context(ctx.session_id, known_modules=["modA"])
        modules = manager.get_active_modules(ctx.session_id)
        modules.append("modC")
        assert manager.get_active_modules(ctx.session_id) == ["modA"]

    def test_get_active_modules_nonexistent_session(self, manager):
        assert manager.get_active_modules("no-such-id") == []


# ------------------------------------------------------------------
# 9. Update context with various fields
# ------------------------------------------------------------------

class TestUpdateContextFields:

    def test_update_multiple_fields(self, manager):
        ctx = manager.create_session()
        updated = manager.update_context(
            ctx.session_id,
            system_architecture={"type": "micro"},
            regulatory_environment=["GDPR", "HIPAA"],
            cost_models={"tier": "enterprise"},
        )
        assert updated.system_architecture == {"type": "micro"}
        assert updated.regulatory_environment == ["GDPR", "HIPAA"]
        assert updated.cost_models == {"tier": "enterprise"}

    def test_update_refreshes_last_accessed(self, manager):
        ctx = manager.create_session()
        old_ts = ctx.last_accessed
        time.sleep(0.01)
        updated = manager.update_context(ctx.session_id, user_input="new")
        assert updated.last_accessed >= old_ts


# ------------------------------------------------------------------
# 10. Cleanup expired sessions
# ------------------------------------------------------------------

class TestCleanupExpired:

    def test_cleanup_removes_expired(self, short_expiry_manager):
        ctx1 = short_expiry_manager.create_session()
        ctx2 = short_expiry_manager.create_session()
        time.sleep(0.2)
        removed = short_expiry_manager.cleanup_expired()
        assert removed == 2
        assert short_expiry_manager.list_sessions() == []

    def test_cleanup_keeps_active_sessions(self, short_expiry_manager):
        ctx1 = short_expiry_manager.create_session()
        time.sleep(0.2)
        ctx2 = short_expiry_manager.create_session()  # still fresh
        removed = short_expiry_manager.cleanup_expired()
        assert removed == 1
        active = short_expiry_manager.list_sessions()
        assert ctx2.session_id in active
        assert ctx1.session_id not in active


# ------------------------------------------------------------------
# 11. Max sessions limit
# ------------------------------------------------------------------

class TestMaxSessionsLimit:

    def test_create_session_returns_none_at_capacity(self):
        mgr = SessionManager(expiry_seconds=3600)
        # Simulate being at capacity by injecting fake sessions
        from session_context import _MAX_SESSIONS
        for i in range(_MAX_SESSIONS):
            mgr._sessions[f"fake-{i}"] = SessionContext(session_id=f"fake-{i}")
        result = mgr.create_session()
        assert result is None


# ------------------------------------------------------------------
# 12. Non-existent session handling
# ------------------------------------------------------------------

class TestNonExistentSession:

    def test_get_nonexistent_returns_none(self, manager):
        assert manager.get_session("does-not-exist") is None

    def test_update_nonexistent_returns_none(self, manager):
        assert manager.update_context("does-not-exist", user_input="x") is None

    def test_add_message_nonexistent_returns_false(self, manager):
        assert manager.add_message("does-not-exist", "msg") is False

    def test_set_resolution_nonexistent_returns_false(self, manager):
        assert manager.set_resolution_level("does-not-exist", "RM1") is False
