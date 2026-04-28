"""
Cryptographic Foundation for Security Plane

Implements post-quantum cryptography with hybrid classical+PQC mode.

SECURITY NOTE — LIBRARY-BACKED CRYPTOGRAPHY (SEC-003)
=====================================================
When the ``cryptography`` Python library (>= 42) is installed this module
delegates classical key-pair generation and signing to real ECDSA (P-256)
operations via ``cryptography.hazmat.primitives``.

Post-quantum primitives (Kyber / Dilithium) are proxied through ``liboqs``
when available.  When neither library is present the module falls back to
the original HMAC-SHA-based **simulation stubs** — these are structurally
correct but do NOT provide real post-quantum security and MUST NOT be used
in a production deployment.

Runtime detection:
    ``_HAS_REAL_CLASSICAL``  — True when ``cryptography`` >= 42 is available
    ``_HAS_REAL_PQC``        — True when ``liboqs`` is available

CRITICAL SECURITY REQUIREMENTS:
1. All cryptography must support hybrid classical + PQC today
2. Full PQC tomorrow
3. No long-lived secrets
4. Automatic key rotation
5. Forward secrecy everywhere

Primitives:
- Kyber (key exchange) - NIST PQC standard
- Dilithium / Falcon (signatures) - NIST PQC standard
- SHA-3 / BLAKE3 (hashing)
- AES-256-GCM (symmetric encryption)

Key Rotation:
- Automatic
- Frequent (minutes)
- Invisible to users
"""

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Optional, Tuple

logger = logging.getLogger("security_plane.cryptography")

from .schemas import AuthorityBand, CryptographicAlgorithm, CryptographicKey, ExecutionPacketSignature

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SEC-003: Runtime library detection
# ---------------------------------------------------------------------------
_HAS_REAL_CLASSICAL = False
_HAS_REAL_PQC = False
_HAS_FERNET = False

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
        encode_dss_signature,
    )
    _HAS_REAL_CLASSICAL = True
    _HAS_FERNET = True
    _log.info("SEC-003: Real classical crypto available (cryptography library)")
except ImportError:
    _log.warning("SEC-003: cryptography library not available — using HMAC simulation for classical crypto")

try:
    import oqs  # liboqs-python
    _HAS_REAL_PQC = True
    _log.info("SEC-003: Real PQC available (liboqs)")
except ImportError:
    _log.info("SEC-003: liboqs not available — using HMAC simulation for PQC (expected in VM)")  # PATCH-110d


class HashAlgorithm(Enum):
    """Hash algorithm type."""
    SHA256 = "sha256"
    SHA3_256 = "sha3_256"
    BLAKE3 = "blake3"


