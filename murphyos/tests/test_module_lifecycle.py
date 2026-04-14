# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Tests for murphy_module_lifecycle — systemd module lifecycle management."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# PYTHONPATH
# ---------------------------------------------------------------------------
_MURPHYOS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MURPHYOS / "userspace" / "murphy-module-lifecycle"))

from murphy_module_lifecycle import (
    ModuleLifecycleError,
    ModuleLifecycleManager,
    ModuleRecord,
    ModuleStatus,
    _scope_name,
    _unit_name,
)


# ── helpers ───────────────────────────────────────────────────────────────
def _make_manager(tmp_path: pathlib.Path) -> ModuleLifecycleManager:
    """Create a manager with a temp registry path."""
    return ModuleLifecycleManager(registry_path=tmp_path / "registry.json")


# ── initialisation ────────────────────────────────────────────────────────
class TestModuleLifecycleManagerInit:
    def test_init_creates_empty_registry(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.list_modules() == []

    def test_init_loads_existing_registry(self, tmp_path):
        reg_path = tmp_path / "registry.json"
        reg_path.write_text(json.dumps({
            "test-mod": {
                "name": "test-mod",
                "version": "1.0.0",
                "entry_point": "/usr/bin/test-mod",
                "config": {},
                "memory_max": "512M",
                "cpu_weight": 100,
                "registered_at": "2024-01-01T00:00:00Z",
                "crash_count": 0,
                "last_crash_ts": 0.0,
            },
        }))
        mgr = ModuleLifecycleManager(registry_path=reg_path)
        assert len(mgr._modules) == 1


# ── register_module ───────────────────────────────────────────────────────
class TestRegisterModule:
    def test_register_module_adds_to_registry(self, tmp_path):
        mgr = _make_manager(tmp_path)
        rec = mgr.register_module("analytics", "2.1.0", "/opt/murphy/analytics")
        assert isinstance(rec, ModuleRecord)
        assert rec.name == "analytics"
        assert rec.version == "2.1.0"

    def test_register_duplicate_raises(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_module("mod-a", "1.0", "/usr/bin/mod-a")
        with pytest.raises(ModuleLifecycleError):
            mgr.register_module("mod-a", "1.0", "/usr/bin/mod-a")

    def test_register_empty_name_raises(self, tmp_path):
        mgr = _make_manager(tmp_path)
        with pytest.raises(ModuleLifecycleError):
            mgr.register_module("", "1.0", "/usr/bin/mod")


# ── unregister_module ─────────────────────────────────────────────────────
class TestUnregisterModule:
    def test_unregister_module_removes_from_registry(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_module("to-remove", "1.0", "/usr/bin/to-remove")
        mgr.unregister_module("to-remove")
        assert all(m.get("name") != "to-remove" for m in mgr.list_modules())

    def test_unregister_unknown_module_raises(self, tmp_path):
        mgr = _make_manager(tmp_path)
        with pytest.raises(ModuleLifecycleError):
            mgr.unregister_module("nonexistent")


# ── list_modules ──────────────────────────────────────────────────────────
class TestListModules:
    def test_list_modules_returns_all_with_status(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_module("mod-1", "1.0", "/usr/bin/mod-1")
        mgr.register_module("mod-2", "2.0", "/usr/bin/mod-2")
        with mock.patch.object(mgr, "get_module_status", return_value=ModuleStatus(name="x", active_state="inactive")):
            modules = mgr.list_modules()
        assert len(modules) == 2


# ── start_module ──────────────────────────────────────────────────────────
class TestStartModule:
    @mock.patch("murphy_module_lifecycle._run")
    def test_start_module_calls_systemd_run(self, mock_run, tmp_path):
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="", stderr="")
        mgr = _make_manager(tmp_path)
        mgr.register_module("web", "1.0", "/usr/bin/web-server")
        scope = mgr.start_module("web")
        assert isinstance(scope, str)
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert "systemd-run" in cmd_args[0]

    def test_start_unregistered_module_raises(self, tmp_path):
        mgr = _make_manager(tmp_path)
        with pytest.raises(ModuleLifecycleError):
            mgr.start_module("unknown-mod")


# ── stop_module ───────────────────────────────────────────────────────────
class TestStopModule:
    @mock.patch("murphy_module_lifecycle._run")
    def test_stop_module_calls_systemctl_stop(self, mock_run, tmp_path):
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="", stderr="")
        mgr = _make_manager(tmp_path)
        mgr.register_module("worker", "1.0", "/usr/bin/worker")
        mgr.stop_module("worker")
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        assert "systemctl" in cmd_args[0]
        assert "stop" in cmd_args[1]

    def test_stop_unregistered_module_raises(self, tmp_path):
        mgr = _make_manager(tmp_path)
        with pytest.raises(ModuleLifecycleError):
            mgr.stop_module("ghost-module")


# ── get_module_status ─────────────────────────────────────────────────────
class TestGetModuleStatus:
    @mock.patch("murphy_module_lifecycle._run")
    def test_get_module_status_queries_systemctl(self, mock_run, tmp_path):
        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="ActiveState=active\nSubState=running\nMainPID=1234\nMemoryCurrent=1048576\nId=test.scope\n",
            stderr="",
        )
        mgr = _make_manager(tmp_path)
        mgr.register_module("api", "1.0", "/usr/bin/api")
        status = mgr.get_module_status("api")
        assert isinstance(status, ModuleStatus)
        assert status.active_state == "active"
        assert status.pid == 1234
        assert status.healthy is True


# ── check_module_health ───────────────────────────────────────────────────
class TestCheckModuleHealth:
    def test_check_health_http_success(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_module("svc", "1.0", "/usr/bin/svc", config={"health_url": "http://localhost:8080/health"})
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            assert mgr.check_module_health("svc") is True

    def test_check_health_unregistered_returns_false(self, tmp_path):
        mgr = _make_manager(tmp_path)
        assert mgr.check_module_health("missing") is False


# ── state persistence ─────────────────────────────────────────────────────
class TestStatePersistence:
    def test_save_and_load_registry(self, tmp_path):
        reg_path = tmp_path / "registry.json"
        mgr1 = ModuleLifecycleManager(registry_path=reg_path)
        mgr1.register_module("persisted-mod", "3.0", "/usr/bin/persisted")

        mgr2 = ModuleLifecycleManager(registry_path=reg_path)
        assert "persisted-mod" in mgr2._modules
        assert mgr2._modules["persisted-mod"].version == "3.0"


# ── auto-restart backoff ─────────────────────────────────────────────────
class TestAutoRestartBackoff:
    def test_crash_count_increments(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.register_module("crashy", "1.0", "/usr/bin/crashy")
        with mock.patch.object(mgr, "restart_module", side_effect=ModuleLifecycleError("ERR", "fail")):
            with mock.patch.object(mgr, "_save_registry"):
                mgr._modules["crashy"].crash_count = 0
                mgr._handle_module_crash("crashy")
        assert mgr._modules["crashy"].crash_count >= 1


# ── helper functions ──────────────────────────────────────────────────────
class TestHelperFunctions:
    def test_scope_name_format(self):
        result = _scope_name("analytics", "abc123")
        assert "analytics" in result
        assert "abc123" in result

    def test_unit_name_format(self):
        result = _unit_name("web-server")
        assert "web-server" in result
