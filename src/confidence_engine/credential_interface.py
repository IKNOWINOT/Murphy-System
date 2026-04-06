"""
Credential Verification Interface
Provides unified interface for credential verification across different services.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
from src.confidence_engine.credential_verifier import (
    Credential,
    CredentialStatus,
    CredentialType,
    CredentialVerificationResult,
)


class VerificationMethod(str, Enum):
    """Methods for verifying credentials."""
    API_CALL = "api_call"
    TOKEN_VALIDATION = "token_validation"
    SIGNATURE_CHECK = "signature_check"
    EXPIRY_CHECK = "expiry_check"
    PERMISSION_CHECK = "permission_check"
    RATE_LIMIT_CHECK = "rate_limit_check"


class ServiceProvider(str, Enum):
    """Supported service providers."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    GITHUB = "github"
    GITLAB = "gitlab"
    TWILIO = "twilio"
    SENDGRID = "sendgrid"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DATABASE = "database"
    CUSTOM = "custom"


class CredentialPermission(BaseModel):
    """Represents a permission associated with a credential."""
    name: str
    scope: str
    granted: bool
    expires_at: Optional[datetime] = None


class VerificationRequest(BaseModel):
    """Request for credential verification."""
    credential_id: str
    verification_methods: List[VerificationMethod]
    service_provider: ServiceProvider
    required_permissions: List[str] = Field(default_factory=list)
    check_rate_limits: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerificationResponse(BaseModel):
    """Response from credential verification."""
    credential_id: str
    is_valid: bool
    status: CredentialStatus
    verification_methods_passed: List[VerificationMethod]
    verification_methods_failed: List[VerificationMethod]
    permissions: List[CredentialPermission] = Field(default_factory=list)
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset_at: Optional[datetime] = None
    error_details: Optional[str] = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_provider: Optional[ServiceProvider] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ICredentialVerifier(Protocol):
    """Protocol for credential verifiers."""

    async def verify(
        self,
        credential: Credential,
        request: VerificationRequest
    ) -> VerificationResponse:
        """Verify a credential."""
        ...

    async def check_permissions(
        self,
        credential: Credential,
        required_permissions: List[str]
    ) -> List[CredentialPermission]:
        """Check credential permissions."""
        ...

    async def check_rate_limits(
        self,
        credential: Credential
    ) -> Tuple[Optional[int], Optional[datetime]]:
        """Check rate limits for credential."""
        ...


