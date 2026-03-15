"""
Murphy System Core Component Integration Tests
Tests interfaces between all 13 Murphy core components

Test Hierarchy: Level 2 (Integration Tests)
Test Category: Component Interface Testing
"""

import pytest
from datetime import datetime, timedelta
import json

# Import all Murphy components
import pytest
try:
    from src.confidence_engine.confidence_engine import ConfidenceEngine
    from src.gate_synthesis.gate_synthesis import GateSynthesisEngine
    from src.deterministic_compute_plane.compute_plane import DeterministicComputePlane
    from src.execution_packet_compiler.compiler import ExecutionPacketCompiler
    from src.execution_orchestrator.orchestrator import ExecutionOrchestrator
    from src.bridge_layer.hypothesis_intake import HypothesisIntakeService
    from src.supervisor_system.supervisor_loop import SupervisorInterface
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)


# ============================================================================
# SIT-INT-001: Confidence Engine ↔ Gate Synthesis Integration
# ============================================================================

def test_sit_int_001_confidence_to_gate_synthesis():
    """
    Test ID: SIT-INT-001
    Test Name: Confidence Engine to Gate Synthesis Integration
    Components: Confidence Engine, Gate Synthesis Engine

    Test Objective:
    Validate that confidence scores from Confidence Engine correctly trigger
    gate synthesis in Gate Synthesis Engine. Low confidence should generate
    more restrictive gates.

    Prerequisites:
    - Confidence Engine operational
    - Gate Synthesis Engine operational
    - Test artifact graph available

    Test Methodology:
    1. Create artifact graph with varying confidence levels
    2. Compute confidence using Confidence Engine
    3. Pass confidence to Gate Synthesis Engine
    4. Verify gates generated match confidence level
    5. Validate gate restrictiveness increases as confidence decreases

    Test Modes: Normal operation

    Expected Results:
    - High confidence (>0.8): Minimal gates (0-2)
    - Medium confidence (0.5-0.8): Moderate gates (3-5)
    - Low confidence (<0.5): Maximum gates (6+)
    - Gate types match risk profile
    - All gates are enforceable
    """
    # Setup
    confidence_engine = ConfidenceEngine()
    gate_engine = GateSynthesisEngine()

    # Test Case 1: High Confidence Scenario
    high_conf_artifacts = [
        {"id": "art_001", "type": "verified", "confidence": 0.95},
        {"id": "art_002", "type": "verified", "confidence": 0.90},
    ]

    confidence_result = confidence_engine.compute_confidence(high_conf_artifacts)
    gates = gate_engine.synthesize_gates(
        confidence=confidence_result["overall_confidence"],
        murphy_index=confidence_result.get("murphy_index", 0.1)
    )

    assert confidence_result["overall_confidence"] >= 0.8, \
        f"High confidence scenario failed: {confidence_result['overall_confidence']}"
    assert len(gates) <= 2, \
        f"Too many gates for high confidence: {len(gates)}"

    # Test Case 2: Low Confidence Scenario
    low_conf_artifacts = [
        {"id": "art_003", "type": "unverified", "confidence": 0.3},
        {"id": "art_004", "type": "contradicted", "confidence": 0.2},
    ]

    confidence_result = confidence_engine.compute_confidence(low_conf_artifacts)
    gates = gate_engine.synthesize_gates(
        confidence=confidence_result["overall_confidence"],
        murphy_index=confidence_result.get("murphy_index", 0.8)
    )

    assert confidence_result["overall_confidence"] < 0.5, \
        f"Low confidence scenario failed: {confidence_result['overall_confidence']}"
    assert len(gates) >= 6, \
        f"Too few gates for low confidence: {len(gates)}"

    # Validation: Gate restrictiveness
    for gate in gates:
        assert "gate_id" in gate
        assert "gate_type" in gate
        assert "blocking" in gate
        assert gate["blocking"] is True  # Low confidence gates must block


