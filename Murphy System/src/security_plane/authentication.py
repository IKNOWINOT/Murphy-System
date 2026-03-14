"""
Authentication & Identity System

Implements human-easy and machine authentication for the Security Plane.

CRITICAL PRINCIPLES:
1. Humans authenticate via passkeys/hardware keys (FIDO2)
2. Machines authenticate via mTLS (mutual TLS)
3. No passwords, no API keys, no manual secrets
4. Contextual verification (time, location, task)
5. Intent confirmation (semantic intent match)

Security UX Principle:
> If a human must copy a secret, the system failed.

Components:
- HumanAuthenticator: Passkey/biometric authentication
- MachineAuthenticator: mTLS authentication
- IdentityVerifier: Identity verification and validation
- ContextualVerifier: Context-based verification
- IntentConfirmer: Semantic intent matching
"""

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .cryptography import CryptographicAlgorithm, CryptographicPrimitives, KeyManager
from .schemas import AuthorityBand, SecurityAction, SecurityArtifact, TrustLevel, TrustScore

logger = logging.getLogger(__name__)


class AuthenticationType(Enum):
    """Type of authentication."""
    PASSKEY = "passkey"
    BIOMETRIC = "biometric"
    HARDWARE_KEY = "hardware_key"
    MTLS = "mtls"
    CONTEXTUAL = "contextual"
    INTENT = "intent"


class IdentityType(Enum):
    """Type of identity."""
    HUMAN = "human"
    SERVICE = "service"
    AGENT = "agent"
    DEVICE = "device"


class BiometricType(Enum):
    """Type of biometric authentication."""
    FINGERPRINT = "fingerprint"
    FACE = "face"
    IRIS = "iris"
    VOICE = "voice"


@dataclass
class Identity:
    """
    Identity in the system.

    Can be human, service, agent, or device.
    """
    identity_id: str
    identity_type: IdentityType
    display_name: str
    created_at: datetime

    # Authentication methods
    allowed_auth_methods: List[AuthenticationType]

    # Trust context
    trust_score: Optional[TrustScore] = None
    authority_band: AuthorityBand = AuthorityBand.NONE

    # Metadata
    metadata: Dict[str, str] = field(default_factory=dict)

    # Status
    active: bool = True
    suspended: bool = False
    suspended_reason: Optional[str] = None


@dataclass
class AuthenticationCredential:
    """
    Authentication credential for an identity.

    CRITICAL: No passwords, no long-lived secrets.
    """
    credential_id: str
    identity_id: str
    credential_type: AuthenticationType

    # Credential data (encrypted)
    public_key: Optional[bytes] = None
    credential_data_encrypted: Optional[bytes] = None

    # Lifecycle
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    use_count: int = 0

    # Device binding (for passkeys)
    device_id: Optional[str] = None
    device_name: Optional[str] = None

    # Status
    active: bool = True
    revoked: bool = False
    revoked_at: Optional[datetime] = None


@dataclass
class AuthenticationAttempt:
    """Record of an authentication attempt."""
    attempt_id: str
    identity_id: str
    auth_type: AuthenticationType
    timestamp: datetime

    # Result
    success: bool
    failure_reason: Optional[str] = None

    # Context
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None

    # Trust impact
    trust_score_before: Optional[float] = None
    trust_score_after: Optional[float] = None


@dataclass
class AuthenticationSession:
    """
    Authentication session.

    Short-lived, automatically expires.
    """
    session_id: str
    identity_id: str
    auth_type: AuthenticationType

    # Lifecycle
    created_at: datetime
    expires_at: datetime
    last_activity: datetime

    # Session token (cryptographically secure)
    session_token: str

    # Trust context
    trust_score: TrustScore
    authority_band: AuthorityBand

    # Status
    active: bool = True
    terminated: bool = False
    termination_reason: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def is_idle(self, idle_timeout: timedelta = timedelta(minutes=15)) -> bool:
        """Check if session is idle."""
        return datetime.now(timezone.utc) - self.last_activity > idle_timeout

    def refresh(self) -> None:
        """Refresh session activity."""
        self.last_activity = datetime.now(timezone.utc)


