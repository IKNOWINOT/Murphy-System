"""
Tests for Security Plane - Access Control & Authorization
=========================================================

Tests zero-trust access control with continuous trust re-computation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from src.security_plane.access_control import (
    AccessDecision,
    CapabilityScope,
    Capability,
    AccessRequest,
    AccessGrant,
    TrustRecomputer,
    AuthorityBandEnforcer,
    CapabilityManager,
    ZeroTrustAccessController
)
from src.security_plane.schemas import TrustScore, AuthorityLevel, TrustLevel


def create_trust_score(confidence: float, hours_ago: int = 0, decay_rate: float = 0.1) -> TrustScore:
    """Helper to create TrustScore with proper schema"""
    computed_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)

    # Determine trust level from confidence
    if confidence >= 0.9:
        trust_level = TrustLevel.HIGH
    elif confidence >= 0.7:
        trust_level = TrustLevel.MEDIUM
    elif confidence >= 0.5:
        trust_level = TrustLevel.LOW
    else:
        trust_level = TrustLevel.NONE

    return TrustScore(
        identity_id="user1",
        trust_level=trust_level,
        confidence=confidence,
        computed_at=computed_at,
        cryptographic_proof_strength=confidence,
        behavioral_consistency=confidence,
        confidence_stability=confidence,
        artifact_lineage_valid=True,
        gate_history_clean=True,
        telemetry_coherent=True,
        decay_rate=decay_rate
    )


class TestCapability:
    """Test capability model"""

    def test_capability_creation(self):
        """Test creating a capability"""
        cap = Capability(
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="execution_packets/*",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            granted_by="admin",
            granted_at=datetime.now(timezone.utc)
        )

        assert cap.scope == CapabilityScope.READ_ONLY
        assert cap.resource_pattern == "execution_packets/*"
        assert not cap.is_expired()

    def test_capability_expiration(self):
        """Test capability expiration"""
        cap = Capability(
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            granted_by="admin",
            granted_at=datetime.now(timezone.utc) - timedelta(minutes=16)
        )

        assert cap.is_expired()

    def test_capability_resource_matching(self):
        """Test resource pattern matching"""
        cap = Capability(
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="execution_packets/*",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            granted_by="admin",
            granted_at=datetime.now(timezone.utc)
        )

        assert cap.matches_resource("execution_packets/123")
        assert cap.matches_resource("execution_packets/abc")
        assert not cap.matches_resource("confidence_engine/read")


class TestTrustRecomputer:
    """Test trust score re-computation"""

    def test_trust_decay(self):
        """Test trust score decays over time"""
        recomputer = TrustRecomputer(decay_rate=0.1)

        # Create trust score from 1 hour ago
        old_trust = create_trust_score(confidence=1.0, hours_ago=1, decay_rate=0.1)

        new_trust = recomputer.recompute_trust(old_trust, "user1")

        # Should decay by ~10% per hour
        assert new_trust.confidence < old_trust.confidence
        assert new_trust.confidence >= 0.85  # (1 - 0.1)^1 = 0.9

    def test_behavior_signals_positive(self):
        """Test positive behavior signals increase trust"""
        recomputer = TrustRecomputer(decay_rate=0.1)

        # Add positive signals
        recomputer.add_behavior_signal("user1", 0.05, "good_behavior")
        recomputer.add_behavior_signal("user1", 0.05, "good_behavior")

        old_trust = create_trust_score(confidence=0.7, hours_ago=0, decay_rate=0.1)

        new_trust = recomputer.recompute_trust(old_trust, "user1")

        # Should increase due to positive signals
        assert new_trust.confidence > old_trust.confidence

    def test_behavior_signals_negative(self):
        """Test negative behavior signals decrease trust"""
        recomputer = TrustRecomputer(decay_rate=0.1)

        # Add negative signals
        recomputer.add_behavior_signal("user1", -0.1, "bad_behavior")

        old_trust = create_trust_score(confidence=0.7, hours_ago=0, decay_rate=0.1)

        new_trust = recomputer.recompute_trust(old_trust, "user1")

        # Should decrease due to negative signals
        assert new_trust.confidence < old_trust.confidence


class TestAuthorityBandEnforcer:
    """Test authority band enforcement"""

    def test_authority_thresholds(self):
        """Test authority level computation from trust scores"""
        enforcer = AuthorityBandEnforcer()

        assert enforcer.compute_authority_level(0.0) == AuthorityLevel.NONE
        assert enforcer.compute_authority_level(0.5) == AuthorityLevel.LOW
        assert enforcer.compute_authority_level(0.7) == AuthorityLevel.MEDIUM
        assert enforcer.compute_authority_level(0.85) == AuthorityLevel.HIGH
        assert enforcer.compute_authority_level(0.95) == AuthorityLevel.CRITICAL

    def test_authority_sufficiency(self):
        """Test checking if authority is sufficient"""
        enforcer = AuthorityBandEnforcer()

        # HIGH is sufficient for MEDIUM
        assert enforcer.check_authority_sufficient(
            AuthorityLevel.HIGH,
            AuthorityLevel.MEDIUM
        )

        # MEDIUM is NOT sufficient for HIGH
        assert not enforcer.check_authority_sufficient(
            AuthorityLevel.MEDIUM,
            AuthorityLevel.HIGH
        )

        # CRITICAL is sufficient for everything
        assert enforcer.check_authority_sufficient(
            AuthorityLevel.CRITICAL,
            AuthorityLevel.CRITICAL
        )

    def test_authority_history_tracking(self):
        """Test authority change tracking"""
        enforcer = AuthorityBandEnforcer()

        enforcer.record_authority_change("user1", AuthorityLevel.LOW)
        enforcer.record_authority_change("user1", AuthorityLevel.MEDIUM)
        enforcer.record_authority_change("user1", AuthorityLevel.HIGH)

        trend = enforcer.get_authority_trend("user1")
        assert trend == "increasing"

    def test_authority_trend_decreasing(self):
        """Test detecting decreasing authority trend"""
        enforcer = AuthorityBandEnforcer()

        enforcer.record_authority_change("user1", AuthorityLevel.HIGH)
        enforcer.record_authority_change("user1", AuthorityLevel.MEDIUM)
        enforcer.record_authority_change("user1", AuthorityLevel.LOW)

        trend = enforcer.get_authority_trend("user1")
        assert trend == "decreasing"


class TestCapabilityManager:
    """Test capability management"""

    def test_grant_capability(self):
        """Test granting a capability"""
        manager = CapabilityManager()

        cap = manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin"
        )

        assert cap.scope == CapabilityScope.READ_ONLY
        assert not cap.is_expired()

    def test_get_capabilities(self):
        """Test retrieving capabilities"""
        manager = CapabilityManager()

        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin"
        )

        caps = manager.get_capabilities("user1")
        assert len(caps) == 1
        assert caps[0].scope == CapabilityScope.READ_ONLY

    def test_get_capabilities_filtered(self):
        """Test retrieving capabilities filtered by resource"""
        manager = CapabilityManager()

        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin"
        )

        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.WRITE_DATA,
            resource_pattern="data/*",
            granted_by="admin"
        )

        caps = manager.get_capabilities("user1", "test/123")
        assert len(caps) == 1
        assert caps[0].resource_pattern == "test/*"

    def test_revoke_capability(self):
        """Test revoking capabilities"""
        manager = CapabilityManager()

        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin"
        )

        revoked = manager.revoke_capability("user1", "test/*")
        assert revoked == 1

        caps = manager.get_capabilities("user1")
        assert len(caps) == 0

    def test_cleanup_expired(self):
        """Test cleaning up expired capabilities"""
        manager = CapabilityManager()

        # Grant expired capability
        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin",
            ttl=timedelta(seconds=-1)  # Already expired
        )

        manager.cleanup_expired()

        caps = manager.get_capabilities("user1")
        assert len(caps) == 0


class TestZeroTrustAccessController:
    """Test zero-trust access control"""

    def test_access_granted(self):
        """Test access granted when all conditions met"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        # Grant capability
        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin"
        )

        # Create high trust score
        trust = create_trust_score(confidence=0.9)

        request = AccessRequest(
            principal_id="user1",
            resource="test/123",
            action="read"
        )

        grant = controller.evaluate_access_request(
            request,
            trust,
            AuthorityLevel.MEDIUM
        )

        assert grant.decision == AccessDecision.GRANTED
        assert len(grant.capabilities_used) > 0

    def test_access_denied_no_capability(self):
        """Test access denied when no matching capability"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        trust = create_trust_score(confidence=0.9)

        request = AccessRequest(
            principal_id="user1",
            resource="test/123",
            action="read"
        )

        grant = controller.evaluate_access_request(
            request,
            trust,
            AuthorityLevel.MEDIUM
        )

        assert grant.decision == AccessDecision.DENIED

    def test_access_requires_elevation(self):
        """Test access requires elevation when authority insufficient"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        # Grant capability
        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin"
        )

        # Low trust score = LOW authority
        trust = create_trust_score(confidence=0.6)

        request = AccessRequest(
            principal_id="user1",
            resource="test/123",
            action="read"
        )

        # Require HIGH authority
        grant = controller.evaluate_access_request(
            request,
            trust,
            AuthorityLevel.HIGH
        )

        assert grant.decision == AccessDecision.REQUIRES_ELEVATION

    def test_access_requires_reauth(self):
        """Test access requires re-authentication when trust too low"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        # Very low trust score
        trust = create_trust_score(confidence=0.2)

        request = AccessRequest(
            principal_id="user1",
            resource="test/123",
            action="read"
        )

        grant = controller.evaluate_access_request(
            request,
            trust,
            AuthorityLevel.LOW
        )

        assert grant.decision == AccessDecision.REQUIRES_REAUTH

    def test_access_frozen(self):
        """Test access denied when principal frozen"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        # Freeze principal
        controller.freeze_principal("user1", "security_violation")

        trust = create_trust_score(confidence=0.9)

        request = AccessRequest(
            principal_id="user1",
            resource="test/123",
            action="read"
        )

        grant = controller.evaluate_access_request(
            request,
            trust,
            AuthorityLevel.LOW
        )

        assert grant.decision == AccessDecision.FROZEN

    def test_unfreeze_principal(self):
        """Test unfreezing a principal"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        controller.freeze_principal("user1", "test")
        assert "user1" in controller.frozen_principals

        controller.unfreeze_principal("user1")
        assert "user1" not in controller.frozen_principals

    def test_access_statistics(self):
        """Test access statistics tracking"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        # Grant capability
        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin"
        )

        trust = create_trust_score(confidence=0.9)

        # Make several requests
        for i in range(5):
            request = AccessRequest(
                principal_id="user1",
                resource="test/123",
                action="read"
            )
            controller.evaluate_access_request(request, trust, AuthorityLevel.MEDIUM)

        stats = controller.get_access_statistics("user1")
        assert stats["total_requests"] == 5
        assert stats["granted"] == 5


