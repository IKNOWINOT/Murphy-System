"""
Authorization Enhancer for Murphy System.

Design Label: SAF-005 — Per-Request Ownership Verification
Owner: Platform Engineering / Security Team

Implements per-request ownership verification:
  - Bind each API request to an authenticated principal and validate
    ownership of the target resource before execution
  - Propagate verified identity through the full request lifecycle
  - Log ownership verification outcomes for audit trail

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Fail-closed: missing session or unknown resource → request denied
  - Bounded: configurable max audit entries

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_AUDIT_ENTRIES = 10_000


class OwnershipVerificationResult(str, Enum):
    """Outcome of an ownership verification check."""
    ALLOWED = "allowed"
    DENIED_NOT_OWNER = "denied_not_owner"
    DENIED_NO_SESSION = "denied_no_session"
    DENIED_EXPIRED_SESSION = "denied_expired_session"
    DENIED_INVALID_PRINCIPAL = "denied_invalid_principal"


@dataclass
class AuthorizationRequest:
    """Incoming request requiring ownership verification."""
    request_id: str
    principal_id: str
    resource_id: str
    resource_type: str
    action: str
    session_id: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "principal_id": self.principal_id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "action": self.action,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AuthorizationDecision:
    """Recorded decision for an ownership verification check."""
    request_id: str
    result: OwnershipVerificationResult
    principal_id: str
    resource_id: str
    reason: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "result": self.result.value,
            "principal_id": self.principal_id,
            "resource_id": self.resource_id,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SessionContext:
    """Verified identity propagated through the request lifecycle."""
    session_id: str
    principal_id: str
    tenant_id: str
    roles: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1)
    )
    is_active: bool = True

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_active": self.is_active,
        }


class AuthorizationEnhancer:
    """Enhanced authorization with per-request ownership verification.

    Design Label: SAF-005

    Usage::

        enhancer = AuthorizationEnhancer()
        session = enhancer.create_session("principal-1", "tenant-1", ["admin"])
        enhancer.register_resource_owner("res-1", "document", "principal-1", "tenant-1")
        decision = enhancer.verify_request(request)
    """

    def __init__(self, max_audit_entries: int = _MAX_AUDIT_ENTRIES) -> None:
        self._lock = threading.Lock()
        self._max_audit_entries = max_audit_entries
        self._sessions: Dict[str, SessionContext] = {}
        self._resource_owners: Dict[str, Dict[str, str]] = {}
        self._audit_trail: List[AuthorizationDecision] = []
        logger.info("AuthorizationEnhancer initialised (max_audit=%d)", max_audit_entries)

    def create_session(
        self,
        principal_id: str,
        tenant_id: str,
        roles: List[str],
        ttl_seconds: int = 3600,
    ) -> SessionContext:
        """Create a new session context for an authenticated principal."""
        now = datetime.now(timezone.utc)
        session = SessionContext(
            session_id=str(uuid.uuid4()),
            principal_id=principal_id,
            tenant_id=tenant_id,
            roles=list(roles),
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        logger.info("Session created session_id=%s principal=%s", session.session_id, principal_id)
        return session

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate an existing session. Returns True if found."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                logger.warning("Invalidation failed: session_id=%s not found", session_id)
                return False
            session.is_active = False
        logger.info("Session invalidated session_id=%s", session_id)
        return True

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session context by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def register_resource_owner(
        self, resource_id: str, resource_type: str, owner_id: str, tenant_id: str,
    ) -> None:
        """Register ownership of a resource."""
        with self._lock:
            self._resource_owners[resource_id] = {
                "resource_type": resource_type,
                "owner_id": owner_id,
                "tenant_id": tenant_id,
            }
        logger.info("Resource owner registered resource=%s owner=%s", resource_id, owner_id)

    def get_resource_owner(self, resource_id: str) -> Optional[str]:
        """Get the owner of a resource."""
        with self._lock:
            entry = self._resource_owners.get(resource_id)
            return entry["owner_id"] if entry else None

    def verify_request(self, request: AuthorizationRequest) -> AuthorizationDecision:
        """Verify that the principal owns or has access to the target resource.

        Checks executed in order: session existence → expiry → principal
        match → resource ownership.  Fail-closed on any check failure.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            session = self._sessions.get(request.session_id)

            if session is None or not session.is_active:
                return self._deny(request, OwnershipVerificationResult.DENIED_NO_SESSION,
                                  "No active session found for session_id", now)

            if session.is_expired():
                return self._deny(request, OwnershipVerificationResult.DENIED_EXPIRED_SESSION,
                                  "Session has expired", now)

            if session.principal_id != request.principal_id:
                return self._deny(request, OwnershipVerificationResult.DENIED_INVALID_PRINCIPAL,
                                  "Session principal does not match request principal", now)

            owner_entry = self._resource_owners.get(request.resource_id)
            if owner_entry is None or owner_entry["owner_id"] != request.principal_id:
                return self._deny(request, OwnershipVerificationResult.DENIED_NOT_OWNER,
                                  "Principal is not the owner of the target resource", now)

            decision = AuthorizationDecision(
                request_id=request.request_id,
                result=OwnershipVerificationResult.ALLOWED,
                principal_id=request.principal_id,
                resource_id=request.resource_id,
                reason="Ownership verified",
                timestamp=now,
            )
            self._record_decision(decision)
            return decision

    def get_audit_trail(
        self,
        principal_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuthorizationDecision]:
        """Get audit trail entries with optional filters (newest first)."""
        with self._lock:
            entries = self._audit_trail
            if principal_id is not None:
                entries = [e for e in entries if e.principal_id == principal_id]
            if resource_id is not None:
                entries = [e for e in entries if e.resource_id == resource_id]
            return list(reversed(entries[-limit:]))

    def get_stats(self) -> Dict[str, Any]:
        """Get authorization statistics."""
        with self._lock:
            result_counts: Dict[str, int] = {}
            for entry in self._audit_trail:
                key = entry.result.value
                result_counts[key] = result_counts.get(key, 0) + 1
            return {
                "total_sessions": len(self._sessions),
                "active_sessions": sum(
                    1 for s in self._sessions.values() if s.is_active and not s.is_expired()
                ),
                "registered_resources": len(self._resource_owners),
                "audit_entries": len(self._audit_trail),
                "result_counts": result_counts,
            }

    # -- internal helpers ------------------------------------------------

    def _deny(
        self,
        request: AuthorizationRequest,
        result: OwnershipVerificationResult,
        reason: str,
        now: datetime,
    ) -> AuthorizationDecision:
        """Build a denial decision, record it, and return it.

        Must be called while holding ``self._lock``.
        """
        decision = AuthorizationDecision(
            request_id=request.request_id,
            result=result,
            principal_id=request.principal_id,
            resource_id=request.resource_id,
            reason=reason,
            timestamp=now,
        )
        self._record_decision(decision)
        return decision

    def _record_decision(self, decision: AuthorizationDecision) -> None:
        """Append a decision to the bounded audit trail.

        Must be called while holding ``self._lock``.
        """
        if len(self._audit_trail) >= self._max_audit_entries:
            self._audit_trail = self._audit_trail[-(self._max_audit_entries // 2):]
        self._audit_trail.append(decision)
        logger.info(
            "Authorization decision request=%s result=%s principal=%s resource=%s",
            decision.request_id, decision.result.value,
            decision.principal_id, decision.resource_id,
        )
