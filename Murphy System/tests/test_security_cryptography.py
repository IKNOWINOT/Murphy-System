"""
Tests for Security Plane Cryptography

Tests:
- CryptographicPrimitives (hashing, nonce generation)
- ClassicalCryptography (key generation, signing, verification)
- PostQuantumCryptography (Kyber, Dilithium)
- HybridCryptography (classical + PQC)
- KeyManager (key generation, rotation, expiry)
- PacketSigner (packet signing, verification, single-use)
"""

import pytest
from datetime import datetime, timedelta, timezone
import time

from src.security_plane.cryptography import (
    CryptographicPrimitives,
    HashAlgorithm,
    ClassicalCryptography,
    PostQuantumCryptography,
    HybridCryptography,
    KeyManager,
    PacketSigner,
    KeyPair,
    SignatureResult,
    VerificationResult
)
from src.security_plane.schemas import (
    CryptographicAlgorithm,
    AuthorityBand
)


class TestCryptographicPrimitives:
    """Test CryptographicPrimitives."""

    def test_hash_data_sha256(self):
        """Test SHA-256 hashing."""
        data = b"test data"
        hash1 = CryptographicPrimitives.hash_data(data, HashAlgorithm.SHA256)
        hash2 = CryptographicPrimitives.hash_data(data, HashAlgorithm.SHA256)

        # Same data produces same hash
        assert hash1 == hash2

        # Different data produces different hash
        hash3 = CryptographicPrimitives.hash_data(b"different data", HashAlgorithm.SHA256)
        assert hash1 != hash3

    def test_generate_nonce(self):
        """Test nonce generation."""
        nonce1 = CryptographicPrimitives.generate_nonce()
        nonce2 = CryptographicPrimitives.generate_nonce()

        # Nonces should be unique
        assert nonce1 != nonce2

        # Nonces should be hex strings
        assert isinstance(nonce1, str)
        assert len(nonce1) == 64  # 32 bytes = 64 hex chars

    def test_constant_time_compare(self):
        """Test constant-time comparison."""
        data1 = b"test data"
        data2 = b"test data"
        data3 = b"different"

        assert CryptographicPrimitives.constant_time_compare(data1, data2) is True
        assert CryptographicPrimitives.constant_time_compare(data1, data3) is False


class TestClassicalCryptography:
    """Test ClassicalCryptography."""

    def test_generate_keypair(self):
        """Test classical key pair generation."""
        keypair = ClassicalCryptography.generate_keypair()

        assert keypair.algorithm == CryptographicAlgorithm.CLASSICAL
        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert keypair.is_expired() is False

    def test_sign_and_verify(self):
        """Test classical signing and verification."""
        keypair = ClassicalCryptography.generate_keypair()
        data = b"test data to sign"

        # Sign data
        signature = ClassicalCryptography.sign(data, keypair.private_key)

        # Verify signature
        valid = ClassicalCryptography.verify(
            data,
            signature,
            keypair.public_key,
            keypair.private_key
        )

        assert valid is True

    def test_verify_invalid_signature(self):
        """Test verification of invalid signature."""
        keypair = ClassicalCryptography.generate_keypair()
        data = b"test data"
        wrong_signature = b"invalid signature"

        valid = ClassicalCryptography.verify(
            data,
            wrong_signature,
            keypair.public_key,
            keypair.private_key
        )

        assert valid is False


class TestPostQuantumCryptography:
    """Test PostQuantumCryptography."""

    def test_generate_keypair_kyber(self):
        """Test Kyber key pair generation."""
        keypair = PostQuantumCryptography.generate_keypair_kyber()

        assert keypair.algorithm == CryptographicAlgorithm.POST_QUANTUM
        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert "kyber" in keypair.key_id

    def test_generate_keypair_dilithium(self):
        """Test Dilithium key pair generation."""
        keypair = PostQuantumCryptography.generate_keypair_dilithium()

        assert keypair.algorithm == CryptographicAlgorithm.POST_QUANTUM
        assert keypair.public_key is not None
        assert keypair.private_key is not None
        assert "dilithium" in keypair.key_id

    def test_sign_and_verify_dilithium(self):
        """Test Dilithium signing and verification."""
        keypair = PostQuantumCryptography.generate_keypair_dilithium()
        data = b"test data to sign"

        # Sign data
        signature = PostQuantumCryptography.sign_dilithium(data, keypair.private_key)

        # Verify signature
        valid = PostQuantumCryptography.verify_dilithium(
            data,
            signature,
            keypair.public_key,
            keypair.private_key
        )

        assert valid is True


class TestHybridCryptography:
    """Test HybridCryptography."""

    def test_generate_keypair(self):
        """Test hybrid key pair generation."""
        classical_kp, pqc_kp = HybridCryptography.generate_keypair()

        assert classical_kp.algorithm == CryptographicAlgorithm.CLASSICAL
        assert pqc_kp.algorithm == CryptographicAlgorithm.POST_QUANTUM

    def test_sign_and_verify_hybrid(self):
        """Test hybrid signing and verification."""
        classical_kp, pqc_kp = HybridCryptography.generate_keypair()
        data = b"test data to sign"

        # Sign with both algorithms
        classical_sig, pqc_sig = HybridCryptography.sign_hybrid(
            data,
            classical_kp.private_key,
            pqc_kp.private_key
        )

        # Verify with both algorithms
        valid = HybridCryptography.verify_hybrid(
            data,
            classical_sig,
            pqc_sig,
            classical_kp.public_key,
            pqc_kp.public_key,
            classical_kp.private_key,
            pqc_kp.private_key
        )

        assert valid is True

    def test_verify_hybrid_requires_both(self):
        """Test that hybrid verification requires both signatures to be valid."""
        classical_kp, pqc_kp = HybridCryptography.generate_keypair()
        data = b"test data"

        classical_sig, pqc_sig = HybridCryptography.sign_hybrid(
            data,
            classical_kp.private_key,
            pqc_kp.private_key
        )

        # Tamper with one signature
        invalid_classical_sig = b"invalid"

        valid = HybridCryptography.verify_hybrid(
            data,
            invalid_classical_sig,
            pqc_sig,
            classical_kp.public_key,
            pqc_kp.public_key,
            classical_kp.private_key,
            pqc_kp.private_key
        )

        # Should fail because classical signature is invalid
        assert valid is False


