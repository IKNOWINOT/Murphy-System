"""
Test: Saved Form Data Scoped to Session

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.sessions import SessionManager, TenantAccessError


@pytest.fixture
def mgr():
    return SessionManager()


def test_form_data_scoped_to_session(mgr):
    """Form data set in one session does not appear in another session."""
    s1 = mgr.create_session("account_1", "Session 1")
    s2 = mgr.create_session("account_1", "Session 2")

    mgr.update_form_data(s1.session_id, "company_name", "Inoni LLC", "account_1")

    data_s2 = mgr.get_form_data(s2.session_id, "account_1")
    assert "company_name" not in data_s2, "company_name from session 1 leaked into session 2"


def test_form_data_survives_across_requests(mgr):
    """Form data persists within a session (like browser auto-fill)."""
    s = mgr.create_session("account_1", "My Session")
    mgr.update_form_data(s.session_id, "state", "OR", "account_1")
    mgr.update_form_data(s.session_id, "project_type", "bas_bms", "account_1")

    data = mgr.get_form_data(s.session_id, "account_1")
    assert data["state"].field_value == "OR"
    assert data["project_type"].field_value == "bas_bms"


def test_bulk_update_form_data(mgr):
    """Bulk update stores multiple fields at once."""
    s = mgr.create_session("account_1", "Bulk Test")
    fields = {
        "company_name": "Inoni LLC",
        "ein": "12-3456789",
        "state": "OR",
        "project_type": "ai_platform",
    }
    result = mgr.bulk_update_form_data(s.session_id, fields, "account_1")
    assert len(result) == 4

    data = mgr.get_form_data(s.session_id, "account_1")
    for key in fields:
        assert key in data
        assert data[key].field_value == fields[key]


def test_form_data_update_overwrites_previous(mgr):
    """Updating an existing key replaces the previous value."""
    s = mgr.create_session("account_1", "Overwrite Test")
    mgr.update_form_data(s.session_id, "project_cost", 50_000, "account_1")
    mgr.update_form_data(s.session_id, "project_cost", 75_000, "account_1")

    data = mgr.get_form_data(s.session_id, "account_1")
    assert data["project_cost"].field_value == 75_000


def test_form_data_source_tracked(mgr):
    """Source of form data is recorded correctly."""
    s = mgr.create_session("account_1", "Source Test")
    mgr.update_form_data(s.session_id, "company_name", "Inoni LLC", "account_1", source="user_input")
    mgr.update_form_data(s.session_id, "naics", "541715", "account_1", source="auto_filled")

    data = mgr.get_form_data(s.session_id, "account_1")
    assert data["company_name"].source == "user_input"
    assert data["naics"].source == "auto_filled"


def test_form_data_confidence_stored(mgr):
    """Confidence score is stored with form data."""
    s = mgr.create_session("account_1", "Confidence Test")
    mgr.update_form_data(s.session_id, "naics", "541715", "account_1", confidence=0.85)

    data = mgr.get_form_data(s.session_id, "account_1")
    assert abs(data["naics"].confidence - 0.85) < 1e-6


def test_cross_tenant_form_data_not_accessible(mgr):
    """Account B cannot read form data from Account A's session."""
    s_a = mgr.create_session("account_a", "A's Session")
    mgr.update_form_data(s_a.session_id, "secret", "top_secret", "account_a")

    with pytest.raises(TenantAccessError):
        mgr.get_form_data(s_a.session_id, "account_b")


def test_deleted_session_form_data_cleared(mgr):
    """Deleting a session clears all form data."""
    s = mgr.create_session("account_1", "To Delete")
    mgr.update_form_data(s.session_id, "key1", "value1", "account_1")
    mgr.update_form_data(s.session_id, "key2", "value2", "account_1")

    mgr.delete_session(s.session_id, "account_1")

    data = mgr.get_form_data(s.session_id, "account_1")
    assert len(data) == 0, "Form data should be cleared after session deletion"
