"""
Tests for Security Plane - Adaptive Defense System
==================================================

Tests anomaly detection, threat intelligence, and automated response.
"""

import pytest
from datetime import datetime, timezone, timedelta
from src.security_plane.adaptive_defense import (
    ThreatLevel,
    AnomalyType,
    ResponseAction,
    AttackType,
    SecurityEvent,
    Anomaly,
    ThreatIndicator,
    DefenseResponse,
    BehavioralAnomalyDetector,
    StatisticalAnomalyDetector,
    RateLimiter,
    ThreatIntelligence,
    AttackPatternRecognizer,
    AutomatedResponseSystem,
    AdaptiveDefenseStatistics
)


class TestSecurityEvent:
    """Test security event model"""

    def test_security_event_creation(self):
        """Test creating security event"""
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            principal_id="user1",
            event_type="login",
            source_ip="192.168.1.1",
            success=True
        )

        assert event.principal_id == "user1"
        assert event.event_type == "login"
        assert event.success is True

    def test_security_event_to_dict(self):
        """Test converting event to dict"""
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            principal_id="user1",
            event_type="login",
            source_ip="192.168.1.1"
        )

        result = event.to_dict()
        assert isinstance(result, dict)
        assert result["principal_id"] == "user1"


class TestBehavioralAnomalyDetector:
    """Test behavioral anomaly detection"""

    def test_add_event(self):
        """Test adding events"""
        detector = BehavioralAnomalyDetector()

        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            principal_id="user1",
            event_type="login",
            source_ip="192.168.1.1"
        )

        detector.add_event(event)
        assert len(detector.event_history["user1"]) == 1

    def test_build_baseline(self):
        """Test building baseline profile"""
        detector = BehavioralAnomalyDetector()

        # Add 20 events
        for i in range(20):
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=i),
                principal_id="user1",
                event_type="login",
                source_ip="192.168.1.1",
                resource="/api/data",
                action="read"
            )
            detector.add_event(event)

        baseline = detector.build_baseline("user1")

        assert "common_resources" in baseline
        assert "common_actions" in baseline
        assert "common_ips" in baseline

    def test_detect_unusual_ip(self):
        """Test detecting unusual IP address"""
        detector = BehavioralAnomalyDetector()

        # Build baseline with normal IP
        for i in range(20):
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=i),
                principal_id="user1",
                event_type="login",
                source_ip="192.168.1.1"
            )
            detector.add_event(event)

        detector.build_baseline("user1")

        # Event from unusual IP
        unusual_event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            principal_id="user1",
            event_type="login",
            source_ip="10.0.0.1"  # Different IP
        )

        anomaly = detector.detect_anomalies(unusual_event)
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.BEHAVIORAL

    def test_detect_multiple_failures(self):
        """Test detecting multiple failures"""
        detector = BehavioralAnomalyDetector()

        # Add baseline events
        for i in range(20):
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=i),
                principal_id="user1",
                event_type="login",
                source_ip="192.168.1.1",
                success=True
            )
            detector.add_event(event)

        detector.build_baseline("user1")

        # Add multiple failures
        for i in range(5):
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc),
                principal_id="user1",
                event_type="login",
                source_ip="192.168.1.1",
                success=False
            )
            detector.add_event(event)

        # Check for anomaly
        test_event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            principal_id="user1",
            event_type="login",
            source_ip="192.168.1.1",
            success=False
        )

        anomaly = detector.detect_anomalies(test_event)
        assert anomaly is not None
        assert anomaly.threat_level in (ThreatLevel.MEDIUM, ThreatLevel.HIGH)


class TestStatisticalAnomalyDetector:
    """Test statistical anomaly detection"""

    def test_add_metric(self):
        """Test adding metrics"""
        detector = StatisticalAnomalyDetector()

        detector.add_metric("response_time", 100.0)
        assert len(detector.metrics["response_time"]) == 1

    def test_detect_outlier(self):
        """Test detecting statistical outlier"""
        detector = StatisticalAnomalyDetector(threshold=3.0)

        # Add normal values
        for i in range(100):
            detector.add_metric("response_time", 100.0 + i * 0.1)

        # Add outlier
        anomaly = detector.detect_anomaly("response_time", 500.0)

        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.STATISTICAL

    def test_no_anomaly_for_normal_value(self):
        """Test no anomaly for normal value"""
        detector = StatisticalAnomalyDetector()

        # Add normal values
        for i in range(100):
            detector.add_metric("response_time", 100.0)

        # Add normal value
        anomaly = detector.detect_anomaly("response_time", 101.0)

        assert anomaly is None