class TestKeyManager:
    """Test KeyManager."""

    def test_generate_key_hybrid(self):
        """Test generating hybrid key."""
        manager = KeyManager()

        key = manager.generate_key(
            identity_id="user-001",
            key_type="signing",
            algorithm=CryptographicAlgorithm.HYBRID
        )

        assert key.algorithm == CryptographicAlgorithm.HYBRID
        assert key.identity_id == "user-001"
        assert key.is_expired() is False

    def test_generate_key_pqc(self):
        """Test generating PQC key."""
        manager = KeyManager()

        key = manager.generate_key(
            identity_id="user-002",
            key_type="signing",
            algorithm=CryptographicAlgorithm.POST_QUANTUM
        )

        assert key.algorithm == CryptographicAlgorithm.POST_QUANTUM

    def test_get_key(self):
        """Test retrieving key."""
        manager = KeyManager()

        key = manager.generate_key(
            identity_id="user-003",
            key_type="signing"
        )

        retrieved = manager.get_key(key.key_id)

        assert retrieved is not None
        assert retrieved.key_id == key.key_id

    def test_rotate_key(self):
        """Test key rotation."""
        manager = KeyManager()

        old_key = manager.generate_key(
            identity_id="user-004",
            key_type="signing"
        )

        new_key = manager.rotate_key(old_key.key_id)

        # Old key should be marked as rotated
        assert old_key.rotated is True

        # New key should have same properties
        assert new_key.identity_id == old_key.identity_id
        assert new_key.key_type == old_key.key_type
        assert new_key.algorithm == old_key.algorithm

        # But different key ID
        assert new_key.key_id != old_key.key_id

    def test_check_rotation_needed(self):
        """Test checking which keys need rotation."""
        manager = KeyManager(rotation_threshold=timedelta(minutes=5))

        # Create key that expires soon
        key = manager.generate_key(
            identity_id="user-005",
            key_type="signing"
        )

        # Manually set expiry to be soon
        key.expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)

        keys_to_rotate = manager.check_rotation_needed()

        assert key.key_id in keys_to_rotate

    def test_auto_rotate_keys(self):
        """Test automatic key rotation."""
        manager = KeyManager(rotation_threshold=timedelta(minutes=5))

        # Create key that expires soon
        key = manager.generate_key(
            identity_id="user-006",
            key_type="signing"
        )

        # Manually set expiry to be soon
        key.expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)

        rotated = manager.auto_rotate_keys()

        assert len(rotated) > 0


class TestPacketSigner:
    """Test PacketSigner."""

    def test_sign_execution_packet(self):
        """Test signing execution packet."""
        manager = KeyManager()
        signer = PacketSigner(manager)

        packet_data = b"execution packet data"

        signature = signer.sign_execution_packet(
            packet_id="pkt-001",
            packet_data=packet_data,
            authority_band=AuthorityBand.MEDIUM,
            target_adapter="adapter-001",
            time_window_minutes=5
        )

        assert signature.packet_id == "pkt-001"
        assert signature.authority_band == AuthorityBand.MEDIUM
        assert signature.target_adapter == "adapter-001"
        assert signature.is_valid() is True

    def test_verify_packet_signature(self):
        """Test verifying packet signature."""
        manager = KeyManager()
        signer = PacketSigner(manager)

        packet_data = b"execution packet data"

        # Sign packet
        signature = signer.sign_execution_packet(
            packet_id="pkt-002",
            packet_data=packet_data,
            authority_band=AuthorityBand.HIGH,
            target_adapter="adapter-002"
        )

        # Verify signature
        result = signer.verify_packet_signature(signature, packet_data)

        assert result.valid is True
        assert result.error_message is None

    def test_verify_expired_packet(self):
        """Test verifying expired packet."""
        manager = KeyManager()
        signer = PacketSigner(manager)

        packet_data = b"execution packet data"

        # Sign packet
        signature = signer.sign_execution_packet(
            packet_id="pkt-003",
            packet_data=packet_data,
            authority_band=AuthorityBand.MEDIUM,
            target_adapter="adapter-003",
            time_window_minutes=0  # Expires immediately
        )

        # Wait a moment
        time.sleep(0.1)

        # Verify signature (should fail due to expiry)
        result = signer.verify_packet_signature(signature, packet_data)

        assert result.valid is False
        assert "expired" in result.error_message.lower()

    def test_single_use_enforcement(self):
        """Test single-use enforcement."""
        manager = KeyManager()
        signer = PacketSigner(manager)

        packet_data = b"execution packet data"

        # Sign packet
        signature = signer.sign_execution_packet(
            packet_id="pkt-004",
            packet_data=packet_data,
            authority_band=AuthorityBand.MEDIUM,
            target_adapter="adapter-004"
        )

        # First verification should succeed
        result1 = signer.verify_packet_signature(signature, packet_data)
        assert result1.valid is True

        # Mark as used
        signature.mark_used()

        # Second verification should fail
        result2 = signer.verify_packet_signature(signature, packet_data)
        assert result2.valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
