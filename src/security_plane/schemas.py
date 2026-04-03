"""
Security Plane Data Models

Core data structures for the Security Plane.

CRITICAL SECURITY CONSTRAINTS:
1. No identity is trusted by default
2. Trust is continuously re-computed
3. Authority decays automatically
4. All actions are logged immutably
5. Fail closed on any anomaly
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TrustLevel(Enum):
    """Trust level for an identity."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthorityBand(Enum):
    """Authority band for execution."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Alias for compatibility
AuthorityLevel = AuthorityBand


class SecurityAction(Enum):
    """Security action taken by the Security Plane."""
    ALLOW = "allow"
    RESTRICT = "restrict"
    THROTTLE = "throttle"
    QUARANTINE = "quarantine"
    FREEZE = "freeze"
    ESCALATE = "escalate"


class AnomalyType(Enum):
    """Type of security anomaly detected."""
    UNUSUAL_PATTERN = "unusual_pattern"
    AUTHORITY_PRESSURE = "authority_pressure"
    NEAR_GATE_ATTEMPTS = "near_gate_attempts"
    TIMING_ANOMALY = "timing_anomaly"
    CORRELATION_ATTEMPT = "correlation_attempt"
    SEMANTIC_PROBING = "semantic_probing"
    REPLAY_ATTEMPT = "replay_attempt"
    FORGERY_ATTEMPT = "forgery_attempt"


class CryptographicAlgorithm(Enum):
    """Cryptographic algorithm type."""
    CLASSICAL = "classical"
    POST_QUANTUM = "post_quantum"
    HYBRID = "hybrid"


@dataclass
class TrustScore:
    """
    Continuously computed trust score for an identity.

    Trust is NOT binary - it's a multi-dimensional score that decays over time.
    """
    identity_id: str
    trust_level: TrustLevel
    confidence: float  # 0.0 to 1.0
    computed_at: datetime

    # Trust inputs
    cryptographic_proof_strength: float  # 0.0 to 1.0
    behavioral_consistency: float  # 0.0 to 1.0
    confidence_stability: float  # 0.0 to 1.0
    artifact_lineage_valid: bool
    gate_history_clean: bool
    telemetry_coherent: bool

    # Decay parameters
    decay_rate: float = 0.1  # Trust decays 10% per hour by default
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, max_age_seconds: int = 3600) -> bool:
        """Check if trust score has expired."""
        age = (datetime.now(timezone.utc) - self.computed_at).total_seconds()
        return age > max_age_seconds

    def compute_decayed_confidence(self) -> float:
        """Compute confidence after time-based decay."""
        elapsed_hours = (datetime.now(timezone.utc) - self.last_activity).total_seconds() / 3600
        decayed = self.confidence * (1 - self.decay_rate) ** elapsed_hours
        return max(0.0, decayed)

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            "identity_id": self.identity_id,
            "trust_level": self.trust_level.value,
            "confidence": self.confidence,
            "computed_at": self.computed_at.isoformat(),
            "cryptographic_proof_strength": self.cryptographic_proof_strength,
            "behavioral_consistency": self.behavioral_consistency,
            "confidence_stability": self.confidence_stability,
            "artifact_lineage_valid": self.artifact_lineage_valid,
            "gate_history_clean": self.gate_history_clean,
            "telemetry_coherent": self.telemetry_coherent
        }


@dataclass
class SecurityArtifact:
    """
    Immutable security artifact for audit trail.

    Every security decision is recorded as an artifact.
    """
    artifact_id: str
    artifact_type: str  # "trust_computation", "access_decision", "anomaly_detection", etc.
    timestamp: datetime
    identity_id: str
    action: SecurityAction

    # Context
    trust_score: Optional[TrustScore]
    authority_band: Optional[AuthorityBand]
    resource_accessed: Optional[str]

    # Decision rationale
    rationale: str
    contributing_factors: Dict[str, float]

    # Cryptographic integrity
    integrity_hash: str = field(init=False)

    def __post_init__(self):
        """Compute integrity hash."""
        content = f"{self.artifact_id}{self.artifact_type}{self.timestamp}{self.identity_id}{self.action.value}{self.rationale}"
        self.integrity_hash = hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify artifact has not been tampered with."""
        content = f"{self.artifact_id}{self.artifact_type}{self.timestamp}{self.identity_id}{self.action.value}{self.rationale}"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.integrity_hash == expected_hash


@dataclass
class SecurityAnomaly:
    """
    Detected security anomaly.

    Anomalies do NOT block directly - they feed into trust computation
    and Murphy Index.
    """
    anomaly_id: str
    anomaly_type: AnomalyType
    detected_at: datetime
    identity_id: str

    # Anomaly details
    severity: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    description: str
    evidence: Dict

    # Impact on trust
    trust_impact: float  # How much to reduce trust (0.0 to 1.0)
    murphy_index_contribution: float  # Contribution to Murphy Index

    # Response
    recommended_action: SecurityAction
    escalation_required: bool


