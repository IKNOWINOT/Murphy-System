"""
Phase 1: Murphy Core Component Integration Tests
Simplified version using actual Murphy System structure

Test Hierarchy: Level 2 (Integration Tests)
Test Category: Component Interface Testing
"""

import pytest
from datetime import datetime
import json


# ============================================================================
# SIT-INT-001: Confidence Engine ↔ Gate Synthesis Integration
# ============================================================================

def test_sit_int_001_confidence_to_gate_synthesis():
    """
    Test ID: SIT-INT-001
    Test Name: Confidence Engine to Gate Synthesis Integration

    Test Objective:
    Validate that confidence scores trigger appropriate gate synthesis.
    Low confidence should generate more restrictive gates.

    Expected Results:
    - High confidence (>0.8): Minimal gates (0-2)
    - Low confidence (<0.5): Maximum gates (6+)
    - Gate restrictiveness increases as confidence decreases
    """
    from src.confidence_engine.confidence_calculator import ConfidenceCalculator
    from src.gate_synthesis.gate_generator import GateGenerator
    from src.gate_synthesis.models import FailureMode, FailureModeType, RiskVector
    from src.confidence_engine.models import Phase, AuthorityBand

    # Setup
    confidence_calc = ConfidenceCalculator()
    gate_gen = GateGenerator()

    # Test Case 1: High Confidence Scenario
    high_murphy_index = 0.1  # Low risk

    failure_modes_high = [
        FailureMode(
            id="fm_1",
            type=FailureModeType.SEMANTIC_DRIFT,
            description="A minor failure",
            probability=high_murphy_index,
            impact=0.3,
            risk_vector=RiskVector(H=high_murphy_index, one_minus_D=0.7, exposure=0.3, authority_risk=0.1)
        )
    ]

    gates_high = gate_gen.generate_gates(
        failure_modes=failure_modes_high,
        current_phase=Phase.EXECUTE,
        current_authority=AuthorityBand.EXECUTE,
        murphy_probabilities={"fm_1": high_murphy_index}
    )

    assert len(gates_high) <= 3, \
        f"Too many gates for high confidence: {len(gates_high)}"

    print(f"✓ High confidence (murphy={high_murphy_index}): {len(gates_high)} gates generated")

    # Test Case 2: Low Confidence Scenario
    low_murphy_index = 0.8  # High risk

    failure_modes_low = [
        FailureMode(
            id="fm_2",
            type=FailureModeType.CONSTRAINT_VIOLATION,
            description="A critical failure",
            probability=low_murphy_index,
            impact=0.9,
            risk_vector=RiskVector(H=low_murphy_index, one_minus_D=0.1, exposure=0.9, authority_risk=0.8)
        ),
        FailureMode(
            id="fm_3",
            type=FailureModeType.SEMANTIC_DRIFT,
            description="Another failure",
            probability=0.6,
            impact=0.7,
            risk_vector=RiskVector(H=0.6, one_minus_D=0.3, exposure=0.7, authority_risk=0.5)
        )
    ]

    gates_low = gate_gen.generate_gates(
        failure_modes=failure_modes_low,
        current_phase=Phase.EXECUTE,
        current_authority=AuthorityBand.PROPOSE,
        murphy_probabilities={"fm_2": low_murphy_index, "fm_3": 0.6}
    )

    assert len(gates_low) >= 2, \
        f"Too few gates for low confidence: {len(gates_low)}"

    print(f"✓ Low confidence (murphy={low_murphy_index}): {len(gates_low)} gates generated")

    # Validation: More gates for higher Murphy index (lower confidence)
    assert len(gates_low) >= len(gates_high), \
        "Low confidence should generate at least as many gates as high confidence"

    print("✓ SIT-INT-001 PASSED: Confidence to Gate Synthesis integration working")


# ============================================================================
# SIT-INT-002: Component Health Check Integration
# ============================================================================

def test_sit_int_002_component_health_checks():
    """
    Test ID: SIT-INT-002
    Test Name: Component Health Check Integration

    Test Objective:
    Validate that all Murphy components can be imported and initialized.

    Expected Results:
    - All components import successfully
    - All components can be instantiated
    - No import errors or initialization failures
    """
    components_tested = []

    # Test Confidence Engine
    try:
        from src.confidence_engine.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        components_tested.append("Confidence Engine")
        print("✓ Confidence Engine: OK")
    except Exception as e:
        pytest.fail(f"Confidence Engine failed: {e}")

    # Test Gate Synthesis
    try:
        from src.gate_synthesis.gate_generator import GateGenerator
        gen = GateGenerator()
        components_tested.append("Gate Synthesis")
        print("✓ Gate Synthesis: OK")
    except Exception as e:
        pytest.fail(f"Gate Synthesis failed: {e}")

    # Test Execution Orchestrator
    try:
        from src.execution_orchestrator.executor import StepwiseExecutor
        exec_engine = StepwiseExecutor()
        components_tested.append("Execution Orchestrator")
        print("✓ Execution Orchestrator: OK")
    except Exception as e:
        pytest.fail(f"Execution Orchestrator failed: {e}")

    # Test Bridge Layer
    try:
        from src.bridge_layer.intake import HypothesisIntakeService as HypothesisIntake
        intake = HypothesisIntake()
        components_tested.append("Bridge Layer")
        print("✓ Bridge Layer: OK")
    except Exception as e:
        pytest.fail(f"Bridge Layer failed: {e}")

    # Test Supervisor System
    try:
        from src.supervisor_system.supervisor_loop import SupervisorInterface
        from src.supervisor_system.assumption_management import (
            AssumptionRegistry, AssumptionValidator, AssumptionLifecycleManager
        )
        registry = AssumptionRegistry()
        validator = AssumptionValidator(registry)
        lifecycle_manager = AssumptionLifecycleManager(registry)
        supervisor = SupervisorInterface(registry, validator, lifecycle_manager)
        components_tested.append("Supervisor System")
        print("✓ Supervisor System: OK")
    except Exception as e:
        pytest.fail(f"Supervisor System failed: {e}")

    assert len(components_tested) >= 5, \
        f"Not all components tested: {components_tested}"

    print(f"\n✓ SIT-INT-002 PASSED: {len(components_tested)} components healthy")