@dataclass
class KeyPair:
    """
    Cryptographic key pair.

    CRITICAL: Keys are short-lived (minutes).
    """
    public_key: bytes
    private_key: bytes
    algorithm: CryptographicAlgorithm
    created_at: datetime
    expires_at: datetime
    key_id: str

    def is_expired(self) -> bool:
        """Check if key pair has expired."""
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class SignatureResult:
    """Result of a signature operation."""
    signature: bytes
    algorithm: CryptographicAlgorithm
    signed_at: datetime
    public_key: bytes
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of a signature verification."""
    valid: bool
    algorithm: CryptographicAlgorithm
    verified_at: datetime
    public_key: bytes
    error_message: Optional[str] = None


class CryptographicPrimitives:
    """
    Low-level cryptographic primitives.

    This is a simplified implementation for demonstration.
    In production, use proper PQC libraries like liboqs, pqcrypto, etc.
    """

    @staticmethod
    def hash_data(data: bytes, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> bytes:
        """
        Hash data using specified algorithm.

        Default: SHA-256 (will migrate to SHA-3 or BLAKE3)
        """
        if algorithm == HashAlgorithm.SHA256:
            return hashlib.sha256(data).digest()
        elif algorithm == HashAlgorithm.SHA3_256:
            return hashlib.sha3_256(data).digest()
        elif algorithm == HashAlgorithm.BLAKE3:
            # BLAKE3 not in standard library, fallback to SHA-256
            # In production: import blake3; return blake3.blake3(data).digest()
            return hashlib.sha256(data).digest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    @staticmethod
    def generate_nonce(length: int = 32) -> str:
        """Generate cryptographically secure nonce."""
        return secrets.token_hex(length)

    @staticmethod
    def constant_time_compare(a: bytes, b: bytes) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        return hmac.compare_digest(a, b)

    @staticmethod
    def derive_key(master_key: bytes, context: bytes, length: int = 32) -> bytes:
        """
        Derive key from master key using HKDF-like construction.

        In production: Use proper HKDF from cryptography library.
        """
        return hashlib.pbkdf2_hmac('sha256', master_key, context, 100000, dklen=length)


class ClassicalCryptography:
    """
    Classical cryptography (ECDSA P-256 when ``cryptography`` is available,
    HMAC-SHA256 simulation otherwise).
    """

    @staticmethod
    def generate_keypair(key_size: int = 2048) -> KeyPair:
        """Generate classical key pair.

        Uses real ECDSA P-256 when the ``cryptography`` library is
        installed; falls back to HMAC-based simulation otherwise.
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=10)  # Short-lived

        if _HAS_REAL_CLASSICAL:
            _priv = ec.generate_private_key(ec.SECP256R1())
            priv_bytes = _priv.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            pub_bytes = _priv.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            return KeyPair(
                public_key=pub_bytes,
                private_key=priv_bytes,
                algorithm=CryptographicAlgorithm.CLASSICAL,
                created_at=now,
                expires_at=expires,
                key_id=f"ecdsa-{secrets.token_hex(8)}",
            )

        # --- Simulation fallback ---
        private_key = secrets.token_bytes(key_size // 8)
        public_key = hashlib.sha256(private_key).digest()
        return KeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=CryptographicAlgorithm.CLASSICAL,
            created_at=now,
            expires_at=expires,
            key_id=f"classical-{secrets.token_hex(8)}",
        )

    @staticmethod
    def sign(data: bytes, private_key: bytes) -> bytes:
        """Sign *data* with *private_key*.

        Uses real ECDSA when available, HMAC-SHA256 simulation otherwise.
        """
        if _HAS_REAL_CLASSICAL:
            try:
                _priv = serialization.load_der_private_key(private_key, password=None)
                return _priv.sign(data, ec.ECDSA(hashes.SHA256()))
            except Exception as exc:
                _log.debug("Suppressed exception: %s", exc)
                pass  # fall through to simulation
        return hmac.new(private_key, data, hashlib.sha256).digest()

    @staticmethod
    def verify(data: bytes, signature: bytes, public_key: bytes, private_key: bytes) -> bool:
        """Verify *signature* over *data*.

        Uses real ECDSA when available, HMAC-SHA256 simulation otherwise.
        The *private_key* argument is only used in simulation mode.
        """
        if _HAS_REAL_CLASSICAL:
            try:
                _pub = serialization.load_der_public_key(public_key)
                _pub.verify(signature, data, ec.ECDSA(hashes.SHA256()))
                return True
            except Exception as exc:
                _log.debug("Suppressed exception: %s", exc)
                return False
        expected_signature = hmac.new(private_key, data, hashlib.sha256).digest()
        return CryptographicPrimitives.constant_time_compare(signature, expected_signature)


