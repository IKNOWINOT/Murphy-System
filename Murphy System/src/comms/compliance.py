"""
Safety & Compliance for Communications

Provides:
1. Advanced redaction engine (PII detection)
2. Retention policy management (data lifecycle)
3. Audit trail management (immutable logs)
4. Compliance validation (GDPR, CCPA, etc.)
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set

from .schemas import (
    AuditLogEntry,
    Channel,
    MessageArtifact,
    RedactionLevel,
    RedactionRule,
    RetentionPolicy,
)

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    ADDRESS = "address"
    NAME = "name"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"


class RedactionEngine:
    """
    Advanced PII detection and redaction engine

    Supports:
    - Multiple PII types
    - Custom patterns
    - Configurable redaction levels
    - Token preservation (for re-identification if needed)
    """

    def __init__(self):
        # Built-in redaction rules
        self.rules: Dict[PIIType, RedactionRule] = {
            PIIType.EMAIL: RedactionRule(
                rule_id='email',
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                replacement='[EMAIL_REDACTED]',
                pii_type='email'
            ),
            PIIType.PHONE: RedactionRule(
                rule_id='phone',
                pattern=r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b',
                replacement='[PHONE_REDACTED]',
                pii_type='phone'
            ),
            PIIType.SSN: RedactionRule(
                rule_id='ssn',
                pattern=r'\b\d{3}-\d{2}-\d{4}\b',
                replacement='[SSN_REDACTED]',
                pii_type='ssn'
            ),
            PIIType.CREDIT_CARD: RedactionRule(
                rule_id='credit_card',
                pattern=r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
                replacement='[CC_REDACTED]',
                pii_type='credit_card'
            ),
            PIIType.IP_ADDRESS: RedactionRule(
                rule_id='ip_address',
                pattern=r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                replacement='[IP_REDACTED]',
                pii_type='ip_address'
            ),
        }

        # Token map for re-identification (if legally required)
        self.token_map: Dict[str, str] = {}

    def add_rule(self, pii_type: PIIType, rule: RedactionRule):
        """Add or update redaction rule"""
        self.rules[pii_type] = rule

    def detect_pii(self, text: str) -> Dict[PIIType, List[str]]:
        """
        Detect PII in text

        Args:
            text: Text to scan

        Returns:
            Dict mapping PII types to detected instances
        """
        detected = {}

        for pii_type, rule in self.rules.items():
            if not rule.enabled:
                continue

            matches = re.findall(rule.pattern, text)
            if matches:
                detected[pii_type] = matches

        return detected

    def redact(
        self,
        text: str,
        level: RedactionLevel = RedactionLevel.FULL,
        preserve_tokens: bool = False
    ) -> str:
        """
        Redact PII from text

        Args:
            text: Text to redact
            level: Redaction level
            preserve_tokens: Whether to preserve tokens for re-identification

        Returns:
            Redacted text
        """
        if level == RedactionLevel.NONE:
            return text

        redacted = text

        for pii_type, rule in self.rules.items():
            if not rule.enabled:
                continue

            if level == RedactionLevel.COMPLETE:
                # Redact everything
                redacted = rule.apply(redacted)
            elif level == RedactionLevel.FULL:
                # Redact all PII
                if preserve_tokens:
                    # Generate tokens for re-identification
                    matches = re.finditer(rule.pattern, redacted)
                    for match in matches:
                        original = match.group(0)
                        token = self._generate_token(original)
                        self.token_map[token] = original
                        redacted = redacted.replace(original, f"[{pii_type.value.upper()}_TOKEN_{token}]")
                else:
                    redacted = rule.apply(redacted)
            elif level == RedactionLevel.PARTIAL:
                # Redact only sensitive PII (SSN, credit card, etc.)
                if pii_type in [PIIType.SSN, PIIType.CREDIT_CARD, PIIType.PASSPORT]:
                    redacted = rule.apply(redacted)

        return redacted

    def _generate_token(self, value: str) -> str:
        """Generate token for value"""
        return hashlib.sha256(value.encode()).hexdigest()[:8]

    def reidentify(self, token: str) -> Optional[str]:
        """Re-identify value from token (if legally required)"""
        return self.token_map.get(token)


class RetentionPolicyManager:
    """
    Manages data retention policies

    Implements:
    - Automatic archiving
    - Automatic deletion
    - Legal hold support
    - Compliance reporting
    """

    def __init__(self):
        self.policies: Dict[Channel, RetentionPolicy] = {}
        self.legal_holds: Set[str] = set()  # Message IDs under legal hold

    def set_policy(self, channel: Channel, policy: RetentionPolicy):
        """Set retention policy for channel"""
        self.policies[channel] = policy

    def get_policy(self, channel: Channel) -> Optional[RetentionPolicy]:
        """Get retention policy for channel"""
        return self.policies.get(channel)

    def add_legal_hold(self, message_id: str):
        """Add message to legal hold (prevents deletion)"""
        self.legal_holds.add(message_id)

    def remove_legal_hold(self, message_id: str):
        """Remove message from legal hold"""
        self.legal_holds.discard(message_id)

    def is_under_legal_hold(self, message_id: str) -> bool:
        """Check if message is under legal hold"""
        return message_id in self.legal_holds

    def should_archive(self, message: MessageArtifact) -> bool:
        """Check if message should be archived"""
        policy = self.policies.get(message.channel)
        if not policy:
            return False

        age_days = (datetime.now(timezone.utc) - message.created_at).days
        return age_days >= policy.archive_after_days

    def should_delete(self, message: MessageArtifact) -> bool:
        """Check if message should be deleted"""
        # Never delete if under legal hold
        if self.is_under_legal_hold(message.message_id):
            return False

        policy = self.policies.get(message.channel)
        if not policy:
            return False

        age_days = (datetime.now(timezone.utc) - message.created_at).days
        return age_days >= policy.delete_after_days

    def get_retention_status(self, message: MessageArtifact) -> Dict[str, any]:
        """Get retention status for message"""
        policy = self.policies.get(message.channel)
        if not policy:
            return {'status': 'no_policy'}

        age_days = (datetime.now(timezone.utc) - message.created_at).days

        status = {
            'age_days': age_days,
            'retention_days': policy.retention_days,
            'archive_after_days': policy.archive_after_days,
            'delete_after_days': policy.delete_after_days,
            'under_legal_hold': self.is_under_legal_hold(message.message_id),
            'should_archive': self.should_archive(message),
            'should_delete': self.should_delete(message),
        }

        if age_days < policy.archive_after_days:
            status['status'] = 'active'
        elif age_days < policy.delete_after_days:
            status['status'] = 'archived'
        else:
            status['status'] = 'expired' if not self.is_under_legal_hold(message.message_id) else 'legal_hold'

        return status


class AuditTrailManager:
    """
    Manages immutable audit trails

    Features:
    - Cryptographic integrity
    - Tamper detection
    - Compliance reporting
    - Export capabilities
    """

    def __init__(self):
        self.audit_logs: List[AuditLogEntry] = []
        self.chain_hash: Optional[str] = None

    def add_log(self, log: AuditLogEntry):
        """
        Add log entry to audit trail

        CRITICAL: Logs are immutable once added
        """
        # Verify log is immutable
        if not log.immutable:
            raise ValueError("Audit log must be immutable")

        # Add to chain
        self.audit_logs.append(log)

        # Update chain hash
        self.chain_hash = self._compute_chain_hash()

    def _compute_chain_hash(self) -> str:
        """Compute hash of entire audit chain"""
        if not self.audit_logs:
            return hashlib.sha256(b'').hexdigest()

        # Concatenate all log hashes
        chain_data = ''.join(log.integrity_hash for log in self.audit_logs)
        return hashlib.sha256(chain_data.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify integrity of audit trail"""
        # Verify each log
        for log in self.audit_logs:
            if log.integrity_hash != log._compute_hash():
                return False

        # Verify chain
        expected_chain_hash = self._compute_chain_hash()
        return self.chain_hash == expected_chain_hash

    def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None
    ) -> List[AuditLogEntry]:
        """Get audit logs with optional filters"""
        logs = self.audit_logs

        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]

        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]

        if event_type:
            logs = [log for log in logs if log.event_type == event_type]

        return logs

    def export_logs(self, output_format: str = 'json') -> str:
        """Export audit logs for compliance reporting"""
        import json

        if output_format == 'json':
            logs_data = [
                {
                    'log_id': log.log_id,
                    'event_type': log.event_type,
                    'timestamp': log.timestamp.isoformat(),
                    'message_id': log.message_id,
                    'packet_id': log.packet_id,
                    'channel': log.channel.value if log.channel else None,
                    'actor': log.actor,
                    'details': log.details,
                    'integrity_hash': log.integrity_hash
                }
                for log in self.audit_logs
            ]

            return json.dumps({
                'logs': logs_data,
                'chain_hash': self.chain_hash,
                'total_logs': len(self.audit_logs)
            }, indent=2)

        return ""


