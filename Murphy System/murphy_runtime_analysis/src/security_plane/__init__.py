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
from .schemas import (
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

# Import cryptography
from .cryptography import (
    CryptographicPrimitives,
    HashAlgorithm,
    ClassicalCryptography,
    PostQuantumCryptography,
    HybridCryptography,
    KeyManager,
    PacketSigner,
    KeyPair,
    SignatureResult,
    VerificationResult
)

# Import authentication
from .authentication import (
    HumanAuthenticator,
    MachineAuthenticator,
    IdentityVerifier,
    ContextualVerifier,
    IntentConfirmer,
    Identity,
    IdentityType,
    AuthenticationType,
    BiometricType,
    AuthenticationCredential,
    AuthenticationSession,
    ContextualVerification,
    IntentConfirmation
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
]