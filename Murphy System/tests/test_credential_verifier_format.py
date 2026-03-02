"""
API-002: Credential Verifier Format Validation Tests

Tests proper format validation in credential verifiers:
- API key format and service-specific prefix validation
- OAuth token structural integrity
- JWT token structure (header.payload.signature) with base64 validation
"""

import os
import sys
import base64
import json
import pytest

_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_here, "..", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from confidence_engine.credential_verifier import (
    Credential,
    CredentialType,
    CredentialStore,
    CredentialVerifier,
)


@pytest.fixture
def store():
    return CredentialStore()


@pytest.fixture
def verifier(store):
    return CredentialVerifier(store)


def _make_jwt(alg="HS256", payload=None):
    """Build a minimal valid JWT string for testing."""
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": alg, "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(
        json.dumps(payload or {"sub": "user1"}).encode()
    ).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fakesignature12345").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


# =========================================================================
# API Key Verification
# =========================================================================


class TestAPIKeyVerification:
    """Test improved API key format validation (API-002)."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self, verifier):
        cred = Credential(
            id="test-1",
            credential_type=CredentialType.API_KEY,
            service_name="generic",
            credential_value="abcdefghijklmnopqrstuvwxyz",
        )
        assert await verifier._verify_api_key(cred) is True

    @pytest.mark.asyncio
    async def test_too_short_api_key(self, verifier):
        cred = Credential(
            id="test-2",
            credential_type=CredentialType.API_KEY,
            service_name="generic",
            credential_value="short",
        )
        assert await verifier._verify_api_key(cred) is False

    @pytest.mark.asyncio
    async def test_api_key_with_special_chars(self, verifier):
        cred = Credential(
            id="test-3",
            credential_type=CredentialType.API_KEY,
            service_name="generic",
            credential_value="has spaces and $pecial chars!",
        )
        assert await verifier._verify_api_key(cred) is False

    @pytest.mark.asyncio
    async def test_openai_key_valid_prefix(self, verifier):
        cred = Credential(
            id="test-4",
            credential_type=CredentialType.API_KEY,
            service_name="openai",
            credential_value="sk-" + "a" * 48,
        )
        assert await verifier._verify_api_key(cred) is True

    @pytest.mark.asyncio
    async def test_openai_key_wrong_prefix(self, verifier):
        cred = Credential(
            id="test-5",
            credential_type=CredentialType.API_KEY,
            service_name="openai",
            credential_value="wrong_prefix_" + "a" * 48,
        )
        assert await verifier._verify_api_key(cred) is False

    @pytest.mark.asyncio
    async def test_groq_key_valid_prefix(self, verifier):
        cred = Credential(
            id="test-6",
            credential_type=CredentialType.API_KEY,
            service_name="groq",
            credential_value="gsk_" + "a" * 48,
        )
        assert await verifier._verify_api_key(cred) is True

    @pytest.mark.asyncio
    async def test_stripe_key_valid_prefix(self, verifier):
        cred = Credential(
            id="test-7",
            credential_type=CredentialType.API_KEY,
            service_name="stripe",
            credential_value="sk_test_" + "a" * 48,
        )
        assert await verifier._verify_api_key(cred) is True

    @pytest.mark.asyncio
    async def test_github_key_valid_prefix(self, verifier):
        cred = Credential(
            id="test-8",
            credential_type=CredentialType.API_KEY,
            service_name="github",
            credential_value="ghp_" + "a" * 48,
        )
        assert await verifier._verify_api_key(cred) is True

    @pytest.mark.asyncio
    async def test_empty_api_key(self, verifier):
        cred = Credential(
            id="test-9",
            credential_type=CredentialType.API_KEY,
            service_name="generic",
            credential_value="",
        )
        assert await verifier._verify_api_key(cred) is False


# =========================================================================
# OAuth Token Verification
# =========================================================================


class TestOAuthTokenVerification:
    """Test improved OAuth token validation (API-002)."""

    @pytest.mark.asyncio
    async def test_valid_oauth_token(self, verifier):
        cred = Credential(
            id="test-oauth-1",
            credential_type=CredentialType.OAUTH_TOKEN,
            service_name="github",
            credential_value="a1b2c3d4e5f6" * 5,  # 60 chars, diverse
        )
        assert await verifier._verify_oauth_token(cred) is True

    @pytest.mark.asyncio
    async def test_too_short_oauth_token(self, verifier):
        cred = Credential(
            id="test-oauth-2",
            credential_type=CredentialType.OAUTH_TOKEN,
            service_name="github",
            credential_value="short",
        )
        assert await verifier._verify_oauth_token(cred) is False

    @pytest.mark.asyncio
    async def test_trivially_invalid_oauth_token(self, verifier):
        """Token with all same characters is rejected."""
        cred = Credential(
            id="test-oauth-3",
            credential_type=CredentialType.OAUTH_TOKEN,
            service_name="github",
            credential_value="a" * 50,
        )
        assert await verifier._verify_oauth_token(cred) is False

    @pytest.mark.asyncio
    async def test_oauth_token_with_control_chars(self, verifier):
        cred = Credential(
            id="test-oauth-4",
            credential_type=CredentialType.OAUTH_TOKEN,
            service_name="github",
            credential_value="valid_token_start\x00" + "a" * 30,
        )
        assert await verifier._verify_oauth_token(cred) is False


# =========================================================================
# JWT Token Verification
# =========================================================================


class TestJWTTokenVerification:
    """Test improved JWT token validation (API-002)."""

    @pytest.mark.asyncio
    async def test_valid_jwt_token(self, verifier):
        cred = Credential(
            id="test-jwt-1",
            credential_type=CredentialType.JWT_TOKEN,
            service_name="auth0",
            credential_value=_make_jwt(),
        )
        assert await verifier._verify_jwt_token(cred) is True

    @pytest.mark.asyncio
    async def test_jwt_missing_part(self, verifier):
        cred = Credential(
            id="test-jwt-2",
            credential_type=CredentialType.JWT_TOKEN,
            service_name="auth0",
            credential_value="header.payload",  # Missing signature
        )
        assert await verifier._verify_jwt_token(cred) is False

    @pytest.mark.asyncio
    async def test_jwt_invalid_base64(self, verifier):
        cred = Credential(
            id="test-jwt-3",
            credential_type=CredentialType.JWT_TOKEN,
            service_name="auth0",
            credential_value="not-base64.not-base64.not-base64",
        )
        assert await verifier._verify_jwt_token(cred) is False

    @pytest.mark.asyncio
    async def test_jwt_missing_alg_header(self, verifier):
        """JWT without 'alg' in header is rejected."""
        header = base64.urlsafe_b64encode(
            json.dumps({"typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "user1"}).encode()
        ).rstrip(b"=").decode()
        sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()

        cred = Credential(
            id="test-jwt-4",
            credential_type=CredentialType.JWT_TOKEN,
            service_name="auth0",
            credential_value=f"{header}.{payload}.{sig}",
        )
        assert await verifier._verify_jwt_token(cred) is False

    @pytest.mark.asyncio
    async def test_jwt_empty_string(self, verifier):
        cred = Credential(
            id="test-jwt-5",
            credential_type=CredentialType.JWT_TOKEN,
            service_name="auth0",
            credential_value="",
        )
        assert await verifier._verify_jwt_token(cred) is False

    @pytest.mark.asyncio
    async def test_jwt_with_custom_claims(self, verifier):
        cred = Credential(
            id="test-jwt-6",
            credential_type=CredentialType.JWT_TOKEN,
            service_name="auth0",
            credential_value=_make_jwt(
                payload={"sub": "user1", "role": "admin", "exp": 9999999999}
            ),
        )
        assert await verifier._verify_jwt_token(cred) is True