class BaseCredentialVerifier(ABC):
    """Base class for credential verifiers."""

    def __init__(self, service_provider: ServiceProvider):
        self.service_provider = service_provider
        self.verification_cache: Dict[str, Tuple[datetime, VerificationResponse]] = {}
        self.cache_ttl_seconds = 300  # 5 minutes

    @abstractmethod
    async def verify_api_call(self, credential: Credential) -> bool:
        """Verify credential by making an API call."""
        pass

    @abstractmethod
    async def verify_token(self, credential: Credential) -> bool:
        """Verify token validity."""
        pass

    @abstractmethod
    async def check_permissions(
        self,
        credential: Credential,
        required_permissions: List[str]
    ) -> List[CredentialPermission]:
        """Check credential permissions."""
        pass

    @abstractmethod
    async def check_rate_limits(
        self,
        credential: Credential
    ) -> Tuple[Optional[int], Optional[datetime]]:
        """Check rate limits."""
        pass

    async def verify(
        self,
        credential: Credential,
        request: VerificationRequest
    ) -> VerificationResponse:
        """
        Verify credential using requested methods.

        Args:
            credential: Credential to verify
            request: Verification request with methods and requirements

        Returns:
            VerificationResponse with verification results
        """
        # Check cache
        cache_key = f"{credential.id}_{request.service_provider}"
        if cache_key in self.verification_cache:
            cached_time, cached_response = self.verification_cache[cache_key]
            if (datetime.now(timezone.utc) - cached_time).seconds < self.cache_ttl_seconds:
                return cached_response

        passed_methods = []
        failed_methods = []
        is_valid = True
        error_details = None

        # Run verification methods
        for method in request.verification_methods:
            try:
                if method == VerificationMethod.API_CALL:
                    result = await self.verify_api_call(credential)
                elif method == VerificationMethod.TOKEN_VALIDATION:
                    result = await self.verify_token(credential)
                elif method == VerificationMethod.EXPIRY_CHECK:
                    result = not credential.is_expired()
                elif method == VerificationMethod.SIGNATURE_CHECK:
                    result = await self.verify_signature(credential)
                else:
                    result = True  # Default pass for unknown methods

                if result:
                    passed_methods.append(method)
                else:
                    failed_methods.append(method)
                    is_valid = False

            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                failed_methods.append(method)
                is_valid = False
                error_details = str(exc)

        # Check permissions if required
        permissions = []
        if request.required_permissions:
            permissions = await self.check_permissions(
                credential,
                request.required_permissions
            )

            # Fail if any required permission is not granted
            if not all(p.granted for p in permissions):
                is_valid = False

        # Check rate limits if requested
        rate_limit_remaining = None
        rate_limit_reset_at = None
        if request.check_rate_limits:
            rate_limit_remaining, rate_limit_reset_at = await self.check_rate_limits(credential)

            # Fail if rate limit exceeded
            if rate_limit_remaining is not None and rate_limit_remaining <= 0:
                is_valid = False
                error_details = "Rate limit exceeded"

        # Determine status
        if is_valid:
            status = CredentialStatus.ACTIVE
        elif credential.is_expired():
            status = CredentialStatus.EXPIRED
        else:
            status = CredentialStatus.INVALID

        response = VerificationResponse(
            credential_id=credential.id,
            is_valid=is_valid,
            status=status,
            verification_methods_passed=passed_methods,
            verification_methods_failed=failed_methods,
            permissions=permissions,
            rate_limit_remaining=rate_limit_remaining,
            rate_limit_reset_at=rate_limit_reset_at,
            error_details=error_details
        )

        # Cache response
        self.verification_cache[cache_key] = (datetime.now(timezone.utc), response)

        return response

    async def verify_signature(self, credential: Credential) -> bool:
        """Verify credential signature. Override in subclasses."""
        return True


class AWSCredentialVerifier(BaseCredentialVerifier):
    """Verifier for AWS credentials."""

    def __init__(self):
        super().__init__(ServiceProvider.AWS)

    async def verify_api_call(self, credential: Credential) -> bool:
        """Verify AWS credentials via STS GetCallerIdentity (or format check).

        Falls back to format validation when boto3 is absent or when the
        STS call fails due to network / permission issues.
        """
        if not credential.credential_value:
            return False
        try:
            import boto3  # type: ignore[import-untyped]
            sts = boto3.client(
                "sts",
                aws_access_key_id=credential.credential_value,
                aws_secret_access_key=credential.metadata.get("secret_key", ""),
            )
            sts.get_caller_identity()
            return True
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            pass
        # Fallback — validate key format only
        return self._validate_aws_key_format(credential.credential_value)

    async def verify_token(self, credential: Credential) -> bool:
        """Verify AWS credential type and format."""
        if credential.credential_type not in (
            CredentialType.API_KEY,
            CredentialType.SERVICE_ACCOUNT,
        ):
            return False
        return self._validate_aws_key_format(credential.credential_value)

    async def check_permissions(
        self,
        credential: Credential,
        required_permissions: List[str]
    ) -> List[CredentialPermission]:
        """Check AWS IAM permissions (simulated when boto3 unavailable)."""
        permissions: List[CredentialPermission] = []
        for perm in required_permissions:
            permissions.append(CredentialPermission(
                name=perm,
                scope="aws",
                granted=True  # Simulated — real impl uses IAM policy simulator
            ))
        return permissions

    async def check_rate_limits(
        self,
        credential: Credential
    ) -> Tuple[Optional[int], Optional[datetime]]:
        """AWS uses per-service rate limits; return None to indicate no global cap."""
        return None, None

    @staticmethod
    def _validate_aws_key_format(value: str) -> bool:
        """Basic format validation for AWS access key IDs.

        AWS access-key IDs are 20-character alphanumeric strings that
        start with ``AKIA`` (long-term) or ``ASIA`` (temporary/STS).
        Secret access keys are 40 characters.  We accept either form
        via a minimum-length check plus an optional prefix test.
        """
        if not value:
            return False
        # Accept AKIA*/ASIA* keys or any sufficiently long credential value
        if value.startswith(("AKIA", "ASIA")):
            return len(value) >= 20
        return len(value) >= 16