@dataclass
class ExecutionPacketSignature:
    """
    Cryptographic signature for execution packet.

    CRITICAL: Execution packets MUST be signed by Control Plane.
    """
    packet_id: str
    signature: bytes
    algorithm: CryptographicAlgorithm
    signed_at: datetime
    signed_by: str  # Control Plane identity

    # Binding constraints
    time_window_start: datetime
    time_window_end: datetime
    authority_band: AuthorityBand
    target_adapter: str

    # Single-use enforcement
    nonce: str  # Unique nonce prevents replay
    used: bool = False
    used_at: Optional[datetime] = None

    def is_valid(self) -> bool:
        """Check if signature is still valid."""
        now = datetime.now(timezone.utc)

        # Check time window
        if now < self.time_window_start or now > self.time_window_end:
            return False

        # Check single-use
        if self.used:
            return False

        return True

    def mark_used(self) -> None:
        """Mark packet as used (single-use enforcement)."""
        if self.used:
            raise ValueError(f"Packet {self.packet_id} already used at {self.used_at}")

        self.used = True
        self.used_at = datetime.now(timezone.utc)


@dataclass
class AccessRequest:
    """
    Request for access to a resource.

    All access goes through zero-trust evaluation.
    """
    request_id: str
    identity_id: str
    resource: str
    operation: str  # "read", "write", "execute", etc.
    requested_at: datetime

    # Context
    purpose: str  # Why is access needed?
    scope: str  # What data is needed?
    duration: timedelta  # How long is access needed?

    # Trust context
    current_trust_score: Optional[TrustScore] = None
    required_trust_level: TrustLevel = TrustLevel.MEDIUM
    required_authority_band: AuthorityBand = AuthorityBand.MEDIUM


@dataclass
class AccessDecision:
    """
    Decision on an access request.

    Every access decision is logged immutably.
    """
    decision_id: str
    request_id: str
    decision: SecurityAction
    decided_at: datetime

    # Rationale
    trust_score: TrustScore
    authority_granted: Optional[AuthorityBand]
    rationale: str

    # Constraints
    time_bound: Optional[datetime]  # Access expires at this time
    scope_restrictions: List[str]  # What data can be accessed
    rate_limit: Optional[int]  # Max operations per minute

    # Audit
    decided_by: str  # Security Plane component
    artifact: SecurityArtifact


@dataclass
class SecurityTelemetry:
    """
    Security telemetry event.

    Feeds into adaptive defense system.
    """
    telemetry_id: str
    event_type: str
    timestamp: datetime
    identity_id: str

    # Event details
    resource: str
    operation: str
    success: bool

    # Timing information (for anomaly detection)
    duration_ms: float

    # Pattern detection
    call_pattern: List[str]  # Sequence of recent calls
    authority_level: AuthorityBand

    # Metadata (minimized)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class CryptographicKey:
    """
    Cryptographic key with automatic rotation.

    CRITICAL: No long-lived keys exist.
    """
    key_id: str
    key_type: str  # "signing", "encryption", "key_exchange"
    algorithm: CryptographicAlgorithm

    # Key material (encrypted at rest)
    public_key: bytes
    private_key_encrypted: bytes

    # Lifecycle
    created_at: datetime
    expires_at: datetime

    # Scope
    identity_id: str

    # Optional fields with defaults
    rotated: bool = False
    rotation_scheduled_at: Optional[datetime] = None
    capabilities: Set[str] = field(default_factory=set)

    def is_expired(self) -> bool:
        """Check if key has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def time_until_expiry(self) -> timedelta:
        """Get time until key expires."""
        return self.expires_at - datetime.now(timezone.utc)

    def should_rotate(self, rotation_threshold: timedelta = timedelta(minutes=5)) -> bool:
        """Check if key should be rotated."""
        return self.time_until_expiry() < rotation_threshold


@dataclass
class SecurityGate:
    """
    Security gate synthesized by adaptive defense.

    Gates are created in response to detected anomalies.
    """
    gate_id: str
    gate_type: str
    created_at: datetime
    created_by: str  # Security telemetry agent

    # Trigger
    triggered_by_anomaly: str  # Anomaly ID
    anomaly_type: AnomalyType

    # Gate logic
    condition: str  # Condition that must be met
    threshold: float

    # Lifecycle
    active: bool = True
    expires_at: Optional[datetime] = None

    # Impact
    blocks_authority_band: Optional[AuthorityBand] = None
    requires_escalation: bool = False


@dataclass
class SecurityFreeze:
    """
    Security freeze event.

    System freezes on any anomaly - fail closed.
    """
    freeze_id: str
    triggered_at: datetime
    triggered_by: str  # Anomaly ID or security component

    # Freeze scope
    identity_id: Optional[str]  # If None, system-wide freeze
    resource: Optional[str]  # If None, all resources frozen

    # Rationale
    reason: str
    severity: float
    anomalies: List[str]  # Anomaly IDs

    # Resolution
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None


@dataclass
class AuditLogEntry:
    """
    Immutable audit log entry.

    All security events are logged with cryptographic integrity.
    """
    log_id: str
    timestamp: datetime
    event_type: str  # "request", "response", "authentication", "authorization", etc.
    component: str
    operation: str

    # Identity
    identity: Optional[str] = None
    trust_score: float = 0.0

    # Result
    success: bool = True
    error_message: Optional[str] = None

    # Details
    details: Dict[str, Any] = field(default_factory=dict)

    # Immutability
    hash: str = field(default="")

    def __post_init__(self):
        """Compute hash for immutability"""
        if not self.hash:
            import hashlib
            content = f"{self.log_id}{self.timestamp}{self.event_type}{self.component}{self.operation}{self.identity}{self.success}"
            self.hash = hashlib.sha256(content.encode()).hexdigest()