@dataclass
class ContextualVerification:
    """
    Contextual verification data.

    Verifies authentication based on context (time, location, task).
    """
    verification_id: str
    identity_id: str
    timestamp: datetime

    # Context factors
    time_of_day: str  # "business_hours", "after_hours", "weekend"
    location: Optional[str]  # Geographic location
    device_id: Optional[str]  # Device identifier
    network: Optional[str]  # Network identifier
    task: Optional[str]  # Task being performed

    # Verification result
    verified: bool
    confidence: float  # 0.0 to 1.0
    anomalies: List[str] = field(default_factory=list)


@dataclass
class IntentConfirmation:
    """
    Intent confirmation for high-risk operations.

    Ensures user understands what they're authorizing.
    """
    confirmation_id: str
    identity_id: str
    timestamp: datetime

    # Intent
    operation: str  # What operation is being performed
    description: str  # Human-readable description
    risk_level: str  # "low", "medium", "high", "critical"

    # Confirmation
    confirmed: bool
    confirmation_method: str  # "explicit", "biometric", "hardware_key"

    # Semantic match
    user_understanding: Optional[str] = None  # What user thinks they're doing
    semantic_match: Optional[float] = None  # 0.0 to 1.0


class HumanAuthenticator:
    """
    Authenticates humans using passkeys, biometrics, or hardware keys.

    CRITICAL: No passwords, no manual secrets.
    """

    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self._credentials: Dict[str, AuthenticationCredential] = {}
        self._sessions: Dict[str, AuthenticationSession] = {}
        self._attempts: List[AuthenticationAttempt] = []

    def register_passkey(
        self,
        identity_id: str,
        public_key: bytes,
        device_id: str,
        device_name: str
    ) -> AuthenticationCredential:
        """
        Register passkey for identity.

        Passkeys are FIDO2-compliant, device-bound credentials.
        """
        credential_id = f"passkey-{secrets.token_hex(16)}"

        credential = AuthenticationCredential(
            credential_id=credential_id,
            identity_id=identity_id,
            credential_type=AuthenticationType.PASSKEY,
            public_key=public_key,
            device_id=device_id,
            device_name=device_name,
            created_at=datetime.now(timezone.utc),
            expires_at=None,  # Passkeys don't expire
            active=True
        )

        self._credentials[credential_id] = credential
        return credential

    def register_biometric(
        self,
        identity_id: str,
        biometric_type: BiometricType,
        biometric_template_encrypted: bytes,
        device_id: str
    ) -> AuthenticationCredential:
        """
        Register biometric for identity.

        Biometric templates are encrypted and device-bound.
        """
        credential_id = f"biometric-{secrets.token_hex(16)}"

        credential = AuthenticationCredential(
            credential_id=credential_id,
            identity_id=identity_id,
            credential_type=AuthenticationType.BIOMETRIC,
            credential_data_encrypted=biometric_template_encrypted,
            device_id=device_id,
            created_at=datetime.now(timezone.utc),
            expires_at=None,  # Biometrics don't expire
            active=True
        )

        self._credentials[credential_id] = credential
        return credential

    def authenticate_passkey(
        self,
        identity_id: str,
        challenge: bytes,
        signature: bytes,
        credential_id: str
    ) -> Tuple[bool, Optional[AuthenticationSession]]:
        """
        Authenticate using passkey.

        FIDO2 challenge-response authentication.
        """
        # Get credential
        credential = self._credentials.get(credential_id)
        if not credential or credential.identity_id != identity_id:
            self._record_attempt(identity_id, AuthenticationType.PASSKEY, False, "Invalid credential")
            return False, None

        if not credential.active or credential.revoked:
            self._record_attempt(identity_id, AuthenticationType.PASSKEY, False, "Credential revoked")
            return False, None

        # Verify signature (simulated FIDO2 verification)
        # In production: Use proper FIDO2 library
        expected_signature = CryptographicPrimitives.hash_data(
            challenge + credential.public_key
        )

        if not CryptographicPrimitives.constant_time_compare(signature, expected_signature):
            self._record_attempt(identity_id, AuthenticationType.PASSKEY, False, "Invalid signature")
            return False, None

        # Update credential
        credential.last_used = datetime.now(timezone.utc)
        credential.use_count += 1

        # Create session
        session = self._create_session(
            identity_id,
            AuthenticationType.PASSKEY,
            trust_level=TrustLevel.HIGH
        )

        self._record_attempt(identity_id, AuthenticationType.PASSKEY, True)
        return True, session

    def authenticate_biometric(
        self,
        identity_id: str,
        biometric_data: bytes,
        credential_id: str
    ) -> Tuple[bool, Optional[AuthenticationSession]]:
        """
        Authenticate using biometric.

        Biometric matching is done on-device.
        """
        # Get credential
        credential = self._credentials.get(credential_id)
        if not credential or credential.identity_id != identity_id:
            self._record_attempt(identity_id, AuthenticationType.BIOMETRIC, False, "Invalid credential")
            return False, None

        if not credential.active or credential.revoked:
            self._record_attempt(identity_id, AuthenticationType.BIOMETRIC, False, "Credential revoked")
            return False, None

        # Verify biometric (simulated)
        # In production: Biometric matching done on secure hardware
        biometric_hash = CryptographicPrimitives.hash_data(biometric_data)

        # Simulated match (in reality, this would be fuzzy matching)
        if len(biometric_hash) < 32:
            self._record_attempt(identity_id, AuthenticationType.BIOMETRIC, False, "Biometric mismatch")
            return False, None

        # Update credential
        credential.last_used = datetime.now(timezone.utc)
        credential.use_count += 1

        # Create session
        session = self._create_session(
            identity_id,
            AuthenticationType.BIOMETRIC,
            trust_level=TrustLevel.HIGH
        )

        self._record_attempt(identity_id, AuthenticationType.BIOMETRIC, True)
        return True, session

    def _create_session(
        self,
        identity_id: str,
        auth_type: AuthenticationType,
        trust_level: TrustLevel = TrustLevel.MEDIUM,
        session_duration: timedelta = timedelta(hours=8)
    ) -> AuthenticationSession:
        """Create authentication session."""
        session_id = f"session-{secrets.token_hex(16)}"
        session_token = secrets.token_urlsafe(32)

        now = datetime.now(timezone.utc)
        expires = now + session_duration

        # Create trust score
        trust_score = TrustScore(
            identity_id=identity_id,
            trust_level=trust_level,
            confidence=0.9,
            computed_at=now,
            cryptographic_proof_strength=1.0,
            behavioral_consistency=0.9,
            confidence_stability=0.9,
            artifact_lineage_valid=True,
            gate_history_clean=True,
            telemetry_coherent=True
        )

        session = AuthenticationSession(
            session_id=session_id,
            identity_id=identity_id,
            auth_type=auth_type,
            created_at=now,
            expires_at=expires,
            last_activity=now,
            session_token=session_token,
            trust_score=trust_score,
            authority_band=AuthorityBand.MEDIUM,
            active=True
        )

        self._sessions[session_id] = session
        return session

    def _record_attempt(
        self,
        identity_id: str,
        auth_type: AuthenticationType,
        success: bool,
        failure_reason: Optional[str] = None
    ) -> None:
        """Record authentication attempt."""
        attempt = AuthenticationAttempt(
            attempt_id=f"attempt-{secrets.token_hex(8)}",
            identity_id=identity_id,
            auth_type=auth_type,
            timestamp=datetime.now(timezone.utc),
            success=success,
            failure_reason=failure_reason
        )

        capped_append(self._attempts, attempt)

    def get_session(self, session_id: str) -> Optional[AuthenticationSession]:
        """Get session by ID."""
        session = self._sessions.get(session_id)

        if not session:
            return None

        # Check expiry
        if session.is_expired():
            session.active = False
            session.terminated = True
            session.termination_reason = "expired"
            return None

        # Check idle timeout
        if session.is_idle():
            session.active = False
            session.terminated = True
            session.termination_reason = "idle_timeout"
            return None

        return session

    def terminate_session(self, session_id: str, reason: str = "user_logout") -> bool:
        """Terminate session."""
        session = self._sessions.get(session_id)

        if not session:
            return False

        session.active = False
        session.terminated = True
        session.termination_reason = reason

        return True

    def revoke_credential(self, credential_id: str, reason: str) -> bool:
        """Revoke credential."""
        credential = self._credentials.get(credential_id)

        if not credential:
            return False

        credential.active = False
        credential.revoked = True
        credential.revoked_at = datetime.now(timezone.utc)

        return True


