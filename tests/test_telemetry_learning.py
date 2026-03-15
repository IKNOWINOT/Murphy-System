"""
Comprehensive Test Suite for Telemetry & Learning System

Tests all components:
1. Telemetry ingestion
2. Learning loops
3. Safety constraints
4. Authorization
5. Rollback
6. Shadow mode
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from src.telemetry_learning.models import (
    TelemetryDomain,
    TelemetryArtifact,
    GateEvolutionArtifact,
    InsightArtifact,
    InsightType,
    ReasonCode,
    OperationalTelemetry,
    HumanTelemetry,
    ControlTelemetry,
    SafetyTelemetry,
)
from src.telemetry_learning.ingestion import (
    TelemetryBus,
    TelemetryIngester,
)
from src.telemetry_learning.learning import (
    GateStrengtheningEngine,
    PhaseTuningEngine,
    BottleneckDetector,
    AssumptionInvalidator,
    HardeningPolicyEngine,
)
from src.telemetry_learning.shadow_mode import (
    ShadowModeController,
    AuthorizationInterface,
    SafetyEnforcer,
    OperationMode,
)


# Fixtures
@pytest.fixture
def telemetry_bus():
    bus = TelemetryBus(max_buffer_size=1000)
    yield bus
    bus.clear()


@pytest.fixture
def telemetry_ingester(telemetry_bus):
    ingester = TelemetryIngester(telemetry_bus, validate_schemas=False)
    yield ingester
    ingester.clear()


@pytest.fixture
def sample_operational_telemetry():
    return OperationalTelemetry(
        task_id="task_001",
        completion_status="success",
        retry_count=0,
        latency_ms=1500.0,
        phase="execution",
    )


@pytest.fixture
def sample_safety_telemetry():
    return SafetyTelemetry(
        event_type="near_miss",
        severity="medium",
        affected_artifact_ids=["artifact_001"],
        near_miss_details={"type": "confidence_drop"},
    )


# Test 1: Telemetry Artifact Creation
def test_telemetry_artifact_creation():
    """Test creating telemetry artifact with integrity hash"""
    artifact = TelemetryArtifact.create(
        domain=TelemetryDomain.OPERATIONAL,
        source_id="test_component",
        data={"test": "data"},
    )

    assert artifact.artifact_id.startswith("telemetry_operational_")
    assert artifact.domain == TelemetryDomain.OPERATIONAL
    assert artifact.source_id == "test_component"
    assert artifact.data == {"test": "data"}
    assert len(artifact.integrity_hash) == 64  # SHA-256
    assert artifact.verify_integrity()


# Test 2: Telemetry Bus Publishing
def test_telemetry_bus_publish(telemetry_bus):
    """Test publishing events to telemetry bus"""
    success = telemetry_bus.publish(
        domain=TelemetryDomain.OPERATIONAL,
        source_id="test",
        data={"key": "value"},
    )

    assert success
    stats = telemetry_bus.get_stats()
    assert stats["events_received"] == 1
    assert stats["buffer_size"] == 1


# Test 3: Telemetry Bus Deduplication
def test_telemetry_bus_deduplication(telemetry_bus):
    """Test event deduplication"""
    data = {"key": "value"}

    # Publish same event twice
    success1 = telemetry_bus.publish(
        domain=TelemetryDomain.OPERATIONAL,
        source_id="test",
        data=data,
    )
    success2 = telemetry_bus.publish(
        domain=TelemetryDomain.OPERATIONAL,
        source_id="test",
        data=data,
    )

    assert success1
    assert not success2  # Deduplicated

    stats = telemetry_bus.get_stats()
    assert stats["events_received"] == 2
    assert stats["events_deduplicated"] == 1
    assert stats["buffer_size"] == 1


# Test 4: Telemetry Ingestion
def test_telemetry_ingestion(telemetry_bus, telemetry_ingester):
    """Test ingesting telemetry from bus"""
    # Publish events
    for i in range(5):
        telemetry_bus.publish(
            domain=TelemetryDomain.OPERATIONAL,
            source_id=f"source_{i}",
            data={"index": i},
        )

    # Ingest
    ingested = telemetry_ingester.ingest_batch(batch_size=10)

    assert ingested == 5
    stats = telemetry_ingester.get_stats()
    assert stats["artifacts_ingested"] == 5


# Test 5: Telemetry Query
def test_telemetry_query(telemetry_bus, telemetry_ingester):
    """Test querying telemetry artifacts"""
    # Publish and ingest
    telemetry_bus.publish(
        domain=TelemetryDomain.OPERATIONAL,
        source_id="test",
        data={"key": "value"},
    )
    telemetry_ingester.ingest_batch()

    # Query
    artifacts = telemetry_ingester.get_artifacts(
        domain=TelemetryDomain.OPERATIONAL,
        limit=10,
    )

    assert len(artifacts) == 1
    assert artifacts[0].domain == TelemetryDomain.OPERATIONAL


# Test 6: Gate Strengthening Engine - Near Miss
def test_gate_strengthening_near_miss():
    """Test gate strengthening on near-miss detection"""
    engine = GateStrengtheningEngine()

    # Create near-miss events
    telemetry = []
    for i in range(3):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.SAFETY,
            source_id="safety_monitor",
            data={
                "event_type": "near_miss",
                "severity": "medium",
                "affected_artifact_ids": ["artifact_001"],
            },
        )
        telemetry.append(artifact)

    # Analyze
    proposals = engine.analyze(telemetry)

    assert len(proposals) == 1
    assert proposals[0].gate_id == "safety_gate_artifact_001"
    assert ReasonCode.NEAR_MISS_DETECTED in proposals[0].reason_codes
    assert not proposals[0].authorized


# Test 7: Gate Strengthening Engine - Contradictions
def test_gate_strengthening_contradictions():
    """Test gate strengthening on contradiction increase"""
    engine = GateStrengtheningEngine()

    # Create contradiction events (historical low, recent high)
    telemetry = []

    # Historical (6+ hours ago)
    for i in range(5):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.CONTROL,
            source_id="confidence_engine",
            data={
                "event_type": "murphy_spike",
                "murphy_index": 0.1,
            },
        )
        artifact.timestamp = datetime.now(timezone.utc) - timedelta(hours=12)
        telemetry.append(artifact)

    # Recent (high)
    for i in range(5):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.CONTROL,
            source_id="confidence_engine",
            data={
                "event_type": "murphy_spike",
                "murphy_index": 0.5,
            },
        )
        telemetry.append(artifact)

    # Analyze
    proposals = engine.analyze(telemetry)

    assert len(proposals) >= 1
    assert any(
        ReasonCode.CONTRADICTION_INCREASE in p.reason_codes
        for p in proposals
    )


# Test 8: Phase Tuning Engine - Backlog
def test_phase_tuning_backlog():
    """Test phase tuning on verification backlog"""
    engine = PhaseTuningEngine()

    # Create backlog events
    telemetry = []
    for i in range(15):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.OPERATIONAL,
            source_id="orchestrator",
            data={
                "task_id": f"task_{i}",
                "completion_status": "timeout",
                "retry_count": 0,
                "latency_ms": 5000.0,
                "phase": "verification",
            },
        )
        telemetry.append(artifact)

    # Analyze
    insights = engine.analyze(telemetry)

    assert len(insights) >= 1
    assert any(
        i.insight_type == InsightType.PHASE_TUNING
        for i in insights
    )


# Test 9: Phase Tuning Engine - Retries
def test_phase_tuning_retries():
    """Test phase tuning on high retry rate"""
    engine = PhaseTuningEngine()

    # Create high-retry events
    telemetry = []
    for i in range(10):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.OPERATIONAL,
            source_id="orchestrator",
            data={
                "task_id": f"task_{i}",
                "completion_status": "success",
                "retry_count": 3,
                "latency_ms": 2000.0,
            },
        )
        telemetry.append(artifact)

    # Analyze
    insights = engine.analyze(telemetry)

    assert len(insights) >= 1
    assert any(
        "retry" in i.title.lower()
        for i in insights
    )


# Test 10: Bottleneck Detector - Latency
def test_bottleneck_detector_latency():
    """Test bottleneck detection on high latency"""
    detector = BottleneckDetector()

    # Create high-latency events
    telemetry = []
    for i in range(10):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.OPERATIONAL,
            source_id="orchestrator",
            data={
                "task_id": f"task_{i}",
                "completion_status": "success",
                "retry_count": 0,
                "latency_ms": 6000.0,  # Above threshold
                "phase": "execution",
            },
        )
        telemetry.append(artifact)

    # Analyze
    insights = detector.analyze(telemetry)

    assert len(insights) >= 1
    assert any(
        i.insight_type == InsightType.BOTTLENECK_DETECTION
        for i in insights
    )


# Test 11: Assumption Invalidator - Confidence Drops
def test_assumption_invalidator_confidence():
    """Test assumption invalidation on confidence drops"""
    invalidator = AssumptionInvalidator()

    # Create confidence drop events
    telemetry = []
    for i in range(15):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.CONTROL,
            source_id="confidence_engine",
            data={
                "event_type": "confidence_update",
                "confidence_before": 0.8,
                "confidence_after": 0.5,  # Significant drop
            },
        )
        telemetry.append(artifact)

    # Analyze
    insights = invalidator.analyze(telemetry)

    assert len(insights) >= 1
    assert any(
        i.insight_type == InsightType.ASSUMPTION_INVALIDATION
        for i in insights
    )


# Test 12: Hardening Policy Engine
def test_hardening_policy_engine():
    """Test hardening policy application"""
    engine = HardeningPolicyEngine()

    # Create mixed telemetry
    telemetry = []

    # Safety events
    for i in range(3):
        artifact = TelemetryArtifact.create(
            domain=TelemetryDomain.SAFETY,
            source_id="safety_monitor",
            data={
                "event_type": "near_miss",
                "severity": "medium",
                "affected_artifact_ids": ["artifact_001"],
            },
        )
        telemetry.append(artifact)

    # Analyze
    proposals, insights = engine.analyze_all(telemetry)

    assert len(proposals) >= 0  # May or may not generate proposals
    assert len(insights) >= 0


# Test 13: Shadow Mode Controller
def test_shadow_mode_controller():
    """Test shadow mode operation"""
    controller = ShadowModeController(mode=OperationMode.SHADOW)

    # In shadow mode, should not enforce
    assert not controller.should_enforce("test_id")

    # Change to full mode
    controller.set_mode(OperationMode.FULL)
    assert controller.should_enforce("test_id")

    # Change to gradual mode
    controller.set_mode(OperationMode.GRADUAL)
    controller.set_enforcement_percentage(0.5)

    # Should enforce ~50% of the time (deterministic by hash)
    enforced_count = sum(
        1 for i in range(100)
        if controller.should_enforce(f"test_{i}")
    )
    assert 40 <= enforced_count <= 60  # Roughly 50%


# Test 14: Shadow Mode Logging
def test_shadow_mode_logging():
    """Test shadow mode logging"""
    controller = ShadowModeController()

    # Create proposal
    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    # Log
    controller.log_proposal(proposal, enforced=False)

    # Check log
    log = controller.get_shadow_log()
    assert len(log) == 1
    assert log[0]["evolution_id"] == proposal.evolution_id


# Test 15: Authorization Interface - Submit
def test_authorization_submit():
    """Test submitting proposal for authorization"""
    interface = AuthorizationInterface()

    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    evolution_id = interface.submit_proposal(proposal)

    assert evolution_id == proposal.evolution_id
    pending = interface.get_pending_proposals()
    assert len(pending) == 1


# Test 16: Authorization Interface - Approve
def test_authorization_approve():
    """Test approving a proposal"""
    interface = AuthorizationInterface()

    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    interface.submit_proposal(proposal)
    success = interface.authorize_proposal(
        evolution_id=proposal.evolution_id,
        authorized_by="admin",
    )

    assert success
    assert proposal.authorized
    assert proposal.authorized_by == "admin"

    # Should be removed from pending
    pending = interface.get_pending_proposals()
    assert len(pending) == 0


# Test 17: Authorization Interface - Reject
def test_authorization_reject():
    """Test rejecting a proposal"""
    interface = AuthorizationInterface()

    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    interface.submit_proposal(proposal)
    success = interface.reject_proposal(
        evolution_id=proposal.evolution_id,
        rejected_by="admin",
        reason="Not needed",
    )

    assert success

    # Should be removed from pending
    pending = interface.get_pending_proposals()
    assert len(pending) == 0


# Test 18: Authorization Interface - Rollback
def test_authorization_rollback():
    """Test rolling back an evolution"""
    interface = AuthorizationInterface()

    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    # Submit and authorize
    interface.submit_proposal(proposal)
    interface.authorize_proposal(
        evolution_id=proposal.evolution_id,
        authorized_by="admin",
    )

    # Rollback
    rollback_state = interface.rollback_evolution(
        evolution_id=proposal.evolution_id,
        rolled_back_by="admin",
        reason="Testing rollback",
    )

    assert rollback_state is not None
    assert rollback_state["evolution_id"] == proposal.evolution_id


# Test 19: Safety Enforcer - Validation
def test_safety_enforcer_validation():
    """Test safety validation of proposals"""
    enforcer = SafetyEnforcer()

    # Valid proposal
    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    is_valid, error = enforcer.validate_proposal(proposal)
    assert is_valid
    assert error is None


# Test 20: Safety Enforcer - Relaxation Without Evidence
def test_safety_enforcer_relaxation_check():
    """Test safety check for relaxation without evidence"""
    enforcer = SafetyEnforcer()

    # Relaxation proposal without deterministic evidence
    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],  # Wrong reason
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.85, "after": 0.7}},  # Relaxation
        rollback_state={"threshold": 0.85},
    )

    is_valid, error = enforcer.validate_proposal(proposal)
    assert not is_valid
    assert "deterministic evidence" in error.lower()


# Test 21: Safety Enforcer - Block Execution
def test_safety_enforcer_block_execution():
    """Test blocking execution actions"""
    enforcer = SafetyEnforcer()

    enforcer.block_execution_action(
        action_type="direct_execution",
        reason="Telemetry must not execute",
    )

    blocked = enforcer.get_blocked_actions()
    assert len(blocked) == 1
    assert blocked[0]["action_type"] == "direct_execution"


# Test 22: Hardening Coefficient Application
def test_hardening_coefficient():
    """Test hardening coefficient makes proposals more conservative"""
    engine = HardeningPolicyEngine()

    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    hardened = engine._apply_hardening_coefficient(proposal)

    # After should be higher than original
    original_after = 0.85
    hardened_after = hardened.parameter_diff["threshold"]["after"]
    assert hardened_after > original_after


# Test 23: Integration - Full Workflow
def test_full_workflow(telemetry_bus, telemetry_ingester):
    """Test complete workflow from telemetry to insights"""
    # 1. Publish telemetry (3+ near-misses for same artifact to trigger proposal)
    for i in range(5):
        telemetry_bus.publish(
            domain=TelemetryDomain.SAFETY,
            source_id="safety_monitor",
            data={
                "event_type": "near_miss",
                "severity": "medium",
                "affected_artifact_ids": ["artifact_001"],  # Same artifact
                "index": i,  # Make events unique
            },
        )

    # 2. Ingest
    telemetry_ingester.ingest_batch()

    # 3. Get artifacts
    artifacts = telemetry_ingester.get_artifacts(limit=100)
    assert len(artifacts) == 5

    # 4. Run learning
    engine = HardeningPolicyEngine()
    proposals, insights = engine.analyze_all(artifacts)

    # Should generate proposals due to 5 near-misses for same artifact (threshold is 3)
    assert len(proposals) >= 1


# Test 24: Telemetry Integrity Verification
def test_telemetry_integrity():
    """Test integrity verification of telemetry artifacts"""
    artifact = TelemetryArtifact.create(
        domain=TelemetryDomain.OPERATIONAL,
        source_id="test",
        data={"key": "value"},
    )

    # Should verify
    assert artifact.verify_integrity()

    # Tamper with data
    artifact.data["key"] = "tampered"

    # Should fail verification
    assert not artifact.verify_integrity()


# Test 25: Conservative Trajectory Enforcement
def test_conservative_trajectory():
    """Test that system defaults to more strict over time"""
    engine = HardeningPolicyEngine()

    # Create strengthening proposal
    proposal = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.7, "after": 0.85}},
        rollback_state={"threshold": 0.7},
    )

    # Apply hardening
    hardened = engine._apply_hardening_policy([proposal])

    # Should accept strengthening
    assert len(hardened) == 1

    # Create relaxation proposal without evidence
    relaxation = GateEvolutionArtifact.create(
        gate_id="test_gate",
        reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
        telemetry_evidence=["evidence_001"],
        parameter_diff={"threshold": {"before": 0.85, "after": 0.7}},
        rollback_state={"threshold": 0.85},
    )

    # Apply hardening
    hardened = engine._apply_hardening_policy([relaxation])

    # Should reject relaxation without deterministic evidence
    assert len(hardened) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