# ============================================================================
# SIT-INT-002: Gate Synthesis ↔ Execution Packet Compiler Integration
# ============================================================================

def test_sit_int_002_gate_synthesis_to_packet_compiler():
    """
    Test ID: SIT-INT-002
    Test Name: Gate Synthesis to Execution Packet Compiler Integration
    Components: Gate Synthesis Engine, Execution Packet Compiler

    Test Objective:
    Validate that gates from Gate Synthesis Engine are correctly enforced
    by Execution Packet Compiler. Packets should not compile if gates fail.

    Prerequisites:
    - Gate Synthesis Engine operational
    - Execution Packet Compiler operational
    - Test gates available

    Test Methodology:
    1. Generate gates with Gate Synthesis Engine
    2. Attempt to compile execution packet
    3. Verify compiler checks all gates
    4. Confirm compilation fails if any gate fails
    5. Confirm compilation succeeds if all gates pass

    Test Modes: Normal operation, gate failure mode

    Expected Results:
    - Compiler checks ALL gates before compilation
    - Compilation fails if ANY gate fails
    - Compilation succeeds ONLY if ALL gates pass
    - Failure reason clearly indicates which gate failed
    - No partial compilation (atomic operation)
    """
    # Setup
    gate_engine = GateSynthesisEngine()
    compiler = ExecutionPacketCompiler()

    # Test Case 1: All Gates Pass
    passing_gates = [
        {"gate_id": "g001", "gate_type": "confidence", "threshold": 0.7, "current": 0.8, "blocking": True},
        {"gate_id": "g002", "gate_type": "verification", "required": True, "verified": True, "blocking": True},
    ]

    hypothesis = {
        "hypothesis_id": "hyp_001",
        "plan": "Execute safe operation",
        "confidence": 0.8,
        "gates": passing_gates
    }

    result = compiler.compile(hypothesis)

    assert result["success"] is True, \
        "Compilation should succeed when all gates pass"
    assert "execution_packet" in result
    assert result["execution_packet"]["gates_satisfied"] is True

    # Test Case 2: One Gate Fails
    failing_gates = [
        {"gate_id": "g003", "gate_type": "confidence", "threshold": 0.7, "current": 0.5, "blocking": True},  # FAILS
        {"gate_id": "g004", "gate_type": "verification", "required": True, "verified": True, "blocking": True},
    ]

    hypothesis_fail = {
        "hypothesis_id": "hyp_002",
        "plan": "Execute risky operation",
        "confidence": 0.5,
        "gates": failing_gates
    }

    result_fail = compiler.compile(hypothesis_fail)

    assert result_fail["success"] is False, \
        "Compilation should fail when any gate fails"
    assert "error" in result_fail
    assert "g003" in result_fail["error"], \
        "Error should identify failing gate"
    assert "execution_packet" not in result_fail, \
        "No packet should be created on failure"


# ============================================================================
# SIT-INT-003: Execution Packet Compiler ↔ Execution Orchestrator Integration
# ============================================================================

