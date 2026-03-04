"""
Tests for Security Plane - Execution Packet Protection
======================================================

Tests cryptographic signature verification, replay prevention, and integrity validation.
"""

import pytest
from datetime import datetime, timezone, timedelta
import secrets
from src.security_plane.packet_protection import (
    PacketStatus,
    VerificationResult,
    AuthorityLevel,
    ExecutionPacket,
    PacketSignature,
    VerificationRecord,
    PacketSigner,
    ReplayPrevention,
    AuthorityEnforcer,
    IntegrityValidator,
    PacketProtectionSystem,
    PacketProtectionStatistics
)


class TestExecutionPacket:
    """Test execution packet model"""

    def test_packet_creation(self):
        """Test creating execution packet"""
        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test123",
            principal_id="user1",
            action="read_data",
            parameters={"resource": "/api/data"},
            authority_level=AuthorityLevel.MEDIUM,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce123"
        )

        assert packet.packet_id == "test123"
        assert packet.principal_id == "user1"
        assert packet.status == PacketStatus.PENDING

    def test_packet_validation(self):
        """Test packet validation on creation"""
        now = datetime.now(timezone.utc)

        # Missing packet_id
        with pytest.raises(ValueError):
            ExecutionPacket(
                packet_id="",
                principal_id="user1",
                action="test",
                parameters={},
                authority_level=AuthorityLevel.LOW,
                created_at=now,
                expires_at=now + timedelta(minutes=5),
                nonce="nonce"
            )

        # Expires before created
        with pytest.raises(ValueError):
            ExecutionPacket(
                packet_id="test",
                principal_id="user1",
                action="test",
                parameters={},
                authority_level=AuthorityLevel.LOW,
                created_at=now,
                expires_at=now - timedelta(minutes=5),
                nonce="nonce"
            )

    def test_packet_expiration(self):
        """Test packet expiration check"""
        now = datetime.now(timezone.utc)

        # Not expired
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )
        assert not packet.is_expired()

        # Expired
        expired_packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.LOW,
            created_at=now - timedelta(minutes=10),
            expires_at=now - timedelta(minutes=5),
            nonce="nonce"
        )
        assert expired_packet.is_expired()

    def test_packet_integrity_hash(self):
        """Test packet integrity hash computation"""
        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={"key": "value"},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        hash1 = packet.compute_integrity_hash()
        hash2 = packet.compute_integrity_hash()

        # Same packet should produce same hash
        assert hash1 == hash2

        # Modified packet should produce different hash
        packet.parameters["key"] = "different"
        hash3 = packet.compute_integrity_hash()
        assert hash1 != hash3


class TestPacketSigner:
    """Test packet signing"""

    def test_sign_packet(self):
        """Test signing a packet"""
        signing_key = secrets.token_bytes(32)
        signer = PacketSigner(signing_key)

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        signature = signer.sign_packet(packet, "signer1")

        assert packet.signature is not None
        assert signature.packet_id == packet.packet_id
        assert signature.algorithm == "HMAC-SHA256"

    def test_verify_signature(self):
        """Test verifying packet signature"""
        signing_key = secrets.token_bytes(32)
        signer = PacketSigner(signing_key)

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        # Sign packet
        signer.sign_packet(packet, "signer1")

        # Verify signature
        assert signer.verify_signature(packet) is True

    def test_verify_tampered_packet(self):
        """Test verifying tampered packet"""
        signing_key = secrets.token_bytes(32)
        signer = PacketSigner(signing_key)

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={"key": "value"},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        # Sign packet
        signer.sign_packet(packet, "signer1")

        # Tamper with packet
        packet.parameters["key"] = "tampered"

        # Verification should fail
        assert signer.verify_signature(packet) is False