class PostQuantumCryptography:
    """
    Post-quantum cryptography (Kyber, Dilithium, Falcon).

    Uses ``liboqs`` when available (``_HAS_REAL_PQC``); falls back to
    HMAC-SHA3-based simulation otherwise.
    """

    @staticmethod
    def generate_keypair_kyber() -> KeyPair:
        """Generate Kyber key pair for key exchange."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=10)

        if _HAS_REAL_PQC:
            kem = oqs.KeyEncapsulation("Kyber512")
            pub = kem.generate_keypair()
            priv = kem.export_secret_key()
            return KeyPair(
                public_key=pub,
                private_key=priv,
                algorithm=CryptographicAlgorithm.POST_QUANTUM,
                created_at=now,
                expires_at=expires,
                key_id=f"kyber-{secrets.token_hex(8)}",
            )

        # --- Simulation fallback ---
        private_key = secrets.token_bytes(128)
        public_key = hashlib.sha3_256(private_key).digest()
        return KeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=CryptographicAlgorithm.POST_QUANTUM,
            created_at=now,
            expires_at=expires,
            key_id=f"kyber-{secrets.token_hex(8)}",
        )

    @staticmethod
    def generate_keypair_dilithium() -> KeyPair:
        """Generate Dilithium key pair for signatures."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=10)

        if _HAS_REAL_PQC:
            sig = oqs.Signature("Dilithium2")
            pub = sig.generate_keypair()
            priv = sig.export_secret_key()
            return KeyPair(
                public_key=pub,
                private_key=priv,
                algorithm=CryptographicAlgorithm.POST_QUANTUM,
                created_at=now,
                expires_at=expires,
                key_id=f"dilithium-{secrets.token_hex(8)}",
            )

        # --- Simulation fallback ---
        private_key = secrets.token_bytes(256)
        public_key = hashlib.sha3_256(private_key).digest()
        return KeyPair(
            public_key=public_key,
            private_key=private_key,
            algorithm=CryptographicAlgorithm.POST_QUANTUM,
            created_at=now,
            expires_at=expires,
            key_id=f"dilithium-{secrets.token_hex(8)}",
        )

    @staticmethod
    def sign_dilithium(data: bytes, private_key: bytes) -> bytes:
        """Sign *data* with Dilithium.

        Uses real liboqs Dilithium2 when available, HMAC-SHA3 simulation
        otherwise.
        """
        if _HAS_REAL_PQC:
            try:
                sig = oqs.Signature("Dilithium2", private_key)
                return sig.sign(data)
            except Exception as exc:
                _log.debug("Suppressed exception: %s", exc)
                pass
        return hmac.new(private_key, data, hashlib.sha3_256).digest()

    @staticmethod
    def verify_dilithium(data: bytes, signature: bytes, public_key: bytes, private_key: bytes) -> bool:
        """Verify Dilithium *signature* over *data*.

        Uses real liboqs when available, HMAC-SHA3 simulation otherwise.
        The *private_key* argument is only used in simulation mode.
        """
        if _HAS_REAL_PQC:
            try:
                verifier = oqs.Signature("Dilithium2")
                return verifier.verify(data, signature, public_key)
            except Exception as exc:
                _log.debug("Suppressed exception: %s", exc)
                return False
        expected_signature = hmac.new(private_key, data, hashlib.sha3_256).digest()
        return CryptographicPrimitives.constant_time_compare(signature, expected_signature)


class HybridCryptography:
    """
    Hybrid classical + post-quantum cryptography.

    CRITICAL: This is the default mode for production.
    Provides security against both classical and quantum attacks.
    """

    @staticmethod
    def generate_keypair() -> Tuple[KeyPair, KeyPair]:
        """
        Generate hybrid key pair (classical + PQC).

        Returns (classical_keypair, pqc_keypair)
        """
        classical = ClassicalCryptography.generate_keypair()
        pqc = PostQuantumCryptography.generate_keypair_dilithium()

        return classical, pqc

    @staticmethod
    def sign_hybrid(data: bytes, classical_private: bytes, pqc_private: bytes) -> Tuple[bytes, bytes]:
        """
        Sign data with both classical and PQC algorithms.

        Returns (classical_signature, pqc_signature)
        """
        classical_sig = ClassicalCryptography.sign(data, classical_private)
        pqc_sig = PostQuantumCryptography.sign_dilithium(data, pqc_private)

        return classical_sig, pqc_sig

    @staticmethod
    def verify_hybrid(
        data: bytes,
        classical_sig: bytes,
        pqc_sig: bytes,
        classical_public: bytes,
        pqc_public: bytes,
        classical_private: bytes,
        pqc_private: bytes
    ) -> bool:
        """
        Verify hybrid signature.

        BOTH signatures must be valid.
        """
        classical_valid = ClassicalCryptography.verify(
            data, classical_sig, classical_public, classical_private
        )
        pqc_valid = PostQuantumCryptography.verify_dilithium(
            data, pqc_sig, pqc_public, pqc_private
        )

        return classical_valid and pqc_valid


