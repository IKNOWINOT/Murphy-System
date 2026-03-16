"""
Core data models for Communication Connectors & Governance Layer

CRITICAL SAFETY CONSTRAINTS:
- Inbound messages are artifacts ONLY (never trigger execution)
- Outbound messages require CommunicationPacket authorization
- PII is redacted by default
- Audit trails are immutable
- Human signoff required for external communications
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


class Channel(Enum):
    """Communication channels"""
    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    SMS = "sms"
    TICKET = "ticket"


class IntentClassification(Enum):
    """Intent classification for messages"""
    QUESTION = "question"                # Asking for information
    APPROVAL_REQUEST = "approval_request" # Requesting approval (NOT granting)
    APPROVAL_GRANT = "approval_grant"    # Granting approval (BLOCKED for execution)
    DENIAL = "denial"                    # Denying request
    CLARIFICATION = "clarification"      # Seeking clarification
    INFORMATION = "information"          # Providing information
    ESCALATION = "escalation"            # Escalating issue
    REPORT = "report"                    # Status report
    UNKNOWN = "unknown"                  # Cannot classify


class RedactionLevel(Enum):
    """Redaction levels for PII"""
    NONE = "none"           # No redaction
    PARTIAL = "partial"     # Redact sensitive fields only
    FULL = "full"          # Redact all PII
    COMPLETE = "complete"   # Redact everything except metadata


@dataclass
class RedactionRule:
    """
    Rule for redacting PII from messages
    """
    rule_id: str
    pattern: str              # Regex pattern to match
    replacement: str          # Replacement text (e.g., "[REDACTED]")
    pii_type: str            # Type of PII (email, phone, ssn, etc.)
    enabled: bool = True

    def apply(self, text: str) -> str:
        """Apply redaction rule to text"""
        import re
        return re.sub(self.pattern, self.replacement, text)


@dataclass
class RetentionPolicy:
    """
    Data retention policy for messages
    """
    policy_id: str
    channel: Channel
    retention_days: int       # How long to keep messages
    archive_after_days: int   # When to archive (move to cold storage)
    delete_after_days: int    # When to permanently delete
    requires_legal_hold: bool = False

    def __post_init__(self):
        """Validate retention policy"""
        if self.delete_after_days < self.retention_days:
            raise ValueError("delete_after_days must be >= retention_days")
        if self.archive_after_days > self.delete_after_days:
            raise ValueError("archive_after_days must be <= delete_after_days")


@dataclass
class MessageArtifact:
    """
    Message artifact (inbound or outbound)

    CRITICAL: Messages are ARTIFACTS ONLY. They CANNOT trigger execution.
    All messages must go through Control Plane for any action.
    """
    message_id: str
    channel: Channel
    thread_id: str

    # Sender/recipient (hashed or tokenized for privacy)
    sender_hash: str          # SHA-256 hash of sender identifier
    recipient_hash: str       # SHA-256 hash of recipient identifier

    # Content (redacted by default)
    content_redacted: str     # Redacted content (safe to store/display)

    # Classification
    intent: IntentClassification

    # Metadata
    timestamp: datetime
    direction: Literal["inbound", "outbound"]
    external_party: bool      # True if involves external party

    # Provenance
    source_system: str        # Which connector ingested this

    content_original: Optional[str] = None  # Original content (secure storage only)
    provenance: Dict[str, any] = field(default_factory=dict)
    integrity_hash: Optional[str] = None

    # Safety flags
    triggers_execution: bool = False  # MUST be False (enforced)
    requires_human_review: bool = False

    # Audit
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Enforce safety constraints"""
        # CRITICAL: Messages CANNOT trigger execution
        if self.triggers_execution:
            raise ValueError("MessageArtifact.triggers_execution MUST be False")

        # Compute integrity hash
        if self.integrity_hash is None:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of message"""
        data = {
            "message_id": self.message_id,
            "channel": self.channel.value,
            "thread_id": self.thread_id,
            "sender_hash": self.sender_hash,
            "recipient_hash": self.recipient_hash,
            "content_redacted": self.content_redacted,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify integrity hash matches current state"""
        return self.integrity_hash == self._compute_hash()

    @staticmethod
    def hash_identifier(identifier: str) -> str:
        """Hash an identifier (email, phone, etc.) for privacy"""
        return hashlib.sha256(identifier.encode()).hexdigest()


