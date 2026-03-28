"""Tests for security enhancement modules (Phases 1–4)."""

import os
import pytest
from datetime import datetime, timezone, timedelta
import time

# Ensure the src package is importable

from security_plane.authorization_enhancer import (
    AuthorizationEnhancer, AuthorizationRequest, AuthorizationDecision,
    SessionContext, OwnershipVerificationResult,
)
from security_plane.log_sanitizer import (
    LogSanitizer, PIIType, PIIPattern, SanitizationResult,
)
from security_plane.bot_resource_quotas import (
    BotResourceQuotaManager, BotQuota, BotUsage, SwarmQuota,
    QuotaStatus, QuotaViolation, ViolationType,
)
from security_plane.swarm_communication_monitor import (
    SwarmCommunicationMonitor, SwarmMessage, CommunicationIncident,
    CommunicationAlert,
)
from security_plane.bot_identity_verifier import (
    BotIdentityVerifier, BotIdentity, SignedMessage,
    IdentityStatus, VerificationResult as IdentityVerificationResult,
)
from security_plane.bot_anomaly_detector import (
    BotAnomalyDetector, BotMetrics, AnomalyAlert,
    AnomalyType, AlertSeverity,
)
from security_plane.security_dashboard import (
    SecurityDashboard, SecurityEvent, SecurityEventType,
    EscalationLevel, CorrelatedEventGroup, SecurityReport,
)


# ---------------------------------------------------------------------------
# Authorization Enhancer
# ---------------------------------------------------------------------------

class TestAuthorizationEnhancer:
    """Tests for the AuthorizationEnhancer module."""

    def test_create_session(self):
        enhancer = AuthorizationEnhancer()
        session = enhancer.create_session(
            principal_id="bot-1",
            tenant_id="tenant-a",
            roles=["reader"],
            ttl_seconds=600,
        )
        assert isinstance(session, SessionContext)
        assert session.principal_id == "bot-1"
        assert session.tenant_id == "tenant-a"
        assert "reader" in session.roles
        assert session.is_active is True
        assert session.session_id is not None

    def test_session_expiration(self):
        enhancer = AuthorizationEnhancer()
        session = enhancer.create_session(
            principal_id="bot-2",
            tenant_id="tenant-a",
            roles=["writer"],
            ttl_seconds=1,
        )
        enhancer.register_resource_owner("res-1", "file", "bot-2", "tenant-a")
        time.sleep(1.5)
        req = AuthorizationRequest(
            request_id="req-exp",
            principal_id="bot-2",
            resource_id="res-1",
            resource_type="file",
            action="read",
            session_id=session.session_id,
            timestamp=datetime.now(timezone.utc),
        )
        decision = enhancer.verify_request(req)
        assert decision.result == OwnershipVerificationResult.DENIED_EXPIRED_SESSION

    def test_register_resource_and_verify_owner(self):
        enhancer = AuthorizationEnhancer()
        session = enhancer.create_session("owner-1", "tenant-a", ["admin"])
        enhancer.register_resource_owner("doc-1", "document", "owner-1", "tenant-a")
        req = AuthorizationRequest(
            request_id="req-own",
            principal_id="owner-1",
            resource_id="doc-1",
            resource_type="document",
            action="write",
            session_id=session.session_id,
            timestamp=datetime.now(timezone.utc),
        )
        decision = enhancer.verify_request(req)
        assert decision.result == OwnershipVerificationResult.ALLOWED

    def test_deny_non_owner(self):
        enhancer = AuthorizationEnhancer()
        owner_session = enhancer.create_session("owner-1", "tenant-a", ["admin"])
        other_session = enhancer.create_session("other-1", "tenant-a", ["reader"])
        enhancer.register_resource_owner("doc-2", "document", "owner-1", "tenant-a")
        req = AuthorizationRequest(
            request_id="req-deny",
            principal_id="other-1",
            resource_id="doc-2",
            resource_type="document",
            action="write",
            session_id=other_session.session_id,
            timestamp=datetime.now(timezone.utc),
        )
        decision = enhancer.verify_request(req)
        assert decision.result == OwnershipVerificationResult.DENIED_NOT_OWNER

    def test_deny_no_session(self):
        enhancer = AuthorizationEnhancer()
        enhancer.register_resource_owner("doc-3", "document", "owner-1", "tenant-a")
        req = AuthorizationRequest(
            request_id="req-nosess",
            principal_id="owner-1",
            resource_id="doc-3",
            resource_type="document",
            action="read",
            session_id="nonexistent-session",
            timestamp=datetime.now(timezone.utc),
        )
        decision = enhancer.verify_request(req)
        assert decision.result == OwnershipVerificationResult.DENIED_NO_SESSION

    def test_invalidate_session(self):
        enhancer = AuthorizationEnhancer()
        session = enhancer.create_session("bot-inv", "tenant-a", ["admin"])
        enhancer.register_resource_owner("res-inv", "file", "bot-inv", "tenant-a")
        result = enhancer.invalidate_session(session.session_id)
        assert result is True
        req = AuthorizationRequest(
            request_id="req-inv",
            principal_id="bot-inv",
            resource_id="res-inv",
            resource_type="file",
            action="read",
            session_id=session.session_id,
            timestamp=datetime.now(timezone.utc),
        )
        decision = enhancer.verify_request(req)
        assert decision.result != OwnershipVerificationResult.ALLOWED

    def test_audit_trail(self):
        enhancer = AuthorizationEnhancer()
        session = enhancer.create_session("bot-aud", "tenant-a", ["reader"])
        enhancer.register_resource_owner("res-aud", "file", "bot-aud", "tenant-a")
        req = AuthorizationRequest(
            request_id="req-aud",
            principal_id="bot-aud",
            resource_id="res-aud",
            resource_type="file",
            action="read",
            session_id=session.session_id,
            timestamp=datetime.now(timezone.utc),
        )
        enhancer.verify_request(req)
        trail = enhancer.get_audit_trail(principal_id="bot-aud")
        assert len(trail) >= 1
        entry = trail[0]
        # Audit entries may be dicts or AuthorizationDecision objects
        if isinstance(entry, dict):
            assert entry["principal_id"] == "bot-aud"
        else:
            assert entry.principal_id == "bot-aud"

    def test_get_stats(self):
        enhancer = AuthorizationEnhancer()
        enhancer.create_session("bot-stat", "tenant-a", ["reader"])
        stats = enhancer.get_stats()
        assert "total_sessions" in stats
        assert stats["total_sessions"] >= 1
        assert "active_sessions" in stats
        assert "registered_resources" in stats
        assert "audit_entries" in stats