class TestRateLimiter:
    """Test rate limiting"""

    def test_rate_limit_allows_within_limit(self):
        """Test rate limiter allows requests within limit"""
        limiter = RateLimiter(default_limit=10, window_seconds=60)

        # Make 5 requests (within limit)
        for i in range(5):
            allowed, count = limiter.check_rate_limit("user1")
            assert allowed is True

    def test_rate_limit_blocks_over_limit(self):
        """Test rate limiter blocks requests over limit"""
        limiter = RateLimiter(default_limit=5, window_seconds=60)

        # Make 5 requests (at limit)
        for i in range(5):
            allowed, count = limiter.check_rate_limit("user1")
            assert allowed is True

        # 6th request should be blocked
        allowed, count = limiter.check_rate_limit("user1")
        assert allowed is False

    def test_custom_limit(self):
        """Test custom rate limit"""
        limiter = RateLimiter(default_limit=10, window_seconds=60)

        # Set custom limit
        limiter.set_custom_limit("user1", 20)

        # Should allow up to 20 requests
        for i in range(20):
            allowed, count = limiter.check_rate_limit("user1")
            assert allowed is True

    def test_detect_burst(self):
        """Test burst detection"""
        limiter = RateLimiter(default_limit=100, window_seconds=60)

        # Make many requests quickly
        for i in range(50):
            limiter.check_rate_limit("user1")

        # Should detect burst
        is_burst = limiter.detect_burst("user1")
        assert is_burst is True


class TestThreatIntelligence:
    """Test threat intelligence"""

    def test_add_indicator(self):
        """Test adding threat indicator"""
        ti = ThreatIntelligence()

        indicator = ThreatIndicator(
            indicator_type="ip",
            value="10.0.0.1",
            threat_level=ThreatLevel.HIGH,
            description="Known malicious IP",
            source="threat_feed",
            added_at=datetime.now(timezone.utc)
        )

        ti.add_indicator(indicator)

        assert len(ti.indicators["ip"]) == 1
        assert "10.0.0.1" in ti.blocked_ips

    def test_check_threat(self):
        """Test checking for known threat"""
        ti = ThreatIntelligence()

        indicator = ThreatIndicator(
            indicator_type="ip",
            value="10.0.0.1",
            threat_level=ThreatLevel.HIGH,
            description="Known malicious IP",
            source="threat_feed",
            added_at=datetime.now(timezone.utc)
        )

        ti.add_indicator(indicator)

        # Check for threat
        threat = ti.check_threat("ip", "10.0.0.1")
        assert threat is not None
        assert threat.value == "10.0.0.1"

    def test_is_blocked_ip(self):
        """Test checking if IP is blocked"""
        ti = ThreatIntelligence()

        indicator = ThreatIndicator(
            indicator_type="ip",
            value="10.0.0.1",
            threat_level=ThreatLevel.HIGH,
            description="Known malicious IP",
            source="threat_feed",
            added_at=datetime.now(timezone.utc)
        )

        ti.add_indicator(indicator)

        assert ti.is_blocked_ip("10.0.0.1") is True
        assert ti.is_blocked_ip("192.168.1.1") is False

    def test_cleanup_expired(self):
        """Test cleaning up expired indicators"""
        ti = ThreatIntelligence()

        # Add expired indicator
        indicator = ThreatIndicator(
            indicator_type="ip",
            value="10.0.0.1",
            threat_level=ThreatLevel.HIGH,
            description="Expired threat",
            source="threat_feed",
            added_at=datetime.now(timezone.utc) - timedelta(days=2),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )

        ti.add_indicator(indicator)

        # Cleanup
        ti.cleanup_expired()

        assert len(ti.indicators["ip"]) == 0
        assert "10.0.0.1" not in ti.blocked_ips


class TestAttackPatternRecognizer:
    """Test attack pattern recognition"""

    def test_recognize_brute_force(self):
        """Test recognizing brute force attack"""
        recognizer = AttackPatternRecognizer()

        # Add multiple failed login attempts
        for i in range(10):
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc) - timedelta(seconds=i),
                principal_id="user1",
                event_type="login",
                source_ip="10.0.0.1",
                success=False
            )
            recognizer.add_event(event)

        # Should recognize brute force
        result = recognizer.recognize_attack("user1")
        assert result is not None
        attack_type, confidence = result
        assert attack_type == AttackType.BRUTE_FORCE
        assert confidence > 0.8

    def test_recognize_reconnaissance(self):
        """Test recognizing reconnaissance"""
        recognizer = AttackPatternRecognizer()

        # Add requests to many different resources
        for i in range(25):
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc) - timedelta(seconds=i),
                principal_id="user1",
                event_type="access",
                source_ip="10.0.0.1",
                resource=f"/api/resource{i}",
                success=True
            )
            recognizer.add_event(event)

        # Should recognize reconnaissance
        result = recognizer.recognize_attack("user1")
        assert result is not None
        attack_type, confidence = result
        assert attack_type == AttackType.RECONNAISSANCE


