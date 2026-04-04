"""Tests for GAP-2: IntegrationBus._load_all() includes the 4 new modules,
each _load_*() method returns an instance or None gracefully, and get_status()
reports their presence.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "src"


def _load_integration_bus():
    src = _src_path()
    spec = importlib.util.spec_from_file_location(
        "integration_bus", src / "integration_bus.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["integration_bus"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIntegrationBusNewModuleAttributes:
    """GAP-2: IntegrationBus has private attributes for the 4 new modules."""

    def test_init_has_shadow_knostalgia_bridge(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_shadow_knostalgia_bridge")

    def test_init_has_dynamic_assist_engine(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_dynamic_assist_engine")

    def test_init_has_kfactor_calculator(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_kfactor_calculator")

    def test_init_has_onboarding_team_pipeline(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_onboarding_team_pipeline")

    def test_new_attributes_default_none(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert bus._shadow_knostalgia_bridge is None
        assert bus._dynamic_assist_engine is None
        assert bus._kfactor_calculator is None
        assert bus._onboarding_team_pipeline is None


class TestIntegrationBusLoaderMethods:
    """GAP-2: Each _load_*() method exists and returns None gracefully."""

    def test_load_shadow_knostalgia_bridge_exists(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_load_shadow_knostalgia_bridge")

    def test_load_dynamic_assist_engine_exists(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_load_dynamic_assist_engine")

    def test_load_kfactor_calculator_exists(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_load_kfactor_calculator")

    def test_load_onboarding_team_pipeline_exists(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert hasattr(bus, "_load_onboarding_team_pipeline")

    def test_load_shadow_bridge_graceful_on_import_error(self):
        """_load_shadow_knostalgia_bridge returns None when module is missing."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        # Force import to fail
        with patch.object(mod, "_try_import", return_value=None):
            result = bus._load_shadow_knostalgia_bridge()
        assert result is None

    def test_load_dynamic_assist_graceful_on_import_error(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        with patch.object(mod, "_try_import", return_value=None):
            result = bus._load_dynamic_assist_engine()
        assert result is None

    def test_load_kfactor_graceful_on_import_error(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        with patch.object(mod, "_try_import", return_value=None):
            result = bus._load_kfactor_calculator()
        assert result is None

    def test_load_onboarding_pipeline_graceful_on_import_error(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        with patch.object(mod, "_try_import", return_value=None):
            result = bus._load_onboarding_team_pipeline()
        assert result is None

    def test_load_dynamic_assist_returns_instance_when_available(self):
        """When DynamicAssistEngine is importable, the loader returns an instance."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        fake_instance = MagicMock()
        fake_cls = MagicMock(return_value=fake_instance)
        fake_module = MagicMock()
        fake_module.DynamicAssistEngine = fake_cls

        def _fake_import(path: str):
            if "dynamic_assist" in path:
                return fake_module
            return None

        with patch.object(mod, "_try_import", side_effect=_fake_import):
            result = bus._load_dynamic_assist_engine()
        assert result is fake_instance

    def test_load_kfactor_returns_instance_when_available(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        fake_instance = MagicMock()
        fake_cls = MagicMock(return_value=fake_instance)
        fake_module = MagicMock()
        fake_module.KFactorCalculator = fake_cls

        def _fake_import(path: str):
            if "kfactor" in path:
                return fake_module
            return None

        with patch.object(mod, "_try_import", side_effect=_fake_import):
            result = bus._load_kfactor_calculator()
        assert result is fake_instance

    def test_load_onboarding_returns_instance_when_available(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        fake_instance = MagicMock()
        fake_cls = MagicMock(return_value=fake_instance)
        fake_module = MagicMock()
        fake_module.OnboardingTeamPipeline = fake_cls

        def _fake_import(path: str):
            if "onboarding_team" in path:
                return fake_module
            return None

        with patch.object(mod, "_try_import", side_effect=_fake_import):
            result = bus._load_onboarding_team_pipeline()
        assert result is fake_instance


class TestIntegrationBusLoadAll:
    """GAP-2: _load_all() calls the new loaders."""

    def test_load_all_calls_shadow_knostalgia_bridge_loader(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        called = {}

        original = bus._load_shadow_knostalgia_bridge
        def _spy():
            called["shadow"] = True
            return None
        bus._load_shadow_knostalgia_bridge = _spy

        # Also stub the others so they don't fail
        bus._load_dynamic_assist_engine = lambda: None
        bus._load_kfactor_calculator = lambda: None
        bus._load_onboarding_team_pipeline = lambda: None

        bus._load_all()
        assert called.get("shadow") is True

    def test_load_all_calls_onboarding_pipeline_loader(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        called = {}

        def _spy():
            called["onboarding"] = True
            return None
        bus._load_onboarding_team_pipeline = _spy
        bus._load_shadow_knostalgia_bridge = lambda: None
        bus._load_dynamic_assist_engine = lambda: None
        bus._load_kfactor_calculator = lambda: None

        bus._load_all()
        assert called.get("onboarding") is True


class TestIntegrationBusGetStatus:
    """GAP-2: get_status() includes the 4 new module keys."""

    def test_get_status_contains_shadow_knostalgia_bridge_key(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        status = bus.get_status()
        assert "shadow_knostalgia_bridge" in status["modules"]

    def test_get_status_contains_dynamic_assist_engine_key(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        status = bus.get_status()
        assert "dynamic_assist_engine" in status["modules"]

    def test_get_status_contains_kfactor_calculator_key(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        status = bus.get_status()
        assert "kfactor_calculator" in status["modules"]

    def test_get_status_contains_onboarding_team_pipeline_key(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        status = bus.get_status()
        assert "onboarding_team_pipeline" in status["modules"]

    def test_get_status_false_before_init(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        status = bus.get_status()
        # Before initialize(), all new modules report False
        assert status["modules"]["shadow_knostalgia_bridge"] is False
        assert status["modules"]["dynamic_assist_engine"] is False
        assert status["modules"]["kfactor_calculator"] is False
        assert status["modules"]["onboarding_team_pipeline"] is False

    def test_initialize_is_idempotent_with_new_modules(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        bus.initialize()
        bus.initialize()
        assert bus._initialized is True
