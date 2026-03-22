"""
Session & Tenant Isolation Logic — GrantSession management with zero data bleed.

Each account gets isolated grant workspaces (GrantSession). Session data is
scoped per-tenant. No data bleeds between accounts.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.billing.grants.models import (
    ApplicationStatus,
    GrantApplication,
    GrantSession,
    SavedFormData,
    SessionCredential,
    SessionRole,
)

logger = logging.getLogger(__name__)


class TenantAccessError(Exception):
    """Raised when a user attempts to access another tenant's session."""


class SessionManager:
    """
    In-memory session store for grant workspaces.

    Production deployments should replace the in-memory store with a
    database-backed store encrypted with GRANT_SESSION_ENCRYPTION_KEY.
    """

    def __init__(self) -> None:
        # account_id -> list of sessions
        self._sessions: Dict[str, Dict[str, GrantSession]] = {}
        # session_id -> list of credentials
        self._credentials: Dict[str, List[SessionCredential]] = {}
        # session_id -> SavedFormData (keyed by field_key)
        self._form_data: Dict[str, Dict[str, SavedFormData]] = {}
        # session_id -> list of GrantApplications
        self._applications: Dict[str, List[GrantApplication]] = {}

    # -----------------------------------------------------------------------
    # Session CRUD
    # -----------------------------------------------------------------------

    def create_session(
        self,
        account_id: str,
        name: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GrantSession:
        """Create a new grant workspace for an account."""
        max_sessions = int(os.environ.get("GRANT_MAX_SESSIONS_PER_ACCOUNT", "10"))
        existing = self._sessions.get(account_id, {})
        active_count = sum(1 for s in existing.values() if s.is_active)
        if active_count >= max_sessions:
            raise ValueError(
                f"Account {account_id!r} has reached the maximum of "
                f"{max_sessions} active grant sessions."
            )

        session = GrantSession(
            account_id=account_id,
            name=name,
            description=description,
            metadata=metadata or {},
        )

        if account_id not in self._sessions:
            self._sessions[account_id] = {}
        self._sessions[account_id][session.session_id] = session

        # Grant owner credential to creating user
        owner_cred = SessionCredential(
            session_id=session.session_id,
            user_id=account_id,
            role=SessionRole.OWNER,
            granted_by=account_id,
        )
        self._credentials[session.session_id] = [owner_cred]
        self._form_data[session.session_id] = {}
        self._applications[session.session_id] = []

        logger.info("Created grant session %s for account %s", session.session_id, account_id)
        return session

    def get_session(self, session_id: str, requesting_account_id: str) -> GrantSession:
        """Retrieve a session, enforcing tenant isolation."""
        session = self._find_session(session_id)
        self._assert_access(session_id, requesting_account_id)
        return session

    def list_sessions(self, account_id: str) -> List[GrantSession]:
        """List all sessions for an account."""
        return list(self._sessions.get(account_id, {}).values())

    def delete_session(self, session_id: str, requesting_account_id: str) -> None:
        """Soft-delete a session and all its associated data."""
        session = self._find_session(session_id)
        self._assert_owner(session_id, requesting_account_id)

        session.is_active = False
        session.updated_at = datetime.utcnow()
        # Clear all associated data
        self._form_data[session_id] = {}
        self._applications[session_id] = []
        logger.info("Deleted grant session %s", session_id)

    # -----------------------------------------------------------------------
    # Credential management
    # -----------------------------------------------------------------------

    def assign_credential(
        self,
        session_id: str,
        user_id: str,
        role: SessionRole,
        granted_by: str,
    ) -> SessionCredential:
        """Assign access to a session for a user."""
        self._find_session(session_id)
        self._assert_owner(session_id, granted_by)

        # Revoke existing credential for this user if any
        self._credentials[session_id] = [
            c for c in self._credentials.get(session_id, [])
            if c.user_id != user_id
        ]

        cred = SessionCredential(
            session_id=session_id,
            user_id=user_id,
            role=role,
            granted_by=granted_by,
        )
        self._credentials[session_id].append(cred)
        return cred

    def revoke_credential(
        self,
        session_id: str,
        user_id: str,
        revoked_by: str,
    ) -> None:
        """Revoke a user's access to a session."""
        self._find_session(session_id)
        self._assert_owner(session_id, revoked_by)

        before = len(self._credentials.get(session_id, []))
        self._credentials[session_id] = [
            c for c in self._credentials.get(session_id, [])
            if c.user_id != user_id
        ]
        after = len(self._credentials.get(session_id, []))
        if before == after:
            raise KeyError(f"No credential found for user {user_id!r} on session {session_id!r}")

    def list_credentials(self, session_id: str, requesting_account_id: str) -> List[SessionCredential]:
        """List all credentials for a session."""
        self._find_session(session_id)
        self._assert_access(session_id, requesting_account_id)
        return list(self._credentials.get(session_id, []))

    # -----------------------------------------------------------------------
    # Saved Form Data (browser-like auto-fill, scoped to session)
    # -----------------------------------------------------------------------

    def get_form_data(self, session_id: str, requesting_account_id: str) -> Dict[str, SavedFormData]:
        """Get all saved form data for a session."""
        self._find_session(session_id)
        self._assert_access(session_id, requesting_account_id)
        return dict(self._form_data.get(session_id, {}))

    def update_form_data(
        self,
        session_id: str,
        field_key: str,
        field_value: Any,
        requesting_account_id: str,
        source: str = "user_input",
        confidence: float = 1.0,
    ) -> SavedFormData:
        """Update a single form data field for a session."""
        self._find_session(session_id)
        self._assert_write_access(session_id, requesting_account_id)

        entry = SavedFormData(
            session_id=session_id,
            field_key=field_key,
            field_value=field_value,
            source=source,
            confidence=confidence,
        )
        if session_id not in self._form_data:
            self._form_data[session_id] = {}
        self._form_data[session_id][field_key] = entry
        return entry

    def bulk_update_form_data(
        self,
        session_id: str,
        data: Dict[str, Any],
        requesting_account_id: str,
        source: str = "user_input",
    ) -> Dict[str, SavedFormData]:
        """Update multiple form data fields at once."""
        result = {}
        for key, value in data.items():
            result[key] = self.update_form_data(
                session_id, key, value, requesting_account_id, source=source
            )
        return result

    # -----------------------------------------------------------------------
    # Application management
    # -----------------------------------------------------------------------

    def create_application(
        self,
        session_id: str,
        grant_id: str,
        requesting_account_id: str,
    ) -> GrantApplication:
        """Start a new grant application within a session."""
        self._find_session(session_id)
        self._assert_write_access(session_id, requesting_account_id)

        app = GrantApplication(
            session_id=session_id,
            grant_id=grant_id,
        )
        if session_id not in self._applications:
            self._applications[session_id] = []
        self._applications[session_id].append(app)
        return app

    def list_applications(
        self, session_id: str, requesting_account_id: str
    ) -> List[GrantApplication]:
        """List all applications in a session."""
        self._find_session(session_id)
        self._assert_access(session_id, requesting_account_id)
        return list(self._applications.get(session_id, []))

    def get_application(
        self,
        session_id: str,
        application_id: str,
        requesting_account_id: str,
    ) -> GrantApplication:
        """Get a specific application."""
        self._find_session(session_id)
        self._assert_access(session_id, requesting_account_id)
        for app in self._applications.get(session_id, []):
            if app.application_id == application_id:
                return app
        raise KeyError(f"Application {application_id!r} not found in session {session_id!r}")

    def update_application(
        self,
        session_id: str,
        application_id: str,
        updates: Dict[str, Any],
        requesting_account_id: str,
    ) -> GrantApplication:
        """Update an application."""
        app = self.get_application(session_id, application_id, requesting_account_id)
        self._assert_write_access(session_id, requesting_account_id)

        for key, value in updates.items():
            if hasattr(app, key):
                setattr(app, key, value)
        app.updated_at = datetime.utcnow()
        return app

    def delete_application(
        self,
        session_id: str,
        application_id: str,
        requesting_account_id: str,
    ) -> None:
        """Delete an application from a session."""
        self._find_session(session_id)
        self._assert_write_access(session_id, requesting_account_id)
        apps = self._applications.get(session_id, [])
        before = len(apps)
        self._applications[session_id] = [
            a for a in apps if a.application_id != application_id
        ]
        if len(self._applications[session_id]) == before:
            raise KeyError(f"Application {application_id!r} not found in session {session_id!r}")

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _find_session(self, session_id: str) -> GrantSession:
        for account_sessions in self._sessions.values():
            if session_id in account_sessions:
                return account_sessions[session_id]
        raise KeyError(f"Grant session {session_id!r} not found")

    def _assert_access(self, session_id: str, user_id: str) -> None:
        """Assert that a user has any access to a session."""
        creds = self._credentials.get(session_id, [])
        if any(c.user_id == user_id and c.is_active for c in creds):
            return
        # Also allow if user is the session owner (account_id matches)
        session = self._find_session(session_id)
        if session.account_id == user_id:
            return
        raise TenantAccessError(
            f"User {user_id!r} does not have access to session {session_id!r}"
        )

    def _assert_write_access(self, session_id: str, user_id: str) -> None:
        """Assert that a user has write access (editor, admin, or owner)."""
        creds = self._credentials.get(session_id, [])
        write_roles = {SessionRole.OWNER, SessionRole.ADMIN, SessionRole.EDITOR}
        if any(c.user_id == user_id and c.is_active and c.role in write_roles for c in creds):
            return
        session = self._find_session(session_id)
        if session.account_id == user_id:
            return
        raise TenantAccessError(
            f"User {user_id!r} does not have write access to session {session_id!r}"
        )

    def _assert_owner(self, session_id: str, user_id: str) -> None:
        """Assert that a user is the owner or admin of a session."""
        creds = self._credentials.get(session_id, [])
        owner_roles = {SessionRole.OWNER, SessionRole.ADMIN}
        if any(c.user_id == user_id and c.is_active and c.role in owner_roles for c in creds):
            return
        session = self._find_session(session_id)
        if session.account_id == user_id:
            return
        raise TenantAccessError(
            f"User {user_id!r} is not an owner/admin of session {session_id!r}"
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
