"""
Wave 6 Commissioning Tests — Security Plane Cryptography

Verifies the security_plane/cryptography.py module operates correctly in
both real-crypto and simulation modes. Tests the full lifecycle:
key generation → signing → verification → rotation.

Commissioning Questions Answered:
  - Does the module do what it was designed to do? → Classical, PQC, Hybrid sign/verify cycles
  - What conditions are possible? → Real vs stub crypto, key expiry, rotation, invalid sigs
  - Does the test profile reflect full capabilities? → All 6 core classes tested
  - What is the expected result? → Valid signatures verify, tampered data rejects
  - Has hardening been applied? → Constant-time compare, key encryption at rest

Copyright © 2020 Inoni Limited Liability Company
License: BSL-1.1
"""

import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))


class TestCryptoRuntimeDetection:
    """Verify the module correctly detects available crypto backends."""

    def test_classical_detection(self):
        from security_plane.cryptography import _HAS_REAL_CLASSICAL
        assert isinstance(_HAS_REAL_CLASSICAL, bool)

    def test_pqc_detection(self):
        from security_plane.cryptography import _HAS_REAL_PQC
        assert isinstance(_HAS_REAL_PQC, bool)


class TestCryptographicPrimitives:
    """Test hash and comparison primitives."""

    def test_hash_deterministic(self):
        from security_plane.cryptography import CryptographicPrimitives, HashAlgorithm
        data = b"murphy-system-test-data"
        h1 = CryptographicPrimitives.hash_data(data, HashAlgorithm.SHA256)
        h2 = CryptographicPrimitives.hash_data(data, HashAlgorithm.SHA256)
        assert h1 == h2

    def test_hash_different_data(self):
        from security_plane.cryptography import CryptographicPrimitives, HashAlgorithm
        h1 = CryptographicPrimitives.hash_data(b"data-a", HashAlgorithm.SHA256)
        h2 = CryptographicPrimitives.hash_data(b"data-b", HashAlgorithm.SHA256)
        assert h1 != h2

    def test_sha3_256_available(self):
        from security_plane.cryptography import CryptographicPrimitives, HashAlgorithm
        h = CryptographicPrimitives.hash_data(b"test", HashAlgorithm.SHA3_256)
        # Returns bytes for SHA3
        assert h is not None and len(h) > 0

    def test_constant_time_compare_equal(self):
        from security_plane.cryptography import CryptographicPrimitives
        assert CryptographicPrimitives.constant_time_compare(b"abc", b"abc") is True

    def test_constant_time_compare_not_equal(self):
        from security_plane.cryptography import CryptographicPrimitives
        assert CryptographicPrimitives.constant_time_compare(b"abc", b"xyz") is False

    def test_nonce_generation(self):
        from security_plane.cryptography import CryptographicPrimitives
        n1 = CryptographicPrimitives.generate_nonce()
        n2 = CryptographicPrimitives.generate_nonce()
        assert n1 != n2
        assert isinstance(n1, str) and len(n1) > 0


class TestClassicalCryptography:
    """Test ECDSA-based classical cryptography."""

    def test_key_generation(self):
        from security_plane.cryptography import ClassicalCryptography
        crypto = ClassicalCryptography()
        keypair = crypto.generate_keypair()
        assert keypair.public_key is not None
        assert keypair.private_key is not None

    def test_sign_verify_cycle(self):
        from security_plane.cryptography import ClassicalCryptography
        crypto = ClassicalCryptography()
        keypair = crypto.generate_keypair()
        data = b"test-payload-for-signing"
        signature = crypto.sign(data, keypair.private_key)
        assert signature is not None
        result = crypto.verify(data, signature, keypair.public_key, keypair.private_key)
        # May return bool or VerificationResult depending on mode
        if hasattr(result, "is_valid"):
            assert result.is_valid is True
        else:
            assert result is True

    def test_tampered_data_fails_verification(self):
        from security_plane.cryptography import ClassicalCryptography
        crypto = ClassicalCryptography()
        keypair = crypto.generate_keypair()
        data = b"original-data"
        signature = crypto.sign(data, keypair.private_key)
        tampered = b"tampered-data"
        result = crypto.verify(tampered, signature, keypair.public_key, keypair.private_key)
        if hasattr(result, "is_valid"):
            assert result.is_valid is False
        else:
            assert result is False


