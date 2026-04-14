# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_pqc — Post-Quantum Cryptography library for MurphyOS.

Provides:
  • ML-KEM-1024  (Kyber)     — key encapsulation
  • ML-DSA-87    (Dilithium) — digital signatures
  • SLH-DSA-SHA2-256f (SPHINCS+) — hash-based signatures
  • Hybrid classical + PQC mode (X25519 / Ed25519)
  • AES-256-GCM symmetric encryption with PQC-derived keys
  • HKDF-SHA3-256 key derivation
  • SHAKE-256 quantum-resistant session tokens
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import struct
from typing import Optional, Tuple

logger = logging.getLogger("murphy.pqc")

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------
# MURPHY-PQC-ERR-001  liboqs-python unavailable (PQC fallback stubs active)
# MURPHY-PQC-ERR-002  nacl (PyNaCl) unavailable — hybrid mode disabled
# MURPHY-PQC-ERR-003  cryptography library unavailable — AES-GCM fallback
# MURPHY-PQC-ERR-010  ML-KEM-1024 key generation failed
# MURPHY-PQC-ERR-011  ML-KEM-1024 encapsulation failed
# MURPHY-PQC-ERR-012  ML-KEM-1024 decapsulation failed
# MURPHY-PQC-ERR-020  ML-DSA-87 key generation failed
# MURPHY-PQC-ERR-021  ML-DSA-87 signing failed
# MURPHY-PQC-ERR-022  ML-DSA-87 verification failed
# MURPHY-PQC-ERR-030  SLH-DSA key generation failed
# MURPHY-PQC-ERR-031  SLH-DSA signing failed
# MURPHY-PQC-ERR-032  SLH-DSA verification failed
# MURPHY-PQC-ERR-040  Hybrid key exchange failed
# MURPHY-PQC-ERR-041  Hybrid classical signature verification failed
# MURPHY-PQC-ERR-050  AES-256-GCM symmetric encryption/decryption error
# MURPHY-PQC-ERR-060  HKDF-SHA3-256 key derivation failed
# MURPHY-PQC-ERR-070  Session token generation failed
# ---------------------------------------------------------------------------

_ERR_OQS_UNAVAILABLE    = "MURPHY-PQC-ERR-001"
_ERR_NACL_UNAVAILABLE   = "MURPHY-PQC-ERR-002"
_ERR_CRYPTO_UNAVAILABLE = "MURPHY-PQC-ERR-003"
_ERR_KEM_KEYGEN_FAIL    = "MURPHY-PQC-ERR-010"
_ERR_KEM_ENCAPS_FAIL    = "MURPHY-PQC-ERR-011"
_ERR_KEM_DECAPS_FAIL    = "MURPHY-PQC-ERR-012"
_ERR_SIG_KEYGEN_FAIL    = "MURPHY-PQC-ERR-020"
_ERR_SIG_SIGN_FAIL      = "MURPHY-PQC-ERR-021"
_ERR_SIG_VERIFY_FAIL    = "MURPHY-PQC-ERR-022"
_ERR_HASH_SIG_KEYGEN    = "MURPHY-PQC-ERR-030"
_ERR_HASH_SIG_SIGN      = "MURPHY-PQC-ERR-031"
_ERR_HASH_SIG_VERIFY    = "MURPHY-PQC-ERR-032"
_ERR_HYBRID_FAIL        = "MURPHY-PQC-ERR-040"
_ERR_HYBRID_VERIFY_FAIL = "MURPHY-PQC-ERR-041"
_ERR_SYMMETRIC_FAIL     = "MURPHY-PQC-ERR-050"
_ERR_KDF_FAIL           = "MURPHY-PQC-ERR-060"
_ERR_TOKEN_FAIL         = "MURPHY-PQC-ERR-070"

# ---------------------------------------------------------------------------
# Backend detection — prefer liboqs-python, fall back to pure-hashlib stubs
# ---------------------------------------------------------------------------

_HAS_OQS = False
_HAS_NACL = False

try:
    import oqs  # type: ignore[import-untyped]
    _HAS_OQS = True
except ImportError:
    logger.warning(
        "%s: liboqs-python not found — PQC operations will use "
        "fallback stubs (NOT quantum-safe)", _ERR_OQS_UNAVAILABLE,
    )

