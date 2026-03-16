"""
Basic Import Tests

Tests that all integration classes can be imported successfully.
This is a simpler test than the full integration tests.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import sys
import os

# Add src to path

def test_unified_confidence_engine_import():
    """Test UnifiedConfidenceEngine can be imported"""
    from confidence_engine.unified_confidence_engine import UnifiedConfidenceEngine
    assert UnifiedConfidenceEngine is not None

def test_integrated_correction_system_import():
    """Test IntegratedCorrectionSystem can be imported"""
    from learning_engine.integrated_correction_system import IntegratedCorrectionSystem
    assert IntegratedCorrectionSystem is not None

def test_integrated_form_executor_import():
    """Test IntegratedFormExecutor can be imported"""
    from execution_engine.integrated_form_executor import IntegratedFormExecutor
    assert IntegratedFormExecutor is not None

def test_integrated_hitl_monitor_import():
    """Test IntegratedHITLMonitor can be imported"""
    from supervisor_system.integrated_hitl_monitor import IntegratedHITLMonitor
    assert IntegratedHITLMonitor is not None

def test_form_intake_import():
    """Test form intake modules can be imported"""
    from form_intake.schemas import PlanUploadForm
    assert PlanUploadForm is not None

def main():
    """Run all import tests"""
    print("=" * 60)
    print("Murphy System Integration - Basic Import Tests")
    print("=" * 60)

    tests = [
        test_unified_confidence_engine_import,
        test_integrated_correction_system_import,
        test_integrated_form_executor_import,
        test_integrated_hitl_monitor_import,
        test_form_intake_import,
    ]

    results = []
    for test in tests:
        print(f"\nTesting: {test.__name__}")
        results.append(test())

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✓ All imports successful!")
        return 0
    else:
        print("\n✗ Some imports failed. See details above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