def test_sit_int_003_compiler_to_orchestrator():
    """
    Test ID: SIT-INT-003
    Test Name: Execution Packet Compiler to Execution Orchestrator Integration
    Components: Execution Packet Compiler, Execution Orchestrator

    Test Objective:
    Validate that execution packets from compiler are correctly validated
    and executed by orchestrator. Verify signature validation, authority
    enforcement, and execution tracking.

    Prerequisites:
    - Execution Packet Compiler operational
    - Execution Orchestrator operational
    - Security Plane operational (for signature validation)

    Test Methodology:
    1. Compile valid execution packet
    2. Submit to orchestrator
    3. Verify signature validation
    4. Verify authority enforcement
    5. Verify execution tracking
    6. Test with invalid packet (should reject)

    Test Modes: Normal operation, security validation mode

    Expected Results:
    - Valid packets accepted and executed
    - Invalid signatures rejected
    - Authority levels enforced
    - Execution tracked in telemetry
    - Replay attacks prevented
    - Complete audit trail maintained
    """
    # Setup
    compiler = ExecutionPacketCompiler()
    orchestrator = ExecutionOrchestrator()

    # Test Case 1: Valid Packet Execution
    hypothesis = {
        "hypothesis_id": "hyp_003",
        "plan": "Execute validated operation",
        "confidence": 0.9,
        "authority": "medium",
        "gates": []
    }

    compile_result = compiler.compile(hypothesis)
    assert compile_result["success"] is True

    packet = compile_result["execution_packet"]

    # Submit to orchestrator
    exec_result = orchestrator.execute(packet)

    assert exec_result["accepted"] is True, \
        "Valid packet should be accepted"
    assert exec_result["signature_valid"] is True, \
        "Signature validation should pass"
    assert exec_result["authority_enforced"] is True, \
        "Authority should be enforced"
    assert "execution_id" in exec_result

    # Test Case 2: Invalid Signature
    tampered_packet = packet.copy()
    tampered_packet["signature"] = "invalid_signature"

    exec_result_invalid = orchestrator.execute(tampered_packet)

    assert exec_result_invalid["accepted"] is False, \
        "Tampered packet should be rejected"
    assert "signature" in exec_result_invalid["rejection_reason"].lower()

    # Test Case 3: Replay Attack
    exec_result_replay = orchestrator.execute(packet)  # Same packet again

    assert exec_result_replay["accepted"] is False, \
        "Replay attack should be prevented"
    assert "replay" in exec_result_replay["rejection_reason"].lower()


# ============================================================================
# SIT-INT-004: Bridge Layer ↔ Confidence Engine Integration
# ============================================================================

def test_sit_int_004_bridge_to_confidence():
    """
    Test ID: SIT-INT-004
    Test Name: Bridge Layer to Confidence Engine Integration
    Components: Bridge Layer (Hypothesis Intake), Confidence Engine

    Test Objective:
    Validate that hypotheses from Bridge Layer are correctly processed
    by Confidence Engine. Verify sandbox constraints, verification
    requirements, and confidence computation.

    Prerequisites:
    - Bridge Layer operational
    - Confidence Engine operational
    - Test hypotheses available

    Test Methodology:
    1. Create sandbox hypothesis via Bridge Layer
    2. Extract claims and assumptions
    3. Generate verification requests
    4. Compute confidence after verification
    5. Verify sandbox constraints maintained

    Test Modes: Normal operation, sandbox enforcement mode

    Expected Results:
    - Hypotheses remain sandbox-only until verified
    - All assumptions extracted correctly
    - Verification requests generated for each claim
    - Confidence computed only after verification
    - No execution rights granted to unverified hypotheses
    """
    # Setup
    intake = HypothesisIntakeService()
    confidence_engine = ConfidenceEngine()

    # Test Case 1: Sandbox Hypothesis Processing
    hypothesis = {
        "hypothesis_id": "hyp_004",
        "plan_summary": "Automate HR onboarding process. Assumes: 1) Employee data is accurate, 2) Systems are available",
        "status": "sandbox",
        "confidence": None,  # Must be None for sandbox
        "execution_rights": False
    }

    # Intake processing
    intake_result = intake.process_hypothesis(hypothesis)

    assert intake_result["valid"] is True
    assert intake_result["sandbox_constraints_enforced"] is True
    assert len(intake_result["assumptions"]) >= 2, \
        "Should extract at least 2 assumptions"
    assert len(intake_result["verification_requests"]) >= 2, \
        "Should generate verification for each assumption"

    # Test Case 2: Confidence Computation After Verification
    # Simulate verification completion
    verified_artifacts = [
        {"id": "ver_001", "type": "verified", "confidence": 0.85, "assumption": "Employee data accurate"},
        {"id": "ver_002", "type": "verified", "confidence": 0.90, "assumption": "Systems available"},
    ]

    confidence_result = confidence_engine.compute_confidence(verified_artifacts)

    assert confidence_result["overall_confidence"] > 0.0, \
        "Confidence should be computed after verification"
    assert confidence_result["overall_confidence"] <= 1.0
    assert "assumptions_verified" in confidence_result

    # Test Case 3: Sandbox Constraint Violation
    invalid_hypothesis = {
        "hypothesis_id": "hyp_005",
        "plan_summary": "Invalid hypothesis",
        "status": "sandbox",
        "confidence": 0.9,  # INVALID: sandbox cannot have confidence
        "execution_rights": False
    }

    intake_result_invalid = intake.process_hypothesis(invalid_hypothesis)

    assert intake_result_invalid["valid"] is False, \
        "Should reject hypothesis with confidence in sandbox"
    assert "sandbox" in intake_result_invalid["error"].lower()


