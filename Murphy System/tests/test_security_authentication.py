"""
Tests for Security Plane Authentication

Tests:
- HumanAuthenticator (passkeys, biometrics)
- MachineAuthenticator (mTLS)
- IdentityVerifier (identity management)
- ContextualVerifier (context-based verification)
- IntentConfirmer (intent confirmation)
"""

import pytest
from datetime import datetime, timedelta
import time

from src.security_plane.authentication import (
    HumanAuthenticator,
    MachineAuthenticator,
    IdentityVerifier,
    ContextualVerifier,
    IntentConfirmer,
    Identity,
    IdentityType,
    AuthenticationType,
    BiometricType,
    AuthenticationCredential,
    AuthenticationSession,
    ContextualVerification,
    IntentConfirmation
)
from src.security_plane.cryptography import KeyManager, CryptographicPrimitives
from src.security_plane.schemas import TrustLevel, AuthorityBand


class TestHumanAuthenticator:
    """Test HumanAuthenticator."""

    def test_register_passkey(self):
        """Test registering a passkey."""
        key_manager = KeyManager()
        authenticator = HumanAuthenticator(key_manager)

        public_key = b"public_key_bytes"

        credential = authenticator.register_passkey(
            identity_id="user-001",
            public_key=public_key,
            device_id="device-001",
            device_name="iPhone 15"
        )

        assert credential.credential_type == AuthenticationType.PASSKEY
        assert credential.identity_id == "user-001"
        assert credential.device_id == "device-001"
        assert credential.active is True

    def test_authenticate_passkey(self):
        """Test passkey authentication."""
        key_manager = KeyManager()
        authenticator = HumanAuthenticator(key_manager)

        public_key = b"public_key_bytes"

        # Register passkey
        credential = authenticator.register_passkey(
            identity_id="user-002",
            public_key=public_key,
            device_id="device-002",
            device_name="MacBook Pro"
        )

        # Authenticate
        challenge = b"random_challenge"
        signature = CryptographicPrimitives.hash_data(challenge + public_key)

        success, session = authenticator.authenticate_passkey(
            identity_id="user-002",
            challenge=challenge,
            signature=signature,
            credential_id=credential.credential_id
        )

        assert success is True
        assert session is not None
        assert session.identity_id == "user-002"
        assert session.auth_type == AuthenticationType.PASSKEY

    def test_authenticate_passkey_invalid_signature(self):
        """Test passkey authentication with invalid signature."""
        key_manager = KeyManager()
        authenticator = HumanAuthenticator(key_manager)

        public_key = b"public_key_bytes"

        # Register passkey
        credential = authenticator.register_passkey(
            identity_id="user-003",
            public_key=public_key,
            device_id="device-003",
            device_name="iPad"
        )

        # Authenticate with wrong signature
        challenge = b"random_challenge"
        wrong_signature = b"wrong_signature"

        success, session = authenticator.authenticate_passkey(
            identity_id="user-003",
            challenge=challenge,
            signature=wrong_signature,
            credential_id=credential.credential_id
        )

        assert success is False
        assert session is None

    def test_register_biometric(self):
        """Test registering a biometric."""
        key_manager = KeyManager()
        authenticator = HumanAuthenticator(key_manager)

        biometric_template = b"encrypted_biometric_template"

        credential = authenticator.register_biometric(
            identity_id="user-004",
            biometric_type=BiometricType.FINGERPRINT,
            biometric_template_encrypted=biometric_template,
            device_id="device-004"
        )

        assert credential.credential_type == AuthenticationType.BIOMETRIC
        assert credential.identity_id == "user-004"
        assert credential.active is True

    def test_session_expiry(self):
        """Test session expiry."""
        key_manager = KeyManager()
        authenticator = HumanAuthenticator(key_manager)

        # Create session with short duration
        session = authenticator._create_session(
            identity_id="user-005",
            auth_type=AuthenticationType.PASSKEY,
            session_duration=timedelta(seconds=1)
        )

        # Session should be active initially
        assert session.is_expired() is False

        # Wait for expiry
        time.sleep(1.1)

        # Session should be expired
        assert session.is_expired() is True

    def test_revoke_credential(self):
        """Test credential revocation."""
        key_manager = KeyManager()
        authenticator = HumanAuthenticator(key_manager)

        public_key = b"public_key_bytes"

        # Register passkey
        credential = authenticator.register_passkey(
            identity_id="user-006",
            public_key=public_key,
            device_id="device-006",
            device_name="Device"
        )

        # Revoke credential
        success = authenticator.revoke_credential(
            credential.credential_id,
            reason="Device lost"
        )

        assert success is True
        assert credential.revoked is True
        assert credential.active is False


