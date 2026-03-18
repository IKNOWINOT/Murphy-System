"""
Tests for the Murphy System Boot Dispatcher and related tiered runtime components.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent


def _stub_create_app():
    """Return a minimal stub for src.runtime.app.create_app()."""
    app = MagicMock()
    app.__name__ = "monolith_app"
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove MURPHY_RUNTIME_MODE from env before each test."""
    monkeypatch.delenv("MURPHY_RUNTIME_MODE", raising=False)
    # Also reset the module-level RUNTIME_MODE cache by reimporting
    if "src.runtime.boot" in sys.modules:
        del sys.modules["src.runtime.boot"]
    yield


@pytest.fixture()
def stub_monolith_app(monkeypatch):
    """Patch src.runtime.app so create_app() returns a stub without loading the full app."""
    app_module = types.ModuleType("src.runtime.app")
    app_module.create_app = _stub_create_app
    monkeypatch.setitem(sys.modules, "src.runtime.app", app_module)
    return app_module


# ---------------------------------------------------------------------------
# Test: default mode is monolith
# ---------------------------------------------------------------------------

class TestDefaultMode:
    def test_missing_env_var_defaults_to_monolith(self, stub_monolith_app):
        """MURPHY_RUNTIME_MODE not set → monolith boot."""
        assert "MURPHY_RUNTIME_MODE" not in os.environ

        from src.runtime.boot import boot_murphy  # noqa: PLC0415
        app = asyncio.run(boot_murphy())
        assert app is not None

    def test_explicit_monolith_mode(self, stub_monolith_app):
        """Passing mode='monolith' explicitly → monolith boot."""
        from src.runtime.boot import boot_murphy  # noqa: PLC0415
        app = asyncio.run(boot_murphy(mode="monolith"))
        assert app is not None

    def test_unknown_mode_falls_back_to_monolith(self, stub_monolith_app):
        """An unknown mode string warns and falls back to monolith."""
        from src.runtime.boot import boot_murphy  # noqa: PLC0415
        app = asyncio.run(boot_murphy(mode="banana"))
        assert app is not None


# ---------------------------------------------------------------------------
# Test: monolith boot
# ---------------------------------------------------------------------------

class TestMonolithBoot:
    def test_boot_monolith_calls_create_app(self, stub_monolith_app):
        """boot_monolith() returns the result of create_app()."""
        from src.runtime.boot import boot_monolith  # noqa: PLC0415
        app = asyncio.run(boot_monolith())
        assert app is not None

    def test_env_var_monolith(self, monkeypatch, stub_monolith_app):
        """MURPHY_RUNTIME_MODE=monolith → monolith boot."""
        monkeypatch.setenv("MURPHY_RUNTIME_MODE", "monolith")
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]
        from src.runtime.boot import boot_murphy  # noqa: PLC0415
        app = asyncio.run(boot_murphy())
        assert app is not None


# ---------------------------------------------------------------------------
# Test: tiered boot
# ---------------------------------------------------------------------------

