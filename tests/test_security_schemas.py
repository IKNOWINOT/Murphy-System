"""
Tests for Security Plane Schemas

Tests:
- TrustScore computation and decay
- SecurityArtifact integrity
- ExecutionPacketSignature validation
- AccessRequest and AccessDecision
- SecurityAnomaly detection
- CryptographicKey lifecycle
- SecurityGate creation
- SecurityFreeze enforcement
"""

import pytest
from datetime import datetime, timedelta
import time

from src.security_plane.schemas import (
    TrustScore,
    TrustLevel,
    SecurityArtifact,
    SecurityAction,
    SecurityAnomaly,
    AnomalyType,
    ExecutionPacketSignature,
    CryptographicAlgorithm,
    AuthorityBand,
    AccessRequest,
    AccessDecision,
    SecurityTelemetry,
    CryptographicKey,
    SecurityGate,
    SecurityFreeze
)


class TestTrustScore:
    """Test TrustScore computation and decay."""

    def test_trust_score_creation(self):
        """Test creating a trust score."""
        score = TrustScore(
            identity_id="user-001",
            trust_level=TrustLevel.HIGH,
            confidence=0.95,
            computed_at=datetime.now(),
            cryptographic_proof_strength=1.0,
            behavioral_consistency=0.9,
            confidence_stability=0.95,
            artifact_lineage_valid=True,
            gate_history_clean=True,
            telemetry_coherent=True
        )

        assert score.identity_id == "user-001"
        assert score.trust_level == TrustLevel.HIGH
        assert score.confidence == 0.95

    def test_trust_score_expiry(self):
        """Test trust score expiration."""
        old_time = datetime.now() - timedelta(hours=2)
        score = TrustScore(
            identity_id="user-002",
            trust_level=TrustLevel.MEDIUM,
            confidence=0.8,
            computed_at=old_time,
            cryptographic_proof_strength=0.9,
            behavioral_consistency=0.8,
            confidence_stability=0.85,
            artifact_lineage_valid=True,
            gate_history_clean=True,
            telemetry_coherent=True
        )

        assert score.is_expired(max_age_seconds=3600) is True

    def test_trust_score_decay(self):
        """Test trust score decay over time."""
        old_time = datetime.now() - timedelta(hours=1)
        score = TrustScore(
            identity_id="user-003",
            trust_level=TrustLevel.HIGH,
            confidence=1.0,
            computed_at=datetime.now(),
            cryptographic_proof_strength=1.0,
            behavioral_consistency=1.0,
            confidence_stability=1.0,
            artifact_lineage_valid=True,
            gate_history_clean=True,
            telemetry_coherent=True,
            decay_rate=0.1,
            last_activity=old_time
        )

        decayed = score.compute_decayed_confidence()

        # After 1 hour with 10% decay rate: 1.0 * (1 - 0.1)^1 = 0.9
        assert abs(decayed - 0.9) < 0.01


class TestSecurityArtifact:
    """Test SecurityArtifact integrity."""

    def test_artifact_creation(self):
        """Test creating a security artifact."""
        artifact = SecurityArtifact(
            artifact_id="art-001",
            artifact_type="access_decision",
            timestamp=datetime.now(),
            identity_id="user-001",
            action=SecurityAction.ALLOW,
            trust_score=None,
            authority_band=AuthorityBand.MEDIUM,
            resource_accessed="resource-001",
            rationale="Trust score sufficient",
            contributing_factors={"trust": 0.9, "behavior": 0.85}
        )

        assert artifact.artifact_id == "art-001"
        assert artifact.action == SecurityAction.ALLOW
        assert artifact.integrity_hash is not None

    def test_artifact_integrity_verification(self):
        """Test artifact integrity verification."""
        artifact = SecurityArtifact(
            artifact_id="art-002",
            artifact_type="access_decision",
            timestamp=datetime.now(),
            identity_id="user-002",
            action=SecurityAction.RESTRICT,
            trust_score=None,
            authority_band=AuthorityBand.LOW,
            resource_accessed="resource-002",
            rationale="Trust score insufficient",
            contributing_factors={"trust": 0.5}
        )

        # Verify integrity
        assert artifact.verify_integrity() is True

        # Tamper with artifact
        artifact.rationale = "Modified rationale"

        # Verification should fail
        assert artifact.verify_integrity() is False


