"""
Tests for Data Leak Prevention System
Phase 8 of Security Plane

Tests all DLP components:
- Sensitive data classification
- Data exfiltration detection
- Encryption enforcement
- Access logging
- Data retention policies
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import json

from src.security_plane.data_leak_prevention import (
    # Enums
    DataSensitivityLevel,
    DataCategory,
    # Classification
    DataClassification,
    SensitiveDataClassifier,
    # Exfiltration
    DataTransfer,
    ExfiltrationDetector,
    # Encryption
    EncryptionPolicy,
    EncryptionEnforcer,
    # Access Logging
    DataAccessLog,
    DataAccessLogger,
    # Retention
    RetentionPolicy,
    DataRetentionManager,
    # Integrated System
    DataLeakPreventionSystem,
)


# ============================================================================
# DATA CLASSIFICATION TESTS
# ============================================================================

def test_data_classification_validation():
    """Test classification validation"""
    # Valid classification
    classification = DataClassification(
        data_id="test_001",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.PII},
        detected_patterns=["SSN"],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=["authorized_users"]
    )
    assert classification.data_id == "test_001"

    # Invalid confidence
    with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
        DataClassification(
            data_id="test_002",
            sensitivity_level=DataSensitivityLevel.PUBLIC,
            categories=set(),
            detected_patterns=[],
            classification_confidence=1.5,  # Invalid
            classified_at=datetime.now(timezone.utc),
            classified_by="test",
            encryption_required=False,
            retention_days=None,
            access_restrictions=[]
        )

    # SECRET without encryption
    with pytest.raises(ValueError, match="MUST require encryption"):
        DataClassification(
            data_id="test_003",
            sensitivity_level=DataSensitivityLevel.SECRET,
            categories={DataCategory.FINANCIAL},
            detected_patterns=["Credit Card"],
            classification_confidence=0.9,
            classified_at=datetime.now(timezone.utc),
            classified_by="test",
            encryption_required=False,  # Invalid for SECRET
            retention_days=365,
            access_restrictions=[]
        )


def test_classifier_pii_detection():
    """Test PII detection"""
    classifier = SensitiveDataClassifier()

    # SSN detection
    data = "My SSN is 123-45-6789"
    classification = classifier.classify(data, "test_ssn")

    assert DataCategory.PII in classification.categories
    assert "SSN" in classification.detected_patterns
    # SSN pattern matches both PII and FINANCIAL patterns, so it's classified as SECRET
    assert classification.sensitivity_level in [DataSensitivityLevel.CONFIDENTIAL, DataSensitivityLevel.SECRET]
    assert classification.classification_confidence > 0.8

    # Email detection
    data = "Contact me at user@example.com"
    classification = classifier.classify(data, "test_email")

    assert DataCategory.PII in classification.categories
    assert "Email" in classification.detected_patterns


def test_classifier_credentials_detection():
    """Test credentials detection"""
    classifier = SensitiveDataClassifier()

    # Password detection
    data = "password: super_secret_123"
    classification = classifier.classify(data, "test_pwd")

    assert DataCategory.CREDENTIALS in classification.categories
    assert "Password" in classification.detected_patterns
    assert classification.sensitivity_level == DataSensitivityLevel.TOP_SECRET
    assert classification.encryption_required is True
    assert classification.retention_days == 90  # Short retention

    # API key detection
    data = "api_key=abc123xyz789"
    classification = classifier.classify(data, "test_api")

    assert DataCategory.CREDENTIALS in classification.categories
    assert "API Key" in classification.detected_patterns


def test_classifier_financial_detection():
    """Test financial data detection"""
    classifier = SensitiveDataClassifier()

    # Credit card detection
    data = "Card number: 4532-1234-5678-9010"
    classification = classifier.classify(data, "test_cc")

    assert DataCategory.FINANCIAL in classification.categories
    assert "Credit Card" in classification.detected_patterns
    assert classification.sensitivity_level == DataSensitivityLevel.SECRET
    assert classification.retention_days == 2555  # 7 years


def test_classifier_cryptographic_detection():
    """Test cryptographic material detection"""
    classifier = SensitiveDataClassifier()

    data = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
    classification = classifier.classify(data, "test_key")

    assert DataCategory.CRYPTOGRAPHIC in classification.categories
    assert "Private Key" in classification.detected_patterns
    assert classification.sensitivity_level == DataSensitivityLevel.TOP_SECRET


def test_classifier_public_data():
    """Test public data classification"""
    classifier = SensitiveDataClassifier()

    data = "This is just some public information"
    classification = classifier.classify(data, "test_public")

    assert len(classification.categories) == 0
    assert classification.sensitivity_level == DataSensitivityLevel.PUBLIC
    assert classification.encryption_required is False
    assert classification.retention_days is None


# ============================================================================
# EXFILTRATION DETECTION TESTS
# ============================================================================

def test_exfiltration_unencrypted_sensitive():
    """Test blocking unencrypted sensitive data transfer"""
    detector = ExfiltrationDetector()

    classification = DataClassification(
        data_id="secret_001",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=["Credit Card"],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    transfer = detector.check_transfer(
        data_id="secret_001",
        classification=classification,
        source="internal_db",
        destination="external_api",
        size_bytes=1024,
        initiated_by="user_123",
        encrypted=False  # Not encrypted
    )

    assert transfer.blocked is True
    assert "Unencrypted transfer" in transfer.block_reason
    assert transfer.authorized is False


def test_exfiltration_blocked_destination():
    """Test blocking transfers to blocked destinations"""
    detector = ExfiltrationDetector()

    classification = DataClassification(
        data_id="data_001",
        sensitivity_level=DataSensitivityLevel.INTERNAL,
        categories={DataCategory.PII},
        detected_patterns=["Email"],
        classification_confidence=0.8,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=False,
        retention_days=365,
        access_restrictions=[]
    )

    transfer = detector.check_transfer(
        data_id="data_001",
        classification=classification,
        source="internal_db",
        destination="external_network",  # Blocked
        size_bytes=1024,
        initiated_by="user_123",
        encrypted=True
    )

    assert transfer.blocked is True
    assert "blocked destination" in transfer.block_reason


def test_exfiltration_rate_limiting():
    """Test rate limiting for sensitive data"""
    detector = ExfiltrationDetector()

    classification = DataClassification(
        data_id="secret_002",
        sensitivity_level=DataSensitivityLevel.TOP_SECRET,
        categories={DataCategory.CREDENTIALS},
        detected_patterns=["API Key"],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=90,
        access_restrictions=[]
    )

    # First transfer (5MB) - should succeed
    transfer1 = detector.check_transfer(
        data_id="secret_002",
        classification=classification,
        source="vault",
        destination="secure_endpoint",
        size_bytes=5 * 1024 * 1024,
        initiated_by="user_123",
        encrypted=True
    )
    assert transfer1.blocked is False

    # Second transfer (6MB) - should be blocked (total 11MB > 10MB limit)
    transfer2 = detector.check_transfer(
        data_id="secret_002",
        classification=classification,
        source="vault",
        destination="secure_endpoint",
        size_bytes=6 * 1024 * 1024,
        initiated_by="user_123",
        encrypted=True
    )
    assert transfer2.blocked is True
    assert "Rate limit exceeded" in transfer2.block_reason


def test_exfiltration_authorized_transfer():
    """Test authorized transfer"""
    detector = ExfiltrationDetector()

    classification = DataClassification(
        data_id="data_002",
        sensitivity_level=DataSensitivityLevel.CONFIDENTIAL,
        categories={DataCategory.PII},
        detected_patterns=["Email"],
        classification_confidence=0.8,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    transfer = detector.check_transfer(
        data_id="data_002",
        classification=classification,
        source="internal_db",
        destination="secure_backup",
        size_bytes=1024,
        initiated_by="user_123",
        encrypted=True
    )

    assert transfer.blocked is False
    assert transfer.authorized is True
    assert transfer.block_reason is None


def test_exfiltration_get_blocked_transfers():
    """Test retrieving blocked transfers"""
    detector = ExfiltrationDetector()

    classification = DataClassification(
        data_id="data_003",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    # Create some transfers
    detector.check_transfer("data_003", classification, "src", "external_network", 1024, "user", True)
    detector.check_transfer("data_003", classification, "src", "secure", 1024, "user", True)

    blocked = detector.get_blocked_transfers()
    assert len(blocked) >= 1
    assert all(t.blocked for t in blocked)


# ============================================================================
# ENCRYPTION ENFORCEMENT TESTS
# ============================================================================

def test_encryption_policy_top_secret():
    """Test TOP_SECRET encryption policy"""
    enforcer = EncryptionEnforcer()
    policy = enforcer.get_policy(DataSensitivityLevel.TOP_SECRET)

    assert policy.encryption_at_rest_required is True
    assert policy.encryption_in_transit_required is True
    assert policy.key_rotation_days == 30


def test_encryption_policy_public():
    """Test PUBLIC encryption policy"""
    enforcer = EncryptionEnforcer()
    policy = enforcer.get_policy(DataSensitivityLevel.PUBLIC)

    assert policy.encryption_at_rest_required is False
    assert policy.encryption_in_transit_required is False


def test_encryption_validation_success():
    """Test successful encryption validation"""
    enforcer = EncryptionEnforcer()

    classification = DataClassification(
        data_id="data_004",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    valid, error = enforcer.validate_encryption(
        classification=classification,
        encrypted_at_rest=True,
        encrypted_in_transit=True
    )

    assert valid is True
    assert error is None


def test_encryption_validation_missing_at_rest():
    """Test validation failure for missing encryption at rest"""
    enforcer = EncryptionEnforcer()

    classification = DataClassification(
        data_id="data_005",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    valid, error = enforcer.validate_encryption(
        classification=classification,
        encrypted_at_rest=False,  # Missing
        encrypted_in_transit=True
    )

    assert valid is False
    assert "at rest required" in error


def test_encryption_validation_missing_in_transit():
    """Test validation failure for missing encryption in transit"""
    enforcer = EncryptionEnforcer()

    classification = DataClassification(
        data_id="data_006",
        sensitivity_level=DataSensitivityLevel.CONFIDENTIAL,
        categories={DataCategory.PII},
        detected_patterns=[],
        classification_confidence=0.8,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    valid, error = enforcer.validate_encryption(
        classification=classification,
        encrypted_at_rest=True,
        encrypted_in_transit=False  # Missing
    )

    assert valid is False
    assert "in transit required" in error


# ============================================================================
# ACCESS LOGGING TESTS
# ============================================================================

def test_access_logging():
    """Test access logging"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        log_file = Path(f.name)

    try:
        logger = DataAccessLogger(log_file)

        classification = DataClassification(
            data_id="data_007",
            sensitivity_level=DataSensitivityLevel.CONFIDENTIAL,
            categories={DataCategory.PII},
            detected_patterns=["Email"],
            classification_confidence=0.8,
            classified_at=datetime.now(timezone.utc),
            classified_by="test",
            encryption_required=True,
            retention_days=365,
            access_restrictions=[]
        )

        log_entry = logger.log_access(
            data_id="data_007",
            classification=classification,
            accessed_by="user_123",
            access_type="read",
            authorized=True,
            source_ip="192.168.1.100"
        )

        assert log_entry.data_id == "data_007"
        assert log_entry.accessed_by == "user_123"
        assert log_entry.authorized is True

        # Check file was written
        assert log_file.exists()
        with open(log_file) as f:
            content = f.read()
            assert "data_007" in content
            assert "user_123" in content

    finally:
        log_file.unlink()


