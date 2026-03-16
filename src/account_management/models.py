"""
Account Management — Data Models
==================================

Defines all data classes for the account management subsystem:
- OAuthProvider enum (Microsoft, Google, Meta, and extensible custom)
- AccountRecord with full audit trail
- OAuthToken with expiry and refresh lifecycle
- StoredCredential with API-key-style encryption metadata
- ConsentRecord for credential-sharing consent flow
- AccountEvent for the account audit log

Design Label: ACCT-001
Owner: Platform Engineering
"""

import enum
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OAuthProvider(str, enum.Enum):
    """Supported OAuth identity providers."""
    MICROSOFT = "microsoft"
    GOOGLE = "google"
    META = "meta"
    GITHUB = "github"
    LINKEDIN = "linkedin"
    APPLE = "apple"
    CUSTOM = "custom"


class AccountStatus(str, enum.Enum):
    """Lifecycle status of an account record."""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class ConsentStatus(str, enum.Enum):
    """Status of a credential-sharing consent request."""
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"


class AccountEventType(str, enum.Enum):
    """Types of events in the account audit log."""
    CREATED = "account_created"
    OAUTH_LINKED = "oauth_linked"
    OAUTH_UNLINKED = "oauth_unlinked"
    PASSWORD_SET = "password_set"
    PASSWORD_CHANGED = "password_changed"
    CREDENTIAL_STORED = "credential_stored"
    CREDENTIAL_ROTATED = "credential_rotated"
    CREDENTIAL_REMOVED = "credential_removed"
    CONSENT_REQUESTED = "consent_requested"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_DENIED = "consent_denied"
    CONSENT_REVOKED = "consent_revoked"
    STATUS_CHANGED = "status_changed"
    MISSING_INTEGRATION_TICKET = "missing_integration_ticket"
    LOGIN = "login"
    LOGOUT = "logout"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class OAuthToken:
    """OAuth token with expiry and refresh lifecycle."""
    provider: OAuthProvider
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    raw_profile: Dict[str, Any] = field(default_factory=dict)
    issued_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.expires_at is None:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) >= exp
        except (ValueError, TypeError):
            return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.value,
            "token_type": self.token_type,
            "scopes": self.scopes,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "is_expired": self.is_expired(),
            "has_refresh_token": self.refresh_token is not None,
        }


@dataclass
class StoredCredential:
    """A credential stored with API-key-style treatment.

    The ``encrypted_value`` field holds the credential after encryption.
    The plaintext is never persisted.  ``key_hash`` is a SHA-256 prefix
    used for verification without decryption.
    """
    credential_id: str = field(
        default_factory=lambda: f"cred-{uuid.uuid4().hex[:12]}"
    )
    account_id: str = ""
    service_name: str = ""
    credential_type: str = "password"  # password | api_key | oauth_token | other
    encrypted_value: str = ""
    key_hash: str = ""  # SHA-256 prefix for verification
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_rotated_at: Optional[str] = None
    rotation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Safe serialization — never includes the encrypted value."""
        return {
            "credential_id": self.credential_id,
            "account_id": self.account_id,
            "service_name": self.service_name,
            "credential_type": self.credential_type,
            "key_hash": self.key_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_rotated_at": self.last_rotated_at,
            "rotation_count": self.rotation_count,
        }


@dataclass
class ConsentRecord:
    """Record of a credential-sharing consent request."""
    consent_id: str = field(
        default_factory=lambda: f"consent-{uuid.uuid4().hex[:8]}"
    )
    account_id: str = ""
    description: str = ""
    services_requested: List[str] = field(default_factory=list)
    services_granted: List[str] = field(default_factory=list)
    services_denied: List[str] = field(default_factory=list)
    status: ConsentStatus = ConsentStatus.PENDING
    requested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    responded_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consent_id": self.consent_id,
            "account_id": self.account_id,
            "description": self.description,
            "services_requested": self.services_requested,
            "services_granted": self.services_granted,
            "services_denied": self.services_denied,
            "status": self.status.value,
            "requested_at": self.requested_at,
            "responded_at": self.responded_at,
        }


@dataclass
class AccountEvent:
    """Immutable entry in the account audit log."""
    event_id: str = field(
        default_factory=lambda: f"evt-{uuid.uuid4().hex[:10]}"
    )
    account_id: str = ""
    event_type: str = ""
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "account_id": self.account_id,
            "event_type": self.event_type,
            "detail": self.detail,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class AccountRecord:
    """Primary account record with linked OAuth providers and audit trail."""
    account_id: str = field(
        default_factory=lambda: f"acct-{uuid.uuid4().hex[:10]}"
    )
    display_name: str = ""
    email: Optional[str] = None
    status: AccountStatus = AccountStatus.PENDING
    oauth_providers: Dict[str, OAuthToken] = field(default_factory=dict)
    stored_credentials: Dict[str, StoredCredential] = field(default_factory=dict)
    consent_records: List[ConsentRecord] = field(default_factory=list)
    events: List[AccountEvent] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def _emit(self, event_type: str, detail: str = "",
              meta: Optional[Dict[str, Any]] = None) -> AccountEvent:
        """Append an event to the audit log and return it."""
        evt = AccountEvent(
            account_id=self.account_id,
            event_type=event_type,
            detail=detail,
            metadata=meta or {},
        )
        self.events.append(evt)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return evt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "display_name": self.display_name,
            "email": self.email,
            "status": self.status.value,
            "oauth_providers": {
                k: v.to_dict() for k, v in self.oauth_providers.items()
            },
            "stored_credentials": {
                k: v.to_dict() for k, v in self.stored_credentials.items()
            },
            "consent_records": [c.to_dict() for c in self.consent_records],
            "event_count": len(self.events),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
