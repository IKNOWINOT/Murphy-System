"""
Test: Session Credential Assignment & Revocation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import pytest

from src.billing.grants.sessions import SessionManager, TenantAccessError
from src.billing.grants.models import SessionRole


@pytest.fixture
def mgr():
    return SessionManager()


@pytest.fixture
def session_setup(mgr):
    session = mgr.create_session("owner_account", "Test Session")
    return mgr, session


def test_owner_can_assign_credential(session_setup):
    """Session owner can grant access to another user."""
    mgr, session = session_setup
    cred = mgr.assign_credential(
        session.session_id, "editor_user", SessionRole.EDITOR, "owner_account"
    )
    assert cred.user_id == "editor_user"
    assert cred.role == SessionRole.EDITOR
    assert cred.granted_by == "owner_account"


def test_assigned_user_can_access_session(session_setup):
    """User granted access can read the session."""
    mgr, session = session_setup
    mgr.assign_credential(session.session_id, "viewer_user", SessionRole.VIEWER, "owner_account")
    retrieved = mgr.get_session(session.session_id, "viewer_user")
    assert retrieved.session_id == session.session_id


def test_viewer_cannot_write_form_data(session_setup):
    """VIEWER role cannot update form data (write access denied)."""
    mgr, session = session_setup
    mgr.assign_credential(session.session_id, "viewer_user", SessionRole.VIEWER, "owner_account")
    with pytest.raises(TenantAccessError):
        mgr.update_form_data(session.session_id, "key", "value", "viewer_user")


def test_editor_can_write_form_data(session_setup):
    """EDITOR role can update form data."""
    mgr, session = session_setup
    mgr.assign_credential(session.session_id, "editor_user", SessionRole.EDITOR, "owner_account")
    entry = mgr.update_form_data(session.session_id, "company", "ACME", "editor_user")
    assert entry.field_value == "ACME"


def test_owner_can_revoke_access(session_setup):
    """Session owner can revoke a user's access."""
    mgr, session = session_setup
    mgr.assign_credential(session.session_id, "temp_user", SessionRole.VIEWER, "owner_account")
    mgr.revoke_credential(session.session_id, "temp_user", "owner_account")

    with pytest.raises(TenantAccessError):
        mgr.get_session(session.session_id, "temp_user")


def test_non_owner_cannot_assign_credential(session_setup):
    """Non-owner cannot assign access to a session."""
    mgr, session = session_setup
    mgr.assign_credential(session.session_id, "editor_user", SessionRole.EDITOR, "owner_account")

    # editor cannot grant access to others
    with pytest.raises(TenantAccessError):
        mgr.assign_credential(session.session_id, "new_user", SessionRole.VIEWER, "editor_user")


def test_revoke_nonexistent_credential_raises(session_setup):
    """Revoking a credential that doesn't exist raises KeyError."""
    mgr, session = session_setup
    with pytest.raises(KeyError):
        mgr.revoke_credential(session.session_id, "nonexistent_user", "owner_account")


def test_reassigning_role_replaces_existing(session_setup):
    """Re-assigning a role to the same user replaces the previous role."""
    mgr, session = session_setup
    mgr.assign_credential(session.session_id, "user1", SessionRole.VIEWER, "owner_account")
    mgr.assign_credential(session.session_id, "user1", SessionRole.ADMIN, "owner_account")

    creds = mgr.list_credentials(session.session_id, "owner_account")
    user1_creds = [c for c in creds if c.user_id == "user1"]
    assert len(user1_creds) == 1
    assert user1_creds[0].role == SessionRole.ADMIN


def test_list_credentials_shows_all_users(session_setup):
    """list_credentials returns all active credentials for a session."""
    mgr, session = session_setup
    mgr.assign_credential(session.session_id, "user_a", SessionRole.VIEWER, "owner_account")
    mgr.assign_credential(session.session_id, "user_b", SessionRole.EDITOR, "owner_account")

    creds = mgr.list_credentials(session.session_id, "owner_account")
    user_ids = {c.user_id for c in creds}
    assert "user_a" in user_ids
    assert "user_b" in user_ids
    # Owner credential should also be present
    assert "owner_account" in user_ids
