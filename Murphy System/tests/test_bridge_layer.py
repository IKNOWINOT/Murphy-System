"""
Comprehensive Test Suite for Bridge Layer

Tests all components:
1. System A cannot create ExecutionPackets
2. Intake fails on missing assumptions
3. Packet compilation fails without gates
4. Packet compilation fails without verification
5. End-to-end bridge workflow
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from src.bridge_layer.models import (
    HypothesisArtifact,
    VerificationArtifact,
    VerificationRequest,
    VerificationStatus,
    CompilationResult,
    BlockingReason,
)
from src.bridge_layer.intake import (
    HypothesisIntakeService,
    ClaimExtractor,
    VerificationRequestGenerator,
)
from src.bridge_layer.compilation import (
    ExecutionPacketCompiler,
    CompilationGate,
)
from src.bridge_layer.ux import (
    ExecutabilityExplainer,
    BlockingFeedback,
)


# Fixtures
@pytest.fixture
def valid_hypothesis():
    """Create a valid hypothesis artifact"""
    return HypothesisArtifact(
        hypothesis_id="hyp_001",
        plan_summary="Calculate optimal route assuming traffic is normal and weather is clear",
        assumptions=[
            "Traffic is normal",
            "Weather is clear",
            "GPS data is accurate",
        ],
        dependencies=[
            "GPS API",
            "Traffic API",
            "Weather API",
        ],
        risk_flags=[],
        proposed_actions=[
            {"action": "query_gps", "description": "Get current location"},
            {"action": "query_traffic", "description": "Get traffic data"},
            {"action": "calculate_route", "description": "Calculate optimal route"},
        ],
    )


@pytest.fixture
def intake_service():
    """Create intake service"""
    return HypothesisIntakeService()


@pytest.fixture
def packet_compiler():
    """Create packet compiler"""
    return ExecutionPacketCompiler()


@pytest.fixture
def executability_explainer():
    """Create executability explainer"""
    return ExecutabilityExplainer()


# Test 1: HypothesisArtifact Sandbox Constraints
def test_hypothesis_sandbox_constraints():
    """Test that HypothesisArtifact enforces sandbox constraints"""
    # Valid hypothesis
    hyp = HypothesisArtifact(
        hypothesis_id="hyp_001",
        plan_summary="Test plan",
        assumptions=["Test assumption"],
        dependencies=[],
        risk_flags=[],
        proposed_actions=[{"action": "test"}],
    )

    assert hyp.status == "sandbox"
    assert hyp.confidence is None
    assert hyp.execution_rights is False


# Test 2: HypothesisArtifact Cannot Have Execution Rights
def test_hypothesis_cannot_have_execution_rights():
    """Test that System A cannot create artifacts with execution rights"""
    with pytest.raises(ValueError, match="execution_rights MUST be false"):
        HypothesisArtifact(
            hypothesis_id="hyp_001",
            plan_summary="Test plan",
            assumptions=["Test assumption"],
            dependencies=[],
            risk_flags=[],
            proposed_actions=[{"action": "test"}],
            execution_rights=True,  # INVALID
        )


# Test 3: HypothesisArtifact Cannot Have Confidence
def test_hypothesis_cannot_have_confidence():
    """Test that System A cannot assign confidence"""
    with pytest.raises(ValueError, match="confidence MUST be null"):
        HypothesisArtifact(
            hypothesis_id="hyp_001",
            plan_summary="Test plan",
            assumptions=["Test assumption"],
            dependencies=[],
            risk_flags=[],
            proposed_actions=[{"action": "test"}],
            confidence=0.8,  # INVALID
        )


# Test 4: HypothesisArtifact Must Be Sandbox
def test_hypothesis_must_be_sandbox():
    """Test that status must be 'sandbox'"""
    with pytest.raises(ValueError, match="status MUST be 'sandbox'"):
        HypothesisArtifact(
            hypothesis_id="hyp_001",
            plan_summary="Test plan",
            assumptions=["Test assumption"],
            dependencies=[],
            risk_flags=[],
            proposed_actions=[{"action": "test"}],
            status="executable",  # INVALID
        )


# Test 5: Intake Rejects Missing Assumptions
def test_intake_rejects_missing_assumptions(intake_service):
    """Test that intake fails when assumptions are missing"""
    hyp = HypothesisArtifact(
        hypothesis_id="hyp_002",
        plan_summary="Test plan with sufficient length for validation",
        assumptions=[],  # NO ASSUMPTIONS
        dependencies=[],
        risk_flags=[],
        proposed_actions=[{"action": "test"}],
    )

    result = intake_service.intake_hypothesis(hyp)

    assert not result.admitted
    # Schema validation catches empty assumptions
    assert any("should be non-empty" in reason or "No explicit assumptions" in reason or "too short" in reason
               for reason in result.rejection_reasons)


# Test 6: Intake Validates Schema
def test_intake_validates_schema(intake_service, valid_hypothesis):
    """Test that intake validates hypothesis schema"""
    result = intake_service.intake_hypothesis(valid_hypothesis)

    assert result.admitted
    assert len(result.extracted_assumptions) == 3
    assert len(result.verification_requests) > 0


# Test 7: Claim Extraction
def test_claim_extraction(valid_hypothesis):
    """Test claim extraction from hypothesis"""
    extractor = ClaimExtractor()
    claims = extractor.extract_claims(valid_hypothesis)

    # Should extract claims from plan summary
    assert len(claims) > 0


# Test 8: Verification Request Generation
def test_verification_request_generation(valid_hypothesis):
    """Test verification request generation"""
    generator = VerificationRequestGenerator()

    claims = ["Traffic is normal"]
    assumptions = ["Weather is clear"]

    requests = generator.generate_requests(
        hypothesis=valid_hypothesis,
        claims=claims,
        assumptions=assumptions,
    )

    assert len(requests) >= 2  # At least claims + assumptions


# Test 9: Compilation Fails Without Verification
def test_compilation_fails_without_verification(packet_compiler, valid_hypothesis):
    """Test that compilation fails when verifications are incomplete"""
    # Create incomplete verifications
    verifications = [
        VerificationArtifact.create(
            request_id="req_001",
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.PENDING,
            result=None,
            evidence={},
            method="pending",
            verified_by="system",
        )
    ]

    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.8,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=[],
        gates_required=["gate_001"],
    )

    assert not result.success
    assert BlockingReason.VERIFICATION_INCOMPLETE in result.blocking_reasons


# Test 10: Compilation Fails Without Gates
def test_compilation_fails_without_gates(packet_compiler, valid_hypothesis):
    """Test that compilation fails when gates are not satisfied"""
    # Create complete verifications
    verifications = [
        VerificationArtifact.create(
            request_id="req_001",
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.VERIFIED,
            result=True,
            evidence={"verified": True},
            method="deterministic",
            verified_by="system",
        )
    ]

    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.8,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=[],  # NO GATES SATISFIED
        gates_required=["gate_001", "gate_002"],
    )

    assert not result.success
    assert BlockingReason.GATES_NOT_SATISFIED in result.blocking_reasons
    assert len(result.gates_blocking) == 2


# Test 11: Compilation Fails With Low Confidence
def test_compilation_fails_low_confidence(packet_compiler, valid_hypothesis):
    """Test that compilation fails when confidence is too low"""
    verifications = [
        VerificationArtifact.create(
            request_id="req_001",
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.VERIFIED,
            result=True,
            evidence={"verified": True},
            method="deterministic",
            verified_by="system",
        )
    ]

    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.5,  # TOO LOW
        contradictions=0,
        authority_level="medium",
        gates_satisfied=["gate_001"],
        gates_required=["gate_001"],
    )

    assert not result.success
    assert BlockingReason.CONFIDENCE_TOO_LOW in result.blocking_reasons


# Test 12: Compilation Fails With High Contradictions
def test_compilation_fails_high_contradictions(packet_compiler, valid_hypothesis):
    """Test that compilation fails when contradictions are too high"""
    verifications = [
        VerificationArtifact.create(
            request_id="req_001",
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.VERIFIED,
            result=True,
            evidence={"verified": True},
            method="deterministic",
            verified_by="system",
        )
    ]

    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.8,
        contradictions=5,  # TOO HIGH
        authority_level="medium",
        gates_satisfied=["gate_001"],
        gates_required=["gate_001"],
    )

    assert not result.success
    assert BlockingReason.CONTRADICTIONS_TOO_HIGH in result.blocking_reasons


# Test 13: Compilation Succeeds With All Criteria Met
def test_compilation_succeeds_all_criteria_met(packet_compiler, valid_hypothesis):
    """Test that compilation succeeds when all criteria are met"""
    verifications = [
        VerificationArtifact.create(
            request_id="req_001",
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.VERIFIED,
            result=True,
            evidence={"verified": True},
            method="deterministic",
            verified_by="system",
        )
    ]

    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.8,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=["gate_001"],
        gates_required=["gate_001"],
    )

    assert result.success
    assert result.execution_packet is not None
    assert result.execution_packet["execution_rights"] is True
    assert "signature" in result.execution_packet


# Test 14: ExecutionPacket Has Signature
def test_execution_packet_has_signature(packet_compiler, valid_hypothesis):
    """Test that compiled ExecutionPacket has cryptographic signature"""
    verifications = [
        VerificationArtifact.create(
            request_id="req_001",
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.VERIFIED,
            result=True,
            evidence={"verified": True},
            method="deterministic",
            verified_by="system",
        )
    ]

    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.8,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=["gate_001"],
        gates_required=["gate_001"],
    )

    assert result.success
    packet = result.execution_packet

    assert "signature" in packet
    assert len(packet["signature"]) == 64  # SHA-256
    assert "nonce" in packet
    assert packet["execution_rights"] is True


# Test 15: Executability Explainer
def test_executability_explainer(executability_explainer, valid_hypothesis):
    """Test executability explainer generates feedback"""
    compilation_result = CompilationResult(
        hypothesis_id=valid_hypothesis.hypothesis_id,
        success=False,
        execution_packet=None,
        blocking_reasons=[
            BlockingReason.CONFIDENCE_TOO_LOW,
            BlockingReason.GATES_NOT_SATISFIED,
        ],
        confidence=0.5,
        authority_level="low",
        gates_satisfied=[],
        gates_blocking=["gate_001", "gate_002"],
        verifications_complete=[],
        verifications_pending=["ver_001"],
        required_evidence=["Increase confidence", "Satisfy gates"],
    )

    feedback = executability_explainer.explain(
        hypothesis=valid_hypothesis,
        compilation_result=compilation_result,
        verifications=[],
    )

    assert feedback.hypothesis_id == valid_hypothesis.hypothesis_id
    assert len(feedback.blocking_reasons) == 2
    assert len(feedback.gates_blocking) == 2
    assert len(feedback.required_evidence) == 2


# Test 16: Terminal Output Formatting
def test_terminal_output_formatting(executability_explainer, valid_hypothesis):
    """Test terminal output has proper formatting"""
    compilation_result = CompilationResult(
        hypothesis_id=valid_hypothesis.hypothesis_id,
        success=False,
        execution_packet=None,
        blocking_reasons=[BlockingReason.CONFIDENCE_TOO_LOW],
        confidence=0.5,
        authority_level="low",
        gates_satisfied=[],
        gates_blocking=["gate_001"],
        verifications_complete=[],
        verifications_pending=["ver_001"],
        required_evidence=["Increase confidence"],
    )

    feedback = executability_explainer.explain(
        hypothesis=valid_hypothesis,
        compilation_result=compilation_result,
        verifications=[],
    )

    terminal_output = feedback.to_terminal_output()

    # Check for ANSI color codes (neon green)
    assert "\033[92m" in terminal_output  # Green
    assert "\033[91m" in terminal_output  # Red
    assert "NOT EXECUTABLE" in terminal_output
    assert "BLOCKING REASONS" in terminal_output


# Test 17: End-to-End Workflow
def test_end_to_end_workflow(intake_service, packet_compiler, executability_explainer, valid_hypothesis):
    """Test complete workflow from hypothesis to compilation"""
    # Step 1: Intake hypothesis
    intake_result = intake_service.intake_hypothesis(valid_hypothesis)

    assert intake_result.admitted
    assert len(intake_result.verification_requests) > 0

    # Step 2: Create verifications (simulate completion)
    verifications = []
    for req in intake_result.verification_requests:
        verification = VerificationArtifact.create(
            request_id=req.request_id,
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.VERIFIED,
            result=True,
            evidence={"verified": True},
            method="deterministic",
            verified_by="system",
        )
        verifications.append(verification)

    # Step 3: Attempt compilation (should fail - gates not satisfied)
    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.8,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=[],
        gates_required=intake_result.gate_proposals,
    )

    assert not result.success
    assert BlockingReason.GATES_NOT_SATISFIED in result.blocking_reasons

    # Step 4: Get feedback
    feedback = executability_explainer.explain(
        hypothesis=valid_hypothesis,
        compilation_result=result,
        verifications=verifications,
    )

    assert len(feedback.gates_blocking) > 0
    assert len(feedback.required_evidence) > 0


# Test 18: Integrity Verification
def test_hypothesis_integrity_verification(valid_hypothesis):
    """Test hypothesis integrity verification"""
    assert valid_hypothesis.verify_integrity()

    # Tamper with hypothesis
    valid_hypothesis.plan_summary = "Tampered plan"

    # Should fail verification
    assert not valid_hypothesis.verify_integrity()


# Test 19: Verification Artifact Provenance
def test_verification_artifact_provenance():
    """Test verification artifact includes provenance"""
    verification = VerificationArtifact.create(
        request_id="req_001",
        hypothesis_id="hyp_001",
        status=VerificationStatus.VERIFIED,
        result=True,
        evidence={"verified": True},
        method="deterministic",
        verified_by="system",
        provenance={"parent": "hyp_001"},
    )

    assert verification.provenance == {"parent": "hyp_001"}
    assert len(verification.integrity_hash) == 64


# Test 20: Gate Proposals Generated
def test_gate_proposals_generated(intake_service, valid_hypothesis):
    """Test that intake generates gate proposals"""
    result = intake_service.intake_hypothesis(valid_hypothesis)

    assert result.admitted
    assert len(result.gate_proposals) > 0

    # Should have verification gate
    assert any("verification_gate" in gate for gate in result.gate_proposals)

    # Should have assumption gate
    assert any("assumption_gate" in gate for gate in result.gate_proposals)


# Test 21: Compilation Gate Multi-Criteria
def test_compilation_gate_multi_criteria():
    """Test compilation gate checks all criteria"""
    gate = CompilationGate(
        confidence_threshold=0.7,
        max_contradictions=0,
        min_authority="medium",
    )

    # All criteria met
    can_compile, reasons = gate.check(
        confidence=0.8,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=["gate_001"],
        gates_required=["gate_001"],
        verifications_complete=["ver_001"],
        verifications_required=["ver_001"],
        risk_flags=[],
    )

    assert can_compile
    assert len(reasons) == 0

    # Confidence too low
    can_compile, reasons = gate.check(
        confidence=0.5,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=["gate_001"],
        gates_required=["gate_001"],
        verifications_complete=["ver_001"],
        verifications_required=["ver_001"],
        risk_flags=[],
    )

    assert not can_compile
    assert BlockingReason.CONFIDENCE_TOO_LOW in reasons


# Test 22: Risk Flags Block Compilation
def test_risk_flags_block_compilation(packet_compiler, valid_hypothesis):
    """Test that risk flags block compilation"""
    # Add risk flags
    valid_hypothesis.risk_flags = ["High latency risk", "Data loss risk"]

    verifications = [
        VerificationArtifact.create(
            request_id="req_001",
            hypothesis_id=valid_hypothesis.hypothesis_id,
            status=VerificationStatus.VERIFIED,
            result=True,
            evidence={"verified": True},
            method="deterministic",
            verified_by="system",
        )
    ]

    result = packet_compiler.attempt_compilation(
        hypothesis=valid_hypothesis,
        verifications=verifications,
        confidence=0.8,
        contradictions=0,
        authority_level="medium",
        gates_satisfied=["gate_001"],
        gates_required=["gate_001"],
    )

    assert not result.success
    assert BlockingReason.RISK_FLAGS_PRESENT in result.blocking_reasons


# Test 23: Statistics Tracking
def test_statistics_tracking(intake_service, packet_compiler):
    """Test that statistics are tracked"""
    # Initial stats
    intake_stats = intake_service.get_stats()
    assert intake_stats["hypotheses_received"] == 0

    # Intake hypothesis
    hyp = HypothesisArtifact(
        hypothesis_id="hyp_stats",
        plan_summary="Test plan with sufficient length for validation",
        assumptions=["Test assumption"],
        dependencies=[],
        risk_flags=[],
        proposed_actions=[{"action": "test"}],
    )

    intake_service.intake_hypothesis(hyp)

    # Check stats updated
    intake_stats = intake_service.get_stats()
    assert intake_stats["hypotheses_received"] == 1
    assert intake_stats["hypotheses_admitted"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