def test_access_logging_unauthorized():
    """Test logging unauthorized access"""
    logger = DataAccessLogger()

    classification = DataClassification(
        data_id="data_008",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    log_entry = logger.log_access(
        data_id="data_008",
        classification=classification,
        accessed_by="user_456",
        access_type="write",
        authorized=False,
        denial_reason="Insufficient permissions"
    )

    assert log_entry.authorized is False
    assert log_entry.denial_reason == "Insufficient permissions"


def test_access_logging_query():
    """Test querying access logs"""
    logger = DataAccessLogger()

    classification = DataClassification(
        data_id="data_009",
        sensitivity_level=DataSensitivityLevel.INTERNAL,
        categories={DataCategory.PII},
        detected_patterns=[],
        classification_confidence=0.7,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=False,
        retention_days=365,
        access_restrictions=[]
    )

    # Log multiple accesses
    logger.log_access("data_009", classification, "user_123", "read", True)
    logger.log_access("data_009", classification, "user_456", "write", True)
    logger.log_access("data_010", classification, "user_123", "read", True)

    # Query by data_id
    logs = logger.get_access_logs(data_id="data_009")
    assert len(logs) == 2

    # Query by user
    logs = logger.get_access_logs(accessed_by="user_123")
    assert len(logs) == 2


def test_access_logging_unauthorized_attempts():
    """Test retrieving unauthorized access attempts"""
    logger = DataAccessLogger()

    classification = DataClassification(
        data_id="data_011",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    # Log authorized and unauthorized
    logger.log_access("data_011", classification, "user_123", "read", True)
    logger.log_access("data_011", classification, "user_456", "write", False, "No permission")
    logger.log_access("data_011", classification, "user_789", "delete", False, "No permission")

    unauthorized = logger.get_unauthorized_access_attempts()
    assert len(unauthorized) == 2
    assert all(not log.authorized for log in unauthorized)


# ============================================================================
# DATA RETENTION TESTS
# ============================================================================

def test_retention_policy_top_secret():
    """Test TOP_SECRET retention policy"""
    manager = DataRetentionManager()
    policy = manager.get_policy(DataSensitivityLevel.TOP_SECRET)

    assert policy.retention_days == 90
    assert policy.auto_delete is True
    assert policy.archive_before_delete is True


def test_retention_policy_public():
    """Test PUBLIC retention policy"""
    manager = DataRetentionManager()
    policy = manager.get_policy(DataSensitivityLevel.PUBLIC)

    assert policy.retention_days is None  # Indefinite
    assert policy.auto_delete is False


def test_retention_should_delete_expired():
    """Test deletion of expired data"""
    manager = DataRetentionManager()

    classification = DataClassification(
        data_id="data_012",
        sensitivity_level=DataSensitivityLevel.TOP_SECRET,
        categories={DataCategory.CREDENTIALS},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=90,
        access_restrictions=[]
    )

    # Data created 100 days ago (expired)
    created_at = datetime.now(timezone.utc) - timedelta(days=100)
    should_delete, reason = manager.should_delete("data_012", classification, created_at)

    assert should_delete is True
    assert reason is None


def test_retention_should_not_delete_not_expired():
    """Test retention of non-expired data"""
    manager = DataRetentionManager()

    classification = DataClassification(
        data_id="data_013",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=2555,
        access_restrictions=[]
    )

    # Data created 30 days ago (not expired)
    created_at = datetime.now(timezone.utc) - timedelta(days=30)
    should_delete, reason = manager.should_delete("data_013", classification, created_at)

    assert should_delete is False
    assert "not expired" in reason


def test_retention_legal_hold():
    """Test legal hold prevents deletion"""
    manager = DataRetentionManager()

    classification = DataClassification(
        data_id="data_014",
        sensitivity_level=DataSensitivityLevel.SECRET,
        categories={DataCategory.FINANCIAL},
        detected_patterns=[],
        classification_confidence=0.9,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=True,
        retention_days=365,
        access_restrictions=[]
    )

    # Add legal hold
    manager.add_legal_hold("data_014")

    # Data created 400 days ago (expired but under legal hold)
    created_at = datetime.now(timezone.utc) - timedelta(days=400)
    should_delete, reason = manager.should_delete("data_014", classification, created_at)

    assert should_delete is False
    assert "legal hold" in reason

    # Remove legal hold
    manager.remove_legal_hold("data_014")
    should_delete, reason = manager.should_delete("data_014", classification, created_at)
    # After removing legal hold, check if policy allows auto-delete
    # SECRET policy has 2555 days retention, so 400 days is not expired
    assert should_delete is False
    assert "not expired" in reason


def test_retention_indefinite():
    """Test indefinite retention"""
    manager = DataRetentionManager()

    classification = DataClassification(
        data_id="data_015",
        sensitivity_level=DataSensitivityLevel.PUBLIC,
        categories=set(),
        detected_patterns=[],
        classification_confidence=0.5,
        classified_at=datetime.now(timezone.utc),
        classified_by="test",
        encryption_required=False,
        retention_days=None,
        access_restrictions=[]
    )

    # Data created 1000 days ago
    created_at = datetime.now(timezone.utc) - timedelta(days=1000)
    should_delete, reason = manager.should_delete("data_015", classification, created_at)

    assert should_delete is False
    assert "Indefinite retention" in reason


# ============================================================================
# INTEGRATED SYSTEM TESTS
# ============================================================================

def test_dlp_system_classify_and_protect():
    """Test integrated classification and protection"""
    dlp = DataLeakPreventionSystem()

    data = "My credit card is 4532-1234-5678-9010"
    classification = dlp.classify_and_protect(data, "card_001")

    assert classification.data_id == "card_001"
    assert DataCategory.FINANCIAL in classification.categories
    assert classification.sensitivity_level == DataSensitivityLevel.SECRET
    assert "card_001" in dlp.classified_data


def test_dlp_system_authorize_transfer():
    """Test integrated transfer authorization"""
    dlp = DataLeakPreventionSystem()

    # Classify data
    data = "password: secret123"
    classification = dlp.classify_and_protect(data, "pwd_001")

    # Try unencrypted transfer (should fail)
    authorized, reason = dlp.authorize_transfer(
        data_id="pwd_001",
        source="vault",
        destination="api",
        size_bytes=1024,
        initiated_by="user_123",
        encrypted=False
    )

    assert authorized is False
    assert "Unencrypted transfer" in reason

    # Try encrypted transfer (should succeed)
    authorized, reason = dlp.authorize_transfer(
        data_id="pwd_001",
        source="vault",
        destination="secure_api",
        size_bytes=1024,
        initiated_by="user_123",
        encrypted=True
    )

    assert authorized is True


def test_dlp_system_validate_storage():
    """Test integrated storage validation"""
    dlp = DataLeakPreventionSystem()

    # Classify sensitive data
    data = "SSN: 123-45-6789"
    classification = dlp.classify_and_protect(data, "ssn_001")

    # Validate storage without encryption (should fail)
    valid, error = dlp.validate_storage(
        data_id="ssn_001",
        encrypted_at_rest=False,
        encrypted_in_transit=True
    )

    assert valid is False
    assert "at rest required" in error

    # Validate storage with encryption (should succeed)
    valid, error = dlp.validate_storage(
        data_id="ssn_001",
        encrypted_at_rest=True,
        encrypted_in_transit=True
    )

    assert valid is True


def test_dlp_system_check_retention():
    """Test integrated retention checking"""
    dlp = DataLeakPreventionSystem()

    # Classify data
    data = "api_key=abc123"
    classification = dlp.classify_and_protect(data, "key_001")

    # Check retention for old data
    created_at = datetime.now(timezone.utc) - timedelta(days=100)
    should_delete, reason = dlp.check_retention("key_001", created_at)

    assert should_delete is True  # TOP_SECRET has 90-day retention


def test_dlp_system_statistics():
    """Test DLP statistics"""
    dlp = DataLeakPreventionSystem()

    # Classify some data
    dlp.classify_and_protect("password: secret", "pwd_001")
    dlp.classify_and_protect("SSN: 123-45-6789", "ssn_001")
    dlp.classify_and_protect("Public info", "pub_001")

    # Attempt transfers
    dlp.authorize_transfer("pwd_001", "src", "dst", 1024, "user", False)
    dlp.authorize_transfer("ssn_001", "src", "dst", 1024, "user", True)

    stats = dlp.get_statistics()

    assert stats["classified_data_count"] == 3
    assert stats["total_transfers"] == 2
    assert stats["blocked_transfers"] >= 1
    assert stats["total_access_logs"] >= 2


def test_dlp_system_unclassified_data():
    """Test handling of unclassified data"""
    dlp = DataLeakPreventionSystem()

    # Try to authorize transfer of unclassified data
    authorized, reason = dlp.authorize_transfer(
        data_id="unknown_001",
        source="src",
        destination="dst",
        size_bytes=1024,
        initiated_by="user",
        encrypted=True
    )

    assert authorized is False
    assert "not classified" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