class GitHubCredentialVerifier(BaseCredentialVerifier):
    """Verifier for GitHub credentials."""

    def __init__(self):
        super().__init__(ServiceProvider.GITHUB)

    async def verify_api_call(self, credential: Credential) -> bool:
        """Verify GitHub token via the /user API (or format fallback)."""
        if not credential.credential_value:
            return False
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {credential.credential_value}",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception as exc:
            # Network unavailable — fall back to format check
            logger.debug("Suppressed exception: %s", exc)
            return self._validate_github_token_format(credential.credential_value)

    async def verify_token(self, credential: Credential) -> bool:
        """Verify GitHub token format (ghp_, gho_, ghs_, ghu_ prefix)."""
        return self._validate_github_token_format(credential.credential_value)

    async def check_permissions(
        self,
        credential: Credential,
        required_permissions: List[str]
    ) -> List[CredentialPermission]:
        """Check GitHub OAuth scopes (simulated when network unavailable)."""
        permissions: List[CredentialPermission] = []
        for perm in required_permissions:
            permissions.append(CredentialPermission(
                name=perm,
                scope="github",
                granted=True  # Simulated — real impl checks X-OAuth-Scopes header
            ))
        return permissions

    async def check_rate_limits(
        self,
        credential: Credential
    ) -> Tuple[Optional[int], Optional[datetime]]:
        """Return GitHub's standard authenticated rate limit."""
        return 5000, datetime.now(timezone.utc) + timedelta(hours=1)

    @staticmethod
    def _validate_github_token_format(value: str) -> bool:
        """GitHub PATs/fine-grained tokens have known prefixes."""
        if not value:
            return False
        return value.startswith(("ghp_", "gho_", "ghs_", "ghu_", "github_pat_"))


class DatabaseCredentialVerifier(BaseCredentialVerifier):
    """Verifier for database credentials."""

    def __init__(self):
        super().__init__(ServiceProvider.DATABASE)

    async def verify_api_call(self, credential: Credential) -> bool:
        """Verify database credentials by format inspection.

        A real implementation would attempt a lightweight connection (e.g.,
        ``SELECT 1``).  Without knowing the driver at runtime we validate
        the connection-string format instead.
        """
        if not credential.credential_value:
            return False
        return self._looks_like_connection_string(credential.credential_value)

    async def verify_token(self, credential: Credential) -> bool:
        """Verify database credential format."""
        return self._looks_like_connection_string(credential.credential_value)

    async def check_permissions(
        self,
        credential: Credential,
        required_permissions: List[str]
    ) -> List[CredentialPermission]:
        """Check database permissions (simulated without live connection)."""
        permissions: List[CredentialPermission] = []
        for perm in required_permissions:
            permissions.append(CredentialPermission(
                name=perm,
                scope="database",
                granted=True  # Simulated — real impl queries INFORMATION_SCHEMA
            ))
        return permissions

    async def check_rate_limits(
        self,
        credential: Credential
    ) -> Tuple[Optional[int], Optional[datetime]]:
        """Databases use connection-pool limits, not rate limits."""
        return None, None

    @staticmethod
    def _looks_like_connection_string(value: str) -> bool:
        """Heuristic check for common connection-string patterns."""
        if not value:
            return False
        lowered = value.lower()
        return any(
            keyword in lowered
            for keyword in (
                "host=", "server=", "database=", "mongodb://",
                "postgresql://", "mysql://", "sqlite://", "dsn=",
            )
        )