class TestExecutionPacketSignature:
    """Test ExecutionPacketSignature validation."""

    def test_signature_creation(self):
        """Test creating an execution packet signature."""
        now = datetime.now()
        signature = ExecutionPacketSignature(
            packet_id="pkt-001",
            signature=b"signature_bytes",
            algorithm=CryptographicAlgorithm.HYBRID,
            signed_at=now,
            signed_by="control-plane",
            time_window_start=now,
            time_window_end=now + timedelta(minutes=5),
            authority_band=AuthorityBand.MEDIUM,
            target_adapter="adapter-001",
            nonce="unique-nonce-001"
        )

        assert signature.packet_id == "pkt-001"
        assert signature.is_valid() is True

    def test_signature_time_window(self):
        """Test signature time window validation."""
        past_time = datetime.now() - timedelta(hours=1)
        signature = ExecutionPacketSignature(
            packet_id="pkt-002",
            signature=b"signature_bytes",
            algorithm=CryptographicAlgorithm.HYBRID,
            signed_at=past_time,
            signed_by="control-plane",
            time_window_start=past_time,
            time_window_end=past_time + timedelta(minutes=5),
            authority_band=AuthorityBand.MEDIUM,
            target_adapter="adapter-002",
            nonce="unique-nonce-002"
        )

        # Time window expired
        assert signature.is_valid() is False

    def test_signature_single_use(self):
        """Test signature single-use enforcement."""
        now = datetime.now()
        signature = ExecutionPacketSignature(
            packet_id="pkt-003",
            signature=b"signature_bytes",
            algorithm=CryptographicAlgorithm.HYBRID,
            signed_at=now,
            signed_by="control-plane",
            time_window_start=now,
            time_window_end=now + timedelta(minutes=5),
            authority_band=AuthorityBand.MEDIUM,
            target_adapter="adapter-003",
            nonce="unique-nonce-003"
        )

        # Initially valid
        assert signature.is_valid() is True

        # Mark as used
        signature.mark_used()

        # No longer valid
        assert signature.is_valid() is False

        # Cannot mark as used again
        with pytest.raises(ValueError, match="already used"):
            signature.mark_used()


class TestAccessRequestAndDecision:
    """Test AccessRequest and AccessDecision."""

    def test_access_request_creation(self):
        """Test creating an access request."""
        request = AccessRequest(
            request_id="req-001",
            identity_id="user-001",
            resource="resource-001",
            operation="read",
            requested_at=datetime.now(),
            purpose="Data analysis",
            scope="minimal",
            duration=timedelta(hours=1),
            required_trust_level=TrustLevel.MEDIUM,
            required_authority_band=AuthorityBand.MEDIUM
        )

        assert request.request_id == "req-001"
        assert request.operation == "read"

    def test_access_decision_creation(self):
        """Test creating an access decision."""
        trust_score = TrustScore(
            identity_id="user-001",
            trust_level=TrustLevel.HIGH,
            confidence=0.9,
            computed_at=datetime.now(),
            cryptographic_proof_strength=1.0,
            behavioral_consistency=0.9,
            confidence_stability=0.9,
            artifact_lineage_valid=True,
            gate_history_clean=True,
            telemetry_coherent=True
        )

        artifact = SecurityArtifact(
            artifact_id="art-003",
            artifact_type="access_decision",
            timestamp=datetime.now(),
            identity_id="user-001",
            action=SecurityAction.ALLOW,
            trust_score=trust_score,
            authority_band=AuthorityBand.HIGH,
            resource_accessed="resource-001",
            rationale="Trust score sufficient",
            contributing_factors={"trust": 0.9}
        )

        decision = AccessDecision(
            decision_id="dec-001",
            request_id="req-001",
            decision=SecurityAction.ALLOW,
            decided_at=datetime.now(),
            trust_score=trust_score,
            authority_granted=AuthorityBand.HIGH,
            rationale="Trust score sufficient",
            time_bound=datetime.now() + timedelta(hours=1),
            scope_restrictions=["read_only"],
            rate_limit=100,
            decided_by="security-plane",
            artifact=artifact
        )

        assert decision.decision == SecurityAction.ALLOW
        assert decision.authority_granted == AuthorityBand.HIGH