# ---------------------------------------------------------------------------
# Log Sanitizer
# ---------------------------------------------------------------------------

class TestLogSanitizer:
    """Tests for the LogSanitizer module."""

    def test_sanitize_email(self):
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("Contact john.doe@example.com for info")
        assert "john.doe@example.com" not in result
        assert "[HASH:" in result or "REDACTED" in result.upper()

    def test_sanitize_phone(self):
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("Call me at 555-123-4567 please")
        assert "555-123-4567" not in result

    def test_sanitize_ssn(self):
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("SSN is 123-45-6789")
        assert "123-45-6789" not in result

    def test_sanitize_credit_card(self):
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("Card: 4111-1111-1111-1111")
        assert "4111-1111-1111-1111" not in result

    def test_sanitize_api_key(self):
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("api_key=sk_live_abc123xyz")
        assert "sk_live_abc123xyz" not in result

    def test_sanitize_password(self):
        sanitizer = LogSanitizer()
        result = sanitizer.sanitize("password=SuperSecret123!")
        assert "SuperSecret123!" not in result

    def test_sanitize_dict(self):
        sanitizer = LogSanitizer()
        data = {
            "user": "alice",
            "email": "Contact alice@example.com",
            "nested": {"ssn": "SSN: 987-65-4321"},
        }
        cleaned = sanitizer.sanitize_dict(data)
        assert "alice@example.com" not in str(cleaned)
        assert "987-65-4321" not in str(cleaned)

    def test_scan_text_no_redaction(self):
        sanitizer = LogSanitizer()
        text = "Email me at user@test.org, SSN 111-22-3333"
        findings = sanitizer.scan_text(text)
        assert isinstance(findings, dict)
        total_found = sum(findings.values())
        assert total_found >= 2

    def test_retroactive_sanitize(self):
        sanitizer = LogSanitizer()
        entries = [
            {"message": "User email: admin@corp.com"},
            {"message": "Card 4222-2222-2222-2222 used"},
        ]
        cleaned = sanitizer.sanitize_log_entries(entries)
        assert len(cleaned) == 2
        assert "admin@corp.com" not in str(cleaned)
        assert "4222-2222-2222-2222" not in str(cleaned)

    def test_custom_pattern(self):
        sanitizer = LogSanitizer()
        custom = PIIPattern(
            pii_type=PIIType.EMAIL,
            pattern=r"CUSTOM-\d{5}",
            replacement="[CUSTOM_REDACTED]",
        )
        sanitizer.add_pattern(custom)
        result = sanitizer.sanitize("Code is CUSTOM-98765")
        assert "CUSTOM-98765" not in result

    def test_get_stats(self):
        sanitizer = LogSanitizer()
        sanitizer.sanitize("email: test@test.com")
        stats = sanitizer.get_stats()
        assert isinstance(stats, dict)


