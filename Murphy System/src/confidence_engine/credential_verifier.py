"""
Credential Verification System
Manages credential validation, expiry tracking, and refresh mechanisms.
"""

import base64
import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)
import hashlib
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CredentialType(str, Enum):
    """Types of credentials."""
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    JWT_TOKEN = "jwt_token"
    BASIC_AUTH = "basic_auth"
    SSH_KEY = "ssh_key"
    DATABASE_CREDENTIALS = "database_credentials"
    SERVICE_ACCOUNT = "service_account"


class CredentialStatus(str, Enum):
    """Status of a credential."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_REFRESH = "pending_refresh"
    INVALID = "invalid"


class Credential(BaseModel):
    """Represents a credential with metadata."""
    id: str
    credential_type: CredentialType
    service_name: str
    credential_value: str  # Encrypted/hashed in production
    status: CredentialStatus = CredentialStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    last_verified: Optional[datetime] = None
    verification_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if credential is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def needs_refresh(self, threshold_hours: int = 24) -> bool:
        """Check if credential needs refresh."""
        if not self.expires_at:
            return False
        threshold = datetime.now(timezone.utc) + timedelta(hours=threshold_hours)
        return threshold > self.expires_at

    def get_hash(self) -> str:
        """Get hash of credential for caching."""
        data = f"{self.service_name}:{self.credential_type}:{self.credential_value}"
        return hashlib.sha256(data.encode()).hexdigest()


class CredentialVerificationResult(BaseModel):
    """Result of credential verification."""
    credential_id: str
    is_valid: bool
    status: CredentialStatus
    confidence: float = Field(ge=0.0, le=1.0)
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class CredentialStore:
    """
    Stores and manages credentials.
    In production, this would use encrypted storage (e.g., HashiCorp Vault, AWS Secrets Manager).
    """

    def __init__(self):
        self.credentials: Dict[str, Credential] = {}

    def add_credential(self, credential: Credential) -> str:
        """Add a credential to the store."""
        self.credentials[credential.id] = credential
        return credential.id

    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Retrieve a credential by ID."""
        return self.credentials.get(credential_id)

    def update_credential(self, credential_id: str, updates: Dict[str, Any]) -> bool:
        """Update credential fields."""
        credential = self.credentials.get(credential_id)
        if not credential:
            return False

        for key, value in updates.items():
            if hasattr(credential, key):
                setattr(credential, key, value)

        return True

    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential."""
        if credential_id in self.credentials:
            del self.credentials[credential_id]
            return True
        return False

    def list_credentials(
        self,
        service_name: Optional[str] = None,
        credential_type: Optional[CredentialType] = None,
        status: Optional[CredentialStatus] = None
    ) -> List[Credential]:
        """List credentials with optional filters."""
        credentials = list(self.credentials.values())

        if service_name:
            credentials = [c for c in credentials if c.service_name == service_name]

        if credential_type:
            credentials = [c for c in credentials if c.credential_type == credential_type]

        if status:
            credentials = [c for c in credentials if c.status == status]

        return credentials

    def get_expiring_credentials(self, hours: int = 24) -> List[Credential]:
        """Get credentials expiring within specified hours."""
        threshold = datetime.now(timezone.utc) + timedelta(hours=hours)
        return [
            c for c in self.credentials.values()
            if c.expires_at and c.expires_at < threshold
        ]


class CredentialVerifier:
    """
    Verifies credentials using various methods.
    Integrates with ExternalValidationService for actual verification.
    """

    def __init__(self, credential_store: CredentialStore):
        self.credential_store = credential_store
        self.verification_history: List[CredentialVerificationResult] = []

    async def verify_credential(
        self,
        credential_id: str,
        force_refresh: bool = False
    ) -> CredentialVerificationResult:
        """
        Verify a credential.

        Args:
            credential_id: ID of credential to verify
            force_refresh: Force verification even if recently verified

        Returns:
            CredentialVerificationResult
        """
        credential = self.credential_store.get_credential(credential_id)
        if not credential:
            return CredentialVerificationResult(
                credential_id=credential_id,
                is_valid=False,
                status=CredentialStatus.INVALID,
                confidence=0.0,
                error_message="Credential not found"
            )

        # Check if expired
        if credential.is_expired():
            result = CredentialVerificationResult(
                credential_id=credential_id,
                is_valid=False,
                status=CredentialStatus.EXPIRED,
                confidence=0.0,
                details={"expires_at": credential.expires_at.isoformat()}
            )
            self._update_credential_status(credential_id, CredentialStatus.EXPIRED)
            return result

        # Check if recently verified (unless force_refresh)
        if not force_refresh and credential.last_verified:
            time_since_verification = datetime.now(timezone.utc) - credential.last_verified
            if time_since_verification < timedelta(minutes=5):
                return CredentialVerificationResult(
                    credential_id=credential_id,
                    is_valid=True,
                    status=credential.status,
                    confidence=1.0,
                    details={"cached": True, "last_verified": credential.last_verified.isoformat()}
                )

        # Perform actual verification
        try:
            is_valid = await self._verify_credential_value(credential)

            result = CredentialVerificationResult(
                credential_id=credential_id,
                is_valid=is_valid,
                status=CredentialStatus.ACTIVE if is_valid else CredentialStatus.INVALID,
                confidence=1.0 if is_valid else 0.0,
                details={
                    "credential_type": credential.credential_type,
                    "service_name": credential.service_name
                }
            )

            # Update credential
            self.credential_store.update_credential(credential_id, {
                "last_verified": datetime.now(timezone.utc),
                "verification_count": credential.verification_count + 1,
                "status": result.status
            })

            self.verification_history.append(result)
            return result

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return CredentialVerificationResult(
                credential_id=credential_id,
                is_valid=False,
                status=CredentialStatus.INVALID,
                confidence=0.0,
                error_message=str(exc)
            )

    async def _verify_credential_value(self, credential: Credential) -> bool:
        """
        Verify the actual credential value.
        Override this method to implement service-specific verification.
        """
        # Simplified implementation; extend with real provider SDK
        # In production, this would make actual API calls to verify credentials

        if credential.credential_type == CredentialType.API_KEY:
            return await self._verify_api_key(credential)
        elif credential.credential_type == CredentialType.OAUTH_TOKEN:
            return await self._verify_oauth_token(credential)
        elif credential.credential_type == CredentialType.JWT_TOKEN:
            return await self._verify_jwt_token(credential)
        else:
            # Default verification
            return len(credential.credential_value) > 0

    async def _verify_api_key(self, credential: Credential) -> bool:
        """
        Verify API key.

        Format gate: key must be at least 20 characters.
        Network gate: attempts a lightweight validation call; on auth failure
        returns False; on network error treats the key as tentatively valid.
        """
        if len(credential.credential_value) < 20:
            return False
        # Attempt network validation if a provider endpoint is configured
        provider_url = credential.metadata.get('validation_url')
        if provider_url:
            try:
                req = urllib.request.Request(
                    provider_url,
                    headers={'Authorization': f'Bearer {credential.credential_value}'},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status < 400
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    logger.debug("API key auth rejected by provider: %s", exc)
                    return False
                # Other HTTP error — treat as network problem, tentatively valid
                logger.debug("Provider returned unexpected HTTP status: %s", exc)
                return True
            except Exception as exc:
                # Network error — unverified but not definitively invalid
                logger.debug("Network error during API key validation (unverified): %s", exc)
                return True
        return True

    async def _verify_oauth_token(self, credential: Credential) -> bool:
        """
        Verify OAuth / JWT token.

        Decodes the token without signature verification to check the expiry
        claim.  Returns False if the token is expired, True otherwise.
        """
        token = credential.credential_value
        parts = token.split('.')
        if len(parts) != 3:
            return False
        try:
            # Pad base64url payload segment and decode
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get('exp')
            if exp is not None:
                exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                if exp_dt < datetime.now(tz=timezone.utc):
                    logger.debug("OAuth token expired at %s", exp_dt)
                    return False
        except Exception as exc:
            logger.debug("Could not decode token payload: %s", exc)
            # Cannot parse — treat as structurally invalid
            return False
        return True

    async def _verify_jwt_token(self, credential: Credential) -> bool:
        """
        Verify JWT token structure and expiry.

        Checks that the token has three dot-separated base64url segments and
        that the exp claim (if present) is in the future.
        """
        try:
            parts = credential.credential_value.split('.')
            if len(parts) != 3:
                return False
            # Validate payload contains valid JSON with optional exp check
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp = payload.get('exp')
            if exp is not None:
                exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                if exp_dt < datetime.now(tz=timezone.utc):
                    logger.debug("JWT expired at %s", exp_dt)
                    return False
            return True
        except Exception as exc:
            logger.debug("JWT structure validation failed: %s", exc)
            return False

    def _update_credential_status(self, credential_id: str, status: CredentialStatus):
        """Update credential status."""
        self.credential_store.update_credential(credential_id, {"status": status})

    async def verify_multiple_credentials(
        self,
        credential_ids: List[str]
    ) -> List[CredentialVerificationResult]:
        """Verify multiple credentials in parallel."""
        import asyncio

        tasks = [self.verify_credential(cred_id) for cred_id in credential_ids]
        return await asyncio.gather(*tasks)

    def get_verification_history(
        self,
        credential_id: Optional[str] = None,
        limit: int = 100
    ) -> List[CredentialVerificationResult]:
        """Get verification history."""
        history = self.verification_history

        if credential_id:
            history = [h for h in history if h.credential_id == credential_id]

        return history[-limit:]


class CredentialRefreshManager:
    """
    Manages credential refresh operations.
    Handles automatic refresh for expiring credentials.
    """

    def __init__(self, credential_store: CredentialStore, verifier: CredentialVerifier):
        self.credential_store = credential_store
        self.verifier = verifier
        self.refresh_handlers: Dict[CredentialType, Any] = {}

    def register_refresh_handler(self, credential_type: CredentialType, handler):
        """Register a refresh handler for a credential type."""
        self.refresh_handlers[credential_type] = handler

    async def refresh_credential(self, credential_id: str) -> bool:
        """
        Refresh a credential.

        Args:
            credential_id: ID of credential to refresh

        Returns:
            True if refresh successful, False otherwise
        """
        credential = self.credential_store.get_credential(credential_id)
        if not credential:
            return False

        handler = self.refresh_handlers.get(credential.credential_type)
        if not handler:
            return False

        try:
            new_credential_value = await handler.refresh(credential)

            # Update credential
            updates = {
                "credential_value": new_credential_value,
                "status": CredentialStatus.ACTIVE,
                "expires_at": datetime.now(timezone.utc) + timedelta(days=30)  # Default 30 days
            }

            self.credential_store.update_credential(credential_id, updates)

            # Verify new credential
            result = await self.verifier.verify_credential(credential_id, force_refresh=True)
            return result.is_valid

        except Exception as exc:
            logger.info(f"Error refreshing credential {credential_id}: {exc}")
            return False

    async def auto_refresh_expiring_credentials(self, hours_threshold: int = 24):
        """
        Automatically refresh credentials expiring within threshold.

        Args:
            hours_threshold: Refresh credentials expiring within this many hours
        """
        expiring = self.credential_store.get_expiring_credentials(hours_threshold)

        for credential in expiring:
            if credential.status == CredentialStatus.ACTIVE:
                await self.refresh_credential(credential.id)


class CredentialVerificationSystem:
    """
    Complete credential verification system.
    Provides unified interface for credential management and verification.
    """

    def __init__(self):
        self.store = CredentialStore()
        self.verifier = CredentialVerifier(self.store)
        self.refresh_manager = CredentialRefreshManager(self.store, self.verifier)

    def add_credential(
        self,
        credential_type: CredentialType,
        service_name: str,
        credential_value: str,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a new credential."""
        credential = Credential(
            id=f"{service_name}_{credential_type}_{datetime.now(timezone.utc).timestamp()}",
            credential_type=credential_type,
            service_name=service_name,
            credential_value=credential_value,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        return self.store.add_credential(credential)

    async def verify_credential(self, credential_id: str) -> CredentialVerificationResult:
        """Verify a credential."""
        return await self.verifier.verify_credential(credential_id)

    async def verify_service_credentials(self, service_name: str) -> List[CredentialVerificationResult]:
        """Verify all credentials for a service."""
        credentials = self.store.list_credentials(service_name=service_name)
        credential_ids = [c.id for c in credentials]
        return await self.verifier.verify_multiple_credentials(credential_ids)

    def get_credential_status(self, credential_id: str) -> Optional[CredentialStatus]:
        """Get current status of a credential."""
        credential = self.store.get_credential(credential_id)
        return credential.status if credential else None

    async def refresh_credential(self, credential_id: str) -> bool:
        """Refresh a credential."""
        return await self.refresh_manager.refresh_credential(credential_id)

    def register_refresh_handler(self, credential_type: CredentialType, handler):
        """Register a refresh handler."""
        self.refresh_manager.register_refresh_handler(credential_type, handler)

    async def auto_refresh_expiring(self, hours_threshold: int = 24):
        """Auto-refresh expiring credentials."""
        await self.refresh_manager.auto_refresh_expiring_credentials(hours_threshold)

    def get_verification_history(self, credential_id: Optional[str] = None) -> List[CredentialVerificationResult]:
        """Get verification history."""
        return self.verifier.get_verification_history(credential_id)