class ComplianceValidator:
    """
    Validates compliance with regulations

    Supports:
    - GDPR (EU data protection)
    - CCPA (California privacy)
    - HIPAA (Healthcare privacy)
    - SOX (Financial reporting)
    """

    def __init__(self):
        self.regulations = {
            'GDPR': {
                'requires_consent': True,
                'right_to_erasure': True,
                'data_portability': True,
                'retention_limit_days': 365
            },
            'CCPA': {
                'requires_consent': True,
                'right_to_deletion': True,
                'right_to_opt_out': True,
                'retention_limit_days': 365
            },
            'HIPAA': {
                'requires_encryption': True,
                'audit_trail_required': True,
                'retention_min_days': 2190,  # 6 years
                'retention_max_days': 2555   # 7 years
            },
            'SOX': {
                'audit_trail_required': True,
                'retention_min_days': 2555,  # 7 years
                'immutable_logs': True
            }
        }

    def validate_gdpr(self, message: MessageArtifact, retention_policy: Optional[RetentionPolicy]) -> Dict[str, bool]:
        """Validate GDPR compliance"""
        checks = {
            'pii_redacted': message.content_redacted != message.content_original,
            'retention_policy_set': retention_policy is not None,
            'retention_within_limit': False
        }

        if retention_policy:
            checks['retention_within_limit'] = retention_policy.delete_after_days <= self.regulations['GDPR']['retention_limit_days']

        return checks

    def validate_ccpa(self, message: MessageArtifact, retention_policy: Optional[RetentionPolicy]) -> Dict[str, bool]:
        """Validate CCPA compliance"""
        checks = {
            'pii_redacted': message.content_redacted != message.content_original,
            'retention_policy_set': retention_policy is not None,
            'retention_within_limit': False
        }

        if retention_policy:
            checks['retention_within_limit'] = retention_policy.delete_after_days <= self.regulations['CCPA']['retention_limit_days']

        return checks

    def validate_hipaa(self, message: MessageArtifact, has_audit_trail: bool) -> Dict[str, bool]:
        """Validate HIPAA compliance"""
        checks = {
            'pii_redacted': message.content_redacted != message.content_original,
            'audit_trail_exists': has_audit_trail,
            'integrity_verified': message.verify_integrity()
        }

        return checks

    def validate_sox(self, audit_trail: AuditTrailManager) -> Dict[str, bool]:
        """Validate SOX compliance"""
        checks = {
            'audit_trail_exists': len(audit_trail.audit_logs) > 0,
            'audit_trail_immutable': all(log.immutable for log in audit_trail.audit_logs),
            'integrity_verified': audit_trail.verify_integrity()
        }

        return checks

    def generate_compliance_report(
        self,
        messages: List[MessageArtifact],
        retention_policies: Dict[Channel, RetentionPolicy],
        audit_trail: AuditTrailManager
    ) -> Dict[str, any]:
        """Generate comprehensive compliance report"""
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_messages': len(messages),
            'regulations': {}
        }

        # GDPR checks
        gdpr_compliant = 0
        for message in messages:
            policy = retention_policies.get(message.channel)
            checks = self.validate_gdpr(message, policy)
            if all(checks.values()):
                gdpr_compliant += 1

        report['regulations']['GDPR'] = {
            'compliant_messages': gdpr_compliant,
            'compliance_rate': gdpr_compliant / (len(messages) or 1) if messages else 0
        }

        # SOX checks
        sox_checks = self.validate_sox(audit_trail)
        report['regulations']['SOX'] = {
            'checks': sox_checks,
            'compliant': all(sox_checks.values())
        }

        return report