class TestMachineAuthenticator:
    """Test MachineAuthenticator."""

    def test_issue_certificate(self):
        """Test issuing mTLS certificate."""
        key_manager = KeyManager()
        authenticator = MachineAuthenticator(key_manager)

        credential = authenticator.issue_certificate(
            identity_id="service-001",
            identity_type=IdentityType.SERVICE,
            capabilities=["read", "write"],
            certificate_duration=timedelta(minutes=10)
        )

        assert credential.credential_type == AuthenticationType.MTLS
        assert credential.identity_id == "service-001"
        assert credential.active is True
        assert credential.expires_at is not None

    def test_authenticate_mtls(self):
        """Test mTLS authentication."""
        key_manager = KeyManager()
        authenticator = MachineAuthenticator(key_manager)

        # Issue certificate
        credential = authenticator.issue_certificate(
            identity_id="service-002",
            identity_type=IdentityType.SERVICE,
            capabilities=["execute"]
        )

        # Authenticate
        client_cert = credential.public_key

        success, session = authenticator.authenticate_mtls(
            identity_id="service-002",
            client_certificate=client_cert,
            credential_id=credential.credential_id
        )

        assert success is True
        assert session is not None
        assert session.identity_id == "service-002"
        assert session.auth_type == AuthenticationType.MTLS

    def test_authenticate_mtls_expired_certificate(self):
        """Test mTLS authentication with expired certificate."""
        key_manager = KeyManager()
        authenticator = MachineAuthenticator(key_manager)

        # Issue certificate with immediate expiry
        credential = authenticator.issue_certificate(
            identity_id="service-003",
            identity_type=IdentityType.SERVICE,
            capabilities=["read"],
            certificate_duration=timedelta(seconds=0)
        )

        # Wait a moment
        time.sleep(0.1)

        # Authenticate (should fail due to expiry)
        client_cert = credential.public_key

        success, session = authenticator.authenticate_mtls(
            identity_id="service-003",
            client_certificate=client_cert,
            credential_id=credential.credential_id
        )

        assert success is False
        assert session is None


class TestIdentityVerifier:
    """Test IdentityVerifier."""

    def test_register_identity(self):
        """Test registering an identity."""
        verifier = IdentityVerifier()

        identity = verifier.register_identity(
            identity_id="user-007",
            identity_type=IdentityType.HUMAN,
            display_name="John Doe",
            allowed_auth_methods=[AuthenticationType.PASSKEY, AuthenticationType.BIOMETRIC]
        )

        assert identity.identity_id == "user-007"
        assert identity.identity_type == IdentityType.HUMAN
        assert identity.active is True

    def test_verify_identity(self):
        """Test verifying an identity."""
        verifier = IdentityVerifier()

        # Register identity
        verifier.register_identity(
            identity_id="user-008",
            identity_type=IdentityType.HUMAN,
            display_name="Jane Doe",
            allowed_auth_methods=[AuthenticationType.PASSKEY]
        )

        # Verify identity
        valid = verifier.verify_identity("user-008")
        assert valid is True

        # Verify non-existent identity
        valid = verifier.verify_identity("user-999")
        assert valid is False

    def test_suspend_identity(self):
        """Test suspending an identity."""
        verifier = IdentityVerifier()

        # Register identity
        verifier.register_identity(
            identity_id="user-009",
            identity_type=IdentityType.HUMAN,
            display_name="Suspended User",
            allowed_auth_methods=[AuthenticationType.PASSKEY]
        )

        # Suspend identity
        success = verifier.suspend_identity("user-009", reason="Security incident")
        assert success is True

        # Verify suspended identity
        valid = verifier.verify_identity("user-009")
        assert valid is False

    def test_reactivate_identity(self):
        """Test reactivating a suspended identity."""
        verifier = IdentityVerifier()

        # Register and suspend identity
        verifier.register_identity(
            identity_id="user-010",
            identity_type=IdentityType.HUMAN,
            display_name="Reactivated User",
            allowed_auth_methods=[AuthenticationType.PASSKEY]
        )
        verifier.suspend_identity("user-010", reason="Test")

        # Reactivate identity
        success = verifier.reactivate_identity("user-010")
        assert success is True

        # Verify reactivated identity
        valid = verifier.verify_identity("user-010")
        assert valid is True