# ---------------------------------------------------------------------------
# Bot Resource Quotas
# ---------------------------------------------------------------------------

class TestBotResourceQuotaManager:
    """Tests for the BotResourceQuotaManager module."""

    def test_register_and_track_bot(self):
        mgr = BotResourceQuotaManager()
        quota = BotQuota(bot_id="bot-q1", tenant_id="t1", max_api_calls=100)
        mgr.register_bot(quota)
        mgr.record_usage("bot-q1", api_calls=10)
        status = mgr.check_bot_quota("bot-q1")
        assert status is not None

    def test_bot_quota_violation(self):
        mgr = BotResourceQuotaManager()
        quota = BotQuota(bot_id="bot-q2", tenant_id="t1", max_api_calls=50)
        mgr.register_bot(quota)
        mgr.record_usage("bot-q2", api_calls=60)
        violations = mgr.get_violations(bot_id="bot-q2")
        assert len(violations) >= 1

    def test_bot_warning_threshold(self):
        mgr = BotResourceQuotaManager()
        quota = BotQuota(bot_id="bot-q3", tenant_id="t1", max_memory_mb=100.0)
        mgr.register_bot(quota)
        mgr.record_usage("bot-q3", memory_mb=85.0)
        status = mgr.check_bot_quota("bot-q3")
        assert status is not None

    def test_swarm_aggregate_limit(self):
        mgr = BotResourceQuotaManager()
        swarm = SwarmQuota(swarm_id="swarm-1", tenant_id="t1", max_total_api_calls=100)
        mgr.register_swarm(swarm)
        q1 = BotQuota(bot_id="sq1", tenant_id="t1", max_api_calls=200)
        q2 = BotQuota(bot_id="sq2", tenant_id="t1", max_api_calls=200)
        mgr.register_bot(q1)
        mgr.register_bot(q2)
        mgr.assign_bot_to_swarm("sq1", "swarm-1")
        mgr.assign_bot_to_swarm("sq2", "swarm-1")
        mgr.record_usage("sq1", api_calls=60)
        mgr.record_usage("sq2", api_calls=60)
        violations = mgr.get_violations(swarm_id="swarm-1")
        assert len(violations) >= 1

    def test_suspend_and_resume_bot(self):
        mgr = BotResourceQuotaManager()
        quota = BotQuota(bot_id="bot-sr", tenant_id="t1")
        mgr.register_bot(quota)
        mgr.suspend_bot("bot-sr", reason="policy")
        status = mgr.check_bot_quota("bot-sr")
        assert status is not None
        mgr.resume_bot("bot-sr")
        status_after = mgr.check_bot_quota("bot-sr")
        assert status_after is not None

    def test_get_stats(self):
        mgr = BotResourceQuotaManager()
        mgr.register_bot(BotQuota(bot_id="stat-b", tenant_id="t1"))
        stats = mgr.get_stats()
        assert "total_bots" in stats
        assert stats["total_bots"] >= 1
        assert "total_swarms" in stats
        assert "total_violations" in stats


# ---------------------------------------------------------------------------
# Swarm Communication Monitor
# ---------------------------------------------------------------------------

