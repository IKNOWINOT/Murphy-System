"""Utilities for signing and encrypting messages."""
from __future__ import annotations

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def sign_message(private_key: Ed25519PrivateKey, message: bytes) -> bytes:
    """Return a signature for the given message."""
    return private_key.sign(message)


def verify_signature(public_key: Ed25519PublicKey, message: bytes, signature: bytes) -> bool:
    """Verify a signature and return ``True`` if valid."""
    try:
        public_key.verify(signature, message)
        return True
    except Exception:
        return False


def encrypt_payload(key: bytes, data: bytes) -> bytes:
    """Encrypt bytes using ``Fernet``."""
    return Fernet(key).encrypt(data)


def decrypt_payload(key: bytes, token: bytes) -> bytes:
    """Decrypt bytes using ``Fernet``."""
    return Fernet(key).decrypt(token)
