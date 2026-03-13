"""
Security Plane for Murphy System (MFGC-AI)

The Security Plane wraps all Murphy System components with:
- Zero-trust access model
- Post-quantum cryptography
- Human-easy authentication
- Machine authentication (mTLS)
- Adaptive defense
- Execution packet protection
- Data leak prevention
- Anti-surveillance measures
- Fail-safe behavior

Security Principles:
1. Security is additive, orthogonal, and absolute
2. Control Plane supremacy preserved
3. No hidden execution paths
4. Fail closed always
5. Trust is continuously re-computed
6. Authority decays automatically

Components:
- schemas: Core security data models
- cryptography: Post-quantum cryptographic primitives
- authentication: Human and machine authentication
- access_control: Zero-trust access model
- hardening: Entrance and exit hardening
- adaptive_defense: Security telemetry and anomaly detection
- packet_protection: Execution packet signing and verification
- data_protection: Data leak prevention
- anti_surveillance: Anti-tracking and anti-fingerprinting
"""

__version__ = "1.0.0"
__author__ = "InonI LLC"

# Import schemas
# Import authentication
from .authentication import (
    AuthenticationCredential,
    AuthenticationSession,
    AuthenticationType,
    BiometricType,
    ContextualVerification,
    ContextualVerifier,
    HumanAuthenticator,
    Identity,
    IdentityType,
    IdentityVerifier,
    IntentConfirmation,
    IntentConfirmer,
    MachineAuthenticator,
)

# Import security enhancements
from .authorization_enhancer import (
    AuthorizationDecision,
    AuthorizationEnhancer,
    AuthorizationRequest,
    OwnershipVerificationResult,
    SessionContext,
)
from .bot_anomaly_detector import (
    AnomalyAlert,
    BotAnomalyDetector,
)
from .bot_identity_verifier import (
    BotIdentity,
    BotIdentityVerifier,
    IdentityStatus,
    SignedMessage,
)
from .bot_resource_quotas import (
    BotQuota,
    BotResourceQuotaManager,
    BotUsage,
    QuotaStatus,
    QuotaViolation,
    SwarmQuota,
    ViolationType,
)

# Import cryptography
from .cryptography import (
    ClassicalCryptography,
    CryptographicPrimitives,
    HashAlgorithm,
    HybridCryptography,
    KeyManager,
    KeyPair,
    PacketSigner,
    PostQuantumCryptography,
    SignatureResult,
    VerificationResult,
)
from .log_sanitizer import LogSanitizer, PIIPattern, PIIType, SanitizationResult
from .schemas import (
    AccessDecision,
    AccessRequest,
    AnomalyType,
    AuthorityBand,
    CryptographicAlgorithm,
    CryptographicKey,
    ExecutionPacketSignature,
    SecurityAction,
    SecurityAnomaly,
    SecurityArtifact,
    SecurityFreeze,
    SecurityGate,
    SecurityTelemetry,
    TrustLevel,
    TrustScore,
)
from .security_dashboard import (
    CorrelatedEventGroup,
    EscalationLevel,
    SecurityDashboard,
    SecurityEvent,
    SecurityEventType,
    SecurityReport,
)
from .swarm_communication_monitor import (
    CommunicationAlert,
    CommunicationIncident,
    SwarmCommunicationMonitor,
    SwarmMessage,
)

__all__ = [
    # Schemas
    "TrustScore",
    "TrustLevel",
    "SecurityArtifact",
    "SecurityAction",
    "SecurityAnomaly",
    "AnomalyType",
    "ExecutionPacketSignature",
    "CryptographicAlgorithm",
    "AuthorityBand",
    "AccessRequest",
    "AccessDecision",
    "SecurityTelemetry",
    "CryptographicKey",
    "SecurityGate",
    "SecurityFreeze",

    # Cryptography
    "CryptographicPrimitives",
    "HashAlgorithm",
    "ClassicalCryptography",
    "PostQuantumCryptography",
    "HybridCryptography",
    "KeyManager",
    "PacketSigner",
    "KeyPair",
    "SignatureResult",
    "VerificationResult",

    # Authentication
    "HumanAuthenticator",
    "MachineAuthenticator",
    "IdentityVerifier",
    "ContextualVerifier",
    "IntentConfirmer",
    "Identity",
    "IdentityType",
    "AuthenticationType",
    "BiometricType",
    "AuthenticationCredential",
    "AuthenticationSession",
    "ContextualVerification",
    "IntentConfirmation",

    # Security Enhancements
    "AuthorizationEnhancer",
    "AuthorizationRequest",
    "AuthorizationDecision",
    "SessionContext",
    "OwnershipVerificationResult",
    "LogSanitizer",
    "PIIType",
    "PIIPattern",
    "SanitizationResult",
    "BotResourceQuotaManager",
    "BotQuota",
    "BotUsage",
    "SwarmQuota",
    "QuotaViolation",
    "QuotaStatus",
    "ViolationType",
    "SwarmCommunicationMonitor",
    "SwarmMessage",
    "CommunicationIncident",
    "CommunicationAlert",
    "BotIdentityVerifier",
    "BotIdentity",
    "SignedMessage",
    "IdentityStatus",
    "BotAnomalyDetector",
    "AnomalyAlert",
    "SecurityDashboard",
    "SecurityEvent",
    "SecurityEventType",
    "EscalationLevel",
    "CorrelatedEventGroup",
    "SecurityReport",
]
