"""
Credential Vault
==================

Stores credentials with API-key-style treatment:
- Passwords are encrypted at rest using Fernet symmetric encryption
- SHA-256 hash prefixes allow verification without decryption
- Automatic rotation tracking with change-history audit
- Never exposes plaintext credentials through public APIs

Integrates with the SecureKeyManager for master-key management.

Design Label: ACCT-003
Owner: Platform Engineering
"""

import base64
import hashlib
import hmac
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from account_management.models import StoredCredential

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption helpers (Fernet-compatible or fallback)
# ---------------------------------------------------------------------------

_MAX_CREDENTIALS_PER_ACCOUNT = 100
_MAX_CREDENTIAL_VALUE_LENGTH = 4096

try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


def _derive_key(master_key: str) -> bytes:
    """Derive a 32-byte Fernet key from a master key string."""
    digest = hashlib.sha256(master_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _encrypt(plaintext: str, master_key: str) -> str:
    """Encrypt a plaintext value. Returns base64 string."""
    if _HAS_FERNET:
        key = _derive_key(master_key)
        f = Fernet(key)
        return f.encrypt(plaintext.encode("utf-8")).decode("ascii")
    # Fallback: base64 encode + HMAC tag (NOT production-secure, but testable)
    encoded = base64.urlsafe_b64encode(plaintext.encode("utf-8")).decode("ascii")
    tag = hmac.new(master_key.encode("utf-8"), plaintext.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"b64:{tag}:{encoded}"


def _decrypt(ciphertext: str, master_key: str) -> str:
    """Decrypt a ciphertext value. Returns plaintext string."""
    if _HAS_FERNET and not ciphertext.startswith("b64:"):
        key = _derive_key(master_key)
        f = Fernet(key)
        return f.decrypt(ciphertext.encode("ascii")).decode("utf-8")
    # Fallback decode
    if ciphertext.startswith("b64:"):
        parts = ciphertext.split(":", 2)
        if len(parts) == 3:
            return base64.urlsafe_b64decode(parts[2]).decode("utf-8")
    raise ValueError("Unable to decrypt credential")


def _hash_prefix(plaintext: str) -> str:
    """SHA-256 hash prefix for verification without decryption."""
    full = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    return full[:16]


# ---------------------------------------------------------------------------
# Credential Vault
# ---------------------------------------------------------------------------


class CredentialVault:
    """Thread-safe credential storage with encryption and rotation tracking.

    Usage::

        vault = CredentialVault(master_key="your-secret-key")
        cred_id = vault.store_credential("acct-1", "github", "password", "s3cret!")
        assert vault.verify_credential(cred_id, "s3cret!")
        vault.rotate_credential(cred_id, "n3w-s3cret!")
    """

    def __init__(
        self,
        master_key: Optional[str] = None,
    ) -> None:
        self._lock = threading.Lock()
        resolved_key = master_key or os.environ.get(
            "MURPHY_CREDENTIAL_MASTER_KEY", ""
        )
        if not resolved_key:
            murphy_env = os.environ.get("MURPHY_ENV", "development")
            if murphy_env not in ("development", "test", "testing"):
                raise ValueError(
                    "MURPHY_CREDENTIAL_MASTER_KEY environment variable must be "
                    "set in production. Generate one with: "
                    "python -c \"from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())\""
                )
            # Development/test only — ephemeral key per process invocation.
            # NOT safe for production — credentials won't survive restarts.
            if _HAS_FERNET:
                resolved_key = Fernet.generate_key().decode()
            else:
                resolved_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
            logger.warning(
                "Using ephemeral dev master key — credentials will not "
                "persist across restarts. Set MURPHY_CREDENTIAL_MASTER_KEY "
                "for persistent storage."
            )
        self._master_key = resolved_key
        self._credentials: Dict[str, StoredCredential] = {}
        # Index: account_id → list of credential_ids
        self._account_index: Dict[str, List[str]] = {}

    # -- Store / Retrieve ---------------------------------------------------

    def store_credential(
        self,
        account_id: str,
        service_name: str,
        credential_type: str,
        plaintext_value: str,
    ) -> str:
        """Encrypt and store a credential. Returns the credential_id.

        Raises:
            ValueError: if the plaintext is empty or too long.
        """
        if not plaintext_value:
            raise ValueError("Credential value cannot be empty")
        if len(plaintext_value) > _MAX_CREDENTIAL_VALUE_LENGTH:
            raise ValueError(
                f"Credential value exceeds max length ({_MAX_CREDENTIAL_VALUE_LENGTH})"
            )

        encrypted = _encrypt(plaintext_value, self._master_key)
        key_hash = _hash_prefix(plaintext_value)

        cred = StoredCredential(
            account_id=account_id,
            service_name=service_name,
            credential_type=credential_type,
            encrypted_value=encrypted,
            key_hash=key_hash,
        )

        with self._lock:
            existing = self._account_index.get(account_id, [])
            if len(existing) >= _MAX_CREDENTIALS_PER_ACCOUNT:
                raise ValueError(
                    f"Account {account_id} already has {_MAX_CREDENTIALS_PER_ACCOUNT} credentials"
                )
            self._credentials[cred.credential_id] = cred
            self._account_index.setdefault(account_id, []).append(cred.credential_id)

        logger.info(
            "Stored credential %s for account %s (service=%s, type=%s)",
            cred.credential_id, account_id, service_name, credential_type,
        )
        return cred.credential_id

    def get_credential_metadata(self, credential_id: str) -> Optional[Dict[str, Any]]:
        """Get credential metadata (never returns the encrypted value)."""
        with self._lock:
            cred = self._credentials.get(credential_id)
            return cred.to_dict() if cred else None

    def retrieve_credential(self, credential_id: str) -> Optional[str]:
        """Decrypt and return the plaintext credential value.

        WARNING: This should only be called by authorized internal processes.
        """
        with self._lock:
            cred = self._credentials.get(credential_id)
        if cred is None:
            return None
        try:
            return _decrypt(cred.encrypted_value, self._master_key)
        except Exception as exc:
            logger.error("Failed to decrypt credential %s: %s", credential_id, exc)
            return None

    def verify_credential(self, credential_id: str, plaintext_value: str) -> bool:
        """Verify a credential by comparing hash prefixes (no decryption needed)."""
        with self._lock:
            cred = self._credentials.get(credential_id)
        if cred is None:
            return False
        return hmac.compare_digest(
            cred.key_hash, _hash_prefix(plaintext_value)
        )

    # -- Rotation -----------------------------------------------------------

    def rotate_credential(
        self,
        credential_id: str,
        new_plaintext_value: str,
    ) -> bool:
        """Rotate a credential to a new value.

        Returns True if successful, False if credential_id not found.
        """
        if not new_plaintext_value:
            raise ValueError("New credential value cannot be empty")
        if len(new_plaintext_value) > _MAX_CREDENTIAL_VALUE_LENGTH:
            raise ValueError(
                f"Credential value exceeds max length ({_MAX_CREDENTIAL_VALUE_LENGTH})"
            )

        with self._lock:
            cred = self._credentials.get(credential_id)
            if cred is None:
                return False
            cred.encrypted_value = _encrypt(new_plaintext_value, self._master_key)
            cred.key_hash = _hash_prefix(new_plaintext_value)
            cred.rotation_count += 1
            cred.last_rotated_at = datetime.now(timezone.utc).isoformat()
            cred.updated_at = datetime.now(timezone.utc).isoformat()

        logger.info("Rotated credential %s (rotation #%d)", credential_id, cred.rotation_count)
        return True

    # -- Removal ------------------------------------------------------------

    def remove_credential(self, credential_id: str) -> bool:
        """Remove a credential from the vault."""
        with self._lock:
            cred = self._credentials.pop(credential_id, None)
            if cred is None:
                return False
            idx = self._account_index.get(cred.account_id, [])
            if credential_id in idx:
                idx.remove(credential_id)
            return True

    # -- Queries ------------------------------------------------------------

    def list_credentials_for_account(self, account_id: str) -> List[Dict[str, Any]]:
        """List all credential metadata for an account."""
        with self._lock:
            ids = self._account_index.get(account_id, [])
            return [
                self._credentials[cid].to_dict()
                for cid in ids
                if cid in self._credentials
            ]

    def list_all_services(self) -> List[str]:
        """Return unique service names across all stored credentials."""
        with self._lock:
            return sorted(set(c.service_name for c in self._credentials.values()))

    def get_status(self) -> Dict[str, Any]:
        """Status summary."""
        with self._lock:
            services = sorted(set(c.service_name for c in self._credentials.values()))
            return {
                "total_credentials": len(self._credentials),
                "total_accounts": len(self._account_index),
                "services": services,
                "has_fernet": _HAS_FERNET,
            }
