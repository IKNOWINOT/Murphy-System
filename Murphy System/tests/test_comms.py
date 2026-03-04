"""
Comprehensive tests for Communication Connectors & Governance Layer

Tests:
1. Schema validation and safety constraints
2. Connector functionality
3. Message pipeline
4. Governance enforcement
5. Compliance validation
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.comms.schemas import (
    MessageArtifact,
    CommunicationPacket,
    IntentClassification,
    Channel,
    RedactionRule,
    RetentionPolicy,
    AuditLogEntry,
    ConnectorConfig,
)
from src.comms.connectors import (
    BaseConnector,
    EmailConnector,
    SlackConnector,
)
from src.comms.pipeline import (
    MessageIngestor,
    IntentClassifier,
    RedactionPipeline,
    MessageStorage,
    ThreadManager,
    MessagePipeline,
)
from src.comms.governance import (
    CommunicationAuthorizer,
    OutboundValidator,
    ApprovalBlocker,
    HumanSignoffEnforcer,
    AuditLogger,
    GovernanceLayer,
)
from src.comms.compliance import (
    RedactionEngine,
    RetentionPolicyManager,
    AuditTrailManager,
    ComplianceValidator,
)


# ============================================================================
# SCHEMA TESTS
# ============================================================================

class TestSchemas:
    """Test schema validation and safety constraints"""

    def test_message_cannot_trigger_execution(self):
        """Test that messages cannot trigger execution"""
        with pytest.raises(ValueError, match="triggers_execution MUST be False"):
            MessageArtifact(
                message_id="test",
                channel=Channel.EMAIL,
                thread_id="thread1",
                sender_hash="sender_hash",
                recipient_hash="recipient_hash",
                content_redacted="test content",
                intent=IntentClassification.QUESTION,
                timestamp=datetime.now(timezone.utc),
                direction="inbound",
                external_party=False,
                source_system="test",
                triggers_execution=True  # Should fail
            )

    def test_packet_cannot_contain_approval(self):
        """Test that packets cannot contain executable approvals"""
        with pytest.raises(ValueError, match="cannot contain executable approvals"):
            CommunicationPacket(
                packet_id="test",
                channel=Channel.EMAIL,
                thread_id="thread1",
                recipient_hashes=["hash1"],
                content="test",
                authorized_by="auth1",
                authority_level="high",
                gates_satisfied=["gate1"],
                external_party=False,
                contains_approval=True  # Should fail
            )

    def test_packet_cannot_contain_payment(self):
        """Test that packets cannot contain executable payments"""
        with pytest.raises(ValueError, match="cannot contain executable payments"):
            CommunicationPacket(
                packet_id="test",
                channel=Channel.EMAIL,
                thread_id="thread1",
                recipient_hashes=["hash1"],
                content="test",
                authorized_by="auth1",
                authority_level="high",
                gates_satisfied=["gate1"],
                external_party=False,
                contains_payment=True  # Should fail
            )

    def test_packet_cannot_contain_contract(self):
        """Test that packets cannot contain executable contracts"""
        with pytest.raises(ValueError, match="cannot contain executable contracts"):
            CommunicationPacket(
                packet_id="test",
                channel=Channel.EMAIL,
                thread_id="thread1",
                recipient_hashes=["hash1"],
                content="test",
                authorized_by="auth1",
                authority_level="high",
                gates_satisfied=["gate1"],
                external_party=False,
                contains_contract=True  # Should fail
            )

    def test_audit_log_immutability(self):
        """Test that audit logs are immutable"""
        with pytest.raises(ValueError, match="immutable MUST be True"):
            AuditLogEntry(
                log_id="test",
                event_type="message_received",
                timestamp=datetime.now(timezone.utc),
                actor="system",
                immutable=False  # Should fail
            )

    def test_message_integrity_hash(self):
        """Test message integrity hash"""
        message = MessageArtifact(
            message_id="test",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="test",
            intent=IntentClassification.QUESTION,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        assert message.integrity_hash is not None
        assert message.verify_integrity()


# ============================================================================
# CONNECTOR TESTS
# ============================================================================

class TestConnectors:
    """Test connector functionality"""

    def test_email_connector_initialization(self):
        """Test email connector initialization"""
        config = ConnectorConfig(
            connector_id="email1",
            channel=Channel.EMAIL,
            connection_params={
                'smtp_host': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'test@example.com',
                'smtp_password': 'password'
            }
        )

        connector = EmailConnector(config)
        assert connector.channel == Channel.EMAIL
        assert connector.smtp_host == 'smtp.example.com'

    def test_slack_connector_initialization(self):
        """Test Slack connector initialization"""
        config = ConnectorConfig(
            connector_id="slack1",
            channel=Channel.SLACK,
            connection_params={
                'bot_token': 'xoxb-test',
                'webhook_url': 'https://hooks.slack.com/test'
            }
        )

        connector = SlackConnector(config)
        assert connector.channel == Channel.SLACK
        assert connector.bot_token == 'xoxb-test'


# ============================================================================
# PIPELINE TESTS
# ============================================================================

class TestPipeline:
    """Test message pipeline"""

    def test_message_ingestor_rejects_execution_triggers(self):
        """Test that ingestor rejects messages that trigger execution"""
        ingestor = MessageIngestor()

        # Create message with triggers_execution=True (should fail in schema)
        # This test verifies the ingestor's additional check
        with pytest.raises(ValueError):
            # First create a valid message
            message = MessageArtifact(
                message_id="test",
                channel=Channel.EMAIL,
                thread_id="thread1",
                sender_hash="sender",
                recipient_hash="recipient",
                content_redacted="test",
                intent=IntentClassification.QUESTION,
                timestamp=datetime.now(timezone.utc),
                direction="inbound",
                external_party=False,
                source_system="test"
            )
            # Then try to modify it (would fail in real scenario)
            message.triggers_execution = True
            ingestor.ingest([message])

    def test_intent_classifier(self):
        """Test intent classification"""
        classifier = IntentClassifier()

        # Question
        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="What is the status?",
            intent=IntentClassification.UNKNOWN,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        intent = classifier.classify(message)
        assert intent == IntentClassification.QUESTION

    def test_redaction_pipeline(self):
        """Test PII redaction"""
        redactor = RedactionPipeline()

        text = "Contact me at john@example.com or 555-123-4567"
        redacted = redactor.redact(text)

        assert "[EMAIL_REDACTED]" in redacted
        assert "[PHONE_REDACTED]" in redacted
        assert "john@example.com" not in redacted
        assert "555-123-4567" not in redacted

    def test_message_storage(self):
        """Test message storage"""
        storage = MessageStorage()

        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="test",
            intent=IntentClassification.QUESTION,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        storage.store(message)
        retrieved = storage.get("test1")

        assert retrieved is not None
        assert retrieved.message_id == "test1"

    def test_thread_manager(self):
        """Test thread management"""
        manager = ThreadManager()

        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="test",
            intent=IntentClassification.QUESTION,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        manager.add_message_to_thread(message)
        thread = manager.get_thread("thread1")

        assert thread is not None
        assert len(thread.messages) == 1
        assert thread.requires_response  # Question requires response


# ============================================================================
# GOVERNANCE TESTS
# ============================================================================

class TestGovernance:
    """Test governance enforcement"""

    def test_communication_authorizer(self):
        """Test communication authorization"""
        authorizer = CommunicationAuthorizer()

        packet = authorizer.authorize(
            channel=Channel.EMAIL,
            thread_id="thread1",
            recipient_hashes=["hash1"],
            content="test message",
            authorized_by="control_plane_1",
            authority_level="high",
            gates_satisfied=["gate1", "gate2"],
            external_party=False
        )

        assert packet.authorized_by == "control_plane_1"
        assert len(packet.gates_satisfied) == 2
        assert authorizer.verify_authorization(packet.packet_id)

    def test_outbound_validator_detects_prohibited_content(self):
        """Test that validator detects prohibited content"""
        validator = OutboundValidator()

        # Test approval detection
        flags = validator.scan_content("I approve this transaction")
        assert flags['contains_approval']

        # Test payment detection
        flags = validator.scan_content("Please pay $1000 to vendor")
        assert flags['contains_payment']

    def test_approval_blocker(self):
        """Test approval blocker"""
        blocker = ApprovalBlocker()

        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="I approve this",
            intent=IntentClassification.APPROVAL_GRANT,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        # Should allow but flag for review
        is_safe = blocker.check_message(message)
        assert is_safe
        assert message.requires_human_review

    def test_human_signoff_enforcer(self):
        """Test human signoff enforcement"""
        enforcer = HumanSignoffEnforcer()

        packet = CommunicationPacket(
            packet_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            recipient_hashes=["hash1"],
            content="test",
            authorized_by="auth1",
            authority_level="high",
            gates_satisfied=["gate1"],
            external_party=True  # External requires signoff
        )

        # Require signoff
        enforcer.require_signoff(packet, "manager")
        assert not enforcer.verify_signoff(packet)

        # Grant signoff
        enforcer.grant_signoff(packet, "manager")
        assert enforcer.verify_signoff(packet)

    def test_audit_logger(self):
        """Test audit logging"""
        logger = AuditLogger()

        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="test",
            intent=IntentClassification.QUESTION,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        logger.log_message_received(message)

        logs = logger.get_logs("message_received")
        assert len(logs) == 1
        assert logs[0].message_id == "test1"


# ============================================================================
# COMPLIANCE TESTS
# ============================================================================

class TestCompliance:
    """Test compliance validation"""

    def test_redaction_engine(self):
        """Test advanced redaction engine"""
        engine = RedactionEngine()

        text = "Email: john@example.com, Phone: 555-123-4567, SSN: 123-45-6789"
        redacted = engine.redact(text)

        assert "[EMAIL_REDACTED]" in redacted
        assert "[PHONE_REDACTED]" in redacted
        assert "[SSN_REDACTED]" in redacted

    def test_retention_policy_manager(self):
        """Test retention policy management"""
        manager = RetentionPolicyManager()

        policy = RetentionPolicy(
            policy_id="email_policy",
            channel=Channel.EMAIL,
            retention_days=30,
            archive_after_days=30,
            delete_after_days=365
        )

        manager.set_policy(Channel.EMAIL, policy)

        # Create old message
        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="test",
            intent=IntentClassification.QUESTION,
            timestamp=datetime.now(timezone.utc) - timedelta(days=40),
            direction="inbound",
            external_party=False,
            source_system="test",
            created_at=datetime.now(timezone.utc) - timedelta(days=40)
        )

        assert manager.should_archive(message)
        assert not manager.should_delete(message)

    def test_legal_hold(self):
        """Test legal hold prevents deletion"""
        manager = RetentionPolicyManager()

        policy = RetentionPolicy(
            policy_id="email_policy",
            channel=Channel.EMAIL,
            retention_days=30,
            archive_after_days=30,
            delete_after_days=365
        )

        manager.set_policy(Channel.EMAIL, policy)

        # Create very old message
        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="test",
            intent=IntentClassification.QUESTION,
            timestamp=datetime.now(timezone.utc) - timedelta(days=400),
            direction="inbound",
            external_party=False,
            source_system="test",
            created_at=datetime.now(timezone.utc) - timedelta(days=400)
        )

        # Add legal hold
        manager.add_legal_hold("test1")

        # Should not delete despite age
        assert not manager.should_delete(message)

    def test_audit_trail_integrity(self):
        """Test audit trail integrity verification"""
        trail = AuditTrailManager()

        log1 = AuditLogEntry(
            log_id="log1",
            event_type="message_received",
            timestamp=datetime.now(timezone.utc),
            actor="system"
        )

        log2 = AuditLogEntry(
            log_id="log2",
            event_type="message_sent",
            timestamp=datetime.now(timezone.utc),
            actor="user1"
        )

        trail.add_log(log1)
        trail.add_log(log2)

        # Verify integrity
        assert trail.verify_integrity()

    def test_compliance_validator_gdpr(self):
        """Test GDPR compliance validation"""
        validator = ComplianceValidator()

        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="[EMAIL_REDACTED]",
            content_original="john@example.com",
            intent=IntentClassification.QUESTION,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        policy = RetentionPolicy(
            policy_id="email_policy",
            channel=Channel.EMAIL,
            retention_days=30,
            archive_after_days=30,
            delete_after_days=365
        )

        checks = validator.validate_gdpr(message, policy)

        assert checks['pii_redacted']
        assert checks['retention_policy_set']
        assert checks['retention_within_limit']


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test end-to-end integration"""

    def test_complete_inbound_flow(self):
        """Test complete inbound message flow"""
        # Create pipeline
        pipeline = MessagePipeline()

        # Create inbound message
        message = MessageArtifact(
            message_id="test1",
            channel=Channel.EMAIL,
            thread_id="thread1",
            sender_hash="sender",
            recipient_hash="recipient",
            content_redacted="What is the status?",
            content_original="What is the status?",
            intent=IntentClassification.UNKNOWN,
            timestamp=datetime.now(timezone.utc),
            direction="inbound",
            external_party=False,
            source_system="test"
        )

        # Process through pipeline
        processed = pipeline.process([message])

        assert len(processed) == 1
        assert processed[0].intent != IntentClassification.UNKNOWN
        assert processed[0].content_redacted is not None

    def test_complete_outbound_flow(self):
        """Test complete outbound message flow"""
        # Create governance layer
        governance = GovernanceLayer()

        # Authorize outbound
        packet = governance.authorize_outbound(
            channel=Channel.EMAIL,
            thread_id="thread1",
            recipient_hashes=["hash1"],
            content="This is a response",
            authorized_by="control_plane_1",
            authority_level="high",
            gates_satisfied=["gate1"],
            external_party=False
        )

        # Validate
        can_send, error = governance.send_outbound(packet, "system")

        assert can_send
        assert error is None

    def test_external_communication_requires_signoff(self):
        """Test that external communications require human signoff"""
        governance = GovernanceLayer()

        # Authorize external communication
        packet = governance.authorize_outbound(
            channel=Channel.EMAIL,
            thread_id="thread1",
            recipient_hashes=["hash1"],
            content="External message",
            authorized_by="control_plane_1",
            authority_level="high",
            gates_satisfied=["gate1"],
            external_party=True  # External
        )

        # Should not be able to send without signoff
        can_send, error = governance.send_outbound(packet, "system")
        assert not can_send
        assert "signoff" in error.lower()

        # Grant signoff
        governance.grant_signoff(packet, "manager")

        # Now should be able to send
        can_send, error = governance.send_outbound(packet, "system")
        assert can_send


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
