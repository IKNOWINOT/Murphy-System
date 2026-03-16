"""Tests for GAP-1: SystemIntegrator initializes with the 4 new modules
(or gracefully degrades), and the wired public methods are reachable.

Also covers GAP-6: handle_team_discovery_message() exists and is reachable
through SystemIntegrator.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src_root() -> Path:
    return Path(__file__).resolve().parent.parent



def _load_system_integrator():
    import importlib
    mod = importlib.import_module("src.system_integrator")
    return mod


# ---------------------------------------------------------------------------
# Tests: _enabled flags
# ---------------------------------------------------------------------------


class TestSystemIntegratorNewModuleFlags:
    """GAP-1: SystemIntegrator has _enabled flags for the 4 new modules."""

    def _make_integrator(self):
        mod = _load_system_integrator()
        return mod.SystemIntegrator()

    def test_has_dynamic_assist_enabled_flag(self):
        si = self._make_integrator()
        assert hasattr(si, "dynamic_assist_enabled")

    def test_has_shadow_knostalgia_bridge_enabled_flag(self):
        si = self._make_integrator()
        assert hasattr(si, "shadow_knostalgia_bridge_enabled")

    def test_has_onboarding_team_pipeline_enabled_flag(self):
        si = self._make_integrator()
        assert hasattr(si, "onboarding_team_pipeline_enabled")

    def test_enabled_flags_are_bool(self):
        si = self._make_integrator()
        assert isinstance(si.dynamic_assist_enabled, bool)
        assert isinstance(si.shadow_knostalgia_bridge_enabled, bool)
        assert isinstance(si.onboarding_team_pipeline_enabled, bool)

    def test_new_module_attributes_present(self):
        si = self._make_integrator()
        assert hasattr(si, "dynamic_assist_engine")
        assert hasattr(si, "kfactor_calculator")
        assert hasattr(si, "shadow_knostalgia_bridge")
        assert hasattr(si, "onboarding_team_pipeline")


# ---------------------------------------------------------------------------
# Tests: evaluate_dynamic_assist_mode()
# ---------------------------------------------------------------------------


class TestSystemIntegratorEvaluateDynamicAssistMode:
    """GAP-1: evaluate_dynamic_assist_mode() is reachable and graceful."""

    def _make_integrator(self):
        mod = _load_system_integrator()
        return mod.SystemIntegrator()

    def test_method_exists(self):
        si = self._make_integrator()
        assert hasattr(si, "evaluate_dynamic_assist_mode"), (
            "SystemIntegrator must have evaluate_dynamic_assist_mode()"
        )

    def test_returns_dict(self):
        si = self._make_integrator()
        result = si.evaluate_dynamic_assist_mode()
        assert isinstance(result, dict)

    def test_returns_success_key(self):
        si = self._make_integrator()
        result = si.evaluate_dynamic_assist_mode()
        assert "success" in result

    def test_graceful_when_bridge_disabled(self):
        si = self._make_integrator()
        si.shadow_knostalgia_bridge_enabled = False
        si.shadow_knostalgia_bridge = None
        result = si.evaluate_dynamic_assist_mode()
        assert result["success"] is False
        assert "error" in result

    def test_calls_bridge_compute_assist_mode(self):
        si = self._make_integrator()
        fake_output = SimpleNamespace(
            observe_only=False,
            may_suggest=True,
            may_execute=True,
            requires_approval=False,
            computed_epsilon=0.15,
            computed_learning_rate=0.08,
            computed_confidence_threshold=0.7,
        )
        mock_bridge = MagicMock()
        mock_bridge.compute_assist_mode.return_value = fake_output
        si.shadow_knostalgia_bridge = mock_bridge
        si.shadow_knostalgia_bridge_enabled = True

        result = si.evaluate_dynamic_assist_mode()
        assert result["success"] is True
        assert result["computed_epsilon"] == 0.15
        assert result["computed_learning_rate"] == 0.08
        mock_bridge.compute_assist_mode.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: handle_team_discovery_message() (GAP-6)
# ---------------------------------------------------------------------------


class TestSystemIntegratorHandleTeamDiscovery:
    """GAP-6 / GAP-1: handle_team_discovery_message() is reachable via SystemIntegrator."""

    def _make_integrator(self):
        mod = _load_system_integrator()
        return mod.SystemIntegrator()

    def test_method_exists(self):
        si = self._make_integrator()
        assert hasattr(si, "handle_team_discovery_message"), (
            "SystemIntegrator must have handle_team_discovery_message()"
        )

    def test_returns_dict(self):
        si = self._make_integrator()
        result = si.handle_team_discovery_message("I have an accountant named Alice.")
        assert isinstance(result, dict)

    def test_returns_success_key(self):
        si = self._make_integrator()
        result = si.handle_team_discovery_message("test message")
        assert "success" in result

    def test_graceful_when_pipeline_disabled(self):
        si = self._make_integrator()
        si.onboarding_team_pipeline_enabled = False
        si.onboarding_team_pipeline = None
        result = si.handle_team_discovery_message("I have a developer named Bob.")
        assert result["success"] is False
        assert "error" in result

    def test_no_members_found(self):
        si = self._make_integrator()
        if not si.onboarding_team_pipeline_enabled:
            pytest.skip("OnboardingTeamPipeline not available")
        # Use a message that contains no recognizable role keywords
        result = si.handle_team_discovery_message("12345 67890")
        assert result["success"] is True
        assert result["members_found"] == 0

    def test_full_flow_with_mock_pipeline(self):
        """Full flow: message → extract → generate → summary → result dict."""
        si = self._make_integrator()

        fake_member = SimpleNamespace(name="Alice", role="accountant")
        fake_discovery = SimpleNamespace(members=[fake_member])
        fake_result = SimpleNamespace(
            member=fake_member,
            shadow_agent_id="shadow-001",
            rosetta_doc_id="rosetta-001",
            rosetta_summary="Alice — Finance automation",
            domain="finance",
        )
        mock_pipeline = MagicMock()
        mock_pipeline.extract_team_members.return_value = fake_discovery
        mock_pipeline.generate_all_rosettas.return_value = [fake_result]
        mock_pipeline.build_hitl_summary.return_value = "HITL: 1 member ready."

        si.onboarding_team_pipeline = mock_pipeline
        si.onboarding_team_pipeline_enabled = True

        result = si.handle_team_discovery_message("I have an accountant named Alice.")
        assert result["success"] is True
        assert result["members_found"] == 1
        assert "HITL" in result["hitl_summary"]
        assert len(result["results"]) == 1

        mock_pipeline.extract_team_members.assert_called_once()
        mock_pipeline.generate_all_rosettas.assert_called_once()
        mock_pipeline.build_hitl_summary.assert_called_once()

    def test_real_pipeline_extract_accountant(self):
        """If OnboardingTeamPipeline is available, real NL extraction works."""
        si = self._make_integrator()
        if not si.onboarding_team_pipeline_enabled:
            pytest.skip("OnboardingTeamPipeline not available in this environment")

        result = si.handle_team_discovery_message(
            "I have 2 employees: Alice is our accountant and Bob is the operations manager."
        )
        assert result["success"] is True
        assert result["members_found"] >= 1
        assert isinstance(result["hitl_summary"], str)
        assert len(result["hitl_summary"]) > 0