class TestSecurityAnomaly:
    """Test SecurityAnomaly detection."""

    def test_anomaly_creation(self):
        """Test creating a security anomaly."""
        anomaly = SecurityAnomaly(
            anomaly_id="anom-001",
            anomaly_type=AnomalyType.UNUSUAL_PATTERN,
            detected_at=datetime.now(),
            identity_id="user-001",
            severity=0.8,
            confidence=0.9,
            description="Unusual call pattern detected",
            evidence={"pattern": "rapid_succession", "count": 100},
            trust_impact=0.3,
            murphy_index_contribution=0.2,
            recommended_action=SecurityAction.THROTTLE,
            escalation_required=False
        )

        assert anomaly.anomaly_type == AnomalyType.UNUSUAL_PATTERN
        assert anomaly.severity == 0.8
        assert anomaly.recommended_action == SecurityAction.THROTTLE


class TestCryptographicKey:
    """Test CryptographicKey lifecycle."""

    def test_key_creation(self):
        """Test creating a cryptographic key."""
        now = datetime.now()
        key = CryptographicKey(
            key_id="key-001",
            key_type="signing",
            algorithm=CryptographicAlgorithm.HYBRID,
            public_key=b"public_key_bytes",
            private_key_encrypted=b"encrypted_private_key",
            created_at=now,
            expires_at=now + timedelta(minutes=10),
            identity_id="user-001",
            capabilities={"sign", "verify"}
        )

        assert key.key_id == "key-001"
        assert key.is_expired() is False

    def test_key_expiry(self):
        """Test key expiration."""
        past_time = datetime.now() - timedelta(hours=1)
        key = CryptographicKey(
            key_id="key-002",
            key_type="encryption",
            algorithm=CryptographicAlgorithm.POST_QUANTUM,
            public_key=b"public_key_bytes",
            private_key_encrypted=b"encrypted_private_key",
            created_at=past_time,
            expires_at=past_time + timedelta(minutes=10),
            identity_id="user-002",
            capabilities={"encrypt", "decrypt"}
        )

        assert key.is_expired() is True

    def test_key_rotation(self):
        """Test key rotation check."""
        now = datetime.now()
        key = CryptographicKey(
            key_id="key-003",
            key_type="key_exchange",
            algorithm=CryptographicAlgorithm.HYBRID,
            public_key=b"public_key_bytes",
            private_key_encrypted=b"encrypted_private_key",
            created_at=now,
            expires_at=now + timedelta(minutes=3),
            identity_id="user-003",
            capabilities={"exchange"}
        )

        # Should rotate (expires in 3 minutes, threshold is 5 minutes)
        assert key.should_rotate(rotation_threshold=timedelta(minutes=5)) is True


class TestSecurityGate:
    """Test SecurityGate creation."""

    def test_gate_creation(self):
        """Test creating a security gate."""
        gate = SecurityGate(
            gate_id="gate-001",
            gate_type="rate_limit",
            created_at=datetime.now(),
            created_by="security-telemetry-agent",
            triggered_by_anomaly="anom-001",
            anomaly_type=AnomalyType.UNUSUAL_PATTERN,
            condition="requests_per_minute < 10",
            threshold=10.0,
            active=True,
            expires_at=datetime.now() + timedelta(hours=1),
            blocks_authority_band=AuthorityBand.HIGH,
            requires_escalation=False
        )

        assert gate.gate_id == "gate-001"
        assert gate.active is True


class TestSecurityFreeze:
    """Test SecurityFreeze enforcement."""

    def test_freeze_creation(self):
        """Test creating a security freeze."""
        freeze = SecurityFreeze(
            freeze_id="freeze-001",
            triggered_at=datetime.now(),
            triggered_by="anom-001",
            identity_id="user-001",
            resource="resource-001",
            reason="Critical anomaly detected",
            severity=0.95,
            anomalies=["anom-001", "anom-002"],
            resolved=False
        )

        assert freeze.freeze_id == "freeze-001"
        assert freeze.resolved is False

    def test_freeze_resolution(self):
        """Test resolving a security freeze."""
        freeze = SecurityFreeze(
            freeze_id="freeze-002",
            triggered_at=datetime.now(),
            triggered_by="anom-003",
            identity_id="user-002",
            resource=None,  # System-wide freeze
            reason="System-wide anomaly",
            severity=1.0,
            anomalies=["anom-003"],
            resolved=False
        )

        # Resolve freeze
        freeze.resolved = True
        freeze.resolved_at = datetime.now()
        freeze.resolved_by = "security-admin"
        freeze.resolution_notes = "Anomaly investigated and cleared"

        assert freeze.resolved is True
        assert freeze.resolved_by == "security-admin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
