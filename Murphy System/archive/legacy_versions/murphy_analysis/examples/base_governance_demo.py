"""
Base Governance & Compliance Runtime Demonstration

Demonstrates all aspects of the Murphy System Base Governance & Compliance framework
including preset management, validation, compliance monitoring, and risk assessment.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from src.base_governance_runtime.governance_runtime_complete import (
    GovernanceRuntime,
    RuntimeConfig
)
from src.base_governance_runtime.preset_manager import PresetManager
from src.base_governance_runtime.validation_engine import ValidationEngine
from src.base_governance_runtime.compliance_monitor import ComplianceMonitor


def demo_mandatory_baseline_controls():
    """Demonstrate mandatory baseline control checks"""
    print("=" * 60)
    print("1. MANDATORY BASELINE CONTROLS CHECK")
    print("=" * 60)
    
    engine = ValidationEngine()
    baseline_check = engine.check_mandatory_baseline_controls()
    
    print(f"\nValidation ID: {baseline_check.validation_id}")
    print(f"Overall Status: {baseline_check.overall_status.value}")
    print(f"Compliance Percentage: {baseline_check.get_compliance_percentage():.1f}%")
    print(f"System Deployable: {not baseline_check.has_blocking_gaps()}")
    
    if baseline_check.gaps:
        print(f"\nGaps: {len(baseline_check.gaps)}")
    else:
        print("\n✅ All mandatory baseline controls present!")
    print()


def demo_complete_validation_output():
    """Demonstrate complete validation output as required"""
    print("=" * 60)
    print("COMPLETE VALIDATION OUTPUT (AS REQUIRED)")
    print("=" * 60)
    
    config = RuntimeConfig(strict_mode=False)
    runtime = GovernanceRuntime(config)
    runtime.initialize()
    
    validation_output = runtime.get_validation_output()
    
    print(f"\nPresets Enabled: {validation_output['presets_enabled']}")
    print(f"Presets Disabled: {validation_output['presets_disabled']}")
    print(f"Controls Enforced by Default: {validation_output['controls_enforced_by_default']}")
    print(f"Controls Enforced Conditionally: {validation_output['controls_enforced_conditionally']}")
    print(f"Controls Not Supported: {validation_output['controls_not_supported']}")
    print(f"Compliance Status: {validation_output['compliance_status']}")
    print(f"Compliance Percentage: {validation_output['compliance_percentage']:.1f}%")
    print(f"System Deployable: {validation_output['system_deployable']}")
    
    if validation_output['risk_statements']:
        print("\nRisk Statements:")
        for risk in validation_output['risk_statements'][:3]:
            print(f"  - {risk}")
    print()


def main():
    """Run all demonstrations"""
    print("Murphy System Base Governance & Compliance Runtime")
    print("Comprehensive Demonstration")
    print("=" * 60)
    print()
    
    try:
        demo_mandatory_baseline_controls()
        demo_complete_validation_output()
        
        print("=" * 60)
        print("🎉 DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()