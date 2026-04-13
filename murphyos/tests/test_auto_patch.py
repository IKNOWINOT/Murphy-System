"""Tests for murphy_auto_patch — auto-patch engine."""

import json
import pathlib
from unittest import mock

import pytest

from murphy_auto_patch import AutoPatchEngine, _sha3_256


# ── check_updates ─────────────────────────────────────────────────────────
class TestCheckUpdates:
    def test_check_updates_returns_list(self):
        payload = json.dumps({"patches": [{"id": "p1", "url": "https://x", "sha3": "abc"}]})
        resp = mock.MagicMock()
        resp.read.return_value = payload.encode()
        resp.__enter__ = mock.MagicMock(return_value=resp)
        resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("murphy_auto_patch._urlreq") as mock_urlreq:
            mock_urlreq.Request.return_value = mock.MagicMock()
            mock_urlreq.urlopen.return_value = resp
            eng = AutoPatchEngine()
            updates = eng.check_updates()
        assert isinstance(updates, list)
        assert updates[0]["id"] == "p1"

    def test_check_updates_network_failure(self):
        with mock.patch("murphy_auto_patch._urlreq") as mock_urlreq:
            mock_urlreq.Request.return_value = mock.MagicMock()
            mock_urlreq.urlopen.side_effect = OSError("network down")
            eng = AutoPatchEngine()
            updates = eng.check_updates()
        assert updates == []


# ── rollback / snapshot ───────────────────────────────────────────────────
class TestRollback:
    def test_rollback_no_snapshot_path_returns_false(self):
        eng = AutoPatchEngine()
        eng._snapshot_backend = None
        result = eng.rollback(snapshot_path=None)
        assert result is False

    def test_create_snapshot_no_backend(self, tmp_dir):
        eng = AutoPatchEngine()
        eng._snapshot_backend = None
        assert eng._create_snapshot("test-snap") is None


# ── unsigned patch rejected ───────────────────────────────────────────────
class TestUnsignedPatch:
    def test_verify_patch_no_verifier_skips(self):
        """Without a PQC verifier, _verify_patch returns True (insecure skip)."""
        eng = AutoPatchEngine()
        eng._pqc_verify = None
        assert eng._verify_patch(b"data", b"sig") is True

    def test_verify_patch_bad_signature(self):
        verifier = mock.MagicMock(return_value=False)
        eng = AutoPatchEngine()
        eng._pqc_verify = verifier
        assert eng._verify_patch(b"data", b"bad") is False

    def test_apply_patch_rejects_missing_url(self):
        eng = AutoPatchEngine()
        meta = {"sha3": "abc", "signature": ""}
        assert eng.apply_patch(meta) is False


# ── sha3 helper ───────────────────────────────────────────────────────────
class TestSha3:
    def test_sha3_deterministic(self):
        assert _sha3_256(b"hello") == _sha3_256(b"hello")

    def test_sha3_different_inputs(self):
        assert _sha3_256(b"a") != _sha3_256(b"b")
