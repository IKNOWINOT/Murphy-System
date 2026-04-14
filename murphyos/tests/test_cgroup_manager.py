# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Tests for murphy_cgroup_manager — cgroup v2 resource isolation."""

from __future__ import annotations

import pathlib
import sys
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# PYTHONPATH — make the module importable
# ---------------------------------------------------------------------------
_MURPHYOS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MURPHYOS / "userspace" / "murphy-cgroup"))

from murphy_cgroup_manager import (
    CGroupError,
    CGroupManager,
    CGroupNotAvailable,
    ScopeLimits,
    ScopeNotFound,
    ScopeUsage,
    parse_human_bytes,
    _validate_scope_name,
)


# ── parse_human_bytes ─────────────────────────────────────────────────────
class TestParseHumanBytes:
    def test_parse_plain_int(self):
        assert parse_human_bytes(1024) == 1024

    def test_parse_megabytes_string(self):
        assert parse_human_bytes("512M") == 512 * 1024 ** 2

    def test_parse_gigabytes_string(self):
        assert parse_human_bytes("4G") == 4 * 1024 ** 3


# ── CGroupManager initialisation ─────────────────────────────────────────
class TestCGroupManagerInit:
    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_init_noop_when_cgroupv2_unavailable(self, _mock_is_file):
        """Manager falls back to no-op when cgroup v2 is not mounted."""
        mgr = CGroupManager()
        assert mgr.is_noop is True

    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch.object(pathlib.Path, "is_file", return_value=True)
    def test_init_active_when_cgroupv2_available(self, _is_file, _mkdir, _wt):
        """Manager is active when cgroup v2 hierarchy is detected."""
        mgr = CGroupManager()
        assert mgr.is_noop is False


# ── create_scope ──────────────────────────────────────────────────────────
class TestCreateScope:
    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch.object(pathlib.Path, "is_file", return_value=True)
    def test_create_scope_returns_path(self, _isf, _mkdir, _wt):
        mgr = CGroupManager()
        result = mgr.create_scope("test-agent-1", memory_max="256M", cpu_weight=50)
        assert isinstance(result, pathlib.Path)
        assert "test-agent-1" in str(result)

    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_create_scope_noop_returns_expected_path(self, _isf):
        mgr = CGroupManager()
        assert mgr.is_noop is True
        result = mgr.create_scope("my-scope")
        assert "my-scope" in str(result)

    def test_create_scope_rejects_invalid_name(self):
        with mock.patch.object(pathlib.Path, "is_file", return_value=False):
            mgr = CGroupManager()
        with pytest.raises(CGroupError):
            mgr.create_scope("invalid name!!")


# ── destroy_scope ─────────────────────────────────────────────────────────
class TestDestroyScope:
    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_destroy_scope_noop_mode(self, _isf):
        """In no-op mode, destroy_scope returns without error."""
        mgr = CGroupManager()
        mgr.destroy_scope("some-scope")  # should not raise

    @mock.patch.object(pathlib.Path, "rmdir")
    @mock.patch("murphy_cgroup_manager._safe_read", return_value="")
    @mock.patch.object(pathlib.Path, "read_text", return_value="")
    @mock.patch.object(pathlib.Path, "is_dir", return_value=True)
    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch.object(pathlib.Path, "is_file", return_value=True)
    def test_destroy_scope_removes_directory(self, _isf, _mkdir, _wt, _isd, _rt, _sr, mock_rmdir):
        mgr = CGroupManager()
        mgr.destroy_scope("valid-scope")
        mock_rmdir.assert_called()


# ── list_scopes ───────────────────────────────────────────────────────────
class TestListScopes:
    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_list_scopes_noop_returns_empty(self, _isf):
        mgr = CGroupManager()
        assert mgr.list_scopes() == []

    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch.object(pathlib.Path, "is_file", return_value=True)
    def test_list_scopes_reads_directory(self, _isf, _mkdir, _wt):
        mgr = CGroupManager()
        child_a = mock.MagicMock()
        child_a.name = "agent-1"
        child_a.is_dir.return_value = True
        child_b = mock.MagicMock()
        child_b.name = "agent-2"
        child_b.is_dir.return_value = True
        with mock.patch.object(pathlib.Path, "is_dir", return_value=True):
            with mock.patch.object(pathlib.Path, "iterdir", return_value=[child_a, child_b]):
                result = mgr.list_scopes()
        assert result == ["agent-1", "agent-2"]