class MachineAuthenticator:
    """
    Authenticates machines (services, agents, devices) using mTLS.

    CRITICAL: Mutual TLS with short-lived certificates.
    """

    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self._certificates: Dict[str, AuthenticationCredential] = {}
        self._sessions: Dict[str, AuthenticationSession] = {}

    def issue_certificate(
        self,
        identity_id: str,
        identity_type: IdentityType,
        capabilities: List[str],
        certificate_duration: timedelta = timedelta(minutes=10)
    ) -> AuthenticationCredential:
        """
        Issue short-lived certificate for machine authentication.

        Certificates expire in minutes.
        """
        # Generate key pair
        key = self.key_manager.generate_key(
            identity_id=identity_id,
            key_type="mtls",
            algorithm=CryptographicAlgorithm.HYBRID,
            capabilities=set(capabilities)
        )

        credential_id = f"cert-{secrets.token_hex(16)}"

        now = datetime.now(timezone.utc)
        expires = now + certificate_duration

        credential = AuthenticationCredential(
            credential_id=credential_id,
            identity_id=identity_id,
            credential_type=AuthenticationType.MTLS,
            public_key=key.public_key,
            created_at=now,
            expires_at=expires,
            active=True
        )

        self._certificates[credential_id] = credential
        return credential

    def authenticate_mtls(
        self,
        identity_id: str,
        client_certificate: bytes,
        credential_id: str
    ) -> Tuple[bool, Optional[AuthenticationSession]]:
        """
        Authenticate using mTLS.

        Verifies client certificate.
        """
        # Get credential
        credential = self._certificates.get(credential_id)
        if not credential or credential.identity_id != identity_id:
            return False, None

        if not credential.active or credential.revoked:
            return False, None

        # Check expiry
        if credential.expires_at and datetime.now(timezone.utc) > credential.expires_at:
            return False, None

        # Verify certificate (simulated)
        # In production: Use proper TLS certificate verification
        cert_hash = CryptographicPrimitives.hash_data(client_certificate)
        expected_hash = CryptographicPrimitives.hash_data(credential.public_key)

        if not CryptographicPrimitives.constant_time_compare(cert_hash, expected_hash):
            return False, None

        # Update credential
        credential.last_used = datetime.now(timezone.utc)
        credential.use_count += 1

        # Create session
        session = self._create_session(
            identity_id,
            AuthenticationType.MTLS,
            trust_level=TrustLevel.HIGH
        )

        return True, session

    def _create_session(
        self,
        identity_id: str,
        auth_type: AuthenticationType,
        trust_level: TrustLevel = TrustLevel.HIGH,
        session_duration: timedelta = timedelta(minutes=10)
    ) -> AuthenticationSession:
        """Create machine authentication session."""
        session_id = f"session-{secrets.token_hex(16)}"
        session_token = secrets.token_urlsafe(32)

        now = datetime.now(timezone.utc)
        expires = now + session_duration

        # Create trust score
        trust_score = TrustScore(
            identity_id=identity_id,
            trust_level=trust_level,
            confidence=0.95,
            computed_at=now,
            cryptographic_proof_strength=1.0,
            behavioral_consistency=1.0,
            confidence_stability=1.0,
            artifact_lineage_valid=True,
            gate_history_clean=True,
            telemetry_coherent=True
        )

        session = AuthenticationSession(
            session_id=session_id,
            identity_id=identity_id,
            auth_type=auth_type,
            created_at=now,
            expires_at=expires,
            last_activity=now,
            session_token=session_token,
            trust_score=trust_score,
            authority_band=AuthorityBand.HIGH,
            active=True
        )

        self._sessions[session_id] = session
        return session


