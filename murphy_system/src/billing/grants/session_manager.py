"""
Grant Session Manager — Tenant-isolated in-memory session and application store.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class GrantSession:
    session_id: str
    tenant_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    applications: Dict[str, Any] = field(default_factory=dict)
    saved_form_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GrantApplication:
    application_id: str
    session_id: str
    program_id: str
    form_id: str
    status: str
    filled_fields: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class GrantSessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, GrantSession] = {}
        self._applications: Dict[str, GrantApplication] = {}

    def create_session(self, tenant_id: str, name: str, metadata: Dict[str, Any]) -> GrantSession:
        session_id = str(uuid.uuid4())
        now = _now()
        session = GrantSession(
            session_id=session_id,
            tenant_id=tenant_id,
            name=name,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str, tenant_id: str) -> Optional[GrantSession]:
        session = self._sessions.get(session_id)
        if session is None or session.tenant_id != tenant_id:
            return None
        return session

    def list_sessions(self, tenant_id: str) -> List[GrantSession]:
        return [s for s in self._sessions.values() if s.tenant_id == tenant_id]

    def create_application(
        self,
        session_id: str,
        tenant_id: str,
        program_id: str,
        form_id: str,
    ) -> GrantApplication:
        session = self.get_session(session_id, tenant_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found for tenant {tenant_id}")
        application_id = str(uuid.uuid4())
        now = _now()
        app = GrantApplication(
            application_id=application_id,
            session_id=session_id,
            program_id=program_id,
            form_id=form_id,
            status="draft",
            filled_fields={},
            created_at=now,
            updated_at=now,
        )
        self._applications[application_id] = app
        session.applications[application_id] = True
        session.updated_at = now
        return app

    def get_application(
        self,
        application_id: str,
        session_id: str,
        tenant_id: str,
    ) -> Optional[GrantApplication]:
        app = self._applications.get(application_id)
        if app is None or app.session_id != session_id:
            return None
        session = self.get_session(session_id, tenant_id)
        if session is None:
            return None
        return app

    def list_applications(self, session_id: str, tenant_id: str) -> List[GrantApplication]:
        session = self.get_session(session_id, tenant_id)
        if session is None:
            return []
        return [
            app for app in self._applications.values()
            if app.session_id == session_id
        ]

    def update_application(
        self,
        application_id: str,
        session_id: str,
        tenant_id: str,
        updates: Dict[str, Any],
    ) -> Optional[GrantApplication]:
        app = self.get_application(application_id, session_id, tenant_id)
        if app is None:
            return None
        allowed_fields = {"status", "filled_fields"}
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(app, key, value)
        app.updated_at = _now()
        return app

    def save_form_data(
        self,
        session_id: str,
        tenant_id: str,
        field_data: Dict[str, Any],
    ) -> bool:
        session = self.get_session(session_id, tenant_id)
        if session is None:
            return False
        session.saved_form_data.update(field_data)
        session.updated_at = _now()
        return True

    def get_saved_form_data(self, session_id: str, tenant_id: str) -> Dict[str, Any]:
        session = self.get_session(session_id, tenant_id)
        if session is None:
            return {}
        return dict(session.saved_form_data)