class TestAutomatedResponseSystem:
    """Test automated response system"""

    def test_determine_response_low_threat(self):
        """Test response for low threat"""
        system = AutomatedResponseSystem()

        anomaly = Anomaly(
            anomaly_type=AnomalyType.BEHAVIORAL,
            threat_level=ThreatLevel.LOW,
            principal_id="user1",
            description="Minor anomaly",
            detected_at=datetime.now(timezone.utc),
            confidence=0.5
        )

        actions = system.determine_response(anomaly)

        assert ResponseAction.LOG in actions
        assert ResponseAction.ALERT in actions

    def test_determine_response_high_threat(self):
        """Test response for high threat"""
        system = AutomatedResponseSystem()

        anomaly = Anomaly(
            anomaly_type=AnomalyType.BEHAVIORAL,
            threat_level=ThreatLevel.HIGH,
            principal_id="user1",
            description="Serious anomaly",
            detected_at=datetime.now(timezone.utc),
            confidence=0.9
        )

        actions = system.determine_response(anomaly)

        assert ResponseAction.LOG in actions
        assert ResponseAction.ALERT in actions
        assert ResponseAction.TEMPORARY_BLOCK in actions

    def test_determine_response_critical_threat(self):
        """Test response for critical threat"""
        system = AutomatedResponseSystem()

        anomaly = Anomaly(
            anomaly_type=AnomalyType.BEHAVIORAL,
            threat_level=ThreatLevel.CRITICAL,
            principal_id="user1",
            description="Critical threat",
            detected_at=datetime.now(timezone.utc),
            confidence=1.0
        )

        actions = system.determine_response(anomaly)

        assert ResponseAction.PERMANENT_BLOCK in actions
        assert ResponseAction.FREEZE_PRINCIPAL in actions
        assert ResponseAction.ESCALATE_TO_HUMAN in actions

    def test_execute_response(self):
        """Test executing response"""
        system = AutomatedResponseSystem()

        response = system.execute_response(
            action=ResponseAction.TEMPORARY_BLOCK,
            target="user1",
            reason="Suspicious activity",
            threat_level=ThreatLevel.HIGH,
            duration=timedelta(hours=1)
        )

        assert response.action == ResponseAction.TEMPORARY_BLOCK
        assert response.target == "user1"
        assert not response.is_expired()

    def test_is_blocked(self):
        """Test checking if target is blocked"""
        system = AutomatedResponseSystem()

        system.execute_response(
            action=ResponseAction.TEMPORARY_BLOCK,
            target="user1",
            reason="Test",
            threat_level=ThreatLevel.HIGH,
            duration=timedelta(hours=1)
        )

        assert system.is_blocked("user1") is True
        assert system.is_blocked("user2") is False


class TestIntegration:
    """Test integrated adaptive defense scenarios"""

    def test_full_defense_workflow(self):
        """Test complete defense workflow"""
        # Initialize components
        behavioral = BehavioralAnomalyDetector()
        ti = ThreatIntelligence()
        response_system = AutomatedResponseSystem()

        # Add threat indicator
        indicator = ThreatIndicator(
            indicator_type="ip",
            value="10.0.0.1",
            threat_level=ThreatLevel.HIGH,
            description="Known attacker",
            source="threat_feed",
            added_at=datetime.now(timezone.utc)
        )
        ti.add_indicator(indicator)

        # Create event from known threat
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            principal_id="user1",
            event_type="login",
            source_ip="10.0.0.1",
            success=False
        )

        # Check threat intelligence
        threat = ti.check_threat("ip", event.source_ip)
        assert threat is not None

        # Execute response
        response = response_system.execute_response(
            action=ResponseAction.PERMANENT_BLOCK,
            target=event.source_ip,
            reason=f"Known threat: {threat.description}",
            threat_level=threat.threat_level
        )

        assert response_system.is_blocked(event.source_ip)

    def test_rate_limiting_with_anomaly_detection(self):
        """Test rate limiting combined with anomaly detection"""
        limiter = RateLimiter(default_limit=10, window_seconds=60)
        response_system = AutomatedResponseSystem()

        # Simulate rapid requests
        for i in range(15):
            allowed, count = limiter.check_rate_limit("user1")

            if not allowed:
                # Rate limit exceeded - execute response
                response = response_system.execute_response(
                    action=ResponseAction.RATE_LIMIT,
                    target="user1",
                    reason="Rate limit exceeded",
                    threat_level=ThreatLevel.MEDIUM,
                    duration=timedelta(minutes=5)
                )
                break

        # Verify response was executed
        assert len(response_system.active_responses["user1"]) > 0


class TestAdaptiveDefenseStatistics:
    """Test adaptive defense statistics"""

    def test_statistics_creation(self):
        """Test creating statistics"""
        stats = AdaptiveDefenseStatistics(
            total_events=1000,
            anomalies_detected=50,
            attacks_recognized=5
        )

        assert stats.total_events == 1000
        assert stats.anomalies_detected == 50

    def test_statistics_to_dict(self):
        """Test converting statistics to dict"""
        stats = AdaptiveDefenseStatistics(total_events=100)
        result = stats.to_dict()

        assert isinstance(result, dict)
        assert result["total_events"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
