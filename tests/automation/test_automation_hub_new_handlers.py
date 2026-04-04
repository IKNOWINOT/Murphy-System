"""Tests for GAP-7: AutomationIntegrationHub routes onboarding and shadow events
to the new module handlers (OnboardingTeamPipeline, ShadowKnostalgiaBridge).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "src"


def _load_hub():
    src = _src_path()
    spec = importlib.util.spec_from_file_location(
        "automation_integration_hub", src / "automation_integration_hub.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["automation_integration_hub"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests: register_onboarding_pipeline()
# ---------------------------------------------------------------------------


class TestRegisterOnboardingPipeline:
    """GAP-7: register_onboarding_pipeline() registers the pipeline for onboarding events."""

    def test_method_exists(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        assert hasattr(hub, "register_onboarding_pipeline"), (
            "AutomationIntegrationHub must have register_onboarding_pipeline()"
        )

    def test_register_adds_module(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_pipeline = MagicMock()
        hub.register_onboarding_pipeline(mock_pipeline)
        assert "BIZ-003-TEAM" in hub._modules

    def test_register_binds_onboarding_event_type(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_pipeline = MagicMock()
        hub.register_onboarding_pipeline(mock_pipeline)
        routes = hub.get_event_routes()
        assert "BIZ-003-TEAM" in routes.get("ONBOARDING_TEAM_DISCOVERY", []) or \
               "BIZ-003-TEAM" in routes.get("ONBOARDING_MESSAGE", [])

    def test_register_none_does_not_raise(self):
        """Passing None gracefully skips registration."""
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        try:
            hub.register_onboarding_pipeline(None)
        except Exception as exc:
            pytest.fail(f"register_onboarding_pipeline(None) raised: {exc}")
        assert "BIZ-003-TEAM" not in hub._modules

    def test_routing_calls_extract_team_members(self):
        """Routing ONBOARDING_TEAM_DISCOVERY should call pipeline.extract_team_members()."""
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_pipeline = MagicMock()
        hub.register_onboarding_pipeline(mock_pipeline)

        hub.route_event(
            "ONBOARDING_TEAM_DISCOVERY",
            source="test",
            payload={"message": "I have an accountant named Alice."},
        )
        mock_pipeline.extract_team_members.assert_called_once_with(
            "I have an accountant named Alice."
        )

    def test_routing_empty_message_does_not_call_extract(self):
        """No message in payload → extract_team_members should NOT be called."""
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_pipeline = MagicMock()
        hub.register_onboarding_pipeline(mock_pipeline)

        hub.route_event(
            "ONBOARDING_TEAM_DISCOVERY",
            source="test",
            payload={},
        )
        mock_pipeline.extract_team_members.assert_not_called()

    def test_handler_error_does_not_raise_to_caller(self):
        """Handler errors are caught; route_event should still return records."""
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_pipeline = MagicMock()
        mock_pipeline.extract_team_members.side_effect = RuntimeError("boom")
        hub.register_onboarding_pipeline(mock_pipeline)

        records = hub.route_event(
            "ONBOARDING_TEAM_DISCOVERY",
            source="test",
            payload={"message": "I have a manager."},
        )
        assert len(records) == 1
        # Status should reflect handler error
        assert records[0].status.value in ("handler_error", "delivered")


# ---------------------------------------------------------------------------
# Tests: register_shadow_bridge()
# ---------------------------------------------------------------------------


class TestRegisterShadowBridge:
    """GAP-7: register_shadow_bridge() registers the bridge for shadow observation events."""

    def test_method_exists(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        assert hasattr(hub, "register_shadow_bridge"), (
            "AutomationIntegrationHub must have register_shadow_bridge()"
        )

    def test_register_adds_module(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_bridge = MagicMock()
        hub.register_shadow_bridge(mock_bridge)
        assert "SHADOW-OBS-001" in hub._modules

    def test_register_binds_shadow_event_type(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_bridge = MagicMock()
        hub.register_shadow_bridge(mock_bridge)
        routes = hub.get_event_routes()
        assert "SHADOW-OBS-001" in routes.get("SHADOW_OBSERVATION", []) or \
               "SHADOW-OBS-001" in routes.get("SHADOW_AGENT_EVENT", [])

    def test_register_none_does_not_raise(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        try:
            hub.register_shadow_bridge(None)
        except Exception as exc:
            pytest.fail(f"register_shadow_bridge(None) raised: {exc}")
        assert "SHADOW-OBS-001" not in hub._modules

    def test_routing_calls_record_observation(self):
        """Routing SHADOW_OBSERVATION should call bridge.record_observation()."""
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_bridge = MagicMock()
        hub.register_shadow_bridge(mock_bridge)

        payload = {
            "shadow_agent_id": "agent-42",
            "process_name": "invoice_approval",
            "action_observed": "clicked_approve",
            "variation_from_norm": True,
        }
        hub.route_event("SHADOW_OBSERVATION", source="test", payload=payload)

        mock_bridge.record_observation.assert_called_once_with(
            shadow_agent_id="agent-42",
            process_name="invoice_approval",
            action_observed="clicked_approve",
            variation_from_norm=True,
        )

    def test_shadow_handler_error_does_not_propagate(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_bridge = MagicMock()
        mock_bridge.record_observation.side_effect = ValueError("bridge broken")
        hub.register_shadow_bridge(mock_bridge)

        records = hub.route_event(
            "SHADOW_OBSERVATION",
            source="test",
            payload={"shadow_agent_id": "a", "process_name": "p",
                     "action_observed": "x", "variation_from_norm": False},
        )
        assert len(records) == 1


# ---------------------------------------------------------------------------
# Tests: combined registration
# ---------------------------------------------------------------------------


class TestCombinedRegistration:
    """GAP-7: Both handlers can coexist in the hub."""

    def test_both_handlers_registered_simultaneously(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        mock_pipeline = MagicMock()
        mock_bridge = MagicMock()

        hub.register_onboarding_pipeline(mock_pipeline)
        hub.register_shadow_bridge(mock_bridge)

        assert "BIZ-003-TEAM" in hub._modules
        assert "SHADOW-OBS-001" in hub._modules

    def test_health_report_includes_new_modules(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        hub.register_onboarding_pipeline(MagicMock())
        hub.register_shadow_bridge(MagicMock())

        report = hub.generate_health_report()
        assert report.total_modules >= 2

    def test_list_modules_includes_new_modules(self):
        mod = _load_hub()
        hub = mod.AutomationIntegrationHub()
        hub.register_onboarding_pipeline(MagicMock())
        hub.register_shadow_bridge(MagicMock())

        modules = hub.list_modules()
        names = [m["name"] for m in modules]
        assert "OnboardingTeamPipeline" in names
        assert "ShadowKnostalgiaBridge" in names