class TestTieredBoot:
    def _make_stub_orchestrator(self, success: bool = True):
        orch = MagicMock()
        boot_result = MagicMock()
        boot_result.success = success
        boot_result.errors = [] if success else ["boom"]
        orch.boot = AsyncMock(return_value=boot_result)
        orch.register_pack = MagicMock()
        orch.get_active_routers = MagicMock(return_value=[])
        orch.get_status = MagicMock(return_value={"booted": True, "packs": {}})
        return orch

    def test_env_var_tiered_boots_tiered(self, monkeypatch, stub_monolith_app):
        """MURPHY_RUNTIME_MODE=tiered uses the tiered path."""
        monkeypatch.setenv("MURPHY_RUNTIME_MODE", "tiered")
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]

        stub_orch = self._make_stub_orchestrator(success=True)

        with patch("src.runtime.tiered_orchestrator.TieredOrchestrator",
                   return_value=stub_orch), \
             patch("src.runtime.runtime_packs.registry.get_all_packs",
                   return_value=[]), \
             patch("src.runtime.tiered_app_factory.create_tiered_app",
                   return_value=MagicMock()) as mock_factory:

            from src.runtime.boot import boot_murphy  # noqa: PLC0415
            app = asyncio.run(boot_murphy())

        mock_factory.assert_called_once_with(stub_orch)
        assert app is not None

    def test_tiered_failure_falls_back_to_monolith(self, monkeypatch, stub_monolith_app):
        """When tiered boot fails, system automatically falls back to monolith."""
        monkeypatch.setenv("MURPHY_RUNTIME_MODE", "tiered")
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]

        stub_orch = self._make_stub_orchestrator(success=False)

        with patch("src.runtime.tiered_orchestrator.TieredOrchestrator",
                   return_value=stub_orch), \
             patch("src.runtime.runtime_packs.registry.get_all_packs",
                   return_value=[]):

            from src.runtime.boot import boot_murphy  # noqa: PLC0415
            app = asyncio.run(boot_murphy())

        # Should have fallen back to monolith
        assert app is not None

    def test_tiered_exception_falls_back_to_monolith(self, monkeypatch, stub_monolith_app):
        """If TieredOrchestrator import raises, falls back to monolith."""
        monkeypatch.setenv("MURPHY_RUNTIME_MODE", "tiered")
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]

        with patch("src.runtime.tiered_orchestrator.TieredOrchestrator",
                   side_effect=ImportError("mock missing dep")):
            from src.runtime.boot import boot_murphy  # noqa: PLC0415
            app = asyncio.run(boot_murphy())

        assert app is not None

    def test_boot_tiered_no_fallback_raises(self, monkeypatch, stub_monolith_app):
        """With fallback_on_error=False, tiered failure propagates the exception."""
        monkeypatch.setenv("MURPHY_RUNTIME_MODE", "tiered")
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]

        stub_orch = self._make_stub_orchestrator(success=False)

        with patch("src.runtime.tiered_orchestrator.TieredOrchestrator",
                   return_value=stub_orch), \
             patch("src.runtime.runtime_packs.registry.get_all_packs",
                   return_value=[]):
            from src.runtime.boot import boot_tiered  # noqa: PLC0415
            with pytest.raises(RuntimeError, match="Tiered boot failed"):
                asyncio.run(boot_tiered(fallback_on_error=False))


# ---------------------------------------------------------------------------
# Test: _load_team_profile
# ---------------------------------------------------------------------------

class TestLoadTeamProfile:
    def test_missing_persistence_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MURPHY_PERSISTENCE_DIR", str(tmp_path / "nonexistent"))
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]
        from src.runtime.boot import _load_team_profile  # noqa: PLC0415
        assert _load_team_profile() == {}

    def test_valid_profile_loaded(self, tmp_path, monkeypatch):
        profile = {"capabilities": ["analytics", "billing"]}
        (tmp_path / "team_profile.json").write_text(json.dumps(profile))
        monkeypatch.setenv("MURPHY_PERSISTENCE_DIR", str(tmp_path))
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]
        from src.runtime.boot import _load_team_profile  # noqa: PLC0415
        result = _load_team_profile()
        assert result["capabilities"] == ["analytics", "billing"]

    def test_corrupt_profile_returns_empty(self, tmp_path, monkeypatch):
        (tmp_path / "team_profile.json").write_text("{NOT VALID JSON}")
        monkeypatch.setenv("MURPHY_PERSISTENCE_DIR", str(tmp_path))
        if "src.runtime.boot" in sys.modules:
            del sys.modules["src.runtime.boot"]
        from src.runtime.boot import _load_team_profile  # noqa: PLC0415
        assert _load_team_profile() == {}


# ---------------------------------------------------------------------------
# Test: Lazy runtime proxy
# ---------------------------------------------------------------------------

class TestLazyRuntimeProxy:
    def test_runtime_is_lazy_proxy(self):
        """Importing modular_runtime should not instantiate ModularRuntime."""
        # Re-import to get a fresh module
        if "src.modular_runtime" in sys.modules:
            del sys.modules["src.modular_runtime"]

        instantiated = []

        class FakeModularRuntime:
            def __init__(self):
                instantiated.append(True)

            def some_method(self):
                return "called"

        with patch("src.modular_runtime.ModularRuntime", FakeModularRuntime):
            import importlib  # noqa: PLC0415
            mod = importlib.import_module("src.modular_runtime")
            # After import, no instantiation yet
            assert len(instantiated) == 0, "ModularRuntime was eagerly instantiated!"

            # Accessing an attribute triggers instantiation
            _ = mod.runtime.some_method()
            assert len(instantiated) == 1, "ModularRuntime was not instantiated on first access."

    def test_lazy_proxy_caches_instance(self):
        """Second attribute access reuses the same ModularRuntime instance."""
        if "src.modular_runtime" in sys.modules:
            del sys.modules["src.modular_runtime"]

        instances = []

        class FakeModularRuntime:
            def __init__(self):
                instances.append(id(self))

            def foo(self):
                return "foo"

        with patch("src.modular_runtime.ModularRuntime", FakeModularRuntime):
            import importlib  # noqa: PLC0415
            mod = importlib.import_module("src.modular_runtime")
            _ = mod.runtime.foo()
            _ = mod.runtime.foo()
            assert len(instances) == 1, "ModularRuntime was instantiated more than once!"


