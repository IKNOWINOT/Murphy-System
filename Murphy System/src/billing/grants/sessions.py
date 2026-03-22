"""Session management with strict tenant isolation for grants module."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.billing.grants.models import GrantSession, GrantTrack

# In-memory store: session_id -> GrantSession
_SESSIONS: Dict[str, GrantSession] = {}


def create_session(tenant_id: str, track: GrantTrack) -> GrantSession:
    """Create an isolated session for a tenant.

    Args:
        tenant_id: Unique identifier for the tenant.
        track: Whether this is Track A (Murphy) or Track B (customer).

    Returns:
        Newly created GrantSession.
    """
    now = datetime.now(timezone.utc)
    session = GrantSession(
        session_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        track=track,
        created_at=now,
        updated_at=now,
    )
    _SESSIONS[session.session_id] = session
    return session


def get_session(session_id: str, tenant_id: Optional[str] = None) -> Optional[GrantSession]:
    """Retrieve session, optionally validating tenant ownership.

    Args:
        session_id: ID of the session to retrieve.
        tenant_id: If provided, session is returned only if it belongs to this tenant.

    Returns:
        GrantSession if found (and tenant matches if supplied), else None.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        return None
    if tenant_id is not None and session.tenant_id != tenant_id:
        return None
    return session


def update_session(
    session_id: str,
    data: Dict[str, Any],
    tenant_id: Optional[str] = None,
) -> Optional[GrantSession]:
    """Update session profile_data; raises ValueError if tenant_id mismatch.

    Args:
        session_id: ID of the session to update.
        data: Mapping to merge into session.profile_data.
        tenant_id: If provided, raises ValueError when session belongs to a different tenant.

    Returns:
        Updated GrantSession or None if session does not exist.

    Raises:
        ValueError: If tenant_id is provided and does not match session.tenant_id.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        return None
    if tenant_id is not None and session.tenant_id != tenant_id:
        raise ValueError(
            f"Tenant '{tenant_id}' does not own session '{session_id}'"
        )
    session.profile_data.update(data)
    session.updated_at = datetime.now(timezone.utc)
    return session


def destroy_session(session_id: str, tenant_id: Optional[str] = None) -> bool:
    """Destroy session completely.

    Args:
        session_id: ID of the session to destroy.
        tenant_id: If provided, raises ValueError when session belongs to a different tenant.

    Returns:
        True if session existed and was destroyed, False otherwise.

    Raises:
        ValueError: If tenant_id is provided and does not match session.tenant_id.
    """
    session = _SESSIONS.get(session_id)
    if session is None:
        return False
    if tenant_id is not None and session.tenant_id != tenant_id:
        raise ValueError(
            f"Tenant '{tenant_id}' does not own session '{session_id}'"
        )
    del _SESSIONS[session_id]
    return True


def list_sessions(tenant_id: str) -> List[GrantSession]:
    """List all sessions belonging to a tenant.

    Args:
        tenant_id: Tenant whose sessions to list.

    Returns:
        List of GrantSession objects owned by the tenant.
    """
    return [s for s in _SESSIONS.values() if s.tenant_id == tenant_id]
