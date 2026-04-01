"""
Tests for WIRE-004: AdvancedLoopWiring.

Validates that wire_advanced_loop() returns correctly cross-wired
components and degrades gracefully when modules are missing.

Design Label: TEST-WIRE-004
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from advanced_loop_wiring import wire_advanced_loop
from self_fix_loop_connector import SelfFixLoopConnector
from task_execution_bridge import TaskExecutionBridge


# ---------------------------------------------------------------------------
# Test: wire_advanced_loop returns expected components
# ---------------------------------------------------------------------------

class TestWireAdvancedLoop:
    def test_returns_dict(self):
        components = wire_advanced_loop()
        assert isinstance(components, dict)

    def test_fix_loop_connector_present(self):
        components = wire_advanced_loop()
        assert "fix_loop_connector" in components
        assert isinstance(components["fix_loop_connector"], SelfFixLoopConnector)

    def test_task_execution_bridge_present(self):
        components = wire_advanced_loop()
        assert "task_execution_bridge" in components
        assert isinstance(components["task_execution_bridge"], TaskExecutionBridge)

    def test_base_components_created(self):
        components = wire_advanced_loop()
        # Core components should be created
        assert "event_backbone" in components
        assert "orchestrator" in components

    def test_components_are_cross_wired(self):
        components = wire_advanced_loop()
        fix_conn = components["fix_loop_connector"]
        task_bridge = components["task_execution_bridge"]

        # SelfFixLoopConnector should have automation_connector
        assert fix_conn._connector is not None or fix_conn._fix_loop is not None
        # TaskExecutionBridge should have orchestrator
        assert task_bridge._orchestrator is not None


# ---------------------------------------------------------------------------
# Test: accepts and reuses base_components
# ---------------------------------------------------------------------------

class TestBaseComponents:
    def test_reuses_provided_orchestrator(self):
        from self_automation_orchestrator import SelfAutomationOrchestrator
        orch = SelfAutomationOrchestrator()
        components = wire_advanced_loop(base_components={"orchestrator": orch})
        assert components["orchestrator"] is orch
        assert components["task_execution_bridge"]._orchestrator is orch

    def test_reuses_provided_backbone(self):
        from event_backbone import EventBackbone
        bb = EventBackbone()
        components = wire_advanced_loop(base_components={"event_backbone": bb})
        assert components["event_backbone"] is bb

    def test_reuses_provided_fix_loop(self):
        from self_fix_loop import SelfFixLoop
        loop = SelfFixLoop()
        components = wire_advanced_loop(base_components={"fix_loop": loop})
        assert components.get("fix_loop") is loop
        fix_conn = components["fix_loop_connector"]
        assert fix_conn._fix_loop is loop


# ---------------------------------------------------------------------------
# Test: graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def test_wire_with_empty_base(self):
        """Should not raise even when starting from scratch."""
        components = wire_advanced_loop(base_components={})
        assert isinstance(components, dict)
        # At minimum the two new components must be attempted
        assert "fix_loop_connector" in components or "task_execution_bridge" in components

    def test_repeated_calls_independent(self):
        """Each call to wire_advanced_loop creates independent instances."""
        c1 = wire_advanced_loop()
        c2 = wire_advanced_loop()
        assert c1["fix_loop_connector"] is not c2["fix_loop_connector"]
        assert c1["task_execution_bridge"] is not c2["task_execution_bridge"]

    def test_none_base_components(self):
        """None is treated the same as empty dict."""
        components = wire_advanced_loop(None)
        assert isinstance(components, dict)