class KeyManager:
    """
    Manages cryptographic keys with automatic rotation.

    CRITICAL FEATURES:
    1. Short-lived keys (minutes)
    2. Automatic rotation
    3. Capability-scoped
    4. Encrypted at rest
    """

    def __init__(self, rotation_threshold: timedelta = timedelta(minutes=5)):
        self.rotation_threshold = rotation_threshold
        self._keys: Dict[str, CryptographicKey] = {}
        self._keypairs: Dict[str, Tuple[KeyPair, Optional[KeyPair]]] = {}  # (classical, pqc)

    def generate_key(
        self,
        identity_id: str,
        key_type: str,
        algorithm: CryptographicAlgorithm = CryptographicAlgorithm.HYBRID,
        capabilities: set = None
    ) -> CryptographicKey:
        """
        Generate new cryptographic key.

        Default: Hybrid classical + PQC
        """
        if capabilities is None:
            capabilities = {"sign", "verify"}

        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=10)

        if algorithm == CryptographicAlgorithm.HYBRID:
            classical_kp, pqc_kp = HybridCryptography.generate_keypair()
            keypairs = (classical_kp, pqc_kp)
            public_key = classical_kp.public_key + pqc_kp.public_key
            private_key = classical_kp.private_key + pqc_kp.private_key
        elif algorithm == CryptographicAlgorithm.POST_QUANTUM:
            pqc_kp = PostQuantumCryptography.generate_keypair_dilithium()
            keypairs = (pqc_kp, None)
            public_key = pqc_kp.public_key
            private_key = pqc_kp.private_key
        else:  # CLASSICAL
            classical_kp = ClassicalCryptography.generate_keypair()
            keypairs = (classical_kp, None)
            public_key = classical_kp.public_key
            private_key = classical_kp.private_key

        key_id = f"key-{secrets.token_hex(16)}"

        # Encrypt private key using Fernet (MURPHY_CREDENTIAL_MASTER_KEY env var)
        private_key_encrypted = self._encrypt_private_key(private_key)

        key = CryptographicKey(
            key_id=key_id,
            key_type=key_type,
            algorithm=algorithm,
            public_key=public_key,
            private_key_encrypted=private_key_encrypted,
            created_at=now,
            expires_at=expires,
            identity_id=identity_id,
            capabilities=capabilities
        )

        self._keys[key_id] = key
        self._keypairs[key_id] = keypairs

        return key

    @staticmethod
    def _get_fernet() -> "Optional[Fernet]":
        """
        Load or derive the Fernet instance used for private-key encryption.

        Reads ``MURPHY_CREDENTIAL_MASTER_KEY`` from the environment.  The key
        must be a URL-safe base-64 encoded 32-byte value as produced by
        ``Fernet.generate_key()``.

        Returns None when the ``cryptography`` library is unavailable so that
        callers can fall back to the legacy stub behaviour.

        Raises ``RuntimeError`` in production/staging when the env var is not
        set, to prevent silent data loss.
        """
        if not _HAS_FERNET:
            return None
        import base64
        import os as _os
        raw = _os.environ.get("MURPHY_CREDENTIAL_MASTER_KEY", "")
        if raw:
            try:
                fernet_key = raw.encode() if isinstance(raw, str) else raw
                return Fernet(fernet_key)
            except Exception as exc:
                _log.error("MURPHY_CREDENTIAL_MASTER_KEY is set but invalid: %s", exc)
                raise RuntimeError(
                    "MURPHY_CREDENTIAL_MASTER_KEY is set but is not a valid Fernet key. "
                    "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                ) from exc
        # No key configured — derive a per-process ephemeral key and warn
        murphy_env = _os.environ.get("MURPHY_ENV", "development")
        if murphy_env not in ("development", "test"):
            raise RuntimeError(
                "MURPHY_CREDENTIAL_MASTER_KEY must be set in production/staging. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _log.warning(
            "MURPHY_CREDENTIAL_MASTER_KEY not set — using ephemeral per-process key. "
            "Private keys will not survive process restart. Set the env var for production."
        )
        # Generate and cache an ephemeral key for this process lifetime
        if not hasattr(KeyManager, "_ephemeral_fernet"):
            KeyManager._ephemeral_fernet = Fernet(Fernet.generate_key())  # type: ignore[attr-defined]
        return KeyManager._ephemeral_fernet  # type: ignore[attr-defined]

    def _encrypt_private_key(self, private_key: bytes) -> bytes:
        """
        Encrypt private key at rest using Fernet symmetric encryption.

        Uses ``MURPHY_CREDENTIAL_MASTER_KEY`` env var.  Falls back to an
        ephemeral per-process key in development/test with a warning.
        """
        fernet = self._get_fernet()
        if fernet is not None:
            return fernet.encrypt(private_key)
        # cryptography library not available — store as-is with a warning
        _log.warning(
            "cryptography library not available — private key stored unencrypted. "
            "Install 'cryptography' for proper at-rest encryption."
        )
        return private_key

    def _decrypt_private_key(self, encrypted_key: bytes) -> bytes:
        """
        Decrypt a Fernet-encrypted private key.

        Returns the plaintext key bytes.
        """
        fernet = self._get_fernet()
        if fernet is not None:
            try:
                return fernet.decrypt(encrypted_key)
            except Exception as exc:
                _log.error("Failed to decrypt private key: %s", exc)
                raise ValueError("Private key decryption failed — check MURPHY_CREDENTIAL_MASTER_KEY") from exc
        # cryptography library not available — key was stored unencrypted
        return encrypted_key

    def get_key(self, key_id: str) -> Optional[CryptographicKey]:
        """Get key by ID."""
        return self._keys.get(key_id)

    def get_keypairs(self, key_id: str) -> Tuple[Optional[KeyPair], Optional[KeyPair]]:
        """Return the ``(classical_kp, pqc_kp)`` tuple for *key_id*."""
        return self._keypairs.get(key_id, (None, None))

    def rotate_key(self, key_id: str) -> CryptographicKey:
        """
        Rotate key (generate new key with same properties).

        Old key is marked as rotated.
        """
        old_key = self._keys.get(key_id)
        if not old_key:
            raise ValueError(f"Key {key_id} not found")

        # Mark old key as rotated
        old_key.rotated = True
        old_key.rotation_scheduled_at = datetime.now(timezone.utc)

        # Generate new key
        new_key = self.generate_key(
            identity_id=old_key.identity_id,
            key_type=old_key.key_type,
            algorithm=old_key.algorithm,
            capabilities=old_key.capabilities
        )

        return new_key

    def check_rotation_needed(self) -> list[str]:
        """
        Check which keys need rotation.

        Returns list of key IDs that should be rotated.
        """
        keys_to_rotate = []

        for key_id, key in self._keys.items():
            if key.should_rotate(self.rotation_threshold):
                keys_to_rotate.append(key_id)

        return keys_to_rotate

    def auto_rotate_keys(self) -> list[str]:
        """
        Automatically rotate keys that need rotation.

        Returns list of rotated key IDs.
        """
        keys_to_rotate = self.check_rotation_needed()
        rotated = []

        for key_id in keys_to_rotate:
            try:
                self.rotate_key(key_id)
                rotated.append(key_id)
            except Exception as exc:
                # Log error but continue rotating other keys
                logger.info(f"Error rotating key {key_id}: {exc}")

        return rotated


class PacketSigner:
    """
    Signs execution packets with Control Plane authority.

    CRITICAL: Only Control Plane can sign execution packets.
    """

    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager

    def sign_execution_packet(
        self,
        packet_id: str,
        packet_data: bytes,
        authority_band: AuthorityBand,
        target_adapter: str,
        time_window_minutes: int = 5,
        signer_id: str = "control-plane"
    ) -> ExecutionPacketSignature:
        """
        Sign execution packet.

        CRITICAL: This creates a cryptographically sealed, single-use,
        time-bound execution packet.
        """
        # Get or generate signing key
        signing_key = self._get_or_create_signing_key(signer_id)

        # Generate unique nonce for replay prevention
        nonce = CryptographicPrimitives.generate_nonce()

        # Create signature payload
        now = datetime.now(timezone.utc)
        time_window_start = now
        time_window_end = now + timedelta(minutes=time_window_minutes)

        payload = (
            f"{packet_id}{packet_data.hex()}{authority_band.value}"
            f"{target_adapter}{time_window_start.isoformat()}"
            f"{time_window_end.isoformat()}{nonce}"
        ).encode()

        # Sign with hybrid cryptography
        keypairs = self.key_manager._keypairs.get(signing_key.key_id)
        if not keypairs:
            raise ValueError(f"Keypairs not found for key {signing_key.key_id}")

        classical_kp, pqc_kp = keypairs

        if signing_key.algorithm == CryptographicAlgorithm.HYBRID and pqc_kp:
            classical_sig, pqc_sig = HybridCryptography.sign_hybrid(
                payload,
                classical_kp.private_key,
                pqc_kp.private_key
            )
            # Prefix with 4-byte little-endian classical sig length so verify
            # can split at the correct position regardless of ECDSA DER length.
            signature = len(classical_sig).to_bytes(4, 'little') + classical_sig + pqc_sig
        elif signing_key.algorithm == CryptographicAlgorithm.POST_QUANTUM:
            signature = PostQuantumCryptography.sign_dilithium(
                payload,
                classical_kp.private_key
            )
        else:  # CLASSICAL
            signature = ClassicalCryptography.sign(
                payload,
                classical_kp.private_key
            )

        return ExecutionPacketSignature(
            packet_id=packet_id,
            signature=signature,
            algorithm=signing_key.algorithm,
            signed_at=now,
            signed_by=signer_id,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
            authority_band=authority_band,
            target_adapter=target_adapter,
            nonce=nonce
        )

    def _get_or_create_signing_key(self, signer_id: str) -> CryptographicKey:
        """Get or create signing key for signer."""
        # Look for existing valid key
        for key in self.key_manager._keys.values():
            if (key.identity_id == signer_id and
                key.key_type == "signing" and
                not key.is_expired() and
                not key.rotated):
                return key

        # Create new key
        return self.key_manager.generate_key(
            identity_id=signer_id,
            key_type="signing",
            algorithm=CryptographicAlgorithm.HYBRID,
            capabilities={"sign"}
        )

    def verify_packet_signature(
        self,
        packet_signature: ExecutionPacketSignature,
        packet_data: bytes
    ) -> VerificationResult:
        """
        Verify execution packet signature.

        Checks:
        1. Signature validity
        2. Time window
        3. Single-use enforcement
        """
        # Check time window
        if not packet_signature.is_valid():
            return VerificationResult(
                valid=False,
                algorithm=packet_signature.algorithm,
                verified_at=datetime.now(timezone.utc),
                public_key=b"",
                error_message="Packet signature expired or already used"
            )

        # Get signing key
        signing_key = None
        for key in self.key_manager._keys.values():
            if key.identity_id == packet_signature.signed_by and key.key_type == "signing":
                signing_key = key
                break

        if not signing_key:
            return VerificationResult(
                valid=False,
                algorithm=packet_signature.algorithm,
                verified_at=datetime.now(timezone.utc),
                public_key=b"",
                error_message="Signing key not found"
            )

        # Reconstruct payload
        payload = (
            f"{packet_signature.packet_id}{packet_data.hex()}{packet_signature.authority_band.value}"
            f"{packet_signature.target_adapter}{packet_signature.time_window_start.isoformat()}"
            f"{packet_signature.time_window_end.isoformat()}{packet_signature.nonce}"
        ).encode()

        # Verify signature
        keypairs = self.key_manager._keypairs.get(signing_key.key_id)
        if not keypairs:
            return VerificationResult(
                valid=False,
                algorithm=packet_signature.algorithm,
                verified_at=datetime.now(timezone.utc),
                public_key=signing_key.public_key,
                error_message="Keypairs not found"
            )

        classical_kp, pqc_kp = keypairs

        try:
            if packet_signature.algorithm == CryptographicAlgorithm.HYBRID and pqc_kp:
                # Decode 4-byte prefix that encodes the classical sig length.
                raw = packet_signature.signature
                if len(raw) < 4:
                    raise ValueError("Hybrid signature too short to contain length prefix")
                classical_sig_len = int.from_bytes(raw[:4], 'little')
                classical_sig = raw[4:4 + classical_sig_len]
                pqc_sig = raw[4 + classical_sig_len:]

                valid = HybridCryptography.verify_hybrid(
                    payload,
                    classical_sig,
                    pqc_sig,
                    classical_kp.public_key,
                    pqc_kp.public_key,
                    classical_kp.private_key,
                    pqc_kp.private_key
                )
            elif packet_signature.algorithm == CryptographicAlgorithm.POST_QUANTUM:
                valid = PostQuantumCryptography.verify_dilithium(
                    payload,
                    packet_signature.signature,
                    classical_kp.public_key,
                    classical_kp.private_key
                )
            else:  # CLASSICAL
                valid = ClassicalCryptography.verify(
                    payload,
                    packet_signature.signature,
                    classical_kp.public_key,
                    classical_kp.private_key
                )

            return VerificationResult(
                valid=valid,
                algorithm=packet_signature.algorithm,
                verified_at=datetime.now(timezone.utc),
                public_key=signing_key.public_key,
                error_message=None if valid else "Signature verification failed"
            )

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return VerificationResult(
                valid=False,
                algorithm=packet_signature.algorithm,
                verified_at=datetime.now(timezone.utc),
                public_key=signing_key.public_key,
                error_message=f"Verification error: {str(exc)}"
            )
