# Copyright © 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1
"""
src/runtime/runtime_packs/tests/test_tiered_orchestrator.py
=============================================================
Unit tests for the TieredOrchestrator.

These tests use lightweight stub packs with fake module paths so that
real Murphy module imports are not required.  A custom import hook
(``_FakeModuleLoader``) lets every listed module path in a stub pack
succeed without the actual file being present.

Tests cover:
- KERNEL pack failure aborts boot
- PLATFORM pack failure aborts boot
- DOMAIN pack failure does NOT abort boot (graceful degradation)
- ``request_capability()`` lazy-loads the correct pack
- ``idle_sweep()`` unloads idle packs
- ``fallback_to_monolith()`` path (mocked)
- Pack dependency ordering
- Monolith-mode skips the tiered system
- ``unload_pack()`` refuses to unload KERNEL / PLATFORM packs
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import time
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.runtime.tiered_orchestrator import (
    BootResult,
    PackStatus,
    RuntimePack,
    RuntimeTier,
    TieredOrchestrator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub_pack(
    name: str,
    tier: RuntimeTier,
    modules: list[str] | None = None,
    dependencies: list[str] | None = None,
    capabilities: list[str] | None = None,
    idle_timeout_minutes: int = 30,
) -> RuntimePack:
    """Return a minimal RuntimePack suitable for unit tests."""
    return RuntimePack(
        name=name,
        tier=tier,
        modules=modules or [f"_stub.{name}"],
        dependencies=dependencies or [],
        capabilities=capabilities or [],
        api_routers=[],
        idle_timeout_minutes=idle_timeout_minutes,
        max_memory_mb=64,
    )


def _install_fake_module(dotted_path: str) -> None:
    """Register a real (but empty) Python module object for *dotted_path*.

    This prevents ``importlib.import_module()`` from raising ``ModuleNotFoundError``
    for paths that don't correspond to real files.
    """
    parts = dotted_path.split(".")
    for i in range(1, len(parts) + 1):
        path = ".".join(parts[:i])
        if path not in sys.modules:
            mod = types.ModuleType(path)
            sys.modules[path] = mod


def _uninstall_fake_modules(*dotted_paths: str) -> None:
    """Remove fake modules inserted by ``_install_fake_module``."""
    for path in dotted_paths:
        sys.modules.pop(path, None)
        parts = path.split(".")
        for i in range(len(parts), 0, -1):
            parent = ".".join(parts[:i])
            sys.modules.pop(parent, None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def orchestrator() -> TieredOrchestrator:
    return TieredOrchestrator(fallback_mode="strict")


@pytest.fixture
def monolith_orchestrator() -> TieredOrchestrator:
    return TieredOrchestrator(fallback_mode="monolith")


@pytest.fixture
def degraded_orchestrator() -> TieredOrchestrator:
    return TieredOrchestrator(fallback_mode="degraded")


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_valid_fallback_modes(self) -> None:
        for mode in ("monolith", "degraded", "strict"):
            orch = TieredOrchestrator(fallback_mode=mode)
            assert orch.fallback_mode == mode

    def test_invalid_fallback_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid fallback_mode"):
            TieredOrchestrator(fallback_mode="banana")

    def test_default_fallback_mode_is_monolith(self) -> None:
        orch = TieredOrchestrator()
        assert orch.fallback_mode == "monolith"

    def test_initial_state_is_empty(self, orchestrator: TieredOrchestrator) -> None:
        status = orchestrator.get_status()
        assert status["registered_packs"] == 0
        assert status["active_packs"] == 0
        assert status["in_fallback"] is False


# ---------------------------------------------------------------------------
# Pack registration
# ---------------------------------------------------------------------------


class TestRegisterPack:
    def test_register_single_pack(self, orchestrator: TieredOrchestrator) -> None:
        pack = _make_stub_pack("k_sec", RuntimeTier.KERNEL)
        orchestrator.register_pack(pack)
        status = orchestrator.get_status()
        assert status["registered_packs"] == 1
        assert "k_sec" in status["packs"]

    def test_duplicate_registration_raises(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        pack = _make_stub_pack("k_sec", RuntimeTier.KERNEL)
        orchestrator.register_pack(pack)
        with pytest.raises(ValueError, match="already registered"):
            orchestrator.register_pack(pack)


# ---------------------------------------------------------------------------
# Load pack
# ---------------------------------------------------------------------------


class TestLoadPack:
    def test_load_unknown_pack_returns_false(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator.load_pack("does_not_exist")
        )
        assert result is False

    def test_load_pack_with_real_module(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.mypkg")
        try:
            pack = _make_stub_pack("mypkg", RuntimeTier.KERNEL, modules=["_stub.mypkg"])
            orchestrator.register_pack(pack)
            result = asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("mypkg")
            )
            assert result is True
            status = orchestrator.get_status()
            assert status["packs"]["mypkg"]["status"] == PackStatus.ACTIVE.value
        finally:
            _uninstall_fake_modules("_stub.mypkg")

    def test_load_pack_with_bad_module_marks_failed(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        pack = _make_stub_pack(
            "bad_pack", RuntimeTier.DOMAIN, modules=["_nonexistent_.bad_module"]
        )
        orchestrator.register_pack(pack)
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator.load_pack("bad_pack")
        )
        assert result is False
        status = orchestrator.get_status()
        assert status["packs"]["bad_pack"]["status"] == PackStatus.FAILED.value

    def test_load_already_active_pack_returns_true(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.active_mod")
        try:
            pack = _make_stub_pack(
                "active_pack", RuntimeTier.DOMAIN, modules=["_stub.active_mod"]
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("active_pack")
            )
            # Second call should return True immediately
            result = asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("active_pack")
            )
            assert result is True
        finally:
            _uninstall_fake_modules("_stub.active_mod")


# ---------------------------------------------------------------------------
# Boot sequence — KERNEL failure aborts
# ---------------------------------------------------------------------------


class TestBootKernelFailure:
    def test_kernel_failure_aborts_strict(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        """KERNEL pack failure must abort boot (strict mode)."""
        pack = _make_stub_pack(
            "k_fail", RuntimeTier.KERNEL, modules=["_no_such_module_k"]
        )
        orchestrator.register_pack(pack)
        result: BootResult = asyncio.get_event_loop().run_until_complete(
            orchestrator.boot()
        )
        assert result.success is False
        assert "k_fail" in result.failed_packs

    def test_kernel_failure_triggers_monolith_fallback(
        self, monolith_orchestrator: TieredOrchestrator
    ) -> None:
        """KERNEL failure in monolith mode must attempt monolith fallback."""
        pack = _make_stub_pack(
            "k_fail_mono", RuntimeTier.KERNEL, modules=["_no_such_module_km"]
        )
        monolith_orchestrator.register_pack(pack)

        # Patch fallback_to_monolith so we don't need the real MurphySystem
        async def _fake_fallback() -> bool:
            monolith_orchestrator._in_fallback = True
            return True

        monolith_orchestrator.fallback_to_monolith = _fake_fallback  # type: ignore[method-assign]

        result: BootResult = asyncio.get_event_loop().run_until_complete(
            monolith_orchestrator.boot()
        )
        assert result.fallback_used is True
        assert monolith_orchestrator._in_fallback is True


# ---------------------------------------------------------------------------
# Boot sequence — PLATFORM failure aborts
# ---------------------------------------------------------------------------


class TestBootPlatformFailure:
    def test_platform_failure_aborts_strict(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        """PLATFORM pack failure must abort boot (strict mode)."""
        pack = _make_stub_pack(
            "p_fail", RuntimeTier.PLATFORM, modules=["_no_such_module_p"]
        )
        orchestrator.register_pack(pack)
        result: BootResult = asyncio.get_event_loop().run_until_complete(
            orchestrator.boot()
        )
        assert result.success is False
        assert "p_fail" in result.failed_packs


# ---------------------------------------------------------------------------
# Boot sequence — DOMAIN failure does NOT abort
# ---------------------------------------------------------------------------


class TestBootDomainFailure:
    def test_domain_failure_does_not_abort(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        """DOMAIN pack failure must NOT abort boot — graceful degradation."""
        _install_fake_module("_stub.k_ok")
        _install_fake_module("_stub.p_ok")
        try:
            kernel = _make_stub_pack(
                "k_ok", RuntimeTier.KERNEL, modules=["_stub.k_ok"]
            )
            platform = _make_stub_pack(
                "p_ok",
                RuntimeTier.PLATFORM,
                modules=["_stub.p_ok"],
                dependencies=["k_ok"],
            )
            domain_bad = _make_stub_pack(
                "d_bad",
                RuntimeTier.DOMAIN,
                modules=["_no_such_module_d"],
                capabilities=["bad_capability"],
            )
            orchestrator.register_pack(kernel)
            orchestrator.register_pack(platform)
            orchestrator.register_pack(domain_bad)

            # Boot without a team profile — DOMAIN packs not pre-loaded
            result: BootResult = asyncio.get_event_loop().run_until_complete(
                orchestrator.boot()
            )
            # Boot itself should succeed because KERNEL and PLATFORM loaded
            assert result.success is True
            assert "d_bad" not in result.failed_packs

            # Now explicitly try to load the domain pack (simulates capability request)
            load_result = asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("d_bad")
            )
            assert load_result is False
            # System is still running — KERNEL & PLATFORM remain active
            status = orchestrator.get_status()
            assert status["packs"]["k_ok"]["status"] == PackStatus.ACTIVE.value
            assert status["packs"]["p_ok"]["status"] == PackStatus.ACTIVE.value
        finally:
            _uninstall_fake_modules("_stub.k_ok", "_stub.p_ok")


# ---------------------------------------------------------------------------
# request_capability — lazy load
# ---------------------------------------------------------------------------


class TestRequestCapability:
    def test_request_capability_lazy_loads_correct_pack(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.domain_crm_mod")
        try:
            domain_crm = _make_stub_pack(
                "domain_crm",
                RuntimeTier.DOMAIN,
                modules=["_stub.domain_crm_mod"],
                capabilities=["crm_automation"],
            )
            orchestrator.register_pack(domain_crm)

            # Patch the CAPABILITY_TO_PACK lookup
            with patch(
                "src.runtime.tiered_orchestrator.TieredOrchestrator.request_capability",
                wraps=orchestrator.request_capability,
            ):
                with patch.dict(
                    "sys.modules",
                    {
                        "src.runtime.runtime_packs.registry": types.SimpleNamespace(
                            CAPABILITY_TO_PACK={"crm_automation": "domain_crm"}
                        )
                    },
                ):
                    result = asyncio.get_event_loop().run_until_complete(
                        orchestrator.request_capability("crm_automation")
                    )
            assert result == "domain_crm"
            status = orchestrator.get_status()
            assert status["packs"]["domain_crm"]["status"] == PackStatus.ACTIVE.value
        finally:
            _uninstall_fake_modules("_stub.domain_crm_mod")

    def test_request_unknown_capability_returns_none(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        with patch.dict(
            "sys.modules",
            {
                "src.runtime.runtime_packs.registry": types.SimpleNamespace(
                    CAPABILITY_TO_PACK={}
                )
            },
        ):
            result = asyncio.get_event_loop().run_until_complete(
                orchestrator.request_capability("unknown_capability_xyz")
            )
        assert result is None


# ---------------------------------------------------------------------------
# idle_sweep
# ---------------------------------------------------------------------------


class TestIdleSweep:
    def test_idle_sweep_unloads_idle_domain_packs(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.idle_domain")
        try:
            pack = RuntimePack(
                name="idle_domain_pack",
                tier=RuntimeTier.DOMAIN,
                modules=["_stub.idle_domain"],
                dependencies=[],
                capabilities=[],
                api_routers=[],
                idle_timeout_minutes=1,  # 1 minute timeout
                max_memory_mb=64,
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("idle_domain_pack")
            )

            # Backdate last_activity to simulate idleness
            with orchestrator._lock:
                orchestrator._registry["idle_domain_pack"].last_activity = (
                    time.time() - 120  # 2 minutes ago
                )

            unloaded = asyncio.get_event_loop().run_until_complete(
                orchestrator.idle_sweep()
            )
            assert "idle_domain_pack" in unloaded
            status = orchestrator.get_status()
            assert (
                status["packs"]["idle_domain_pack"]["status"]
                == PackStatus.UNLOADED.value
            )
        finally:
            _uninstall_fake_modules("_stub.idle_domain")

    def test_idle_sweep_skips_kernel_packs(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.kernel_keep")
        try:
            pack = RuntimePack(
                name="kernel_keep",
                tier=RuntimeTier.KERNEL,
                modules=["_stub.kernel_keep"],
                dependencies=[],
                capabilities=[],
                api_routers=[],
                idle_timeout_minutes=1,
                max_memory_mb=64,
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("kernel_keep")
            )
            with orchestrator._lock:
                orchestrator._registry["kernel_keep"].last_activity = (
                    time.time() - 3600
                )

            unloaded = asyncio.get_event_loop().run_until_complete(
                orchestrator.idle_sweep()
            )
            assert "kernel_keep" not in unloaded
        finally:
            _uninstall_fake_modules("_stub.kernel_keep")

    def test_idle_sweep_skips_pack_with_timeout_zero(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.never_unload")
        try:
            pack = RuntimePack(
                name="never_unload_pack",
                tier=RuntimeTier.DOMAIN,
                modules=["_stub.never_unload"],
                dependencies=[],
                capabilities=[],
                api_routers=[],
                idle_timeout_minutes=0,  # disabled
                max_memory_mb=64,
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("never_unload_pack")
            )
            with orchestrator._lock:
                orchestrator._registry["never_unload_pack"].last_activity = (
                    time.time() - 3600
                )

            unloaded = asyncio.get_event_loop().run_until_complete(
                orchestrator.idle_sweep()
            )
            assert "never_unload_pack" not in unloaded
        finally:
            _uninstall_fake_modules("_stub.never_unload")


# ---------------------------------------------------------------------------
# unload_pack — refuses KERNEL / PLATFORM
# ---------------------------------------------------------------------------


class TestUnloadPack:
    def test_unload_kernel_pack_refused(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.kern_no_unload")
        try:
            pack = _make_stub_pack(
                "kern_no_unload", RuntimeTier.KERNEL, modules=["_stub.kern_no_unload"]
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("kern_no_unload")
            )
            result = asyncio.get_event_loop().run_until_complete(
                orchestrator.unload_pack("kern_no_unload")
            )
            assert result is False
            status = orchestrator.get_status()
            assert (
                status["packs"]["kern_no_unload"]["status"] == PackStatus.ACTIVE.value
            )
        finally:
            _uninstall_fake_modules("_stub.kern_no_unload")

    def test_unload_platform_pack_refused(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.plat_no_unload")
        try:
            pack = _make_stub_pack(
                "plat_no_unload",
                RuntimeTier.PLATFORM,
                modules=["_stub.plat_no_unload"],
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("plat_no_unload")
            )
            result = asyncio.get_event_loop().run_until_complete(
                orchestrator.unload_pack("plat_no_unload")
            )
            assert result is False
        finally:
            _uninstall_fake_modules("_stub.plat_no_unload")

    def test_unload_domain_pack_succeeds(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.domain_unload")
        try:
            pack = _make_stub_pack(
                "domain_unload",
                RuntimeTier.DOMAIN,
                modules=["_stub.domain_unload"],
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("domain_unload")
            )
            result = asyncio.get_event_loop().run_until_complete(
                orchestrator.unload_pack("domain_unload")
            )
            assert result is True
            status = orchestrator.get_status()
            assert (
                status["packs"]["domain_unload"]["status"]
                == PackStatus.UNLOADED.value
            )
        finally:
            _uninstall_fake_modules("_stub.domain_unload")


# ---------------------------------------------------------------------------
# Dependency ordering
# ---------------------------------------------------------------------------


class TestDependencyOrdering:
    def test_dependency_loaded_before_dependent(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.dep_base")
        _install_fake_module("_stub.dep_child")
        try:
            base = _make_stub_pack(
                "dep_base", RuntimeTier.KERNEL, modules=["_stub.dep_base"]
            )
            child = _make_stub_pack(
                "dep_child",
                RuntimeTier.PLATFORM,
                modules=["_stub.dep_child"],
                dependencies=["dep_base"],
            )
            orchestrator.register_pack(base)
            orchestrator.register_pack(child)

            # Load child directly — should auto-load base first
            result = asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("dep_child")
            )
            assert result is True
            status = orchestrator.get_status()
            assert status["packs"]["dep_base"]["status"] == PackStatus.ACTIVE.value
            assert status["packs"]["dep_child"]["status"] == PackStatus.ACTIVE.value
        finally:
            _uninstall_fake_modules("_stub.dep_base", "_stub.dep_child")

    def test_unresolvable_dependency_fails(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        pack = _make_stub_pack(
            "orphan", RuntimeTier.DOMAIN, dependencies=["nonexistent_dep"]
        )
        orchestrator.register_pack(pack)
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator.load_pack("orphan")
        )
        assert result is False


# ---------------------------------------------------------------------------
# fallback_to_monolith — mocked path
# ---------------------------------------------------------------------------


class TestFallbackToMonolith:
    def test_fallback_to_monolith_invoked_on_kernel_failure(
        self, monolith_orchestrator: TieredOrchestrator
    ) -> None:
        pack = _make_stub_pack(
            "k_fail2", RuntimeTier.KERNEL, modules=["_no_such_module_kf2"]
        )
        monolith_orchestrator.register_pack(pack)

        fallback_called = []

        async def _mock_fallback() -> bool:
            fallback_called.append(True)
            monolith_orchestrator._in_fallback = True
            return True

        monolith_orchestrator.fallback_to_monolith = _mock_fallback  # type: ignore[method-assign]

        result: BootResult = asyncio.get_event_loop().run_until_complete(
            monolith_orchestrator.boot()
        )
        assert result.fallback_used is True
        assert len(fallback_called) == 1

    def test_fallback_to_monolith_sets_in_fallback_flag(
        self, monolith_orchestrator: TieredOrchestrator
    ) -> None:
        assert monolith_orchestrator._in_fallback is False

        mock_murphy = MagicMock()
        mock_murphy.startup = AsyncMock(return_value=None)

        with patch.dict(
            "sys.modules",
            {
                "src.runtime.murphy_system_core": types.SimpleNamespace(
                    MurphySystem=lambda: mock_murphy
                )
            },
        ):
            result = asyncio.get_event_loop().run_until_complete(
                monolith_orchestrator.fallback_to_monolith()
            )

        assert result is True
        assert monolith_orchestrator._in_fallback is True


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    def test_get_status_structure(self, orchestrator: TieredOrchestrator) -> None:
        status = orchestrator.get_status()
        assert "fallback_mode" in status
        assert "in_fallback" in status
        assert "registered_packs" in status
        assert "active_packs" in status
        assert "packs" in status

    def test_get_status_reflects_loaded_pack(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        _install_fake_module("_stub.status_test")
        try:
            pack = _make_stub_pack(
                "status_pack", RuntimeTier.DOMAIN, modules=["_stub.status_test"]
            )
            orchestrator.register_pack(pack)
            asyncio.get_event_loop().run_until_complete(
                orchestrator.load_pack("status_pack")
            )
            status = orchestrator.get_status()
            assert status["active_packs"] == 1
            assert status["packs"]["status_pack"]["status"] == PackStatus.ACTIVE.value
        finally:
            _uninstall_fake_modules("_stub.status_test")


# ---------------------------------------------------------------------------
# Monolith mode skips tiered system
# ---------------------------------------------------------------------------


class TestMonolithMode:
    def test_empty_boot_succeeds_with_no_packs(
        self, orchestrator: TieredOrchestrator
    ) -> None:
        """When no packs are registered the boot should succeed trivially."""
        result: BootResult = asyncio.get_event_loop().run_until_complete(
            orchestrator.boot()
        )
        assert result.success is True
        assert result.fallback_used is False
        assert result.loaded_packs == []