class IdentityVerifier:
    """
    Verifies identity and maintains identity registry.
    """

    def __init__(self):
        self._identities: Dict[str, Identity] = {}

    def register_identity(
        self,
        identity_id: str,
        identity_type: IdentityType,
        display_name: str,
        allowed_auth_methods: List[AuthenticationType]
    ) -> Identity:
        """Register new identity."""
        identity = Identity(
            identity_id=identity_id,
            identity_type=identity_type,
            display_name=display_name,
            created_at=datetime.now(timezone.utc),
            allowed_auth_methods=allowed_auth_methods,
            active=True
        )

        self._identities[identity_id] = identity
        return identity

    def get_identity(self, identity_id: str) -> Optional[Identity]:
        """Get identity by ID."""
        return self._identities.get(identity_id)

    def verify_identity(self, identity_id: str) -> bool:
        """Verify identity exists and is active."""
        identity = self._identities.get(identity_id)

        if not identity:
            return False

        if not identity.active or identity.suspended:
            return False

        return True

    def suspend_identity(self, identity_id: str, reason: str) -> bool:
        """Suspend identity."""
        identity = self._identities.get(identity_id)

        if not identity:
            return False

        identity.suspended = True
        identity.suspended_reason = reason

        return True

    def reactivate_identity(self, identity_id: str) -> bool:
        """Reactivate suspended identity."""
        identity = self._identities.get(identity_id)

        if not identity:
            return False

        identity.suspended = False
        identity.suspended_reason = None

        return True