class TestReplayPrevention:
    """Test replay attack prevention"""

    def test_check_fresh_nonce(self):
        """Test checking fresh nonce"""
        rp = ReplayPrevention()

        nonce = "test_nonce_123"
        assert rp.check_nonce(nonce) is True

    def test_check_used_nonce(self):
        """Test checking used nonce"""
        rp = ReplayPrevention()

        nonce = "test_nonce_123"
        rp.mark_nonce_used(nonce)

        assert rp.check_nonce(nonce) is False

    def test_generate_nonce(self):
        """Test nonce generation"""
        rp = ReplayPrevention()

        nonce1 = rp.generate_nonce()
        nonce2 = rp.generate_nonce()

        # Nonces should be unique
        assert nonce1 != nonce2
        assert len(nonce1) == 64  # 32 bytes hex = 64 chars

    def test_cleanup_old_nonces(self):
        """Test cleanup of old nonces"""
        rp = ReplayPrevention(max_age=timedelta(seconds=1))

        nonce = "old_nonce"
        rp.mark_nonce_used(nonce)

        # Wait for nonce to age
        import time
        time.sleep(1.1)

        # Cleanup should remove old nonce
        rp._cleanup_old_nonces()

        # Nonce should be fresh again
        assert rp.check_nonce(nonce) is True


class TestAuthorityEnforcer:
    """Test authority enforcement"""

    def test_check_sufficient_authority(self):
        """Test checking sufficient authority"""
        enforcer = AuthorityEnforcer()

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="read_data",
            parameters={},
            authority_level=AuthorityLevel.HIGH,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        # HIGH authority is sufficient for MEDIUM requirement
        assert enforcer.check_authority(packet, AuthorityLevel.MEDIUM) is True

    def test_check_insufficient_authority(self):
        """Test checking insufficient authority"""
        enforcer = AuthorityEnforcer()

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="read_data",
            parameters={},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        # LOW authority is NOT sufficient for HIGH requirement
        assert enforcer.check_authority(packet, AuthorityLevel.HIGH) is False

    def test_custom_requirements(self):
        """Test custom authority requirements"""
        enforcer = AuthorityEnforcer()

        # Set custom requirement
        enforcer.set_requirement("special_action", AuthorityLevel.CRITICAL)

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="special_action",
            parameters={},
            authority_level=AuthorityLevel.HIGH,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        # HIGH is not sufficient for CRITICAL
        assert enforcer.check_authority(packet) is False


class TestIntegrityValidator:
    """Test integrity validation"""

    def test_store_and_verify_integrity(self):
        """Test storing and verifying integrity"""
        validator = IntegrityValidator()

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={"key": "value"},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        # Store integrity hash
        validator.store_hash(packet)

        # Verify integrity
        assert validator.verify_integrity(packet) is True

    def test_detect_tampering(self):
        """Test detecting packet tampering"""
        validator = IntegrityValidator()

        now = datetime.now(timezone.utc)
        packet = ExecutionPacket(
            packet_id="test",
            principal_id="user1",
            action="test",
            parameters={"key": "value"},
            authority_level=AuthorityLevel.LOW,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            nonce="nonce"
        )

        # Store integrity hash
        validator.store_hash(packet)

        # Tamper with packet
        packet.parameters["key"] = "tampered"

        # Verification should fail
        assert validator.verify_integrity(packet) is False