class TestAccessIntegration:
    """Test integrated access control scenarios"""

    def test_trust_decay_reduces_authority(self):
        """Test that trust decay reduces authority over time"""
        recomputer = TrustRecomputer(decay_rate=0.5)  # High decay
        enforcer = AuthorityBandEnforcer()

        # Start with high trust
        old_trust = create_trust_score(confidence=0.95, hours_ago=2, decay_rate=0.5)

        # Recompute after 2 hours
        new_trust = recomputer.recompute_trust(old_trust, "user1")

        old_authority = enforcer.compute_authority_level(old_trust.confidence)
        new_authority = enforcer.compute_authority_level(new_trust.confidence)

        # Authority should decrease
        assert old_authority == AuthorityLevel.CRITICAL
        assert new_authority.value != AuthorityLevel.CRITICAL.value

    def test_positive_behavior_maintains_authority(self):
        """Test that positive behavior maintains authority"""
        recomputer = TrustRecomputer(decay_rate=0.1)
        enforcer = AuthorityBandEnforcer()

        # Add many positive signals
        for i in range(10):
            recomputer.add_behavior_signal("user1", 0.02, "good_behavior")

        trust = create_trust_score(confidence=0.7)

        new_trust = recomputer.recompute_trust(trust, "user1")

        # Trust should increase
        assert new_trust.confidence > trust.confidence

    def test_capability_expiration_denies_access(self):
        """Test that expired capabilities deny access"""
        recomputer = TrustRecomputer()
        enforcer = AuthorityBandEnforcer()
        manager = CapabilityManager()
        controller = ZeroTrustAccessController(recomputer, enforcer, manager)

        # Grant short-lived capability
        manager.grant_capability(
            principal_id="user1",
            scope=CapabilityScope.READ_ONLY,
            resource_pattern="test/*",
            granted_by="admin",
            ttl=timedelta(seconds=-1)  # Already expired
        )

        trust = create_trust_score(confidence=0.9)

        request = AccessRequest(
            principal_id="user1",
            resource="test/123",
            action="read"
        )

        grant = controller.evaluate_access_request(
            request,
            trust,
            AuthorityLevel.MEDIUM
        )

        # Should be denied due to expired capability
        assert grant.decision == AccessDecision.DENIED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