class ContextualVerifier:
    """
    Verifies authentication based on context.

    Context factors: time, location, device, network, task.
    """

    def __init__(
        self,
        known_locations: Optional[set] = None,
        known_devices: Optional[dict] = None,
        private_networks: Optional[list] = None,
    ):
        self._verifications: List[ContextualVerification] = []
        # Registry of trusted location identifiers (None = not configured)
        self._known_locations: Optional[set] = known_locations
        # Map of device_id -> fingerprint metadata (None = not configured)
        self._known_devices: Optional[dict] = known_devices
        # List of known private CIDR prefixes — None means "not configured, use heuristic"
        self._private_networks: Optional[list] = private_networks
        # Default CIDR prefixes used when a custom list is explicitly provided
        self._default_private_prefixes: list = [
            "10.", "172.16.", "172.17.", "172.18.", "172.19.",
            "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
            "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
            "172.30.", "172.31.", "192.168.", "127.",
        ]

    def register_location(self, location_id: str) -> None:
        """Add a location identifier to the trusted-locations registry."""
        if self._known_locations is None:
            self._known_locations = set()
        self._known_locations.add(location_id)

    def register_device(self, device_id: str, fingerprint: dict) -> None:
        """Add a device to the known-device fingerprint store."""
        if self._known_devices is None:
            self._known_devices = {}
        self._known_devices[device_id] = fingerprint

    def _is_private_network(self, network: str) -> bool:
        """Return True if the network identifier matches a private IP range prefix."""
        prefixes = self._private_networks if self._private_networks is not None else self._default_private_prefixes
        return any(network.startswith(prefix) for prefix in prefixes)

    def verify_context(
        self,
        identity_id: str,
        time_of_day: str,
        location: Optional[str] = None,
        device_id: Optional[str] = None,
        network: Optional[str] = None,
        task: Optional[str] = None
    ) -> ContextualVerification:
        """
        Verify authentication context.

        Returns verification with confidence score.
        """
        verification_id = f"ctx-{secrets.token_hex(8)}"
        anomalies = []
        confidence = 1.0

        # Check time of day
        if time_of_day == "after_hours":
            anomalies.append("Authentication during after hours")
            confidence *= 0.8
        elif time_of_day == "weekend":
            anomalies.append("Authentication during weekend")
            confidence *= 0.9

        # Check location against known-locations registry
        if location is not None:
            if self._known_locations is not None and location not in self._known_locations:
                anomalies.append(f"Authentication from unknown location: {location}")
                confidence *= 0.7
            elif self._known_locations is None and location.startswith("unknown"):
                # Fallback heuristic when no registry is configured
                anomalies.append("Authentication from unknown location")
                confidence *= 0.7

        # Check device against fingerprint store
        if device_id is not None:
            if self._known_devices is not None and device_id not in self._known_devices:
                anomalies.append(f"Authentication from unrecognised device: {device_id}")
                confidence *= 0.8
            elif self._known_devices is None and device_id.startswith("new"):
                # Fallback heuristic when no device store is configured
                anomalies.append("Authentication from new device")
                confidence *= 0.8

        # Check network — private ranges are trusted; public ranges reduce confidence
        if network is not None:
            if self._private_networks is not None:
                # Custom registry in use — use CIDR prefix matching
                if self._is_private_network(network):
                    pass  # private network — no penalty
                else:
                    anomalies.append(f"Authentication from public/external network: {network}")
                    confidence *= 0.9
            elif network.startswith("public"):
                # Fallback heuristic when no custom registry configured
                anomalies.append("Authentication from public network")
                confidence *= 0.9

        verified = confidence >= 0.7

        verification = ContextualVerification(
            verification_id=verification_id,
            identity_id=identity_id,
            timestamp=datetime.now(timezone.utc),
            time_of_day=time_of_day,
            location=location,
            device_id=device_id,
            network=network,
            task=task,
            verified=verified,
            confidence=confidence,
            anomalies=anomalies
        )

        capped_append(self._verifications, verification)
        return verification