class TestPacketProtectionSystem:
    """Test complete packet protection system"""

    def test_create_packet(self):
        """Test creating packet"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        packet = system.create_packet(
            principal_id="user1",
            action="read_data",
            parameters={"resource": "/api/data"},
            authority_level=AuthorityLevel.MEDIUM
        )

        assert packet.packet_id is not None
        assert packet.nonce is not None
        assert packet.status == PacketStatus.PENDING

    def test_sign_and_verify_packet(self):
        """Test signing and verifying packet"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        # Create packet
        packet = system.create_packet(
            principal_id="user1",
            action="read_data",
            parameters={},
            authority_level=AuthorityLevel.MEDIUM
        )

        # Sign packet
        system.sign_packet(packet, "signer1")

        # Verify packet
        record = system.verify_packet(packet, "verifier1")

        assert record.result == VerificationResult.VALID
        assert packet.status == PacketStatus.VERIFIED

    def test_reject_expired_packet(self):
        """Test rejecting expired packet"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        # Create packet with very short TTL
        packet = system.create_packet(
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.LOW,
            ttl=timedelta(microseconds=1)  # Very short TTL
        )

        # Sign packet
        system.sign_packet(packet, "signer1")

        # Wait for expiration
        import time
        time.sleep(0.001)

        # Verify packet
        record = system.verify_packet(packet, "verifier1")

        assert record.result == VerificationResult.EXPIRED

    def test_reject_replayed_packet(self):
        """Test rejecting replayed packet"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        # Create packet with MEDIUM authority (default requirement for "test" action)
        packet = system.create_packet(
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.MEDIUM
        )

        # Sign packet
        system.sign_packet(packet, "signer1")

        # Verify packet (first time - should succeed)
        record1 = system.verify_packet(packet, "verifier1")
        assert record1.result == VerificationResult.VALID

        # Verify packet again (replay - should fail)
        record2 = system.verify_packet(packet, "verifier1")
        assert record2.result == VerificationResult.REPLAYED

    def test_reject_insufficient_authority(self):
        """Test rejecting packet with insufficient authority"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        # Create packet with LOW authority
        packet = system.create_packet(
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.LOW
        )

        # Sign packet
        system.sign_packet(packet, "signer1")

        # Verify packet with HIGH authority requirement
        record = system.verify_packet(
            packet,
            "verifier1",
            required_authority=AuthorityLevel.HIGH
        )

        assert record.result == VerificationResult.INSUFFICIENT_AUTHORITY

    def test_reject_tampered_packet(self):
        """Test rejecting tampered packet"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        # Create packet with MEDIUM authority
        packet = system.create_packet(
            principal_id="user1",
            action="test",
            parameters={"key": "value"},
            authority_level=AuthorityLevel.MEDIUM
        )

        # Sign packet
        system.sign_packet(packet, "signer1")

        # Tamper with packet
        packet.parameters["key"] = "tampered"

        # Verify packet
        record = system.verify_packet(packet, "verifier1")

        # Tampering causes signature verification to fail first
        assert record.result == VerificationResult.INVALID_SIGNATURE

    def test_reject_unsigned_packet(self):
        """Test rejecting unsigned packet"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        # Create packet (don't sign it)
        packet = system.create_packet(
            principal_id="user1",
            action="test",
            parameters={},
            authority_level=AuthorityLevel.LOW
        )

        # Verify packet
        record = system.verify_packet(packet, "verifier1")

        assert record.result == VerificationResult.MISSING_SIGNATURE

    def test_verification_history(self):
        """Test verification history tracking"""
        signing_key = secrets.token_bytes(32)
        system = PacketProtectionSystem(signing_key)

        # Create and verify multiple packets
        for i in range(3):
            packet = system.create_packet(
                principal_id=f"user{i}",
                action="test",
                parameters={},
                authority_level=AuthorityLevel.LOW
            )
            system.sign_packet(packet, "signer1")
            system.verify_packet(packet, "verifier1")

        # Check history
        history = system.get_verification_history()
        assert len(history) == 3


class TestPacketProtectionStatistics:
    """Test packet protection statistics"""

    def test_statistics_creation(self):
        """Test creating statistics"""
        stats = PacketProtectionStatistics(
            total_packets_created=100,
            successful_verifications=95,
            failed_verifications=5
        )

        assert stats.total_packets_created == 100
        assert stats.successful_verifications == 95

    def test_statistics_to_dict(self):
        """Test converting statistics to dict"""
        stats = PacketProtectionStatistics(total_packets_created=10)
        result = stats.to_dict()

        assert isinstance(result, dict)
        assert result["total_packets_created"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