try:
    from nacl.public import PrivateKey as NaClPrivateKey  # type: ignore[import-untyped]
    from nacl.signing import SigningKey as NaClSigningKey  # type: ignore[import-untyped]
    from nacl.bindings import (  # type: ignore[import-untyped]
        crypto_scalarmult,
    )
    _HAS_NACL = True
except ImportError:  # MURPHY-PQC-ERR-002
    logger.debug("%s: nacl not found — hybrid mode unavailable", _ERR_NACL_UNAVAILABLE)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore[import-untyped]
    _HAS_CRYPTOGRAPHY = True
except ImportError:  # MURPHY-PQC-ERR-003
    logger.debug("%s: cryptography library not found — AES-GCM will use fallback", _ERR_CRYPTO_UNAVAILABLE)
    _HAS_CRYPTOGRAPHY = False

# ---------------------------------------------------------------------------
# ML-KEM-1024 (Kyber) — Key Encapsulation
# ---------------------------------------------------------------------------

_KEM_ALGO = "ML-KEM-1024"


class PQCError(Exception):
    """Base exception for all PQC operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def generate_kem_keypair() -> Tuple[bytes, bytes]:
    """Generate an ML-KEM-1024 keypair.

    Returns:
        (public_key, secret_key)
    """
    if _HAS_OQS:
        try:
            with oqs.KeyEncapsulation(_KEM_ALGO) as kem:
                pk = kem.generate_keypair()
                sk = kem.export_secret_key()
                return (bytes(pk), bytes(sk))
        except Exception as exc:
            raise PQCError(_ERR_KEM_KEYGEN_FAIL, str(exc)) from exc

    # Fallback: generate random bytes mimicking key sizes
    logger.warning("Using fallback KEM keygen — NOT quantum-safe")
    pk = secrets.token_bytes(1568)
    sk = secrets.token_bytes(3168)
    return (pk, sk)


def encapsulate(public_key: bytes) -> Tuple[bytes, bytes]:
    """Encapsulate a shared secret against *public_key*.

    Returns:
        (ciphertext, shared_secret)
    """
    if _HAS_OQS:
        try:
            with oqs.KeyEncapsulation(_KEM_ALGO) as kem:
                ct, ss = kem.encap_secret(public_key)
                return (bytes(ct), bytes(ss))
        except Exception as exc:
            raise PQCError(_ERR_KEM_ENCAPS_FAIL, str(exc)) from exc

    logger.warning("Using fallback encapsulate — NOT quantum-safe")
    ss = secrets.token_bytes(32)
    ct = hashlib.sha3_256(public_key + ss).digest() + ss
    return (ct, ss)


def decapsulate(secret_key: bytes, ciphertext: bytes) -> bytes:
    """Decapsulate *ciphertext* using *secret_key*.

    Returns:
        shared_secret
    """
    if _HAS_OQS:
        try:
            with oqs.KeyEncapsulation(_KEM_ALGO, secret_key) as kem:
                ss = kem.decap_secret(ciphertext)
                return bytes(ss)
        except Exception as exc:
            raise PQCError(_ERR_KEM_DECAPS_FAIL, str(exc)) from exc

    logger.warning("Using fallback decapsulate — NOT quantum-safe")
    return ciphertext[32:]

# ---------------------------------------------------------------------------
# ML-DSA-87 (Dilithium5) — Digital Signatures
# ---------------------------------------------------------------------------

_SIG_ALGO = "ML-DSA-87"


def generate_sig_keypair() -> Tuple[bytes, bytes]:
    """Generate an ML-DSA-87 signing keypair.

    Returns:
        (public_key, secret_key)
    """
    if _HAS_OQS:
        try:
            with oqs.Signature(_SIG_ALGO) as sig:
                pk = sig.generate_keypair()
                sk = sig.export_secret_key()
                return (bytes(pk), bytes(sk))
        except Exception as exc:
            raise PQCError(_ERR_SIG_KEYGEN_FAIL, str(exc)) from exc

    logger.warning("Using fallback sig keygen — NOT quantum-safe")
    sk = secrets.token_bytes(64)
    pk = hashlib.sha3_256(sk).digest()
    return (pk, sk)


def sign(secret_key: bytes, message: bytes) -> bytes:
    """Sign *message* with ML-DSA-87 *secret_key*."""
    if _HAS_OQS:
        try:
            with oqs.Signature(_SIG_ALGO, secret_key) as sig:
                return bytes(sig.sign(message))
        except Exception as exc:
            raise PQCError(_ERR_SIG_SIGN_FAIL, str(exc)) from exc

    logger.warning("Using fallback sign — NOT quantum-safe")
    return hmac.new(secret_key, message, hashlib.sha3_256).digest()


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an ML-DSA-87 *signature* over *message*."""
    if _HAS_OQS:
        try:
            with oqs.Signature(_SIG_ALGO) as sig:
                return sig.verify(message, signature, public_key)
        except Exception as exc:
            logger.error("%s: %s", _ERR_SIG_VERIFY_FAIL, exc)
            return False

    logger.warning("Using fallback verify — NOT quantum-safe")
    expected = hmac.new(public_key[:64], message, hashlib.sha3_256).digest()
    return hmac.compare_digest(expected, signature)

