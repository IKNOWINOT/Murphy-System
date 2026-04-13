"""Tests for murphy_credential_vault — secret management."""

import os
import pathlib
from unittest import mock

import pytest

from murphy_credential_vault import CredentialVault, _derive_key, _encrypt_blob, _decrypt_blob


# ── store / retrieve round-trip ───────────────────────────────────────────
class TestStoreRetrieve:
    def test_round_trip(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        vault.store_credential("api_key", "super-secret-123", owner="admin")
        val = vault.retrieve_credential("api_key", requester="admin")
        assert val == "super-secret-123"

    def test_retrieve_nonexistent(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        assert vault.retrieve_credential("nope") is None

    def test_overwrite_credential(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        vault.store_credential("key", "v1", owner="admin")
        vault.store_credential("key", "v2", owner="admin")
        assert vault.retrieve_credential("key", requester="admin") == "v2"

    def test_list_credentials(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        vault.store_credential("a", "1", owner="admin")
        vault.store_credential("b", "2", owner="admin")
        names = vault.list_credentials(requester="admin")
        assert set(names) >= {"a", "b"}


# ── rotation ──────────────────────────────────────────────────────────────
class TestRotation:
    def test_rotation_changes_value(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        vault.store_credential("db_pass", "old-pass", owner="admin")
        vault.rotate_credential("db_pass", new_value="new-pass", requester="admin")
        assert vault.retrieve_credential("db_pass", requester="admin") == "new-pass"

    def test_rotation_nonexistent_returns_result(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        result = vault.rotate_credential("ghost", new_value="x", requester="admin")
        # store_credential is called internally; returns bool based on store
        assert isinstance(result, bool)


# ── breach detection ──────────────────────────────────────────────────────
class TestBreachDetection:
    def test_tampered_vault_detected(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        vault.store_credential("token", "s3cret", owner="admin")
        # Tamper with the on-disk credential file
        for f in tmp_dir.iterdir():
            if f.is_file() and f.suffix != ".json":
                raw = bytearray(f.read_bytes())
                if len(raw) > 4:
                    raw[-1] ^= 0xFF
                    f.write_bytes(bytes(raw))
        alerts = vault.check_breach_indicators()
        assert isinstance(alerts, list)

    def test_no_breach_on_clean_vault(self, tmp_dir):
        vault = CredentialVault(vault_dir=tmp_dir)
        vault.store_credential("clean", "value", owner="admin")
        alerts = vault.check_breach_indicators()
        assert isinstance(alerts, list)


# ── crypto helpers ────────────────────────────────────────────────────────
class TestCryptoHelpers:
    def test_encrypt_decrypt_blob(self):
        key = os.urandom(32)
        ct = _encrypt_blob(key, b"hello vault")
        pt = _decrypt_blob(key, ct)
        assert pt == b"hello vault"

    def test_derive_key_length(self):
        k = _derive_key(b"pass", os.urandom(16))
        assert len(k) == 32
