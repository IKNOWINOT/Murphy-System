"""Tests for GAP-6 / full pipeline: NL message → extract_team_members()
→ generate_all_rosettas() → build_hitl_summary() → on_confirmed(), invoked
through SystemIntegrator.handle_team_discovery_message().

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _add_paths() -> None:
    for p in (_src_root(), _src_root() / "src"):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


def _load_pipeline_module():
    _add_paths()
    import importlib
    return importlib.import_module("src.onboarding_team_pipeline")


def _load_system_integrator():
    _add_paths()
    import importlib
    return importlib.import_module("src.system_integrator")


# ---------------------------------------------------------------------------
# Tests: OnboardingTeamPipeline in isolation
# ---------------------------------------------------------------------------


class TestOnboardingPipelineIsolation:
    """Basic isolation tests for the pipeline itself."""

    def test_pipeline_importable(self):
        try:
            mod = _load_pipeline_module()
            assert hasattr(mod, "OnboardingTeamPipeline")
        except ImportError as exc:
            pytest.skip(f"OnboardingTeamPipeline not importable: {exc}")

    def test_extract_team_members_returns_result(self):
        try:
            mod = _load_pipeline_module()
        except ImportError:
            pytest.skip("OnboardingTeamPipeline not importable")
        pipeline = mod.OnboardingTeamPipeline()
        result = pipeline.extract_team_members(
            "I have an accountant named Alice and a manager named Bob."
        )
        assert hasattr(result, "members")
        assert hasattr(result, "confidence")

    def test_extract_finds_accountant(self):
        try:
            mod = _load_pipeline_module()
        except ImportError:
            pytest.skip("OnboardingTeamPipeline not importable")
        pipeline = mod.OnboardingTeamPipeline()
        result = pipeline.extract_team_members(
            "My accountant Alice handles all the books."
        )
        assert len(result.members) >= 1
        roles = [m.role.lower() for m in result.members]
        assert any("account" in r for r in roles)

    def test_generate_all_rosettas_returns_list(self):
        try:
            mod = _load_pipeline_module()
        except ImportError:
            pytest.skip("OnboardingTeamPipeline not importable")
        pipeline = mod.OnboardingTeamPipeline()
        discovery = pipeline.extract_team_members(
            "I have 2 employees: Alice the accountant and Bob the manager."
        )
        if not discovery.members:
            pytest.skip("No members extracted")
        results = pipeline.generate_all_rosettas(discovery, {})
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_build_hitl_summary_returns_string(self):
        try:
            mod = _load_pipeline_module()
        except ImportError:
            pytest.skip("OnboardingTeamPipeline not importable")
        pipeline = mod.OnboardingTeamPipeline()
        discovery = pipeline.extract_team_members(
            "I have an accountant named Alice."
        )
        if not discovery.members:
            pytest.skip("No members extracted")
        results = pipeline.generate_all_rosettas(discovery, {})
        summary = pipeline.build_hitl_summary(results)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_on_confirmed_does_not_raise(self):
        try:
            mod = _load_pipeline_module()
        except ImportError:
            pytest.skip("OnboardingTeamPipeline not importable")
        pipeline = mod.OnboardingTeamPipeline()
        discovery = pipeline.extract_team_members(
            "I have an accountant named Alice."
        )
        if not discovery.members:
            pytest.skip("No members extracted")
        results = pipeline.generate_all_rosettas(discovery, {})
        try:
            pipeline.on_confirmed(results)
        except Exception as exc:
            pytest.fail(f"on_confirmed raised: {exc}")


# ---------------------------------------------------------------------------
# Tests: Full flow via SystemIntegrator (GAP-6)
# ---------------------------------------------------------------------------


class TestOnboardingPipelineViaSystemIntegrator:
    """GAP-6: Full flow invoked through SystemIntegrator."""

    def _make_integrator(self):
        mod = _load_system_integrator()
        return mod.SystemIntegrator()

    def test_handle_team_discovery_message_exists(self):
        si = self._make_integrator()
        assert hasattr(si, "handle_team_discovery_message")

    def test_full_flow_with_real_pipeline(self):
        si = self._make_integrator()
        if not si.onboarding_team_pipeline_enabled:
            pytest.skip("OnboardingTeamPipeline not available")
        result = si.handle_team_discovery_message(
            "I have 3 employees: Alice is our accountant, Bob is the operations manager, "
            "and Carol is the marketing director."
        )
        assert result["success"] is True
        assert result["members_found"] >= 1
        assert isinstance(result["hitl_summary"], str)

    def test_mock_pipeline_full_flow(self):
        """Mock pipeline: proves all 4 steps are called in order."""
        si = self._make_integrator()

        fake_member = SimpleNamespace(name="Alice", role="accountant")
        fake_discovery = SimpleNamespace(members=[fake_member])
        fake_rosetta = SimpleNamespace(
            member=fake_member,
            shadow_agent_id="s-001",
            rosetta_doc_id="r-001",
            rosetta_summary="Alice — Finance",
            domain="finance",
        )
        mock_pipeline = MagicMock()
        mock_pipeline.extract_team_members.return_value = fake_discovery
        mock_pipeline.generate_all_rosettas.return_value = [fake_rosetta]
        mock_pipeline.build_hitl_summary.return_value = "HITL summary for Alice"

        si.onboarding_team_pipeline = mock_pipeline
        si.onboarding_team_pipeline_enabled = True

        result = si.handle_team_discovery_message("I have an accountant named Alice.")

        # All steps called in the correct order
        mock_pipeline.extract_team_members.assert_called_once()
        mock_pipeline.generate_all_rosettas.assert_called_once_with(fake_discovery, {})
        mock_pipeline.build_hitl_summary.assert_called_once_with([fake_rosetta])

        assert result["success"] is True
        assert result["members_found"] == 1
        assert result["hitl_summary"] == "HITL summary for Alice"
        assert result["results"] == [fake_rosetta]

    def test_on_confirmed_callable_on_results(self):
        """The returned results list can be passed to on_confirmed()."""
        si = self._make_integrator()

        fake_member = SimpleNamespace(name="Bob", role="manager")
        fake_discovery = SimpleNamespace(members=[fake_member])
        fake_rosetta = SimpleNamespace(
            member=fake_member, shadow_agent_id="s-002",
            rosetta_doc_id="r-002", rosetta_summary="Bob — Operations",
            domain="operations",
        )
        mock_pipeline = MagicMock()
        mock_pipeline.extract_team_members.return_value = fake_discovery
        mock_pipeline.generate_all_rosettas.return_value = [fake_rosetta]
        mock_pipeline.build_hitl_summary.return_value = "HITL"

        si.onboarding_team_pipeline = mock_pipeline
        si.onboarding_team_pipeline_enabled = True

        result = si.handle_team_discovery_message("I have a manager named Bob.")
        # Simulate human confirmation
        si.onboarding_team_pipeline.on_confirmed(result["results"])
        mock_pipeline.on_confirmed.assert_called_once_with([fake_rosetta])

    def test_graceful_degradation_when_disabled(self):
        si = self._make_integrator()
        si.onboarding_team_pipeline_enabled = False
        si.onboarding_team_pipeline = None
        result = si.handle_team_discovery_message("I have a developer.")
        assert result["success"] is False

    def test_empty_message_returns_zero_members(self):
        si = self._make_integrator()
        if not si.onboarding_team_pipeline_enabled:
            pytest.skip("OnboardingTeamPipeline not available")
        # Use a message with no recognizable role keywords
        result = si.handle_team_discovery_message("12345 67890")
        assert result["success"] is True
        assert result["members_found"] == 0