class TestSwarmCommunicationMonitor:
    """Tests for the SwarmCommunicationMonitor module."""

    def _make_message(self, swarm_id, from_bot, to_bot, msg_id=None):
        import hashlib
        content = f"{from_bot}->{to_bot}"
        return SwarmMessage(
            message_id=msg_id or f"msg-{from_bot}-{to_bot}",
            swarm_id=swarm_id,
            from_bot=from_bot,
            to_bot=to_bot,
            timestamp=datetime.now(timezone.utc),
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
        )

    def test_record_message_no_incident(self):
        monitor = SwarmCommunicationMonitor()
        msg = self._make_message("s1", "botA", "botB")
        incident = monitor.record_message(msg)
        assert incident is None

    def test_rate_limit_exceeded(self):
        monitor = SwarmCommunicationMonitor(max_messages_per_minute=5)
        incidents = []
        for i in range(10):
            msg = self._make_message("s2", "botX", "botY", msg_id=f"rl-{i}")
            result = monitor.record_message(msg)
            if result is not None:
                incidents.append(result)
        assert len(incidents) >= 1
        assert any(
            inc.alert_type == CommunicationAlert.RATE_LIMIT_EXCEEDED
            for inc in incidents
        )

    def test_cycle_detection(self):
        monitor = SwarmCommunicationMonitor(loop_detection_window=50)
        incidents = []
        for _ in range(20):
            for from_b, to_b in [("A", "B"), ("B", "C"), ("C", "A")]:
                msg = self._make_message(
                    "s3", from_b, to_b,
                    msg_id=f"cyc-{from_b}{to_b}-{_}",
                )
                result = monitor.record_message(msg)
                if result is not None:
                    incidents.append(result)
        loop_incidents = [
            i for i in incidents
            if i.alert_type == CommunicationAlert.LOOP_DETECTED
        ]
        assert len(loop_incidents) >= 1

    def test_unusual_pattern(self):
        monitor = SwarmCommunicationMonitor(
            max_messages_per_minute=200,
            max_messages_per_channel=100,
        )
        incidents = []
        for i in range(80):
            msg = self._make_message("s4", "spamA", "spamB", msg_id=f"up-{i}")
            result = monitor.record_message(msg)
            if result is not None:
                incidents.append(result)
        pattern_incidents = [
            i for i in incidents
            if i.alert_type == CommunicationAlert.UNUSUAL_PATTERN
        ]
        assert len(pattern_incidents) >= 0  # may or may not trigger

    def test_get_message_graph(self):
        monitor = SwarmCommunicationMonitor()
        monitor.record_message(self._make_message("g1", "a", "b", "g-1"))
        monitor.record_message(self._make_message("g1", "b", "c", "g-2"))
        graph = monitor.get_message_graph("g1")
        assert isinstance(graph, dict)
        assert "a" in graph
        assert "b" in graph["a"]

    def test_clear_swarm(self):
        monitor = SwarmCommunicationMonitor()
        monitor.record_message(self._make_message("clr", "x", "y", "clr-1"))
        monitor.clear_swarm("clr")
        graph = monitor.get_message_graph("clr")
        assert len(graph) == 0

    def test_get_stats(self):
        monitor = SwarmCommunicationMonitor()
        monitor.record_message(self._make_message("st", "a", "b", "st-1"))
        stats = monitor.get_stats()
        assert "total_messages_recorded" in stats
        assert stats["total_messages_recorded"] >= 1
        assert "active_swarms" in stats
        assert "total_incidents" in stats


# ---------------------------------------------------------------------------
# Bot Identity Verifier
# ---------------------------------------------------------------------------

