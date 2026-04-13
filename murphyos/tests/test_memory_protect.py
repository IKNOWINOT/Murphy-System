"""Tests for murphy_memory_protect — memory hardening."""

from unittest import mock

import pytest

from murphy_memory_protect import MemoryProtectionEngine, _write_sysctl, _read_sysctl


# ── enable_aslr_max ───────────────────────────────────────────────────────
class TestEnableASLRMax:
    @mock.patch("murphy_memory_protect._read_sysctl", return_value="1")
    @mock.patch("murphy_memory_protect._write_sysctl", return_value=True)
    def test_aslr_writes_value_2(self, mock_write, mock_read):
        eng = MemoryProtectionEngine()
        result = eng.enable_aslr_max()
        assert result is True
        mock_write.assert_called_once_with("/proc/sys/kernel/randomize_va_space", "2")

    @mock.patch("murphy_memory_protect._read_sysctl", return_value="2")
    def test_aslr_already_max(self, mock_read):
        eng = MemoryProtectionEngine()
        result = eng.enable_aslr_max()
        assert result is True

    @mock.patch("murphy_memory_protect._read_sysctl", return_value="0")
    @mock.patch("murphy_memory_protect._write_sysctl", return_value=False)
    def test_aslr_failure_returns_false(self, mock_write, mock_read):
        eng = MemoryProtectionEngine()
        result = eng.enable_aslr_max()
        assert result is False


# ── enforce_w_xor_x ──────────────────────────────────────────────────────
class TestEnforceWXorX:
    @mock.patch(
        "builtins.open",
        mock.mock_open(read_data="addr perms offset dev inode pathname\n"
                                 "00400000-004ff000 r-xp 00000000 08:01 1234 /usr/bin/python\n"),
    )
    def test_reads_proc_maps(self):
        eng = MemoryProtectionEngine()
        result = eng.enforce_w_xor_x()
        assert isinstance(result, bool)

    @mock.patch("builtins.open", side_effect=PermissionError)
    def test_permission_denied_returns_false(self, _):
        eng = MemoryProtectionEngine()
        assert eng.enforce_w_xor_x() is False


# ── status ────────────────────────────────────────────────────────────────
class TestStatus:
    def test_status_returns_dict(self):
        eng = MemoryProtectionEngine()
        # Warm up by running enable_aslr_max (mocked)
        with mock.patch("murphy_memory_protect._read_sysctl", return_value="2"):
            eng.enable_aslr_max()
        st = eng.status()
        assert isinstance(st, dict)
        assert "aslr_max" in st


# ── sysctl helpers ────────────────────────────────────────────────────────
class TestSysctlHelpers:
    @mock.patch("murphy_memory_protect.pathlib.Path.write_text")
    def test_write_sysctl_success(self, mock_wt):
        assert _write_sysctl("/proc/sys/kernel/randomize_va_space", "2") is True

    @mock.patch("murphy_memory_protect.pathlib.Path.write_text", side_effect=PermissionError)
    def test_write_sysctl_permission_denied(self, _):
        assert _write_sysctl("/proc/sys/kernel/randomize_va_space", "2") is False

    @mock.patch("murphy_memory_protect.pathlib.Path.read_text", return_value="2\n")
    def test_read_sysctl_success(self, _):
        assert _read_sysctl("/proc/sys/kernel/randomize_va_space") == "2"

    @mock.patch("murphy_memory_protect.pathlib.Path.read_text", side_effect=FileNotFoundError)
    def test_read_sysctl_missing(self, _):
        assert _read_sysctl("/proc/sys/nonexistent") is None
