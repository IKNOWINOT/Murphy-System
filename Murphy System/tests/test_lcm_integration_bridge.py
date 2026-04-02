# Copyright 2020 Inoni LLC -- BSL 1.1
# Creator: Corey Post
"""
Module: tests/test_lcm_integration_bridge.py
Subsystem: LCM Integration Bridge -- Gate profiles across integration layers
Label: TEST-LCM-BRIDGE -- Commission tests for LCMIntegrationBridge

Commissioning Answers (G1-G9)
-----------------------------
1. G1 -- Purpose: Does this do what it was designed to do?
   YES -- validates all 5 bridge classes (WorldModel, Enterprise, AM,
   BAS, BotGovernance) and the master LCMIntegrationBridge.

2. G2 -- Spec: What is it supposed to do?
   Intercept calls to AM workflows, BAS actions, enterprise DAG steps,
   generic connectors, and bot governance -- checking LCM gate profiles
   before allowing execution. Degrades gracefully without LCM engine.

3. G3 -- Conditions: What conditions are possible?
   - With LCM engine attached / detached (None)
   - Gate passes / gate fails (weight below threshold)
   - Unknown process types / system types
   - Exception during predict
   - Various AM process types (safe FDM vs dangerous SLM)
   - Various BAS system types (safe FCU vs dangerous boiler)
   - Industry mapping for bot governance

4. G4 -- Test Profile: Does test profile reflect full range?
   YES -- 18 tests covering all bridges and conditions.

5. G5 -- Expected vs Actual: All tests pass.
6. G6 -- Regression Loop: Run: pytest tests/test_lcm_integration_bridge.py -v
7. G7 -- As-Builts: YES.
8. G8 -- Hardening: Graceful degradation without engine tested.
9. G9 -- Re-commissioned: YES.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.lcm_integration_bridge import (
    AMWorkflowGateBridge,
    BASActionGateBridge,
    BotGovernanceGateBridge,
    EnterpriseIntegrationGateBridge,
    GatedConnectorResult,
    LCMIntegrationBridge,
    WorldModelGateBridge,
    _check_gates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_engine(confidence=0.9, gate_types=None, gate_weights=None):
    """Create a mock LCM engine that returns predictable profiles."""
    if gate_types is None:
        gate_types = ["safety", "quality", "compliance", "energy", "monitoring"]
    if gate_weights is None:
        gate_weights = {g: confidence for g in gate_types}

    mock_profile = MagicMock()
    mock_profile.to_dict.return_value = {
        "domain_id": "test",
        "role": "expert",
        "gate_types": gate_types,
        "gate_weights": gate_weights,
        "confidence": confidence,
    }
    mock_profile.gate_types = gate_types
    mock_profile.gate_weights = gate_weights
    mock_profile.confidence = confidence

    engine = MagicMock()
    engine.predict.return_value = mock_profile
    return engine


def _make_failing_engine():
    """Create a mock LCM engine whose predict() raises."""
    engine = MagicMock()
    engine.predict.side_effect = RuntimeError("LCM engine crashed")
    return engine


# ---------------------------------------------------------------------------
# GatedConnectorResult
# ---------------------------------------------------------------------------

class TestGatedConnectorResult:
    """COMMISSION: G4 -- LCM Bridge / GatedConnectorResult."""

    def test_construction(self):
        r = GatedConnectorResult(
            connector_name="test_connector",
            domain_id="hvac_bas",
            gate_passed=True,
            gate_profile={"confidence": 0.9},
        )
        assert r.connector_name == "test_connector"
        assert r.gate_passed is True
        assert r.error is None

    def test_to_dict(self):
        r = GatedConnectorResult(
            connector_name="test", domain_id="d1",
            gate_passed=False, gate_profile={},
            error="gate failed", gate_check_ms=1.5,
        )
        d = r.to_dict()
        assert d["error"] == "gate failed"
        assert d["gate_check_ms"] == 1.5


# ---------------------------------------------------------------------------
# _check_gates
# ---------------------------------------------------------------------------

class TestCheckGates:
    """COMMISSION: G4 -- LCM Bridge / _check_gates helper."""

    def test_no_profile_fails(self):
        passed, reason = _check_gates(None)
        assert passed is False
        assert "no gate profile" in reason

    def test_no_required_gates_passes(self):
        profile = MagicMock()
        profile.to_dict.return_value = {"gate_weights": {}, "confidence": 0.8}
        passed, reason = _check_gates(profile, [])
        assert passed is True

    def test_weight_below_threshold_fails(self):
        profile = MagicMock()
        profile.to_dict.return_value = {
            "gate_weights": {"safety": 0.5},
            "confidence": 0.5,
        }
        passed, reason = _check_gates(profile, ["safety"])
        assert passed is False
        assert "safety" in reason

    def test_weight_above_threshold_passes(self):
        profile = MagicMock()
        profile.to_dict.return_value = {
            "gate_weights": {"quality": 0.9},
            "confidence": 0.9,
        }
        passed, reason = _check_gates(profile, ["quality"])
        assert passed is True


# ---------------------------------------------------------------------------
# WorldModelGateBridge
# ---------------------------------------------------------------------------

class TestWorldModelGateBridge:
    """COMMISSION: G4 -- LCM Bridge / WorldModelGateBridge."""

    def test_execute_gated_without_engine(self):
        bridge = WorldModelGateBridge(lcm_engine=None)
        result = bridge.execute_gated("connector_a", "read", {}, "hvac_bas")
        assert result.gate_passed is True
        assert result.result is not None
        assert result.result["executed"] is True

    def test_execute_gated_with_engine(self):
        engine = _make_mock_engine(confidence=0.95)
        bridge = WorldModelGateBridge(lcm_engine=engine)
        result = bridge.execute_gated("connector_a", "read", {}, "hvac_bas")
        assert result.gate_passed is True
        engine.predict.assert_called_once()

    def test_execute_gated_engine_exception(self):
        engine = _make_failing_engine()
        bridge = WorldModelGateBridge(lcm_engine=engine)
        result = bridge.execute_gated("connector_a", "read", {}, "hvac_bas")
        assert result.gate_passed is False
        assert result.error is not None

    def test_gate_check_ms_is_nonnegative(self):
        bridge = WorldModelGateBridge(lcm_engine=None)
        result = bridge.execute_gated("x", "y", {}, "d1")
        assert result.gate_check_ms >= 0.0


# ---------------------------------------------------------------------------
# EnterpriseIntegrationGateBridge
# ---------------------------------------------------------------------------

class TestEnterpriseIntegrationGateBridge:
    """COMMISSION: G4 -- LCM Bridge / EnterpriseIntegrationGateBridge."""

    def test_execute_step_without_engine(self):
        bridge = EnterpriseIntegrationGateBridge(lcm_engine=None)
        result = bridge.execute_step_gated("step_1", "enterprise_crm", {})
        assert result["gate_passed"] is True
        assert result["executed"] is True

    def test_execute_step_with_engine_compliance_passes(self):
        engine = _make_mock_engine(confidence=0.95)
        bridge = EnterpriseIntegrationGateBridge(lcm_engine=engine)
        result = bridge.execute_step_gated("step_1", "enterprise_crm", {})
        assert result["gate_passed"] is True

    def test_execute_step_compliance_gate_fails(self):
        engine = _make_mock_engine(
            confidence=0.5,
            gate_types=["compliance"],
            gate_weights={"compliance": 0.5},
        )
        bridge = EnterpriseIntegrationGateBridge(lcm_engine=engine)
        result = bridge.execute_step_gated("step_1", "banking", {})
        assert result["gate_passed"] is False

    def test_execute_step_engine_exception(self):
        engine = _make_failing_engine()
        bridge = EnterpriseIntegrationGateBridge(lcm_engine=engine)
        result = bridge.execute_step_gated("step_1", "d1", {})
        assert result["gate_passed"] is False
        assert result["error"] is not None


# ---------------------------------------------------------------------------
# AMWorkflowGateBridge
# ---------------------------------------------------------------------------

class TestAMWorkflowGateBridge:
    """COMMISSION: G4 -- LCM Bridge / AMWorkflowGateBridge."""

    def test_fdm_without_engine_passes(self):
        bridge = AMWorkflowGateBridge(lcm_engine=None)
        result = bridge.execute_am_action_gated("fdm_fff", "start_print", {})
        assert result.gate_passed is True
        assert result.result["executed"] is True

    def test_slm_with_engine_high_confidence_passes(self):
        engine = _make_mock_engine(confidence=0.95)
        bridge = AMWorkflowGateBridge(lcm_engine=engine)
        result = bridge.execute_am_action_gated("slm_dmls", "start_print", {})
        assert result.gate_passed is True

    def test_slm_with_low_safety_fails(self):
        engine = _make_mock_engine(
            confidence=0.5,
            gate_types=["safety", "quality", "compliance", "energy"],
            gate_weights={"safety": 0.5, "quality": 0.5, "compliance": 0.5, "energy": 0.5},
        )
        bridge = AMWorkflowGateBridge(lcm_engine=engine)
        result = bridge.execute_am_action_gated("slm_dmls", "start_print", {})
        assert result.gate_passed is False

    def test_unknown_process_uses_default_gates(self):
        bridge = AMWorkflowGateBridge(lcm_engine=None)
        result = bridge.execute_am_action_gated("future_process_xyz", "start", {})
        assert result.gate_passed is True

    def test_domain_id_derived_from_process_type(self):
        engine = _make_mock_engine(confidence=0.95)
        bridge = AMWorkflowGateBridge(lcm_engine=engine)
        bridge.execute_am_action_gated("sla_dlp", "start", {})
        call_args = engine.predict.call_args
        assert "3d_printing_sla_dlp" == call_args[0][0]


# ---------------------------------------------------------------------------
# BASActionGateBridge
# ---------------------------------------------------------------------------

class TestBASActionGateBridge:
    """COMMISSION: G4 -- LCM Bridge / BASActionGateBridge."""

    def test_fcu_without_engine_passes(self):
        bridge = BASActionGateBridge(lcm_engine=None)
        result = bridge.execute_bas_action_gated("fcu", "set_fan_speed", {})
        assert result.gate_passed is True

    def test_boiler_with_high_confidence_passes(self):
        engine = _make_mock_engine(confidence=0.95)
        bridge = BASActionGateBridge(lcm_engine=engine)
        result = bridge.execute_bas_action_gated("boiler", "ignite", {})
        assert result.gate_passed is True

    def test_boiler_with_low_safety_fails(self):
        engine = _make_mock_engine(
            confidence=0.5,
            gate_types=["safety", "energy", "compliance"],
            gate_weights={"safety": 0.5, "energy": 0.5, "compliance": 0.5},
        )
        bridge = BASActionGateBridge(lcm_engine=engine)
        result = bridge.execute_bas_action_gated("boiler", "ignite", {})
        assert result.gate_passed is False

    def test_unknown_system_uses_default_gates(self):
        bridge = BASActionGateBridge(lcm_engine=None)
        result = bridge.execute_bas_action_gated("future_hvac_xyz", "test", {})
        assert result.gate_passed is True

    def test_engine_exception_is_caught(self):
        engine = _make_failing_engine()
        bridge = BASActionGateBridge(lcm_engine=engine)
        result = bridge.execute_bas_action_gated("ahu", "start", {})
        assert result.gate_passed is False
        assert "crashed" in result.error


# ---------------------------------------------------------------------------
# BotGovernanceGateBridge
# ---------------------------------------------------------------------------

class TestBotGovernanceGateBridge:
    """COMMISSION: G4 -- LCM Bridge / BotGovernanceGateBridge."""

    def test_without_engine_returns_default_profile(self):
        bridge = BotGovernanceGateBridge(lcm_engine=None)
        result = bridge.get_bot_gate_profile("triage_bot", "3d printing")
        assert result["bot_name"] == "triage_bot"
        assert result["industry"] == "3d printing"
        assert "gate_profile" in result

    def test_with_engine_returns_predicted_profile(self):
        engine = _make_mock_engine(confidence=0.92)
        bridge = BotGovernanceGateBridge(lcm_engine=engine)
        result = bridge.get_bot_gate_profile("audit_bot", "banking")
        assert "gate_profile" in result
        engine.predict.assert_called_once()

    def test_industry_mapping_hvac(self):
        engine = _make_mock_engine()
        bridge = BotGovernanceGateBridge(lcm_engine=engine)
        bridge.get_bot_gate_profile("bot", "HVAC and building automation")
        call_args = engine.predict.call_args
        assert call_args[0][0] == "hvac_bas"

    def test_industry_mapping_healthcare(self):
        engine = _make_mock_engine()
        bridge = BotGovernanceGateBridge(lcm_engine=engine)
        bridge.get_bot_gate_profile("bot", "healthcare clinic")
        call_args = engine.predict.call_args
        assert call_args[0][0] == "clinical_operations"

    def test_industry_mapping_unknown_defaults_to_consulting(self):
        engine = _make_mock_engine()
        bridge = BotGovernanceGateBridge(lcm_engine=engine)
        bridge.get_bot_gate_profile("bot", "space exploration")
        call_args = engine.predict.call_args
        assert call_args[0][0] == "consulting"

    def test_engine_exception_returns_error_profile(self):
        engine = _make_failing_engine()
        bridge = BotGovernanceGateBridge(lcm_engine=engine)
        result = bridge.get_bot_gate_profile("bot", "manufacturing")
        assert "error" in result["gate_profile"]


# ---------------------------------------------------------------------------
# LCMIntegrationBridge (master)
# ---------------------------------------------------------------------------

class TestLCMIntegrationBridge:
    """COMMISSION: G4 -- LCM Bridge / LCMIntegrationBridge master."""

    def test_construction_without_engine(self):
        bridge = LCMIntegrationBridge(lcm_engine=None)
        assert bridge.world_model is not None
        assert bridge.enterprise is not None
        assert bridge.am_workflow is not None
        assert bridge.bas_action is not None
        assert bridge.bot_governance is not None

    def test_construction_with_engine(self):
        engine = _make_mock_engine()
        bridge = LCMIntegrationBridge(lcm_engine=engine)
        status = bridge.status()
        assert status["lcm_attached"] is True

    def test_status_without_engine(self):
        bridge = LCMIntegrationBridge(lcm_engine=None)
        status = bridge.status()
        assert status["lcm_attached"] is False
        assert "bridges" in status
        assert status["bridges"]["world_model"] == "ok"

    def test_all_bridges_accessible(self):
        bridge = LCMIntegrationBridge(lcm_engine=None)
        # Each sub-bridge should be usable
        r1 = bridge.world_model.execute_gated("c", "a", {}, "d")
        assert r1.gate_passed is True
        r2 = bridge.enterprise.execute_step_gated("s", "d", {})
        assert r2["gate_passed"] is True
        r3 = bridge.am_workflow.execute_am_action_gated("fdm_fff", "a", {})
        assert r3.gate_passed is True
        r4 = bridge.bas_action.execute_bas_action_gated("fcu", "a", {})
        assert r4.gate_passed is True
        r5 = bridge.bot_governance.get_bot_gate_profile("b", "retail")
        assert "gate_profile" in r5