# ── get_usage ─────────────────────────────────────────────────────────────
class TestGetUsage:
    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_get_usage_noop_returns_zeros(self, _isf):
        mgr = CGroupManager()
        usage = mgr.get_usage("my-scope")
        assert isinstance(usage, ScopeUsage)
        assert usage.memory_current_bytes == 0
        assert usage.pids_current == 0

    @mock.patch("murphy_cgroup_manager._safe_read")
    @mock.patch.object(pathlib.Path, "read_text")
    @mock.patch.object(pathlib.Path, "is_dir", return_value=True)
    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch.object(pathlib.Path, "is_file", return_value=True)
    def test_get_usage_reads_cgroup_files(self, _isf, _mkdir, _wt, _isd, _rt, mock_sr):
        mock_sr.side_effect = lambda p: {
            "memory.current": "1048576",
            "memory.max": "536870912",
            "cpu.stat": "usage_usec 500000\nnr_periods 10\nnr_throttled 2",
            "pids.current": "5",
            "pids.max": "64",
            "io.stat": "",
        }.get(p.name, "0")
        _rt.side_effect = lambda *a, **kw: mock_sr(pathlib.Path(str(a[0]) if a else ""))
        mgr = CGroupManager()
        usage = mgr.get_usage("scope-1")
        assert isinstance(usage, ScopeUsage)
        assert usage.name == "scope-1"


# ── set_limits ────────────────────────────────────────────────────────────
class TestSetLimits:
    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_set_limits_noop_mode(self, _isf):
        mgr = CGroupManager()
        mgr.set_limits("my-scope", memory_max="1G", cpu_weight=200)  # no error

    @mock.patch("murphy_cgroup_manager._safe_write")
    @mock.patch.object(pathlib.Path, "is_dir", return_value=True)
    @mock.patch.object(pathlib.Path, "write_text")
    @mock.patch.object(pathlib.Path, "mkdir")
    @mock.patch.object(pathlib.Path, "is_file", return_value=True)
    def test_set_limits_writes_controller_files(self, _isf, _mkdir, _wt, _isd, mock_sw):
        mgr = CGroupManager()
        mgr.set_limits("scope-x", memory_max="2G", cpu_weight=300)
        assert mock_sw.call_count >= 2


# ── cleanup_orphans ───────────────────────────────────────────────────────
class TestCleanupOrphans:
    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_cleanup_orphans_noop_returns_zero(self, _isf):
        mgr = CGroupManager()
        assert mgr.cleanup_orphans() == 0


# ── configuration ─────────────────────────────────────────────────────────
class TestConfiguration:
    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_config_loading_from_yaml(self, _isf):
        yaml_content = "murphy_cgroup:\n  base_slice: test.slice\n  enabled: false\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=yaml_content)):
            with mock.patch.object(pathlib.Path, "is_file", side_effect=[True, False]):
                mgr = CGroupManager(config_path="/etc/murphy/cgroup.yaml")
        assert mgr.is_noop is True

    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_fallback_to_defaults_when_no_config(self, _isf):
        mgr = CGroupManager()
        defaults = mgr.swarm_defaults()
        assert "memory_max" in defaults
        assert "cpu_weight" in defaults

    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_llm_defaults_contain_expected_keys(self, _isf):
        mgr = CGroupManager()
        defaults = mgr.llm_defaults()
        assert "memory_max" in defaults

    @mock.patch.object(pathlib.Path, "is_file", return_value=False)
    def test_automation_defaults_contain_expected_keys(self, _isf):
        mgr = CGroupManager()
        defaults = mgr.automation_defaults()
        assert "memory_max" in defaults


# ── scope name validation ─────────────────────────────────────────────────
class TestScopeNameValidation:
    def test_valid_scope_name_passes(self):
        _validate_scope_name("murphy-swarm-abc123")

    def test_empty_scope_name_raises(self):
        with pytest.raises(CGroupError):
            _validate_scope_name("")

    def test_invalid_chars_raise(self):
        with pytest.raises(CGroupError):
            _validate_scope_name("scope name with spaces")