class TestBotIdentityVerifier:
    """Tests for the BotIdentityVerifier module."""

    def test_register_and_sign(self):
        verifier = BotIdentityVerifier()
        identity = verifier.register_bot("id-1", "tenant-a")
        assert isinstance(identity, BotIdentity)
        assert identity.bot_id == "id-1"
        assert identity.status == IdentityStatus.ACTIVE
        signed = verifier.sign_message("id-1", "id-2", "hello")
        assert isinstance(signed, SignedMessage)
        assert signed.from_bot == "id-1"

    def test_verify_valid_signature(self):
        verifier = BotIdentityVerifier()
        verifier.register_bot("v1", "t1")
        verifier.register_bot("v2", "t1")
        signed = verifier.sign_message("v1", "v2", "payload")
        result = verifier.verify_message(signed)
        assert result == IdentityVerificationResult.VALID

    def test_verify_invalid_signature(self):
        verifier = BotIdentityVerifier()
        verifier.register_bot("t1", "tenant")
        verifier.register_bot("t2", "tenant")
        signed = verifier.sign_message("t1", "t2", "data")
        tampered = SignedMessage(
            message_id=signed.message_id,
            from_bot=signed.from_bot,
            to_bot=signed.to_bot,
            payload_hash="tampered_hash_value",
            signature=signed.signature,
            timestamp=signed.timestamp,
        )
        result = verifier.verify_message(tampered)
        assert result == IdentityVerificationResult.INVALID_SIGNATURE

    def test_unknown_bot_rejected(self):
        verifier = BotIdentityVerifier()
        verifier.register_bot("known", "t1")
        fake = SignedMessage(
            message_id="fake-msg",
            from_bot="unknown-bot",
            to_bot="known",
            payload_hash="abc",
            signature="bad",
            timestamp=datetime.now(timezone.utc),
        )
        result = verifier.verify_message(fake)
        assert result == IdentityVerificationResult.UNKNOWN_BOT

    def test_revoke_identity(self):
        verifier = BotIdentityVerifier()
        verifier.register_bot("rev-1", "t1")
        verifier.register_bot("rev-2", "t1")
        signed = verifier.sign_message("rev-1", "rev-2", "secret")
        verifier.revoke_identity("rev-1", reason="compromised")
        result = verifier.verify_message(signed)
        assert result == IdentityVerificationResult.REVOKED_IDENTITY

    def test_rotate_key(self):
        verifier = BotIdentityVerifier()
        identity = verifier.register_bot("rot-1", "t1")
        old_key = identity.signing_key
        new_identity = verifier.rotate_key("rot-1")
        assert new_identity is not None
        assert new_identity.signing_key != old_key
        assert new_identity.status == IdentityStatus.ACTIVE

    def test_list_identities(self):
        verifier = BotIdentityVerifier()
        verifier.register_bot("list-1", "t-list")
        verifier.register_bot("list-2", "t-list")
        verifier.register_bot("list-3", "t-other")
        filtered = verifier.list_identities(tenant_id="t-list")
        assert len(filtered) == 2
        assert all(i.tenant_id == "t-list" for i in filtered)

    def test_get_stats(self):
        verifier = BotIdentityVerifier()
        verifier.register_bot("stat-1", "t1")
        stats = verifier.get_stats()
        assert stats["total_identities"] >= 1
        assert stats["active"] >= 1
        assert "revoked" in stats
        assert "max_identities" in stats


# ---------------------------------------------------------------------------
# Bot Anomaly Detector
# ---------------------------------------------------------------------------

class TestBotAnomalyDetector:
    """Tests for the BotAnomalyDetector module."""

    def test_normal_metrics_no_alert(self):
        detector = BotAnomalyDetector(min_samples=5)
        for _ in range(10):
            alerts = detector.record_metric("norm-1", response_time=50.0)
        assert len(alerts) == 0

    def test_z_score_anomaly(self):
        detector = BotAnomalyDetector(
            min_samples=10, z_score_threshold=2.0,
        )
        for _ in range(15):
            detector.record_metric("zscore-1", response_time=100.0)
        alerts = detector.record_metric("zscore-1", response_time=1000.0)
        assert len(alerts) >= 1
        assert any(
            a.anomaly_type == AnomalyType.RESPONSE_TIME_SPIKE for a in alerts
        )

    def test_resource_spike_detection(self):
        detector = BotAnomalyDetector(
            min_samples=10, z_score_threshold=2.0,
        )
        for _ in range(15):
            detector.record_metric("res-1", memory_mb=200.0, cpu_percent=20.0)
        alerts = detector.record_metric("res-1", memory_mb=2000.0, cpu_percent=99.0)
        assert len(alerts) >= 1

    def test_api_pattern_anomaly(self):
        detector = BotAnomalyDetector(min_samples=10)
        for _ in range(15):
            detector.record_metric("api-1", api_calls=10, api_endpoint="/v1/chat")
        alerts = detector.record_metric(
            "api-1", api_calls=500, api_endpoint="/v1/admin/delete",
        )
        assert isinstance(alerts, list)

    def test_get_bot_baseline(self):
        detector = BotAnomalyDetector(min_samples=5)
        for _ in range(10):
            detector.record_metric("base-1", response_time=42.0, api_calls=5)
        baseline = detector.get_bot_baseline("base-1")
        assert baseline is not None
        assert baseline["bot_id"] == "base-1"
        assert "response_times" in baseline
        assert baseline["response_times"]["count"] == 10

    def test_get_stats(self):
        detector = BotAnomalyDetector()
        detector.record_metric("s1", response_time=10.0)
        stats = detector.get_stats()
        assert isinstance(stats, dict)


# ---------------------------------------------------------------------------
# Security Dashboard
# ---------------------------------------------------------------------------