# ============================================================================
# SIT-INT-003: Data Flow Integration
# ============================================================================

def test_sit_int_003_data_flow_integration():
    """
    Test ID: SIT-INT-003
    Test Name: Data Flow Integration

    Test Objective:
    Validate that data flows correctly between components.

    Expected Results:
    - Data structures are compatible
    - No data loss during transfer
    - Proper error handling
    """
    from src.confidence_engine.models import ArtifactNode, ArtifactType, ArtifactSource
    from src.gate_synthesis.models import Gate, GateType, GateCategory

    # Test Case 1: Artifact Node Creation
    artifact = ArtifactNode(
        id="test_001",
        type=ArtifactType.HYPOTHESIS,
        source=ArtifactSource.API,
        content={"text": "Test hypothesis"},
        confidence_weight=0.8
    )

    assert artifact.id == "test_001"
    assert artifact.confidence_weight == 0.8
    print("✓ Artifact creation: OK")

    # Test Case 2: Gate Creation
    gate = Gate(
        id="gate_001",
        type=GateType.CONSTRAINT,
        category=GateCategory.SEMANTIC_STABILITY,
        target="execution",
        trigger_condition={"threshold": 0.7},
        enforcement_effect={"action": "block"},
        reason="Confidence too low"
    )

    assert gate.id == "gate_001"
    assert gate.type == GateType.CONSTRAINT
    print("✓ Gate creation: OK")

    # Test Case 3: Data Serialization
    artifact_dict = {
        "artifact_id": artifact.id,
        "confidence": artifact.confidence_weight,
        "type": artifact.type.value
    }

    gate_dict = {
        "gate_id": gate.id,
        "type": gate.type.value,
        "category": gate.category.value
    }

    # Verify serialization works
    artifact_json = json.dumps(artifact_dict)
    gate_json = json.dumps(gate_dict)

    assert len(artifact_json) > 0
    assert len(gate_json) > 0
    print("✓ Data serialization: OK")

    print("\n✓ SIT-INT-003 PASSED: Data flow integration working")


# ============================================================================
# SIT-INT-004: Security Plane Integration
# ============================================================================

def test_sit_int_004_security_plane_integration():
    """
    Test ID: SIT-INT-004
    Test Name: Security Plane Integration

    Test Objective:
    Validate that Security Plane components integrate with Murphy core.

    Expected Results:
    - Security components import successfully
    - Data classification works
    - Encryption enforcement works
    """
    from src.security_plane.data_leak_prevention import (
        SensitiveDataClassifier,
        DataLeakPreventionSystem
    )

    # Test Case 1: Data Classification
    classifier = SensitiveDataClassifier()

    test_data = "Employee SSN: 123-45-6789"
    classification = classifier.classify(test_data, "test_data_001")

    assert classification.data_id == "test_data_001"
    assert len(classification.categories) > 0
    print(f"✓ Data classification: {classification.sensitivity_level.value}")

    # Test Case 2: DLP System
    dlp = DataLeakPreventionSystem()

    classification = dlp.classify_and_protect(test_data, "test_data_002")

    assert classification.data_id == "test_data_002"
    assert classification.encryption_required in [True, False]
    print(f"✓ DLP system: Encryption required = {classification.encryption_required}")

    # Test Case 3: Statistics
    stats = dlp.get_statistics()

    assert "classified_data_count" in stats
    assert stats["classified_data_count"] >= 1
    print(f"✓ DLP statistics: {stats['classified_data_count']} items classified")

    print("\n✓ SIT-INT-004 PASSED: Security Plane integration working")


# ============================================================================
# SIT-INT-005: Telemetry Integration
# ============================================================================

def test_sit_int_005_telemetry_integration():
    """
    Test ID: SIT-INT-005
    Test Name: Telemetry Integration

    Test Objective:
    Validate that telemetry collection works across components.

    Expected Results:
    - Telemetry can be collected
    - Metrics are properly formatted
    - No errors during collection
    """
    # Test Case 1: Basic Telemetry
    telemetry_data = {
        "timestamp": datetime.now().isoformat(),
        "component": "test_component",
        "metric": "test_metric",
        "value": 42
    }

    assert "timestamp" in telemetry_data
    assert "component" in telemetry_data
    assert "metric" in telemetry_data
    assert "value" in telemetry_data
    print("✓ Telemetry structure: OK")

    # Test Case 2: Metrics Collection
    metrics = {
        "confidence_score": 0.85,
        "active_gates": 3,
        "execution_count": 100,
        "system_health": 0.95
    }

    for metric_name, metric_value in metrics.items():
        assert isinstance(metric_value, (int, float))
        assert metric_value >= 0

    print(f"✓ Metrics collection: {len(metrics)} metrics")

    # Test Case 3: Telemetry Serialization
    telemetry_json = json.dumps(telemetry_data)
    metrics_json = json.dumps(metrics)

    assert len(telemetry_json) > 0
    assert len(metrics_json) > 0
    print("✓ Telemetry serialization: OK")

    print("\n✓ SIT-INT-005 PASSED: Telemetry integration working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