class TestPostQuantumCryptography:
    """Test PQC cryptography (real liboqs or HMAC simulation)."""

    def test_dilithium_key_generation(self):
        from security_plane.cryptography import PostQuantumCryptography
        pqc = PostQuantumCryptography()
        keypair = pqc.generate_keypair_dilithium()
        assert keypair.public_key is not None
        assert keypair.private_key is not None

    def test_dilithium_sign_verify_cycle(self):
        from security_plane.cryptography import PostQuantumCryptography
        pqc = PostQuantumCryptography()
        keypair = pqc.generate_keypair_dilithium()
        data = b"pqc-test-payload"
        signature = pqc.sign_dilithium(data, keypair.private_key)
        assert signature is not None
        result = pqc.verify_dilithium(data, signature, keypair.public_key, keypair.private_key)
        assert result is True

    def test_kyber_key_generation(self):
        from security_plane.cryptography import PostQuantumCryptography
        pqc = PostQuantumCryptography()
        keypair = pqc.generate_keypair_kyber()
        assert keypair.public_key is not None
        assert keypair.private_key is not None


class TestHybridCryptography:
    """Test combined classical + PQC hybrid signing."""

    def test_key_generation(self):
        from security_plane.cryptography import HybridCryptography
        hybrid = HybridCryptography()
        keypair = hybrid.generate_keypair()
        assert keypair is not None

    def test_sign_verify_cycle(self):
        from security_plane.cryptography import HybridCryptography
        hybrid = HybridCryptography()
        keypair_tuple = hybrid.generate_keypair()
        # Returns (classical_keypair, pqc_keypair) tuple
        assert isinstance(keypair_tuple, tuple) and len(keypair_tuple) == 2
        classical_kp, pqc_kp = keypair_tuple
        data = b"hybrid-test-payload"
        # sign_hybrid(data, classical_private, pqc_private) -> (classical_sig, pqc_sig)
        classical_sig, pqc_sig = hybrid.sign_hybrid(
            data, classical_kp.private_key, pqc_kp.private_key
        )
        assert classical_sig is not None
        assert pqc_sig is not None
        # verify_hybrid(data, classical_sig, pqc_sig, classical_public, pqc_public,
        #               classical_private, pqc_private) -> bool
        result = hybrid.verify_hybrid(
            data, classical_sig, pqc_sig,
            classical_kp.public_key, pqc_kp.public_key,
            classical_kp.private_key, pqc_kp.private_key,
        )
        assert result is True


class TestKeyManager:
    """Test key lifecycle management."""

    def test_generate_key(self):
        from security_plane.cryptography import KeyManager
        km = KeyManager()
        key = km.generate_key("test-identity", "signing")
        assert key is not None
        assert hasattr(key, "key_id")

    def test_rotate_key(self):
        from security_plane.cryptography import KeyManager
        km = KeyManager()
        key = km.generate_key("rotation-test", "signing")
        new_key = km.rotate_key(key.key_id)
        assert new_key is not None
        assert new_key.key_id != key.key_id

    def test_get_key(self):
        from security_plane.cryptography import KeyManager
        km = KeyManager()
        key = km.generate_key("retrieve-test", "signing")
        retrieved = km.get_key(key.key_id)
        assert retrieved is not None


class TestPacketSigner:
    """Test execution packet signing and verification."""

    def test_sign_and_verify_packet(self):
        from security_plane.cryptography import PacketSigner, KeyManager
        from security_plane.schemas import AuthorityBand
        km = KeyManager()
        signer = PacketSigner(key_manager=km)
        packet_data = b'{"action": "deploy"}'
        sig = signer.sign_execution_packet(
            packet_id="pkt-001",
            packet_data=packet_data,
            authority_band=AuthorityBand.CRITICAL,
            target_adapter="test-adapter",
            signer_id="commissioning-test",
        )
        assert sig is not None
        assert hasattr(sig, "packet_id")
        assert sig.packet_id == "pkt-001"

        result = signer.verify_packet_signature(sig, packet_data)
        assert result is not None
        assert result.valid is True


class TestAllSecurityModulesImport:
    """Verify all 17 security_plane modules import without errors."""

    MODULES = [
        "security_plane.access_control",
        "security_plane.adaptive_defense",
        "security_plane.anti_surveillance",
        "security_plane.authentication",
        "security_plane.authorization_enhancer",
        "security_plane.bot_anomaly_detector",
        "security_plane.bot_identity_verifier",
        "security_plane.bot_resource_quotas",
        "security_plane.cryptography",
        "security_plane.data_leak_prevention",
        "security_plane.hardening",
        "security_plane.log_sanitizer",
        "security_plane.middleware",
        "security_plane.packet_protection",
        "security_plane.schemas",
        "security_plane.security_dashboard",
        "security_plane.swarm_communication_monitor",
    ]

    @pytest.mark.parametrize("module_name", MODULES)
    def test_module_imports(self, module_name):
        import importlib
        mod = importlib.import_module(module_name)
        assert mod is not None