class TestContextualVerifier:
    """Test ContextualVerifier."""

    def test_verify_context_business_hours(self):
        """Test context verification during business hours."""
        verifier = ContextualVerifier()

        verification = verifier.verify_context(
            identity_id="user-011",
            time_of_day="business_hours",
            location="office",
            device_id="known-device",
            network="corporate"
        )

        assert verification.verified is True
        assert verification.confidence == 1.0
        assert len(verification.anomalies) == 0

    def test_verify_context_after_hours(self):
        """Test context verification after hours."""
        verifier = ContextualVerifier()

        verification = verifier.verify_context(
            identity_id="user-012",
            time_of_day="after_hours",
            location="home",
            device_id="known-device",
            network="home"
        )

        assert verification.verified is True
        assert verification.confidence < 1.0
        assert "after hours" in verification.anomalies[0].lower()

    def test_verify_context_unknown_location(self):
        """Test context verification from unknown location."""
        verifier = ContextualVerifier()

        verification = verifier.verify_context(
            identity_id="user-013",
            time_of_day="business_hours",
            location="unknown-country",
            device_id="known-device",
            network="public"
        )

        assert verification.confidence < 0.8
        assert any("unknown location" in a.lower() for a in verification.anomalies)

    def test_verify_context_new_device(self):
        """Test context verification from new device."""
        verifier = ContextualVerifier()

        verification = verifier.verify_context(
            identity_id="user-014",
            time_of_day="business_hours",
            location="office",
            device_id="new-device",
            network="corporate"
        )

        assert verification.confidence < 1.0
        assert any("new device" in a.lower() for a in verification.anomalies)


class TestIntentConfirmer:
    """Test IntentConfirmer."""

    def test_request_confirmation(self):
        """Test requesting intent confirmation."""
        confirmer = IntentConfirmer()

        confirmation = confirmer.request_confirmation(
            identity_id="user-015",
            operation="delete_database",
            description="Delete production database",
            risk_level="critical"
        )

        assert confirmation.operation == "delete_database"
        assert confirmation.risk_level == "critical"
        assert confirmation.confirmed is False

    def test_confirm_intent(self):
        """Test confirming intent."""
        confirmer = IntentConfirmer()

        # Request confirmation
        confirmation = confirmer.request_confirmation(
            identity_id="user-016",
            operation="deploy_code",
            description="Deploy code to production",
            risk_level="high"
        )

        # Confirm intent
        success = confirmer.confirm_intent(
            confirmation.confirmation_id,
            confirmation_method="hardware_key"
        )

        assert success is True
        assert confirmation.confirmed is True

    def test_confirm_intent_with_semantic_match(self):
        """Test confirming intent with semantic matching."""
        confirmer = IntentConfirmer()

        # Request confirmation
        confirmation = confirmer.request_confirmation(
            identity_id="user-017",
            operation="transfer_funds",
            description="Transfer funds to external account",
            risk_level="high"
        )

        # Confirm with matching understanding
        success = confirmer.confirm_intent(
            confirmation.confirmation_id,
            confirmation_method="biometric",
            user_understanding="transfer funds to external account"
        )

        assert success is True
        assert confirmation.semantic_match is not None
        assert confirmation.semantic_match > 0.8

    def test_confirm_intent_semantic_mismatch(self):
        """Test confirming intent with semantic mismatch."""
        confirmer = IntentConfirmer()

        # Request confirmation
        confirmation = confirmer.request_confirmation(
            identity_id="user-018",
            operation="delete_user",
            description="Delete user account permanently",
            risk_level="critical"
        )

        # Confirm with mismatched understanding
        success = confirmer.confirm_intent(
            confirmation.confirmation_id,
            confirmation_method="explicit",
            user_understanding="create new user account"
        )

        # Should fail due to semantic mismatch
        assert success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