# ---------------------------------------------------------------------------
# Test: TieredOrchestrator unit tests
# ---------------------------------------------------------------------------

class TestTieredOrchestrator:
    def test_register_and_boot_all_packs(self):
        from src.runtime.tiered_orchestrator import RuntimePack, TieredOrchestrator  # noqa: PLC0415
        orch = TieredOrchestrator()
        pack = RuntimePack(name="test_pack", capabilities={"test_cap"})
        orch.register_pack(pack)
        result = asyncio.run(orch.boot())
        assert result.success
        assert "test_pack" in result.loaded_packs

    def test_capability_filtering_skips_irrelevant_packs(self):
        from src.runtime.tiered_orchestrator import RuntimePack, TieredOrchestrator  # noqa: PLC0415
        orch = TieredOrchestrator()
        orch.register_pack(RuntimePack(name="billing", capabilities={"payments"}))
        orch.register_pack(RuntimePack(name="hvac", capabilities={"hvac"}))
        result = asyncio.run(orch.boot(team_profile={"capabilities": ["payments"]}))
        assert "billing" in result.loaded_packs
        assert "hvac" in result.skipped_packs

    def test_failed_pack_on_load_hook(self):
        from src.runtime.tiered_orchestrator import RuntimePack, TieredOrchestrator  # noqa: PLC0415

        async def bad_load():
            raise RuntimeError("intentional failure")

        orch = TieredOrchestrator()
        orch.register_pack(RuntimePack(name="bad", capabilities={"bad"}, on_load=bad_load))
        result = asyncio.run(orch.boot())
        assert not result.success
        assert "bad" in result.failed_packs

    def test_duplicate_registration_ignored(self):
        from src.runtime.tiered_orchestrator import RuntimePack, TieredOrchestrator  # noqa: PLC0415
        orch = TieredOrchestrator()
        pack = RuntimePack(name="dup", capabilities={"x"})
        orch.register_pack(pack)
        orch.register_pack(pack)  # second registration should be silently ignored
        assert len(orch.packs) == 1

    def test_unload_pack(self):
        from src.runtime.tiered_orchestrator import PackStatus, RuntimePack, TieredOrchestrator  # noqa: PLC0415
        orch = TieredOrchestrator()
        pack = RuntimePack(name="removable", capabilities={"r"})
        orch.register_pack(pack)
        asyncio.run(orch.boot())
        assert orch.packs["removable"].status == PackStatus.LOADED
        asyncio.run(orch.unload_pack("removable"))
        assert orch.packs["removable"].status == PackStatus.UNLOADED


# ---------------------------------------------------------------------------
# Test: registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_get_all_packs_returns_list(self):
        from src.runtime.runtime_packs.registry import get_all_packs  # noqa: PLC0415
        packs = get_all_packs()
        assert len(packs) > 0
        names = [p.name for p in packs]
        assert "core" in names

    def test_capability_to_pack_mapping(self):
        from src.runtime.runtime_packs.registry import CAPABILITY_TO_PACK, get_pack_for_capability  # noqa: PLC0415
        assert get_pack_for_capability("auth") == "core"
        assert get_pack_for_capability("hvac") == "hvac"
        assert get_pack_for_capability("nonexistent_capability") is None

    def test_each_pack_has_unique_name(self):
        from src.runtime.runtime_packs.registry import get_all_packs  # noqa: PLC0415
        packs = get_all_packs()
        names = [p.name for p in packs]
        assert len(names) == len(set(names)), "Duplicate pack names found!"

    def test_get_capabilities_for_pack(self):
        from src.runtime.runtime_packs.registry import get_capabilities_for_pack  # noqa: PLC0415
        caps = get_capabilities_for_pack("core")
        assert "auth" in caps