# ---------------------------------------------------------------------------
# SLH-DSA-SHA2-256f (SPHINCS+) — Hash-Based Signatures
# ---------------------------------------------------------------------------

_HASH_SIG_ALGO = "SLH-DSA-SHA2-256f"


def generate_hash_sig_keypair() -> Tuple[bytes, bytes]:
    """Generate an SLH-DSA-SHA2-256f keypair for long-term / boot signing."""
    if _HAS_OQS:
        try:
            with oqs.Signature(_HASH_SIG_ALGO) as sig:
                pk = sig.generate_keypair()
                sk = sig.export_secret_key()
                return (bytes(pk), bytes(sk))
        except Exception as exc:
            raise PQCError(_ERR_HASH_SIG_KEYGEN, str(exc)) from exc

    logger.warning("Using fallback hash-sig keygen — NOT quantum-safe")
    sk = secrets.token_bytes(128)
    pk = hashlib.sha3_256(sk).digest()
    return (pk, sk)


def hash_sign(secret_key: bytes, message: bytes) -> bytes:
    """Sign *message* with SLH-DSA-SHA2-256f."""
    if _HAS_OQS:
        try:
            with oqs.Signature(_HASH_SIG_ALGO, secret_key) as sig:
                return bytes(sig.sign(message))
        except Exception as exc:
            raise PQCError(_ERR_HASH_SIG_SIGN, str(exc)) from exc

    logger.warning("Using fallback hash_sign — NOT quantum-safe")
    return hmac.new(secret_key[:64], message, hashlib.sha3_256).digest()


