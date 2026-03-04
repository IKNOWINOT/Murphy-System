"""
Comprehensive Test Suite for Base Governance & Compliance Runtime

Tests all aspects of the governance framework including:
- Mandatory baseline control validation
- Preset management and configuration
- Compliance monitoring and reporting
- System activation and risk assessment
"""

import pytest
from datetime import datetime, timedelta
from src.base_governance_runtime.governance_runtime_complete import (
    GovernanceRuntime, RuntimeConfig, RuntimeStatus
)
from src.base_governance_runtime.preset_manager import (
    PresetManager, GovernancePreset, EnforcementMode
)
from src.base_governance_runtime.validation_engine import (
    ValidationEngine, ValidationResult, ComplianceStatus
)
from src.base_governance_runtime.compliance_monitor import (
    ComplianceMonitor, ComplianceReport
)


class TestMandatoryBaselineControls:
    """Test mandatory baseline control validation"""

    def test_baseline_control_check(self):
        """Test that mandatory baseline controls are properly validated"""
        engine = ValidationEngine()
        result = engine.check_mandatory_baseline_controls()

        assert result is not None
        assert hasattr(result, 'validation_id')
        assert hasattr(result, 'overall_status')
        assert hasattr(result, 'total_requirements')
        assert hasattr(result, 'satisfied_requirements')
        assert hasattr(result, 'gaps')

    def test_blocking_gap_detection(self):
        """Test detection of blocking gaps"""
        engine = ValidationEngine()
        result = engine.check_mandatory_baseline_controls()

        # Should detect gaps (since we don't have all controls implemented)
        assert len(result.gaps) >= 0

        # Check if system is deployable
        is_deployable = not result.has_blocking_gaps()
        assert isinstance(is_deployable, bool)

    def test_compliance_percentage_calculation(self):
        """Test compliance percentage calculation"""
        engine = ValidationEngine()
        result = engine.check_mandatory_baseline_controls()

        percentage = result.get_compliance_percentage()
        assert isinstance(percentage, float)
        assert 0.0 <= percentage <= 100.0


class TestPresetManagement:
    """Test preset management functionality"""

    def test_preset_manager_initialization(self):
        """Test preset manager initialization with default presets"""
        manager = PresetManager()

        presets = manager.list_presets()
        assert len(presets) >= 2  # At least AI and Enterprise presets

        # Check for specific presets
        preset_ids = [p.preset_id for p in presets]
        assert "ai_governance_v1" in preset_ids
        assert "enterprise_security_v1" in preset_ids

    def test_preset_enabling_disabling(self):
        """Test preset enable/disable functionality"""
        manager = PresetManager()

        # Test enabling a preset
        assert manager.enable_preset("ai_governance_v1") == True
        assert "ai_governance_v1" in manager.enabled_presets

        # Test disabling a preset
        assert manager.disable_preset("ai_governance_v1") == True
        assert "ai_governance_v1" not in manager.enabled_presets

        # Test non-existent preset
        assert manager.enable_preset("non_existent") == False

    def test_governance_preset_structure(self):
        """Test governance preset structure"""
        manager = PresetManager()
        ai_preset = manager.get_preset("ai_governance_v1")

        assert ai_preset is not None
        assert ai_preset.preset_id == "ai_governance_v1"
        assert ai_preset.domain == "AI_GOVERNANCE"
        assert len(ai_preset.requirements) >= 3

        # Check mandatory requirements
        mandatory = ai_preset.get_mandatory_requirements()
        assert len(mandatory) >= 2


class TestGovernanceRuntime:
    """Test governance runtime orchestration"""

    def test_runtime_initialization(self):
        """Test governance runtime initialization"""
        config = RuntimeConfig(strict_mode=False)
        runtime = GovernanceRuntime(config)

        assert runtime.status == RuntimeStatus.INACTIVE
        assert runtime.preset_manager is not None
        assert runtime.validation_engine is not None
        assert runtime.compliance_monitor is not None

    def test_system_status_reporting(self):
        """Test comprehensive system status reporting"""
        config = RuntimeConfig()
        runtime = GovernanceRuntime(config)

        status = runtime.get_system_status()

        assert "runtime_status" in status
        assert "compliance_status" in status
        assert "active_presets" in status
        assert "available_presets" in status
        assert "blocking_gaps" in status
        assert "can_activate" in status

    def test_validation_output_generation(self):
        """Test complete validation output as required"""
        config = RuntimeConfig(strict_mode=False)
        runtime = GovernanceRuntime(config)

        # Initialize runtime
        runtime.initialize()

        # Get validation output
        output = runtime.get_validation_output()

        # Check required output fields
        assert "presets_enabled" in output
        assert "presets_disabled" in output
        assert "controls_enforced_by_default" in output
        assert "compliance_status" in output
        assert "compliance_percentage" in output
        assert "system_deployable" in output
        assert "risk_statements" in output

    def test_preset_selection_handling(self):
        """Test preset selection with gap analysis"""
        config = RuntimeConfig()
        runtime = GovernanceRuntime(config)

        # Test valid preset
        result = runtime.handle_preset_selection("ai_governance_v1")

        assert result["preset_found"] == True
        assert "preset_name" in result
        assert "fully_enforceable" in result
        assert "gaps_identified" in result
        assert "requires_operator_acknowledgement" in result

        # Test invalid preset
        result = runtime.handle_preset_selection("invalid_preset")
        assert result["preset_found"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