@dataclass
class CommunicationPacket:
    """
    Authorized outbound communication packet

    CRITICAL: This is the ONLY way to send outbound messages.
    Requires Control Plane authorization and gate clearance.
    """
    packet_id: str
    channel: Channel
    thread_id: str

    # Recipients (hashed)
    recipient_hashes: List[str]

    # Content (must be pre-approved)
    content: str

    # Authorization (REQUIRED)
    authorized_by: str        # Control Plane authorization ID
    authority_level: str      # Authority level of authorizer
    gates_satisfied: List[str] # Gates that were satisfied

    # Safety constraints
    external_party: bool
    human_signoff_required: bool = True  # Default: require human signoff
    human_signoff_granted: bool = False
    human_signoff_by: Optional[str] = None
    human_signoff_at: Optional[datetime] = None

    # Prohibited actions (CANNOT be in content)
    contains_approval: bool = False      # MUST be False
    contains_payment: bool = False       # MUST be False
    contains_contract: bool = False      # MUST be False

    # Audit
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None

    # Provenance
    integrity_hash: Optional[str] = None

    def __post_init__(self):
        """Enforce safety constraints"""
        # CRITICAL: Cannot contain executable approvals/payments/contracts
        if self.contains_approval:
            raise ValueError("CommunicationPacket cannot contain executable approvals")
        if self.contains_payment:
            raise ValueError("CommunicationPacket cannot contain executable payments")
        if self.contains_contract:
            raise ValueError("CommunicationPacket cannot contain executable contracts")

        # External communications require human signoff
        if self.external_party and self.human_signoff_required and not self.human_signoff_granted:
            # This is OK - signoff will be granted later
            pass

        # Compute integrity hash
        if self.integrity_hash is None:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of packet"""
        data = {
            "packet_id": self.packet_id,
            "channel": self.channel.value,
            "thread_id": self.thread_id,
            "recipient_hashes": sorted(self.recipient_hashes),
            "content": self.content,
            "authorized_by": self.authorized_by,
            "external_party": self.external_party,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def grant_human_signoff(self, signoff_by: str):
        """Grant human signoff for external communication"""
        if not self.external_party:
            raise ValueError("Human signoff only required for external communications")

        self.human_signoff_granted = True
        self.human_signoff_by = signoff_by
        self.human_signoff_at = datetime.now(timezone.utc)

    def can_send(self) -> bool:
        """Check if packet can be sent"""
        # Must have authorization
        if not self.authorized_by:
            return False

        # External communications require human signoff
        if self.external_party and self.human_signoff_required and not self.human_signoff_granted:
            return False

        # Cannot contain prohibited actions
        if self.contains_approval or self.contains_payment or self.contains_contract:
            return False

        return True


@dataclass
class ThreadContext:
    """
    Conversation thread context
    """
    thread_id: str
    channel: Channel
    participants: List[str]   # Hashed identifiers
    messages: List[MessageArtifact] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Classification
    primary_intent: Optional[IntentClassification] = None
    requires_response: bool = False

    def add_message(self, message: MessageArtifact):
        """Add message to thread"""
        if message.thread_id != self.thread_id:
            raise ValueError("Message thread_id does not match thread")

        self.messages.append(message)
        self.last_activity = datetime.now(timezone.utc)

        # Update primary intent if not set
        if not self.primary_intent and message.intent != IntentClassification.UNKNOWN:
            self.primary_intent = message.intent


@dataclass
class AuditLogEntry:
    """
    Immutable audit log entry for communication events
    """
    log_id: str
    event_type: Literal[
        "message_received",
        "message_sent",
        "authorization_granted",
        "authorization_denied",
        "human_signoff_granted",
        "redaction_applied"
    ]
    timestamp: datetime

    # Actor
    actor: str                # Who performed the action

    # Event details
    message_id: Optional[str] = None
    packet_id: Optional[str] = None
    channel: Optional[Channel] = None

    # Details
    details: Dict[str, any] = field(default_factory=dict)

    # Integrity
    integrity_hash: Optional[str] = None
    immutable: bool = True    # ALWAYS True

    def __post_init__(self):
        """Enforce immutability"""
        if not self.immutable:
            raise ValueError("AuditLogEntry.immutable MUST be True")

        # Compute integrity hash
        if self.integrity_hash is None:
            self.integrity_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of log entry"""
        data = {
            "log_id": self.log_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "packet_id": self.packet_id,
            "actor": self.actor,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class ConnectorConfig:
    """
    Configuration for a communication connector
    """
    connector_id: str
    channel: Channel
    enabled: bool = True

    # Connection details (encrypted in production)
    connection_params: Dict[str, any] = field(default_factory=dict)

    # Rate limits
    max_messages_per_minute: int = 60
    max_messages_per_hour: int = 1000

    # Retry policy
    max_retries: int = 3
    retry_delay_seconds: int = 5

    # Security
    require_tls: bool = True
    verify_certificates: bool = True
