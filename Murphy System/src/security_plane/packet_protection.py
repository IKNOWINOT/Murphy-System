"""
Security Plane - Phase 7: Execution Packet Protection
=====================================================

Cryptographic protection for execution packets with signature verification,
replay prevention, and integrity validation.

CRITICAL PRINCIPLES:
1. All packets must be cryptographically signed
2. Signatures must be verified before execution
3. Packets cannot be replayed (single-use)
4. Authority levels must be enforced
5. Packet integrity must be validated

Author: Murphy System (MFGC-AI)
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PacketStatus(Enum):
    """Execution packet status"""
    PENDING = "pending"
    VERIFIED = "verified"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class VerificationResult(Enum):
    """Signature verification result"""
    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED = "expired"
    REPLAYED = "replayed"
    INSUFFICIENT_AUTHORITY = "insufficient_authority"
    TAMPERED = "tampered"
    MISSING_SIGNATURE = "missing_signature"


class AuthorityLevel(Enum):
    """Authority levels for execution"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ExecutionPacket:
    """
    Execution packet with cryptographic protection.

    CRITICAL: This is the ONLY way to execute actions in the Murphy System.
    """
    packet_id: str
    principal_id: str
    action: str
    parameters: Dict[str, Any]
    authority_level: AuthorityLevel
    created_at: datetime
    expires_at: datetime
    nonce: str  # Single-use token
    signature: Optional[str] = None
    status: PacketStatus = PacketStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate packet on creation"""
        if not self.packet_id:
            raise ValueError("packet_id is required")
        if not self.principal_id:
            raise ValueError("principal_id is required")
        if not self.action:
            raise ValueError("action is required")
        if not self.nonce:
            raise ValueError("nonce is required")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")

    def is_expired(self) -> bool:
        """Check if packet has expired"""
        return datetime.now(timezone.utc) >= self.expires_at

    def to_signable_dict(self) -> Dict:
        """
        Convert to dictionary for signing.

        Excludes signature and status fields.
        """
        return {
            "packet_id": self.packet_id,
            "principal_id": self.principal_id,
            "action": self.action,
            "parameters": self.parameters,
            "authority_level": self.authority_level.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "nonce": self.nonce,
            "metadata": self.metadata
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        result = self.to_signable_dict()
        result["signature"] = self.signature
        result["status"] = self.status.value
        return result

    def compute_integrity_hash(self) -> str:
        """
        Compute integrity hash of packet.

        Returns:
            SHA-256 hash of packet contents
        """
        signable = json.dumps(self.to_signable_dict(), sort_keys=True)
        return hashlib.sha256(signable.encode()).hexdigest()


@dataclass
class PacketSignature:
    """Cryptographic signature for execution packet"""
    packet_id: str
    signature: str
    algorithm: str
    signed_at: datetime
    signed_by: str
    key_id: str

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "packet_id": self.packet_id,
            "signature": self.signature,
            "algorithm": self.algorithm,
            "signed_at": self.signed_at.isoformat(),
            "signed_by": self.signed_by,
            "key_id": self.key_id
        }


@dataclass
class VerificationRecord:
    """Record of packet verification"""
    packet_id: str
    result: VerificationResult
    verified_at: datetime
    verified_by: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "packet_id": self.packet_id,
            "result": self.result.value,
            "verified_at": self.verified_at.isoformat(),
            "verified_by": self.verified_by,
            "details": self.details
        }


class PacketSigner:
    """
    Signs execution packets with cryptographic signatures.

    Uses HMAC-SHA256 for signing.
    """

    def __init__(self, signing_key: bytes):
        """
        Initialize packet signer.

        Args:
            signing_key: Secret key for signing
        """
        self.signing_key = signing_key
        self.key_id = hashlib.sha256(signing_key).hexdigest()[:16]

    def sign_packet(
        self,
        packet: ExecutionPacket,
        signed_by: str
    ) -> PacketSignature:
        """
        Sign an execution packet.

        Args:
            packet: Execution packet to sign
            signed_by: Identity of signer

        Returns:
            Packet signature
        """
        # Get signable representation
        signable = json.dumps(packet.to_signable_dict(), sort_keys=True)

        # Compute HMAC-SHA256 signature
        signature = hmac.new(
            self.signing_key,
            signable.encode(),
            hashlib.sha256
        ).hexdigest()

        # Update packet
        packet.signature = signature

        # Create signature record
        return PacketSignature(
            packet_id=packet.packet_id,
            signature=signature,
            algorithm="HMAC-SHA256",
            signed_at=datetime.now(timezone.utc),
            signed_by=signed_by,
            key_id=self.key_id
        )

    def verify_signature(
        self,
        packet: ExecutionPacket
    ) -> bool:
        """
        Verify packet signature.

        Args:
            packet: Execution packet to verify

        Returns:
            True if signature is valid
        """
        if not packet.signature:
            return False

        # Get signable representation
        signable = json.dumps(packet.to_signable_dict(), sort_keys=True)

        # Compute expected signature
        expected = hmac.new(
            self.signing_key,
            signable.encode(),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(packet.signature, expected)


class ReplayPrevention:
    """
    Prevents replay attacks by tracking used nonces.

    Each packet can only be executed once.
    """

    def __init__(self, max_age: timedelta = timedelta(hours=24)):
        """
        Initialize replay prevention.

        Args:
            max_age: Maximum age for tracking nonces
        """
        self.max_age = max_age
        self.used_nonces: Dict[str, datetime] = {}

    def check_nonce(self, nonce: str) -> bool:
        """
        Check if nonce has been used.

        Args:
            nonce: Nonce to check

        Returns:
            True if nonce is fresh (not used)
        """
        # Cleanup old nonces
        self._cleanup_old_nonces()

        return nonce not in self.used_nonces

    def mark_nonce_used(self, nonce: str):
        """
        Mark nonce as used.

        Args:
            nonce: Nonce to mark
        """
        self.used_nonces[nonce] = datetime.now(timezone.utc)

    def _cleanup_old_nonces(self):
        """Remove old nonces from tracking"""
        cutoff = datetime.now(timezone.utc) - self.max_age
        self.used_nonces = {
            nonce: timestamp
            for nonce, timestamp in self.used_nonces.items()
            if timestamp >= cutoff
        }

    def generate_nonce(self) -> str:
        """
        Generate a cryptographically secure nonce.

        Returns:
            Random nonce string
        """
        return secrets.token_hex(32)


class AuthorityEnforcer:
    """
    Enforces authority level requirements for packet execution.

    Ensures packets have sufficient authority for their actions.
    """

    # Authority requirements for different action types
    ACTION_REQUIREMENTS = {
        "read": AuthorityLevel.LOW,
        "write": AuthorityLevel.MEDIUM,
        "execute": AuthorityLevel.HIGH,
        "admin": AuthorityLevel.CRITICAL,
        "delete": AuthorityLevel.HIGH,
        "modify": AuthorityLevel.MEDIUM,
        "create": AuthorityLevel.MEDIUM,
    }

    def __init__(self):
        """Initialize authority enforcer"""
        self.custom_requirements: Dict[str, AuthorityLevel] = {}

    def check_authority(
        self,
        packet: ExecutionPacket,
        required_level: Optional[AuthorityLevel] = None
    ) -> bool:
        """
        Check if packet has sufficient authority.

        Args:
            packet: Execution packet
            required_level: Required authority level (optional)

        Returns:
            True if authority is sufficient
        """
        # Determine required level
        if required_level is None:
            required_level = self._get_required_level(packet.action)

        # Check if packet authority is sufficient
        return self._is_sufficient(packet.authority_level, required_level)

    def set_requirement(self, action: str, level: AuthorityLevel):
        """
        Set custom authority requirement for action.

        Args:
            action: Action name
            level: Required authority level
        """
        self.custom_requirements[action] = level

    def _get_required_level(self, action: str) -> AuthorityLevel:
        """Get required authority level for action"""
        # Check custom requirements first
        if action in self.custom_requirements:
            return self.custom_requirements[action]

        # Check default requirements
        for pattern, level in self.ACTION_REQUIREMENTS.items():
            if pattern in action.lower():
                return level

        # Default to MEDIUM
        return AuthorityLevel.MEDIUM

    def _is_sufficient(
        self,
        current: AuthorityLevel,
        required: AuthorityLevel
    ) -> bool:
        """Check if current authority is sufficient"""
        authority_order = [
            AuthorityLevel.NONE,
            AuthorityLevel.LOW,
            AuthorityLevel.MEDIUM,
            AuthorityLevel.HIGH,
            AuthorityLevel.CRITICAL
        ]

        current_idx = authority_order.index(current)
        required_idx = authority_order.index(required)

        return current_idx >= required_idx


class IntegrityValidator:
    """
    Validates packet integrity to detect tampering.

    Uses cryptographic hashing to detect modifications.
    """

    def __init__(self):
        """Initialize integrity validator"""
        self.integrity_hashes: Dict[str, str] = {}

    def compute_hash(self, packet: ExecutionPacket) -> str:
        """
        Compute integrity hash for packet.

        Args:
            packet: Execution packet

        Returns:
            SHA-256 hash
        """
        return packet.compute_integrity_hash()

    def store_hash(self, packet: ExecutionPacket):
        """
        Store integrity hash for packet.

        Args:
            packet: Execution packet
        """
        hash_value = self.compute_hash(packet)
        self.integrity_hashes[packet.packet_id] = hash_value

    def verify_integrity(self, packet: ExecutionPacket) -> bool:
        """
        Verify packet integrity.

        Args:
            packet: Execution packet

        Returns:
            True if integrity is valid
        """
        if packet.packet_id not in self.integrity_hashes:
            return False

        stored_hash = self.integrity_hashes[packet.packet_id]
        current_hash = self.compute_hash(packet)

        return hmac.compare_digest(stored_hash, current_hash)


class PacketProtectionSystem:
    """
    Complete packet protection system.

    Integrates signing, verification, replay prevention, authority enforcement,
    and integrity validation.
    """

    def __init__(
        self,
        signing_key: bytes,
        replay_max_age: timedelta = timedelta(hours=24)
    ):
        """
        Initialize packet protection system.

        Args:
            signing_key: Secret key for signing
            replay_max_age: Maximum age for replay prevention
        """
        self.signer = PacketSigner(signing_key)
        self.replay_prevention = ReplayPrevention(replay_max_age)
        self.authority_enforcer = AuthorityEnforcer()
        self.integrity_validator = IntegrityValidator()
        self.verification_log: List[VerificationRecord] = []

    def create_packet(
        self,
        principal_id: str,
        action: str,
        parameters: Dict[str, Any],
        authority_level: AuthorityLevel,
        ttl: timedelta = timedelta(minutes=5)
    ) -> ExecutionPacket:
        """
        Create a new execution packet.

        Args:
            principal_id: Principal creating the packet
            action: Action to execute
            parameters: Action parameters
            authority_level: Authority level
            ttl: Time-to-live

        Returns:
            Created execution packet
        """
        now = datetime.now(timezone.utc)

        packet = ExecutionPacket(
            packet_id=secrets.token_hex(16),
            principal_id=principal_id,
            action=action,
            parameters=parameters,
            authority_level=authority_level,
            created_at=now,
            expires_at=now + ttl,
            nonce=self.replay_prevention.generate_nonce()
        )

        # Store integrity hash
        self.integrity_validator.store_hash(packet)

        return packet

    def sign_packet(
        self,
        packet: ExecutionPacket,
        signed_by: str
    ) -> PacketSignature:
        """
        Sign an execution packet.

        Args:
            packet: Execution packet
            signed_by: Identity of signer

        Returns:
            Packet signature
        """
        return self.signer.sign_packet(packet, signed_by)

    def verify_packet(
        self,
        packet: ExecutionPacket,
        verified_by: str,
        required_authority: Optional[AuthorityLevel] = None
    ) -> VerificationRecord:
        """
        Verify an execution packet.

        Performs all security checks:
        1. Signature verification
        2. Expiration check
        3. Replay prevention
        4. Authority enforcement
        5. Integrity validation

        Args:
            packet: Execution packet to verify
            verified_by: Identity of verifier
            required_authority: Required authority level (optional)

        Returns:
            Verification record
        """
        details = {}

        # Check signature
        if not packet.signature:
            result = VerificationResult.MISSING_SIGNATURE
            details["reason"] = "Packet has no signature"

        elif not self.signer.verify_signature(packet):
            result = VerificationResult.INVALID_SIGNATURE
            details["reason"] = "Signature verification failed"

        # Check expiration
        elif packet.is_expired():
            result = VerificationResult.EXPIRED
            details["reason"] = "Packet has expired"
            details["expired_at"] = packet.expires_at.isoformat()

        # Check replay
        elif not self.replay_prevention.check_nonce(packet.nonce):
            result = VerificationResult.REPLAYED
            details["reason"] = "Nonce has already been used"

        # Check authority
        elif not self.authority_enforcer.check_authority(packet, required_authority):
            result = VerificationResult.INSUFFICIENT_AUTHORITY
            details["reason"] = "Insufficient authority level"
            details["packet_authority"] = packet.authority_level.value
            if required_authority:
                details["required_authority"] = required_authority.value

        # Check integrity
        elif not self.integrity_validator.verify_integrity(packet):
            result = VerificationResult.TAMPERED
            details["reason"] = "Packet integrity check failed"

        # All checks passed
        else:
            result = VerificationResult.VALID
            details["checks_passed"] = [
                "signature",
                "expiration",
                "replay",
                "authority",
                "integrity"
            ]

            # Mark nonce as used
            self.replay_prevention.mark_nonce_used(packet.nonce)

            # Update packet status
            packet.status = PacketStatus.VERIFIED

        # Create verification record
        record = VerificationRecord(
            packet_id=packet.packet_id,
            result=result,
            verified_at=datetime.now(timezone.utc),
            verified_by=verified_by,
            details=details
        )

        # Log verification
        self.verification_log.append(record)

        return record

    def get_verification_history(
        self,
        packet_id: Optional[str] = None
    ) -> List[VerificationRecord]:
        """
        Get verification history.

        Args:
            packet_id: Optional packet ID to filter by

        Returns:
            List of verification records
        """
        if packet_id:
            return [r for r in self.verification_log if r.packet_id == packet_id]
        return self.verification_log


@dataclass
class PacketProtectionStatistics:
    """Statistics for packet protection"""
    total_packets_created: int = 0
    total_packets_signed: int = 0
    total_verifications: int = 0
    successful_verifications: int = 0
    failed_verifications: int = 0
    replay_attempts_blocked: int = 0
    expired_packets_rejected: int = 0
    insufficient_authority_rejected: int = 0
    tampered_packets_detected: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "total_packets_created": self.total_packets_created,
            "total_packets_signed": self.total_packets_signed,
            "total_verifications": self.total_verifications,
            "successful_verifications": self.successful_verifications,
            "failed_verifications": self.failed_verifications,
            "replay_attempts_blocked": self.replay_attempts_blocked,
            "expired_packets_rejected": self.expired_packets_rejected,
            "insufficient_authority_rejected": self.insufficient_authority_rejected,
            "tampered_packets_detected": self.tampered_packets_detected
        }
