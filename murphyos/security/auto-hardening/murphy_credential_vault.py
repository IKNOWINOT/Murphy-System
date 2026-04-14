# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Automatic secret management — the ``CredentialVault``.

Stores credentials encrypted at rest using AES-256-GCM (keys from PQC
hierarchy or PBKDF2 + machine-id fallback).  Provides per-user access
control, breach detection, and automatic credential rotation.

Users never have to think about secret storage — the vault handles
everything transparently.

Error codes: MURPHY-AUTOSEC-ERR-046 .. MURPHY-AUTOSEC-ERR-060
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import platform
import secrets
import struct
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("murphy.autosec.credential_vault")

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore[import-untyped]

    _HAS_AESGCM = True
except ImportError:  # MURPHY-AUTOSEC-ERR-046
    _HAS_AESGCM = False
    logger.info(
        "MURPHY-AUTOSEC-ERR-046: 'cryptography' not installed; "
        "vault will use HMAC-sealed JSON fallback."
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VAULT_DIR = pathlib.Path("/var/lib/murphy/vault")
NONCE_LEN = 12
TAG_LEN = 16
KEY_LEN = 32
PBKDF2_ITERATIONS = 600_000
ROTATION_INTERVAL = 86400 * 90  # 90 days default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _machine_id() -> bytes:
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            return pathlib.Path(p).read_bytes().strip()
        except OSError:
            continue
    return platform.node().encode()


def _derive_key(passphrase: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase, salt, PBKDF2_ITERATIONS)


def _encrypt_blob(key: bytes, plaintext: bytes) -> bytes:
    """Return nonce‖tag‖ciphertext."""
    nonce = secrets.token_bytes(NONCE_LEN)
    if _HAS_AESGCM:
        aesgcm = AESGCM(key)
        ct_tag = aesgcm.encrypt(nonce, plaintext, None)
        ct = ct_tag[:-TAG_LEN]
        tag = ct_tag[-TAG_LEN:]
    else:
        # HMAC-sealed fallback (NOT real encryption — defence in depth only)
        tag = hashlib.sha256(key + nonce + plaintext).digest()[:TAG_LEN]
        ct = plaintext  # plaintext preserved (logged as degraded)
        logger.warning(
            "MURPHY-AUTOSEC-ERR-047: Encryption unavailable; storing "
            "HMAC-sealed plaintext."
        )
    return nonce + tag + ct


def _decrypt_blob(key: bytes, blob: bytes) -> bytes:
    """Reverse of ``_encrypt_blob``."""
    nonce = blob[:NONCE_LEN]
    tag = blob[NONCE_LEN : NONCE_LEN + TAG_LEN]
    ct = blob[NONCE_LEN + TAG_LEN :]
    if _HAS_AESGCM:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct + tag, None)
    # HMAC check for fallback mode
    expected = hashlib.sha256(key + nonce + ct).digest()[:TAG_LEN]
    if not secrets.compare_digest(tag, expected):
        raise ValueError("MURPHY-AUTOSEC-ERR-048: HMAC verification failed")
    return ct


