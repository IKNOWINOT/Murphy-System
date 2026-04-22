"""Tests for src/runtime/subsystem_registry.py.

Class S Roadmap, Item 1 (scaffolding) — verifies the typed registry that will
replace the inline ``try/except ImportError`` blocks in
``murphy_production_server.py``.
"""

from __future__ import annotations

import pytest

from src.runtime import subsystem_registry as reg
from src.runtime.subsystem_registry import SubsystemRegistry


@pytest.fixture
def registry() -> SubsystemRegistry:
    return SubsystemRegistry()


def test_unknown_subsystem_is_unavailable(registry: SubsystemRegistry) -> None:
    assert registry.is_available("does_not_exist") is False
    assert registry.get("does_not_exist") is None
    assert registry.get("does_not_exist", default="fallback") == "fallback"
    with pytest.raises(ImportError):
        registry.require("does_not_exist")


def test_register_and_resolve_real_module(registry: SubsystemRegistry) -> None:
    # ``json`` is part of the stdlib and always importable.
    registry.register("json_mod", import_path="json")
    assert registry.is_available("json_mod") is True
    mod = registry.require("json_mod")
    assert mod.dumps({"a": 1}) == '{"a": 1}'


def test_register_with_attribute(registry: SubsystemRegistry) -> None:
    registry.register("json_dumps", import_path="json", attribute="dumps")
    fn = registry.require("json_dumps")
    assert callable(fn)
    assert fn([1, 2]) == "[1, 2]"


def test_unimportable_module_is_unavailable(registry: SubsystemRegistry) -> None:
    registry.register("ghost", import_path="this.module.does.not.exist")
    assert registry.is_available("ghost") is False
    assert registry.get("ghost") is None
    with pytest.raises(ImportError):
        registry.require("ghost")


def test_resolution_is_cached(registry: SubsystemRegistry, monkeypatch) -> None:
    """A second call must not re-attempt import."""
    import importlib

    calls = {"n": 0}
    real_import = importlib.import_module

    def counting_import(name: str, *args, **kwargs):
        calls["n"] += 1
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", counting_import)
    registry.register("json_mod", import_path="json")
    assert registry.is_available("json_mod")
    assert registry.is_available("json_mod")
    registry.get("json_mod")
    assert calls["n"] == 1


def test_idempotent_registration(registry: SubsystemRegistry) -> None:
    a = registry.register("json_mod", import_path="json")
    b = registry.register("json_mod", import_path="json")
    assert a is b


def test_conflicting_registration_raises(registry: SubsystemRegistry) -> None:
    registry.register("x", import_path="json")
    with pytest.raises(ValueError):
        registry.register("x", import_path="os")


def test_snapshot_reports_status(registry: SubsystemRegistry) -> None:
    registry.register("ok", import_path="json", description="json stdlib")
    registry.register("bad", import_path="this.does.not.exist")
    snap = registry.snapshot()
    assert snap["ok"]["status"] == "available"
    assert snap["ok"]["error"] is None
    assert snap["bad"]["status"] == "unavailable"
    assert snap["bad"]["error"] is not None
    # ModuleNotFoundError (a subclass of ImportError) is also acceptable.
    assert "Error" in snap["bad"]["error"]


def test_snapshot_without_resolve_keeps_unresolved(registry: SubsystemRegistry) -> None:
    registry.register("lazy", import_path="json")
    snap = registry.snapshot(resolve=False)
    assert snap["lazy"]["status"] == "unresolved"


def test_module_level_default_registry_isolated() -> None:
    """Module-level helpers operate on the shared default registry; clear it
    afterwards so other tests are not polluted."""
    name = "pytest_subsystem_registry_smoke"
    try:
        reg.register(name, import_path="json")
        assert reg.is_available(name)
        assert reg.require(name).dumps([]) == "[]"
        assert name in reg.snapshot()
    finally:
        # Best-effort cleanup: remove only our entry, not the whole registry.
        reg.default_registry.remove(name)
