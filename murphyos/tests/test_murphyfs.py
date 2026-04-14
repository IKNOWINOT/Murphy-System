"""Tests for murphyfs — FUSE virtual filesystem (FUSE fully mocked)."""

import errno
import sys
from unittest import mock

import pytest

# Mock the fuse module before importing murphyfs
_fuse_mock = mock.MagicMock()
_fuse_mock.FUSE = mock.MagicMock()


class _FakeOperations:
    """Stub base class for Operations."""
    pass


_fuse_mock.Operations = _FakeOperations
_fuse_mock.FuseOSError = type("FuseOSError", (OSError,), {})
sys.modules.setdefault("fuse", _fuse_mock)

from murphyfs import MurphyFS, _Cache, _api_get  # noqa: E402


# ── path resolution ───────────────────────────────────────────────────────
class TestPathResolution:
    def _fs(self):
        return MurphyFS(api_url="http://127.0.0.1:4242")

    @mock.patch("murphyfs._api_get", return_value='{"score":92}')
    def test_resolve_confidence(self, _):
        """The FS root is the virtual mount; /confidence lives at top level."""
        fs = self._fs()
        data = fs._resolve("/confidence")
        assert data is not None

    def test_resolve_root(self):
        fs = self._fs()
        assert fs._is_dir("/") is True

    def test_resolve_engines_dir(self):
        fs = self._fs()
        assert fs._is_dir("/engines") is True

    def test_resolve_system_dir(self):
        fs = self._fs()
        assert fs._is_dir("/system") is True

    def test_resolve_nonexistent(self):
        fs = self._fs()
        FuseOSError = sys.modules["fuse"].FuseOSError
        with pytest.raises(FuseOSError):
            fs._resolve("/nonexistent_path_xyz")

    @mock.patch("murphyfs._api_get", return_value='{"version":"1.0.0"}')
    def test_resolve_version(self, _):
        fs = self._fs()
        data = fs._resolve("/system/version")
        assert data is not None


# ── readdir ───────────────────────────────────────────────────────────────
class TestReaddir:
    def test_readdir_root(self):
        fs = MurphyFS(api_url="http://127.0.0.1:4242")
        entries = fs.readdir("/", 0)
        assert "." in entries
        assert ".." in entries
        assert "confidence" in entries
        assert "engines" in entries

    @mock.patch("murphyfs._api_get", return_value='{"eng1":{"status":"ok"}}')
    def test_readdir_engines(self, _):
        fs = MurphyFS(api_url="http://127.0.0.1:4242")
        entries = fs.readdir("/engines", 0)
        assert isinstance(entries, list)
        assert "eng1" in entries

    def test_readdir_system(self):
        fs = MurphyFS(api_url="http://127.0.0.1:4242")
        entries = fs.readdir("/system", 0)
        assert "version" in entries
        assert "uptime" in entries


# ── cache ─────────────────────────────────────────────────────────────────
class TestCache:
    def test_cache_hit(self):
        c = _Cache(ttl=60.0)
        c.get("k", lambda: "value1")
        result = c.get("k", lambda: "value2")
        assert result == "value1"

    def test_cache_invalidate(self):
        c = _Cache(ttl=60.0)
        c.get("k", lambda: "first")
        c.invalidate("k")
        result = c.get("k", lambda: "second")
        assert result == "second"

    def test_cache_refresh_after_ttl(self):
        c = _Cache(ttl=0.0)  # instant expiry
        c.get("k", lambda: "old")
        import time
        time.sleep(0.01)
        result = c.get("k", lambda: "new")
        assert result == "new"


# ── getattr / statfs ──────────────────────────────────────────────────────
class TestGetattr:
    def test_getattr_root(self):
        fs = MurphyFS(api_url="http://127.0.0.1:4242")
        attr = fs.getattr("/")
        assert "st_mode" in attr

    def test_statfs(self):
        fs = MurphyFS(api_url="http://127.0.0.1:4242")
        sfs = fs.statfs("/")
        assert isinstance(sfs, dict)