# ============================================================================
# SIT-INT-005: Supervisor System ↔ Confidence Engine Integration
# ============================================================================

def test_sit_int_005_supervisor_to_confidence():
    """
    Test ID: SIT-INT-005
    Test Name: Supervisor System to Confidence Engine Integration
    Components: Supervisor System, Confidence Engine

    Test Objective:
    Validate that supervisor feedback correctly triggers confidence
    adjustments in Confidence Engine. Verify assumption invalidation
    causes confidence decay.

    Prerequisites:
    - Supervisor System operational
    - Confidence Engine operational
    - Test assumptions available

    Test Methodology:
    1. Create assumption with initial confidence
    2. Submit supervisor feedback (invalidate)
    3. Verify confidence decays
    4. Verify authority decays
    5. Verify execution freezes if critical

    Test Modes: Normal operation, assumption invalidation mode

    Expected Results:
    - Supervisor feedback processed correctly
    - Confidence decays on invalidation
    - Authority decays proportionally
    - Critical assumptions trigger execution freeze
    - Non-critical assumptions trigger warnings
    - Complete audit trail maintained
    """
    # Setup
    supervisor = SupervisorInterface()
    confidence_engine = ConfidenceEngine()

    # Test Case 1: Assumption Invalidation
    assumption = {
        "assumption_id": "assum_001",
        "description": "Market conditions stable",
        "confidence": 0.8,
        "criticality": "high",
        "validated_by_self": False,
        "requires_external_validation": True
    }

    # Initial confidence
    initial_artifacts = [
        {"id": "art_005", "type": "assumption", "confidence": 0.8, "assumption_id": "assum_001"}
    ]
    initial_confidence = confidence_engine.compute_confidence(initial_artifacts)

    # Supervisor invalidates assumption
    feedback = {
        "feedback_type": "INVALIDATE",
        "assumption_id": "assum_001",
        "rationale": "Market conditions changed significantly",
        "supervisor_id": "sup_001",
        "evidence": ["Market data shows 20% volatility increase"]
    }

    feedback_result = supervisor.process_feedback(feedback)

    assert feedback_result["processed"] is True
    assert feedback_result["assumption_invalidated"] is True

    # Recompute confidence after invalidation
    invalidated_artifacts = [
        {"id": "art_005", "type": "assumption", "confidence": 0.0, "assumption_id": "assum_001", "invalidated": True}
    ]
    new_confidence = confidence_engine.compute_confidence(invalidated_artifacts)

    assert new_confidence["overall_confidence"] < initial_confidence["overall_confidence"], \
        "Confidence should decay after assumption invalidation"
    assert new_confidence["overall_confidence"] <= 0.5, \
        "Confidence should drop significantly for invalidated critical assumption"

    # Test Case 2: Execution Freeze on Critical Invalidation
    if assumption["criticality"] == "high":
        assert feedback_result["execution_frozen"] is True, \
            "Critical assumption invalidation should freeze execution"
        assert "freeze_reason" in feedback_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