def hash_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an SLH-DSA-SHA2-256f *signature* over *message*."""
    if _HAS_OQS:
        try:
            with oqs.Signature(_HASH_SIG_ALGO) as sig:
                return sig.verify(message, signature, public_key)
        except Exception as exc:
            logger.error("%s: %s", _ERR_HASH_SIG_VERIFY, exc)
            return False

    logger.warning("Using fallback hash_verify — NOT quantum-safe")
    expected = hmac.new(public_key[:64], message, hashlib.sha3_256).digest()
    return hmac.compare_digest(expected, signature)

# ---------------------------------------------------------------------------
# Hybrid mode — Classical (X25519 + Ed25519) combined with PQC
# ---------------------------------------------------------------------------


class HybridKeyPair:
    """Container for a classical + PQC keypair bundle."""

    def __init__(
        self,
        classical_pk: bytes,
        classical_sk: bytes,
        pqc_kem_pk: bytes,
        pqc_kem_sk: bytes,
        classical_sig_pk: bytes,
        classical_sig_sk: bytes,
        pqc_sig_pk: bytes,
        pqc_sig_sk: bytes,
    ) -> None:
        self.classical_pk = classical_pk
        self.classical_sk = classical_sk
        self.pqc_kem_pk = pqc_kem_pk
        self.pqc_kem_sk = pqc_kem_sk
        self.classical_sig_pk = classical_sig_pk
        self.classical_sig_sk = classical_sig_sk
        self.pqc_sig_pk = pqc_sig_pk
        self.pqc_sig_sk = pqc_sig_sk


def generate_hybrid_keypair() -> HybridKeyPair:
    """Generate a full hybrid (classical + PQC) keypair bundle."""
    pqc_kem_pk, pqc_kem_sk = generate_kem_keypair()
    pqc_sig_pk, pqc_sig_sk = generate_sig_keypair()

    if _HAS_NACL:
        x_sk = NaClPrivateKey.generate()
        x_pk = x_sk.public_key
        ed_sk = NaClSigningKey.generate()
        ed_pk = ed_sk.verify_key
        return HybridKeyPair(
            classical_pk=bytes(x_pk),
            classical_sk=bytes(x_sk),
            pqc_kem_pk=pqc_kem_pk,
            pqc_kem_sk=pqc_kem_sk,
            classical_sig_pk=bytes(ed_pk),
            classical_sig_sk=bytes(ed_sk),
            pqc_sig_pk=pqc_sig_pk,
            pqc_sig_sk=pqc_sig_sk,
        )

    # Fallback without nacl
    classical_sk = secrets.token_bytes(32)
    classical_pk = hashlib.sha3_256(classical_sk).digest()
    sig_sk = secrets.token_bytes(64)
    sig_pk = hashlib.sha3_256(sig_sk).digest()
    return HybridKeyPair(
        classical_pk=classical_pk,
        classical_sk=classical_sk,
        pqc_kem_pk=pqc_kem_pk,
        pqc_kem_sk=pqc_kem_sk,
        classical_sig_pk=sig_pk,
        classical_sig_sk=sig_sk,
        pqc_sig_pk=pqc_sig_pk,
        pqc_sig_sk=pqc_sig_sk,
    )


def hybrid_key_exchange(
    our_keypair: HybridKeyPair,
    peer_classical_pk: bytes,
    peer_pqc_pk: bytes,
) -> bytes:
    """Perform a hybrid key exchange combining X25519 + ML-KEM-1024.

    The two shared secrets are concatenated and fed through HKDF-SHA3-256
    to produce a single 32-byte key.
    """
    try:
        # PQC component
        pqc_ct, pqc_ss = encapsulate(peer_pqc_pk)

        # Classical component
        if _HAS_NACL:
            classical_ss = crypto_scalarmult(
                our_keypair.classical_sk, peer_classical_pk,
            )
        else:
            classical_ss = hashlib.sha3_256(
                our_keypair.classical_sk + peer_classical_pk,
            ).digest()

        return hkdf_sha3_256(
            classical_ss + pqc_ss,
            info=b"murphy-hybrid-kex",
            length=32,
        )
    except Exception as exc:
        raise PQCError(_ERR_HYBRID_FAIL, str(exc)) from exc


class HybridSignature:
    """Container for a classical + PQC signature pair."""

    def __init__(self, classical_sig: bytes, pqc_sig: bytes) -> None:
        self.classical_sig = classical_sig
        self.pqc_sig = pqc_sig

    def to_bytes(self) -> bytes:
        return (
            struct.pack("!H", len(self.classical_sig))
            + self.classical_sig
            + self.pqc_sig
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "HybridSignature":
        (clen,) = struct.unpack("!H", data[:2])
        classical_sig = data[2 : 2 + clen]
        pqc_sig = data[2 + clen :]
        return cls(classical_sig=classical_sig, pqc_sig=pqc_sig)


def hybrid_sign(keypair: HybridKeyPair, message: bytes) -> HybridSignature:
    """Sign *message* with both Ed25519 and ML-DSA-87."""
    pqc_sig = sign(keypair.pqc_sig_sk, message)

    if _HAS_NACL:
        ed_key = NaClSigningKey(keypair.classical_sig_sk)
        classical_sig = bytes(ed_key.sign(message).signature)
    else:
        classical_sig = hmac.new(
            keypair.classical_sig_sk, message, hashlib.sha3_256,
        ).digest()

    return HybridSignature(classical_sig=classical_sig, pqc_sig=pqc_sig)


def hybrid_verify(
    classical_sig_pk: bytes,
    pqc_sig_pk: bytes,
    message: bytes,
    sig: HybridSignature,
) -> bool:
    """Verify a hybrid signature — both components must pass."""
    pqc_ok = verify(pqc_sig_pk, message, sig.pqc_sig)

    if _HAS_NACL:
        from nacl.signing import VerifyKey as NaClVerifyKey  # type: ignore[import-untyped]
        try:
            NaClVerifyKey(classical_sig_pk).verify(message, sig.classical_sig)
            classical_ok = True
        except Exception as exc:  # MURPHY-PQC-ERR-041
            logger.debug("%s: classical signature verification failed: %s", _ERR_HYBRID_VERIFY_FAIL, exc)
            classical_ok = False
    else:
        expected = hmac.new(
            classical_sig_pk[:64], message, hashlib.sha3_256,
        ).digest()
        classical_ok = hmac.compare_digest(expected, sig.classical_sig)

    return classical_ok and pqc_ok

# ---------------------------------------------------------------------------
# Symmetric encryption — AES-256-GCM with PQC-derived keys
# ---------------------------------------------------------------------------

_AES_NONCE_SIZE = 12  # 96-bit nonce for GCM


def aes256gcm_encrypt(key: bytes, plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
    """Encrypt *plaintext* with AES-256-GCM.

    Returns nonce ‖ ciphertext ‖ tag.
    """
    if len(key) != 32:
        raise PQCError(_ERR_SYMMETRIC_FAIL, "key must be 32 bytes")

    nonce = os.urandom(_AES_NONCE_SIZE)

    if _HAS_CRYPTOGRAPHY:
        ct = AESGCM(key).encrypt(nonce, plaintext, aad)
        return nonce + ct

    # Pure-Python fallback using XOR (NOT production-safe — placeholder)
    logger.warning("Using XOR fallback for AES-256-GCM — NOT secure")
    stream = hashlib.sha3_256(key + nonce).digest() * ((len(plaintext) // 32) + 1)
    ct = bytes(a ^ b for a, b in zip(plaintext, stream[: len(plaintext)]))
    tag = hashlib.sha3_256(key + nonce + ct + (aad or b"")).digest()[:16]
    return nonce + ct + tag


def aes256gcm_decrypt(key: bytes, ciphertext_blob: bytes, aad: Optional[bytes] = None) -> bytes:
    """Decrypt an AES-256-GCM blob produced by :func:`aes256gcm_encrypt`."""
    if len(key) != 32:
        raise PQCError(_ERR_SYMMETRIC_FAIL, "key must be 32 bytes")
    if len(ciphertext_blob) < _AES_NONCE_SIZE + 16:
        raise PQCError(_ERR_SYMMETRIC_FAIL, "ciphertext too short")

    nonce = ciphertext_blob[:_AES_NONCE_SIZE]
    ct_and_tag = ciphertext_blob[_AES_NONCE_SIZE:]

    if _HAS_CRYPTOGRAPHY:
        return AESGCM(key).decrypt(nonce, ct_and_tag, aad)

    logger.warning("Using XOR fallback for AES-256-GCM decrypt — NOT secure")
    ct = ct_and_tag[:-16]
    tag = ct_and_tag[-16:]
    expected_tag = hashlib.sha3_256(key + nonce + ct + (aad or b"")).digest()[:16]
    if not hmac.compare_digest(tag, expected_tag):
        raise PQCError(_ERR_SYMMETRIC_FAIL, "GCM tag mismatch")
    stream = hashlib.sha3_256(key + nonce).digest() * ((len(ct) // 32) + 1)
    return bytes(a ^ b for a, b in zip(ct, stream[: len(ct)]))

# ---------------------------------------------------------------------------
# Key derivation — HKDF-SHA3-256
# ---------------------------------------------------------------------------


def hkdf_sha3_256(
    ikm: bytes,
    salt: Optional[bytes] = None,
    info: bytes = b"",
    length: int = 32,
) -> bytes:
    """HKDF Extract-then-Expand using SHA3-256.

    Implements RFC 5869 logic with SHA3-256 as the underlying hash.
    """
    try:
        hash_len = 32  # SHA3-256 output

        # Extract
        if salt is None:
            salt = b"\x00" * hash_len
        prk = hmac.new(salt, ikm, hashlib.sha3_256).digest()

        # Expand
        t = b""
        okm = b""
        for i in range(1, (length + hash_len - 1) // hash_len + 1):
            t = hmac.new(prk, t + info + bytes([i]), hashlib.sha3_256).digest()
            okm += t

        return okm[:length]
    except Exception as exc:
        raise PQCError(_ERR_KDF_FAIL, str(exc)) from exc

# ---------------------------------------------------------------------------
# Session tokens — SHAKE-256 (512-bit)
# ---------------------------------------------------------------------------


def generate_session_token(context: bytes = b"murphy-session") -> bytes:
    """Generate a 512-bit (64-byte) quantum-resistant session token.

    Uses SHAKE-256 seeded with 64 bytes of OS entropy and optional
    *context* label.
    """
    try:
        entropy = os.urandom(64)
        shake = hashlib.shake_256(entropy + context)
        return shake.digest(64)
    except Exception as exc:
        raise PQCError(_ERR_TOKEN_FAIL, str(exc)) from exc


def verify_session_token(token: bytes) -> bool:
    """Basic structural validation of a session token."""
    return isinstance(token, bytes) and len(token) == 64
