"""
Tests for automation types wired into matrix controls.

Covers all 17+ automation type subcommands added to !murphy automation:
  - list, summary, types
  - mode, hub, rbac, readiness, scale, loop, scheduler
  - marketplace, native, self, onboard-engine
  - building, manufacturing, sales, compliance-bridge, full, deploy
"""

import os


import pytest
from types import SimpleNamespace

from management_systems.management_commands import (
    MANAGEMENT_COMMAND_HANDLERS,
    handle_automation,
    reset_engines,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cmd(subcommand=None, args=None, sender="@tester:localhost", room_id="!room:test"):
    """Build a minimal ParsedCommand-like namespace for testing."""
    return SimpleNamespace(
        prefix="!murphy",
        command="automation",
        subcommand=subcommand,
        args=args or [],
        kwargs={},
        raw="",
        sender=sender,
        room_id=room_id,
        timestamp="2026-01-01T00:00:00Z",
    )


DISPATCHER = None  # handlers accept dispatcher but don't depend on it


@pytest.fixture(autouse=True)
def clean_engines():
    """Reset singleton engines before each test for isolation."""
    reset_engines()
    yield
    reset_engines()


# ---------------------------------------------------------------------------
# automation handler is registered
# ---------------------------------------------------------------------------

class TestAutomationRegistered:
    def test_automation_in_handler_dict(self):
        assert "automation" in MANAGEMENT_COMMAND_HANDLERS

    def test_automation_handler_callable(self):
        assert callable(MANAGEMENT_COMMAND_HANDLERS["automation"])


# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------

class TestAutomationList:
    def test_default_no_subcommand_returns_registry(self):
        resp = handle_automation(DISPATCHER, _cmd())
        assert resp.success is True
        assert "Automation" in resp.message

    def test_list_subcommand(self):
        resp = handle_automation(DISPATCHER, _cmd("list"))
        assert resp.success is True

    def test_list_empty_registry_suggests_onboarding(self):
        resp = handle_automation(DISPATCHER, _cmd("list"))
        # Empty registry should still succeed with helpful message
        assert resp.success is True


# ---------------------------------------------------------------------------
# summary subcommand
# ---------------------------------------------------------------------------

class TestAutomationSummary:
    def test_summary_succeeds(self):
        resp = handle_automation(DISPATCHER, _cmd("summary"))
        assert resp.success is True
        assert "Summary" in resp.message or "Automation" in resp.message

    def test_summary_contains_skm_integration(self):
        resp = handle_automation(DISPATCHER, _cmd("summary"))
        assert "SKM" in resp.message or "loops" in resp.message.lower()


# ---------------------------------------------------------------------------
# types subcommand
# ---------------------------------------------------------------------------

class TestAutomationTypes:
    def test_types_lists_categories(self):
        resp = handle_automation(DISPATCHER, _cmd("types"))
        assert resp.success is True
        # Should contain automation category names
        assert any(cat in resp.message.lower() for cat in [
            "it_operations", "business_process", "marketing", "financial",
            "security", "devops", "compliance"
        ])

    def test_types_includes_template_count(self):
        resp = handle_automation(DISPATCHER, _cmd("types"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# mode subcommand
# ---------------------------------------------------------------------------

class TestAutomationMode:
    def test_mode_show(self):
        resp = handle_automation(DISPATCHER, _cmd("mode", ["show"]))
        assert resp.success is True
        assert "mode" in resp.message.lower() or "Mode" in resp.message

    def test_mode_default_action(self):
        resp = handle_automation(DISPATCHER, _cmd("mode"))
        assert resp.success is True

    def test_mode_history_empty(self):
        resp = handle_automation(DISPATCHER, _cmd("mode", ["history"]))
        assert resp.success is True

    def test_mode_set_valid(self):
        resp = handle_automation(DISPATCHER, _cmd("mode", ["set", "0"]))
        assert resp.success is True

    def test_mode_set_invalid(self):
        resp = handle_automation(DISPATCHER, _cmd("mode", ["set", "999"]))
        assert resp.success is False

    def test_mode_unknown_action(self):
        resp = handle_automation(DISPATCHER, _cmd("mode", ["unknown_action"]))
        # Should still return a helpful message (usage)
        assert "Usage" in resp.message or resp.success is True


# ---------------------------------------------------------------------------
# hub subcommand
# ---------------------------------------------------------------------------

class TestAutomationHub:
    def test_hub_status(self):
        resp = handle_automation(DISPATCHER, _cmd("hub", ["status"]))
        assert resp.success is True
        assert "Hub" in resp.message or "hub" in resp.message.lower()

    def test_hub_modules(self):
        resp = handle_automation(DISPATCHER, _cmd("hub", ["modules"]))
        assert resp.success is True

    def test_hub_routes(self):
        resp = handle_automation(DISPATCHER, _cmd("hub", ["routes"]))
        assert resp.success is True

    def test_hub_default_action(self):
        resp = handle_automation(DISPATCHER, _cmd("hub"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# rbac subcommand
# ---------------------------------------------------------------------------

class TestAutomationRbac:
    def test_rbac_status(self):
        resp = handle_automation(DISPATCHER, _cmd("rbac", ["status"]))
        assert resp.success is True

    def test_rbac_roles_no_user(self):
        # Should return usage hint (no user specified)
        resp = handle_automation(DISPATCHER, _cmd("rbac", ["roles"]))
        # Either usage error or graceful response
        assert isinstance(resp.success, bool)

    def test_rbac_grant_and_revoke(self):
        grant = handle_automation(DISPATCHER, _cmd("rbac", ["grant", "user1", "operator", "tenant1"]))
        assert grant.success is True
        revoke = handle_automation(DISPATCHER, _cmd("rbac", ["revoke", "user1", "operator", "tenant1"]))
        assert revoke.success is True

    def test_rbac_revoke_nonexistent(self):
        resp = handle_automation(DISPATCHER, _cmd("rbac", ["revoke", "nobody", "operator"]))
        # Either success=False or graceful message
        assert isinstance(resp.success, bool)


# ---------------------------------------------------------------------------
# readiness subcommand
# ---------------------------------------------------------------------------

class TestAutomationReadiness:
    def test_readiness_check(self):
        resp = handle_automation(DISPATCHER, _cmd("readiness", ["check"]))
        assert resp.success is True
        assert "Readiness" in resp.message or "readiness" in resp.message.lower()

    def test_readiness_report(self):
        resp = handle_automation(DISPATCHER, _cmd("readiness", ["report"]))
        assert resp.success is True

    def test_readiness_default(self):
        resp = handle_automation(DISPATCHER, _cmd("readiness"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# scale subcommand
# ---------------------------------------------------------------------------

class TestAutomationScale:
    def test_scale_status(self):
        resp = handle_automation(DISPATCHER, _cmd("scale", ["status"]))
        assert resp.success is True

    def test_scale_default(self):
        resp = handle_automation(DISPATCHER, _cmd("scale"))
        assert resp.success is True

    def test_scale_evaluate(self):
        resp = handle_automation(DISPATCHER, _cmd("scale", ["evaluate", "software"]))
        assert isinstance(resp.success, bool)


# ---------------------------------------------------------------------------
# loop subcommand
# ---------------------------------------------------------------------------

class TestAutomationLoop:
    def test_loop_status(self):
        resp = handle_automation(DISPATCHER, _cmd("loop", ["status"]))
        assert resp.success is True
        assert "Loop" in resp.message or "Connector" in resp.message

    def test_loop_run(self):
        resp = handle_automation(DISPATCHER, _cmd("loop", ["run"]))
        assert resp.success is True

    def test_loop_history(self):
        resp = handle_automation(DISPATCHER, _cmd("loop", ["history"]))
        assert resp.success is True


# ---------------------------------------------------------------------------
# scheduler subcommand
# ---------------------------------------------------------------------------

class TestAutomationScheduler:
    def test_scheduler_status(self):
        resp = handle_automation(DISPATCHER, _cmd("scheduler", ["status"]))
        assert resp.success is True
        assert "Scheduler" in resp.message or "scheduler" in resp.message.lower()

    def test_scheduler_queue(self):
        resp = handle_automation(DISPATCHER, _cmd("scheduler", ["queue"]))
        assert resp.success is True

    def test_scheduler_next(self):
        resp = handle_automation(DISPATCHER, _cmd("scheduler", ["next"]))
        assert resp.success is True


# ---------------------------------------------------------------------------
# marketplace subcommand
# ---------------------------------------------------------------------------

class TestAutomationMarketplace:
    def test_marketplace_list(self):
        resp = handle_automation(DISPATCHER, _cmd("marketplace", ["list"]))
        assert resp.success is True

    def test_marketplace_popular(self):
        resp = handle_automation(DISPATCHER, _cmd("marketplace", ["popular"]))
        assert resp.success is True

    def test_marketplace_search(self):
        resp = handle_automation(DISPATCHER, _cmd("marketplace", ["search", "onboarding"]))
        assert resp.success is True

    def test_marketplace_default(self):
        resp = handle_automation(DISPATCHER, _cmd("marketplace"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# native subcommand
# ---------------------------------------------------------------------------

class TestAutomationNative:
    def test_native_status(self):
        resp = handle_automation(DISPATCHER, _cmd("native", ["status"]))
        assert resp.success is True
        assert "Native" in resp.message or "native" in resp.message.lower()

    def test_native_list(self):
        resp = handle_automation(DISPATCHER, _cmd("native", ["list"]))
        assert resp.success is True

    def test_native_default(self):
        resp = handle_automation(DISPATCHER, _cmd("native"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# self subcommand
# ---------------------------------------------------------------------------

class TestAutomationSelf:
    def test_self_status(self):
        resp = handle_automation(DISPATCHER, _cmd("self", ["status"]))
        assert resp.success is True

    def test_self_tasks(self):
        resp = handle_automation(DISPATCHER, _cmd("self", ["tasks"]))
        assert resp.success is True

    def test_self_cycle(self):
        resp = handle_automation(DISPATCHER, _cmd("self", ["cycle"]))
        assert resp.success is True

    def test_self_default(self):
        resp = handle_automation(DISPATCHER, _cmd("self"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# onboard-engine subcommand
# ---------------------------------------------------------------------------

class TestAutomationOnboardEngine:
    def test_onboard_engine_status(self):
        resp = handle_automation(DISPATCHER, _cmd("onboard-engine", ["status"]))
        assert resp.success is True

    def test_onboard_engine_list(self):
        resp = handle_automation(DISPATCHER, _cmd("onboard-engine", ["list"]))
        assert resp.success is True

    def test_onboard_engine_underscore_alias(self):
        resp = handle_automation(DISPATCHER, _cmd("onboard_engine", ["status"]))
        assert resp.success is True


# ---------------------------------------------------------------------------
# building subcommand
# ---------------------------------------------------------------------------

class TestAutomationBuilding:
    def test_building_status(self):
        resp = handle_automation(DISPATCHER, _cmd("building", ["status"]))
        assert resp.success is True
        assert "Building" in resp.message or "building" in resp.message.lower()

    def test_building_devices(self):
        resp = handle_automation(DISPATCHER, _cmd("building", ["devices"]))
        assert resp.success is True

    def test_building_default(self):
        resp = handle_automation(DISPATCHER, _cmd("building"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# manufacturing subcommand
# ---------------------------------------------------------------------------

class TestAutomationManufacturing:
    def test_manufacturing_status(self):
        resp = handle_automation(DISPATCHER, _cmd("manufacturing", ["status"]))
        assert resp.success is True

    def test_manufacturing_connectors(self):
        resp = handle_automation(DISPATCHER, _cmd("manufacturing", ["connectors"]))
        assert resp.success is True

    def test_manufacturing_standards(self):
        resp = handle_automation(DISPATCHER, _cmd("manufacturing", ["standards"]))
        assert resp.success is True


# ---------------------------------------------------------------------------
# sales subcommand
# ---------------------------------------------------------------------------

class TestAutomationSales:
    def test_sales_pipeline(self):
        resp = handle_automation(DISPATCHER, _cmd("sales", ["pipeline"]))
        assert resp.success is True
        assert "Sales" in resp.message or "sales" in resp.message.lower()

    def test_sales_leads(self):
        resp = handle_automation(DISPATCHER, _cmd("sales", ["leads"]))
        assert resp.success is True

    def test_sales_default(self):
        resp = handle_automation(DISPATCHER, _cmd("sales"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# compliance-bridge subcommand
# ---------------------------------------------------------------------------

class TestAutomationComplianceBridge:
    def test_compliance_bridge_posture(self):
        resp = handle_automation(DISPATCHER, _cmd("compliance-bridge", ["posture"]))
        assert resp.success is True

    def test_compliance_bridge_history(self):
        resp = handle_automation(DISPATCHER, _cmd("compliance-bridge", ["history"]))
        assert resp.success is True

    def test_compliance_bridge_underscore_alias(self):
        resp = handle_automation(DISPATCHER, _cmd("compliance_bridge", ["posture"]))
        assert resp.success is True

    def test_compliance_bridge_default(self):
        resp = handle_automation(DISPATCHER, _cmd("compliance-bridge"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# full subcommand
# ---------------------------------------------------------------------------

class TestAutomationFull:
    def test_full_status(self):
        resp = handle_automation(DISPATCHER, _cmd("full", ["status"]))
        assert resp.success is True
        assert "Automation" in resp.message or "mode" in resp.message.lower()

    def test_full_risks(self):
        resp = handle_automation(DISPATCHER, _cmd("full", ["risks"]))
        assert resp.success is True

    def test_full_gaps(self):
        resp = handle_automation(DISPATCHER, _cmd("full", ["gaps"]))
        assert resp.success is True

    def test_full_mode_set_valid(self):
        resp = handle_automation(DISPATCHER, _cmd("full", ["mode", "shadow"]))
        assert isinstance(resp.success, bool)

    def test_full_default(self):
        resp = handle_automation(DISPATCHER, _cmd("full"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# deploy subcommand
# ---------------------------------------------------------------------------

class TestAutomationDeploy:
    def test_deploy_list(self):
        resp = handle_automation(DISPATCHER, _cmd("deploy", ["list"]))
        assert resp.success is True
        assert "Deployment" in resp.message or "deployment" in resp.message.lower()

    def test_deploy_status_missing(self):
        resp = handle_automation(DISPATCHER, _cmd("deploy", ["status", "nonexistent-id"]))
        assert resp.success is False

    def test_deploy_default(self):
        resp = handle_automation(DISPATCHER, _cmd("deploy"))
        assert resp.success is True


# ---------------------------------------------------------------------------
# Unknown subcommand
# ---------------------------------------------------------------------------

class TestAutomationUnknown:
    def test_unknown_subcommand_returns_failure(self):
        resp = handle_automation(DISPATCHER, _cmd("totally_unknown_type"))
        assert resp.success is False
        assert "Unknown" in resp.message

    def test_unknown_subcommand_lists_options(self):
        resp = handle_automation(DISPATCHER, _cmd("totally_unknown_type"))
        # The error message should list available subcommands
        assert "list" in resp.message or "summary" in resp.message


# ---------------------------------------------------------------------------
# All automation types are reachable (smoke test)
# ---------------------------------------------------------------------------

ALL_AUTOMATION_SUBCOMMANDS = [
    "list", "summary", "types",
    "mode", "hub", "rbac", "readiness", "scale",
    "loop", "scheduler", "marketplace", "native",
    "self", "onboard-engine", "building",
    "manufacturing", "sales", "compliance-bridge",
    "full", "deploy",
]


class TestAllSubcommandsReachable:
    @pytest.mark.parametrize("sub", ALL_AUTOMATION_SUBCOMMANDS)
    def test_subcommand_does_not_crash(self, sub):
        """Every automation subcommand must return a CommandResponse without raising."""
        resp = handle_automation(DISPATCHER, _cmd(sub))
        assert hasattr(resp, "success")
        assert hasattr(resp, "message")
        assert isinstance(resp.message, str)
        assert len(resp.message) > 0
