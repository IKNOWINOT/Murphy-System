"""Tests for murphy_auto_encrypt — encryption engine."""

import os
import pathlib
import struct
from unittest import mock

import pytest

from murphy_auto_encrypt import (
    AutoEncryptEngine,
    HEADER_MAGIC,
    HEADER_VERSION,
    _derive_key,
    _machine_id,
)


# ── helpers ────────────────────────────────────────────────────────────────
def _write(path: pathlib.Path, data: bytes) -> pathlib.Path:
    path.write_bytes(data)
    return path


# ── encrypt / decrypt round-trip ──────────────────────────────────────────
class TestEncryptDecryptRoundTrip:
    def test_round_trip_basic(self, tmp_dir):
        """encrypt ▸ decrypt must yield original plaintext."""
        src = _write(tmp_dir / "secret.txt", b"Top-secret payload 42")
        eng = AutoEncryptEngine()
        assert eng.encrypt_file(src) is True
        assert eng.is_encrypted(src) is True
        assert eng.decrypt_file(src) is True
        assert src.read_bytes() == b"Top-secret payload 42"

    def test_round_trip_binary(self, tmp_dir):
        blob = os.urandom(4096)
        src = _write(tmp_dir / "blob.bin", blob)
        eng = AutoEncryptEngine()
        eng.encrypt_file(src)
        eng.decrypt_file(src)
        assert src.read_bytes() == blob

    def test_round_trip_empty_file(self, tmp_dir):
        src = _write(tmp_dir / "empty.txt", b"")
        eng = AutoEncryptEngine()
        assert eng.encrypt_file(src) is True
        assert eng.decrypt_file(src) is True
        assert src.read_bytes() == b""

    def test_encrypt_already_encrypted(self, tmp_dir):
        """Encrypting an already-encrypted file should be a no-op."""
        src = _write(tmp_dir / "dup.txt", b"data")
        eng = AutoEncryptEngine()
        eng.encrypt_file(src)
        first = src.read_bytes()
        eng.encrypt_file(src)
        assert src.read_bytes() == first


# ── is_encrypted magic-byte detection ─────────────────────────────────────
class TestIsEncrypted:
    def test_plain_file_not_detected(self, tmp_dir):
        src = _write(tmp_dir / "plain.txt", b"hello world")
        assert AutoEncryptEngine().is_encrypted(src) is False

    def test_magic_header_detected(self, tmp_dir):
        hdr = HEADER_MAGIC + struct.pack("<B", HEADER_VERSION)
        src = _write(tmp_dir / "enc.bin", hdr + os.urandom(64))
        assert AutoEncryptEngine().is_encrypted(src) is True

    def test_short_file_not_encrypted(self, tmp_dir):
        src = _write(tmp_dir / "tiny.bin", b"MF")
        assert AutoEncryptEngine().is_encrypted(src) is False


# ── corrupted file handling ───────────────────────────────────────────────
class TestCorruptedFile:
    def test_decrypt_corrupted_returns_false(self, tmp_dir):
        """Decrypting a file with valid header but garbled body must fail gracefully."""
        src = _write(tmp_dir / "ok.txt", b"payload")
        eng = AutoEncryptEngine()
        eng.encrypt_file(src)
        raw = bytearray(src.read_bytes())
        raw[-1] ^= 0xFF  # flip last byte
        src.write_bytes(bytes(raw))
        assert eng.decrypt_file(src) is False

    def test_decrypt_plaintext_file_is_noop(self, tmp_dir):
        """Decrypting a non-encrypted file returns True (no-op)."""
        src = _write(tmp_dir / "plain.txt", b"not encrypted")
        assert AutoEncryptEngine().decrypt_file(src) is True
        assert src.read_bytes() == b"not encrypted"

    def test_encrypt_missing_file_returns_false(self):
        eng = AutoEncryptEngine()
        assert eng.encrypt_file(pathlib.Path("/nonexistent/file.txt")) is False


# ── PQC fallback ──────────────────────────────────────────────────────────
class TestPQCFallback:
    def test_fallback_when_pqc_unavailable(self, tmp_dir):
        """When PQC provider raises, engine falls back to local key."""
        pqc = mock.MagicMock()
        pqc.get_key.side_effect = RuntimeError("PQC down")
        eng = AutoEncryptEngine(pqc_key_provider=pqc)
        src = _write(tmp_dir / "fb.txt", b"fallback data")
        assert eng.encrypt_file(src) is True
        assert eng.is_encrypted(src) is True

    def test_derive_key_deterministic(self):
        salt = os.urandom(16)
        k1 = _derive_key(b"passphrase", salt)
        k2 = _derive_key(b"passphrase", salt)
        assert k1 == k2

    def test_machine_id_returns_bytes(self):
        mid = _machine_id()
        assert isinstance(mid, bytes) and len(mid) > 0
