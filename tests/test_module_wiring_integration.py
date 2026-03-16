"""Integration tests for module wiring — PR #249–#252 commissioning.

Validates that:
- All 6 new modules appear in MODULE_MANIFEST with non-empty emits
- The time_tracking manifest entry now declares emits
- The manifest emits/consumes form valid event chains
- CEOBranch publishes to EventBackbone when one is provided
- ProductionAssistantOrchestrator publishes gate events to EventBackbone
- The time-tracking bridge forwards InvoicingHookManager events to EventBackbone
- All 6 new modules are registered in AutomationIntegrationHub

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from matrix_bridge.module_manifest import MODULE_MANIFEST, manifest_by_module
from automation_integration_hub import AutomationIntegrationHub, ModulePhase


# ---------------------------------------------------------------------------
# Constants — the 6 new module names that must be wired
# ---------------------------------------------------------------------------
NEW_MODULES = [
    "self_introspection_module",
    "self_codebase_swarm",
    "cutsheet_engine",
    "visual_swarm_builder",
    "ceo_branch_activation",
    "production_assistant_engine",
]

NEW_MODULE_DESIGN_LABELS = {
    "self_introspection_module": "INTRO-001",
    "self_codebase_swarm": "SCS-001",
    "cutsheet_engine": "CSE-001",
    "visual_swarm_builder": "VSB-001",
    "ceo_branch_activation": "CEO-002",
    "production_assistant_engine": "PROD-ENG-001",
}


# ===========================================================================
# 1. Module Manifest — new modules present and non-empty emits
# ===========================================================================

class TestModuleManifestNewModules:
    """All 6 new modules must appear in MODULE_MANIFEST with emits declared."""

    def test_all_new_modules_in_manifest(self):
        module_names = {e.module for e in MODULE_MANIFEST}
        missing = [m for m in NEW_MODULES if m not in module_names]
        assert missing == [], f"Missing manifest entries: {missing}"

    @pytest.mark.parametrize("module_name", NEW_MODULES)
    def test_new_module_has_non_empty_emits(self, module_name):
        by_module = manifest_by_module()
        entry = by_module[module_name]
        assert entry.emits, (
            f"{module_name} has empty emits — must declare at least one event type"
        )

    @pytest.mark.parametrize("module_name", NEW_MODULES)
    def test_new_module_has_room(self, module_name):
        by_module = manifest_by_module()
        entry = by_module[module_name]
        assert entry.room, f"{module_name} has no room declared"

    @pytest.mark.parametrize("module_name", NEW_MODULES)
    def test_new_module_has_commands(self, module_name):
        by_module = manifest_by_module()
        entry = by_module[module_name]
        assert entry.commands, f"{module_name} has no commands declared"

    @pytest.mark.parametrize("module_name", NEW_MODULES)
    def test_new_module_has_description(self, module_name):
        by_module = manifest_by_module()
        entry = by_module[module_name]
        assert entry.description, f"{module_name} has no description"


# ===========================================================================
# 2. time_tracking manifest entry — emits updated
# ===========================================================================

class TestTimeTrackingManifestEmits:
    """time_tracking manifest entry must declare its emitted events."""

    def test_time_tracking_has_non_empty_emits(self):
        by_module = manifest_by_module()
        assert "time_tracking" in by_module, "time_tracking missing from manifest"
        entry = by_module["time_tracking"]
        assert entry.emits, "time_tracking.emits must be non-empty"

    def test_time_tracking_emits_expected_events(self):
        by_module = manifest_by_module()
        entry = by_module["time_tracking"]
        expected = {
            "entry_approved",
            "entry_invoiced",
            "invoice_generated",
            "billable_threshold_reached",
        }
        assert expected.issubset(set(entry.emits)), (
            f"time_tracking.emits missing: {expected - set(entry.emits)}"
        )


# ===========================================================================
# 3. Event chain validity — every consumed event is emitted somewhere
# ===========================================================================

class TestEventChainValidity:
    """Every consumed event declared by the 6 new modules must be emitted by at least one module."""

    def test_new_module_consumed_events_have_producers(self):
        all_emitted: set = set()
        for entry in MODULE_MANIFEST:
            all_emitted.update(entry.emits)

        by_module = manifest_by_module()
        broken_chains: List[str] = []
        for module_name in NEW_MODULES:
            entry = by_module[module_name]
            for consumed in entry.consumes:
                if consumed not in all_emitted:
                    broken_chains.append(
                        f"{entry.module} consumes '{consumed}' but no module emits it"
                    )

        assert broken_chains == [], (
            "Broken event chains for new modules (consumed but never emitted):\n"
            + "\n".join(broken_chains)
        )


# ===========================================================================
# 4. AutomationIntegrationHub — all 6 modules register without error
# ===========================================================================

class TestAutomationIntegrationHubRegistration:
    """All 6 new modules must be registerable via dedicated hub methods."""

    def test_register_self_introspection_module(self):
        hub = AutomationIntegrationHub()
        hub.register_self_introspection_module()
        assert hub.get_module("INTRO-001") is not None

    def test_register_self_codebase_swarm(self):
        hub = AutomationIntegrationHub()
        hub.register_self_codebase_swarm()
        assert hub.get_module("SCS-001") is not None

    def test_register_cutsheet_engine(self):
        hub = AutomationIntegrationHub()
        hub.register_cutsheet_engine()
        assert hub.get_module("CSE-001") is not None

    def test_register_visual_swarm_builder(self):
        hub = AutomationIntegrationHub()
        hub.register_visual_swarm_builder()
        assert hub.get_module("VSB-001") is not None

    def test_register_ceo_branch_activation(self):
        hub = AutomationIntegrationHub()
        hub.register_ceo_branch_activation()
        assert hub.get_module("CEO-002") is not None

    def test_register_production_assistant_engine(self):
        hub = AutomationIntegrationHub()
        hub.register_production_assistant_engine()
        assert hub.get_module("PROD-ENG-001") is not None

    def test_all_six_registered_together(self):
        hub = AutomationIntegrationHub()
        hub.register_self_introspection_module()
        hub.register_self_codebase_swarm()
        hub.register_cutsheet_engine()
        hub.register_visual_swarm_builder()
        hub.register_ceo_branch_activation()
        hub.register_production_assistant_engine()

        for label in NEW_MODULE_DESIGN_LABELS.values():
            assert hub.get_module(label) is not None, f"{label} not found in hub"

    def test_registration_with_module_instances(self):
        """Registration with real-ish module instances routes events correctly."""
        hub = AutomationIntegrationHub()

        handled: List[str] = []

        class _FakeModule:
            def handle_event(self, event_type: str, payload: dict) -> None:
                handled.append(event_type)

        hub.register_self_introspection_module(_FakeModule())
        hub.route_event("TASK_SUBMITTED", source="test", payload={})
        assert "TASK_SUBMITTED" in handled


# ===========================================================================
# 5. CEOBranch — publishes telemetry to EventBackbone when provided
# ===========================================================================

class TestCEOBranchEventBackboneWiring:
    """CEOBranch must publish telemetry events to an optional EventBackbone."""

    def test_ceo_branch_accepts_event_backbone_param(self):
        from ceo_branch_activation import CEOBranch
        backbone = MagicMock()
        branch = CEOBranch(tick_interval=99999, event_backbone=backbone)
        assert branch._backbone is backbone

    def test_activate_publishes_to_backbone(self):
        from ceo_branch_activation import CEOBranch
        published: List[str] = []

        class _FakeBackbone:
            def publish(self, event: str, payload: dict) -> None:
                published.append(event)

        branch = CEOBranch(tick_interval=99999, event_backbone=_FakeBackbone())
        branch.activate()
        branch.deactivate()

        assert "ceo_branch_activated" in published
        assert "ceo_branch_deactivated" in published

    def test_no_backbone_does_not_raise(self):
        """When event_backbone=None, CEOBranch must still work correctly."""
        from ceo_branch_activation import CEOBranch
        branch = CEOBranch(tick_interval=99999)
        branch.activate()
        telemetry = branch.get_telemetry()
        assert any(e.get("event") == "ceo_branch_activated" for e in telemetry)
        branch.deactivate()

    def test_backbone_failure_does_not_crash_branch(self):
        """If backbone.publish raises, CEOBranch must still record telemetry."""
        from ceo_branch_activation import CEOBranch

        class _BrokenBackbone:
            def publish(self, event: str, payload: dict) -> None:
                raise RuntimeError("backbone down")

        branch = CEOBranch(tick_interval=99999, event_backbone=_BrokenBackbone())
        # Should not raise
        branch.activate()
        telemetry = branch.get_telemetry()
        assert any(e.get("event") == "ceo_branch_activated" for e in telemetry)
        branch.deactivate()


# ===========================================================================
# 6. ProductionAssistantOrchestrator — publishes gate events to EventBackbone
# ===========================================================================

class TestProductionAssistantOrchestratorWiring:
    """ProductionAssistantOrchestrator must publish events when backbone is wired."""

    def test_orchestrator_accepts_event_backbone(self):
        from production_assistant_engine import ProductionAssistantOrchestrator
        backbone = MagicMock()
        orch = ProductionAssistantOrchestrator(event_backbone=backbone)
        assert orch._backbone is backbone

    def test_intake_request_succeeds_with_backbone(self):
        from production_assistant_engine import ProductionAssistantOrchestrator
        published: List[str] = []

        class _FakeBackbone:
            def publish(self, event: Any, payload: dict) -> None:
                published.append(str(event))

        orch = ProductionAssistantOrchestrator(event_backbone=_FakeBackbone())
        profile = orch.intake_request(
            title="Test project",
            country="US",
            industry="construction",
            functions=["project_management"],
        )
        assert profile is not None

    def test_no_backbone_orchestrator_works(self):
        """Orchestrator must operate without a backbone (graceful degradation)."""
        from production_assistant_engine import ProductionAssistantOrchestrator
        orch = ProductionAssistantOrchestrator()
        profile = orch.intake_request(
            title="Standalone test",
            country="US",
            industry="construction",
            functions=["project_management"],
        )
        assert profile is not None


# ===========================================================================
# 7. Time-tracking bridge — forwards InvoicingHookManager events to backbone
# ===========================================================================

class TestTimeTrackingEventBackboneBridge:
    """bridge_time_tracking_to_backbone must forward all TimeTrackingEvent types."""

    def test_bridge_registers_forwarders(self):
        from time_tracking.invoicing_hooks import InvoicingHookManager, TimeTrackingEvent
        from time_tracking.event_backbone_bridge import bridge_time_tracking_to_backbone

        published: List[str] = []

        class _FakeBackbone:
            def publish(self, event: str, payload: dict) -> None:
                published.append(event)

        manager = InvoicingHookManager()
        backbone = _FakeBackbone()
        bridge_time_tracking_to_backbone(manager, backbone)

        # Emit one event and verify it was forwarded
        manager.emit(TimeTrackingEvent.ENTRY_APPROVED, {"entry_id": "t1"})
        assert TimeTrackingEvent.ENTRY_APPROVED.value in published

    def test_bridge_forwards_all_event_types(self):
        from time_tracking.invoicing_hooks import InvoicingHookManager, TimeTrackingEvent
        from time_tracking.event_backbone_bridge import bridge_time_tracking_to_backbone

        forwarded: List[str] = []

        class _FakeBackbone:
            def publish(self, event: str, payload: dict) -> None:
                forwarded.append(event)

        manager = InvoicingHookManager()
        bridge_time_tracking_to_backbone(manager, _FakeBackbone())

        for event in TimeTrackingEvent:
            manager.emit(event, {"test": True})

        forwarded_set = set(forwarded)
        for event in TimeTrackingEvent:
            assert event.value in forwarded_set, (
                f"TimeTrackingEvent.{event.name} was not forwarded to backbone"
            )

    def test_backbone_failure_does_not_crash_hook_manager(self):
        """If backbone.publish raises, the hook manager must still continue."""
        from time_tracking.invoicing_hooks import InvoicingHookManager, TimeTrackingEvent
        from time_tracking.event_backbone_bridge import bridge_time_tracking_to_backbone

        class _BrokenBackbone:
            def publish(self, event: str, payload: dict) -> None:
                raise RuntimeError("backbone unavailable")

        manager = InvoicingHookManager()
        bridge_time_tracking_to_backbone(manager, _BrokenBackbone())
        # Should not raise
        manager.emit(TimeTrackingEvent.ENTRY_APPROVED, {"entry_id": "x"})
