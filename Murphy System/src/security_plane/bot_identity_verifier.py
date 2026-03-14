"""Cryptographic identity verification for bots in the Murphy System."""
# Copyright © 2020 Inoni Limited Liability Company

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class IdentityStatus(str, Enum):
    """Identity status (str subclass)."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class VerificationResult(str, Enum):
    """Verification result (str subclass)."""
    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    UNKNOWN_BOT = "unknown_bot"
    REVOKED_IDENTITY = "revoked_identity"
    EXPIRED_IDENTITY = "expired_identity"


@dataclass
class BotIdentity:
    """Bot identity."""
    bot_id: str
    tenant_id: str
    signing_key: str
    status: IdentityStatus = IdentityStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


@dataclass
class SignedMessage:
    """Signed message."""
    message_id: str
    from_bot: str
    to_bot: str
    payload_hash: str
    signature: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_bot": self.from_bot,
            "to_bot": self.to_bot,
            "payload_hash": self.payload_hash,
            "signature": self.signature,
            "timestamp": self.timestamp.isoformat(),
        }


class BotIdentityVerifier:
    """Manages bot identities and message verification."""

    def __init__(
        self,
        key_length: int = 32,
        default_ttl_days: int = 365,
        max_identities: int = 10000,
    ) -> None:
        self._key_length = key_length
        self._default_ttl_days = default_ttl_days
        self._max_identities = max_identities
        self._identities: Dict[str, BotIdentity] = {}
        self._lock = threading.Lock()
        self._revocation_log: List[Dict[str, Any]] = []
        logger.info(
            "BotIdentityVerifier initialised (key_length=%d, ttl=%dd, max=%d)",
            key_length,
            default_ttl_days,
            max_identities,
        )

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _generate_signing_key(self) -> str:
        """Generate a hex-encoded random signing key."""
        return secrets.token_hex(self._key_length)

    @staticmethod
    def _compute_signature(key_hex: str, data: str) -> str:
        """Compute an HMAC-SHA256 signature over *data*."""
        key_bytes = bytes.fromhex(key_hex)
        return hmac.new(key_bytes, data.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _hash_payload(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Identity management
    # ------------------------------------------------------------------

    def register_bot(
        self, bot_id: str, tenant_id: str, ttl_days: Optional[int] = None
    ) -> BotIdentity:
        """Register a new bot and generate its signing key."""
        with self._lock:
            if bot_id in self._identities:
                raise ValueError(f"Bot '{bot_id}' is already registered")
            if len(self._identities) >= self._max_identities:
                raise RuntimeError("Identity registry has reached its capacity")

            ttl = ttl_days if ttl_days is not None else self._default_ttl_days
            now = datetime.now(timezone.utc)
            identity = BotIdentity(
                bot_id=bot_id,
                tenant_id=tenant_id,
                signing_key=self._generate_signing_key(),
                created_at=now,
                expires_at=now + timedelta(days=ttl),
            )
            self._identities[bot_id] = identity
            logger.info("Registered bot '%s' for tenant '%s'", bot_id, tenant_id)
            return identity

    def revoke_identity(self, bot_id: str, reason: str = "") -> bool:
        """Immediately revoke a bot's identity."""
        with self._lock:
            identity = self._identities.get(bot_id)
            if identity is None:
                logger.warning("Revocation failed: bot '%s' not found", bot_id)
                return False
            if identity.status == IdentityStatus.REVOKED:
                logger.warning("Bot '%s' is already revoked", bot_id)
                return False

            identity.status = IdentityStatus.REVOKED
            identity.revoked_at = datetime.now(timezone.utc)
            capped_append(self._revocation_log,
                {"bot_id": bot_id, "reason": reason, "at": identity.revoked_at.isoformat()}
            )
            logger.info("Revoked identity for bot '%s' (reason: %s)", bot_id, reason)
            return True

    def rotate_key(self, bot_id: str) -> Optional[BotIdentity]:
        """Rotate a bot's signing key."""
        with self._lock:
            identity = self._identities.get(bot_id)
            if identity is None or identity.status != IdentityStatus.ACTIVE:
                logger.warning("Key rotation failed for bot '%s'", bot_id)
                return None
            identity.signing_key = self._generate_signing_key()
            logger.info("Rotated signing key for bot '%s'", bot_id)
            return identity

    def get_identity(self, bot_id: str) -> Optional[BotIdentity]:
        with self._lock:
            return self._identities.get(bot_id)

    def list_identities(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[IdentityStatus] = None,
    ) -> List[BotIdentity]:
        with self._lock:
            results = list(self._identities.values())
        if tenant_id is not None:
            results = [i for i in results if i.tenant_id == tenant_id]
        if status is not None:
            results = [i for i in results if i.status == status]
        return results

    # ------------------------------------------------------------------
    # Message signing / verification
    # ------------------------------------------------------------------

    def sign_message(
        self, from_bot: str, to_bot: str, payload: str
    ) -> Optional[SignedMessage]:
        """Sign a message using the sender bot's key."""
        with self._lock:
            identity = self._identities.get(from_bot)

        if identity is None:
            logger.warning("Cannot sign: bot '%s' is not registered", from_bot)
            return None
        if identity.status != IdentityStatus.ACTIVE:
            logger.warning("Cannot sign: bot '%s' status is %s", from_bot, identity.status.value)
            return None
        if identity.is_expired():
            logger.warning("Cannot sign: bot '%s' identity has expired", from_bot)
            return None

        payload_hash = self._hash_payload(payload)
        message_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        sig_data = f"{message_id}:{from_bot}:{to_bot}:{payload_hash}:{now.isoformat()}"
        signature = self._compute_signature(identity.signing_key, sig_data)

        signed = SignedMessage(
            message_id=message_id,
            from_bot=from_bot,
            to_bot=to_bot,
            payload_hash=payload_hash,
            signature=signature,
            timestamp=now,
        )
        logger.debug("Signed message %s from '%s' to '%s'", message_id, from_bot, to_bot)
        return signed

    def verify_message(self, message: SignedMessage) -> VerificationResult:
        """Verify a signed message."""
        with self._lock:
            identity = self._identities.get(message.from_bot)

        if identity is None:
            logger.warning("Verification failed: unknown bot '%s'", message.from_bot)
            return VerificationResult.UNKNOWN_BOT
        if identity.status == IdentityStatus.REVOKED:
            logger.warning("Verification failed: bot '%s' is revoked", message.from_bot)
            return VerificationResult.REVOKED_IDENTITY
        if identity.is_expired() or identity.status == IdentityStatus.EXPIRED:
            logger.warning("Verification failed: bot '%s' identity expired", message.from_bot)
            return VerificationResult.EXPIRED_IDENTITY

        sig_data = (
            f"{message.message_id}:{message.from_bot}:{message.to_bot}"
            f":{message.payload_hash}:{message.timestamp.isoformat()}"
        )
        expected = self._compute_signature(identity.signing_key, sig_data)
        if not hmac.compare_digest(expected, message.signature):
            logger.warning("Verification failed: invalid signature for message %s", message.message_id)
            return VerificationResult.INVALID_SIGNATURE

        logger.debug("Message %s verified successfully", message.message_id)
        return VerificationResult.VALID

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            identities = list(self._identities.values())
        return {
            "total_identities": len(identities),
            "active": sum(1 for i in identities if i.status == IdentityStatus.ACTIVE),
            "revoked": sum(1 for i in identities if i.status == IdentityStatus.REVOKED),
            "expired": sum(1 for i in identities if i.status == IdentityStatus.EXPIRED or i.is_expired()),
            "suspended": sum(1 for i in identities if i.status == IdentityStatus.SUSPENDED),
            "revocation_log_size": len(self._revocation_log),
            "max_identities": self._max_identities,
        }