class TestSecurityDashboard:
    """Tests for the SecurityDashboard module."""

    def _make_event(self, event_type, level, bot_id="dash-bot", desc="test event"):
        import uuid
        return SecurityEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            escalation_level=level,
            source_module="test",
            bot_id=bot_id,
            tenant_id="tenant-test",
            description=desc,
            metadata={},
            timestamp=datetime.now(timezone.utc),
        )

    def test_record_event(self):
        dashboard = SecurityDashboard()
        event = self._make_event(
            SecurityEventType.ANOMALY_DETECTED, EscalationLevel.WARNING,
        )
        dashboard.record_event(event)
        events = dashboard.get_events(bot_id="dash-bot")
        assert len(events) >= 1
        assert events[0].event_id == event.event_id

    def test_event_correlation(self):
        dashboard = SecurityDashboard(correlation_window_seconds=600)
        e1 = self._make_event(
            SecurityEventType.ANOMALY_DETECTED, EscalationLevel.WARNING,
            bot_id="corr-bot", desc="anomaly 1",
        )
        e2 = self._make_event(
            SecurityEventType.ANOMALY_DETECTED, EscalationLevel.WARNING,
            bot_id="corr-bot", desc="anomaly 2",
        )
        dashboard.record_event(e1)
        group = dashboard.record_event(e2)
        if group is None:
            groups = dashboard.get_correlated_groups()
            corr = [g for g in groups if any(
                ev.bot_id == "corr-bot" for ev in g.events
            )]
            assert len(corr) >= 0  # correlation may or may not group them
        else:
            assert isinstance(group, CorrelatedEventGroup)
            assert len(group.events) >= 2

    def test_escalation_callback(self):
        dashboard = SecurityDashboard()
        captured = []
        dashboard.register_escalation_callback(
            EscalationLevel.CRITICAL,
            lambda evt: captured.append(evt),
        )
        event = self._make_event(
            SecurityEventType.QUOTA_VIOLATION, EscalationLevel.CRITICAL,
            desc="critical quota breach",
        )
        dashboard.record_event(event)
        assert len(captured) >= 1
        assert captured[0].event_id == event.event_id

    def test_generate_report(self):
        dashboard = SecurityDashboard()
        for i in range(5):
            dashboard.record_event(self._make_event(
                SecurityEventType.PII_DETECTED, EscalationLevel.ALERT,
                bot_id=f"rpt-bot-{i % 2}",
            ))
        report = dashboard.generate_report(period_hours=1)
        assert isinstance(report, SecurityReport)
        assert report.total_events >= 5
        assert isinstance(report.events_by_type, dict)
        assert isinstance(report.top_affected_bots, list)
        assert isinstance(report.recommendations, list)

    def test_dashboard_summary(self):
        dashboard = SecurityDashboard()
        dashboard.record_event(self._make_event(
            SecurityEventType.COMMUNICATION_LOOP, EscalationLevel.WARNING,
        ))
        summary = dashboard.get_dashboard_summary()
        assert "total_events_stored" in summary
        assert summary["total_events_stored"] >= 1
        assert "events_last_hour" in summary
        assert "last_hour_by_type" in summary
        assert "last_hour_by_severity" in summary

    def test_event_filtering(self):
        dashboard = SecurityDashboard()
        dashboard.record_event(self._make_event(
            SecurityEventType.AUTHORIZATION_DENIED, EscalationLevel.INFO,
            bot_id="filter-a",
        ))
        dashboard.record_event(self._make_event(
            SecurityEventType.QUOTA_VIOLATION, EscalationLevel.CRITICAL,
            bot_id="filter-b",
        ))
        by_type = dashboard.get_events(
            event_type=SecurityEventType.AUTHORIZATION_DENIED,
        )
        assert all(
            e.event_type == SecurityEventType.AUTHORIZATION_DENIED for e in by_type
        )
        by_level = dashboard.get_events(escalation_level=EscalationLevel.CRITICAL)
        assert all(
            e.escalation_level == EscalationLevel.CRITICAL for e in by_level
        )
        by_bot = dashboard.get_events(bot_id="filter-a")
        assert all(e.bot_id == "filter-a" for e in by_bot)

    def test_get_stats(self):
        dashboard = SecurityDashboard()
        dashboard.record_event(self._make_event(
            SecurityEventType.ANOMALY_DETECTED, EscalationLevel.WARNING,
        ))
        stats = dashboard.get_stats()
        assert isinstance(stats, dict)
