"""
Test: Session Isolation — Zero Data Bleed Between Tenants

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.sessions import SessionManager, TenantAccessError


@pytest.fixture
def mgr():
    return SessionManager()


def test_two_accounts_get_separate_sessions(mgr):
    """Sessions created by account A should not appear for account B."""
    s_a = mgr.create_session("account_a", "A's Session")
    s_b = mgr.create_session("account_b", "B's Session")

    sessions_a = mgr.list_sessions("account_a")
    sessions_b = mgr.list_sessions("account_b")

    a_ids = {s.session_id for s in sessions_a}
    b_ids = {s.session_id for s in sessions_b}

    assert s_a.session_id in a_ids
    assert s_b.session_id in b_ids
    assert s_a.session_id not in b_ids, "Account B can see Account A's session — data bleed!"
    assert s_b.session_id not in a_ids, "Account A can see Account B's session — data bleed!"


def test_cross_tenant_access_raises_error(mgr):
    """Account B cannot access Account A's session."""
    s_a = mgr.create_session("account_a", "A's Session")
    with pytest.raises(TenantAccessError):
        mgr.get_session(s_a.session_id, "account_b")


def test_form_data_isolated_per_session(mgr):
    """Form data saved in session A must not appear in session B."""
    s_a = mgr.create_session("account_a", "A's Session")
    s_b = mgr.create_session("account_b", "B's Session")

    mgr.update_form_data(s_a.session_id, "company_name", "Inoni LLC", "account_a")

    data_b = mgr.get_form_data(s_b.session_id, "account_b")
    assert "company_name" not in data_b, "Form data from session A leaked into session B"


def test_applications_isolated_per_session(mgr):
    """Applications in session A must not appear in session B."""
    s_a = mgr.create_session("account_a", "A's Session")
    s_b = mgr.create_session("account_b", "B's Session")

    app_a = mgr.create_application(s_a.session_id, "sbir_phase1", "account_a")

    apps_b = mgr.list_applications(s_b.session_id, "account_b")
    app_ids_b = {a.application_id for a in apps_b}
    assert app_a.application_id not in app_ids_b, "Application from session A leaked into session B"


def test_cross_tenant_form_data_access_raises(mgr):
    """Account B cannot read Account A's form data."""
    s_a = mgr.create_session("account_a", "A's Session")
    mgr.update_form_data(s_a.session_id, "key", "value", "account_a")
    with pytest.raises(TenantAccessError):
        mgr.get_form_data(s_a.session_id, "account_b")


def test_cross_tenant_application_create_raises(mgr):
    """Account B cannot create applications in Account A's session."""
    s_a = mgr.create_session("account_a", "A's Session")
    with pytest.raises(TenantAccessError):
        mgr.create_application(s_a.session_id, "sbir_phase1", "account_b")


def test_delete_session_clears_data(mgr):
    """Deleting a session clears its form data and applications."""
    s = mgr.create_session("account_a", "My Session")
    mgr.update_form_data(s.session_id, "key", "value", "account_a")
    mgr.create_application(s.session_id, "sbir_phase1", "account_a")

    mgr.delete_session(s.session_id, "account_a")

    data = mgr.get_form_data(s.session_id, "account_a")
    assert len(data) == 0

    apps = mgr.list_applications(s.session_id, "account_a")
    assert len(apps) == 0


def test_max_sessions_per_account_enforced(mgr, monkeypatch):
    """Creating more than GRANT_MAX_SESSIONS_PER_ACCOUNT sessions raises ValueError."""
    monkeypatch.setenv("GRANT_MAX_SESSIONS_PER_ACCOUNT", "2")
    mgr.create_session("account_x", "Session 1")
    mgr.create_session("account_x", "Session 2")
    with pytest.raises(ValueError, match="maximum"):
        mgr.create_session("account_x", "Session 3")


def test_multiple_accounts_independent(mgr):
    """Multiple accounts can all have sessions without interfering."""
    for i in range(5):
        mgr.create_session(f"account_{i}", f"Session {i}")
        mgr.update_form_data(
            mgr.list_sessions(f"account_{i}")[0].session_id,
            "index",
            i,
            f"account_{i}",
        )

    for i in range(5):
        sessions = mgr.list_sessions(f"account_{i}")
        assert len(sessions) == 1
        data = mgr.get_form_data(sessions[0].session_id, f"account_{i}")
        assert data["index"].field_value == i, f"Account {i} got wrong form data value"