class IntentConfirmer:
    """
    Confirms user intent for high-risk operations.

    Ensures user understands what they're authorizing.
    """

    def __init__(self):
        self._confirmations: List[IntentConfirmation] = []

    def request_confirmation(
        self,
        identity_id: str,
        operation: str,
        description: str,
        risk_level: str
    ) -> IntentConfirmation:
        """
        Request intent confirmation from user.

        Returns confirmation object (confirmed=False initially).
        """
        confirmation_id = f"intent-{secrets.token_hex(8)}"

        confirmation = IntentConfirmation(
            confirmation_id=confirmation_id,
            identity_id=identity_id,
            timestamp=datetime.now(timezone.utc),
            operation=operation,
            description=description,
            risk_level=risk_level,
            confirmed=False,
            confirmation_method="pending"
        )

        capped_append(self._confirmations, confirmation)
        return confirmation

    def confirm_intent(
        self,
        confirmation_id: str,
        confirmation_method: str,
        user_understanding: Optional[str] = None
    ) -> bool:
        """
        Confirm user intent.

        Optionally checks semantic match between operation and user understanding.
        """
        confirmation = None
        for c in self._confirmations:
            if c.confirmation_id == confirmation_id:
                confirmation = c
                break

        if not confirmation:
            return False

        # Check semantic match if provided
        if user_understanding:
            semantic_match = self._compute_semantic_match(
                confirmation.description,
                user_understanding
            )
            confirmation.semantic_match = semantic_match
            confirmation.user_understanding = user_understanding

            # Require high semantic match for confirmation
            if semantic_match < 0.8:
                return False

        confirmation.confirmed = True
        confirmation.confirmation_method = confirmation_method

        return True

    def _compute_semantic_match(self, description: str, understanding: str) -> float:
        """
        Compute semantic match between description and user understanding using
        TF-IDF weighted cosine similarity.

        Returns a score in [0.0, 1.0] — higher is a closer match.
        """
        import math

        def tokenize(text: str) -> List[str]:
            return text.lower().split()

        desc_tokens = tokenize(description)
        under_tokens = tokenize(understanding)

        if not desc_tokens or not under_tokens:
            return 0.0

        corpus = [desc_tokens, under_tokens]
        vocab = set(desc_tokens) | set(under_tokens)

        def term_freq(tokens: List[str], term: str) -> float:
            count = tokens.count(term)
            return count / (len(tokens) or 1)

        def inv_doc_freq(term: str) -> float:
            docs_containing = sum(1 for doc in corpus if term in doc)
            return math.log((1 + len(corpus)) / (1 + docs_containing)) + 1.0

        def tfidf_vector(tokens: List[str]) -> Dict[str, float]:
            return {term: term_freq(tokens, term) * inv_doc_freq(term) for term in vocab}

        vec_desc = tfidf_vector(desc_tokens)
        vec_under = tfidf_vector(under_tokens)

        dot = sum(vec_desc[t] * vec_under[t] for t in vocab)
        norm_d = math.sqrt(sum(v * v for v in vec_desc.values()))
        norm_u = math.sqrt(sum(v * v for v in vec_under.values()))

        if norm_d == 0.0 or norm_u == 0.0:
            return 0.0

        return dot / (norm_d * norm_u)
