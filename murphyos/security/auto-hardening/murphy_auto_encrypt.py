# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Transparent file-level encryption at rest.

Uses AES-256-GCM with keys derived from a Post-Quantum Cryptography (PQC)
hierarchy when available, falling back to PBKDF2 + machine-id.

File header layout (binary, big-endian):
    b"MFSE" | 1-byte version | 12-byte nonce | 16-byte GCM tag

The ``AutoEncryptEngine`` provides encrypt_file / decrypt_file /
is_encrypted helpers.  ``TransparentEncryptWatcher`` (optional) uses
inotify to auto-encrypt new files in watched directories.

Graceful degradation: if encryption fails the original file is preserved
**unencrypted** and an alert is emitted — legitimate work is never blocked.

Error codes: MURPHY-AUTOSEC-ERR-001 .. MURPHY-AUTOSEC-ERR-010
"""
from __future__ import annotations

import hashlib
import hmac
import io
import logging
import os
import pathlib
import platform
import secrets
import struct
import threading
import time
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger("murphy.autosec.auto_encrypt")

# ---------------------------------------------------------------------------
# Optional stdlib-compatible imports
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore[import-untyped]

    _HAS_CRYPTOGRAPHY = True
except ImportError:  # MURPHY-AUTOSEC-ERR-001
    _HAS_CRYPTOGRAPHY = False
    logger.info(
        "MURPHY-AUTOSEC-ERR-001: 'cryptography' package not installed; "
        "falling back to stdlib-only AES via ctypes/openssl."
    )

try:
    import ctypes
    import ctypes.util

    _libcrypto_path = ctypes.util.find_library("crypto")
    _libcrypto = ctypes.CDLL(_libcrypto_path) if _libcrypto_path else None
except Exception as exc:  # MURPHY-AUTOSEC-ERR-002
    _libcrypto = None
    logger.debug(
        "MURPHY-AUTOSEC-ERR-002: Could not load libcrypto via ctypes: %s", exc
    )

try:
    import inotify.adapters as _inotify_mod  # type: ignore[import-untyped]

    _HAS_INOTIFY = True
except ImportError:  # MURPHY-AUTOSEC-ERR-003
    _HAS_INOTIFY = False
    logger.debug(
        "MURPHY-AUTOSEC-ERR-003: inotify package unavailable; "
        "TransparentEncryptWatcher will be disabled."
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HEADER_MAGIC = b"MFSE"
HEADER_VERSION = 1
NONCE_LEN = 12
TAG_LEN = 16
HEADER_LEN = len(HEADER_MAGIC) + 1 + NONCE_LEN + TAG_LEN  # 33 bytes
KEY_LEN = 32  # AES-256
PBKDF2_ITERATIONS = 600_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _machine_id() -> bytes:
    """Return a stable machine identifier (best-effort)."""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            return pathlib.Path(path).read_bytes().strip()
        except OSError:
            continue
    return platform.node().encode()


def _derive_key(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a 256-bit key via PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac("sha256", passphrase, salt, PBKDF2_ITERATIONS)


def _aes_gcm_encrypt_stdlib(key: bytes, nonce: bytes, plaintext: bytes) -> Tuple[bytes, bytes]:
    """AES-256-GCM encrypt using the *cryptography* library when available,
    otherwise fall back to a ctypes/libcrypto call.

    Returns (ciphertext, tag).
    """
    if _HAS_CRYPTOGRAPHY:
        aesgcm = AESGCM(key)
        ct_and_tag = aesgcm.encrypt(nonce, plaintext, None)
        return ct_and_tag[:-TAG_LEN], ct_and_tag[-TAG_LEN:]

    if _libcrypto is not None:
        return _aes_gcm_via_ctypes(key, nonce, plaintext, encrypt=True)

    raise RuntimeError("No AES-256-GCM backend available")


def _aes_gcm_decrypt_stdlib(
    key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes
) -> bytes:
    """AES-256-GCM decrypt (mirror of encrypt)."""
    if _HAS_CRYPTOGRAPHY:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext + tag, None)

    if _libcrypto is not None:
        plaintext, _ = _aes_gcm_via_ctypes(
            key, nonce, ciphertext, encrypt=False, tag=tag
        )
        return plaintext

    raise RuntimeError("No AES-256-GCM backend available")


def _aes_gcm_via_ctypes(
    key: bytes,
    nonce: bytes,
    data: bytes,
    encrypt: bool = True,
    tag: Optional[bytes] = None,
) -> Tuple[bytes, bytes]:
    """Minimal ctypes wrapper around OpenSSL EVP for AES-256-GCM."""
    if _libcrypto is None:
        raise RuntimeError("libcrypto not loaded")  # MURPHY-AUTOSEC-ERR-004

    ctx = _libcrypto.EVP_CIPHER_CTX_new()
    if not ctx:
        raise MemoryError("MURPHY-AUTOSEC-ERR-004: EVP_CIPHER_CTX_new failed")

    try:
        cipher = _libcrypto.EVP_aes_256_gcm()
        out_buf = ctypes.create_string_buffer(len(data) + 16)
        out_len = ctypes.c_int(0)

        _libcrypto.EVP_CipherInit_ex(
            ctx, cipher, None, None, None, int(encrypt)
        )
        _libcrypto.EVP_CIPHER_CTX_ctrl(ctx, 0x9, NONCE_LEN, None)  # EVP_CTRL_GCM_SET_IVLEN
        _libcrypto.EVP_CipherInit_ex(ctx, None, None, key, nonce, int(encrypt))

        if not encrypt and tag is not None:
            tag_buf = ctypes.create_string_buffer(tag)
            _libcrypto.EVP_CIPHER_CTX_ctrl(ctx, 0x11, TAG_LEN, tag_buf)  # SET_TAG

        _libcrypto.EVP_CipherUpdate(
            ctx, out_buf, ctypes.byref(out_len), data, len(data)
        )
        result = out_buf.raw[: out_len.value]

        final_buf = ctypes.create_string_buffer(32)
        final_len = ctypes.c_int(0)
        rc = _libcrypto.EVP_CipherFinal_ex(ctx, final_buf, ctypes.byref(final_len))
        if rc <= 0 and not encrypt:
            raise ValueError("MURPHY-AUTOSEC-ERR-005: GCM tag verification failed")
        result += final_buf.raw[: final_len.value]

        out_tag = b""
        if encrypt:
            tag_out = ctypes.create_string_buffer(TAG_LEN)
            _libcrypto.EVP_CIPHER_CTX_ctrl(ctx, 0x10, TAG_LEN, tag_out)  # GET_TAG
            out_tag = tag_out.raw[:TAG_LEN]

        return result, out_tag
    finally:
        _libcrypto.EVP_CIPHER_CTX_free(ctx)


# ---------------------------------------------------------------------------
# AutoEncryptEngine
# ---------------------------------------------------------------------------
class AutoEncryptEngine:
    """Transparent file-level AES-256-GCM encryption engine.

    Parameters
    ----------
    pqc_key_provider : callable, optional
        A zero-arg callable returning a 32-byte key from the PQC hierarchy.
        When *None* the engine falls back to PBKDF2 + machine-id.
    """

    def __init__(self, pqc_key_provider: Optional[object] = None) -> None:
        self._pqc_key_provider = pqc_key_provider
        self._salt = hashlib.sha256(b"murphy-autosec-salt-" + _machine_id()).digest()
        self._key: Optional[bytes] = None
        logger.info("AutoEncryptEngine initialised.")

    # -- key management -----------------------------------------------------

    def _resolve_key(self) -> bytes:
        """Resolve the 256-bit encryption key."""
        if self._key is not None:
            return self._key

        if callable(self._pqc_key_provider):
            try:
                key = self._pqc_key_provider()
                if isinstance(key, bytes) and len(key) == KEY_LEN:
                    self._key = key
                    logger.debug("Using PQC-derived encryption key.")
                    return self._key
            except Exception as exc:  # MURPHY-AUTOSEC-ERR-006
                logger.warning(
                    "MURPHY-AUTOSEC-ERR-006: PQC key provider failed (%s); "
                    "falling back to PBKDF2.",
                    exc,
                )

        self._key = _derive_key(_machine_id(), self._salt)
        logger.debug("Using PBKDF2-derived encryption key.")
        return self._key

    # -- public API ---------------------------------------------------------

    def is_encrypted(self, filepath: Union[str, pathlib.Path]) -> bool:
        """Return *True* if *filepath* bears a valid MFSE header."""
        try:
            with open(filepath, "rb") as fh:
                header = fh.read(HEADER_LEN)
            return (
                len(header) >= HEADER_LEN
                and header[:4] == HEADER_MAGIC
                and header[4] == HEADER_VERSION
            )
        except OSError as exc:  # MURPHY-AUTOSEC-ERR-007
            logger.error(
                "MURPHY-AUTOSEC-ERR-007: Cannot read file %s: %s", filepath, exc
            )
            return False

    def encrypt_file(self, filepath: Union[str, pathlib.Path]) -> bool:
        """Encrypt *filepath* in-place with AES-256-GCM.

        Returns *True* on success.  On failure the original file is
        preserved **unencrypted** and an alert is logged.
        """
        filepath = pathlib.Path(filepath)
        if self.is_encrypted(filepath):
            logger.debug("File already encrypted: %s", filepath)
            return True

        try:
            plaintext = filepath.read_bytes()
        except OSError as exc:  # MURPHY-AUTOSEC-ERR-008
            logger.error(
                "MURPHY-AUTOSEC-ERR-008: Cannot read %s for encryption: %s",
                filepath,
                exc,
            )
            return False

        try:
            key = self._resolve_key()
            nonce = secrets.token_bytes(NONCE_LEN)
            ciphertext, tag = _aes_gcm_encrypt_stdlib(key, nonce, plaintext)
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-009
            logger.error(
                "MURPHY-AUTOSEC-ERR-009: Encryption failed for %s: %s — "
                "file left unencrypted (graceful degradation).",
                filepath,
                exc,
            )
            return False

        header = HEADER_MAGIC + struct.pack("B", HEADER_VERSION) + nonce + tag
        try:
            filepath.write_bytes(header + ciphertext)
        except OSError as exc:  # MURPHY-AUTOSEC-ERR-010
            logger.error(
                "MURPHY-AUTOSEC-ERR-010: Cannot write encrypted file %s: %s — "
                "restoring original plaintext.",
                filepath,
                exc,
            )
            try:
                filepath.write_bytes(plaintext)
            except OSError as restore_exc:  # MURPHY-AUTOSEC-ERR-009
                logger.error("MURPHY-AUTOSEC-ERR-009: failed to restore plaintext after encrypt error: %s", restore_exc)
            return False

        logger.info("Encrypted file: %s", filepath)
        return True

    def decrypt_file(self, filepath: Union[str, pathlib.Path]) -> bool:
        """Decrypt an MFSE-encrypted file in-place.

        Returns *True* on success.
        """
        filepath = pathlib.Path(filepath)
        if not self.is_encrypted(filepath):
            logger.debug("File is not encrypted: %s", filepath)
            return True

        raw = filepath.read_bytes()
        nonce = raw[5 : 5 + NONCE_LEN]
        tag = raw[5 + NONCE_LEN : HEADER_LEN]
        ciphertext = raw[HEADER_LEN:]

        try:
            key = self._resolve_key()
            plaintext = _aes_gcm_decrypt_stdlib(key, nonce, ciphertext, tag)
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-009
            logger.error(
                "MURPHY-AUTOSEC-ERR-009: Decryption failed for %s: %s", filepath, exc
            )
            return False

        filepath.write_bytes(plaintext)
        logger.info("Decrypted file: %s", filepath)
        return True


# ---------------------------------------------------------------------------
# TransparentEncryptWatcher (optional inotify-based)
# ---------------------------------------------------------------------------
class TransparentEncryptWatcher:
    """Watches directories via inotify and auto-encrypts new/modified files.

    Degrades gracefully when the *inotify* package is not installed.
    """

    def __init__(
        self,
        engine: AutoEncryptEngine,
        watch_dirs: Optional[List[str]] = None,
    ) -> None:
        self._engine = engine
        self._watch_dirs = watch_dirs or []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        """Return *True* when the inotify backend is available."""
        return _HAS_INOTIFY

    def start(self) -> None:
        """Start the watcher in a daemon thread."""
        if not _HAS_INOTIFY:
            logger.warning(
                "MURPHY-AUTOSEC-ERR-003: inotify unavailable; watcher not started."
            )
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("TransparentEncryptWatcher started on %s.", self._watch_dirs)

    def stop(self) -> None:
        """Signal the watcher to stop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("TransparentEncryptWatcher stopped.")

    def _run(self) -> None:
        """Main watch loop (runs in background thread)."""
        try:
            i = _inotify_mod.Inotify()  # type: ignore[attr-defined]
            for d in self._watch_dirs:
                i.add_watch(d)
            for event in i.event_gen(yield_nones=False):
                if not self._running:
                    break
                _, type_names, path, filename = event
                if "IN_CLOSE_WRITE" in type_names and filename:
                    full = os.path.join(path, filename)
                    self._engine.encrypt_file(full)
        except Exception as exc:  # MURPHY-AUTOSEC-ERR-003
            logger.error(
                "MURPHY-AUTOSEC-ERR-003: Watcher loop error: %s", exc
            )