# ---------------------------------------------------------------------------
# CredentialVault
# ---------------------------------------------------------------------------
class CredentialVault:
    """Automatic secret management vault.

    Parameters
    ----------
    vault_dir : pathlib.Path
        Directory where encrypted credential files are stored.
    pqc_key_provider : callable, optional
        Zero-arg callable returning a 32-byte key from PQC hierarchy.
    rotation_interval : int
        Seconds between automatic rotation reminders/actions.
    """

    def __init__(
        self,
        vault_dir: pathlib.Path = VAULT_DIR,
        pqc_key_provider: Optional[Callable[[], bytes]] = None,
        rotation_interval: int = ROTATION_INTERVAL,
    ) -> None:
        self._vault_dir = vault_dir
        self._pqc_key_provider = pqc_key_provider
        self._rotation_interval = rotation_interval
        self._salt = hashlib.sha256(b"murphy-vault-" + _machine_id()).digest()
        self._key: Optional[bytes] = None
        self._acl: Dict[str, Set[str]] = {}  # cred_name → {user, …}
        self._lock = threading.Lock()
        self._metadata: Dict[str, Dict[str, Any]] = {}
        logger.info("CredentialVault initialised (dir=%s).", vault_dir)

    # -- key management -----------------------------------------------------

    def _resolve_key(self) -> bytes:
        if self._key is not None:
            return self._key
        if callable(self._pqc_key_provider):
            try:
                k = self._pqc_key_provider()
                if isinstance(k, bytes) and len(k) == KEY_LEN:
                    self._key = k
                    return self._key
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-049
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-049: PQC key provider failed: %s", exc
                )
        self._key = _derive_key(_machine_id(), self._salt)
        return self._key

    # -- file paths ---------------------------------------------------------

    def _cred_path(self, name: str) -> pathlib.Path:
        safe = hashlib.sha256(name.encode()).hexdigest()
        return self._vault_dir / f"{safe}.vault"

    def _meta_path(self) -> pathlib.Path:
        return self._vault_dir / "vault_metadata.json"

    # -- persistence --------------------------------------------------------

    def _save_metadata(self) -> None:
        try:
            self._vault_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "acl": {k: sorted(v) for k, v in self._acl.items()},
                "metadata": self._metadata,
            }
            self._meta_path().write_text(json.dumps(payload, indent=2))
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-050
            logger.error("MURPHY-AUTOSEC-ERR-050: Metadata save failed: %s", exc)

    def _load_metadata(self) -> None:
        try:
            data = json.loads(self._meta_path().read_text())
            self._acl = {k: set(v) for k, v in data.get("acl", {}).items()}
            self._metadata = data.get("metadata", {})
        except FileNotFoundError:
            logger.debug("MURPHY-AUTOSEC-ERR-051: No vault metadata found.")
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-052
            logger.error("MURPHY-AUTOSEC-ERR-052: Metadata load error: %s", exc)

    # -- public API ---------------------------------------------------------

    def store_credential(
        self,
        name: str,
        value: str,
        owner: str = "system",
        allowed_users: Optional[List[str]] = None,
    ) -> bool:
        """Store a credential under *name*, encrypted at rest.

        Parameters
        ----------
        name : str
            Unique credential identifier.
        value : str
            The secret value.
        owner : str
            Owning user/service.
        allowed_users : list[str], optional
            Additional users with access.
        """
        with self._lock:
            try:
                key = self._resolve_key()
                blob = _encrypt_blob(key, value.encode("utf-8"))
                self._vault_dir.mkdir(parents=True, exist_ok=True)
                self._cred_path(name).write_bytes(blob)
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-053
                logger.error(
                    "MURPHY-AUTOSEC-ERR-053: Failed to store credential '%s': %s",
                    name,
                    exc,
                )
                return False

            users = {owner}
            if allowed_users:
                users.update(allowed_users)
            self._acl[name] = users
            self._metadata[name] = {
                "owner": owner,
                "stored_at": time.time(),
                "rotated_at": time.time(),
            }
            self._save_metadata()
        logger.info("Credential '%s' stored (owner=%s).", name, owner)
        return True

    def retrieve_credential(self, name: str, requester: str = "system") -> Optional[str]:
        """Retrieve and decrypt a stored credential.

        Returns *None* if the credential doesn't exist or access is denied.
        """
        with self._lock:
            if name in self._acl and requester not in self._acl[name]:
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-054: Access denied for '%s' → '%s'.",
                    requester,
                    name,
                )
                return None

            path = self._cred_path(name)
            if not path.exists():
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-055: Credential '%s' not found.", name
                )
                return None

            try:
                blob = path.read_bytes()
                key = self._resolve_key()
                plaintext = _decrypt_blob(key, blob)
                return plaintext.decode("utf-8")
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-056
                logger.error(
                    "MURPHY-AUTOSEC-ERR-056: Decryption failed for '%s': %s",
                    name,
                    exc,
                )
                return None

    def rotate_credential(
        self,
        name: str,
        new_value: str,
        requester: str = "system",
    ) -> bool:
        """Rotate (replace) an existing credential.

        The old value is overwritten — no history is kept.
        """
        with self._lock:
            if name in self._acl and requester not in self._acl[name]:
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-057: Rotation denied for '%s' → '%s'.",
                    requester,
                    name,
                )
                return False

        ok = self.store_credential(
            name,
            new_value,
            owner=self._metadata.get(name, {}).get("owner", "system"),
            allowed_users=list(self._acl.get(name, set())),
        )
        if ok:
            with self._lock:
                if name in self._metadata:
                    self._metadata[name]["rotated_at"] = time.time()
                self._save_metadata()
            logger.info("Credential '%s' rotated.", name)
        return ok

    # -- breach detection ---------------------------------------------------

    def check_breach_indicators(self) -> List[str]:
        """Scan for credentials that are overdue for rotation.

        Returns a list of credential names that should be rotated.
        """
        with self._lock:
            overdue: List[str] = []
            now = time.time()
            for name, meta in self._metadata.items():
                last = meta.get("rotated_at", meta.get("stored_at", 0))
                if now - last > self._rotation_interval:
                    overdue.append(name)
            if overdue:
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-058: %d credential(s) overdue for rotation: %s",
                    len(overdue),
                    ", ".join(overdue),
                )
            return overdue

    def auto_rotate_overdue(
        self,
        generator: Optional[Callable[[], str]] = None,
    ) -> Dict[str, bool]:
        """Automatically rotate all overdue credentials.

        Parameters
        ----------
        generator : callable, optional
            A zero-arg callable returning a new secret value.
            Defaults to ``secrets.token_urlsafe(32)``.
        """
        gen = generator or (lambda: secrets.token_urlsafe(32))
        overdue = self.check_breach_indicators()
        results: Dict[str, bool] = {}
        for name in overdue:
            try:
                new_val = gen()
                results[name] = self.rotate_credential(name, new_val)
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-059
                logger.error(
                    "MURPHY-AUTOSEC-ERR-059: Auto-rotation failed for '%s': %s",
                    name,
                    exc,
                )
                results[name] = False
        return results

    # -- cleanup / listing ---------------------------------------------------

    def delete_credential(self, name: str, requester: str = "system") -> bool:
        """Permanently delete a credential from the vault."""
        with self._lock:
            if name in self._acl and requester not in self._acl[name]:
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-060: Deletion denied for '%s' → '%s'.",
                    requester,
                    name,
                )
                return False
            path = self._cred_path(name)
            try:
                if path.exists():
                    path.unlink()
                self._acl.pop(name, None)
                self._metadata.pop(name, None)
                self._save_metadata()
                logger.info("Credential '%s' deleted.", name)
                return True
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-060
                logger.error(
                    "MURPHY-AUTOSEC-ERR-060: Deletion failed for '%s': %s",
                    name,
                    exc,
                )
                return False

    def list_credentials(self, requester: str = "system") -> List[str]:
        """List credential names accessible to *requester*."""
        with self._lock:
            return [
                name
                for name, users in self._acl.items()
                if requester in users
            ]