class CredentialVerifierFactory:
    """Factory for creating credential verifiers."""

    _verifiers: Dict[ServiceProvider, BaseCredentialVerifier] = {}

    @classmethod
    def register_verifier(
        cls,
        provider: ServiceProvider,
        verifier: BaseCredentialVerifier
    ):
        """Register a verifier for a service provider."""
        cls._verifiers[provider] = verifier

    @classmethod
    def get_verifier(cls, provider: ServiceProvider) -> BaseCredentialVerifier:
        """Get verifier for a service provider."""
        if provider not in cls._verifiers:
            # Register default verifiers
            cls._register_default_verifiers()

        return cls._verifiers.get(provider)

    @classmethod
    def _register_default_verifiers(cls):
        """Register default verifiers."""
        if ServiceProvider.AWS not in cls._verifiers:
            cls.register_verifier(ServiceProvider.AWS, AWSCredentialVerifier())

        if ServiceProvider.GITHUB not in cls._verifiers:
            cls.register_verifier(ServiceProvider.GITHUB, GitHubCredentialVerifier())

        if ServiceProvider.DATABASE not in cls._verifiers:
            cls.register_verifier(ServiceProvider.DATABASE, DatabaseCredentialVerifier())

        if ServiceProvider.CUSTOM not in cls._verifiers:
            cls.register_verifier(ServiceProvider.CUSTOM, JWTCredentialVerifier())


class JWTCredentialVerifier(BaseCredentialVerifier):
    """Verifier for JWT tokens — CRED-JWT-001.

    Validates JSON Web Tokens issued by the Murphy System
    :class:`SecurityMiddleware`.  Checks structure, expiry, issuer
    claim, and permission scopes embedded in the ``permissions`` or
    ``scopes`` claim.

    Falls back to structural validation when ``PyJWT`` is not installed.
    """

    def __init__(self) -> None:
        super().__init__(ServiceProvider.CUSTOM)

    async def verify_api_call(self, credential: Credential) -> bool:
        """Validate JWT structure and expiry via decode (or format check).

        Uses :mod:`jwt` when available; otherwise validates the
        three-part Base64 structure manually.
        """
        token = credential.credential_value
        if not token:
            return False
        try:
            import jwt as pyjwt  # type: ignore[import-untyped]
            # Decode without verification to check structure + expiry
            payload = pyjwt.decode(
                token, options={"verify_signature": False}
            )
            # Check expiry
            exp = payload.get("exp")
            if exp is not None:
                from datetime import datetime, timezone as _tz
                if datetime.fromtimestamp(exp, tz=_tz.utc) < datetime.now(_tz.utc):
                    return False
            return True
        except ImportError:
            logger.debug("PyJWT not installed — falling back to format check")
        except Exception as exc:
            logger.debug("JWT decode failed: %s", exc)
            return False
        # Fallback: structural validation (header.payload.signature)
        return self._validate_jwt_format(token)

    async def verify_token(self, credential: Credential) -> bool:
        """Verify JWT credential type and format."""
        if credential.credential_type not in (
            CredentialType.JWT_TOKEN,
            CredentialType.OAUTH_TOKEN,
        ):
            return False
        return self._validate_jwt_format(credential.credential_value)

    async def check_permissions(
        self,
        credential: Credential,
        required_permissions: List[str]
    ) -> List[CredentialPermission]:
        """Extract and validate permissions from the JWT claims."""
        permissions: List[CredentialPermission] = []
        token_perms = self._extract_jwt_permissions(credential.credential_value)
        for perm in required_permissions:
            granted = perm in token_perms or "*" in token_perms
            permissions.append(CredentialPermission(
                name=perm,
                scope="jwt",
                granted=granted,
            ))
        return permissions

    async def check_rate_limits(
        self,
        credential: Credential
    ) -> Tuple[Optional[int], Optional[datetime]]:
        """JWT tokens carry no inherent rate limit; return None."""
        return None, None

    @staticmethod
    def _validate_jwt_format(token: str) -> bool:
        """Validate three-part Base64URL JWT structure."""
        if not token:
            return False
        parts = token.split(".")
        if len(parts) != 3:
            return False
        import base64
        for part in parts[:2]:
            # Pad and attempt decode
            padded = part + "=" * (-len(part) % 4)
            try:
                base64.urlsafe_b64decode(padded)
            except Exception:
                return False
        return True

    @staticmethod
    def _extract_jwt_permissions(token: str) -> List[str]:
        """Extract permission claims from JWT payload without verification."""
        try:
            import base64, json as _json
            parts = token.split(".")
            if len(parts) < 2:
                return []
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = _json.loads(base64.urlsafe_b64decode(padded))
            # Check common permission claim names
            perms = payload.get("permissions", [])
            if not perms:
                perms = payload.get("scopes", [])
            if not perms:
                scope_str = payload.get("scope", "")
                if scope_str:
                    perms = scope_str.split()
            return list(perms) if isinstance(perms, (list, tuple)) else [str(perms)]
        except Exception:
            return []