class ComplianceSystem:
    """
    Complete compliance system

    Integrates:
    - Redaction engine
    - Retention policy manager
    - Audit trail manager
    - Compliance validator
    """

    def __init__(self):
        self.redaction_engine = RedactionEngine()
        self.retention_manager = RetentionPolicyManager()
        self.audit_trail = AuditTrailManager()
        self.validator = ComplianceValidator()

    def process_message(self, message: MessageArtifact, redaction_level: RedactionLevel = RedactionLevel.FULL):
        """Process message for compliance"""
        # Redact PII
        if message.content_original:
            message.content_redacted = self.redaction_engine.redact(
                message.content_original,
                level=redaction_level
            )

    def add_audit_log(self, log: AuditLogEntry):
        """Add log to audit trail"""
        self.audit_trail.add_log(log)

    def validate_compliance(
        self,
        messages: List[MessageArtifact],
        regulation: str
    ) -> Dict[str, any]:
        """Validate compliance with specific regulation"""
        if regulation == 'GDPR':
            results = {}
            for message in messages:
                policy = self.retention_manager.get_policy(message.channel)
                results[message.message_id] = self.validator.validate_gdpr(message, policy)
            return results

        elif regulation == 'SOX':
            return self.validator.validate_sox(self.audit_trail)

        return {}

    def generate_report(self, messages: List[MessageArtifact]) -> Dict[str, any]:
        """Generate comprehensive compliance report"""
        return self.validator.generate_compliance_report(
            messages,
            self.retention_manager.policies,
            self.audit_trail
        )