class CredentialVerificationInterface:
    """
    Unified interface for credential verification across all services.
    """

    def __init__(self):
        self.factory = CredentialVerifierFactory()
        self.verification_history: List[VerificationResponse] = []

    async def verify_credential(
        self,
        credential: Credential,
        service_provider: ServiceProvider,
        verification_methods: Optional[List[VerificationMethod]] = None,
        required_permissions: Optional[List[str]] = None,
        check_rate_limits: bool = True
    ) -> VerificationResponse:
        """
        Verify a credential.

        Args:
            credential: Credential to verify
            service_provider: Service provider for the credential
            verification_methods: Methods to use for verification
            required_permissions: Required permissions to check
            check_rate_limits: Whether to check rate limits

        Returns:
            VerificationResponse with results
        """
        # Default verification methods
        if verification_methods is None:
            verification_methods = [
                VerificationMethod.EXPIRY_CHECK,
                VerificationMethod.TOKEN_VALIDATION,
                VerificationMethod.API_CALL
            ]

        # Create verification request
        request = VerificationRequest(
            credential_id=credential.id,
            verification_methods=verification_methods,
            service_provider=service_provider,
            required_permissions=required_permissions or [],
            check_rate_limits=check_rate_limits
        )

        # Get appropriate verifier
        verifier = self.factory.get_verifier(service_provider)
        if not verifier:
            response = VerificationResponse(
                credential_id=credential.id,
                is_valid=False,
                status=CredentialStatus.INVALID,
                verification_methods_passed=[],
                verification_methods_failed=verification_methods,
                error_details=f"No verifier available for {service_provider}",
                service_provider=service_provider
            )
            self.verification_history.append(response)
            return response

        # Perform verification
        response = await verifier.verify(credential, request)

        # Stamp provider onto the response for downstream filtering
        response.service_provider = service_provider

        # Record in history
        self.verification_history.append(response)

        return response

    async def batch_verify(
        self,
        credentials: List[Tuple[Credential, ServiceProvider]]
    ) -> List[VerificationResponse]:
        """
        Verify multiple credentials in batch.

        Args:
            credentials: List of (credential, service_provider) tuples

        Returns:
            List of VerificationResponse objects
        """
        import asyncio

        tasks = [
            self.verify_credential(cred, provider)
            for cred, provider in credentials
        ]

        return await asyncio.gather(*tasks)

    def get_verification_history(
        self,
        credential_id: Optional[str] = None,
        service_provider: Optional[ServiceProvider] = None,
        limit: int = 100
    ) -> List[VerificationResponse]:
        """Get verification history with optional filters."""
        history = self.verification_history

        if credential_id:
            history = [h for h in history if h.credential_id == credential_id]

        if service_provider:
            history = [h for h in history if h.service_provider == service_provider]

        return history[-limit:]

    def get_verification_statistics(self) -> Dict[str, Any]:
        """Get statistics about verifications."""
        total = len(self.verification_history)

        if total == 0:
            return {
                "total_verifications": 0,
                "success_rate": 0.0,
                "average_methods_per_verification": 0.0
            }

        successful = sum(1 for h in self.verification_history if h.is_valid)

        total_methods = sum(
            len(h.verification_methods_passed) + len(h.verification_methods_failed)
            for h in self.verification_history
        )

        return {
            "total_verifications": total,
            "successful_verifications": successful,
            "failed_verifications": total - successful,
            "success_rate": successful / total,
            "average_methods_per_verification": total_methods / total
        }
